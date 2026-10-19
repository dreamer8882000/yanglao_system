"""密码哈希的向后兼容性测试（TDD）。

背景：数据库现有用户的历史密码是 bcrypt 不可用时的 SHA-256 十六进制回退哈希
（例如 admin/123456 对应 8d969eef...）。升级锁定 bcrypt==4.0.1 后，
hash_password 开始产出 bcrypt 哈希，verify_password 必须同时兼容：
1. 新的 bcrypt 哈希（正常校验）；
2. 历史的 SHA-256 十六进制哈希（回退校验）。
"""
import hashlib

from app.core.security import hash_password, verify_password


def test_hash_password_produces_bcrypt():
    hashed = hash_password('123456')
    assert hashed.startswith('$2'), f'期望 bcrypt 哈希，实际: {hashed[:12]}...'


def test_verify_bcrypt_correct():
    hashed = hash_password('123456')
    assert verify_password('123456', hashed) is True


def test_verify_bcrypt_wrong():
    hashed = hash_password('123456')
    assert verify_password('wrong-password', hashed) is False


def test_verify_legacy_sha256_correct():
    legacy = hashlib.sha256('123456'.encode('utf-8')).hexdigest()
    assert verify_password('123456', legacy) is True


def test_verify_legacy_sha256_wrong():
    legacy = hashlib.sha256('123456'.encode('utf-8')).hexdigest()
    assert verify_password('wrong-password', legacy) is False


def test_verify_empty_hash_is_false():
    assert verify_password('123456', '') is False
