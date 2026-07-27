"""Unit tests for remember-me device token minting, parsing, and verification."""

import core.device_token as device_token


def test_mint_token_roundtrip_verifies():
    minted = device_token.mint_token()

    # Cookie is "<devtok_id>.<secret>" and the id is a 32-hex-char uuid.
    devtok_id, secret = minted.cookie_value.split(".", 1)
    assert devtok_id == minted.devtok_id
    assert len(devtok_id) == 32
    int(devtok_id, 16)  # raises if not hex

    # Only the Argon2 hash is stored, and the secret verifies against it.
    assert minted.tokenhash.startswith("$argon2")
    assert len(minted.tokenhash) <= 255
    assert device_token.verify_secret(secret, minted.tokenhash)


def test_mint_token_is_unique():
    a = device_token.mint_token()
    b = device_token.mint_token()

    assert a.devtok_id != b.devtok_id
    assert a.cookie_value != b.cookie_value
    assert a.tokenhash != b.tokenhash


def test_mint_token_rotation_reuses_id_with_new_secret():
    original = device_token.mint_token()
    rotated = device_token.mint_token(original.devtok_id)

    # Same token id, brand-new secret/hash.
    assert rotated.devtok_id == original.devtok_id
    assert rotated.cookie_value != original.cookie_value
    assert rotated.tokenhash != original.tokenhash

    # The old secret no longer verifies against the rotated hash.
    _, old_secret = original.cookie_value.split(".", 1)
    _, new_secret = rotated.cookie_value.split(".", 1)
    assert not device_token.verify_secret(old_secret, rotated.tokenhash)
    assert device_token.verify_secret(new_secret, rotated.tokenhash)


def test_split_cookie_roundtrip():
    minted = device_token.mint_token()
    parsed = device_token.split_cookie(minted.cookie_value)

    assert parsed is not None
    devtok_id, secret = parsed
    assert devtok_id == minted.devtok_id
    assert device_token.verify_secret(secret, minted.tokenhash)


def test_split_cookie_rejects_malformed():
    assert device_token.split_cookie(None) is None
    assert device_token.split_cookie("") is None
    assert device_token.split_cookie("no-separator") is None
    assert device_token.split_cookie("a" * 32) is None  # missing ".secret"
    assert device_token.split_cookie("." + "secret") is None  # empty id
    assert device_token.split_cookie("a" * 32 + ".") is None  # empty secret
    # id present but not a valid uuid hex string
    assert device_token.split_cookie("not-a-valid-id.secret") is None


def test_verify_secret_rejects_wrong_secret():
    minted = device_token.mint_token()
    assert not device_token.verify_secret("wrong-secret", minted.tokenhash)
