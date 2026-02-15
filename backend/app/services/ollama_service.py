import json

import httpx


class OllamaService:
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 120):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract_structured_signals(
        self,
        domain: str,
        control_query: str,
        context_chunks: list[str],
        best_practices: list[str],
        risk_indicators: list[str],
        missing_areas: list[str],
    ) -> dict:
        prompt = self._build_prompt(
            domain=domain,
            control_query=control_query,
            context_chunks=context_chunks,
            best_practices=best_practices,
            risk_indicators=risk_indicators,
            missing_areas=missing_areas,
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
            'stream': False,
            'keep_alive': '30m',
            'options': {
                'temperature': 0,
                'num_predict': 220,
                'num_ctx': 2048,
            },
        }

        response_json = self._post_chat(payload)
        raw_content = response_json.get('message', {}).get('content', '')
        return self._parse_json_response(raw_content)

    def _post_chat(self, payload: dict) -> dict:
        timeout = httpx.Timeout(
            timeout=self.timeout_seconds,
            connect=8.0,
            read=self.timeout_seconds,
            write=20.0,
            pool=8.0,
        )
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f'{self.base_url}/api/chat', json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            retry_payload = {
                **payload,
                'options': {
                    **payload.get('options', {}),
                    'num_predict': 140,
                },
            }
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f'{self.base_url}/api/chat', json=retry_payload)
                response.raise_for_status()
                return response.json()

    def _build_prompt(
        self,
        domain: str,
        control_query: str,
        context_chunks: list[str],
        best_practices: list[str],
        risk_indicators: list[str],
        missing_areas: list[str],
    ) -> str:
        chunk_block = '\n\n'.join([f'Chunk {idx + 1}: {chunk}' for idx, chunk in enumerate(context_chunks)])
        best_practices_short = '; '.join(best_practices[:8])
        risk_indicators_short = '; '.join(risk_indicators[:8])
        missing_areas_short = '; '.join(missing_areas[:8])

        return f"""
Domain: {domain}
Control query: {control_query}

Expected best practices (reference list):
{best_practices_short}

Expected risk indicators (reference list):
{risk_indicators_short}

Current missing areas (prior loops):
{missing_areas_short}

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
