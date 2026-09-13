# AGENTS.md — Hướng dẫn cho AI agent (Codex · Claude Code)

Đọc file này trước khi làm bất cứ việc gì. Nó ngắn có chủ ý — đọc hết rồi làm.

## Dự án là gì

**Q One Media** — pipeline tự động hoá short video tiếng Việt cho NMI Technologies (phần mềm chất lượng & điều hành sản xuất, thương hiệu Q One).

- **Giai đoạn 1:** video nước ngoài đã khai báo → chọn lọc → biên tập → **lồng tiếng Việt + phụ đề** → publish YouTube/Facebook.
- **Giai đoạn 2:** bài viết nước ngoài đã khai báo → viết kịch bản gốc → ảnh + giọng → render → publish.

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

---

## Môi trường

Mọi thứ chạy trong Docker. **Không cài Python/ffmpeg/model lên máy host.**

```bash
# DEV — code mount vào container, hot reload, port mở
make dev-up            # hoặc: docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml --env-file .env.dev up -d
make dev-logs          # tail 50
make dev-down

# PROD — code nằm trong image, restart tự động
make prod-up
make prod-logs
make prod-down

make test              # pytest trong container dev, bỏ qua gpu/external
make shell             # bash trong worker container
```

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

## Bố cục code

```
src/api/        FastAPI: hộp thư URL, license gate, job queue, publish dispatch
src/ingest/     yt-dlp wrapper, nhánh riêng cho Douyin (tải đồng bộ)
src/tts/        Adapter VoxCPM2; fallback FPT.AI qua cùng interface
src/publish/    YouTube Data API, Facebook Graph API — sau interface publish() duy nhất
src/db/         Schema + migration (sources, items, jobs, licenses)
src/shared/     Config, logging, path helper
vendor/         Code bên thứ ba đã vendor — xem vendor/README.md
tests/unit/     Không cần network, không cần GPU
tests/integration/  Cần container chạy
docker/         Dockerfile + compose
scripts/        Script vận hành một lần (setup, fetch model, migrate)
```

### Quy ước

- Python 3.11, `ruff` format + lint, type hint ở biên public.
- Đường dẫn: **luôn** qua `src/shared/paths.py`, không hardcode `./data/...`.
- Config qua biến môi trường, đọc một lần trong `src/shared/config.py`. Không `os.getenv` rải rác.
- Không bắt `Exception` trần. Lỗi có phân loại: retry được (mạng, rate limit) vs không (license, input sai).
- Log JSON ra stdout; Docker gom vào `data/{env}/logs/`.
- **Không sửa file trong `vendor/`.** Cần đổi hành vi thì bọc thêm lớp adapter trong `src/`. Lý do: còn so được với upstream.

### Về `vendor/`

Code lấy từ VideoLingo (Apache-2.0) và Easel (Apache-2.0). Mỗi thư mục con phải có `ORIGIN.md` ghi: repo, commit SHA, ngày lấy, file nào, đã sửa gì. Đây vừa là nghĩa vụ license vừa để đối chiếu upstream về sau.

---

## Khi bị chặn

- **Thiếu quyết định của người dùng:** xem mục "Còn cần quyết" trong `PLAN.md`. Làm hết phần không phụ thuộc câu trả lời đó, rồi hỏi một câu gọn.
- **Cần GPU mà không có:** đánh dấu test `@pytest.mark.gpu`, viết code, để người dùng chạy.
- **Đặc tả không nói:** chọn phương án đơn giản nhất, ghi giả định vào `PLAN.md` mục Decisions, nói ra trong báo cáo. Đừng dừng lại vì chuyện nhỏ.

## Định nghĩa "xong"

Một task xong khi: code chạy · test của module đó xanh · `PLAN.md` đã cập nhật · không để lại file rác (`*.whl`, `*.log`, output tạm) trong repo.
