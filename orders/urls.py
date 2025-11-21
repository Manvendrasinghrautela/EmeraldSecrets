# orders/urls.py
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Cart URLs
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:product_id>/', views.update_cart_item, name='update_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/count/', views.cart_count, name='cart_count'),

    # Coupon URLs
    path('coupon/apply/', views.apply_coupon, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon, name='remove_coupon'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart_ajax, name='add_to_cart_ajax'),

    path('checkout/', views.checkout, name='checkout'),
    path('create/', views.create_order, name='create_order'),
    path('shipping-quote/', views.shipping_quote, name='shipping_quote'),
    path('payment/<int:order_id>/', views.payment_page, name='payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('success/<int:order_id>/', views.order_success, name='order_success'),
    path('failure/', views.order_failure, name='order_failure'),
    path('failure/<int:order_id>/', views.order_failure, name='order_failure_with_order'),
    path('invoice/<int:order_id>/', views.download_invoice, name='download_invoice'),

    
    # Order URLs
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<int:order_id>/invoice/', views.download_invoice, name='download_invoice'),
    
    # Payment URLs
    path('orders/<int:order_id>/payment-status/', views.payment_status, name='payment_status'),
]