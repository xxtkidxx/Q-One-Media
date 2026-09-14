"""Kịch bản hình ảnh của Giai đoạn 2 — video không dùng thước phim của ai.

Giai đoạn 1 có sẵn hình: cắt từ video nguồn đã có license. Giai đoạn 2 không có
gì cả, nên phải dựng hình từ bốn lớp, xếp theo đúng thứ tự ưu tiên của đặc tả
(mục ⑥): **ảnh/video thật của NMI → kho có license → AI chỉ cho bối cảnh**, cộng
một lớp nữa mà đặc tả gọi là "dạng nội dung mạnh nhất cho khán giả kỹ thuật":
biểu đồ và bảng dựng từ số liệu thật.

Vì sao thứ tự này là quy tắc miền chứ không phải tuỳ chọn hiển thị: ảnh AI đặt
sai chỗ sẽ *minh hoạ sai một dữ kiện kỹ thuật* — một biểu đồ Cpk do model vẽ ra
trông rất thuyết phục và hoàn toàn bịa. Nên lớp AI bị giới hạn ở bối cảnh, và
số liệu thì phải đi qua lớp biểu đồ, nơi con số là do mình đưa vào.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from src.domain.errors import InvariantViolation

MIN_SHOT_SEC = 1.5
MAX_SHOT_SEC = 12.0


class ShotKind(StrEnum):
    UPLOAD = "upload"          # L1: ảnh/video người dùng đưa vào (ảnh NMI thật)
    STOCK = "stock"            # L2: kho có license, đã tải sẵn về máy
    CHART = "chart"            # số liệu thật → biểu đồ/bảng do mình dựng
    GENERATED = "generated"    # L3: AI, **chỉ** cho bối cảnh
    BRAND_CARD = "brand_card"  # nền thương hiệu + chữ, khi không có gì khác


@dataclass(frozen=True, slots=True)
class Shot:
    """Một cảnh: chiếm bao nhiêu giây, lấy hình từ đâu.

    ``asset`` là đường dẫn tương đối ``MEDIA_ROOT`` với upload/stock; với
    ``generated`` nó rỗng cho tới khi sinh xong, còn ``prompt`` là đề bài. Với
    ``chart`` thì ``data`` mang số liệu.
    """

    kind: ShotKind
    seconds: float
    caption: str = ""
    asset: str | None = None
    prompt: str = ""
    data: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not MIN_SHOT_SEC <= self.seconds <= MAX_SHOT_SEC:
            raise InvariantViolation(
                f"cảnh dài {self.seconds}s, ngoài biên {MIN_SHOT_SEC}–{MAX_SHOT_SEC}s"
            )
        if self.kind in (ShotKind.UPLOAD, ShotKind.STOCK) and not self.asset:
            raise InvariantViolation(f"cảnh {self.kind} phải có file hình")
        if self.kind is ShotKind.GENERATED and not self.prompt.strip():
            raise InvariantViolation("cảnh sinh bằng AI phải có prompt")
        if self.kind is ShotKind.CHART and not self.data:
            raise InvariantViolation(
                "cảnh biểu đồ phải có số liệu thật — biểu đồ không số liệu là hình trang trí "
                "mang dáng vẻ bằng chứng"
            )

    @property
    def is_ready(self) -> bool:
        """Cảnh đã có file để dựng chưa. Cảnh AI chưa sinh thì chưa."""
        return self.kind in (ShotKind.CHART, ShotKind.BRAND_CARD) or bool(self.asset)

    def with_asset(self, asset: str) -> Shot:
        return Shot(
            kind=self.kind,
            seconds=self.seconds,
            caption=self.caption,
            asset=asset,
            prompt=self.prompt,
            data=self.data,
        )


@dataclass(frozen=True, slots=True)
class VisualPlan:
    """Danh sách cảnh phủ đúng thời lượng video."""

    shots: tuple[Shot, ...]

    def __post_init__(self) -> None:
        if not self.shots:
            raise InvariantViolation("kịch bản hình phải có ít nhất một cảnh")

    @property
    def total_sec(self) -> float:
        return sum(shot.seconds for shot in self.shots)

    @property
    def ready(self) -> bool:
        return all(shot.is_ready for shot in self.shots)

    @property
    def pending_prompts(self) -> tuple[Shot, ...]:
        return tuple(shot for shot in self.shots if not shot.is_ready)

    def fitted_to(self, target_sec: float) -> VisualPlan:
        """Co giãn đều các cảnh cho khớp thời lượng giọng đọc.

        Giọng đọc quyết định độ dài video, không phải ngược lại: kịch bản đã viết
        trong ngân sách âm tiết (F2.3), còn hình chỉ việc phủ cho kín. Nếu để
        hình quyết định thì cảnh cuối bị cắt giữa câu.
        """
        if target_sec <= 0:
            raise InvariantViolation("thời lượng mục tiêu phải dương")

        # Một cảnh dài quá 12 giây là ảnh tĩnh đứng im quá lâu, nên khi giọng dài
        # hơn số cảnh cho phép thì **lặp lại vòng cảnh** chứ không kéo dãn cảnh
        # cuối. Ngược lại, giọng quá ngắn thì bớt cảnh — đứng dưới 1,5 giây thì
        # người xem chưa kịp nhìn.
        shots = list(self.shots)
        needed = math.ceil(target_sec / MAX_SHOT_SEC)
        while len(shots) < needed:
            shots.append(shots[len(shots) % len(self.shots)])
        allowed = max(1, int(target_sec // MIN_SHOT_SEC))
        if len(shots) > allowed:
            shots = shots[:allowed]

        per = target_sec / len(shots)
        scaled = []
        for index, shot in enumerate(shots):
            # Cảnh cuối nhận phần dư để tổng khớp đúng thời lượng giọng đọc.
            seconds = (
                round(target_sec - per * (len(shots) - 1), 2)
                if index == len(shots) - 1
                else round(per, 2)
            )
            seconds = min(MAX_SHOT_SEC, max(MIN_SHOT_SEC, seconds))
            scaled.append(
                Shot(
                    kind=shot.kind,
                    seconds=seconds,
                    caption=shot.caption,
                    asset=shot.asset,
                    prompt=shot.prompt,
                    data=shot.data,
                )
            )
        return VisualPlan(tuple(scaled))


def default_plan(*, title: str, target_sec: float) -> VisualPlan:
    """Kịch bản hình tối thiểu khi người dùng chưa đưa gì vào.

    Ba thẻ thương hiệu vẫn ra được một video đọc được — quan trọng hơn là nó
    không **bịa hình**: không có ảnh nào giả vờ là ảnh nhà máy có thật.
    """
    each = max(MIN_SHOT_SEC, min(MAX_SHOT_SEC, target_sec / 3))
    return VisualPlan(
        tuple(
            Shot(kind=ShotKind.BRAND_CARD, seconds=each, caption=caption)
            for caption in (title, "Q One · NMI Technologies", "nmi.vn")
        )
    )
