# Q One Media

Pipeline tự động hoá short video tiếng Việt cho **NMI Technologies Việt Nam** — phần mềm chất lượng và điều hành sản xuất, thương hiệu **Q One**.

- **Giai đoạn 1:** video nước ngoài đã khai báo → chọn lọc → biên tập → **lồng tiếng Việt + phụ đề** → publish YouTube/Facebook
- **Giai đoạn 2:** bài viết nước ngoài đã khai báo → viết kịch bản gốc → ảnh + giọng → render → publish

**Trạng thái:** lõi Giai đoạn 1 đã có code và test — license gate, hộp thư URL, hàng đợi việc,
pipeline media, mặt tiền web nội bộ, adapter publish. Các bước cần GPU hoặc credential nền tảng
(WhisperX, VoxCPM2, YouTube, Facebook) **chưa chạy thật**. Chi tiết: [PLAN.md](PLAN.md).

## Bắt đầu từ đâu

| Bạn là | Đọc file |
|---|---|
| Người theo dõi tiến độ | **[PLAN.md](PLAN.md)** — hiện trạng, bảng việc, quyết định đã chốt, câu hỏi còn chờ |
| AI agent (Codex / Claude Code) | **[AGENTS.md](AGENTS.md)** — quy tắc token, không subagent, kỷ luật test |
| Người cần đặc tả kỹ thuật | **[docs/phuong-an-cuoi-cung.md](docs/phuong-an-cuoi-cung.md)** — bản chốt duy nhất |

## Chạy

Mọi thứ trong Docker. **Không cài Python/ffmpeg/model lên máy host.**

```bash
cp .env.dev.example .env.dev      # điền: mật khẩu postgres, N8N_ENCRYPTION_KEY, ANTHROPIC_API_KEY
make dev-up                       # API :8000 · n8n :5678
make migrate                      # alembic upgrade head — BẮT BUỘC lần đầu
make models                       # tải model vào data/models (~10 GB, chỉ một lần)

make fonts                        # tải font tiếng Việt (trước khi build worker)
make smoke                        # chạy toàn chuỗi ra một video thật, KHÔNG cần GPU
make speech-rate                  # đo tốc độ đọc → TTS_SYLLABLES_PER_SEC
make corpus && make glossary-load  # rút thuật ngữ từ nmi.vn vào bảng glossary

make test                         # unit test, < 1s, không cần DB/GPU/token
make test-int                     # integration test trên Postgres + ffmpeg thật
make lint                         # ruff
make dev-logs                     # tail 50, since 5m
make dev-down
```

Mở trình duyệt vào **http://localhost:8000/web** — bảng điều khiển, khai báo/duyệt nguồn,
soát transcript, duyệt video. API docs ở `/docs`.

Production tách hoàn toàn — dữ liệu riêng, port riêng, chạy song song được với dev:

```bash
cp .env.prod.example .env.prod
make prod-up                      # API :8001 · n8n :5679, chỉ bind 127.0.0.1
```

| | Dev | Prod |
|---|---|---|
| Code | Mount từ host, hot reload | Nằm trong image |
| Dữ liệu | `data/dev/` | `data/prod/` |
| Port | Mở ra localhost | Chỉ `127.0.0.1` |
| Log | DEBUG | INFO, xoay vòng 20 MB × 5 |
| n8n | Không auth | Basic auth |

## Dữ liệu runtime

**Nằm trong `./data/` bằng bind mount, không dùng docker volume** — xoá container hay image không mất gì.

```
data/dev/  data/prod/       tách hoàn toàn
  postgres/                 DB registry           ← KHÔNG xoá
  media/source/             video gốc đã tải      ← không nên xoá (cần để làm lại và chứng minh tuân thủ)
  media/work/               file trung gian       ← xoá được: make clean-work
  media/output/             video thành phẩm      ← KHÔNG xoá
  n8n/                      workflow              ← KHÔNG xoá
  logs/
data/models/                cache model ~10 GB    ← dùng chung dev/prod (artifact bất biến, không phải state)
```

## Bố cục

Clean Architecture — mũi tên phụ thuộc luôn chỉ vào trong. Chi tiết và quy tắc: [AGENTS.md](AGENTS.md).

