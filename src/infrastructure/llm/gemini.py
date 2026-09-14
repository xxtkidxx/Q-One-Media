"""Adapter Gemini cho chọn đoạn và viết kịch bản, gọi REST chính thức."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from src.infrastructure.llm.claude import (
    ClaudeScriptWriter,
    ClaudeSegmentAdvisor,
    LlmFailed,
    LlmRejected,
)


@dataclass
class _GeminiBase:
    api_key: str
    model: str = "gemini-3.5-flash-lite"
    max_tokens: int = 4096

    def __post_init__(self) -> None:
        if not self.api_key:
            raise LlmRejected("thiếu GEMINI_API_KEY")

    def _call_tool(self, *, system: str, prompt: str, tool: dict[str, Any]) -> dict[str, Any]:
        # Gemini hỗ trợ JSON Schema trực tiếp. Dùng schema của tool hiện hữu để
        # hai provider chịu cùng một hợp đồng đầu ra và cùng lớp kiểm tra phía sau.
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
                "responseJsonSchema": tool["input_schema"],
            },
        }
        try:
            response = httpx.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LlmFailed(f"{type(exc).__name__}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            error = f"Gemini HTTP {code}: {exc.response.text[:500]}"
            if code == 429 or code >= 500:
                raise LlmFailed(error) from exc
            raise LlmRejected(error) from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LlmFailed(f"phản hồi Gemini không hợp lệ: {exc}") from exc
        if not isinstance(data, dict):
            raise LlmFailed("Gemini không trả về JSON object")
        return data


class GeminiSegmentAdvisor(_GeminiBase, ClaudeSegmentAdvisor):
    """Dùng quy tắc/prompt chọn đoạn chung, thay phần gọi model bằng Gemini."""


class GeminiScriptWriter(_GeminiBase, ClaudeScriptWriter):
    """Dùng quy tắc/prompt viết kịch bản chung, thay phần gọi model bằng Gemini."""
