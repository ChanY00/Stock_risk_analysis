from django.test import TestCase, Client
from django.contrib.auth.models import User


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

# Create your tests here.
