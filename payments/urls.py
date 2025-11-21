# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('callback/', views.payment_callback, name='payment_callback'),
    path('success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('failure/', views.payment_failure, name='payment_failure'),
    path('failure/<int:order_id>/', views.payment_failure, name='payment_failure_with_order'),
    path('invoice/<int:order_id>/', views.download_invoice, name='download_invoice'),
]
