"""Adapter LLM — phần kiểm tra đầu ra của model, không gọi API thật.

Model là thành phần không xác định, nên mọi thứ nó trả về phải được kiểm. Nhóm
test này kiểm đúng phần kiểm đó.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.infrastructure.llm.claude import (
    ClaudeScriptWriter,
    ClaudeSegmentAdvisor,
    LlmFailed,
    LlmRejected,
    format_transcript_with_timestamps,
    load_glossary_json,
)
from src.infrastructure.llm.gemini import GeminiSegmentAdvisor
from src.infrastructure.llm.registry import build_script_writer, build_segment_advisor
from src.shared.config import LLMSettings


class StubAdvisor(ClaudeSegmentAdvisor):
    """Thay _call_tool để không gọi mạng."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(api_key="test-key")
        self._payload = payload
        self.prompts: list[str] = []

    def _call_tool(self, *, system: str, prompt: str, tool: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(prompt)
        return self._payload


class StubWriter(ClaudeScriptWriter):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(api_key="test-key")
        self._payload = payload
        self.prompts: list[str] = []

    def _call_tool(self, *, system: str, prompt: str, tool: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(prompt)
        return self._payload


# ---------------- Thiếu khoá ----------------


def test_thieu_api_key_thi_bao_loi_khong_retry():
    with pytest.raises(LlmRejected):
        ClaudeSegmentAdvisor(api_key="")


def test_gemini_thieu_api_key_thi_bao_dung_ten_bien():
    with pytest.raises(LlmRejected, match="GEMINI_API_KEY"):
        GeminiSegmentAdvisor(api_key="")


def test_registry_chon_provider_da_cau_hinh():
    gemini = LLMSettings(
        provider="gemini", gemini_api_key="g-key", model="gemini-3.5-flash-lite"
    )
    assert isinstance(build_segment_advisor(gemini), GeminiSegmentAdvisor)

    anthropic = LLMSettings(provider="anthropic", api_key="a-key", model="claude-test")
    assert isinstance(build_script_writer(anthropic), ClaudeScriptWriter)


def test_registry_tu_choi_provider_khong_ho_tro():
    with pytest.raises(LlmRejected, match="không hỗ trợ"):
        build_segment_advisor(LLMSettings(provider="unknown"))


def test_gemini_doc_json_schema_va_doc_ket_qua(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": '{"proposals": '
                    '[{"start_sec": 10, "end_sec": 70, "rationale": "có biểu đồ"}]}'
                }]}}]
            }

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("src.infrastructure.llm.gemini.httpx.post", fake_post)
    advisor = GeminiSegmentAdvisor(api_key="g-key", model="gemini-test")
    assert advisor.propose(transcript="[00:10] dữ kiện", duration_sec=100) == [
        (10.0, 70.0, "có biểu đồ")
    ]
    assert captured["headers"]["x-goog-api-key"] == "g-key"
    config = captured["json"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"]["required"] == ["proposals"]


# ---------------- Kiểm đề xuất đoạn ----------------


def test_de_xuat_vuot_do_dai_video_bi_kep_lai():
    """Model đôi khi đề xuất quá phần cuối. Kẹp, chứ không tin tưởng."""
    advisor = StubAdvisor({"proposals": [{"start_sec": 500, "end_sec": 700, "rationale": "r"}]})
    out = advisor.propose(transcript="[00:00] a", duration_sec=600)
    assert out == [(500.0, 600.0, "r")]


def test_de_xuat_qua_ngan_bi_loai():
    advisor = StubAdvisor(
        {
            "proposals": [
                {"start_sec": 10, "end_sec": 12, "rationale": "quá ngắn"},
                {"start_sec": 100, "end_sec": 160, "rationale": "được"},
            ]
        }
    )
    assert advisor.propose(transcript="x", duration_sec=600) == [(100.0, 160.0, "được")]


def test_khong_de_xuat_nao_hop_le_thi_bao_loi_chu_khong_tra_ve_rong():
    """Trả về danh sách rỗng sẽ làm pipeline đi tiếp mà không có đoạn nào."""
    advisor = StubAdvisor({"proposals": [{"start_sec": 0, "end_sec": 2, "rationale": "r"}]})
    with pytest.raises(LlmFailed):
        advisor.propose(transcript="x", duration_sec=600)


def test_transcript_rong_thi_khong_goi_model():
    advisor = StubAdvisor({"proposals": []})
    with pytest.raises(LlmRejected):
        advisor.propose(transcript="   ", duration_sec=600)
    assert advisor.prompts == []


def test_prompt_chon_doan_neu_ro_cua_so_45_75_giay():
    advisor = StubAdvisor({"proposals": [{"start_sec": 0, "end_sec": 60, "rationale": "r"}]})
    advisor.propose(transcript="[00:00] a", duration_sec=600)
    assert "45–75" in advisor.prompts[0]


# ---------------- Kiểm kịch bản ----------------


def test_kich_ban_rong_thi_bao_loi():
    writer = StubWriter({"script_vi": "   ", "syllable_estimate": 0,
                         "vietnam_context_sentence": ""})
    with pytest.raises(LlmFailed):
        writer.write(transcript="x", segment=(0.0, 60.0), max_syllables=300, glossary={})


def test_prompt_viet_kich_ban_co_ngan_sach_va_bang_thuat_ngu():
    writer = StubWriter({"script_vi": "ok", "syllable_estimate": 10,
                         "vietnam_context_sentence": "vn"})
    writer.write(
        transcript="nguồn",
        segment=(10.0, 70.0),
        max_syllables=330,
        glossary={"control chart": "biểu đồ kiểm soát"},
    )
    prompt = writer.prompts[0]
    assert "330 âm tiết" in prompt
    assert "control chart → biểu đồ kiểm soát" in prompt
    assert "60.0 giây" in prompt


def test_viet_lai_thi_prompt_mang_theo_ban_cu_va_ly_do():
    """Không có chúng thì model viết lại từ đầu và rất dễ tràn đúng như lần trước."""
    writer = StubWriter({"script_vi": "ngắn hơn", "syllable_estimate": 5,
                         "vietnam_context_sentence": "vn"})
    writer.write(
        transcript="nguồn",
        segment=(0.0, 60.0),
        max_syllables=300,
        glossary={},
        previous_attempt="bản dài trước đó",
        rewrite_reason="audio dài 68s, khung 60s",
    )
    prompt = writer.prompts[0]
    assert "bản dài trước đó" in prompt
    assert "audio dài 68s" in prompt
    assert "NGẮN HƠN" in prompt


# ---------------- Prompt system mã hoá quy tắc nghiệp vụ ----------------


def test_system_prompt_cam_dich_va_doi_boi_canh_viet_nam():
    from src.infrastructure.llm.claude import SCRIPT_SYSTEM, SEGMENT_SYSTEM

    assert "KHÔNG dịch" in SCRIPT_SYSTEM
    assert "bối cảnh Việt Nam" in SCRIPT_SYSTEM or "Việt Nam" in SCRIPT_SYSTEM
    assert "talking-head" in SEGMENT_SYSTEM  # tiêu chí tránh
    assert "số liệu kiểm chứng được" in SEGMENT_SYSTEM


# ---------------- Tiện ích ----------------


def test_format_transcript_co_timestamp():
    out = format_transcript_with_timestamps(
        [{"start": 0.0, "text": " mở đầu "}, {"start": 75.5, "text": "phút sau"}]
    )
    assert out == "[00:00] mở đầu" + chr(10) + "[01:15] phút sau"


def test_format_transcript_bo_segment_rong():
    assert format_transcript_with_timestamps([{"start": 1.0, "text": "  "}]) == ""


def test_glossary_json_sai_dinh_dang_thi_bao_loi():
    with pytest.raises(LlmRejected):
        load_glossary_json("{khong phai json}")
    assert load_glossary_json('{"a": "b"}') == {"a": "b"}
