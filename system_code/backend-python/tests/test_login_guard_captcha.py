"""Tests for login throttling and image-captcha generation.

Security gaps under test:
  P5 — the login endpoint had no failure limit at all (brute-forceable).
  P6 — the captcha was a plaintext SVG; the answer was embedded verbatim in the
       response body, so it protected nothing.
"""
from app.services.captcha import ALPHABET, generate_captcha, random_code
from app.services.login_guard import LoginGuard


# ── P5 login throttling ─────────────────────────────────────────────────────
def test_allows_before_any_failure():
    g = LoginGuard(max_attempts=3, window_seconds=600, lockout_seconds=600)
    assert g.remaining_lockout('admin', '1.1.1.1') == 0.0


def test_locks_after_max_attempts():
    g = LoginGuard(max_attempts=3, window_seconds=600, lockout_seconds=600)
    g.record_failure('admin', '1.1.1.1', now=1000)
    g.record_failure('admin', '1.1.1.1', now=1001)
    assert g.remaining_lockout('admin', '1.1.1.1', now=1002) == 0.0
    g.record_failure('admin', '1.1.1.1', now=1002)
    assert g.remaining_lockout('admin', '1.1.1.1', now=1002) > 590


def test_lockout_expires():
    g = LoginGuard(max_attempts=2, window_seconds=600, lockout_seconds=100)
    g.record_failure('admin', 'ip', now=1000)
    g.record_failure('admin', 'ip', now=1001)
    assert g.remaining_lockout('admin', 'ip', now=1050) > 0
    assert g.remaining_lockout('admin', 'ip', now=1200) == 0.0


def test_isolated_per_username_and_ip():
    g = LoginGuard(max_attempts=2, window_seconds=600, lockout_seconds=600)
    g.record_failure('admin', '1.1.1.1', now=1000)
    g.record_failure('admin', '1.1.1.1', now=1001)
    assert g.remaining_lockout('admin', '1.1.1.1', now=1002) > 0
    assert g.remaining_lockout('nurse', '1.1.1.1', now=1002) == 0.0      # other account
    assert g.remaining_lockout('admin', '2.2.2.2', now=1002) == 0.0      # other IP


def test_successful_login_resets_counter():
    g = LoginGuard(max_attempts=3, window_seconds=600, lockout_seconds=600)
    g.record_failure('admin', 'ip', now=1000)
    g.record_failure('admin', 'ip', now=1001)
    g.reset('admin', 'ip')
    g.record_failure('admin', 'ip', now=1002)
    assert g.remaining_lockout('admin', 'ip', now=1002) == 0.0


def test_window_expiry_clears_failures():
    g = LoginGuard(max_attempts=3, window_seconds=60, lockout_seconds=600)
    g.record_failure('admin', 'ip', now=1000)
    g.record_failure('admin', 'ip', now=1001)
    # long gap -> window resets, so one more failure must not lock
    g.record_failure('admin', 'ip', now=2000)
    assert g.remaining_lockout('admin', 'ip', now=2000) == 0.0


def test_cleanup_drops_stale_entries():
    g = LoginGuard(max_attempts=5, window_seconds=10, lockout_seconds=10)
    g.record_failure('a', 'ip', now=1000)
    g.cleanup(now=2000)
    assert g.tracked == 0


# ── P6 image captcha ────────────────────────────────────────────────────────
def test_captcha_returns_png_not_plaintext():
    code, png = generate_captcha()
    assert len(code) == 4
    assert png[:8] == b'\x89PNG\r\n\x1a\n', '应为真正的 PNG'
    assert code.encode() not in png, '明文验证码不得出现在图片字节中'


def test_captcha_chars_avoid_ambiguous():
    for _ in range(50):
        code = random_code()
        assert all(c in ALPHABET for c in code)
        assert not set(code) & set('0O1IL'), f'含易混字符: {code}'


def test_captcha_codes_differ():
    codes = {generate_captcha()[0] for _ in range(30)}
    assert len(codes) > 20, '验证码重复率过高'


# ── route-level integration (no HTTP server / no AI warmup needed) ──────────
import json
from fastapi import HTTPException
from app.api.routes import auth as auth_module
from app.services.login_guard import LoginGuard


def test_captcha_endpoint_never_leaks_the_code():
    data = auth_module.captcha()
    payload = data['data']
    assert payload['image'].startswith('data:image/png;base64,')
    assert 'svg' not in payload, '不应再返回明文 SVG'
    code = auth_module._captchas[payload['id']][0]
    assert code not in json.dumps(data), '响应体不得包含验证码明文'


def test_login_route_returns_429_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(auth_module, '_verify_captcha', lambda *a, **k: None)
    monkeypatch.setattr(auth_module, 'login_guard',
                        LoginGuard(max_attempts=3, window_seconds=600, lockout_seconds=600))
    body = auth_module.LoginBody(username='nobody_xyz_does_not_exist', password='wrong')
    codes = []
    for _ in range(4):
        try:
            auth_module.login(body, request=None)
            codes.append(200)
        except HTTPException as exc:
            codes.append(exc.status_code)
    assert codes == [401, 401, 401, 429], f'实际 {codes}'
