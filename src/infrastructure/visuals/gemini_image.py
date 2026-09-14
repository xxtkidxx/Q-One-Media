"""Sinh ảnh minh hoạ bằng Gemini REST — **tuỳ chọn**, và chỉ cho bối cảnh.

Giới hạn "chỉ bối cảnh" là quy tắc biên tập, không phải hạn chế kỹ thuật: ảnh AI
đặt vào chỗ minh hoạ một dữ kiện kỹ thuật sẽ *minh hoạ sai* — một biểu đồ Cpk do
model vẽ trông rất thuyết phục và hoàn toàn bịa. Số liệu đi qua cảnh ``chart``,
nơi từng cột cao đúng theo con số người dùng nhập.

Gọi REST bằng ``httpx`` đã có sẵn, không thêm SDK — cùng lý lẽ với adapter LLM.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.shared.logging import get_logger

log = get_logger(__name__)

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
STYLE = (
    "Ảnh nền cho short video công nghiệp, phong cách ảnh chụp nhà máy hiện đại, "
    "tông xanh đậm #081120, không chữ, không logo, không biểu đồ, không số liệu. "
)


@dataclass(frozen=True, slots=True)
class GeminiImageGenerator:
    api_key: str
    model: str = "gemini-3-pro-image"
    timeout_sec: float = 60.0

    def generate(self, *, prompt: str, out_dir: Path, name: str) -> str | None:
        """Trả đường dẫn **tuyệt đối** tới ảnh, hoặc ``None`` nếu không sinh được.

        ``None`` không phải lỗi: người gọi rơi về thẻ thương hiệu. Vì vậy ở đây
        không ném ngoại lệ cho mọi thất bại thường gặp — hết quota, model từ chối
        prompt, mạng lỗi — mà ghi log rồi trả ``None``.
        """
        if not self.api_key or not prompt.strip():
            return None
        payload = {
            "contents": [{"parts": [{"text": STYLE + prompt.strip()}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        try:
            response = httpx.post(
                ENDPOINT.format(model=self.model),
                params={"key": self.api_key},
                json=payload,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            log.warning("visuals.generate.failed", error=str(exc)[:200])
            return None

        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                blob = part.get("inlineData") or part.get("inline_data")
                if not blob or not blob.get("data"):
                    continue
                out_dir.mkdir(parents=True, exist_ok=True)
                path = out_dir / f"{name}.png"
                path.write_bytes(base64.b64decode(blob["data"]))
                log.info("visuals.generate.done", path=str(path))
                return str(path)
        log.warning("visuals.generate.empty", model=self.model)
        return None