```
AGENTS.md · CLAUDE.md     hướng dẫn agent (CLAUDE.md chỉ là con trỏ)
PLAN.md                   kế hoạch + hiện trạng
docs/                     đặc tả duy nhất
docker/                   Dockerfile + compose (base/dev/prod) + schema SQL
src/domain/               nghiệp vụ thuần, chỉ stdlib — license gate sống ở đây
src/application/          use case + port
src/infrastructure/       adapter: Postgres, yt-dlp, (tts/publish/media: chưa có)
src/interfaces/           FastAPI + worker
src/shared/               config, paths, logging
vendor/                   code bên thứ ba đã vendor, kèm ORIGIN.md
tests/unit/               không network/GPU/DB, chạy < 1s · tests/integration/ cần container
research/nmi-scan/        corpus song ngữ nmi.vn → rút glossary thuật ngữ
data/                     runtime, gitignored
```

**License gate là kiểu dữ liệu, không phải câu `if`.** Hàm tải video bắt buộc nhận một
`DownloadClearance`, và vật đó chỉ `Source` cấp được sau khi kiểm trạng thái, hạn license và
phạm vi quyền. Không có clearance thì không gọi được hàm. Xem `src/domain/sourcing/clearance.py`.

## Stack

| Khâu | Chọn | Star | License |
|---|---|---:|---|
| Xương sống pipeline video | **VideoLingo** — đã có yt-dlp + Demucs + WhisperX | 18.433 | Apache-2.0 |
| Giọng tiếng Việt | **VoxCPM2** — có `vi`, voice cloning, chạy on-prem | 37.028 | Apache-2.0 |
| Reframe 9:16 | **Easel `reframe.py`** chế độ `blur` | 1.002 | Apache-2.0 |
| Trộn audio | **Easel `audio_mix.py`** + ffmpeg | 1.002 | Apache-2.0 |
| Publish, license registry, hộp thư URL | Tự viết | — | — |
| Mặt tiền web nội bộ | Jinja2 server-rendered, **không JavaScript** | — | — |
| Điều phối bước | Worker + hàng đợi Postgres (`FOR UPDATE SKIP LOCKED`) | — | — |
| Thông báo, trigger định kỳ | n8n self-host | — | — |

**Không có GPL/AGPL nào trong đường sản xuất** — NMI là doanh nghiệp thương mại.

## Quy tắc nghiệp vụ không được vi phạm

1. **License gate không bỏ qua** — pipeline từ chối tải nếu nguồn chưa `approved`. Không thêm cờ bỏ qua.
2. **`may_modify_audio` phải TRUE trước khi lồng tiếng** — quyền "dùng lại" không suy ra quyền sửa audio.
3. **Không viết code né phát hiện bản quyền.** Giữ nguyên watermark và credit gốc.
4. **Gate duyệt của người là bắt buộc** ở Giai đoạn 1.
5. **Nguồn có watermark dán cứng: không publish lên TikTok.**

6. **Xác minh chủ sở hữu trước khi tải** — duyệt *một* kênh không mở quyền cho *cả* nền tảng.
   Khớp theo host chỉ cho ra ứng viên; `Source.assert_owns()` với id chủ kênh từ metadata mới
   là xác minh.

Năm quy tắc đầu được thi hành ở tầng domain, không phải bằng câu `if` ở tầng ngoài — xem
`src/domain/sourcing/clearance.py`. Chi tiết và căn cứ: `docs/phuong-an-cuoi-cung.md` mục B, D.1, F2.

## Test

```
make test        191 unit test, < 1s. Không DB, không GPU, không token
make test-int     43 integration test. Postgres thật + ffmpeg/libass thật
```

Tầng domain thuần stdlib nên toàn bộ quy tắc license và gate duyệt test được trong vài chục
milligiây. Test tích hợp phủ ba chỗ dễ sai im lặng: mapper DB (mất dữ liệu mà unit test không
thấy), glyph tiếng Việt trong libass (render xong nhưng sai font), và form duyệt license (checkbox
không tick phải nghĩa là *không* cấp quyền).
