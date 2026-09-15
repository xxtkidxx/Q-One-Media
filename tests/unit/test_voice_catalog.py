"""Danh mục giọng đọc — chọn theo video, không theo biến môi trường.

Hai điều được giữ ở đây: giọng chưa dùng được vẫn **hiện ra** kèm lý do (giấu đi
thì người dùng tưởng hệ thống chỉ có một giọng), và một lựa chọn giọng hỏng
không được làm dừng cả video.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.tts.catalog import (
    EDGE_VOICES,
    FPTAI_VOICES,
    default_voice_id,
    find_voice,
    label_for,
    list_voices,
)
from src.infrastructure.tts.registry import build_synthesizer_for
from src.shared.config import LLMSettings, PublishSettings, Settings, TTSSettings


def _settings(tmp_path: Path, *, env="dev", **tts_kw) -> Settings:
    return Settings(
        app_env=env,
        database_url="postgresql://x/y",
        media_root=tmp_path,
        model_cache=tmp_path / "models",
        log_level="INFO",
        worker_concurrency=1,
        gpu_count=0,
        llm=LLMSettings(api_key=""),
        tts=TTSSettings(**tts_kw),
        publish=PublishSettings(),
    )


def test_danh_muc_co_du_bon_engine_va_noi_ro_cai_nao_chua_dung_duoc(tmp_path):
    voices = list_voices(_settings(tmp_path))
    by_engine = {voice.engine for voice in voices}
    assert by_engine == {"voxcpm", "vieneu", "fptai", "edge"}

    fptai = [voice for voice in voices if voice.engine == "fptai"]
    assert len(fptai) == len(FPTAI_VOICES)
    # Chưa có FPTAI_API_KEY: vẫn hiện, nhưng nói rõ thiếu gì.
    assert all(not voice.available for voice in fptai)
    assert all("FPTAI_API_KEY" in voice.note for voice in fptai)


def test_edge_hien_o_dev_nhung_khong_dung_duoc_o_prod(tmp_path):
    """Ràng buộc license, không phải chất lượng: edge là client không chính thức."""
    from src.shared.config import WebSettings

    dev = [v for v in list_voices(_settings(tmp_path)) if v.engine == "edge"]
    assert len(dev) == len(EDGE_VOICES)
    assert all(voice.available for voice in dev)

    prod = Settings(
        app_env="prod",
        database_url="postgresql://x/y",
        media_root=tmp_path,
        model_cache=tmp_path / "models",
        log_level="INFO",
        worker_concurrency=1,
        gpu_count=0,
        llm=LLMSettings(api_key=""),
        tts=TTSSettings(engine="voxcpm"),
        publish=PublishSettings(),
        web=WebSettings(user="a", password="b"),
    )
    edge_prod = [v for v in list_voices(prod) if v.engine == "edge"]
    assert edge_prod and all(not voice.available for voice in edge_prod)


def test_tha_file_mau_vao_thu_muc_voices_thi_thanh_mot_giong(tmp_path):
    """Thêm giọng clone = thả file, không phải sửa code."""
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "ky-su-nam.wav").write_bytes(b"RIFF")
    (tmp_path / "voices" / "ky-su-nam.txt").write_text("Lời đọc mẫu.", encoding="utf-8")
    (tmp_path / "voices" / "ghi-chu.md").write_text("bỏ qua", encoding="utf-8")

    voices = list_voices(_settings(tmp_path))
    cloned = [voice for voice in voices if voice.id == "voxcpm:ky-su-nam"]
    assert len(cloned) == 1
    assert cloned[0].ref_text == "Lời đọc mẫu."
    assert "clone sát hơn" in cloned[0].note
    # File không phải audio thì không thành giọng.
    assert not any(voice.id.endswith("ghi-chu") for voice in voices)


def test_mau_thieu_loi_doc_thi_noi_ro_clone_kem_sat_hon(tmp_path):
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "nu-mien-nam.wav").write_bytes(b"RIFF")
    voice = find_voice("voxcpm:nu-mien-nam", _settings(tmp_path))
    assert voice is not None and voice.ref_text is None
    assert "Thiếu file .txt" in voice.note


def test_voxcpm_dung_toan_bo_mau_vieneu_da_cache(tmp_path):
    preview_dir = tmp_path / "work" / "voice-previews"
    preview_dir.mkdir(parents=True)
    (preview_dir / "vieneu-pham-tuyen.wav").write_bytes(b"RIFF-preview")

    voice = find_voice("voxcpm:vieneu-pham-tuyen", _settings(tmp_path))
    assert voice is not None
    assert voice.label == "VoxCPM2 clone — Phạm Tuyên"
    assert voice.gender == "nam" and voice.region == "Bắc"
    assert voice.ref_text == "Xin chào, đây là giọng đọc thử cho video của Q One Media."


@pytest.mark.parametrize(
    "engine,expected",
    [
        ("voxcpm", "voxcpm:default"),
        ("fptai", "fptai:banmai"),
        ("edge", f"edge:{EDGE_VOICES[0][0]}"),
    ],
)
def test_mac_dinh_suy_tu_tts_engine_de_giu_hanh_vi_cu(tmp_path, engine, expected):
    assert default_voice_id(_settings(tmp_path, engine=engine)) == expected


def test_nhan_hien_thi_roi_ve_id_khi_giong_khong_con_trong_danh_muc(tmp_path):
    settings = _settings(tmp_path)
    assert label_for("voxcpm:default", settings).startswith("VoxCPM2")
    assert label_for("voxcpm:da-xoa", settings) == "voxcpm:da-xoa"
    assert label_for(None, settings) == "Giọng mặc định"


def test_giong_hong_thi_roi_ve_mac_dinh_chu_khong_dung_video(tmp_path, monkeypatch):
    """Một lựa chọn giọng không còn dùng được là chuyện nhỏ; dừng video là chuyện lớn."""
    settings = _settings(tmp_path, engine="edge")
    built: list[str] = []

    class FakeEdge:
        def __init__(self, *, voice, measured_syllables_per_sec=None):
            built.append(voice)

    import src.infrastructure.tts.edge as edge_mod

    monkeypatch.setattr(edge_mod, "EdgeTtsSynthesizer", FakeEdge)

    build_synthesizer_for("fptai:banmai", settings)  # thiếu API key → không dùng được
    build_synthesizer_for("edge:vi-VN-NamMinhNeural", settings)
    assert built == [EDGE_VOICES[0][0], "vi-VN-NamMinhNeural"]


def test_chon_giong_fptai_thi_dung_dung_ten_giong(tmp_path, monkeypatch):
    settings = _settings(tmp_path, engine="voxcpm", fptai_api_key="key")
    seen: list[str] = []

    class FakeFpt:
        def __init__(self, *, api_key, voice, measured_syllables_per_sec=None):
            seen.append(voice)

    import src.infrastructure.tts.fptai as fptai_mod

    monkeypatch.setattr(fptai_mod, "FptAiSynthesizer", FakeFpt)
    build_synthesizer_for("fptai:lannhi", settings)
    assert seen == ["lannhi"]


# ---------------- VieNeu-TTS: 20 giọng dựng sẵn ----------------


def test_vieneu_gop_du_20_giong_va_du_ba_mien(tmp_path):
    """Nguồn giọng dùng-được-ngay lớn nhất: không cần thu mẫu như VoxCPM2."""
    from src.infrastructure.tts.vieneu import PRESETS

    voices = [v for v in list_voices(_settings(tmp_path)) if v.engine == "vieneu"]
    assert len(voices) == len(PRESETS) == 20
    assert {v.region for v in voices} == {"Bắc", "Trung", "Nam"}
    assert {v.gender for v in voices} == {"nam", "nữ"}
    assert all(v.id.startswith("vieneu:") for v in voices)


def test_catalog_api_khong_khoa_giong_duoc_cai_o_worker(tmp_path):
    """API chỉ lập catalog; package/model nặng thuộc image worker riêng."""
    voices = [v for v in list_voices(_settings(tmp_path)) if v.engine == "vieneu"]
    assert voices and all(v.available for v in voices)


def test_vox_va_edge_co_duong_dan_nghe_thu(tmp_path):
    voices = list_voices(_settings(tmp_path))

    vox = next(v for v in voices if v.id == "voxcpm:default")
    assert vox.preview_path == tmp_path / "work/voice-previews/voxcpm-default.wav"

    edge = [v for v in voices if v.engine == "edge"]
    assert [v.preview_path for v in edge] == [
        tmp_path / "work/voice-previews" / f"edge-{voice[0]}.mp3"
        for voice in EDGE_VOICES
    ]


def test_chon_giong_vieneu_thi_dung_dung_ten_trong_api(tmp_path, monkeypatch):
    """Id dùng slug ASCII, còn API của thư viện nhận tên có dấu — map phải đúng."""
    import src.infrastructure.tts.vieneu as vieneu_mod

    seen: list[str] = []

    class FakeVieNeu:
        def __init__(self, *, voice, measured_syllables_per_sec=None):
            seen.append(voice)

    monkeypatch.setattr(vieneu_mod, "VieNeuSynthesizer", FakeVieNeu)
    build_synthesizer_for("vieneu:ngoc-tran", _settings(tmp_path))
    assert seen == ["Ngọc Trân"]


def test_vieneu_khong_clone_thi_noi_ra_chu_khong_doi_giong_am_tham(tmp_path, caplog):
    from src.infrastructure.tts.vieneu import VieNeuRejected, VieNeuSynthesizer

    synth = VieNeuSynthesizer(voice="Minh Đức")
    with pytest.raises(VieNeuRejected):
        synth.synthesize(text="   ", dest=tmp_path / "a.wav", clearance=None)
