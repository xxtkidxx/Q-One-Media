"""Adapter OpenAI API cho chọn đoạn và viết kịch bản bằng structured outputs."""

from __future__ import annotations

import json
from copy import deepcopy
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
class _OpenAiBase:
    api_key: str
    model: str = "gpt-5.6-luna"
    max_tokens: int = 4096

    def __post_init__(self) -> None:
        if not self.api_key:
            raise LlmRejected("thiếu OPENAI_API_KEY")

    def _call_tool(self, *, system: str, prompt: str, tool: dict[str, Any]) -> dict[str, Any]:
        schema = deepcopy(tool["input_schema"])
        _close_objects(schema)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": self.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": tool["name"],
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LlmFailed(f"{type(exc).__name__}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            error = f"OpenAI HTTP {code}: {exc.response.text[:500]}"
            if code == 429 or code >= 500:
                raise LlmFailed(error) from exc
            raise LlmRejected(error) from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LlmFailed(f"phản hồi OpenAI không hợp lệ: {exc}") from exc
        if not isinstance(data, dict):
            raise LlmFailed("OpenAI không trả về JSON object")
        return data


def _close_objects(schema: dict[str, Any]) -> None:
    """OpenAI strict schema yêu cầu mọi object từ chối thuộc tính ngoài hợp đồng."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        for child in schema.get("properties", {}).values():
            _close_objects(child)
    items = schema.get("items")
    if isinstance(items, dict):
        _close_objects(items)


class OpenAiSegmentAdvisor(_OpenAiBase, ClaudeSegmentAdvisor):
    """Dùng chung prompt và kiểm tra đầu ra của bộ chọn đoạn."""


class OpenAiScriptWriter(_OpenAiBase, ClaudeScriptWriter):
    """Dùng chung prompt và kiểm tra đầu ra của bộ viết kịch bản."""
