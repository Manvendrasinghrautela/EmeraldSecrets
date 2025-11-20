from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('callback/', views.payment_callback, name='payment_callback'),
]
