"""License gate — nhóm test quan trọng nhất của dự án.

Mỗi test ở đây tương ứng một quy tắc nghiệp vụ trong AGENTS.md. Test đỏ ở file
này nghĩa là hệ thống có thể xử lý nguồn không có quyền — dừng lại và sửa,
không sửa test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.errors import (
    InvariantViolation,
    ScopeNotGranted,
    SourceExpired,
    SourceNotApproved,
)
from src.domain.sourcing.clearance import DownloadClearance, DubbingClearance
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    Language,
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)

FULL_SCOPE = LicenseScope(
    may_translate=True,
    may_modify_audio=True,
    may_subtitle=True,
    may_republish=True,
    may_commercial_use=True,
)
EVIDENCE = LicenseEvidence(
    license_type=LicenseType.VENDOR_MEDIAKIT,
    evidence_ref="https://vendor.example.com/media-kit-terms",
)


def make_source(**kw) -> Source:
    defaults = {
        "platform": Platform.YOUTUBE,
        "kind": SourceKind.CHANNEL,
        "url": SourceUrl("https://www.youtube.com/@VendorAutomation"),
        "id": 1,
    }
    return Source(**{**defaults, **kw})


def approved_source(*, scope: LicenseScope = FULL_SCOPE, **kw) -> Source:
    s = make_source(**kw)
    s.approve(by="quan.nguyen", evidence=EVIDENCE, scope=scope, at=NOW)
    return s


# ---------------- Quy tắc 1: không approved thì không tải ----------------


@pytest.mark.parametrize(
    "status", [ApprovalStatus.PENDING, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED]
)
def test_nguon_chua_approved_khong_cap_clearance_tai(status):
    s = make_source()
    s.status = status
    with pytest.raises(SourceNotApproved):
        s.clear_for_download(NOW)


def test_nguon_approved_cap_clearance_tai():
    clearance = approved_source().clear_for_download(NOW)
    assert clearance.source_id == 1


def test_license_het_han_thi_tu_choi_du_status_van_approved():
    s = approved_source()
    s.expires_at = NOW + timedelta(days=30)
    assert s.clear_for_download(NOW) is not None
    with pytest.raises(SourceExpired):
        s.clear_for_download(NOW + timedelta(days=31))


# ---------------- Quy tắc 2: quyền dùng lại không suy ra quyền sửa audio ----------------


def test_co_quyen_dung_lai_nhung_khong_co_quyen_sua_audio_thi_khong_long_tieng():
    """Đúng cái bẫy mà quy tắc nghiệp vụ số 2 nói tới."""
    s = approved_source(
        scope=LicenseScope(may_republish=True, may_commercial_use=True, may_translate=True)
    )
    s.clear_for_download(NOW)  # tải thì được
    with pytest.raises(ScopeNotGranted) as exc:
        s.clear_for_dubbing(NOW)
    assert "may_modify_audio" in str(exc.value)


@pytest.mark.parametrize("thieu", ["may_translate", "may_modify_audio", "may_subtitle"])
def test_thieu_bat_ky_quyen_nao_trong_ba_quyen_long_tieng_deu_bi_tu_choi(thieu):
    scope = LicenseScope(
        **{
            **dict.fromkeys(("may_translate", "may_modify_audio", "may_subtitle"), True),
            thieu: False,
        }
    )
    with pytest.raises(ScopeNotGranted) as exc:
        approved_source(scope=scope).clear_for_dubbing(NOW)
    assert thieu in str(exc.value)


def test_du_ba_quyen_thi_cap_clearance_long_tieng():
    c = approved_source().clear_for_dubbing(NOW)
    assert c.source_id == 1
    assert c.audio_lang == Language("en")


# ---------------- Quy tắc: clearance không thể tự dựng ở tầng ngoài ----------------


def test_khong_the_tu_dung_clearance_de_di_vong_qua_gate():
    """Đây là lý do clearance là một kiểu dữ liệu chứ không phải câu if.

    Tầng ngoài muốn bỏ qua gate thì phải tự dựng clearance, và việc đó bị chặn.
    """
    with pytest.raises(InvariantViolation):
        DownloadClearance(source_id=1, _grant=object())  # type: ignore[arg-type]
    with pytest.raises(InvariantViolation):
        DubbingClearance(source_id=1, _grant=None)  # type: ignore[arg-type]


# ---------------- Bất biến bằng chứng license ----------------


def test_khong_approve_duoc_ma_khong_co_bang_chung():
    with pytest.raises(InvariantViolation):
        LicenseEvidence(license_type=LicenseType.WRITTEN_PERMISSION, evidence_ref="   ")


def test_cc_by_bat_buoc_co_attribution():
    with pytest.raises(InvariantViolation) as exc:
        LicenseEvidence(license_type=LicenseType.CC_BY, evidence_ref="https://youtu.be/x")
    assert "attribution_text" in str(exc.value)


def test_dung_source_approved_ma_thieu_evidence_la_vi_pham_bat_bien():
    with pytest.raises(InvariantViolation):
        make_source(status=ApprovalStatus.APPROVED)


def test_phai_ghi_ai_duyet():
    with pytest.raises(InvariantViolation):
        make_source().approve(by="  ", evidence=EVIDENCE, scope=FULL_SCOPE, at=NOW)


# ---------------- Watermark dán cứng ----------------


def test_nen_tang_dan_watermark_cung_thi_mac_dinh_coi_la_co():
    """Người khai báo bỏ trống cũng vẫn phải đúng — thà thận trọng thừa."""
    s = make_source(platform=Platform.DOUYIN, has_baked_watermark=False)
    assert s.has_baked_watermark is True


def test_douyin_duoc_danh_dau_url_het_han_nhanh():
    s = approved_source(platform=Platform.DOUYIN, url=SourceUrl("https://www.douyin.com/user/abc"))
    assert s.clear_for_download(NOW).url_expires_fast is True


def test_youtube_khong_het_han_nhanh():
    assert approved_source().clear_for_download(NOW).url_expires_fast is False


# ---------------- Công duyệt theo ngôn ngữ nguồn ----------------


def test_nguon_tieng_trung_du_kien_cong_duyet_gap_doi():
    vi_en = approved_source(audio_lang=Language("en"))
    vi_zh = approved_source(audio_lang=Language("zh"))
    assert vi_en.expected_review_minutes == (20, 35)
    assert vi_zh.expected_review_minutes == (35, 55)


# ---------------- Value object ----------------


@pytest.mark.parametrize("bad", ["", "not-a-url", "ftp://x.com/a", "https://"])
def test_url_khong_hop_le_bi_tu_choi(bad):
    with pytest.raises(InvariantViolation):
        SourceUrl(bad)


def test_source_url_bo_www_khi_lay_host():
    assert SourceUrl("https://www.youtube.com/@x").host == "youtube.com"
