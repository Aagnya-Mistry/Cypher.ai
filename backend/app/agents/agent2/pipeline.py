from app.schemas.agent2 import Agent2ChatResponse, Agent2LoopMessage, RetrievedChunk, StructuredAnswer
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_base_service import DomainKnowledge, KnowledgeBaseService
from app.services.vector_store_service import FaissVectorStore, VectorStoreSearchHit


class StructuredSignalExtractor:
    def extract_structured_signals(
        self,
        domain: str,
        control_query: str,
        context_chunks: list[str],
        best_practices: list[str],
        risk_indicators: list[str],
        missing_areas: list[str],
        loop_number: int = 1,
        prior_summaries: list[str] | None = None,
        prior_control_queries: list[str] | None = None,
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
        loops_limit = 5

        missing_areas = list(domain_cfg.keywords)
        conversation: list[Agent2LoopMessage] = []

        covered_best: set[str] = set()
        covered_risk: set[str] = set()
        used_vector_ids: set[int] = set()
        reached_coverage = False

        for loop_idx in range(loops_limit):
            control_query = self._build_control_query(domain_cfg, loop_idx, missing_areas)

            query_embedding = self.embedding_service.embed_texts([control_query])
            retrieval_top_k = max(top_k, 8)
            hits = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=retrieval_top_k,
                user_id=user_id,
                report_name=report_name,
            )
            if not hits and report_name:
                # Fallback in case report-name filter is stale/mismatched in UI input.
                hits = self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=retrieval_top_k,
                    user_id=user_id,
                    report_name=None,
                )

            llm_hits_limit = max(1, min(top_k, 5))
            selected_hits = self._select_hits_for_loop(
                hits=hits,
                used_vector_ids=used_vector_ids,
                limit=llm_hits_limit,
            )

            # If uniqueness filtering removed too many hits, retry with a loop-specific expanded query.
            if len(selected_hits) < llm_hits_limit:
                expanded_query = self._build_expanded_query(control_query, loop_idx, missing_areas)
                expanded_embedding = self.embedding_service.embed_texts([expanded_query])
                expanded_hits = self.vector_store.search(
                    query_embedding=expanded_embedding,
                    top_k=retrieval_top_k,
                    user_id=user_id,
                    report_name=report_name,
                )
                selected_hits = self._merge_unique_hits(
                    primary=selected_hits,
                    fallback=expanded_hits,
                    used_vector_ids=used_vector_ids,
                    limit=llm_hits_limit,
                )
            context_chunks = [
                self._trim_chunk_for_llm(hit.metadata.get('text', ''))
                for hit in selected_hits
                if hit.metadata.get('text')
            ]
            if not context_chunks:
                raise ValueError('No indexed chunks found. Run Agent 1 document processing first.')

            for hit in selected_hits:
                used_vector_ids.add(hit.vector_id)

            prior_summaries = [loop.llm_answer.summary for loop in conversation if loop.llm_answer.summary]
            prior_queries = [loop.control_query for loop in conversation if loop.control_query]
            try:
                llm_raw = self.llm_service.extract_structured_signals(
                    domain=domain_cfg.key,
                    control_query=control_query,
                    context_chunks=context_chunks,
                    best_practices=domain_cfg.best_practices,
                    risk_indicators=domain_cfg.risk_indicators,
                    missing_areas=missing_areas,
                    loop_number=loop_idx + 1,
                    prior_summaries=prior_summaries[-4:],
                    prior_control_queries=prior_queries[-4:],
                )
            except Exception as exc:
                llm_raw = self._fallback_structured_answer(
                    domain_cfg=domain_cfg,
                    context_chunks=context_chunks,
                    error_message=str(exc),
                    control_query=control_query,
                    loop_number=loop_idx + 1,
                )

            llm_answer = self._normalize_llm_answer(llm_raw)

            covered_best.update(self._match_covered(domain_cfg.best_practices, llm_answer.best_practices_found))
            covered_risk.update(self._match_covered(domain_cfg.risk_indicators, llm_answer.risk_indicators_found))

            coverage_score = self._coverage_score(domain_cfg, covered_best, covered_risk)
            best_ratio = len(covered_best) / max(1, len(domain_cfg.best_practices))
            no_risk_indicators = len(covered_risk) == 0
            heuristic_coverage = best_ratio >= 0.7 and no_risk_indicators
            coverage_complete = llm_answer.coverage_complete or coverage_score >= threshold or heuristic_coverage
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
                        for hit in selected_hits
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
        control_query: str,
        loop_number: int,
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
                f'Loop {loop_number}: fallback extraction for control query '
                f'"{control_query[:120]}". Error: {error_message[:180]}'
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

    def _select_hits_for_loop(
        self,
        hits: list[VectorStoreSearchHit],
        used_vector_ids: set[int],
        limit: int,
    ) -> list[VectorStoreSearchHit]:
        unseen = [hit for hit in hits if hit.vector_id not in used_vector_ids]
        selected = unseen[:limit]
        if selected:
            return selected
        return hits[:limit]

    def _merge_unique_hits(
        self,
        primary: list[VectorStoreSearchHit],
        fallback: list[VectorStoreSearchHit],
        used_vector_ids: set[int],
        limit: int,
    ) -> list[VectorStoreSearchHit]:
        selected: list[VectorStoreSearchHit] = list(primary)
        selected_ids = {hit.vector_id for hit in selected}
        for hit in fallback:
            if len(selected) >= limit:
                break
            if hit.vector_id in selected_ids:
                continue
            if hit.vector_id in used_vector_ids and len(selected) < max(1, limit // 2):
                # Prefer unseen hits, but allow a few seen hits if needed to avoid empty context.
                continue
            selected.append(hit)
            selected_ids.add(hit.vector_id)

        if len(selected) < limit:
            for hit in fallback:
                if len(selected) >= limit:
                    break
                if hit.vector_id in selected_ids:
                    continue
                selected.append(hit)
                selected_ids.add(hit.vector_id)
        return selected

    def _build_expanded_query(self, control_query: str, loop_idx: int, missing_areas: list[str]) -> str:
        focus = ', '.join(missing_areas[:5]) if missing_areas else 'remaining controls'
        return (
            f'{control_query} Loop {loop_idx + 1} follow-up. '
            f'Find different evidence related to: {focus}.'
        )
