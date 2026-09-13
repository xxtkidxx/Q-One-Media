"""Mặt tiền web — kiểm bằng TestClient trên Postgres thật.

Nhóm test này tồn tại vì lý do cụ thể: mặt tiền web là nơi **người** ra quyết
định license và duyệt nội dung. Một form thiếu ô, một nhãn sai, hay một checkbox
không được đọc là dẫn tới quyết định pháp lý sai — và unit test của use case
không bắt được loại lỗi đó.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("thiếu DATABASE_URL — chạy trong container")
    from fastapi.testclient import TestClient

    from src.interfaces.api.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db(client):
    from src.interfaces.api.deps import get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "TRUNCATE publications, jobs, items, audit_log, sources "
                "RESTART IDENTITY CASCADE"
            )
        )
        uow.commit()


# ---------------- Trang hiển thị được ----------------


@pytest.mark.parametrize("path", ["/web", "/web/sources", "/web/review"])
def test_cac_trang_hien_duoc_khi_khong_co_du_lieu(client, path):
    """Trang trống phải nói rõ là trống, không được nổ."""
    resp = client.get(path)
    assert resp.status_code == 200
    assert "Q One Media" in resp.text


def test_trang_nguon_loc_theo_trang_thai_khong_hop_le_thi_bao_400(client):
    assert client.get("/web/sources?status=khong-ton-tai").status_code == 400


# ---------------- Vòng đời qua form ----------------


def _declare(client, **over):
    data = {
        "url": "https://www.youtube.com/@FormVendor",
        "platform": "youtube",
        "kind": "channel",
        "actor": "quan.nguyen",
        "audio_lang": "en",
        "external_owner_id": "UCform0001",
        "topics": "spc, vision",
        "display_name": "Form Vendor",
        "notes": "",
    }
    data.update(over)
    return client.post("/web/sources", data=data, follow_redirects=False)


def _approve(client, source_id, **over):
    data = {
        "actor": "quan.nguyen",
        "license_type": "vendor-mediakit",
        "evidence_ref": "https://vendor.example.com/terms",
        "attribution_text": "",
    }
    data.update(over)
    return client.post(
        f"/web/sources/{source_id}/approve", data=data, follow_redirects=False
    )


def test_khai_bao_roi_duyet_roi_nap_url(client):
    assert _declare(client).status_code == 303
    assert _approve(
        client,
        1,
        may_translate="true",
        may_modify_audio="true",
        may_subtitle="true",
        may_republish="true",
        may_commercial_use="true",
    ).status_code == 303

    resp = client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=form01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert client.get("/web").text.count('class="num">1') >= 1


def test_khai_bao_trung_thi_hien_trang_loi_de_doc_khong_phai_500(client):
    _declare(client)
    resp = _declare(client)
    assert resp.status_code == 200  # trang lỗi, không phải mã 4xx/5xx
    assert "Không khai báo được nguồn" in resp.text
    assert "đã được khai báo" in resp.text


def test_nap_url_khong_thuoc_nguon_nao_thi_noi_ro_phai_lam_gi(client):
    resp = client.post(
        "/web/items", data={"url": "https://vimeo.com/999", "actor": "q"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "khai báo nguồn" in resp.text


def test_nguon_chua_duyet_thi_url_bi_chan_va_trang_noi_ro_ly_do(client):
    """Người dùng phải hiểu vì sao bị chặn, không chỉ thấy nó không chạy."""
    _declare(client)
    resp = client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=blocked", "actor": "q"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "license gate chặn" in resp.text
    assert "pending" in resp.text


# ---------------- Form license: chỗ dễ gây quyết định sai ----------------


def test_checkbox_khong_tick_thi_quyen_khong_duoc_cap(client):
    """Mặc định của checkbox HTML là không gửi gì khi không tick.

    Nếu backend hiểu sai điều đó thành True thì mọi nguồn duyệt qua web sẽ có đủ
    quyền lồng tiếng mà không ai chọn — đúng loại lỗi im lặng tệ nhất.
    """
    _declare(client)
    _approve(client, 1, may_republish="true")  # chỉ tick một quyền
    page = client.get("/web/sources?status=approved").text
    assert "chưa được sửa audio" in page

    detail = client.get("/sources/1").json()
    assert detail["scope"]["may_republish"] is True
    assert detail["scope"]["may_modify_audio"] is False
    assert detail["scope"]["may_translate"] is False


def test_trang_nguon_canh_bao_khi_thieu_external_owner_id(client):
    """Nguồn dạng bao thiếu id chủ kênh thì URL nạp vào sẽ bị chặn — nói trước."""
    _declare(client, external_owner_id="")
    assert "thiếu external_owner_id" in client.get("/web/sources?status=pending").text


def test_duyet_thieu_bang_chung_thi_bao_loi_chu_khong_luu(client):
    _declare(client)
    resp = _approve(client, 1, evidence_ref="   ")
    assert resp.status_code == 200
    assert "Không duyệt được nguồn" in resp.text
    assert client.get("/sources/1").json()["status"] == "pending"


def test_cc_by_thieu_ghi_nguon_thi_bi_tu_choi(client):
    _declare(client)
    resp = _approve(client, 1, license_type="cc-by", attribution_text="")
    assert resp.status_code == 200
    assert "attribution_text" in resp.text


def test_nguon_douyin_hien_canh_bao_watermark(client):
    _declare(
        client,
        url="https://www.douyin.com/user/abc",
        platform="douyin",
        kind="creator-page",
        external_owner_id="MS4w",
    )
    assert "watermark dán cứng" in client.get("/web/sources?status=pending").text


# ---------------- Gate duyệt ----------------


def test_duyet_khong_ghi_ten_nguoi_duyet_thi_bi_tu_choi(client):
    resp = client.post(
        "/web/review/1/approve", data={"actor": "  ", "notes": ""}, follow_redirects=False
    )
    assert resp.status_code == 200
    assert "Thiếu tên người duyệt" in resp.text


def test_tu_choi_ma_khong_ghi_ly_do_thi_bi_chan(client):
    resp = client.post(
        "/web/review/1/reject", data={"actor": "q", "notes": ""}, follow_redirects=False
    )
    assert resp.status_code == 200
    assert "Thiếu lý do" in resp.text


def test_tra_ve_viet_lai_ma_khong_ghi_ly_do_thi_bi_chan(client):
    """Lý do được đưa thẳng vào prompt viết lại — để trống là làm bản sau vô ích."""
    resp = client.post(
        "/web/review/1/rewrite", data={"actor": "q", "notes": ""}, follow_redirects=False
    )
    assert resp.status_code == 200
    assert "prompt" in resp.text


def test_item_khong_ton_tai_thi_404(client):
    assert client.get("/web/review/99999").status_code == 404


# ---------------- Không phục vụ file ngoài output ----------------


def test_chi_mount_thu_muc_output(client):
    """``source/`` chứa video gốc của người khác, ``work/`` chứa file trung gian —
    không có lý do gì để chúng ra được HTTP."""
    assert client.get("/media/source/a.mp4").status_code == 404
    assert client.get("/media/work/a.wav").status_code == 404
