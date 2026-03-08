import os
from datetime import timedelta
from pathlib import Path
from corsheaders.defaults import default_headers


from dotenv import load_dotenv
load_dotenv()


# --------------------------
# BASE
# --------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

API = os.environ.get("START_API_URL")
DEPLOY_TOKEN=os.environ.get("DEPLOY_TOKEN")
SECRET_KEY = os.environ.get("SECRET_KEY")
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'django_saas.User'
DEBUG = int(os.environ.get("DEBUG", default=0))
TIME_ZONE = os.environ.get("TIME_ZONE")
LANGUAGE_CODE = 'EN-US'

# --------------------------
# URLs e Hosts
# --------------------------

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")
CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOW_HEADERS = list(default_headers) + os.environ.get("CORS_ALLOW_HEADERS", "").split(",")
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ORIGIN_WHITELIST = CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")


# --------------------------
# Aplicações
# --------------------------

MY_APPS = [
    'django_saas',
]


    
INSTALLED_APPS = MY_APPS + [

    'djmoney',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',  # CORS

    # DRF
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework.authtoken',  # só para validação de permissão
]

# --------------------------
# Middleware
# --------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',


    'django_saas.core.middleware.file_access.FileAccessMiddleware',
    # 'django_saas.core.middleware.frontend.FrontEndMiddleware',
    'django_saas.core.middleware.tenant.TenantContextMiddleware',

]




ROOT_URLCONF = 'saas.urls'

# ASGI_APPLICATION = "mytech.asgi.application"
WSGI_APPLICATION = 'saas.wsgi.application'

# --------------------------
# Templates
# --------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

# --------------------------
# Banco de dados
# --------------------------
DATABASES = {
    "default": {
        "ENGINE": 'django.db.backends.' + str(os.environ.get("SQL_ENGINE", "sqlite3")),
        "NAME": os.environ.get("SQL_DATABASE", BASE_DIR / "db.sqlite3"),
        "USER": os.environ.get("SQL_USER", "user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
    }
}


DJANGO_REST_AUTH = {
    'FILE_TOKEN': {
        'KEY': os.environ.get('URL_FILE_KEY'),
        'ENABLE_TEMPORARY': True,
        'TEMP_TTL': 300,
        'ENABLE_PERMANENT': True,
    },
    'CACHE_TIME': os.environ.get('DJANGO_REST_AUTH_CACHE_TIME'),
    'FRONT_END': {
        'REQUIRE_CREDENTIALS':os.environ.get('DJANGO_REST_AUTH_REQUIRE_FRONT_END_CREDENTIALS'),
        'PUBLIC_URL': ['public'],
        'URL_RULES': {
            'admin': ['write'],
            'private': ['readwrite', 'write'],
            'public': ['read', 'readwrite', 'write'],
        }
    },
    'EMAIL_TEMPLATES': {
        'REGISTER_CONFIRM': 'emails/meu_confirmacao.html',
        'PASSWORD_RESET': 'emails/meu_reset.html',
        'GENERIC_RESET': 'emails/meu_generico.html',
    }
}

# --------------------------
# DRF e JWT
# --------------------------


REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PERMISSION_CLASSES': (),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'NON_FIELD_ERRORS_KEY': 'error',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    )
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

# --------------------------
# Password validation
# --------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --------------------------
# Internacionalização e Timezone
# --------------------------
USE_I18N = True
USE_TZ = True

# --------------------------
# Static & Media
# --------------------------
STATIC_URL = "/" + os.environ.get("STATIC_URL", "static") + "/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/" + os.environ.get("MEDIA_URL", "media") + "/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

DEPLOY_FILE_PATH = BASE_DIR / "deploy.sh"



# --------------------------
# Email
# --------------------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND")
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = 465 if os.environ.get("EMAIL_USE_SSL") else 587
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", False)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

