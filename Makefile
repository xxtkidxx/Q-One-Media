# Q One Media — lệnh vận hành
# Windows: chạy trong Git Bash, hoặc dùng trực tiếp lệnh docker compose bên dưới.

DC      := docker compose
BASE    := -f docker/docker-compose.yml
DEV     := $(BASE) -f docker/docker-compose.dev.yml --env-file .env.dev
PROD    := $(BASE) -f docker/docker-compose.prod.yml --env-file .env.prod

.DEFAULT_GOAL := help
.PHONY: help dev-up dev-down dev-logs dev-build prod-up prod-down prod-logs prod-build \
        test test-int test-all lint shell psql fonts models speech-rate status clean-work \n        migrate migrate-prod migrate-rev migrate-history

help:
	@echo "DEV : dev-up dev-down dev-logs dev-build"
	@echo "PROD: prod-up prod-down prod-logs prod-build"
	@echo "DB  : migrate migrate-prod migrate-rev migrate-history"
	@echo "KHAC: test test-int test-all lint fonts speech-rate shell psql fonts models speech-rate status clean-work \n        migrate migrate-prod migrate-rev migrate-history"

# ---------------- DEV ----------------
dev-up:
	$(DC) $(DEV) up -d
	@echo "API  -> http://localhost:$${API_PORT:-8000}/docs"
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

# Đo tốc độ đọc thật của giọng đang dùng → TTS_SYLLABLES_PER_SEC (G0.7).
# Đo được 3,52 âm tiết/giây với edge-tts; các nguồn trên mạng ghi 5,28–6.
speech-rate:
	$(DC) $(DEV) run --rm api python scripts/measure_speech_rate.py

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
