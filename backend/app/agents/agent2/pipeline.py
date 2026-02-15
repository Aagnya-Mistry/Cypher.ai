from app.schemas.agent2 import Agent2ChatResponse, Agent2LoopMessage, RetrievedChunk, StructuredAnswer
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_base_service import DomainKnowledge, KnowledgeBaseService
from app.services.vector_store_service import FaissVectorStore


class StructuredSignalExtractor:
    def extract_structured_signals(
        self,
        domain: str,
        control_query: str,
        context_chunks: list[str],
        best_practices: list[str],
        risk_indicators: list[str],
        missing_areas: list[str],
    ) -> dict:
        raise NotImplementedError


class Agent2RagReasoningPipeline:
    def __init__(
        self,
        knowledge_base: KnowledgeBaseService,
        embedding_service: EmbeddingService,
        vector_store: FaissVectorStore,
        llm_service: StructuredSignalExtractor,
        max_loops: int,
    ):
        self.knowledge_base = knowledge_base
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_service = llm_service
        self.max_loops = max_loops

    def run(
        self,
        user_id: str,
        domain: str,
        top_k: int,
        report_name: str | None = None,
        max_loops_override: int | None = None,
    ) -> Agent2ChatResponse:
        domain_cfg = self.knowledge_base.get_domain(domain)
        threshold = self.knowledge_base.get_threshold(domain)
        loops_limit = 6

        missing_areas = list(domain_cfg.keywords)
        conversation: list[Agent2LoopMessage] = []

        covered_best: set[str] = set()
        covered_risk: set[str] = set()
        llm_available = True
        llm_error_message = ''
        reached_coverage = False

        for loop_idx in range(loops_limit):
            control_query = self._build_control_query(domain_cfg, loop_idx, missing_areas)

            query_embedding = self.embedding_service.embed_texts([control_query])
            hits = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                user_id=user_id,
                report_name=report_name,
            )

            llm_hits_limit = max(1, min(top_k, 5))
            selected_hits = hits[:llm_hits_limit]
            context_chunks = [
                self._trim_chunk_for_llm(hit.metadata.get('text', ''))
                for hit in selected_hits
                if hit.metadata.get('text')
            ]
            if not context_chunks:
                raise ValueError('No indexed chunks found. Run Agent 1 document processing first.')

            if llm_available:
                try:
                    llm_raw = self.llm_service.extract_structured_signals(
                        domain=domain_cfg.key,
                        control_query=control_query,
                        context_chunks=context_chunks,
                        best_practices=domain_cfg.best_practices,
                        risk_indicators=domain_cfg.risk_indicators,
                        missing_areas=missing_areas,
                    )
                except Exception as exc:
                    llm_available = False
                    llm_error_message = str(exc)
                    llm_raw = self._fallback_structured_answer(
                        domain_cfg=domain_cfg,
                        context_chunks=context_chunks,
                        error_message=llm_error_message,
                    )
            else:
                llm_raw = self._fallback_structured_answer(
                    domain_cfg=domain_cfg,
                    context_chunks=context_chunks,
                    error_message=(
                        'LLM unavailable for this run after previous failure. '
                        f'Previous error: {llm_error_message[:180]}'
                    ),
                )

            llm_answer = self._normalize_llm_answer(llm_raw)

            covered_best.update(self._match_covered(domain_cfg.best_practices, llm_answer.best_practices_found))
            covered_risk.update(self._match_covered(domain_cfg.risk_indicators, llm_answer.risk_indicators_found))

            coverage_score = self._coverage_score(domain_cfg, covered_best, covered_risk)
            coverage_complete = llm_answer.coverage_complete or coverage_score >= threshold
            if coverage_complete:
                reached_coverage = True

            missing_areas = self._build_missing_areas(domain_cfg, covered_best, covered_risk)
            if llm_answer.missing_areas:
                missing_areas = list(dict.fromkeys(missing_areas + llm_answer.missing_areas))

            conversation.append(
                Agent2LoopMessage(
                    loop_number=loop_idx + 1,
                    control_query=control_query,
                    retrieved_chunks=[
                        RetrievedChunk(
                            vector_id=hit.vector_id,
                            score=hit.score,
                            text_preview=(hit.metadata.get('text') or '')[:240],
                        )
                        for hit in hits
                    ],
                    llm_answer=llm_answer,
                )
            )

        final_score = self._coverage_score(domain_cfg, covered_best, covered_risk)
        return Agent2ChatResponse(
            domain=domain,
            loops_run=loops_limit,
            coverage_complete=reached_coverage or final_score >= threshold,
            final_coverage_score=round(final_score, 4),
            threshold=threshold,
            conversation=conversation,
        )

    def _build_control_query(self, domain: DomainKnowledge, loop_idx: int, missing_areas: list[str]) -> str:
        templates = domain.follow_up_templates
        if not templates:
            base = f'Provide evidence for controls in domain: {domain.key}.'
        else:
            base = templates[loop_idx % len(templates)]

        if missing_areas:
            focus = ', '.join(missing_areas[:4])
            return f'{base} Focus specifically on: {focus}.'

        return base

    def _normalize_llm_answer(self, data: dict) -> StructuredAnswer:
        best_practices_found = self._as_str_list(data.get('best_practices_found'))
        risk_indicators_found = self._as_str_list(data.get('risk_indicators_found'))
        missing_areas = self._as_str_list(data.get('missing_areas'))

        return StructuredAnswer(
            best_practices_found=best_practices_found,
            risk_indicators_found=risk_indicators_found,
            coverage_complete=bool(data.get('coverage_complete', False)),
            missing_areas=missing_areas,
            summary=str(data.get('summary', '')).strip(),
        )

    def _coverage_score(self, domain: DomainKnowledge, covered_best: set[str], covered_risk: set[str]) -> float:
        total = len(domain.best_practices) + len(domain.risk_indicators)
        if total == 0:
            return 1.0

        covered = len(covered_best) + len(covered_risk)
        return covered / total

    def _match_covered(self, expected: list[str], found: list[str]) -> set[str]:
        matched: set[str] = set()
        expected_norm = {item: self._normalize_text(item) for item in expected}

        for found_item in found:
            found_norm = self._normalize_text(found_item)
            for expected_item, expected_item_norm in expected_norm.items():
                if not found_norm:
                    continue
                if found_norm in expected_item_norm or expected_item_norm in found_norm:
                    matched.add(expected_item)

        return matched

    def _build_missing_areas(
        self,
        domain: DomainKnowledge,
        covered_best: set[str],
        covered_risk: set[str],
    ) -> list[str]:
        remaining_best = [item for item in domain.best_practices if item not in covered_best]
        remaining_risk = [item for item in domain.risk_indicators if item not in covered_risk]
        return remaining_best + remaining_risk

    def _normalize_text(self, text: str) -> str:
        return ' '.join(text.lower().strip().split())

    def _as_str_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _fallback_structured_answer(
        self,
        domain_cfg: DomainKnowledge,
        context_chunks: list[str],
        error_message: str,
    ) -> dict:
        context_text = ' '.join(context_chunks).lower()

        best_practices_found = [
            item for item in domain_cfg.best_practices if self._has_token_overlap(item, context_text)
        ]
        risk_indicators_found = [
            item for item in domain_cfg.risk_indicators if self._has_token_overlap(item, context_text)
        ]

        remaining_best = [item for item in domain_cfg.best_practices if item not in best_practices_found]
        remaining_risk = [item for item in domain_cfg.risk_indicators if item not in risk_indicators_found]

        return {
            'best_practices_found': best_practices_found,
            'risk_indicators_found': risk_indicators_found,
            'coverage_complete': False,
            'missing_areas': remaining_best + remaining_risk,
            'summary': (
                'Fallback extraction used because LLM call failed. '
                f'Error: {error_message[:240]}'
            ),
        }

    def _has_token_overlap(self, phrase: str, haystack: str) -> bool:
        tokens = [token for token in self._normalize_text(phrase).split() if len(token) >= 4]
        if not tokens:
            return False
        hits = sum(1 for token in tokens if token in haystack)
        return hits >= max(1, len(tokens) // 2)

    def _trim_chunk_for_llm(self, text: str, max_chars: int = 700) -> str:
        normalized = ' '.join(str(text).split())
        return normalized[:max_chars]
