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
    dashboard = client.get("/web").text
    assert "Tổng nội dung" in dashboard
    assert "Nguồn #1" in dashboard


def test_them_nguon_video_chi_xep_tai_khi_nguoi_dung_bam_start(client):
    resp = _declare(
        client,
        url="https://www.youtube.com/watch?v=auto01",
        kind="single-url",
        external_owner_id="",
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/sources"
    assert client.get("/sources/1").json()["status"] == "pending"

    _approve(client, 1, may_republish="true")
    page = client.get("/web/sources").text
    assert "Start tải video" in page
    resp = client.post("/web/sources/1/start", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/sources?auto_started=1"

    from src.interfaces.api.deps import get_uow

    uow = get_uow()
    with uow:
        item = uow.session.execute(
            text("SELECT source_id, stage FROM items WHERE id=1")
        ).one()
        task = uow.session.execute(
            text("SELECT task FROM jobs WHERE item_id=1")
        ).scalar_one()
    assert item == (1, "inbox")
    assert task == "download"
    status = client.get("/web/item-status").json()["items"]
    assert status[0]["id"] == 1
    assert status[0]["stage"] == "inbox"
    assert status[0]["progress"] == 5
    assert status[0]["step"] == 1
    assert status[0]["total_steps"] == 15
    assert status[0]["label"] == "Đang tải video"


def test_trang_nguon_mac_dinh_hien_tat_ca_va_co_bo_loc_phan_trang_popup(client):
    _declare(client, display_name="Nguồn đang chờ")
    _declare(
        client,
        url="https://www.youtube.com/@ApprovedVendor",
        external_owner_id="UCapproved",
        display_name="Nguồn đã duyệt",
    )
    _approve(client, 2, may_republish="true")

    page = client.get("/web/sources").text
    assert "Nguồn đang chờ" in page
    assert "Nguồn đã duyệt" in page
    assert "Tất cả" in page
    assert "10 / trang" in page
    assert "Thêm nguồn" in page
    assert "Nạp video" in page
    assert "type=\"file\"" in page
    # Nạp video = tạo nguồn mới (không còn ô chọn nguồn có sẵn); nạp vào nguồn đã có
    # là việc riêng của nút Upload file trên từng dòng.
    assert "action=\"/web/uploads\"" in page
    assert "name=\"source_id\"" not in page
    assert "openRowUpload(2," in page
    assert "action=\"/web/items\"" not in page
    assert "Gợi ý điền" in page
    assert "Thông tin bổ sung (không bắt buộc)" in page

    searched = client.get("/web/sources?q=đã+duyệt").text
    assert "Nguồn đã duyệt" in searched
    assert "Nguồn đang chờ" not in searched


def test_upload_video_gan_nguon_va_xep_buoc_tach_audio(client, monkeypatch):
    _declare(client)
    _approve(client, 1, may_modify_audio="true")

    from src.interfaces.api.deps import get_config, get_uow
    from src.interfaces.web import routes

    monkeypatch.setattr(
        routes.ffmpeg,
        "probe",
        lambda _path: type(
            "Info",
            (),
            {
                "has_video": True,
                "has_audio": True,
                "width": 1920,
                "height": 1080,
                "duration_sec": 61.2,
            },
        )(),
    )
    resp = client.post(
        "/web/sources/1/uploads",
        data={"actor": "quan.nguyen"},
        files={"video": ("demo.mp4", b"video-test", "video/mp4")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/sources?uploaded=1"

    uow = get_uow()
    with uow:
        row = uow.session.execute(
            text(
                "SELECT source_id, stage, path_source, duration_sec, aspect_ratio "
                "FROM items WHERE id=1"
            )
        ).one()
        task = uow.session.execute(
            text("SELECT task FROM jobs WHERE item_id=1")
        ).scalar_one()
    assert row.source_id == 1
    assert row.stage == "downloaded"
    assert row.duration_sec == 61
    assert row.aspect_ratio == "16:9"
    assert task == "separate"
    get_config().paths.absolute(row.path_source).unlink(missing_ok=True)

def test_nut_nap_video_tao_nguon_moi_va_van_qua_license_gate(client, monkeypatch):
    """“Nạp video” là tạo nguồn mới; nạp vào nguồn có sẵn là việc của nút Upload file.

    Gộp ba bước vào một màn hình **không** được nới license gate: nguồn mới vẫn đi
    qua khai báo → duyệt với phạm vi quyền, rồi mới nhận file.
    """
    from src.interfaces.api.deps import get_config, get_uow
    from src.interfaces.web import routes

    monkeypatch.setattr(
        routes.ffmpeg,
        "probe",
        lambda _path: type(
            "Info",
            (),
            {
                "has_video": True,
                "has_audio": True,
                "width": 1080,
                "height": 1920,
                "duration_sec": 45.0,
            },
        )(),
    )
    resp = client.post(
        "/web/uploads",
        data={
            "url": "https://www.youtube.com/watch?v=newsrc01",
            "display_name": "Nguồn nạp tay",
            "platform": "youtube",
            "audio_lang": "en",
            "license_type": "own",
            "actor": "quan.nguyen",
            "may_translate": "true",
            "may_modify_audio": "true",
            "may_subtitle": "true",
        },
        files={"video": ("moi.mp4", b"video-test", "video/mp4")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/sources?uploaded=1"

    uow = get_uow()
    with uow:
        source = uow.session.execute(
            text(
                "SELECT id, status, kind, display_name, may_modify_audio, evidence_ref "
                "FROM sources WHERE id=1"
            )
        ).one()
        item = uow.session.execute(
            text("SELECT source_id, stage, path_source FROM items WHERE id=1")
        ).one()
    assert (source.status, source.kind, source.display_name) == (
        "approved", "single-url", "Nguồn nạp tay",
    )
    assert source.may_modify_audio is True
    assert "quan.nguyen" in source.evidence_ref  # xác nhận nội bộ, không bịa bằng chứng
    assert (item.source_id, item.stage) == (1, "downloaded")
    get_config().paths.absolute(item.path_source).unlink(missing_ok=True)


def test_nap_video_thieu_giay_phep_thi_khong_de_lai_file_rac(client, monkeypatch):
    """URL trùng nguồn đã khai → dừng lại, và file vừa ghi phải được dọn."""
    _declare(client, url="https://www.youtube.com/watch?v=dup01", kind="single-url")

    from src.interfaces.web import routes

    monkeypatch.setattr(routes.ffmpeg, "probe", lambda _path: pytest.fail("không được probe"))
    resp = client.post(
        "/web/uploads",
        data={
            "url": "https://www.youtube.com/watch?v=dup01",
            "platform": "youtube",
            "license_type": "own",
            "actor": "quan.nguyen",
        },
        files={"video": ("trung.mp4", b"video-test", "video/mp4")},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "đã được khai báo" in resp.text

    from src.interfaces.api.deps import get_config

    uploads = get_config().paths.source / "uploads"
    assert not list(uploads.glob("*.mp4"))


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


def test_duyet_khong_nhap_bang_chung_thi_tu_ghi_xac_nhan_noi_bo(client):
    _declare(client)
    resp = _approve(client, 1, evidence_ref="   ")
    assert resp.status_code == 303
    detail = client.get("/sources/1").json()
    assert detail["status"] == "approved"
    assert detail["evidence_ref"].startswith("Xác nhận giấy phép có sẵn bởi")


def test_cc_by_thieu_ghi_nguon_thi_tu_tao_tu_thong_tin_nguon(client):
    _declare(client)
    resp = _approve(client, 1, license_type="cc-by", attribution_text="")
    assert resp.status_code == 303
    attribution = client.get("/sources/1").json()["attribution_text"]
    assert "Form Vendor" in attribution
    assert "youtube.com/@FormVendor" in attribution


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
    """Lỗi quay về đúng trang review, không nhảy sang URL của POST."""
    resp = client.post(
        "/web/review/1/approve", data={"actor": "  ", "notes": ""}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/web/review/1?error=")
    assert "Thi%E1%BA%BFu%20t%C3%AAn%20ng%C6%B0%E1%BB%9Di%20duy%E1%BB%87t" in (
        resp.headers["location"]
    )


def test_tu_choi_ma_khong_ghi_ly_do_thi_bi_chan(client):
    resp = client.post(
        "/web/review/1/reject", data={"actor": "q", "notes": ""}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/web/review/1?error=")


def test_tra_ve_viet_lai_ma_khong_ghi_ly_do_thi_bi_chan(client):
    """Lý do được đưa thẳng vào prompt viết lại — để trống là làm bản sau vô ích."""
    resp = client.post(
        "/web/review/1/rewrite", data={"actor": "q", "notes": ""}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert "prompt" in resp.headers["location"]


def test_soat_transcript_hien_nguon_va_thong_bao_sau_khi_duyet(client):
    _declare(client)
    _approve(
        client,
        1,
        may_translate="true",
        may_modify_audio="true",
        may_subtitle="true",
        may_republish="true",
        may_commercial_use="true",
    )
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=form01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.interfaces.api.deps import get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(text("UPDATE items SET stage='transcript_review' WHERE id=1"))
        uow.commit()

    page = client.get("/web/transcripts")
    assert "Nguồn #1" in page.text
    assert "Form Vendor" in page.text

    resp = client.post(
        "/web/transcripts/1/approve",
        data={"actor": "quan.nguyen"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # Việc kế tiếp sau khi soát transcript là chọn đoạn, và form đó nằm ở trang review.
    assert resp.headers["location"] == "/web/review/1?approved=1"

    done = client.get(resp.headers["location"])
    assert "Transcript đã được duyệt" in done.text
    assert 'action="/web/items/1/clips"' in done.text


def test_bien_tap_transcript_tren_trang_review_rieng(client):
    _declare(client)
    _approve(client, 1, may_modify_audio="true", may_subtitle="true")
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=editor01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.application.use_cases.write_script import load_transcript, save_transcript
    from src.interfaces.api.deps import get_config, get_uow

    config = get_config()
    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='transcript_review', path_source=:path, "
                "duration_sec=3, aspect_ratio='16:9' WHERE id=1"
            ),
            {"path": "source/editor01.mp4"},
        )
        uow.commit()
    save_transcript(
        config.media_root,
        1,
        text="Câu gốc.",
        segments=[{"start": 1, "end": 4, "text": "Câu gốc."}],
    )

    source_page = client.get("/web/sources").text
    assert "Mở trang review" in source_page
    assert "class=\"subtitle-editor\"" not in source_page

    page = client.get("/web/review/1")
    assert page.status_code == 200
    assert "Transcript theo mốc thời gian" in page.text
    assert 'src="/web/items/1/source-video"' in page.text
    assert 'name="start"' in page.text
    assert 'name="text_line"' in page.text
    assert "Lưu & duyệt transcript" in page.text

    response = client.post(
        "/web/items/1/transcript",
        data={
            "start": [1.5],
            "end": [4.5],
            "text_line": ["Câu đã sửa."],
            "actor": "quan.nguyen",
            "decision": "save",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/web/review/1?saved=1"
    text_value, segments = load_transcript(config.media_root, 1)
    assert text_value == "Câu đã sửa."
    assert segments == [{"start": 1.5, "end": 3.0, "text": "Câu đã sửa."}]
    saved_page = client.get(response.headers["location"])
    assert 'class="toast success"' in saved_page.text


def test_nguoi_dung_chon_hai_doan_tao_hai_clip_doc_lap(client):
    _declare(client)
    _approve(
        client,
        1,
        may_translate="true",
        may_modify_audio="true",
        may_subtitle="true",
        may_republish="true",
        may_commercial_use="true",
    )
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=multi01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.application.use_cases.write_script import save_transcript
    from src.interfaces.api.deps import get_config, get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='transcript_approved', path_source=:path, "
                "duration_sec=180, aspect_ratio='16:9', external_id='multi01' WHERE id=1"
            ),
            {"path": "source/multi01.mp4"},
        )
        uow.commit()
    save_transcript(
        get_config().media_root,
        1,
        text="Hai đoạn kiểm thử.",
        segments=[{"start": 0, "end": 150, "text": "Hai đoạn kiểm thử."}],
    )

    resp = client.post(
        "/web/items/1/clips",
        data={
            "start_sec": [10, 80],
            "end_sec": [70, 140],
            "actor": "quan.nguyen",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/review/1?created=2"

    with uow:
        clips = uow.session.execute(
            text(
                "SELECT parent_item_id, clip_index, segment_start_sec, segment_end_sec, "
                "include_attribution, stage FROM items WHERE parent_item_id=1 ORDER BY clip_index"
            )
        ).all()
        jobs = uow.session.execute(
            text("SELECT task FROM jobs WHERE item_id IN (2, 3) ORDER BY item_id")
        ).scalars().all()
    assert clips == [
        (1, 1, 10.0, 70.0, False, "segment_picked"),
        (1, 2, 80.0, 140.0, False, "segment_picked"),
    ]
    assert jobs == ["write_script", "write_script"]

    # Trang nguồn chỉ giữ dòng video gốc; hai clip con gộp thành thống kê. Ba dòng
    # cho cùng một video làm người xem tưởng có ba video khác nhau.
    source_page = client.get("/web/sources?open_source=1").text
    assert source_page.count('class="item" data-item-id=') == 1
    assert "2 clip con" in source_page
    assert "2 · Đã chọn đoạn" in source_page
    assert 'class="source-detail" >' in source_page  # open_source mở sẵn nguồn #1

    status = client.get("/web/item-status").json()["items"]
    assert {row["id"]: row["parent_item_id"] for row in status} == {1: None, 2: 1, 3: 1}


def test_trang_review_gom_chon_doan_tien_trinh_va_lich_su(client):
    """Mọi thao tác của một video nằm ở một trang — trang nguồn chỉ còn danh sách.

    Người duyệt làm việc theo từng video chứ không theo từng bảng: bắt họ nhảy giữa
    hai trang cho cùng một item là chỗ dễ bỏ sót nhất.
    """
    _declare(client)
    _approve(client, 1, may_modify_audio="true", may_subtitle="true")
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=gather01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.interfaces.api.deps import get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='transcript_approved', path_source=:path, "
                "duration_sec=180, aspect_ratio='16:9' WHERE id=1"
            ),
            {"path": "source/gather01.mp4"},
        )
        uow.commit()

    page = client.get("/web/review/1").text
    assert 'action="/web/items/1/clips"' in page
    assert "data-live-progress" in page
    assert "Lịch sử hoạt động" in page
    assert "<strong>accepted</strong>" in page  # audit thật của bước nạp URL

    source_page = client.get("/web/sources").text
    assert "/web/items/1/clips" not in source_page
    assert 'href="/web/review/1"' in source_page


def test_trang_review_chia_tab_va_ve_workflow_15_buoc(client):
    """Tab nào mở sẵn phải là việc đang cần làm — không bắt người duyệt đi tìm."""
    _declare(client)
    _approve(client, 1, may_modify_audio="true", may_subtitle="true")
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=tabs01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.interfaces.api.deps import get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='transcript_approved', path_source=:path, "
                "duration_sec=400, aspect_ratio='16:9' WHERE id=1"
            ),
            {"path": "source/tabs01.mp4"},
        )
        uow.commit()

    page = client.get("/web/review/1").text
    for tab in ("transcript", "clip", "clips", "lichsu", "nguon"):
        assert f'data-tab-panel="{tab}"' in page
    # Duyệt thành phẩm không còn là tab riêng: nó là popup của từng clip con.
    assert 'data-tab-panel="duyet"' not in page
    # Sơ đồ 15 bước là tham chiếu chung: mỗi bước mang % của chính nó và KHÔNG tô
    # theo trạng thái item nào — tô theo item gốc hay clip con đều gây hiểu nhầm.
    assert page.count('class="wf-step"') == 15
    assert "45%" in page
    assert "wf-step done" not in page and "wf-step current" not in page
    assert 'data-default-tab="clip"' in page
    assert '<section class="card" data-tab-panel="clip" >' in page  # mở sẵn
    assert 'data-tab-panel="lichsu" hidden' in page

    # Badge nói tiếng Việt, không phơi mã enum trong DB.
    assert "Chọn đoạn</span>" in page
    assert ">transcript_approved<" not in page

    # Item tự chạy hết pipeline (không cắt clip) vẫn có cửa duyệt: nó là một dòng
    # thành phẩm của chính nó trong tab “Clip đã tạo”, mở ra popup có nút duyệt.
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='human_review', path_output='output/item-1/final.mp4',"
                " script_vi='Kịch bản thử.' WHERE id=1"
            )
        )
        uow.commit()
    waiting = client.get("/web/review/1").text
    assert 'data-default-tab="clips"' in waiting
    assert 'action="/web/review/1/approve"' in waiting
    assert "Kịch bản thử." in waiting
    assert "Duyệt thành phẩm" in waiting


def test_popup_clip_con_co_kich_ban_va_nut_duyet_roi_xuat_ban(client):
    """Quan hệ một video gốc → nhiều clip con: mọi quyết định về clip nằm ở trang
    video gốc, trong popup của đúng clip đó."""
    _declare(client)
    _approve(
        client,
        1,
        may_translate="true",
        may_modify_audio="true",
        may_subtitle="true",
        may_republish="true",
        may_commercial_use="true",
    )
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=popup01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.application.use_cases.write_script import save_transcript
    from src.interfaces.api.deps import get_config, get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='transcript_approved', path_source=:path, "
                "duration_sec=180, aspect_ratio='16:9' WHERE id=1"
            ),
            {"path": "source/popup01.mp4"},
        )
        uow.commit()
    save_transcript(
        get_config().media_root,
        1,
        text="Kiểm thử.",
        segments=[{"start": 0, "end": 150, "text": "Kiểm thử."}],
    )
    client.post(
        "/web/items/1/clips",
        data={"start_sec": [10], "end_sec": [70], "actor": "quan.nguyen"},
        follow_redirects=False,
    )
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='human_review', path_output='output/item-2/final.mp4',"
                " script_vi='Kịch bản của clip 1.' WHERE id=2"
            )
        )
        uow.commit()

    page = client.get("/web/review/1").text
    assert 'id="clip-2"' in page  # popup của clip con
    assert "Kịch bản của clip 1." in page
    assert 'action="/web/review/2/approve"' in page
    assert 'name="return_to" value="1"' in page  # duyệt xong ở lại trang video gốc
    assert ">Duyệt thành phẩm<" in page

    resp = client.post(
        "/web/review/2/approve",
        data={"actor": "quan.nguyen", "notes": "", "return_to": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/review/1?decided=approve#clips"

    # Đã duyệt → việc kế tiếp là xuất bản, và nút đó nằm trong cùng popup.
    approved_page = client.get("/web/review/1").text
    assert 'action="/web/review/2/publish"' in approved_page
    assert ">Xuất bản<" in approved_page

    # Lịch sử rẽ nhánh: nguồn · video gốc · từng clip, không trộn một dòng chảy.
    assert "Nguồn #1" in approved_page
    assert "#1-gốc" in approved_page and "#1-1" in approved_page


def test_doan_qua_dai_thi_bao_loi_ngay_tren_trang_review(client):
    """Đoạn ngoài biên 10–180s là lỗi nghiệp vụ hợp lệ — người dùng phải sửa được
    tại chỗ, không bị đẩy sang URL của POST rồi phải bấm back."""
    _declare(client)
    _approve(client, 1, may_modify_audio="true", may_subtitle="true")
    client.post(
        "/web/items",
        data={"url": "https://www.youtube.com/watch?v=toolong01", "actor": "quan.nguyen"},
        follow_redirects=False,
    )

    from src.interfaces.api.deps import get_uow

    uow = get_uow()
    with uow:
        uow.session.execute(
            text(
                "UPDATE items SET stage='transcript_approved', path_source=:path, "
                "duration_sec=956, aspect_ratio='16:9' WHERE id=1"
            ),
            {"path": "source/toolong01.mp4"},
        )
        uow.commit()

    resp = client.post(
        "/web/items/1/clips",
        data={"start_sec": [0], "end_sec": [372], "actor": "quan.nguyen"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/web/review/1?error=")

    page = client.get(resp.headers["location"]).text
    assert 'class="toast error"' in page
    assert "ngoài biên cho phép" in page
    assert "10–180 giây" in page  # form nói trước luật, không để người dùng đoán

    with uow:
        leftovers = uow.session.execute(
            text("SELECT count(*) FROM items WHERE parent_item_id=1")
        ).scalar_one()
    assert leftovers == 0


def test_item_khong_ton_tai_thi_404(client):
    assert client.get("/web/review/99999").status_code == 404


# ---------------- Không phục vụ file ngoài output ----------------


def test_chi_mount_thu_muc_output(client):
    """``source/`` chứa video gốc của người khác, ``work/`` chứa file trung gian —
    không có lý do gì để chúng ra được HTTP."""
    assert client.get("/media/source/a.mp4").status_code == 404
    assert client.get("/media/work/a.wav").status_code == 404
