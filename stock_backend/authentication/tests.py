from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.test.utils import override_settings
from django.core.cache import cache
from django.core import mail
from django.http import HttpResponse
from django.test.utils import override_settings


class TestAuthStatusCsrfCookie(TestCase):
    def setUp(self):
        self.client = Client()

    def test_auth_status_sets_csrf_cookie(self):
        response = self.client.get("/api/auth/status/")
        self.assertIn('csrftoken', response.cookies)


@override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
                   SESSION_COOKIE_SAMESITE='None', CSRF_COOKIE_SAMESITE='None')
class TestCookieSecurityFlags(TestCase):
    def setUp(self):
        self.client = Client()

    def test_secure_and_samesite_flags_on_cookies(self):
        # Trigger a response that sets csrftoken
        resp = self.client.get("/api/auth/status/")
        csrftoken = resp.cookies.get('csrftoken')
        self.assertIsNotNone(csrftoken)
        # Django uses key accessors for attributes; to_string contains flags
        cookie_str = csrftoken.output()
        self.assertIn('Secure', cookie_str)
        self.assertIn('SameSite=None', cookie_str)


class TestLogoutCsrfEnforcement(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(username="alice", password="password123", email="a@a.com")

    def _login_session(self):
        # login via view to create a session cookie
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "alice", "password": "password123"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_logout_without_csrf_fails(self):
        self._login_session()
        # Missing CSRF header should be rejected
        resp = self.client.post("/api/auth/logout/")
        self.assertIn(resp.status_code, [403, 401])

    def test_logout_with_csrf_succeeds(self):
        self._login_session()
        # Fetch status to get csrftoken cookie
        status_resp = self.client.get("/api/auth/status/")
        self.assertIn('csrftoken', status_resp.cookies)
        csrftoken = status_resp.cookies['csrftoken'].value
        # Send logout with CSRF header and session cookie
        resp = self.client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=csrftoken)
        self.assertEqual(resp.status_code, 200)


class TestRememberMeSessionExpiry(TestCase):
    def setUp(self):
        # enforce CSRF because login is POST and client needs header
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(username="bob", password="password123", email="b@b.com")

    def _get_csrf(self):
        r = self.client.get("/api/auth/status/")
        return r.cookies['csrftoken'].value

    def test_login_without_remember_me_expires_on_browser_close(self):
        csrftoken = self._get_csrf()
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "bob", "password": "password123", "remember_me": False},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 200)
        # Django exposes session cookie as 'sessionid'; max-age None means expire at browser close
        session_cookie = resp.client.cookies.get('sessionid')
        self.assertIsNotNone(session_cookie)
        # max-age may be missing (None) for browser-close
        self.assertTrue(session_cookie.get("max-age") in (None, '',))

    def test_login_with_remember_me_sets_max_age(self):
        csrftoken = self._get_csrf()
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "bob", "password": "password123", "remember_me": True},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 200)
        session_cookie = resp.client.cookies.get('sessionid')
        self.assertIsNotNone(session_cookie)
        # When remember_me is true, max-age should be set to a positive integer
        max_age = session_cookie.get("max-age")
        # Some backends set 'Max-Age', Django test client normalizes to 'max-age'
        if max_age is None:
            # Fallback: check for expiry attribute
            expires = session_cookie.get("expires")
            self.assertTrue(expires is not None and expires != '')
        else:
            # If present, should be numeric and > 0
            try:
                self.assertTrue(int(max_age) > 0)
            except Exception:
                self.fail("session cookie max-age is not a positive integer")


@override_settings(AUTH_MAX_LOGIN_ATTEMPTS=3, AUTH_LOCKOUT_SECONDS=60, AUTH_ATTEMPT_WINDOW_SECONDS=300)
class TestLoginRateLimitAndLockout(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        cache.clear()
        self.user = User.objects.create_user(username="rick", password="correcthorse", email="r@r.com")

    def _get_csrf(self):
        r = self.client.get("/api/auth/status/")
        return r.cookies['csrftoken'].value

    def test_lockout_after_repeated_failures(self):
        csrftoken = self._get_csrf()
        # 3 failures
        for _ in range(3):
            resp = self.client.post(
                "/api/auth/login/",
                data={"username": "rick", "password": "wrong"},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrftoken,
            )
            self.assertEqual(resp.status_code, 400)

        # Next attempt should be locked out
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "rick", "password": "correcthorse"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PASSWORD_RESET_TOKEN_TTL_MINUTES=5)
class TestPasswordResetFlow(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(username="kate", password="secret123", email="k@k.com")

    def _get_csrf(self):
        r = self.client.get("/api/auth/status/")
        return r.cookies['csrftoken'].value

    def test_request_password_reset_sends_email(self):
        csrftoken = self._get_csrf()
        resp = self.client.post(
            "/api/auth/password-reset/request/",
            data={"email": "k@k.com"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertIn("비밀번호 재설정", mail.outbox[-1].subject)

    def test_reset_password_with_token(self):
        # request a token
        csrftoken = self._get_csrf()
        self.client.post(
            "/api/auth/password-reset/request/",
            data={"email": "k@k.com"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        # extract token from db
        from authentication.models import PasswordResetToken
        prt = PasswordResetToken.objects.filter(user=self.user, used=False).latest('created_at')

        # reset password
        csrftoken = self._get_csrf()
        resp = self.client.post(
            "/api/auth/password-reset/confirm/",
            data={"email": "k@k.com", "token": str(prt.token), "new_password": "newpass999"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 200)

        # ensure login with new password works
        csrftoken = self._get_csrf()
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "kate", "password": "newpass999"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 200)
        # ensure response payload includes user object
        data = resp.json()
        self.assertIn("user", data)

    # remember-me suite focuses only on session expiry behavior

# Create your tests here.
