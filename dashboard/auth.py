"""
Простая парольная авторизация с подписанной cookie.

Порядок поиска пароля:
  1) переменная окружения DASHBOARD_PASSWORD;
  2) файл dashboard/.password (одна строка);
  3) сгенерируется случайный, распечатается в консоль (одноразовый).

SECRET_KEY подписывает cookie — если поменяется, все сессии слетят.
Он автоматически сохраняется в dashboard/.secret при первом запуске,
чтобы после рестарта не разлогинивать себя.

Оба файла лежат в dashboard/, добавлены в .gitignore.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from itsdangerous import BadSignature, URLSafeSerializer

_SESSION_COOKIE = "vgs_dash"

_DASH_DIR = Path(__file__).parent
_PASSWORD_FILE = _DASH_DIR / ".password"
_SECRET_FILE = _DASH_DIR / ".secret"


def _load_or_generate_password() -> str:
    # 1. Переменная окружения
    pwd = os.getenv("DASHBOARD_PASSWORD", "").strip()
    if pwd:
        return pwd

    # 2. Файл dashboard/.password
    if _PASSWORD_FILE.exists():
        try:
            content = _PASSWORD_FILE.read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"[dashboard] не смог прочитать {_PASSWORD_FILE}: {e}")
            content = ""
        if content:
            return content

    # 3. Одноразовый — генерим и печатаем
    generated = secrets.token_urlsafe(9)
    print("=" * 64)
    print("  Пароль не задан — сгенерирован временный (действует до рестарта):")
    print(f"    {generated}")
    print(f"  Чтобы зафиксировать: запиши свой пароль в {_PASSWORD_FILE}")
    print("  (одной строкой) — либо задай DASHBOARD_PASSWORD в окружении.")
    print("=" * 64)
    return generated


def _load_or_generate_secret() -> str:
    # 1. Переменная окружения
    key = os.getenv("DASHBOARD_SECRET", "").strip()
    if key:
        return key

    # 2. Файл dashboard/.secret
    if _SECRET_FILE.exists():
        try:
            content = _SECRET_FILE.read_text(encoding="utf-8").strip()
            if content:
                return content
        except OSError:
            pass

    # 3. Генерим и сохраняем, чтобы после рестарта сессии не слетели
    generated = secrets.token_urlsafe(48)
    try:
        _SECRET_FILE.write_text(generated, encoding="utf-8")
        # Не критично, если chmod не сработает на Windows
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError as e:
        print(f"[dashboard] не смог сохранить {_SECRET_FILE}: {e}")
    return generated


PASSWORD = _load_or_generate_password()
SECRET_KEY = _load_or_generate_secret()
_serializer = URLSafeSerializer(SECRET_KEY, salt="vgs-dash-session")


def check_password(candidate: str) -> bool:
    return secrets.compare_digest(candidate or "", PASSWORD)


def issue_session_token() -> str:
    return _serializer.dumps({"ok": True})


def verify_cookie(raw: str | None) -> bool:
    if not raw:
        return False
    try:
        data = _serializer.loads(raw)
    except BadSignature:
        return False
    return bool(data.get("ok"))


SESSION_COOKIE = _SESSION_COOKIE
