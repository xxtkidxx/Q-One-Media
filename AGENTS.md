# AGENTS.md — Hướng dẫn cho AI agent (Codex · Claude Code)

Đọc file này trước khi làm bất cứ việc gì. Nó ngắn có chủ ý — đọc hết rồi làm.

## Dự án là gì

**Q One Media** — pipeline tự động hoá short video tiếng Việt cho NMI Technologies (phần mềm chất lượng & điều hành sản xuất, thương hiệu Q One).

- **Giai đoạn 1:** video nước ngoài đã khai báo → chọn lọc → biên tập → **lồng tiếng Việt + phụ đề** → publish YouTube/Facebook.
- **Giai đoạn 2 (Studio):** người dùng nhập đề bài → LLM viết kịch bản tiếng Việt → giọng + hình (ảnh/video đưa vào, biểu đồ từ số liệu, AI cho bối cảnh) → render → publish.

**Đặc tả duy nhất:** `docs/phuong-an-cuoi-cung.md`. **Trạng thái và việc cần làm:** `PLAN.md`.

---

## Quy tắc tiết kiệm token (bắt buộc)

1. **Đọc `PLAN.md` trước, không đọc `docs/phuong-an-cuoi-cung.md` toàn bộ.** Đặc tả dài ~30 KB. Chỉ đọc **phần liên quan** tới task (nó chia theo Phần A–H, mục F2.x là chi tiết kỹ thuật). Dùng `grep -n "^## \|^### "` để lấy mục lục rồi `sed -n 'X,Yp'` đọc đúng đoạn.
2. **Không đọc lại file mình vừa sửa** để "kiểm tra". Edit/Write báo lỗi nếu thất bại.
3. **Không `cat` file > 300 dòng.** Dùng `grep -n`, `sed -n 'X,Yp'`, hoặc `head`/`tail`.
4. **Không tự khảo sát lại web** những gì đã có trong đặc tả (star, license, giá, giới hạn API). Chúng đã được xác minh ngày 13/09/2026 và ghi rõ mức tin cậy.
5. **Không dump `docker compose logs` không giới hạn.** Luôn `--tail 50` và `--since 5m`.
6. **Một task một lần.** Xong, cập nhật `PLAN.md`, dừng. Không làm thêm việc chưa được yêu cầu.
7. **Không tạo tài liệu mới** trừ khi được yêu cầu. Cập nhật `PLAN.md`, đừng viết report song song.

## Không mở subagent

**Không dùng subagent / Task / Agent tool** trừ khi người dùng yêu cầu đích danh. Mỗi subagent khởi động lạnh và phải đọc lại ngữ cảnh — đó là đường đắt nhất.

Task "nhiều bước", "kỹ lưỡng", "nhiều góc độ" **không** phải yêu cầu mở subagent. Làm trực tiếp.

## Kỷ luật test

**Test đúng thứ vừa sửa, không quét cả bộ.**

- Sau khi sửa một module: chạy **đúng file test của module đó** — `pytest tests/unit/test_<module>.py -x -q`.
- Chỉ chạy toàn bộ `pytest` khi chuẩn bị merge hoặc người dùng yêu cầu.
- `-x` (dừng ở lỗi đầu) và `-q` là mặc định. Không dùng `-v` trừ khi đang debug một test cụ thể.
- **Không viết test cho code chưa có.** Không viết test "cho đủ coverage".
- **Không sửa test để nó pass.** Nếu test đúng mà code sai thì sửa code; nếu test sai thì nói ra trước khi sửa.
- Test cần GPU hoặc model thật: đánh dấu `@pytest.mark.gpu` và **không** chạy mặc định.
- Test gọi API bên ngoài (YouTube, Facebook, LLM): đánh dấu `@pytest.mark.external`, mặc định bỏ qua, dùng fixture ghi lại (recorded) thay vì gọi thật.

Khi một test đỏ: đọc **thông báo lỗi thật**, sửa một nguyên nhân, chạy lại **đúng test đó**. Không đoán bừa và không sửa nhiều thứ cùng lúc.

## Báo cáo kết quả

- Nói thẳng: đã làm gì, test nào chạy, kết quả thật.
- Test đỏ thì nói đỏ kèm output. **Không** báo "xong" khi chưa xác minh.
- Bỏ qua bước nào thì nói rõ bỏ qua.
- Không viết lại tóm tắt dài những gì vừa làm — một đoạn ngắn là đủ.

---

## Quy tắc miền — không được vi phạm

Đây là quy tắc nghiệp vụ, không phải gợi ý kỹ thuật:

