from src.common.signing import sign_payload, verify_signature


def test_sign_verify_roundtrip() -> None:
    body = b'{"order_id":"42","status":"delivered"}'
    sig = sign_payload("secret", body)
    assert verify_signature("secret", body, sig)


def test_verify_rejects_tampered_body() -> None:
    sig = sign_payload("secret", b"original")
    assert not verify_signature("secret", b"tampered", sig)


def test_verify_rejects_wrong_secret() -> None:
    sig = sign_payload("secret", b"body")
    assert not verify_signature("other-secret", b"body", sig)
