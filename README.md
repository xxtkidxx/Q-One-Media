# Q One Media

Pipeline tự động hoá short video tiếng Việt cho **NMI Technologies Việt Nam** — phần mềm chất lượng và điều hành sản xuất, thương hiệu **Q One**.

- **Giai đoạn 1:** video nước ngoài đã khai báo → chọn lọc → biên tập → **lồng tiếng Việt + phụ đề** → publish YouTube/Facebook
- **Giai đoạn 2:** bài viết nước ngoài đã khai báo → viết kịch bản gốc → ảnh + giọng → render → publish

**Trạng thái: G0 — khung dự án đã dựng, chưa có code chạy được.**

## Bắt đầu từ đâu

| Bạn là | Đọc file |
|---|---|
| Người theo dõi tiến độ | **[PLAN.md](PLAN.md)** — hiện trạng, bảng việc, quyết định đã chốt, câu hỏi còn chờ |
| AI agent (Codex / Claude Code) | **[AGENTS.md](AGENTS.md)** — quy tắc token, không subagent, kỷ luật test |
| Người cần đặc tả kỹ thuật | **[docs/phuong-an-cuoi-cung.md](docs/phuong-an-cuoi-cung.md)** — bản chốt duy nhất |

## Chạy

Mọi thứ trong Docker. **Không cài Python/ffmpeg/model lên máy host.**

```bash
cp .env.dev.example .env.dev      # rồi điền: mật khẩu postgres, N8N_ENCRYPTION_KEY, ANTHROPIC_API_KEY
make dev-up                       # API :8000 · n8n :5678
make models                       # tải model vào data/models (~10 GB, chỉ một lần)
make test                         # pytest, bỏ qua test cần GPU và API ngoài
make dev-logs                     # tail 50, since 5m
make dev-down
```

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

```
AGENTS.md · CLAUDE.md     hướng dẫn agent (CLAUDE.md chỉ là con trỏ)
PLAN.md                   kế hoạch + hiện trạng
docs/                     đặc tả duy nhất
docker/                   Dockerfile + compose (base/dev/prod) + schema SQL
src/                      code của mình: api, ingest, tts, publish, db, shared
vendor/                   code bên thứ ba đã vendor, kèm ORIGIN.md
tests/                    unit (không network/GPU) · integration
research/nmi-scan/        corpus song ngữ nmi.vn → rút glossary thuật ngữ (đầu vào thật, không phải tài liệu)
data/                     runtime, gitignored
```

## Stack

| Khâu | Chọn | Star | License |
|---|---|---:|---|
| Xương sống pipeline video | **VideoLingo** — đã có yt-dlp + Demucs + WhisperX | 18.433 | Apache-2.0 |
| Giọng tiếng Việt | **VoxCPM2** — có `vi`, voice cloning, chạy on-prem | 37.028 | Apache-2.0 |
| Reframe 9:16 | **Easel `reframe.py`** chế độ `blur` | 1.002 | Apache-2.0 |
| Trộn audio | **Easel `audio_mix.py`** + ffmpeg | 1.002 | Apache-2.0 |
| Publish, license registry, hộp thư URL | Tự viết | — | — |
| Điều phối | n8n self-host | — | — |

**Không có GPL/AGPL nào trong đường sản xuất** — NMI là doanh nghiệp thương mại.

## Quy tắc nghiệp vụ không được vi phạm

1. **License gate không bỏ qua** — pipeline từ chối tải nếu nguồn chưa `approved`. Không thêm cờ bỏ qua.
2. **`may_modify_audio` phải TRUE trước khi lồng tiếng** — quyền "dùng lại" không suy ra quyền sửa audio.
3. **Không viết code né phát hiện bản quyền.** Giữ nguyên watermark và credit gốc.
4. **Gate duyệt của người là bắt buộc** ở Giai đoạn 1.
5. **Nguồn có watermark dán cứng: không publish lên TikTok.**

Chi tiết và căn cứ: `docs/phuong-an-cuoi-cung.md` mục B, D.1, F2.