1. **License gate không được bỏ qua.** Pipeline **từ chối tải video** nếu nguồn cha không có `sources.status = 'approved'`. Không thêm cờ `--skip-license`, không thêm đường tắt "cho dev". Nếu cần fixture để test, dùng nguồn giả đã `approved` trong DB test.
2. **`sources.scope` phải gồm quyền sửa audio** trước khi lồng tiếng. Quyền "được dùng lại" **không** suy ra quyền sửa audio.
3. **Không viết code né phát hiện bản quyền** — crop/lật/đổi tốc độ/chèn nhiễu để lách Content ID. Nếu một task ngụ ý việc này, dừng và hỏi.
4. **Giữ nguyên watermark và credit gốc.** Không viết hàm xoá watermark.
5. **Gate duyệt của người là bắt buộc** ở Giai đoạn 1. Không tự động publish bỏ qua bước duyệt.
6. **Nguồn có watermark dán cứng: không publish lên TikTok.**
7. **Xác minh chủ sở hữu trước khi tải.** Duyệt **một** kênh không mở quyền cho cả nền tảng. Khớp theo host chỉ cho ra ứng viên; phải gọi `Source.assert_owns()` với id chủ kênh lấy từ metadata. Nguồn dạng bao mà chưa khai `external_owner_id` thì từ chối — thiếu cách xác minh là lý do hợp lệ để dừng, không phải lý do để cho qua.

---

## Môi trường

Mọi thứ chạy trong Docker. **Không cài Python/ffmpeg/model lên máy host.**

```bash
# DEV — code mount vào container, hot reload, port mở
make dev-up            # hoặc: docker compose -f docker/docker-compose.dev.yml --env-file .env.dev up -d
make dev-logs          # tail 50
make dev-down

# PROD — code nằm trong image, restart tự động
make prod-up
make prod-logs
make prod-down

make test              # unit test trong container dev, bỏ qua gpu/external/integration
make test-int          # test tích hợp trên Postgres thật (cần container chạy)
                       # Chạy trên DB riêng `<db>_test`, KHÔNG chạm DB dev
make shell             # bash trong worker container
```

**Chỉ có hai file compose**, mỗi file chạy độc lập — `docker-compose.dev.yml` và
`docker-compose.prod.yml`. Không có file base, không override lồng nhau.

**Dữ liệu runtime nằm trong `./data/`** — bind mount, không dùng docker volume. Xoá container/image không mất gì; xoá `./data/` là mất dữ liệu.

| Đường dẫn | Nội dung | Xoá được? |
|---|---|---|
| `data/{dev,prod}/postgres/` | DB registry | **Không** — dữ liệu gốc |
| `data/{dev,prod}/media/source/` | Video gốc đã tải | Không nên — cần để làm lại và chứng minh tuân thủ |
| `data/{dev,prod}/media/work/` | File trung gian | Được — sinh lại được |
| `data/{dev,prod}/media/output/` | Video thành phẩm | **Không** |
| `data/{dev,prod}/n8n/` | Workflow n8n | **Không** |
| `data/models/` | Cache model HF (~10 GB) | Được nhưng tải lại rất lâu. **Dùng chung dev/prod** vì model là artifact bất biến, không phải state |

---

## Bố cục code — Clean Architecture, bốn tầng

```
src/domain/          Thuần Python, CHỈ stdlib. Entity, value object, port (Protocol).
  sourcing/            Source — kiểm soát pháp lý cốt lõi. clearance.py = license gate
  production/          Item — máy trạng thái 17 bước của pipeline
  publishing/          Publication + policy.py (quyết định CÓ đăng hay không)
  scheduling/          Job — hàng đợi
  errors.py            Lỗi có phân loại; nhóm LicenseViolation tách riêng
src/application/     Use case điều phối domain qua port. Không biết framework.
  ports.py             UnitOfWork, Clock, AuditLog, VideoDownloader, SpeechSynthesizer,
                       VideoPublisher, SegmentAdvisor, ScriptWriter
  use_cases/           manage_sources, submit_url, download_item, review_item, publish_item
src/infrastructure/  Adapter. Biết SQLAlchemy, ffmpeg, HTTP, yt-dlp.
  db/                  orm.py (dòng dữ liệu) · mappers.py · repositories.py · uow.py
  ingest/              yt-dlp: YtDlpProbe (metadata) + YtDlpDownloader
  tts/ publish/ media/ chưa hiện thực — xem PLAN.md G2.9, G3.3, G4.3
src/interfaces/      Biên ngoài. Mỏng có chủ ý.
  api/                 FastAPI: main, deps, schemas, routers/
  worker/              Vòng lặp lấy việc từ hàng đợi
src/shared/          Cross-cutting: config.py, paths.py, logging.py

tests/unit/          Không network, không GPU, không DB. Chạy < 1s
tests/integration/   Cần container. Đánh dấu @pytest.mark.integration
tests/fakes.py       Hiện thực in-memory của mọi port
docker/              Dockerfile + compose + schema SQL
```

### Quy tắc phụ thuộc — quan trọng nhất

**Mũi tên chỉ vào trong.** `interfaces` → `application` → `domain`; `infrastructure` → `domain`.
Ngược lại là sai:

