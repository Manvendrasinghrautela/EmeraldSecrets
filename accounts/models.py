"""
Accounts App Models - Updated with Email Notification
User Profile, Addresses, Settings
"""

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


class UserProfile(models.Model):
    """Extended User Profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Preferences
    receive_promotional_emails = models.BooleanField(default=True)
    receive_order_updates = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username


class Address(models.Model):
    """User Shipping/Billing Addresses"""
    ADDRESS_TYPES = [
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
        ('both', 'Both'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='both')
    
    # Address fields
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    
    # Status
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.city}"

    def save(self, *args, **kwargs):
        # If this address is set as default, unset other default addresses
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class AccountSettings(models.Model):
    """User Account Settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    
    # Notification Preferences
    email_on_order = models.BooleanField(default=True)
    email_on_shipment = models.BooleanField(default=True)
    email_on_delivery = models.BooleanField(default=True)
    email_promotions = models.BooleanField(default=True)
    
    # Privacy Settings
    show_profile_publicly = models.BooleanField(default=False)
    show_reviews_publicly = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Account Settings'

    def __str__(self):
        return f"{self.user.username}'s Settings"


# ============================================================================
# SIGNALS - Keep at the end of file
# ============================================================================

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=User)
def create_account_settings(sender, instance, created, **kwargs):
    """Create AccountSettings when a new User is created"""
    if created:
        AccountSettings.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def send_user_signup_email(sender, instance, created, **kwargs):
    """
    Send email notification when a new user signs up
    """
    if created and getattr(settings, 'SEND_NOTIFICATION_EMAILS', False):
        # Send welcome email to user
        send_welcome_email_to_user(instance)
        
        # Send notification to admin
        send_signup_notification_to_admin(instance)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def send_welcome_email_to_user(user):
    """Send welcome email to newly registered user"""
    try:
        subject = f'Welcome to {settings.SITE_NAME}!'
        
        context = {
            'user_name': user.first_name or user.username,
            'site_name': settings.SITE_NAME,
            'site_url': getattr(settings, 'SITE_URL', ''),
        }
        
        # Try to use HTML template, fallback to plain text
        try:
            message_html = render_to_string('emails/welcome.html', context)
        except:
            message_html = None
        
        message_plain = f"""
        Hi {user.first_name or user.username},
        
        Thank you for registering with {settings.SITE_NAME}!
        
        We're excited to have you as part of our community. You can now browse our products,
        make purchases, and enjoy exclusive benefits.
        
        Best regards,
        {settings.SITE_NAME} Team
        """
        
        send_mail(
            subject=subject,
            message=message_plain,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=message_html,
            fail_silently=True,
        )
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")


def send_signup_notification_to_admin(user):
    """Notify admin about new user signup"""
    try:
        admin_email = getattr(settings, 'ADMIN_EMAIL', None)
        if not admin_email:
            return
            
        subject = f'New User Signup - {user.username}'
        
        message = f"""
        A new user has registered on {settings.SITE_NAME}.
        
        Username: {user.username}
        Email: {user.email}
        First Name: {user.first_name}
        Last Name: {user.last_name}
        Joined: {user.date_joined}
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Error sending admin signup notification: {str(e)}")
