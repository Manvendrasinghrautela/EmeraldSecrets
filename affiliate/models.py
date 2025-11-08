# affiliate/models.py - Complete Affiliate Program Models
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
import uuid


# ============================================================================
# AFFILIATE PROGRAM CONFIGURATION
# ============================================================================

class AffiliateProgram(models.Model):
    """Main Affiliate Program Configuration"""
    name = models.CharField(max_length=200, default='Emerald Secrets Affiliate Program')
    description = models.TextField(blank=True)
    
    # Commission Settings - YOUR REQUIREMENT: 2% commission
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.00)  # 2%
    
    # Withdrawal Settings - YOUR REQUIREMENT: ₹1000 minimum
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)  # ₹1000
    
    # Cookie/Tracking Settings
    cookie_duration = models.IntegerField(default=30)  # 30 days cookie
    
    # Terms & Conditions
    terms_and_conditions = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Affiliate Program'
        verbose_name_plural = 'Affiliate Programs'


# ============================================================================
# AFFILIATE USER - Person who joins the program
# ============================================================================

class AffiliateUser(models.Model):
    """Affiliate Program Member - YOUR REQUIREMENT: Track users who join"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]

    # User & Program Link
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate')
    program = models.ForeignKey(AffiliateProgram, on_delete=models.CASCADE, related_name='members')
    
    # YOUR REQUIREMENT: Unique affiliate code (for referral link)
    affiliate_code = models.CharField(max_length=50, unique=True, editable=False)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Bank/Payment Details for Withdrawal
    bank_name = models.CharField(max_length=100, blank=True)
    account_holder = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    
    # YOUR REQUIREMENT: Track all statistics
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Total earned
    total_withdrawn = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Total withdrawn
    total_referrals = models.IntegerField(default=0)  # Number of users referred
    
    # Dates
    joined_at = models.DateTimeField(auto_now_add=True)
    approved_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.affiliate_code}"

    class Meta:
        verbose_name = 'Affiliate User'
        verbose_name_plural = 'Affiliate Users'

    def save(self, *args, **kwargs):
        # YOUR REQUIREMENT: Auto-generate unique affiliate code
        if not self.affiliate_code:
            self.affiliate_code = f"ES-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    # YOUR REQUIREMENT: Calculate available balance
    @property
    def available_balance(self):
        """Money available for withdrawal"""
        return self.total_earnings - self.total_withdrawn

    # YOUR REQUIREMENT: Check if user can withdraw (₹1000 minimum)
    @property
    def can_withdraw(self):
        """Check if user has minimum balance to withdraw"""
        return self.available_balance >= self.program.min_withdrawal

    # YOUR REQUIREMENT: Generate referral link
    @property
    def referral_link(self):
        """Generate unique referral link"""
        return f"{settings.SITE_URL}/?ref={self.affiliate_code}"

    # Stats properties
    @property
    def total_clicks(self):
        """Total clicks on affiliate link"""
        return self.clicks.count()
    
    @property
    def total_orders(self):
        """Total orders from referrals"""
        return self.orders.filter(status__in=['confirmed', 'completed']).count()
    
    @property
    def total_sales(self):
        """Total sales amount from referrals"""
        total = self.orders.filter(
            status__in=['confirmed', 'completed']
        ).aggregate(total=models.Sum('order_amount'))['total']
        return total or Decimal('0.00')
    
    @property
    def pending_commission(self):
        """Commission not yet approved"""
        total = self.orders.filter(
            status='pending'
        ).aggregate(total=models.Sum('commission_amount'))['total']
        return total or Decimal('0.00')

    # Approval/Rejection Methods
    def approve(self):
        """Approve affiliate application"""
        self.status = 'active'
        self.approved_date = timezone.now()
        self.save()
        self.send_approval_email()

    def reject(self):
        """Reject affiliate application"""
        self.status = 'rejected'
        self.save()
        self.send_rejection_email()

    def suspend(self):
        """Suspend affiliate account"""
        self.status = 'suspended'
        self.save()
        self.send_suspension_email()

    # Email Notifications
    def send_approval_email(self):
        """Send approval email"""
        try:
            subject = 'Your Affiliate Account Has Been Approved!'
            message = f"""
Hi {self.user.first_name or self.user.username},

Great news! Your application to join the {self.program.name} has been approved.

Your Affiliate Code: {self.affiliate_code}
Your Referral Link: {self.referral_link}
Commission Rate: {self.program.commission_rate}%
Minimum Withdrawal: ₹{self.program.min_withdrawal}

You can now start promoting our products and earn commissions!

Visit your affiliate dashboard: {settings.SITE_URL}/affiliate/dashboard/

