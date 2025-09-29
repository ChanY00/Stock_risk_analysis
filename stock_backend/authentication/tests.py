from django.test import TestCase, Client


class TestAuthStatusCsrfCookie(TestCase):
    def setUp(self):
        self.client = Client()

    def test_auth_status_sets_csrf_cookie(self):
        response = self.client.get("/api/auth/status/")
        # Django test client exposes cookies directly on the response
        self.assertIn('csrftoken', response.cookies)

# Create your tests here.
