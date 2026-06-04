from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.utils import timezone
from django.utils.text import slugify

from fantasy.models import DeviceSession, Player, PortalSetting


GATE_SALT = "fantasy.gate"
GATE_PASSWORD_KEY = "gate_password_hash"


def normalize_nick(value: str) -> str:
    nick = slugify(value or "").lower()
    return nick[:40]


def has_gate(request) -> bool:
    value = request.COOKIES.get(settings.FANTASY_GATE_COOKIE)
    if not value:
        return False
    try:
        return signing.loads(value, salt=GATE_SALT, max_age=settings.FANTASY_COOKIE_AGE) == "ok"
    except signing.BadSignature:
        return False


def gate_cookie_value() -> str:
    return signing.dumps("ok", salt=GATE_SALT)


def is_gate_password_configured() -> bool:
    return PortalSetting.objects.filter(key=GATE_PASSWORD_KEY).exists()


def verify_or_initialize_gate_password(password: str) -> bool:
    if not password:
        return False
    setting, created = PortalSetting.objects.get_or_create(
        key=GATE_PASSWORD_KEY,
        defaults={"value": make_password(password)},
    )
    if created:
        return True
    return check_password(password, setting.value)


def set_long_cookie(response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=settings.FANTASY_COOKIE_AGE,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_player(request) -> Player | None:
    raw_token = request.COOKIES.get(settings.FANTASY_DEVICE_COOKIE)
    if not raw_token:
        return None
    try:
        device = DeviceSession.objects.select_related("player").get(token_hash=token_hash(raw_token))
    except DeviceSession.DoesNotExist:
        return None
    Player.objects.filter(pk=device.player_id).update(last_seen_at=timezone.now())
    return device.player


def attach_player_device(response, request, player: Player) -> None:
    raw_token = secrets.token_urlsafe(32)
    DeviceSession.objects.create(
        player=player,
        token_hash=token_hash(raw_token),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
    )
    Player.objects.filter(pk=player.pk).update(last_seen_at=timezone.now())
    set_long_cookie(response, settings.FANTASY_DEVICE_COOKIE, raw_token)


def create_player(nick_value: str, pin: str) -> Player:
    nick = normalize_nick(nick_value)
    if not nick:
        raise ValueError("Choose a nick using letters or numbers.")
    if not pin:
        raise ValueError("PIN is required.")
    return Player.objects.create(nick=nick, display_name=nick_value.strip()[:60] or nick, pin_hash=make_password(pin))


def authenticate_player(nick_value: str, pin: str) -> Player | None:
    nick = normalize_nick(nick_value)
    if not nick:
        return None
    try:
        player = Player.objects.get(nick=nick)
    except Player.DoesNotExist:
        return None
    if check_password(pin, player.pin_hash):
        return player
    return None
