import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


DEBUG = True




INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    #'crispy_forms',
    #'crispy_bootstrap',

    # Local apps
    'core',
    'clashroyale',
    'tournament'

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

]

ROOT_URLCONF = 'gaming_hub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gaming_hub.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

#STATIC_URL
STATIC_URL = '/static/'

# Media files

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Add to STATICFILES_DIRS if not exists
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]


# Login URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# For testing (emails print to console):
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# OPTION C: Gmail (real emails)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'gaminghubworld2026@gmail.com'
EMAIL_HOST_PASSWORD = 'ofrt bliv xvpa nccq'  # Google App Password
DEFAULT_FROM_EMAIL = 'Gaming Hub <gaminghubworld2026@gmail.com>'


BASE_DIR = Path(__file__).resolve().parent.parent

# For PythonAnywhere - Simple static setup
# Static files settings
STATIC_URL = '/static/'

# Where collectstatic puts ALL files (creates if doesn't exist)
STATIC_ROOT = BASE_DIR / 'staticfiles'  # ← DIFFERENT from 'static'

# Where YOUR source static files are
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # ← Your custom static folder
]


# For production on PythonAnywhere
if os.environ.get('PYTHONANYWHERE_DOMAIN'):
    DEBUG = False
    ALLOWED_HOSTS = ['gaminghubcompany.pythonanywhere.com']
else:
    # Local development
    DEBUG = True
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']



load_dotenv()

# Clash Royale API Settings
CLASH_ROYALE_API_KEY = os.getenv('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjkwMTRkOGEzLWMxNWYtNGRlOC05ZWY1LTYyOGMxMTM1N2NjZCIsImlhdCI6MTc2NzQ3ODU1MSwic3ViIjoiZGV2ZWxvcGVyLzEzN2JkNjFlLTBiZjAtMDI1OC00NzBhLWQ1Zjg5MTAyYWZhZCIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxMDIuODkuODMuNTUiXSwidHlwZSI6ImNsaWVudCJ9XX0.-fQaAcyzysO9HhlDcyDNSQZ5vxOiE62AxiKrI4ItV_J1kJ3iS2b_5OFhMp73HlUwN3jwPwIU1H6Q5mEVCquJkw', '')
CLASH_ROYALE_API_URL = 'https://api.clashroyale.com/v1'
USE_MOCK_DATA = os.getenv('USE_MOCK_DATA', 'True').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', '6r&ee%c8n4tnq+obtd05gb)m&!+hj8=$d2-yo@w_(*5_=k!^55')
# Cache settings (add if not present)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}


# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')
SITE_NAME = "Gaming Hub"