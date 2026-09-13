-- Chạy tự động khi postgres init lần đầu (thư mục data trống).
-- CHỈ tạo schema cho n8n, vì n8n tự tạo bảng của nó khi khởi động và cần schema
-- tồn tại trước.
--
-- Schema của ứng dụng KHÔNG ở đây nữa: alembic là nguồn duy nhất.
--   make migrate
-- Lý do đổi: hai bản DDL song song (file SQL + model ORM) chắc chắn sẽ lệch
-- nhau, và lệch ở bảng sources nghĩa là lệch ở kiểm soát pháp lý.

CREATE SCHEMA IF NOT EXISTS n8n;
