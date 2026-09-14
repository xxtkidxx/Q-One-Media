"""Chọn nhà cung cấp sinh ảnh từ cấu hình. Chưa cấu hình → bộ sinh rỗng."""

from __future__ import annotations

from pathlib import Path

from src.shared.config import Settings


class NullImageGenerator:
    """Không sinh gì, và đó là một câu trả lời hợp lệ.

    Giữ một hiện thực rỗng thay vì để ``None`` trôi khắp nơi: người gọi không
    phải kiểm ``if generator is not None`` ở bốn chỗ, và quy tắc "thiếu ảnh thì
    rơi về thẻ thương hiệu" nằm đúng một chỗ.
    """

    def generate(self, *, prompt: str, out_dir: Path, name: str) -> str | None:
        return None


def build_image_generator(settings: Settings):
    if not settings.visuals.enabled:
        return NullImageGenerator()
    if settings.visuals.provider == "gemini":
        from src.infrastructure.visuals.gemini_image import GeminiImageGenerator

        return GeminiImageGenerator(
            api_key=settings.visuals.api_key, model=settings.visuals.model
        )
    return NullImageGenerator()
