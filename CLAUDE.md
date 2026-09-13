# CLAUDE.md

**Đọc [AGENTS.md](AGENTS.md) — toàn bộ hướng dẫn nằm ở đó.** File này chỉ là con trỏ để Claude Code và Codex dùng chung một nguồn, không phải hai bản lệch nhau.

Ba điều quan trọng nhất, nhắc lại để không phải mở file khác:

1. **Không mở subagent** trừ khi người dùng yêu cầu đích danh.
2. **Đọc `PLAN.md` trước**, không đọc `docs/phuong-an-cuoi-cung.md` toàn bộ — chỉ đọc mục liên quan.
3. **Test đúng module vừa sửa** (`pytest tests/unit/test_<module>.py -x -q`), không quét cả bộ.
