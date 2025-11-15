from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Order
from affiliate.models import AffiliateOrder

# Send order confirmation email
@receiver(post_save, sender=Order)
def send_order_confirmation(sender, instance, created, **kwargs):
    if created:
        try:
            subject = f'Order Confirmation - #{instance.order_number}'
            email_template = 'emails/order_confirmation.html'
            
            html_message = render_to_string(email_template, {
                'order': instance,
                'order_tracking_url': f"{settings.SITE_URL}/orders/{instance.id}/track/",
                'review_url': f"{settings.SITE_URL}/orders/{instance.id}/review/"
            })
            
            send_mail(
                subject=subject,
                message=f'Thank you for your order #{instance.order_number}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.user.email],
                html_message=html_message,
                fail_silently=True
            )
            
            # Send admin notification
            send_admin_order_notification(instance)
            
        except Exception as e:
            print(f"Error sending order confirmation: {str(e)}")


# Send admin notification
def send_admin_order_notification(order):
    try:
        subject = f'New Order Received - #{order.order_number}'
        
        # Build shipping address string
        shipping_address = f"""
{order.shipping_address_line1}
{order.shipping_address_line2 if order.shipping_address_line2 else ''}
{order.shipping_city}, {order.shipping_state} {order.shipping_postal_code}
{order.shipping_country}
Phone: {order.shipping_phone}
Email: {order.shipping_email}
        """.strip()
        
        message = f"""
New order received!

Order #: {order.order_number}
Customer: {order.shipping_first_name} {order.shipping_last_name}
Email: {order.shipping_email}
Phone: {order.shipping_phone}
Total: ₹{order.total}
Status: {order.get_status_display()}

Shipping Address:
{shipping_address}
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True
        )
    except Exception as e:
        print(f"Error sending admin notification: {str(e)}")


# Create affiliate commission on order
@receiver(post_save, sender=Order)
def create_affiliate_commission(sender, instance, created, **kwargs):
    """Create affiliate commission if order has affiliate_code"""
    # Note: Affiliate tracking is already handled in checkout view
    # This signal is kept for backward compatibility but should not duplicate tracking
    if created and instance.affiliate_code:
        try:
            from affiliate.models import AffiliateUser
            affiliate = AffiliateUser.objects.get(
                affiliate_code=instance.affiliate_code,
                status='active'
            )
            
            # Check if affiliate order already exists (created in checkout view)
            from affiliate.models import AffiliateOrder
            if not AffiliateOrder.objects.filter(order=instance).exists():
                # Only create if not already created in checkout view
                program = affiliate.program
                commission_amount = instance.total * (program.commission_rate / 100)
                
                AffiliateOrder.objects.create(
                    affiliate=affiliate,
                    order=instance,
                    order_amount=instance.total,
                    commission_rate=program.commission_rate,
                    commission_amount=commission_amount,
                    status='pending'
                )
        except Exception as e:
            print(f"Error creating affiliate commission: {str(e)}")

@receiver(post_save, sender=Order)
def update_affiliate_commission(sender, instance, **kwargs):
    """Update affiliate order status when main order status changes"""
    if instance.affiliate_code:
        try:
            affiliate_order = AffiliateOrder.objects.get(order=instance)
            
            # Update status based on order status
            if instance.status == 'delivered':
                affiliate_order.status = 'confirmed'
            elif instance.status == 'cancelled':
                affiliate_order.status = 'cancelled'
            
            affiliate_order.save()
        except AffiliateOrder.DoesNotExist:
            pass