# affiliate/urls.py
from django.urls import path
from . import views

app_name = 'affiliate'

urlpatterns = [
    # Public pages
    path('', views.affiliate_home, name='home'),
    path('join/', views.affiliate_join, name='join'),
    path('track/<str:affiliate_code>/', views.track_affiliate_click, name='track'),
    path('register/', views.affiliate_register, name='register'),

    # Affiliate dashboard (login required)
    path('dashboard/', views.affiliate_dashboard, name='dashboard'),
    path('profile/', views.affiliate_profile, name='profile'),
    path('stats/', views.affiliate_stats, name='stats'),
    
    # Links and banners
    path('links/', views.affiliate_links, name='links'),
    
    # Withdrawals
    path('withdrawals/', views.affiliate_withdrawals, name='withdrawals'),
    path('withdrawals/request/', views.request_withdrawal, name='request_withdrawal'),
    
    # Settings
    path('settings/', views.affiliate_settings, name='settings'),
]