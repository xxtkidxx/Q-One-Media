"""Chọn engine TTS, và lớp chặn engine dev khỏi production.

Nhóm test này bảo vệ một quyết định **license**, không phải kỹ thuật: ``edge-tts``
là client không chính thức của dịch vụ Microsoft Edge nên không dùng thương mại
được. Dự án đã bỏ OmniVoice của VoiceStudio vì đúng loại vấn đề đó (weights
CC-BY-NC) — giữ một chuẩn thì phải giữ cả ở đây.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.tts.edge import VOICE_FEMALE, VOICE_MALE, EdgeTtsRejected
from src.infrastructure.tts.registry import build_synthesizer
from src.shared.config import (
    ConfigError,
    LLMSettings,
    PublishSettings,
    Settings,
    TTSSettings,
    WebSettings,
)


def _settings(*, env: str = "dev", engine: str = "voxcpm", **tts_kw) -> Settings:
    return Settings(
        app_env=env,
        database_url="postgresql://x/y",
        media_root=Path("/data/media"),
        model_cache=Path("/models"),
        log_level="INFO",
        worker_concurrency=1,
        gpu_count=0,
        llm=LLMSettings(api_key=""),
        tts=TTSSettings(engine=engine, **tts_kw),
        publish=PublishSettings(),
        web=WebSettings(user="u", password="p"),
    )


# ---------------- Chặn edge khỏi production ----------------


def test_engine_edge_bi_chan_ngay_khi_doc_config_o_prod():
    """Lớp thứ nhất: config từ chối, nên tiến trình không khởi động được."""
    with pytest.raises(ConfigError) as exc:
        _settings(env="prod", engine="edge")
    assert "chỉ dùng cho dev" in str(exc.value)


def test_engine_edge_bi_chan_lan_hai_o_registry():
    """Lớp thứ hai. Hai lớp vì đây là ràng buộc license, không phải tuỳ chọn.

    Dựng Settings với app_env=dev rồi đổi sang prod mô phỏng đúng cách một cấu
    hình có thể lọt qua lớp đầu: ai đó đổi biến môi trường sau khi đã đọc config.
    """
    settings = _settings(env="dev", engine="edge")
    object.__setattr__(settings, "app_env", "prod")
    with pytest.raises(ConfigError) as exc:
        build_synthesizer(settings)
    assert "không dùng được ở production" in str(exc.value)


def test_engine_edge_chay_duoc_o_dev():
    synth = build_synthesizer(_settings(env="dev", engine="edge"))
    assert synth.name == "edge"


# ---------------- Chọn engine ----------------


def test_engine_khong_nhan_ra_thi_bao_loi_kem_danh_sach():
    with pytest.raises(ConfigError) as exc:
        build_synthesizer(_settings(engine="khong-ton-tai"))
    assert "voxcpm" in str(exc.value)
    assert "fptai" in str(exc.value)
    assert "edge" in str(exc.value)


def test_fptai_thieu_khoa_thi_bao_loi_ro():
    with pytest.raises(ConfigError) as exc:
        build_synthesizer(_settings(engine="fptai"))
    assert "FPTAI_API_KEY" in str(exc.value)


def test_ten_engine_khong_phan_biet_hoa_thuong_va_khoang_trang():
    """Biến môi trường viết tay rất dễ có khoảng trắng ở cuối."""
    assert build_synthesizer(_settings(engine=" EDGE ")).name == "edge"


# ---------------- Giọng ----------------


def test_chi_nhan_hai_giong_tieng_viet_da_xac_minh():
    """Đã xác minh 14/09/2026 bằng edge_tts.list_voices(): đúng hai giọng vi-VN."""
    from src.infrastructure.tts.edge import EdgeTtsSynthesizer

    assert EdgeTtsSynthesizer(voice=VOICE_FEMALE).name == "edge"
    assert EdgeTtsSynthesizer(voice=VOICE_MALE).name == "edge"
    with pytest.raises(EdgeTtsRejected) as exc:
        EdgeTtsSynthesizer(voice="vi-VN-KhongTonTai")
    assert "đã xác minh" in str(exc.value)


def test_toc_do_doc_do_duoc_di_qua_registry():
    synth = build_synthesizer(
        _settings(env="dev", engine="edge", measured_rate=3.54)
    )
    assert synth.measured_rate() == 3.54


def test_chua_do_thi_measured_rate_la_none():
    """None là mặc định có chủ ý: use case phải từ chối chạy chứ không đoán."""
    assert build_synthesizer(_settings(env="dev", engine="edge")).measured_rate() is None
