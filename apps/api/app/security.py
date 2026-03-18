from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import BASE_DIR

# 加密密钥文件路径
KEY_FILE = BASE_DIR / ".encryption_key"


def _get_or_create_key() -> bytes:
    """获取或创建加密密钥。"""
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    # 生成新密钥
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    # 设置文件权限（仅当前用户可读）
    os.chmod(KEY_FILE, 0o600)
    return key


def get_cipher() -> Fernet:
    """获取加密/解密器。"""
    key = _get_or_create_key()
    return Fernet(key)


def encrypt_value(value: str | None) -> str | None:
    """加密敏感值。"""
    if not value:
        return None
    cipher = get_cipher()
    encrypted = cipher.encrypt(value.encode())
    return base64.b64encode(encrypted).decode()


def decrypt_value(encrypted_value: str | None) -> str | None:
    """解密敏感值。"""
    if not encrypted_value:
        return None
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(base64.b64decode(encrypted_value))
        return decrypted.decode()
    except Exception:
        # 解密失败返回None（可能是明文存储的旧数据）
        return encrypted_value


def mask_value(value: str | None, visible_chars: int = 4) -> str | None:
    """脱敏显示敏感值。"""
    if not value:
        return None
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}{'*' * (len(value) - visible_chars * 2)}{value[-visible_chars:]}"
