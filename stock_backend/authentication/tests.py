from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone


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

    # remember-me suite focuses only on session expiry behavior

# Create your tests here.
