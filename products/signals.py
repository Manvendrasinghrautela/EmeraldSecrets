from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Product, Review
from .models import Newsletter

# Send notification for new product
@receiver(post_save, sender=Product)
def notify_new_product(sender, instance, created, **kwargs):
    if created:
        # Get all newsletter subscribers
        subscribers = Newsletter.objects.filter(is_active=True)
        
        for subscriber in subscribers:
            try:
                subject = f'New Product: {instance.name}'
                email_template = 'emails/new_product_notification.html'
                
                html_message = render_to_string(email_template, {
                    'product': instance,
                    'subscriber': subscriber
                })
                
                send_mail(
                    subject=subject,
                    message=f'New product available: {instance.name}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscriber.email],
                    html_message=html_message,
                    fail_silently=True
                )
            except Exception as e:
                print(f"Error sending product notification: {str(e)}")


# Update product rating when review is added
@receiver(post_save, sender=Review)
def update_product_rating(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        
        # Calculate average rating
        reviews = Review.objects.filter(product=product)
        if reviews.exists():
            avg_rating = sum([r.rating for r in reviews]) / reviews.count()
            product.rating = avg_rating
            product.save(update_fields=['rating'])
