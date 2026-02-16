import json
import os
from dataclasses import dataclass
from threading import Lock
from typing import Any

import faiss
import numpy as np


@dataclass(slots=True)
class VectorStoreAddResult:
    vector_ids: list[int]
    total_vectors: int


@dataclass(slots=True)
class VectorStoreSearchHit:
    vector_id: int
    score: float
    metadata: dict[str, Any]


class FaissVectorStore:
    def __init__(self, index_path: str, metadata_path: str):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self._lock = Lock()

    def add_embeddings(self, embeddings: np.ndarray, metadatas: list[dict[str, Any]]) -> VectorStoreAddResult:
        if embeddings.ndim != 2:
            raise ValueError('Embeddings must be a 2D array')
        if embeddings.shape[0] != len(metadatas):
            raise ValueError('Embeddings and metadata lengths do not match')

        if embeddings.shape[0] == 0:
            return VectorStoreAddResult(vector_ids=[], total_vectors=self._existing_total_vectors())

        with self._lock:
            index = self._load_or_create_index(embeddings.shape[1])
            current_total = index.ntotal

            index.add(embeddings)
            faiss.write_index(index, self.index_path)

            vector_ids = list(range(current_total, current_total + embeddings.shape[0]))
            self._append_metadata(vector_ids, metadatas)

            return VectorStoreAddResult(vector_ids=vector_ids, total_vectors=index.ntotal)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        user_id: str | None = None,
        report_name: str | None = None,
    ) -> list[VectorStoreSearchHit]:
        if top_k <= 0:
            return []

        if not os.path.exists(self.index_path):
            return []

        if query_embedding.ndim == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0)

        if query_embedding.ndim != 2 or query_embedding.shape[0] != 1:
            raise ValueError('query_embedding must be shape (1, dim)')

        index = faiss.read_index(self.index_path)
        if index.ntotal == 0:
            return []

        if index.d != query_embedding.shape[1]:
            raise ValueError(f'Query dimension {query_embedding.shape[1]} does not match index dimension {index.d}')

        metadata_by_vector_id = self._load_metadata_map()

        overfetch = min(index.ntotal, max(top_k * 8, top_k + 20))
        scores, indices = index.search(query_embedding.astype(np.float32), overfetch)

        requested_report_name = self._normalize_optional_text(report_name)

        hits: list[VectorStoreSearchHit] = []
        seen_texts: set[str] = set()
        for score, vector_id in zip(scores[0], indices[0]):
            if vector_id < 0:
                continue

            metadata = metadata_by_vector_id.get(int(vector_id))
            if metadata is None:
                continue

            if user_id and metadata.get('user_id') != user_id:
                continue

            metadata_report_name = self._normalize_optional_text(metadata.get('report_name'))
            if requested_report_name and metadata_report_name != requested_report_name:
                continue

            text_key = ' '.join(str(metadata.get('text', '')).split()).lower()
            if text_key and text_key in seen_texts:
                continue

            hits.append(
                VectorStoreSearchHit(
                    vector_id=int(vector_id),
                    score=float(score),
                    metadata=metadata,
                )
            )
            if text_key:
                seen_texts.add(text_key)

            if len(hits) >= top_k:
                break

        return hits

    def _load_or_create_index(self, dim: int) -> faiss.Index:
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        if os.path.exists(self.index_path):
            index = faiss.read_index(self.index_path)
            if index.d != dim:
                raise ValueError(
                    f'Existing FAISS index dimension {index.d} does not match embedding dimension {dim}.'
                )
            return index

        return faiss.IndexFlatIP(dim)

    def _append_metadata(self, vector_ids: list[int], metadatas: list[dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)
        existing = []

        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, 'r', encoding='utf-8') as file:
                existing = json.load(file)

        for vector_id, metadata in zip(vector_ids, metadatas):
            existing.append({'vector_id': vector_id, **metadata})

        with open(self.metadata_path, 'w', encoding='utf-8') as file:
            json.dump(existing, file, indent=2)

    def _load_metadata_map(self) -> dict[int, dict[str, Any]]:
        if not os.path.exists(self.metadata_path):
            return {}

        with open(self.metadata_path, 'r', encoding='utf-8') as file:
            items = json.load(file)

        result: dict[int, dict[str, Any]] = {}
        for item in items:
            vector_id = item.get('vector_id')
            if isinstance(vector_id, int):
                result[vector_id] = item
        return result

    def _existing_total_vectors(self) -> int:
        if not os.path.exists(self.index_path):
            return 0
        index = faiss.read_index(self.index_path)
        return index.ntotal

    def _normalize_optional_text(self, value: Any) -> str:
        if value is None:
            return ''
        return ' '.join(str(value).strip().lower().split())
