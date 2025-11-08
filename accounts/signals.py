"""
Accounts App Signals
Handle user profile and settings creation
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import UserProfile, AccountSettings


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


def send_welcome_email_to_user(user):
    """Send welcome email to newly registered user"""
    try:
        subject = f'Welcome to {getattr(settings, "SITE_NAME", "Emerald Secrets")}!'
        
        context = {
            'user_name': user.first_name or user.username,
            'site_name': getattr(settings, 'SITE_NAME', 'Emerald Secrets'),
            'site_url': getattr(settings, 'SITE_URL', ''),
        }
        
        # Try to use HTML template, fallback to plain text
        try:
            message_html = render_to_string('emails/welcome.html', context)
        except Exception as e:
            print(f"Error loading template: {e}")
            message_html = None
        
        message_plain = f"""
Hi {user.first_name or user.username},

Thank you for registering with {getattr(settings, 'SITE_NAME', 'Emerald Secrets')}!

We're excited to have you as part of our community. You can now browse our products,
make purchases, and enjoy exclusive benefits.

Best regards,
{getattr(settings, 'SITE_NAME', 'Emerald Secrets')} Team
        """
        
        send_mail(
            subject=subject,
            message=message_plain,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
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
A new user has registered on {getattr(settings, 'SITE_NAME', 'Emerald Secrets')}.

Username: {user.username}
Email: {user.email}
First Name: {user.first_name}
Last Name: {user.last_name}
Joined: {user.date_joined}
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Error sending admin signup notification: {str(e)}")
