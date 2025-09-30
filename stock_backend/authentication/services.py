from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
import logging
from typing import Optional
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from .models import PasswordResetToken, EmailVerificationToken


def get_client_ip(request) -> str:
    """Best-effort client IP extraction suitable for rate limiting."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # XFF may contain multiple, use the first
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _attempts_key(username: str, ip: str) -> str:
    prefix = getattr(settings, 'CACHE_KEY_PREFIX', '')
    return f"{prefix}auth:attempts:{username}:{ip}"


def _lock_key(username: str, ip: str) -> str:
    prefix = getattr(settings, 'CACHE_KEY_PREFIX', '')
    return f"{prefix}auth:lock:{username}:{ip}"


def is_locked(username: str, ip: str) -> bool:
    return bool(cache.get(_lock_key(username, ip)))


def record_failed_attempt(username: str, ip: str) -> int:
    """Increment failed attempts counter within attempt window; returns current count."""
    key = _attempts_key(username, ip)
    attempts = cache.get(key)
    window = int(getattr(settings, 'AUTH_ATTEMPT_WINDOW_SECONDS', 600))
    if attempts is None:
        cache.set(key, 1, timeout=window)
        logging.getLogger('authentication').warning(
            "auth.login_failed user=%s ip=%s attempts=%s", username, ip, 1
        )
        return 1
    try:
        # incr preserves original TTL in most backends
        new_attempts = cache.incr(key)
        logging.getLogger('authentication').warning(
            "auth.login_failed user=%s ip=%s attempts=%s", username, ip, new_attempts
        )
        return new_attempts
    except Exception:
        attempts = int(attempts) + 1
        cache.set(key, attempts, timeout=window)
        logging.getLogger('authentication').warning(
            "auth.login_failed user=%s ip=%s attempts=%s", username, ip, attempts
        )
        return attempts


def lock_account(username: str, ip: str) -> None:
    lock_seconds = int(getattr(settings, 'AUTH_LOCKOUT_SECONDS', 300))
    cache.set(_lock_key(username, ip), True, timeout=lock_seconds)
    logging.getLogger('authentication').warning(
        "auth.login_lockout user=%s ip=%s lock_seconds=%s", username, ip, lock_seconds
    )


def reset_attempts(username: str, ip: str) -> None:
    cache.delete_many([_attempts_key(username, ip), _lock_key(username, ip)])
    logging.getLogger('authentication').info(
        "auth.login_reset_attempts user=%s ip=%s", username, ip
    )


# ===== Password reset token services =====
def create_password_reset_token(user) -> PasswordResetToken:
    ttl_minutes = int(getattr(settings, 'PASSWORD_RESET_TOKEN_TTL_MINUTES', 30))
    expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
    return PasswordResetToken.objects.create(user=user, expires_at=expires_at)


def send_password_reset_email(user, token: PasswordResetToken) -> None:
    frontend_url = getattr(settings, 'PASSWORD_RESET_FRONTEND_URL', 'http://localhost:3000/password-reset/confirm')
    reset_link = f"{frontend_url}?token={token.token}&email={user.email}"
    subject = "비밀번호 재설정 안내"
    message = f"다음 링크를 클릭하여 비밀번호를 재설정하세요:\n{reset_link}\n이 링크는 일정 시간 후 만료됩니다."
    send_mail(
        subject,
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
        [user.email],
        fail_silently=False,
    )


# ===== Email verification services =====
def create_email_verification_token(user) -> EmailVerificationToken:
    ttl_minutes = int(getattr(settings, 'EMAIL_VERIFICATION_TOKEN_TTL_MINUTES', 60))
    expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
    return EmailVerificationToken.objects.create(user=user, expires_at=expires_at)


def send_email_verification(user, token: EmailVerificationToken) -> None:
    frontend_url = getattr(settings, 'EMAIL_VERIFICATION_FRONTEND_URL', 'http://localhost:3000/verify-email')
    verify_link = f"{frontend_url}?token={token.token}&email={user.email}"
    subject = "이메일 주소 확인"
    message = f"다음 링크를 클릭하여 이메일 주소를 확인하세요:\n{verify_link}\n이 링크는 일정 시간 후 만료됩니다."
    send_mail(
        subject,
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
        [user.email],
        fail_silently=False,
    )


