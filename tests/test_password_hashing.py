from __future__ import annotations

import hashlib
from pathlib import Path

from models import AuthLoginRequest, AuthRegisterRequest
from server.session_store import InMemorySessionStore


def _store(tmp_path: Path) -> InMemorySessionStore:
    return InMemorySessionStore(store_path=tmp_path / "store.json")


def test_password_hashes_are_salted_and_verify_correctly(tmp_path: Path) -> None:
    store = _store(tmp_path)

    first = store._hash_password("correct horse battery staple")
    second = store._hash_password("correct horse battery staple")

    assert first.startswith("pbkdf2_sha256$600000$")
    assert first != second
    assert store._verify_password("correct horse battery staple", first)
    assert not store._verify_password("incorrect password", first)


def test_legacy_sha256_hash_is_verified_and_upgraded_on_login(tmp_path: Path) -> None:
    store = _store(tmp_path)
    account = store.register_account(
        AuthRegisterRequest(
            name="Legacy User",
            email="legacy@example.com",
            password="password123",
        )
    )
    stored = store._auth_accounts[account.account_id]
    stored.password_hash = hashlib.sha256(b"password123").hexdigest()
    store._write_auth_account(stored)
    store._save()

    response = store.login_account(
        AuthLoginRequest(email="legacy@example.com", password="password123")
    )

    assert response.account.account_id == account.account_id
    assert store._auth_accounts[account.account_id].password_hash.startswith(
        "pbkdf2_sha256$600000$"
    )


def test_malformed_password_hash_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert not store._verify_password("anything", "pbkdf2_sha256$not-a-number$bad$bad")
    assert not store._verify_password("anything", "not-a-supported-hash")
