from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

app_name = 'authentication'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', csrf_exempt(views.user_logout), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('status/', views.auth_status, name='auth_status'),
    path('check-username/', views.check_username, name='check_username'),
    path('password-reset/request/', views.request_password_reset, name='request_password_reset'),
    path('password-reset/confirm/', views.reset_password, name='reset_password'),
] 