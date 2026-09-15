from src.domain.access import Role
from src.interfaces.web.auth import hash_password, verify_password


def test_mat_khau_duoc_bam_va_xac_minh():
    encoded = hash_password("mat-khau-tot")
    assert "mat-khau-tot" not in encoded
    assert verify_password("mat-khau-tot", encoded)
    assert not verify_password("sai", encoded)


def test_vai_tro_co_thu_tu_quyen_ro_rang():
    assert Role.ADMIN.permits(Role.EDITOR)
    assert Role.EDITOR.permits(Role.REVIEWER)
    assert Role.REVIEWER.permits(Role.VIEWER)
    assert not Role.VIEWER.permits(Role.REVIEWER)
