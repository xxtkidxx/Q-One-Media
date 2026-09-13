"""Adapter Claude: chọn đoạn và viết kịch bản tiếng Việt.

Hai prompt ở đây là nơi phần lớn chất lượng nội dung được quyết định, nên chúng
được viết tường minh và có lý do kèm theo — không phải "prompt thần chú".

Dùng tool-use để buộc đầu ra có cấu trúc thay vì parse JSON từ văn xuôi: mô hình
không thể trả về hình dạng khác, nên không cần code dò dấu ngoặc.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.shared.logging import get_logger

log = get_logger(__name__)


class LlmFailed(RuntimeError):
    retryable = True  # rate limit, overload — xếp lại được


class LlmRejected(RuntimeError):
    retryable = False  # input sai, key sai


# ---------------- Prompt chọn đoạn ----------------

SEGMENT_SYSTEM = """\
Bạn chọn đoạn video để làm short video tiếng Việt cho NMI Technologies — công ty \
bán phần mềm chất lượng và điều hành sản xuất (SPC, MSA, MES, historian, AI vision) \
cho nhà máy.

Khán giả là **quản lý chất lượng, quản lý sản xuất, kỹ sư IE/IT trong nhà máy**, \
phần lớn ở doanh nghiệp FDI Nhật tại Việt Nam. Họ đánh giá nội dung bằng tiêu chuẩn \
nghề, không bằng mức giải trí.

Tiêu chí chọn đoạn, theo thứ tự quan trọng:
1. Có **số liệu kiểm chứng được** — thông số, dung sai, kết quả đo, biểu đồ.
2. **Giải thích nguyên nhân**, không chỉ nêu hiện tượng.
3. Có **thiết bị hoặc màn hình thật** xuất hiện trong hình.

Tránh:
- Đoạn chỉ có người nói trước camera (talking-head) — không có gì để xem, và \
reframe về khung dọc sẽ càng trơ.
- Đoạn quảng cáo thuần, không có nội dung kỹ thuật.
- Đoạn mở đầu/kết thúc chỉ có logo và nhạc.

Bạn **đề xuất**, người chọn. Vì vậy lý do phải cụ thể đủ để người đọc quyết định \
được mà không cần mở video: nói rõ đoạn đó có số liệu gì, giải thích điều gì.\
"""

SEGMENT_TOOL: dict[str, Any] = {
    "name": "de_xuat_doan",
    "description": "Đề xuất 2–3 đoạn ứng viên cho short video.",
    "input_schema": {
        "type": "object",
        "properties": {
            "proposals": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "start_sec": {"type": "number"},
                        "end_sec": {"type": "number"},
                        "rationale": {
                            "type": "string",
                            "description": (
                                "Lý do cụ thể bằng tiếng Việt: có số liệu gì, giải thích "
                                "điều gì, thấy thiết bị/màn hình nào."
                            ),
                        },
                    },
                    "required": ["start_sec", "end_sec", "rationale"],
                },
            }
        },
        "required": ["proposals"],
    },
}


# ---------------- Prompt viết kịch bản ----------------

SCRIPT_SYSTEM = """\
Bạn viết kịch bản lời bình tiếng Việt cho short video của NMI Technologies.

**Bạn KHÔNG dịch.** Đây là điểm quan trọng nhất. Việc của bạn là đọc transcript \
nguồn để hiểu **dữ kiện**, rồi **viết một đoạn mới** bằng góc nhìn của NMI. Bản \
dịch sát nguyên văn là sản phẩm sai — vừa kém về nội dung, vừa là tác phẩm phái \
sinh của người khác.

Kịch bản cần có:
1. **Mở đầu 3 giây** nêu thẳng vấn đề nhà máy gặp phải, không rào đón.
2. **Dữ kiện kỹ thuật** lấy từ nguồn, giữ đúng số liệu.
3. **Một câu bối cảnh Việt Nam** — thực tế ở nhà máy Việt, hoặc điều kiện vận \
hành tại Việt Nam. Đây là phần giá trị gốc, không được bỏ.
4. **Kết bằng điều người xem làm được**, không phải lời kêu gọi mua hàng.

