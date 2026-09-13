"""Lỗi của tầng domain.

Phân loại theo **có retry được hay không** — tầng ngoài dựa vào đây để quyết
định xếp lại việc hay bỏ, không phải đoán từ chuỗi thông báo.
"""

from __future__ import annotations


class DomainError(Exception):
    """Gốc của mọi lỗi nghiệp vụ. Không bao giờ retry được: input hoặc trạng thái sai."""

    retryable = False


class InvariantViolation(DomainError):
    """Dữ liệu vi phạm bất biến của aggregate."""


class InvalidTransition(DomainError):
    """Chuyển trạng thái không hợp lệ trong máy trạng thái của item."""


# --- Nhóm license: cố tình tách riêng để không bao giờ bị bắt lẫn với lỗi khác ---


class LicenseViolation(DomainError):
    """Gốc của mọi từ chối vì lý do quyền sử dụng.

    Không bắt rồi bỏ qua nhóm lỗi này ở bất cứ đâu. Nó là kiểm soát pháp lý,
    không phải lỗi kỹ thuật tạm thời.
    """


class SourceNotApproved(LicenseViolation):
    pass


class SourceExpired(LicenseViolation):
    pass


class ScopeNotGranted(LicenseViolation):
    """Nguồn đã approved nhưng phạm vi quyền không gồm việc đang định làm."""


class HumanReviewRequired(DomainError):
    """Chưa qua gate duyệt của người — Giai đoạn 1 bắt buộc."""
