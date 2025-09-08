import os

# Choose settings flavor based on environment, default to development
mode = os.getenv('DJANGO_MODE', os.getenv('DJANGO_ENV', 'development')).lower()
if mode == 'production':
    from .prod import *  # noqa
else:
    from .dev import *  # noqa

