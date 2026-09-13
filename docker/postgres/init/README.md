# docker/postgres/init/

Script trong thư mục này **chỉ chạy một lần**, khi Postgres khởi tạo trên thư mục
`data/` trống. Đã có dữ liệu thì chúng không chạy lại.

Vì vậy ở đây chỉ còn `00-n8n-schema.sql` — thứ phải tồn tại trước khi n8n kết nối.

**Schema của ứng dụng do alembic quản lý:** `alembic/versions/`. Chạy `make migrate`.

Trước đây có `01-schema.sql` chứa toàn bộ DDL. Đã bỏ vì hai bản DDL song song
(file SQL và model ORM) chắc chắn sẽ lệch nhau theo thời gian — và lệch ở bảng
`sources` nghĩa là lệch ở kiểm soát pháp lý. Nội dung cũ nằm trong
`alembic/versions/0001_baseline.py`, viết idempotent nên chạy được cả trên DB
trống và DB đã có bảng từ bản cũ.
