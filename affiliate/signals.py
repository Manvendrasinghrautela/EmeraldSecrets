from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import AffiliateApplication, AffiliateWithdrawal

# Send affiliate application confirmation
@receiver(post_save, sender=AffiliateApplication)
def send_affiliate_application_confirmation(sender, instance, created, **kwargs):
    if created:
        try:
            subject = 'Affiliate Application Received'
            email_template = 'emails/affiliate_application.html'
            
            html_message = render_to_string(email_template, {
                'affiliate': instance,
                'dashboard_url': f"{settings.SITE_URL}/affiliate/dashboard/"
            })
            
            send_mail(
                subject=subject,
                message='Thank you for your affiliate application',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.user.email],
                html_message=html_message,
                fail_silently=True
            )
            
            # Send admin notification
            send_affiliate_admin_notification(instance)
            
        except Exception as e:
            print(f"Error sending affiliate application: {str(e)}")


# Send admin notification
def send_affiliate_admin_notification(affiliate):
    try:
        subject = f'New Affiliate Application - {affiliate.user.email}'
        message = f"""
        New affiliate application received!
        
        User: {affiliate.user.first_name} {affiliate.user.last_name}
        Email: {affiliate.user.email}
        Program: {affiliate.program.name}
        Why: {affiliate.why}
        
        Review in admin: {settings.SITE_URL}/admin/
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


# Send withdrawal confirmation
@receiver(post_save, sender=AffiliateWithdrawal)
def send_withdrawal_confirmation(sender, instance, created, **kwargs):
    if created:
        try:
            subject = 'Withdrawal Request Received'
            email_template = 'emails/affiliate_withdrawal.html'
            
            html_message = render_to_string(email_template, {
                'withdrawal': instance,
                'tracking_url': f"{settings.SITE_URL}/affiliate/withdrawals/"
            })
            
            send_mail(
                subject=subject,
                message=f'Your withdrawal request for ₹{instance.amount} has been received',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.affiliate.user.email],
                html_message=html_message,
                fail_silently=True
            )
            
        except Exception as e:
            print(f"Error sending withdrawal confirmation: {str(e)}")


# Send withdrawal status update
@receiver(post_save, sender=AffiliateWithdrawal)
def send_withdrawal_status_update(sender, instance, **kwargs):
    if instance.status == 'approved' and instance.approved_at:
        try:
            subject = 'Withdrawal Approved'
            message = f"""
            Your withdrawal of ₹{instance.amount} has been approved!
            
            Amount: ₹{instance.amount}
            Status: {instance.get_status_display()}
            
            The amount will be transferred to your bank account shortly.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.affiliate.user.email],
                fail_silently=True
            )
            
        except Exception as e:
            print(f"Error sending withdrawal update: {str(e)}")
    
    elif instance.status == 'rejected' and instance.rejected_at:
        try:
            subject = 'Withdrawal Rejected'
            message = f"""
            Your withdrawal request of ₹{instance.amount} has been rejected.
            
            Reason: {instance.rejection_reason}
            
            Please contact support for more information.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.affiliate.user.email],
                fail_silently=True
            )
            
        except Exception as e:
            print(f"Error sending rejection email: {str(e)}")
