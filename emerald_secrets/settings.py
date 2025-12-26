import os
from decimal import Decimal
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
    'affiliate.middleware.AffiliateTrackingMiddleware',  # ✅ Affiliate tracking
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


# ============================================================================
# DATABASE - MySQL Configuration
# ============================================================================

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


# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

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


# ============================================================================
# INTERNATIONALIZATION
# ============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# ============================================================================
# STATIC & MEDIA FILES
# ============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ============================================================================
# AUTHENTICATION SETTINGS
# ============================================================================

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'products:home'
LOGOUT_REDIRECT_URL = 'products:home'


# ============================================================================
# CRISPY FORMS CONFIGURATION
# ============================================================================

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

# Company email for notifications
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'emeraldsecrets24@gmail.com')
COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', 'emeraldsecrets24@gmail.com')

# Email notification settings
SEND_NOTIFICATION_EMAILS = os.getenv('SEND_NOTIFICATION_EMAILS', 'True') == 'True'


# ============================================================================
# PAYMENT GATEWAY CONFIGURATION (Razorpay)
# ============================================================================

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_live_Ri4CMN9v4I2234')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'BUFxIIS3Lgtr00EZuB3VJ043')


# ============================================================================
# TAX & SHIPPING CONFIGURATION
# ============================================================================

GST_RATE = Decimal(os.getenv('GST_RATE', '0.18'))

DELHIVERY_API_KEY = os.getenv('DELHIVERY_API_KEY', '84fcd5ad3412a8acba8d3013ec09f54c648333d1')
DELHIVERY_RATE_URL = os.getenv('DELHIVERY_RATE_URL', 'https://track.delhivery.com/api/kinko/v1/invoice/charges/.json')
DELHIVERY_ORIGIN_PINCODE = os.getenv('DELHIVERY_ORIGIN_PINCODE', '110001')
DELHIVERY_DEFAULT_ITEM_WEIGHT_G = Decimal(os.getenv('DELHIVERY_DEFAULT_ITEM_WEIGHT_G', '250'))
DELHIVERY_MIN_WEIGHT_G = Decimal(os.getenv('DELHIVERY_MIN_WEIGHT_G', '150'))
DELHIVERY_FALLBACK_CHARGE = Decimal(os.getenv('DELHIVERY_FALLBACK_CHARGE', '65'))
DELHIVERY_REQUEST_TIMEOUT = int(os.getenv('DELHIVERY_REQUEST_TIMEOUT', '10'))


# ============================================================================
# AFFILIATE PROGRAM SETTINGS - ✅ UPDATED TO 5%
# ============================================================================

# ✅ AFFILIATE COMMISSION: Changed from 2% to 5%
AFFILIATE_COMMISSION_RATE = float(os.getenv('AFFILIATE_COMMISSION_RATE', '5.00'))  # ✅ 5% commission

# Cookie duration for tracking affiliate referrals
AFFILIATE_COOKIE_DURATION = int(os.getenv('AFFILIATE_COOKIE_DURATION', '30'))  # 30 days

# Affiliate configuration dictionary
AFFILIATE_CONFIG = {
    'commission_rate': Decimal('5.00'),  # ✅ 5% commission per order
    'min_withdrawal': Decimal('1000.00'),  # ₹1000 minimum withdrawal
    'cookie_duration': 30,  # 30 days cookie expiry
    'auto_approval_days': 7,  # Auto-approve orders after 7 days
    'payment_methods': ['bank', 'upi', 'paypal'],  # Supported payment methods
}

# Affiliate email notifications
AFFILIATE_EMAIL_NOTIFICATIONS = {
    'send_approval': True,
    'send_rejection': True,
    'send_suspension': True,
    'send_withdrawal_approved': True,
    'send_withdrawal_paid': True,
    'send_commission_earned': True,
}


# ============================================================================
# SITE CONFIGURATION
# ============================================================================

SITE_NAME = os.getenv('SITE_NAME', 'Emerald Secrets')
SITE_URL = os.getenv('SITE_URL', 'https://emeraldsecrets.com')


# ============================================================================
# SECURITY SETTINGS
# ============================================================================

SECURE_SSL_REDIRECT = False  # Set True if using HTTPS
SESSION_COOKIE_SECURE = False  # Set True if using HTTPS
CSRF_COOKIE_SECURE = False  # Set True if using HTTPS

# Production security settings
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
        'affiliate_file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'affiliate.log',
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
        'affiliate': {
            'handlers': ['console', 'affiliate_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ============================================================================
# GOOGLE ANALYTICS
# ============================================================================

GOOGLE_ANALYTICS_ID = "G-0H01XYS1K5"


# ============================================================================
# CREATE LOGS DIRECTORY
# ============================================================================

LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)