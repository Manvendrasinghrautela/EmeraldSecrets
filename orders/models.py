"""
Orders App Models - Updated with Email Notification
Cart, Orders, Order Items, Payments
"""

from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from accounts.models import Address
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import uuid
from decimal import Decimal


class Cart(models.Model):
    """Shopping Cart"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ordercart', null=True, blank=True)
    session_key = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"Cart - {self.user.username}"
        return f"Cart - Session {self.session_key}"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.orderitems.all())

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.orderitems.all())

    @property
    def shipping(self):
        # Example shipping logic: free shipping for subtotal >= 500
        return Decimal("50") if self.subtotal < Decimal("500") and self.subtotal > 0 else Decimal("0")

    @property
    def tax(self):
        # Example tax rate: 6.65%
        return self.subtotal * Decimal("0.0665") if self.subtotal > 0 else Decimal("0")

    @property
    def total(self):
        return self.subtotal + self.shipping + self.tax


class CartItem(models.Model):
    """Cart Items"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='orderitems')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_cartitems')
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cart', 'product']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def total_price(self):
        return self.product.price * self.quantity


class Order(models.Model):
    """Customer Orders"""
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    # Order identification
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='orders')
    
    # Order details
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Shipping information
    shipping_first_name = models.CharField(max_length=100)
    shipping_last_name = models.CharField(max_length=100)
    shipping_phone = models.CharField(max_length=15)
    shipping_email = models.EmailField()
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=10)
    shipping_country = models.CharField(max_length=100)
    
    # Payment information
    payment_method = models.CharField(max_length=50, blank=True)
    payment_id = models.CharField(max_length=255, blank=True)
    
    # Affiliate tracking
    affiliate_code = models.CharField(max_length=50, blank=True, null=True)
    
    # Additional notes
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    def generate_order_number(self):
        """Generate unique order number"""
        import random
        import string
        return ''.join(random.choices(string.digits, k=6))

    def __str__(self):
        return f"Order #{self.order_number}"

    @property
    def shipping_address(self):
        """Return formatted shipping address"""
        return f"{self.shipping_address_line1}, {self.shipping_city}, {self.shipping_state} {self.shipping_postal_code}"

    def send_order_confirmation_email(self):
        """Send order confirmation email to customer"""
        if not settings.SEND_NOTIFICATION_EMAILS:
            return
        
        try:
            subject = f'Order Confirmation - {self.order_number}'
            
            context = {
                'order': self,
                'order_items': self.items.all(),
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
            }
            
            message = render_to_string('emails/order_confirmation.html', context)
            
            send_mail(
                subject=subject,
                message=f'Your order {self.order_number} has been received.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.shipping_email],
                html_message=message,
                fail_silently=True,
            )
            
            # Send notification to admin
            self.send_admin_order_notification()
        except Exception as e:
            print(f"Error sending order confirmation email: {str(e)}")

    def send_admin_order_notification(self):
        """Notify admin about new order"""
        try:
            subject = f'New Order - {self.order_number}'
            
            items_text = "\n".join([
                f"- {item.product_name} x {item.quantity}: ₹{item.total_price}"
                for item in self.items.all()
            ])
            
            message = f"""
            A new order has been placed.
            
            Order Number: {self.order_number}
            Customer: {self.shipping_first_name} {self.shipping_last_name}
            Email: {self.shipping_email}
            Phone: {self.shipping_phone}
            
            Items:
            {items_text}
            
            Total: ₹{self.total}
            
            Shipping Address:
            {self.shipping_address}
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending admin order notification: {str(e)}")


class OrderItem(models.Model):
    """Items in an Order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def total_price(self):
        """Calculate total price, handling None values"""
        if self.price is None or self.quantity is None:
            return Decimal('0.00')
        return self.price * self.quantity


class Payment(models.Model):
    """Payment Records"""
    PAYMENT_METHOD = [
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('cod', 'Cash on Delivery'),
    ]

    PAYMENT_STATUS = [
        ('initiated', 'Initiated'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='initiated')
    
    # Payment gateway details
    transaction_id = models.CharField(max_length=255, blank=True)
    payment_gateway = models.CharField(max_length=50, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Payment for Order #{self.order.order_number}"


class Coupon(models.Model):
    """Discount Coupons"""
    DISCOUNT_TYPE = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(blank=True, null=True)
    uses_count = models.PositiveIntegerField(default=0)
    
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_to:
            return False
        if self.max_uses and self.uses_count >= self.max_uses:
            return False
        return True
