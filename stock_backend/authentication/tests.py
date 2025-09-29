from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.test.utils import override_settings
from django.core.cache import cache


class TestAuthStatusCsrfCookie(TestCase):
    def setUp(self):
        self.client = Client()

    def test_auth_status_sets_csrf_cookie(self):
        response = self.client.get("/api/auth/status/")
        self.assertIn('csrftoken', response.cookies)


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
        self.assertIn("제한", resp.json().get("non_field_errors", [""])[0])

    def test_success_resets_failure_counters(self):
        csrftoken = self._get_csrf()
        # one failure
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "rick", "password": "wrong"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 400)

        # success should clear counters
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "rick", "password": "correcthorse"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 200)

        # After login, session may rotate, requiring a fresh CSRF token
        csrftoken = self._get_csrf()

        # another failure should be counted from 1 again (not directly observable here,
        # but at least ensure no lockout after single new failure)
        resp = self.client.post(
            "/api/auth/login/",
            data={"username": "rick", "password": "wrong"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(resp.status_code, 400)

    # remember-me suite focuses only on session expiry behavior

# Create your tests here.
