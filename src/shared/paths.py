"""Đường dẫn media — nguồn duy nhất. Không hardcode './data/...' ở bất cứ đâu khác.

Mọi đường dẫn lưu trong DB là **tương đối** so với MEDIA_ROOT, để di chuyển
được cây data sang máy khác mà không phải sửa DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_ALLOWED_ROOTS = ("source", "work", "output")


@dataclass(frozen=True)
class MediaPaths:
    """Ba vùng dưới MEDIA_ROOT, khác nhau ở chính sách xoá.

    - ``source``: video gốc đã tải. Không xoá — cần để làm lại và chứng minh tuân thủ.
    - ``work``:   file trung gian. Xoá được, sinh lại được.
    - ``output``: thành phẩm. Không xoá.
    """

    root: Path

    @property
    def source(self) -> Path:
        return self.root / "source"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def output(self) -> Path:
        return self.root / "output"

    def ensure(self) -> None:
        for d in (self.source, self.work, self.output):
            d.mkdir(parents=True, exist_ok=True)

    def item_work_dir(self, item_id: int) -> Path:
        """Thư mục làm việc riêng cho một item.

        Bắt buộc phải riêng: VideoLingo dùng thư mục ``output/`` toàn cục nên
        hai item chạy song song trong cùng thư mục sẽ ghi đè nhau.
        """
        d = self.work / f"item-{item_id:08d}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def absolute(self, relative: str) -> Path:
        """Đổi đường dẫn tương đối (như lưu trong DB) thành tuyệt đối.

        Từ chối đường dẫn tuyệt đối, đường dẫn thoát ra ngoài MEDIA_ROOT và
        đường dẫn không nằm trong ba vùng đã biết.
        """
        p = PurePosixPath(relative)
        if p.is_absolute() or relative.startswith("\\") or ":" in relative:
            raise ValueError(f"cần đường dẫn tương đối, nhận: {relative!r}")
        if ".." in p.parts:
            raise ValueError(f"đường dẫn thoát ra ngoài MEDIA_ROOT: {relative!r}")
        if not p.parts or p.parts[0] not in _ALLOWED_ROOTS:
            raise ValueError(
                f"đường dẫn phải bắt đầu bằng một trong {_ALLOWED_ROOTS}: {relative!r}"
            )
        return self.root.joinpath(*p.parts)

    def relative(self, absolute: Path) -> str:
        """Đổi đường dẫn tuyệt đối thành dạng tương đối để lưu DB (luôn dùng '/')."""
        rel = Path(absolute).resolve().relative_to(self.root.resolve())
        return rel.as_posix()
