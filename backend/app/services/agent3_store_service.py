import json
import os
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(slots=True)
class DomainScoreRecord:
    user_id: str
    report_name: str
    domain: str
    payload: dict[str, Any]


class Agent3ScoreStore:
    def __init__(self, store_path: str):
        self.store_path = store_path
        self._lock = Lock()

    def upsert_domain_score(self, record: DomainScoreRecord) -> None:
        with self._lock:
            items = self._load_items()
            updated = False

            for item in items:
                if (
                    item.get('user_id') == record.user_id
                    and item.get('report_name') == record.report_name
                    and item.get('domain') == record.domain
                ):
                    item.update(record.payload)
                    item['user_id'] = record.user_id
                    item['report_name'] = record.report_name
                    item['domain'] = record.domain
                    updated = True
                    break

            if not updated:
                items.append(
                    {
                        'user_id': record.user_id,
                        'report_name': record.report_name,
                        'domain': record.domain,
                        **record.payload,
                    }
                )

            self._save_items(items)

    def list_domain_scores(self, user_id: str, report_name: str) -> list[dict[str, Any]]:
        items = self._load_items()
        result = [
            item
            for item in items
            if item.get('user_id') == user_id and item.get('report_name') == report_name
        ]
        result.sort(key=lambda row: row.get('domain', ''))
        return result

    def _load_items(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.store_path):
            return []

        with open(self.store_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        if isinstance(data, list):
            return data
        return []

    def _save_items(self, items: list[dict[str, Any]]) -> None:
        parent = os.path.dirname(self.store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(self.store_path, 'w', encoding='utf-8') as file:
            json.dump(items, file, indent=2)
