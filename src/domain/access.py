"""Vai trò và quyền của mặt tiền quản trị Q One Media."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    ADMIN = "admin"

    @property
    def label(self) -> str:
        return {
            Role.VIEWER: "Chỉ xem",
            Role.REVIEWER: "Người duyệt",
            Role.EDITOR: "Biên tập viên",
            Role.ADMIN: "Quản trị viên",
        }[self]

    def permits(self, required: Role) -> bool:
        order = (Role.VIEWER, Role.REVIEWER, Role.EDITOR, Role.ADMIN)
        return order.index(self) >= order.index(required)
