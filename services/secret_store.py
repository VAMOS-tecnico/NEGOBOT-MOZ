from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


class SecretStoreError(RuntimeError):
    """Erro seguro de armazenamento ou leitura de segredos."""


def _fernet() -> Fernet:
    explicit_key = os.getenv("TELEGRAM_TOKEN_ENCRYPTION_KEY", "").strip()
    if explicit_key:
        key = explicit_key.encode()
    else:
        platform_key = (os.getenv("PLATFORM_SECRET_KEY") or os.getenv("ADMIN_TOKEN") or "").strip()
        if not platform_key:
            raise SecretStoreError("Nenhuma chave de segurança do Backend está configurada")
        digest = hashlib.sha256(f"negobot-telegram-secret-v1:{platform_key}".encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        return Fernet(key)
    except Exception as exc:
        raise SecretStoreError("Chave de cifragem inválida") from exc


def encrypt_secret(value: str) -> str:
    if not value:
        raise SecretStoreError("Não é possível cifrar um segredo vazio")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretStoreError("Segredo cifrado inválido") from exc
