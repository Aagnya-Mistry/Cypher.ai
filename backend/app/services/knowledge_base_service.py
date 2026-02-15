import json
import os
from dataclasses import dataclass


@dataclass(slots=True)
class DomainKnowledge:
    key: str
    follow_up_templates: list[str]
    best_practices: list[str]
    risk_indicators: list[str]
    keywords: list[str]


class KnowledgeBaseService:
    def __init__(self, knowledge_base_path: str):
        self.knowledge_base_path = knowledge_base_path
        self._cached_data: dict | None = None

    def list_domains(self) -> list[str]:
        data = self._load_data()
        domains = data.get('domains', {})
        return sorted(domains.keys())

    def get_domain(self, domain_key: str) -> DomainKnowledge:
        data = self._load_data()
        domains = data.get('domains', {})
        domain = domains.get(domain_key)
        if domain is None:
            raise ValueError(f'Unknown domain: {domain_key}')

        return DomainKnowledge(
            key=domain_key,
            follow_up_templates=domain.get('follow_up_templates', []),
            best_practices=domain.get('best_practices', []),
            risk_indicators=domain.get('risk_indicators', []),
            keywords=domain.get('keywords', []),
        )

    def get_threshold(self, domain_key: str) -> float:
        data = self._load_data()
        thresholds = data.get('risk_thresholds', {})
        return float(thresholds.get(domain_key, 0.7))

    def _load_data(self) -> dict:
        if self._cached_data is not None:
            return self._cached_data

        resolved_path = self._resolve_path()
        with open(resolved_path, 'r', encoding='utf-8') as file:
            self._cached_data = json.load(file)

        return self._cached_data

    def _resolve_path(self) -> str:
        if os.path.exists(self.knowledge_base_path):
            return self.knowledge_base_path

        backend_relative = os.path.join('backend', self.knowledge_base_path)
        if os.path.exists(backend_relative):
            return backend_relative

        raise FileNotFoundError(f'knowledge base file not found: {self.knowledge_base_path}')
