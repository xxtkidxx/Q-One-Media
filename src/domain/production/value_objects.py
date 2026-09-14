"""Value object của bounded context "sản xuất một video"."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from math import gcd

from src.domain.errors import InvariantViolation

# Cửa sổ đoạn nên chọn cho short-form (đặc tả mục C bước ⑦).
RECOMMENDED_SEGMENT_MIN_SEC = 45.0
RECOMMENDED_SEGMENT_MAX_SEC = 75.0

# Biên cứng: ngoài khoảng này thì không còn là short video.
HARD_SEGMENT_MIN_SEC = 10.0
HARD_SEGMENT_MAX_SEC = 180.0

# Ngưỡng cho phép audio TTS dài hơn khung thời gian (đặc tả F2.3).
# Quá ngưỡng thì viết kịch bản ngắn lại — KHÔNG tăng tốc độ đọc để nhồi cho vừa.
SYLLABLE_OVERRUN_TOLERANCE = 0.05


class ItemStage(StrEnum):
    """Máy trạng thái của một item. Thứ tự khai báo theo đúng dòng chảy pipeline."""

    INBOX = "inbox"
    LICENSE_BLOCKED = "license_blocked"
    DOWNLOADED = "downloaded"
    SEPARATED = "separated"
    TRANSCRIBED = "transcribed"
    TRANSCRIPT_REVIEW = "transcript_review"
    TRANSCRIPT_APPROVED = "transcript_approved"
    SEGMENT_PICKED = "segment_picked"
    SCRIPTED = "scripted"
    VOICED = "voiced"
    ALIGNED = "aligned"
    MIXED = "mixed"
    RENDERED = "rendered"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"

    @property
    def is_terminal(self) -> bool:
        return self in (ItemStage.PUBLISHED, ItemStage.REJECTED, ItemStage.LICENSE_BLOCKED)


@dataclass(frozen=True, slots=True)
class Segment:
    """Đoạn được chọn để làm short video."""

    start_sec: float
    end_sec: float
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.start_sec < 0:
            raise InvariantViolation("start_sec không được âm")
        if self.end_sec <= self.start_sec:
            raise InvariantViolation(
                f"end_sec ({self.end_sec}) phải lớn hơn start_sec ({self.start_sec})"
            )
        if not (HARD_SEGMENT_MIN_SEC <= self.duration_sec <= HARD_SEGMENT_MAX_SEC):
            raise InvariantViolation(
                f"đoạn dài {self.duration_sec:.1f}s, ngoài biên cho phép "
                f"{HARD_SEGMENT_MIN_SEC}–{HARD_SEGMENT_MAX_SEC}s"
            )

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec

    @property
    def is_recommended_length(self) -> bool:
        return RECOMMENDED_SEGMENT_MIN_SEC <= self.duration_sec <= RECOMMENDED_SEGMENT_MAX_SEC


_RATIO_RE = re.compile(r"^(\d{1,5}):(\d{1,5})$")


@dataclass(frozen=True, slots=True)
class AspectRatio:
    """Tỷ lệ khung hình. Tồn tại để trả lời đúng một câu: có phải reframe không."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise InvariantViolation("kích thước khung hình phải dương")

    @classmethod
    def parse(cls, text: str) -> AspectRatio:
        m = _RATIO_RE.match(text.strip())
        if not m:
            raise InvariantViolation(f"tỷ lệ khung hình không hợp lệ: {text!r} (cần dạng '16:9')")
        return cls(int(m.group(1)), int(m.group(2)))

    @classmethod
    def from_size(cls, width: int, height: int) -> AspectRatio:
        d = gcd(width, height) or 1
        return cls(width // d, height // d)

    @property
    def value(self) -> float:
        return self.width / self.height

    def needs_reframe_to(self, target: AspectRatio, *, tolerance: float = 0.02) -> bool:
        """Bỏ qua reframe nếu nguồn đã đúng tỷ lệ — tiết kiệm một lần encode
        và tránh làm giảm chất lượng vô ích (G2.12)."""
        return abs(self.value - target.value) > tolerance

    def __str__(self) -> str:
        return f"{self.width}:{self.height}"


PORTRAIT_9_16 = AspectRatio(9, 16)


class ReframeMode(StrEnum):
    """Chế độ đưa về 9:16 (đặc tả F2.6)."""

    BLUR = "blur"
    CROP = "crop"
    SMART = "smart"


def choose_reframe_mode(source: AspectRatio) -> ReframeMode:
    """Mặc định ``blur`` cho video công nghiệp.

    Lý do không dùng ``crop``: với máy móc, dây chuyền, HMI và screen recording
    thì **toàn bộ khung hình mang thông tin** — cắt hai bên là cắt đúng thứ
    người xem cần thấy.
    """
    return ReframeMode.BLUR


@dataclass(frozen=True, slots=True)
class SpeechRate:
    """Tốc độ đọc thật của giọng đã chọn, đơn vị âm tiết/giây.

    Cố tình **không** có giá trị mặc định. Các con số 5,28–6 âm tiết/giây tìm
    được trên mạng không thống nhất; đặc tả F2.3 yêu cầu tự đo giọng VoxCPM2
    đang dùng (G0.7). Không có số đo thật thì không lập được ngân sách âm tiết.
    """

    syllables_per_sec: float

    def __post_init__(self) -> None:
        if not (1.0 < self.syllables_per_sec < 15.0):
            raise InvariantViolation(
                f"tốc độ đọc {self.syllables_per_sec} âm tiết/giây không thực tế "
                "— đo lại bằng một đoạn 200 âm tiết"
            )


@dataclass(frozen=True, slots=True)
class SyllableBudget:
    """Ngân sách âm tiết cho **một cảnh**, không phải cho cả video.

    Đặt theo cảnh vì kịch bản phải khớp ranh giới cảnh; đặt theo cả video thì
    một cảnh tràn sẽ đẩy lệch mọi cảnh sau.
    """

    window_sec: float
    rate: SpeechRate

    def __post_init__(self) -> None:
        if self.window_sec <= 0:
            raise InvariantViolation("window_sec phải dương")

    @property
    def max_syllables(self) -> int:
        return int(self.window_sec * self.rate.syllables_per_sec)

    @property
    def hard_limit_sec(self) -> float:
        return self.window_sec * (1 + SYLLABLE_OVERRUN_TOLERANCE)

    def overruns(self, actual_audio_sec: float) -> bool:
        """True nghĩa là trả kịch bản về cho LLM viết ngắn lại."""
        return actual_audio_sec > self.hard_limit_sec


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """Đường dẫn **tương đối** so với MEDIA_ROOT. Không bao giờ tuyệt đối.

    Lý do: DB không được gắn với một máy cụ thể; đổi máy hoặc đổi bind mount
    thì dữ liệu vẫn dùng được.
    """

    relative_path: str

    def __post_init__(self) -> None:
        p = self.relative_path
        if not p or p.startswith(("/", "\\")) or ":" in p or ".." in p.split("/"):
            raise InvariantViolation(f"cần đường dẫn tương đối, an toàn; nhận {p!r}")