- `src/domain/` **không** import `sqlalchemy`, `fastapi`, `yt_dlp`, `httpx`, hay `src.shared.config`.
  Nếu một file trong `domain/` cần import ngược ra ngoài thì thiết kế sai, không phải thiếu tiện ích.
- `src/application/` chỉ import `domain` và port của chính nó. Không import `infrastructure`.
- Quy tắc nghiệp vụ nằm ở `domain/`. Thấy một câu `if` về license trong router hay worker
  thì đó là chỗ cần sửa.

### Vì sao license gate là kiểu dữ liệu

`domain/sourcing/clearance.py` định nghĩa `DownloadClearance` / `DubbingClearance` /
`PublishClearance`. Chỉ `Source.clear_for_*()` cấp được, và hàm tải/lồng tiếng/đăng
**bắt buộc nhận** một clearance. Vì vậy không tồn tại đường gọi nào đi vòng qua gate —
trình kiểm tra kiểu báo lỗi ngay, không cần ai nhớ quy tắc.

Hệ quả khi viết code mới: **đừng** thêm tham số `skip_license`, **đừng** đọc `sources.status`
rồi tự quyết định ở tầng ngoài. Xin clearance, và để lỗi nổ ra nếu không được cấp.

Riêng quyền sở hữu: `Source.claims()` chỉ lọc **ứng viên** (cùng host). Xác minh thật là
`Source.assert_owns(id_chủ_kênh_từ_metadata)` — duyệt một kênh YouTube không mở quyền cho
cả youtube.com.

### Quy ước

- Python 3.11, `ruff` format + lint, type hint ở biên public.
- Đường dẫn: **luôn** qua `src/shared/paths.py`. Đường dẫn lưu trong DB là **tương đối** so
  với `MEDIA_ROOT` — để di chuyển cây `data/` sang máy khác không phải sửa DB.
- Config qua biến môi trường, đọc một lần trong `src/shared/config.py`. Không `os.getenv` rải rác.
  **Không thêm cờ cấu hình bật/tắt license gate hay gate duyệt** — đó là bất biến, không phải cấu hình.
- Không bắt `Exception` trần. Lỗi phân loại bằng thuộc tính `retryable`: mạng/rate limit thì có,
  license/input sai thì không. Worker đọc đúng thuộc tính đó để quyết định xếp lại hay bỏ.
- Thời gian: luôn UTC có timezone, lấy qua port `Clock`. So sánh `expires_at` với `datetime`
  naive sẽ nổ `TypeError` ngay trong license gate.
- Log JSON ra stdout; Docker gom vào `data/{env}/logs/`.
- **Không có thư mục `vendor/`.** Code tham khảo từ dự án mở được **viết lại thành module của chính dự án**, đặt trong `src/` và sửa tự do như mọi code khác. Đổi lại: ghi xuất xứ trong docstring của module, và khai vào `THIRD_PARTY_NOTICES.md` — đó là nghĩa vụ license, không phải thủ tục.

### Mượn code từ dự án mở

Không sao chép nguyên trạng và không giữ bản sao "không được đụng vào". Đọc code
upstream, hiểu thuật toán, rồi **viết lại thành module của dự án** trong `src/` — đặt
tên theo nghiệp vụ ở đây, ném lỗi theo phân loại retry của hàng đợi, viết chú thích
bằng tiếng Việt như phần còn lại.

Hai việc bắt buộc khi làm vậy:

1. **Docstring của module** ghi repo, commit và license gốc.
2. **`THIRD_PARTY_NOTICES.md`** ghi đã lấy gì, đưa vào đâu, và **sửa những gì**. Với
   Apache-2.0 thì nêu rõ thay đổi là nghĩa vụ license, không phải thủ tục nội bộ.

Đã làm theo cách này với **Easel** (Apache-2.0) cho đổi khung hình và trộn audio.
Riêng **VideoLingo** thì không lấy gì: bước tải của họ (`core/_1_ytdlp.py`) chạy
`pip install --upgrade` mỗi lần gọi và ghi vào thư mục toàn cục — xem D19 và D23
trong `PLAN.md`.

---

## Khi bị chặn

- **Thiếu quyết định của người dùng:** xem mục "Còn cần quyết" trong `PLAN.md`. Làm hết phần không phụ thuộc câu trả lời đó, rồi hỏi một câu gọn.
- **Cần GPU mà không có:** đánh dấu test `@pytest.mark.gpu`, viết code, để người dùng chạy.
- **Đặc tả không nói:** chọn phương án đơn giản nhất, ghi giả định vào `PLAN.md` mục Decisions, nói ra trong báo cáo. Đừng dừng lại vì chuyện nhỏ.

## Định nghĩa "xong"

Một task xong khi: code chạy · test của module đó xanh · `PLAN.md` đã cập nhật · không để lại file rác (`*.whl`, `*.log`, output tạm) trong repo.
