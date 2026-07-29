from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token(subject="1", extra={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["role"] == "admin"