Best regards,
{settings.SITE_NAME} Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending approval email: {str(e)}")

    def send_rejection_email(self):
        """Send rejection email"""
        try:
            subject = 'Affiliate Application Status'
            message = f"""
Hi {self.user.first_name or self.user.username},

Thank you for your interest in the {self.program.name}.

Unfortunately, your application could not be approved at this time.

Please contact us for more information.

Best regards,
{settings.SITE_NAME} Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending rejection email: {str(e)}")

    def send_suspension_email(self):
        """Send suspension email"""
        try:
            subject = 'Affiliate Account Suspended'
            message = f"""
Hi {self.user.first_name or self.user.username},

We regret to inform you that your {self.program.name} account has been suspended.

Please contact us for more information.

Best regards,
{settings.SITE_NAME} Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending suspension email: {str(e)}")


# ============================================================================
# AFFILIATE CLICK - Track every click on affiliate link
# ============================================================================

class AffiliateClick(models.Model):
    """Track affiliate link clicks - YOUR REQUIREMENT: Track referral activity"""
    affiliate = models.ForeignKey(AffiliateUser, on_delete=models.CASCADE, related_name='clicks')
    
    # Visitor Information
    visitor_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer_url = models.URLField(blank=True, null=True)
    
    # Session tracking
    session_key = models.CharField(max_length=255, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Affiliate Click'
        verbose_name_plural = 'Affiliate Clicks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.affiliate.affiliate_code} - Click at {self.created_at}"


# ============================================================================
# AFFILIATE ORDER - Track orders made through affiliate links
# ============================================================================

class AffiliateOrder(models.Model):
    """Track orders from affiliates - YOUR REQUIREMENT: Track sales & commission"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),  # Order placed, commission not yet approved
        ('confirmed', 'Confirmed'),  # Order confirmed, commission approved
        ('completed', 'Completed'),  # Order delivered, commission ready for withdrawal
        ('cancelled', 'Cancelled'),  # Order cancelled, commission revoked
    ]

    # Links
    affiliate = models.ForeignKey(AffiliateUser, on_delete=models.CASCADE, related_name='orders')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, related_name='affiliate_source')
    
    # YOUR REQUIREMENT: Track order amount and 2% commission
    order_amount = models.DecimalField(max_digits=15, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Store rate at time of order
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Affiliate Order'
        verbose_name_plural = 'Affiliate Orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.affiliate.affiliate_code} - Order #{self.order.order_number if self.order else 'N/A'} - ₹{self.commission_amount}"

    def confirm(self):
        """Confirm order and approve commission"""
        if self.status == 'pending':
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save()

    def complete(self):
        """Complete order - YOUR REQUIREMENT: Add commission to earnings"""
        if self.status in ['pending', 'confirmed']:
            self.status = 'completed'
            self.completed_at = timezone.now()
            
            # YOUR REQUIREMENT: Add to affiliate earnings
            self.affiliate.total_earnings += self.commission_amount
            self.affiliate.save()
            
            # Create transaction record
            AffiliateTransaction.objects.create(
                affiliate=self.affiliate,
                transaction_type='earning',
                amount=self.commission_amount,
                description=f"Commission from Order #{self.order.order_number if self.order else 'N/A'}",
                related_order=self,
                balance_after=self.affiliate.available_balance
            )
            
            self.save()

    def cancel(self):
        """Cancel order and revoke commission"""
        if self.status == 'completed':
            # Deduct from earnings if already added
            self.affiliate.total_earnings -= self.commission_amount
            self.affiliate.save()
            
            # Create transaction record
            AffiliateTransaction.objects.create(
                affiliate=self.affiliate,
                transaction_type='deduction',
                amount=self.commission_amount,
                description=f"Commission revoked - Order #{self.order.order_number if self.order else 'N/A'} cancelled",
                related_order=self,
                balance_after=self.affiliate.available_balance
            )
        
        self.status = 'cancelled'
        self.save()


# ============================================================================
# AFFILIATE WITHDRAWAL - Track withdrawal requests
# ============================================================================

class AffiliateWithdrawal(models.Model):
    """Track affiliate withdrawals - YOUR REQUIREMENT: ₹1000 minimum"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('bank', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('paypal', 'PayPal'),
    ]

    # Links
    affiliate = models.ForeignKey(AffiliateUser, on_delete=models.CASCADE, related_name='withdrawals')
    
    # YOUR REQUIREMENT: Withdrawal amount
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Payment Method
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='bank')
    payment_details = models.TextField(blank=True)  # Bank details, UPI ID, etc.
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Affiliate Withdrawal'
        verbose_name_plural = 'Affiliate Withdrawals'
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.affiliate.user.username} - ₹{self.amount} ({self.status})"

    def approve(self):
        """Approve withdrawal request"""
        if self.status == 'pending':
            self.status = 'approved'
            self.approved_at = timezone.now()
            self.save()
            self.send_approval_email()

    def mark_paid(self):
        """Mark withdrawal as paid - YOUR REQUIREMENT: Update withdrawn amount"""
        if self.status in ['pending', 'approved', 'processing']:
            self.status = 'paid'
            self.paid_at = timezone.now()
            
            # YOUR REQUIREMENT: Update total withdrawn
            self.affiliate.total_withdrawn += self.amount
            self.affiliate.save()
            
            # Create transaction record
            AffiliateTransaction.objects.create(
                affiliate=self.affiliate,
                transaction_type='withdrawal',
                amount=self.amount,
                description=f"Withdrawal via {self.get_payment_method_display()}",
                related_withdrawal=self,
                balance_after=self.affiliate.available_balance
            )
            
            self.save()
            self.send_payment_email()

    def reject(self):
        """Reject withdrawal request"""
        self.status = 'rejected'
        self.save()

    # Email Notifications
    def send_approval_email(self):
        """Send approval email"""
        try:
            subject = 'Withdrawal Request Approved'
            message = f"""
Hi {self.affiliate.user.first_name or self.affiliate.user.username},

Your withdrawal request of ₹{self.amount} has been approved.

Your amount will be transferred to your registered {self.get_payment_method_display()} within 5-7 business days.

Thank you for being part of our affiliate program!

Best regards,
{settings.SITE_NAME} Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.affiliate.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending approval email: {str(e)}")

    def send_payment_email(self):
        """Send payment confirmation email"""
        try:
            subject = 'Withdrawal Payment Completed'
            message = f"""
