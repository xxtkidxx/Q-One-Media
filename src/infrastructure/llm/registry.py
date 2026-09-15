"""Chọn adapter LLM từ cấu hình, không để worker phụ thuộc nhà cung cấp."""

from __future__ import annotations

from src.infrastructure.llm.claude import ClaudeScriptWriter, ClaudeSegmentAdvisor, LlmRejected
from src.infrastructure.llm.gemini import GeminiScriptWriter, GeminiSegmentAdvisor
from src.infrastructure.llm.openai import OpenAiScriptWriter, OpenAiSegmentAdvisor
from src.shared.config import LLMSettings


def build_segment_advisor(settings: LLMSettings):
    if settings.provider == "gemini":
        return GeminiSegmentAdvisor(api_key=settings.gemini_api_key, model=settings.model)
    if settings.provider == "anthropic":
        return ClaudeSegmentAdvisor(api_key=settings.api_key, model=settings.model)
    if settings.provider == "openai":
        return OpenAiSegmentAdvisor(
            api_key=settings.openai_api_key, model=settings.openai_model
        )
    raise LlmRejected(f"LLM_PROVIDER không hỗ trợ: {settings.provider!r}")


def build_script_writer(settings: LLMSettings):
    if settings.provider == "gemini":
        return GeminiScriptWriter(api_key=settings.gemini_api_key, model=settings.model)
    if settings.provider == "anthropic":
        return ClaudeScriptWriter(api_key=settings.api_key, model=settings.model)
    if settings.provider == "openai":
        return OpenAiScriptWriter(api_key=settings.openai_api_key, model=settings.openai_model)
    raise LlmRejected(f"LLM_PROVIDER không hỗ trợ: {settings.provider!r}")
