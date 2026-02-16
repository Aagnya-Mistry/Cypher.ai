import json
import random
import time
from collections import deque
from email.utils import parsedate_to_datetime
from threading import Lock
from typing import Any

import httpx


class GroqService:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = 'https://api.groq.com/openai/v1',
        timeout_seconds: int = 60,
        max_retries: int = 4,
        requests_per_minute: int = 20,
    ):
        if not api_key.strip():
            raise ValueError('GROQ_API_KEY is not configured')

        if requests_per_minute <= 0:
            raise ValueError('GROQ_REQUESTS_PER_MINUTE must be greater than 0')

        self.api_key = api_key.strip()
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.requests_per_minute = requests_per_minute

        self._rate_lock = Lock()
        self._request_timestamps: deque[float] = deque()

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
        prompt = self._build_prompt(
            domain=domain,
            control_query=control_query,
            context_chunks=context_chunks,
            best_practices=best_practices,
            risk_indicators=risk_indicators,
            missing_areas=missing_areas,
            loop_number=loop_number,
            prior_summaries=prior_summaries or [],
            prior_control_queries=prior_control_queries or [],
        )

        payload = {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a compliance analysis assistant. Return only valid JSON.',
                },
                {
                    'role': 'user',
                    'content': prompt,
                },
            ],
            'temperature': 0,
            'max_tokens': 220,
            'response_format': {'type': 'json_object'},
        }

        try:
            response_json = self._post_with_retries(payload)
        except RuntimeError as exc:
            if self._is_json_generation_error(str(exc)):
                # Retry once with relaxed settings when provider-side JSON mode fails.
                relaxed_payload = {
                    **payload,
                    'max_tokens': 260,
                }
                relaxed_payload.pop('response_format', None)
                relaxed_payload['messages'] = [
                    *payload['messages'],
                    {
                        'role': 'user',
                        'content': (
                            'Return valid JSON only. Do not use markdown fences. '
                            'Output must be exactly one JSON object.'
                        ),
                    },
                ]
                response_json = self._post_with_retries(relaxed_payload)
            else:
                raise

        raw_content = self._extract_content(response_json)
        return self._parse_json_response(raw_content)

    def _post_with_retries(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        timeout = httpx.Timeout(
            timeout=self.timeout_seconds,
            connect=10.0,
            read=self.timeout_seconds,
            write=20.0,
            pool=10.0,
        )

        attempt = 0
        while attempt <= self.max_retries:
            self._wait_for_rate_limit_slot()
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f'{self.base_url}/chat/completions',
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (429, 408, 409) or status >= 500:
                    if attempt == self.max_retries:
                        raise RuntimeError(
                            f'Groq API failed after retries with status {status}: '
                            f'{self._safe_error_message(exc.response)}'
                        ) from exc

                    retry_after = self._parse_retry_after(exc.response.headers.get('Retry-After'))
                    self._sleep_before_retry(attempt, retry_after_seconds=retry_after)
                    attempt += 1
                    continue

                raise RuntimeError(
                    f'Groq API request failed with status {status}: {self._safe_error_message(exc.response)}'
                ) from exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(f'Groq API transport failed after retries: {exc}') from exc

                self._sleep_before_retry(attempt)
                attempt += 1

        raise RuntimeError('Groq API retries exhausted')

    def _wait_for_rate_limit_slot(self) -> None:
        while True:
            with self._rate_lock:
                now = time.time()
                self._evict_old_requests(now)

                if len(self._request_timestamps) < self.requests_per_minute:
                    self._request_timestamps.append(now)
                    return

                oldest = self._request_timestamps[0]
                wait_seconds = max(0.05, 60 - (now - oldest))

            time.sleep(min(wait_seconds, 2.0))

    def _evict_old_requests(self, now: float) -> None:
        cutoff = now - 60
        while self._request_timestamps and self._request_timestamps[0] < cutoff:
            self._request_timestamps.popleft()

    def _sleep_before_retry(self, attempt: int, retry_after_seconds: float | None = None) -> None:
        if retry_after_seconds is not None and retry_after_seconds > 0:
            wait_seconds = min(30.0, retry_after_seconds)
        else:
            base = min(30.0, 1.5 * (2 ** attempt))
            wait_seconds = min(30.0, base + random.uniform(0, 0.35))
        time.sleep(wait_seconds)

    def _parse_retry_after(self, header_value: str | None) -> float | None:
        if not header_value:
            return None

        value = header_value.strip()
        if not value:
            return None

        if value.isdigit():
            return float(value)

        try:
            retry_at = parsedate_to_datetime(value).timestamp()
            delta = retry_at - time.time()
            return max(0.0, delta)
        except Exception:
            return None

    def _extract_content(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get('choices', [])
        if not choices:
            return ''

        message = choices[0].get('message', {})
        content = message.get('content', '')
        if isinstance(content, str):
            return content
        return str(content)

    def _safe_error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            error = data.get('error', {})
            message = error.get('message') or data.get('message')
            if isinstance(message, str) and message.strip():
                return message.strip()
        except Exception:
            pass
        return response.text[:300]

    def _build_prompt(
        self,
        domain: str,
        control_query: str,
        context_chunks: list[str],
        best_practices: list[str],
        risk_indicators: list[str],
        missing_areas: list[str],
        loop_number: int,
        prior_summaries: list[str],
        prior_control_queries: list[str],
    ) -> str:
        chunk_block = '\n\n'.join([f'Chunk {idx + 1}: {chunk}' for idx, chunk in enumerate(context_chunks)])
        best_practices_short = '; '.join(best_practices[:8])
        risk_indicators_short = '; '.join(risk_indicators[:8])
        missing_areas_short = '; '.join(missing_areas[:8])
        prior_summary_block = '; '.join(prior_summaries[:4]) if prior_summaries else 'None'
        prior_query_block = '; '.join(prior_control_queries[:4]) if prior_control_queries else 'None'

        return f"""
Domain: {domain}
Loop number: {loop_number}
Control query: {control_query}

Expected best practices (reference list):
{best_practices_short}

Expected risk indicators (reference list):
{risk_indicators_short}

Current missing areas (prior loops):
{missing_areas_short}

Prior loop summaries:
{prior_summary_block}

Prior loop control queries:
{prior_query_block}

Retrieved compliance report context:
{chunk_block}

Extract structured signals from ONLY the retrieved context.
Return JSON with this exact schema:
{{
  "best_practices_found": ["..."],
  "risk_indicators_found": ["..."],
  "coverage_complete": true/false,
  "missing_areas": ["..."],
  "summary": "..."
}}

Rules:
- Keep arrays concise and factual.
- Do not invent controls that are not in context.
- `missing_areas` should identify what still needs verification.
- Keep `summary` under 60 words.
- Avoid repeating prior loop summary wording; focus on this loop query and evidence.
- If findings are unchanged, still explain why this loop's evidence supports or weakens controls.
- Return JSON only, no markdown.
""".strip()

    def _parse_json_response(self, text: str) -> dict:
        text = text.strip()
        if not text:
            return {
                'best_practices_found': [],
                'risk_indicators_found': [],
                'coverage_complete': False,
                'missing_areas': ['No LLM output received'],
                'summary': '',
            }

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass

        return {
            'best_practices_found': [],
            'risk_indicators_found': [],
            'coverage_complete': False,
            'missing_areas': ['Could not parse LLM JSON output'],
            'summary': text[:500],
        }

    def _is_json_generation_error(self, message: str) -> bool:
        normalized = message.lower()
        return (
            'failed to generate json' in normalized
            or 'failed_generation' in normalized
            or 'json_object' in normalized
        )
