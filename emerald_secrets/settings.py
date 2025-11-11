"""
Django settings for emerald_secrets project.
Updated with email notifications configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-this')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,43.220.4.22,emeraldsecrets.com,www.emeraldsecrets.com').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap4',
    
    # Local apps
    'accounts.apps.AccountsConfig',
    'products.apps.ProductsConfig',
    'orders.apps.OrdersConfig',
    'affiliate.apps.AffiliateConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'affiliate.middleware.AffiliateTrackingMiddleware',
]

ROOT_URLCONF = 'emerald_secrets.urls'

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
                'django.template.context_processors.media',
                'products.context_processors.cart_context',

            ],
        },
    },
]

WSGI_APPLICATION = 'emerald_secrets.wsgi.application'

# Database - MySQL Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('MYSQL_DATABASE', 'emeraldsecrets'),
        'USER': os.getenv('MYSQL_USER', 'emerald_user'),
        'PASSWORD': os.getenv('MYSQL_PASSWORD', 'Kulsm19cphantom@'),
        'HOST': os.getenv('MYSQL_HOST', 'localhost'),
        'PORT': os.getenv('MYSQL_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Security (add these)
SECURE_SSL_REDIRECT = False  # Set True if using HTTPS
SESSION_COOKIE_SECURE = False  # Set True if using HTTPS
CSRF_COOKIE_SECURE = False  # Set True if using HTTPS

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'products:home'
LOGOUT_REDIRECT_URL = 'products:home'

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# ============================================================================
# EMAIL CONFIGURATION FOR NOTIFICATIONS
# ============================================================================

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'emeraldsecrets24@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'tkgt xhfb dqyc xjbk')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'emeraldsecrets24@gmail.com')

# Company email for notifications (where orders, signups, and contacts are sent)
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'emeraldsecrets24@gmail.com')
COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', 'emeraldsecrets24@gmail.com')

# Email notification settings
SEND_NOTIFICATION_EMAILS = os.getenv('SEND_NOTIFICATION_EMAILS', 'True') == 'True'

# ============================================================================
# PAYMENT GATEWAY CONFIGURATION (Razorpay example)
# ============================================================================

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')

# ============================================================================
# AFFILIATE PROGRAM SETTINGS
# ============================================================================

AFFILIATE_COMMISSION_RATE = float(os.getenv('AFFILIATE_COMMISSION_RATE', '0.20'))
AFFILIATE_COOKIE_DURATION = int(os.getenv('AFFILIATE_COOKIE_DURATION', '30'))

# ============================================================================
# SITE CONFIGURATION
# ============================================================================

SITE_NAME = os.getenv('SITE_NAME', 'Emerald Secrets')
SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000')

# ============================================================================
# SECURITY SETTINGS (for production)
# ============================================================================

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ============================================================================
# SESSION CONFIGURATION
# ============================================================================

SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True

# ============================================================================
# CART CONFIGURATION
# ============================================================================

CART_SESSION_ID = 'cart'

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'emerald_secrets.log',
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)