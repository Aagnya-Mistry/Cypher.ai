from datetime import datetime, timezone

from app.schemas.agent2 import Agent2ChatResponse
from app.schemas.agent3 import Agent3FinalReport, DomainScoreResult
from app.services.agent3_store_service import Agent3ScoreStore, DomainScoreRecord
from app.services.knowledge_base_service import KnowledgeBaseService


class Agent3RiskScoringPipeline:
    def __init__(self, knowledge_base: KnowledgeBaseService, store: Agent3ScoreStore):
        self.knowledge_base = knowledge_base
        self.store = store

    def score_domain(self, user_id: str, report_name: str, agent2_result: Agent2ChatResponse) -> DomainScoreResult:
        domain_cfg = self.knowledge_base.get_domain(agent2_result.domain)
        threshold = self.knowledge_base.get_threshold(agent2_result.domain)

        found_best = self._collect_unique_texts(
            [loop.llm_answer.best_practices_found for loop in agent2_result.conversation]
        )
        found_risk = self._collect_unique_texts(
            [loop.llm_answer.risk_indicators_found for loop in agent2_result.conversation]
        )
        found_missing = self._collect_unique_texts(
            [loop.llm_answer.missing_areas for loop in agent2_result.conversation]
        )

        matched_best = self._match_expected(domain_cfg.best_practices, found_best)
        matched_risk = self._match_expected(domain_cfg.risk_indicators, found_risk)

        expected_best_count = max(1, len(domain_cfg.best_practices))
        expected_risk_count = max(1, len(domain_cfg.risk_indicators))
        expected_total = max(1, len(domain_cfg.best_practices) + len(domain_cfg.risk_indicators))

        best_ratio = len(matched_best) / expected_best_count
        risk_ratio = len(matched_risk) / expected_risk_count
        missing_ratio = min(1.0, len(found_missing) / expected_total)
        coverage_score = float(agent2_result.final_coverage_score)

        # Deterministic domain score:
        # +coverage and +best-practice matches increase score, while risk matches and missing areas reduce it.
        domain_score = (
            0.50 * coverage_score
            + 0.35 * best_ratio
            + 0.10 * (1.0 - risk_ratio)
            + 0.05 * (1.0 - missing_ratio)
        )
        domain_score = max(0.0, min(1.0, domain_score))

        passes_threshold = domain_score >= threshold
        risk_level = self._risk_level(domain_score, threshold)
        updated_at = self._utc_now_iso()

        result = DomainScoreResult(
            report_name=report_name,
            domain=agent2_result.domain,
            domain_score=round(domain_score, 4),
            threshold=round(float(threshold), 4),
            passes_threshold=passes_threshold,
            risk_level=risk_level,
            coverage_score=round(coverage_score, 4),
            best_practice_match_ratio=round(best_ratio, 4),
            risk_indicator_match_ratio=round(risk_ratio, 4),
            missing_area_ratio=round(missing_ratio, 4),
            loops_run=agent2_result.loops_run,
            matched_best_practices=matched_best,
            matched_risk_indicators=matched_risk,
            updated_at=updated_at,
        )

        self.store.upsert_domain_score(
            DomainScoreRecord(
                user_id=user_id,
                report_name=report_name,
                domain=agent2_result.domain,
                payload=result.model_dump(),
            )
        )

        return result

    def generate_report(self, user_id: str, report_name: str) -> Agent3FinalReport:
        rows = self.store.list_domain_scores(user_id=user_id, report_name=report_name)
        if not rows:
            raise ValueError('No Agent 3 domain scores found for this report. Score at least one domain first.')

        domain_results = [DomainScoreResult(**row) for row in rows]

        total_domains = len(domain_results)
        aggregate_score = sum(item.domain_score for item in domain_results) / total_domains
        average_threshold = sum(item.threshold for item in domain_results) / total_domains
        domains_meeting = sum(1 for item in domain_results if item.passes_threshold)
        domains_below = total_domains - domains_meeting

        if domains_below == 0:
            overall_status = 'Pass'
        elif domains_meeting >= max(1, int(total_domains * 0.6)):
            overall_status = 'Needs Attention'
        else:
            overall_status = 'High Risk'

        return Agent3FinalReport(
            report_name=report_name,
            generated_at=self._utc_now_iso(),
            total_domains_scored=total_domains,
            aggregate_score=round(aggregate_score, 4),
            average_threshold=round(average_threshold, 4),
            domains_meeting_threshold=domains_meeting,
            domains_below_threshold=domains_below,
            overall_status=overall_status,
            domain_results=domain_results,
        )

    def build_excel_rows(self, report: Agent3FinalReport) -> tuple[list[str], list[list[str]]]:
        header = [
            'Report Name',
            'Domain',
            'Domain Score',
            'Threshold',
            'Passes Threshold',
            'Risk Level',
            'Coverage Score',
            'Best Practice Match Ratio',
            'Risk Indicator Match Ratio',
            'Missing Area Ratio',
            'Loops Run',
            'Updated At',
        ]
        rows: list[list[str]] = []
        for item in report.domain_results:
            rows.append(
                [
                    item.report_name,
                    item.domain,
                    f'{item.domain_score:.4f}',
                    f'{item.threshold:.4f}',
                    'Yes' if item.passes_threshold else 'No',
                    item.risk_level,
                    f'{item.coverage_score:.4f}',
                    f'{item.best_practice_match_ratio:.4f}',
                    f'{item.risk_indicator_match_ratio:.4f}',
                    f'{item.missing_area_ratio:.4f}',
                    str(item.loops_run),
                    item.updated_at,
                ]
            )
        return header, rows

    def _risk_level(self, score: float, threshold: float) -> str:
        if score >= max(0.85, threshold + 0.1):
            return 'Low'
        if score >= threshold:
            return 'Moderate'
        return 'High'

    def _collect_unique_texts(self, lists: list[list[str]]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for values in lists:
            for value in values:
                norm = self._normalize_text(value)
                if norm and norm not in seen:
                    seen.add(norm)
                    result.append(value.strip())
        return result

    def _match_expected(self, expected: list[str], found: list[str]) -> list[str]:
        matched: list[str] = []
        found_norm = [self._normalize_text(item) for item in found]
        for item in expected:
            item_norm = self._normalize_text(item)
            for found_item_norm in found_norm:
                if not found_item_norm:
                    continue
                if found_item_norm in item_norm or item_norm in found_item_norm:
                    matched.append(item)
                    break
        return matched

    def _normalize_text(self, text: str) -> str:
        return ' '.join(str(text).lower().strip().split())

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
