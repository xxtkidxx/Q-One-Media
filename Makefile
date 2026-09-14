# Q One Media — lệnh vận hành
# Windows: chạy trong Git Bash, hoặc dùng trực tiếp lệnh docker compose bên dưới.

DC      := docker compose
# Hai file compose độc lập, không override lồng nhau.
DEV     := -f docker/docker-compose.dev.yml  --env-file .env.dev
PROD    := -f docker/docker-compose.prod.yml --env-file .env.prod

.DEFAULT_GOAL := help
.PHONY: help dev-up dev-down dev-logs dev-build prod-up prod-down prod-logs prod-build \
        migrate migrate-prod migrate-rev migrate-history \
        test test-int test-gpu test-all lint \
        fonts models speech-rate measure-load corpus glossary-load \
        shell psql smoke status clean-work

help:
	@echo "DEV : dev-up dev-down dev-logs dev-build"
	@echo "PROD: prod-up prod-down prod-logs prod-build"
	@echo "DB  : migrate migrate-prod migrate-rev migrate-history"
	@echo "TEST: test test-int test-gpu test-all lint"
	@echo "MODEL: models fonts speech-rate measure-load"
	@echo "DATA: corpus glossary-load"
	@echo "KHAC: smoke status shell psql clean-work"

# ---------------- DEV ----------------
dev-up:
	$(DC) $(DEV) up -d
	@echo "API  -> http://localhost:$${API_PORT:-8008}/docs"
	@echo "n8n  -> http://localhost:$${N8N_PORT:-5678}"

dev-down:
	$(DC) $(DEV) down

dev-build:
	$(DC) $(DEV) build

# Luôn giới hạn log — đừng dump vô hạn
dev-logs:
	$(DC) $(DEV) logs --tail 50 --since 5m -f

# ---------------- PROD ----------------
prod-up:
	$(DC) $(PROD) up -d

prod-down:
	$(DC) $(PROD) down

prod-build:
	$(DC) $(PROD) build

prod-logs:
	$(DC) $(PROD) logs --tail 50 --since 5m -f

# ---------------- Test ----------------
# Mặc định: bỏ qua test cần GPU và test gọi API ngoài.
test:
	$(DC) $(DEV) run --rm --no-deps api pytest tests/unit -x -q -m "not gpu and not external"

# Test tích hợp: cần postgres chạy. Mapper là chỗ duy nhất mất dữ liệu im lặng được.
test-int:
	$(DC) $(DEV) run --rm api pytest tests/integration -q -m integration

# Test cần GPU và model thật. Chạy trong worker, không phải api.
test-gpu:
	$(DC) $(DEV) run --rm worker pytest tests/integration/test_gpu_models.py -q -m gpu -s

# Chỉ chạy khi chuẩn bị merge hoặc được yêu cầu
test-all:
	$(DC) $(DEV) run --rm api pytest -q -m "not gpu and not external"

lint:
	$(DC) $(DEV) run --rm --no-deps api ruff check src tests scripts

# ---------------- Migration ----------------
# Alembic là nguồn duy nhất của schema. Baseline viết idempotent nên chạy được
# cả trên DB trống và DB đã có bảng từ bản 01-schema.sql cũ.
migrate:
	$(DC) $(DEV) run --rm api alembic upgrade head

migrate-prod:
	$(DC) $(PROD) run --rm api alembic upgrade head

# make migrate-rev m="them cot x"
migrate-rev:
	$(DC) $(DEV) run --rm api alembic revision --autogenerate -m "$(m)"

migrate-history:
	$(DC) $(DEV) run --rm api alembic history --indicate-current

# ---------------- Tiện ích ----------------
shell:
	$(DC) $(DEV) exec worker bash

psql:
	$(DC) $(DEV) exec postgres psql -U $${POSTGRES_USER:-qone} -d $${POSTGRES_DB:-qone}

# Chạy toàn chuỗi một lần, không cần GPU, ra một video thật trong trang duyệt.
# Bước tải/Demucs/WhisperX/LLM được thay bằng dữ liệu mẫu — script nói rõ cái nào.
# Chay trong worker chu khong phai api: worker co GPU nen Demucs va buoc giong
# chay THAT. Script tu nhan dien — khong co GPU thi no bao ro va dung du lieu mau.
smoke:
	$(DC) $(DEV) run --rm worker python scripts/smoke_pipeline.py

# Corpus nmi.vn → bảng thuật ngữ (G1.3). nmi.vn là site của chính NMI, có mặt ở
# đây vì taxonomy và vì cách NMI đã gọi thuật ngữ bằng tiếng Việt — không phải
# làm nguồn nội dung video.
corpus:
	python scripts/nmi_corpus.py fetch
	python scripts/nmi_corpus.py terms

glossary-load:
	$(DC) $(DEV) run --rm api python scripts/load_glossary.py

# Đo tốc độ đọc thật của giọng đang dùng → TTS_SYLLABLES_PER_SEC (G0.7).
# Đo được 3,52 âm tiết/giây với edge-tts; các nguồn trên mạng ghi 5,28–6.
speech-rate:
	$(DC) $(DEV) run --rm api python scripts/measure_speech_rate.py

# Đo chi phí nạp lại model GPU — trả lời "giữ model trên card hay nhả sau mỗi việc".
# Card 8 GB không đủ cho Whisper large-v3 và VoxCPM2 cùng nằm trên đó, nên câu hỏi
# này là bắt buộc phải trả lời bằng số đo, không phải bằng phỏng đoán.
measure-load:
	$(DC) $(DEV) run --rm worker python scripts/measure_model_load.py

# Tải font tiếng Việt vào docker/worker/fonts/ — chạy TRƯỚC khi build worker.
# Font thiếu dải U+1Exx thì libass âm thầm thay font khác và không báo lỗi.
fonts:
	python scripts/fetch_fonts.py

# Tải model vào data/models (dùng chung dev/prod, ~10 GB, chỉ cần một lần)
models:
	$(DC) $(DEV) run --rm worker python scripts/fetch_models.py

status:
	@$(DC) $(DEV) ps
	@echo "--- dung luong data/ ---"
	@du -sh data/* 2>/dev/null || true

# Xoá file trung gian — an toàn, sinh lại được. KHÔNG xoá source/output/postgres.
clean-work:
	rm -rf data/dev/media/work/* data/prod/media/work/*
	@echo "Da xoa media/work. source, output, postgres, n8n KHONG bi anh huong."
