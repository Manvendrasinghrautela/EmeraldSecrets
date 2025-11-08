from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Order
from affiliate.models import AffiliateCommission, AffiliateOrder

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
        message = f"""
        New order received!
        
        Order #: {order.order_number}
        Customer: {order.user.first_name} {order.user.last_name}
        Email: {order.user.email}
        Total: ₹{order.total}
        Status: {order.get_status_display()}
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
    if created and instance.affiliate:
        try:
            commission_amount = instance.total * (instance.affiliate.program.commission_rate / 100)
            
            AffiliateCommission.objects.create(
                affiliate=instance.affiliate,
                order=instance,
                order_amount=instance.total,
                commission_rate=instance.affiliate.program.commission_rate,
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