"""Series — một loạt video ngắn cùng khuôn: pillar, mẫu hook, thuật ngữ, độ dài, khung.

Vì sao là quy tắc miền chứ không phải form tiện lợi: một kênh chuyên đề sống bằng
sự nhất quán. Video thứ 30 phải cùng khung 9:16, cùng nhịp 25–45 giây và cùng cách
gọi Cpk với video thứ nhất, bất kể ai bấm nút hay gọi từ đường nào. Ràng buộc nằm
ở form thì một đường tạo mới (API, script) sẽ đi vòng; nằm ở đây thì không tạo nổi
một Series sai.

Cấu trúc theo mốc giây và mẫu hook đi vào **đề bài** gửi cho model. Output của model
vẫn là lời bình liền mạch (schema viết kịch bản dùng chung với Giai đoạn 1), nên tầng
này ép cấu trúc bằng chỉ dẫn và trần âm tiết từng phần — chưa kiểm được kịch bản trả
về có đúng mốc hay không.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.errors import InvariantViolation
from src.domain.production.value_objects import (
    PORTRAIT_9_16,
    AspectRatio,
    SpeechRate,
    SyllableBudget,
)

MIN_SERIES_SEC = 25.0
MAX_SERIES_SEC = 45.0
SERIES_LANGUAGE = "vi"

# Hai phần có độ dài cố định; phần còn lại chia 20/60/20 cho đặt khung/thân/chốt.
HOOK_SEC = 3.0
CTA_SEC = 4.0

# Trùng thông số bộ dựng đang dùng (font 54 của ``build_ass``, 42 ký tự/dòng khi gộp
# phụ đề) để Series mới không lệch khỏi video đã có.
DEFAULT_SUBTITLE_FONT_SIZE = 54
DEFAULT_SUBTITLE_MAX_CHARS = 42

WEEKDAY_LABELS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")

_PLACEHOLDER_RE = re.compile(r"\[[^\[\]]+\]")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")

_BEAT_SPECS = (
    (
        "Hook",
        "Câu hook đã chọn, điền chỗ trống theo đề tài. Thuật ngữ chính xuất hiện ngay "
        "ở đây. Không chào hỏi, không giới thiệu kênh.",
    ),
    ("Đặt khung", "Một câu: vì sao chuyện này hay xảy ra hoặc hay bị hiểu sai ở nhà máy."),
    ("Thân", "Tối đa 2–3 ý. Mỗi ý là một câu khẳng định kèm một ví dụ cụ thể trên xưởng."),
    ("Chốt", "Một câu mang về xưởng áp dụng được: một việc kiểm tra cụ thể, không phải khẩu hiệu."),
    (
        "CTA",
        "Đúng một câu: mời bình luận một câu hỏi chuyên môn hoặc mời lưu lại. Không kêu "
        "gọi mua hàng, không nhắc sản phẩm.",
    ),
)


@dataclass(frozen=True, slots=True)
class SubtitlePreset:
    """Preset phụ đề của Series. **Mới lưu và hiển thị** — bộ dựng chưa đọc nó."""

    font_size: int = DEFAULT_SUBTITLE_FONT_SIZE
    max_chars_per_line: int = DEFAULT_SUBTITLE_MAX_CHARS

    def __post_init__(self) -> None:
        if not 32 <= self.font_size <= 96:
            raise InvariantViolation(f"cỡ chữ phụ đề {self.font_size} ngoài khoảng 32–96")
        if not 16 <= self.max_chars_per_line <= 48:
            raise InvariantViolation(
                f"{self.max_chars_per_line} ký tự/dòng ngoài khoảng 16–48 — dòng quá dài "
                "không đọc kịp trên khung dọc"
            )


@dataclass(frozen=True, slots=True)
class PostingCadence:
    """Lịch đăng cố định — kế hoạch để người vận hành nhìn, **không** phải trigger đăng.

    Gate duyệt của người là bắt buộc và client TikTok chưa audit chỉ đăng được
    riêng tư, nên không có đường nào tự đăng theo lịch này.
    """

    weekdays: tuple[int, ...]  # 0 = thứ Hai … 6 = Chủ nhật
    time_of_day: str  # "HH:MM", giờ Việt Nam

    def __post_init__(self) -> None:
        if not self.weekdays:
            raise InvariantViolation("lịch đăng phải có ít nhất một ngày trong tuần")
        if any(day not in range(7) for day in self.weekdays):
            raise InvariantViolation("ngày trong tuần phải từ 0 (thứ Hai) tới 6 (Chủ nhật)")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise InvariantViolation("lịch đăng có ngày bị trùng")
        match = _TIME_RE.match(self.time_of_day)
        if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
            raise InvariantViolation(f"giờ đăng không hợp lệ: {self.time_of_day!r} (cần HH:MM)")

    @property
    def label(self) -> str:
        days = ", ".join(WEEKDAY_LABELS[day] for day in sorted(self.weekdays))
        return f"{days} · {self.time_of_day}"


@dataclass(frozen=True, slots=True)
class Beat:
    """Một phần của video theo mốc giây."""

    label: str
    start_sec: float
    end_sec: float
    instruction: str

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 2)


@dataclass(eq=False)
class Series:
    name: str
    pillar: str
    hook_templates: tuple[str, ...]
    target_sec: float
    kept_terms: tuple[str, ...] = ()
    output_aspect_ratio: AspectRatio = PORTRAIT_9_16
    language: str = SERIES_LANGUAGE
    voice_id: str | None = None
    subtitle: SubtitlePreset = field(default_factory=SubtitlePreset)
    cadence: PostingCadence | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.pillar = self.pillar.strip()
        self.hook_templates = tuple(hook.strip() for hook in self.hook_templates if hook.strip())
        self.kept_terms = _unique_terms(self.kept_terms)
        self.voice_id = (self.voice_id or "").strip() or None

        if not self.name:
            raise InvariantViolation("Series phải có tên")
        if not self.pillar:
            raise InvariantViolation(
                "Series phải có pillar — không có trụ thì không biết video phục vụ mục đích gì"
            )
        if self.language != SERIES_LANGUAGE:
            raise InvariantViolation(f"Series chỉ sản xuất tiếng Việt, nhận được {self.language!r}")
        if not MIN_SERIES_SEC <= self.target_sec <= MAX_SERIES_SEC:
            raise InvariantViolation(
                f"độ dài mục tiêu {self.target_sec:g}s nằm ngoài khung "
                f"{MIN_SERIES_SEC:g}–{MAX_SERIES_SEC:g}s của video ngắn"
            )
        if self.output_aspect_ratio != PORTRAIT_9_16:
            raise InvariantViolation(
                f"Series chỉ nhận khung dọc 9:16, nhận được {self.output_aspect_ratio}"
            )
        if not self.hook_templates:
            raise InvariantViolation("Series phải có ít nhất một mẫu hook")
        for hook in self.hook_templates:
            if not _PLACEHOLDER_RE.search(hook):
                raise InvariantViolation(
                    f"mẫu hook phải có chỗ trống dạng [..]: {hook!r} — không có chỗ trống "
                    "thì mọi video mở đầu y hệt nhau"
                )

    def hook_for(self, position: int) -> str:
        """Mẫu hook cho video con thứ ``position`` (đếm từ 0), xoay vòng tất định.

        Tất định để ghi lại và kiểm được video nào dùng hook nào; để model tự chọn
        thì không ai trả lời được câu đó.
        """
        if position < 0:
            raise InvariantViolation("vị trí video trong Series không được âm")
        return self.hook_templates[position % len(self.hook_templates)]

    def beats(self) -> tuple[Beat, ...]:
        rest = self.target_sec - HOOK_SEC - CTA_SEC
        marks = [
            0.0,
            HOOK_SEC,
            HOOK_SEC + rest * 0.2,
            HOOK_SEC + rest * 0.8,
            self.target_sec - CTA_SEC,
            self.target_sec,
        ]
        marks = [round(mark, 1) for mark in marks]
        return tuple(
            Beat(label=label, start_sec=marks[index], end_sec=marks[index + 1], instruction=text)
            for index, (label, text) in enumerate(_BEAT_SPECS)
        )

    def brief_for(self, topic: str, *, position: int, speech_rate: float) -> str:
        """Đề bài gửi cho model: đề tài + mẫu hook + cấu trúc mốc giây + thuật ngữ."""
        clean_topic = topic.strip()
        if not clean_topic:
            raise InvariantViolation("đề tài rỗng — không có gì để viết")
        rate = SpeechRate(speech_rate)
        lines = [
            f"Series: {self.name}",
            f"Pillar: {self.pillar}",
            f"Đề tài của video này: {clean_topic}",
            f"Độ dài: {self.target_sec:g} giây, khung dọc 9:16.",
            "",
            "Mở đầu bằng đúng mẫu hook sau — điền các chỗ trống [..] cho khớp đề tài, "
            "giữ nguyên cấu trúc câu:",
            self.hook_for(position),
            "",
            "Cấu trúc bắt buộc theo mốc giây. Lời bình vẫn liền mạch, nhưng đi đúng thứ tự "
            "và không vượt trần âm tiết của từng phần:",
        ]
        for beat in self.beats():
            cap = SyllableBudget(window_sec=beat.duration_sec, rate=rate).max_syllables
            lines.append(
                f"- {beat.start_sec:g}–{beat.end_sec:g}s · {beat.label} "
                f"(tối đa {cap} âm tiết): {beat.instruction}"
            )
        if self.kept_terms:
            lines += [
                "",
                "Giữ nguyên tiếng Anh, không dịch, không phiên âm: " + ", ".join(self.kept_terms),
            ]
        lines += [
            "",
            'Không dùng câu giật gân kiểu "sốc", "99% kỹ sư không biết"; không bịa số liệu.',
        ]
        return "\n".join(lines)

    def glossary_over(self, base: dict[str, str]) -> dict[str, str]:
        """Glossary chung + thuật ngữ giữ nguyên của Series; trùng thì Series thắng.

        Ghi ``MES → MES`` thay vì chuỗi rỗng: với model, "giữ nguyên" viết tường minh
        khó hiểu sai hơn một vế phải để trống.
        """
        kept = {term.casefold() for term in self.kept_terms}
        merged = {src: vi for src, vi in base.items() if src.casefold() not in kept}
        merged.update({term: term for term in self.kept_terms})
        return merged


def _unique_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in terms:
        term = raw.strip()
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            out.append(term)
    return tuple(out)