Quy tắc viết:
- Câu ngắn, nói được thành lời. Đây là lời đọc, không phải văn viết.
- Thuật ngữ dùng đúng bảng thuật ngữ được cung cấp. Thuật ngữ không có trong bảng \
thì giữ nguyên tiếng Anh nếu người trong ngành vẫn nói tiếng Anh (Cpk, MES, OPC UA).
- **Không** dùng từ hoa mỹ marketing ("đột phá", "cách mạng", "giải pháp toàn diện").
- **Không** hứa hẹn con số hiệu quả mà nguồn không nói.
- Viết đúng hoặc dưới ngân sách âm tiết. Vượt ngân sách thì audio tràn khung thời \
gian, và cách sửa duy nhất là viết ngắn lại — không đọc nhanh hơn.\
"""

SCRIPT_TOOL: dict[str, Any] = {
    "name": "viet_kich_ban",
    "description": "Trả về kịch bản lời bình tiếng Việt.",
    "input_schema": {
        "type": "object",
        "properties": {
            "script_vi": {
                "type": "string",
                "description": "Lời bình tiếng Việt, liền mạch, không đánh số cảnh.",
            },
            "syllable_estimate": {
                "type": "integer",
                "description": "Số âm tiết bạn tự đếm được trong kịch bản.",
            },
            "vietnam_context_sentence": {
                "type": "string",
                "description": "Chính câu bối cảnh Việt Nam đã đưa vào kịch bản.",
            },
        },
        "required": ["script_vi", "syllable_estimate", "vietnam_context_sentence"],
    },
}


@dataclass
class _ClaudeBase:
    api_key: str
    model: str = "claude-sonnet-5"
    max_tokens: int = 4096

    def __post_init__(self) -> None:
        if not self.api_key:
            raise LlmRejected("thiếu ANTHROPIC_API_KEY")

    def _client(self) -> Any:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise LlmRejected("chưa cài anthropic") from exc
        return Anthropic(api_key=self.api_key)

    def _call_tool(self, *, system: str, prompt: str, tool: dict[str, Any]) -> dict[str, Any]:
        """Gọi model và buộc nó dùng đúng một tool → đầu ra luôn đúng hình dạng."""
        client = self._client()
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
            )
        except Exception as exc:  # noqa: BLE001 — SDK ném nhiều họ exception
            name = type(exc).__name__
            # Rate limit và overload thì xếp lại; còn lại là lỗi của ta.
            if any(k in name for k in ("RateLimit", "Overloaded", "APIConnection", "Timeout")):
                raise LlmFailed(f"{name}: {exc}") from exc
            raise LlmRejected(f"{name}: {exc}") from exc

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        raise LlmFailed(f"model không gọi tool {tool['name']}, trả về: {resp.content!r}")


class ClaudeSegmentAdvisor(_ClaudeBase):
    """Hiện thực port ``SegmentAdvisor``."""

    def propose(
        self, *, transcript: str, duration_sec: int, max_proposals: int = 3
    ) -> list[tuple[float, float, str]]:
        if not transcript.strip():
            raise LlmRejected("transcript rỗng — không đề xuất được đoạn")

        prompt = (
            f"Video dài {duration_sec} giây. Transcript có timestamp:\n\n"
            f"{transcript}\n\n"
            f"Đề xuất tối đa {max_proposals} đoạn dài **45–75 giây** phù hợp nhất. "
            "Đoạn phải nằm trong độ dài video và không chồng nhau."
        )
        data = self._call_tool(system=SEGMENT_SYSTEM, prompt=prompt, tool=SEGMENT_TOOL)
        out: list[tuple[float, float, str]] = []
        for p in data.get("proposals", [])[:max_proposals]:
            start, end = float(p["start_sec"]), float(p["end_sec"])
            # Kẹp vào độ dài video: model đôi khi đề xuất vượt quá phần cuối.
            # Kẹp ở đây chứ không tin tưởng, và cũng không loại bỏ im lặng.
            if end > duration_sec:
                log.warning("llm.segment.clamped", end=end, duration=duration_sec)
                end = float(duration_sec)
            if end - start < 10:
                log.warning("llm.segment.too_short", start=start, end=end)
                continue
            out.append((start, end, str(p["rationale"])))
        if not out:
            raise LlmFailed("không có đề xuất nào hợp lệ sau khi kiểm")
        return out


class ClaudeScriptWriter(_ClaudeBase):
    """Hiện thực port ``ScriptWriter``."""

    def write(
        self,
        *,
        transcript: str,
        segment: tuple[float, float],
        max_syllables: int,
        glossary: dict[str, str],
        previous_attempt: str | None = None,
        rewrite_reason: str | None = None,
    ) -> str:
        start, end = segment
        parts = [
            f"Đoạn được chọn: {start:.1f}s → {end:.1f}s (khung {end - start:.1f} giây).",
            f"**Ngân sách: tối đa {max_syllables} âm tiết.** Viết đúng hoặc ngắn hơn.",
            "",
            "Transcript nguồn của đoạn này:",
            transcript,
        ]
        if glossary:
            parts += [
                "",
                "Bảng thuật ngữ bắt buộc dùng đúng:",
                *(f"- {src} → {vi}" for src, vi in sorted(glossary.items())),
            ]
        if previous_attempt and rewrite_reason:
            # Đưa cả bản cũ và lý do vào: không có chúng thì model viết lại từ đầu
            # và rất dễ tràn ngân sách đúng như lần trước.
            parts += [
                "",
                "Bản trước bị trả lại. Lý do:",
                rewrite_reason,
                "",
                "Bản trước (viết lại NGẮN HƠN, giữ dữ kiện quan trọng nhất):",
                previous_attempt,
            ]
        data = self._call_tool(
            system=SCRIPT_SYSTEM, prompt="\n".join(parts), tool=SCRIPT_TOOL
        )
        script = str(data.get("script_vi", "")).strip()
        if not script:
            raise LlmFailed("model trả kịch bản rỗng")
        log.info(
            "llm.script.done",
            model_estimate=data.get("syllable_estimate"),
            budget=max_syllables,
            has_vn_context=bool(str(data.get("vietnam_context_sentence", "")).strip()),
        )
        return script


def format_transcript_with_timestamps(segments: list[dict[str, Any]]) -> str:
    """Đổi segment của WhisperX thành text có timestamp cho prompt.

    Cần timestamp vì model phải trả về giây, và không có mốc thì nó chỉ đoán được.
    """
    lines = []
    for seg in segments:
        start = float(seg.get("start", 0.0))
        text = str(seg.get("text", "")).strip()
        if text:
            lines.append(f"[{int(start // 60):02d}:{int(start % 60):02d}] {text}")
    return "\n".join(lines)


def load_glossary_json(raw: str) -> dict[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LlmRejected(f"glossary không phải JSON hợp lệ: {exc}") from exc
    return {str(k): str(v) for k, v in data.items()}
