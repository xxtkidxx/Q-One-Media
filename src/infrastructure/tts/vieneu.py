"""Adapter VieNeu-TTS — 20 giọng Việt sẵn có, miễn phí và dùng thương mại được.

Vì sao thêm engine thứ tư khi đã có VoxCPM2: dự án đang có đúng **hai** giọng
dùng ngay được (và cả hai thuộc edge-tts, chỉ dev). VoxCPM2 clone rất tốt nhưng
đòi audio mẫu — chưa thu mẫu thì chưa có giọng để chọn. VieNeu-TTS lấp đúng chỗ
đó: 20 giọng dựng sẵn, đủ Bắc/Trung/Nam và cả nam lẫn nữ, không cần mẫu.

License đã kiểm **trên model card**, không tin license của code (quy tắc của dự
án sau hai lần suýt lọt model NonCommercial):

- ``pnnbao-ump/VieNeu-TTS-v3-Turbo`` — ``apache-2.0``, model card nói thẳng audio
  sinh ra **dùng được cho nội dung thương mại và có kiếm tiền**.
- Base ``neuphonic/neutts-air`` — ``apache-2.0``.
- Codec ``neuphonic/neucodec`` — ``apache-2.0``, dữ liệu huấn luyện CC-BY-4.0/CC0.

Một điểm kỹ thuật đáng giá với máy hiện tại: chạy được **hoàn toàn trên CPU**
qua ONNX Runtime, không cần torch. Card 8 GB đang phải chạy tuần tự Demucs →
Whisper → VoxCPM2 (D54); một engine giọng không tranh VRAM nghĩa là bước lồng
tiếng chạy song song được với bước khác thay vì xếp hàng.

Adapter này chỉ dùng **giọng dựng sẵn**. Clone giọng vẫn là việc của VoxCPM2 —
không viết một đường clone thứ hai khi chưa kiểm chứng được nó bằng máy thật.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.domain.sourcing.clearance import DubbingClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

DEFAULT_MODEL = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
SAMPLE_RATE = 48_000

# (slug, tên gọi trong API, giới tính, vùng) — theo model card v3 Turbo.
PRESETS: tuple[tuple[str, str, str, str], ...] = (
    ("pham-tuyen", "Phạm Tuyên", "nam", "Bắc"),
    ("minh-duc", "Minh Đức", "nam", "Bắc"),
    ("thanh-binh", "Thanh Bình", "nam", "Bắc"),
    ("ngoc-huyen", "Ngọc Huyền", "nữ", "Bắc"),
    ("truc-ly", "Trúc Ly", "nữ", "Bắc"),
    ("doan-trang", "Đoan Trang", "nữ", "Bắc"),
    ("ngoc-linh", "Ngọc Linh", "nữ", "Bắc"),
    ("mai-anh", "Mai Anh", "nữ", "Bắc"),
    ("quynh-anh", "Quỳnh Anh", "nữ", "Bắc"),
    ("quang-son", "Quang Sơn", "nam", "Trung"),
    ("ngoc-tran", "Ngọc Trân", "nữ", "Trung"),
    ("adam", "Adam", "nam", "Nam"),
    ("thai-son", "Thái Sơn", "nam", "Nam"),
    ("minh-triet", "Minh Triết", "nam", "Nam"),
    ("duc-tri", "Đức Trí", "nam", "Nam"),
    ("xuan-vinh", "Xuân Vĩnh", "nam", "Nam"),
    ("thuc-doan", "Thục Đoan", "nữ", "Nam"),
    ("thuy-dung", "Thùy Dung", "nữ", "Nam"),
    ("kim-thanh", "Kim Thanh", "nữ", "Nam"),
    ("my-duyen", "Mỹ Duyên", "nữ", "Nam"),
)
PRESET_BY_SLUG = {slug: name for slug, name, _, _ in PRESETS}


class VieNeuFailed(RuntimeError):
    retryable = True


class VieNeuRejected(RuntimeError):
    retryable = False


@dataclass
class VieNeuSynthesizer:
    """Hiện thực port ``SpeechSynthesizer`` bằng giọng dựng sẵn của VieNeu-TTS."""

    voice: str = "Minh Đức"
    model_id: str = DEFAULT_MODEL
    measured_syllables_per_sec: float | None = None
    _engine: object | None = field(default=None, repr=False)

    def measured_rate(self) -> float | None:
        return self.measured_syllables_per_sec

    def synthesize(
        self,
        *,
        text: str,
        dest: Path,
        clearance: DubbingClearance,
        voice_ref: Path | None = None,
    ) -> Path:
        """Sinh audio tiếng Việt bằng một giọng dựng sẵn.

        ``clearance`` bắt buộc theo port: lồng tiếng cần quyền sửa audio, và chỉ
        ``Source`` cấp được vật chứng minh quyền đó.
        """
        if not text.strip():
            raise VieNeuRejected("không sinh giọng từ chuỗi rỗng")
        if voice_ref is not None:
            # Nói ra thay vì lặng lẽ bỏ qua: người dùng chọn giọng clone thì phải
            # biết engine này không clone, chứ không nhận một giọng khác mà tưởng đúng.
            log.warning(
                "vieneu.voice_ref.ignored",
                reason="engine này chỉ dùng giọng dựng sẵn; clone giọng dùng VoxCPM2",
            )

        engine = self._load()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            audio = engine.infer(text, voice=self.voice)
            engine.save(audio, str(dest))
        except Exception as exc:
            raise VieNeuFailed(f"VieNeu-TTS sinh giọng thất bại: {exc}") from exc
        if not dest.exists() or dest.stat().st_size == 0:
            raise VieNeuFailed(f"VieNeu-TTS không ghi được audio ra {dest}")
        log.info(
            "vieneu.synthesize", voice=self.voice, chars=len(text), bytes=dest.stat().st_size
        )
        return dest

    def _load(self):
        if self._engine is not None:
            return self._engine
        try:
            from vieneu import Vieneu
        except ImportError as exc:
            raise VieNeuRejected(
                "chưa cài gói `vieneu` — thêm vào requirements của worker rồi build lại image"
            ) from exc
        try:
            self._engine = Vieneu(model=self.model_id) if self.model_id else Vieneu()
        except TypeError:
            # Chữ ký khác giữa các bản: rơi về mặc định của thư viện thay vì nổ.
            self._engine = Vieneu()
        except Exception as exc:
            raise VieNeuFailed(f"không nạp được VieNeu-TTS: {exc}") from exc
        return self._engine
