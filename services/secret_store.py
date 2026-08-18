from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class SecretStoreError(RuntimeError):
    """Erro seguro de armazenamento ou leitura de segredos."""


def _fernet() -> Fernet:
    key = os.getenv("TELEGRAM_TOKEN_ENCRYPTION_KEY", "").strip().encode()
    if not key:
        raise SecretStoreError("TELEGRAM_TOKEN_ENCRYPTION_KEY não configurada")
    try:
        return Fernet(key)
    except Exception as exc:
        raise SecretStoreError("TELEGRAM_TOKEN_ENCRYPTION_KEY inválida") from exc


def encrypt_secret(value: str) -> str:
    if not value:
        raise SecretStoreError("Não é possível cifrar um segredo vazio")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretStoreError("Segredo cifrado inválido") from exc