Hi {self.affiliate.user.first_name or self.affiliate.user.username},

Your withdrawal of ₹{self.amount} has been successfully paid to your registered {self.get_payment_method_display()}.

Transaction ID: {self.transaction_id}

Please verify the amount in your account.

Thank you for being part of our affiliate program!

Best regards,
{settings.SITE_NAME} Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.affiliate.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending payment email: {str(e)}")


# ============================================================================
# AFFILIATE TRANSACTION - Complete transaction history
# ============================================================================

class AffiliateTransaction(models.Model):
    """YOUR REQUIREMENT: Store ALL transactions for easy tracking"""
    TRANSACTION_TYPES = [
        ('earning', 'Commission Earned'),
        ('withdrawal', 'Withdrawal'),
        ('bonus', 'Bonus'),
        ('deduction', 'Deduction'),
    ]

    # Links
    affiliate = models.ForeignKey(AffiliateUser, on_delete=models.CASCADE, related_name='transactions')
    
    # Transaction Details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    
    # Related Objects (optional)
    related_order = models.ForeignKey(AffiliateOrder, on_delete=models.SET_NULL, null=True, blank=True)
    related_withdrawal = models.ForeignKey(AffiliateWithdrawal, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Balance after this transaction
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Affiliate Transaction'
        verbose_name_plural = 'Affiliate Transactions'

    def __str__(self):
        return f"{self.affiliate.user.username} - {self.get_transaction_type_display()} - ₹{self.amount}"


# ============================================================================
# AFFILIATE BANNER - Marketing Materials
# ============================================================================

class AffiliateBanner(models.Model):
    """Affiliate marketing banners for promotion"""
    SIZE_CHOICES = [
        ('300x250', '300x250 - Medium Rectangle'),
        ('728x90', '728x90 - Leaderboard'),
        ('970x90', '970x90 - Large Leaderboard'),
        ('160x600', '160x600 - Wide Skyscraper'),
        ('300x600', '300x600 - Half Page'),
    ]

    title = models.CharField(max_length=200)
    size = models.CharField(max_length=20, choices=SIZE_CHOICES)
    image = models.ImageField(upload_to='affiliate/banners/')
    alt_text = models.CharField(max_length=200)
    link_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.size}"

    class Meta:
        verbose_name = 'Affiliate Banner'
        verbose_name_plural = 'Affiliate Banners'


# ============================================================================
# LEGACY MODELS - Keep for backward compatibility
# ============================================================================

class AffiliateApplication(models.Model):
    """Legacy model - can be merged with AffiliateUser"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    website = models.URLField(blank=True, null=True)
    additional_info = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Application: {self.user.username} ({self.status})"


class AffiliateCommission(models.Model):
    """Legacy model - replaced by AffiliateOrder"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.status})"
