"""
Celery configuration for Django project
"""
import os
from celery import Celery
from django.conf import settings

# Django settings 모듈 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings.dev')

app = Celery('stock_backend')

# Django settings에서 Celery 설정 자동 로드
# CELERY_로 시작하는 모든 설정을 로드
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django 앱에서 tasks.py 파일을 자동으로 발견
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Celery 디버깅용 태스크"""
    print(f'Request: {self.request!r}')


