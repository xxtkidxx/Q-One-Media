-- Q One Media — schema khởi tạo
-- Chạy tự động khi postgres init lần đầu (thư mục data trống).
-- Đã có dữ liệu thì file này KHÔNG chạy lại — dùng alembic cho thay đổi sau.

CREATE SCHEMA IF NOT EXISTS n8n;   -- n8n dùng schema riêng, không lẫn với app

-- ============================================================
-- sources — cấp NGUỒN, do người khai báo một lần.
-- Đây là kiểm soát pháp lý cốt lõi của cả hệ thống.
-- ============================================================
CREATE TYPE source_platform AS ENUM
  ('youtube','douyin','bilibili','tiktok','facebook','vimeo','web');

CREATE TYPE source_kind AS ENUM
  ('channel','playlist','creator-page','website','rss','single-url');

CREATE TYPE content_type AS ENUM ('video','article');

CREATE TYPE license_type AS ENUM
  ('vendor-mediakit','written-permission','cc-by','stock','own');

CREATE TYPE approval_status AS ENUM
  ('pending','approved','rejected','expired');

CREATE TABLE sources (
    id              BIGSERIAL PRIMARY KEY,
    platform        source_platform NOT NULL,
    kind            source_kind     NOT NULL,
    content_type    content_type    NOT NULL DEFAULT 'video',
    source_url      TEXT            NOT NULL UNIQUE,
    display_name    TEXT,

    -- Ngôn ngữ audio/text của nguồn: chọn nhánh ASR, chiều glossary,
    -- và mức kỳ vọng công duyệt (zh tốn ~gấp đôi en).
    audio_lang      TEXT            NOT NULL DEFAULT 'en',

    -- Watermark dán cứng (Douyin/TikTok): nếu true thì KHÔNG publish lên TikTok
    -- và không được xoá watermark.
    has_baked_watermark BOOLEAN     NOT NULL DEFAULT FALSE,

    -- ===== License =====
    license_type    license_type,
    evidence_ref    TEXT,          -- link điều khoản / file email đồng ý / số hợp đồng
    attribution_text TEXT,         -- chuỗi ghi nguồn bắt buộc hiện trong video (CC BY yêu cầu)

    -- scope là các quyền RỜI vì "được dùng lại" KHÔNG suy ra "được sửa audio".
    -- Lồng tiếng cần may_modify_audio = TRUE.
    may_translate       BOOLEAN NOT NULL DEFAULT FALSE,
    may_modify_audio    BOOLEAN NOT NULL DEFAULT FALSE,
    may_subtitle        BOOLEAN NOT NULL DEFAULT FALSE,
    may_republish       BOOLEAN NOT NULL DEFAULT FALSE,
    may_commercial_use  BOOLEAN NOT NULL DEFAULT FALSE,

    topics          TEXT[] NOT NULL DEFAULT '{}',  -- theo taxonomy nmi.vn, lọc relevance
    status          approval_status NOT NULL DEFAULT 'pending',
    approved_by     TEXT,
    approved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE sources IS
  'Nguồn đã khai báo. Pipeline TỪ CHỐI tải nếu status<>approved. Không thêm đường tắt bỏ qua.';

-- Nguồn approved bắt buộc phải có bằng chứng license.
ALTER TABLE sources ADD CONSTRAINT sources_approved_needs_evidence
  CHECK (status <> 'approved' OR (license_type IS NOT NULL AND evidence_ref IS NOT NULL));

CREATE INDEX sources_status_idx   ON sources(status);
CREATE INDEX sources_platform_idx ON sources(platform);

-- ============================================================
-- items — cấp từng video/bài, do crawler hoặc hộp thư URL sinh ra
-- ============================================================
CREATE TYPE item_stage AS ENUM (
    'inbox',             -- vừa nạp URL
    'license_blocked',   -- nguồn cha chưa approved
    'downloaded',
    'separated',         -- đã tách audio (demucs)
    'transcribed',
    'transcript_review', -- chờ người soát transcript
    'segment_picked',
    'scripted',
    'voiced',            -- TTS xong
    'aligned',           -- forced alignment xong
    'mixed',
    'rendered',
    'human_review',      -- gate duyệt bắt buộc
    'approved',
    'published',
    'failed',
    'rejected'
);

CREATE TABLE items (
    id              BIGSERIAL PRIMARY KEY,
    source_id       BIGINT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    item_url        TEXT   NOT NULL UNIQUE,
    external_id     TEXT,
    title_original  TEXT,
    duration_sec    INTEGER,
    aspect_ratio    TEXT,      -- '16:9' | '9:16' ... quyết định có reframe hay không

    stage           item_stage NOT NULL DEFAULT 'inbox',
    stage_error     TEXT,

    -- Đường dẫn tương đối trong MEDIA_ROOT, không bao giờ là đường dẫn tuyệt đối
    path_source     TEXT,
    path_work       TEXT,
    path_output     TEXT,

    segment_start_sec NUMERIC(10,3),
    segment_end_sec   NUMERIC(10,3),
    script_vi         TEXT,
    script_sources    JSONB,   -- GĐ2: bài nào đã đọc để viết ra kịch bản này

    review_by       TEXT,
    review_at       TIMESTAMPTZ,
    review_notes    TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX items_stage_idx  ON items(stage);
CREATE INDEX items_source_idx ON items(source_id);

-- ============================================================
-- publications — một item có thể đăng nhiều nền tảng
-- ============================================================
CREATE TYPE publish_platform AS ENUM ('youtube','facebook','tiktok','linkedin');
CREATE TYPE publish_status   AS ENUM ('queued','uploading','published','failed','skipped');

CREATE TABLE publications (
    id              BIGSERIAL PRIMARY KEY,
    item_id         BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    platform        publish_platform NOT NULL,
    status          publish_status   NOT NULL DEFAULT 'queued',
    remote_id       TEXT,
    remote_url      TEXT,
    error           TEXT,
    skipped_reason  TEXT,   -- vd: 'nguồn có watermark dán cứng — không đăng TikTok'
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (item_id, platform)
);

-- ============================================================
-- jobs — hàng đợi việc nặng cho worker (dùng Postgres, không cần Redis)
-- ============================================================
CREATE TYPE job_status AS ENUM ('pending','running','done','failed','cancelled');

CREATE TABLE jobs (
    id            BIGSERIAL PRIMARY KEY,
    item_id       BIGINT REFERENCES items(id) ON DELETE CASCADE,
    task          TEXT   NOT NULL,     -- 'download' | 'asr' | 'tts' | 'reframe' | 'render' ...
    status        job_status NOT NULL DEFAULT 'pending',
    priority      SMALLINT NOT NULL DEFAULT 100,
    attempts      SMALLINT NOT NULL DEFAULT 0,
    max_attempts  SMALLINT NOT NULL DEFAULT 3,
    payload       JSONB NOT NULL DEFAULT '{}',
    error         TEXT,
    locked_by     TEXT,
    locked_at     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);

-- Worker lấy việc bằng SELECT ... FOR UPDATE SKIP LOCKED trên index này
CREATE INDEX jobs_pickup_idx ON jobs(status, priority, created_at) WHERE status = 'pending';

-- ============================================================
-- glossary — thuật ngữ EN↔VI và ZH↔VI, rút từ corpus song ngữ nmi.vn.
-- Dùng chung Giai đoạn 1 và 2.
-- ============================================================
CREATE TABLE glossary (
    id            BIGSERIAL PRIMARY KEY,
    src_lang      TEXT NOT NULL,          -- 'en' | 'zh'
    term_src      TEXT NOT NULL,
    term_vi       TEXT NOT NULL,
    domain        TEXT,                   -- 'spc' | 'msa' | 'mes' | 'historian' | 'vision'
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (src_lang, term_src)
);

-- ============================================================
-- audit_log — vết thao tác trên quyết định license và duyệt nội dung
-- ============================================================
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    entity      TEXT NOT NULL,    -- 'source' | 'item' | 'publication'
    entity_id   BIGINT NOT NULL,
    action      TEXT NOT NULL,
    actor       TEXT,
    detail      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX audit_entity_idx ON audit_log(entity, entity_id);
