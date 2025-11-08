# affiliate/admin.py - Django Admin Configuration for Affiliate Program
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from django.utils import timezone
from .models import (
    AffiliateProgram, AffiliateUser, AffiliateClick, 
    AffiliateOrder, AffiliateWithdrawal, AffiliateTransaction, 
    AffiliateBanner, AffiliateApplication, AffiliateCommission
)


# ============================================================================
# AFFILIATE PROGRAM ADMIN
# ============================================================================

@admin.register(AffiliateProgram)
class AffiliateProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'commission_rate', 'min_withdrawal', 'cookie_duration', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Program Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Commission Settings', {
            'fields': ('commission_rate', 'cookie_duration')
        }),
        ('Withdrawal Settings', {
            'fields': ('min_withdrawal',)
        }),
        ('Terms & Conditions', {
            'fields': ('terms_and_conditions',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')


# ============================================================================
# AFFILIATE APPLICATION ADMIN
# ============================================================================

@admin.register(AffiliateApplication)
class AffiliateApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_editable = ('status',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Application Information', {
            'fields': ('user', 'status')
        }),
        ('Application Details', {
            'fields': ('website', 'additional_info')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    actions = ['approve_applications', 'reject_applications']
    
    def approve_applications(self, request, queryset):
        """Approve selected applications"""
        queryset.update(status='approved')
        self.message_user(request, f'{queryset.count()} applications approved!')
    approve_applications.short_description = "Approve selected applications"
    
    def reject_applications(self, request, queryset):
        """Reject selected applications"""
        queryset.update(status='rejected')
        self.message_user(request, f'{queryset.count()} applications rejected!')
    reject_applications.short_description = "Reject selected applications"


# ============================================================================
# AFFILIATE USER ADMIN
# ============================================================================

@admin.register(AffiliateUser)
class AffiliateUserAdmin(admin.ModelAdmin):
    # FIXED: Removed list_editable, kept status in list_display as field
    list_display = (
        'user_username',
        'affiliate_code',
        'status',  # Now direct field, not method
        'total_earnings_display',
        'total_withdrawn',
        'total_referrals',
        'joined_at'
    )
    list_filter = ('status', 'program', 'joined_at', 'approved_date')
    search_fields = ('user__username', 'user__email', 'affiliate_code')
    # REMOVED: list_editable = ('status',)  # No longer needed with actions
    date_hierarchy = 'joined_at'
    readonly_fields = ('affiliate_code', 'joined_at', 'approved_date', 'available_balance_display')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'program', 'affiliate_code', 'status')
        }),
        ('Bank Details', {
            'fields': ('bank_name', 'account_holder', 'account_number', 'ifsc_code', 'upi_id'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_earnings',
                'total_withdrawn',
                'total_referrals',
                'available_balance_display'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('joined_at', 'approved_date'),
            'classes': ('collapse',)
        }),
    )
    
    def user_username(self, obj):
        """Display username"""
        return obj.user.username
    user_username.short_description = 'Username'
    user_username.admin_order_field = 'user__username'
    
    def total_earnings_display(self, obj):
        """Display total earnings with color"""
        return format_html(
            '<span style="color: green; font-weight: bold;">₹{}</span>',
            obj.total_earnings
        )
    total_earnings_display.short_description = 'Total Earnings'
    total_earnings_display.admin_order_field = 'total_earnings'
    
    def available_balance_display(self, obj):
        """Display available balance"""
        balance = obj.available_balance
        color = 'green' if balance >= obj.program.min_withdrawal else 'red'
        status_text = '✓ Ready' if balance >= obj.program.min_withdrawal else f'₹{obj.program.min_withdrawal - balance} needed'
        return format_html(
            '<span style="color: {}; font-weight: bold;">₹{} ({})</span>',
            color,
            balance,
            status_text
        )
    available_balance_display.short_description = 'Available Balance'
    
    actions = ['approve_affiliates', 'suspend_affiliates', 'reject_affiliates']
    
    def approve_affiliates(self, request, queryset):
        """Bulk approve affiliates"""
        for affiliate in queryset.filter(status='pending'):
            affiliate.approve()
        self.message_user(request, f'{queryset.count()} affiliates approved!')
    approve_affiliates.short_description = 'Approve selected affiliates'
    
    def suspend_affiliates(self, request, queryset):
        """Bulk suspend affiliates"""
        for affiliate in queryset.filter(status='active'):
            affiliate.suspend()
        self.message_user(request, f'{queryset.count()} affiliates suspended!')
    suspend_affiliates.short_description = 'Suspend selected affiliates'
    
    def reject_affiliates(self, request, queryset):
        """Bulk reject affiliates"""
        for affiliate in queryset.filter(status='pending'):
            affiliate.reject()
        self.message_user(request, f'{queryset.count()} affiliates rejected!')
    reject_affiliates.short_description = 'Reject selected affiliates'


# ============================================================================
# AFFILIATE COMMISSION ADMIN
# ============================================================================

@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    # FIXED: Added status to list_display and removed list_editable
    list_display = ('user', 'order_id', 'amount_display', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'order_id')
    # REMOVED: list_editable = ('status',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'paid_at')
    
    fieldsets = (
        ('Commission Information', {
            'fields': ('user', 'order_id', 'amount')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'paid_at')
        }),
    )
    
    def amount_display(self, obj):
        """Display amount"""
        return format_html('₹{}', obj.amount)
    amount_display.short_description = 'Amount'
    
    actions = ['mark_as_approved', 'mark_as_paid']
    
    def mark_as_approved(self, request, queryset):
        """Mark commissions as approved"""
        updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f'{updated} commissions marked as approved!')
    mark_as_approved.short_description = "Mark as Approved"
    
    def mark_as_paid(self, request, queryset):
        """Mark commissions as paid"""
        updated = queryset.filter(status__in=['pending', 'approved']).update(
            status='paid',
            paid_at=timezone.now()
        )
        self.message_user(request, f'{updated} commissions marked as paid!')
    mark_as_paid.short_description = "Mark as Paid"


# ============================================================================
# AFFILIATE CLICK ADMIN
# ============================================================================

@admin.register(AffiliateClick)
class AffiliateClickAdmin(admin.ModelAdmin):
    list_display = ('affiliate_code', 'visitor_id', 'ip_address', 'created_at')
    list_filter = ('affiliate__affiliate_code', 'created_at')
    search_fields = ('affiliate__affiliate_code', 'visitor_id', 'ip_address')
    readonly_fields = ('created_at', 'affiliate', 'visitor_id', 'ip_address', 'user_agent', 'referrer_url')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Click Information', {
            'fields': ('affiliate', 'visitor_id', 'ip_address')
        }),
        ('Technical Details', {
            'fields': ('user_agent', 'referrer_url', 'session_key'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def affiliate_code(self, obj):
        """Display affiliate code"""
        return obj.affiliate.affiliate_code
    affiliate_code.short_description = 'Affiliate'
    
    def has_add_permission(self, request):
        """Disable adding clicks manually"""
        return False


# ============================================================================
# AFFILIATE ORDER ADMIN
# ============================================================================

@admin.register(AffiliateOrder)
class AffiliateOrderAdmin(admin.ModelAdmin):
    list_display = (
        'affiliate_code',
        'order_number',
        'order_amount_display',
        'commission_display',
        'status',
        'created_at'
    )
    list_filter = ('status', 'created_at', 'affiliate__affiliate_code')
    search_fields = ('affiliate__affiliate_code', 'order__order_number')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'confirmed_at', 'completed_at')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('affiliate', 'order')
        }),
        ('Commission Details', {
            'fields': ('order_amount', 'commission_rate', 'commission_amount')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'confirmed_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def affiliate_code(self, obj):
        """Display affiliate code"""
        return obj.affiliate.affiliate_code
    affiliate_code.short_description = 'Affiliate'
    
    def order_number(self, obj):
        """Display order number"""
        return obj.order.order_number if obj.order else 'N/A'
    order_number.short_description = 'Order #'
    
    def order_amount_display(self, obj):
        """Display order amount"""
        return format_html('₹{}', obj.order_amount)
    order_amount_display.short_description = 'Order Amount'
    
    def commission_display(self, obj):
        """Display commission with color"""
        return format_html(
            '<span style="color: green; font-weight: bold;">₹{}</span>',
            obj.commission_amount
        )
    commission_display.short_description = 'Commission (2%)'
    
    actions = ['confirm_orders', 'complete_orders', 'cancel_orders']
    
    def confirm_orders(self, request, queryset):
        """Confirm selected orders"""
        for order in queryset.filter(status='pending'):
            order.confirm()
        self.message_user(request, f'{queryset.count()} orders confirmed!')
    confirm_orders.short_description = 'Confirm selected orders'
    
    def complete_orders(self, request, queryset):
        """Complete selected orders and add commission"""
        count = 0
        for order in queryset.filter(status__in=['pending', 'confirmed']):
            order.complete()
            count += 1
        self.message_user(request, f'{count} orders completed and commissions added!')
    complete_orders.short_description = 'Complete orders (add commission)'
    
    def cancel_orders(self, request, queryset):
        """Cancel selected orders"""
        for order in queryset.filter(status='completed'):
            order.cancel()
        self.message_user(request, f'{queryset.count()} orders cancelled!')
    cancel_orders.short_description = 'Cancel selected orders'


# ============================================================================
# AFFILIATE WITHDRAWAL ADMIN
# ============================================================================

@admin.register(AffiliateWithdrawal)
class AffiliateWithdrawalAdmin(admin.ModelAdmin):
    # FIXED: Added status to list_display and removed list_editable
    list_display = (
        'affiliate_username',
        'amount_display',
        'payment_method',
        'status',
        'requested_at'
    )
    list_filter = ('status', 'payment_method', 'requested_at')
    search_fields = ('affiliate__user__username', 'affiliate__affiliate_code')
    # REMOVED: list_editable = ('status',)
    date_hierarchy = 'requested_at'
    readonly_fields = ('requested_at', 'approved_at', 'paid_at')
    
    fieldsets = (
        ('Withdrawal Request', {
            'fields': ('affiliate', 'amount', 'status')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_details', 'transaction_id')
        }),
        ('Admin Notes', {
            'fields': ('admin_notes',)
        }),
        ('Processing History', {
            'fields': ('requested_at', 'approved_at', 'paid_at'),
            'classes': ('collapse',)
        }),
    )
    
    def affiliate_username(self, obj):
        """Display affiliate username"""
        return obj.affiliate.user.username
    affiliate_username.short_description = 'Affiliate'
    
    def amount_display(self, obj):
        """Display amount with color based on status"""
        colors = {
            'pending': '#FFA500',
            'approved': '#4169E1',
            'processing': '#800080',
            'paid': '#228B22',
            'rejected': '#DC143C'
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">₹{}</span>',
            color,
            obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    actions = ['approve_withdrawals', 'mark_as_processing', 'mark_as_paid', 'reject_withdrawals']
    
    def approve_withdrawals(self, request, queryset):
        """Approve selected withdrawals"""
        updated = queryset.filter(status='pending').update(
            status='approved',
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} withdrawals approved!')
    approve_withdrawals.short_description = 'Approve withdrawals'
    
    def mark_as_processing(self, request, queryset):
        """Mark as processing"""
        updated = queryset.filter(status='approved').update(status='processing')
        self.message_user(request, f'{updated} withdrawals marked as processing!')
    mark_as_processing.short_description = 'Mark as processing'
    
    def mark_as_paid(self, request, queryset):
        """Mark withdrawals as paid"""
        count = 0
        for withdrawal in queryset.filter(status__in=['pending', 'approved', 'processing']):
            withdrawal.mark_paid()
            count += 1
        self.message_user(request, f'{count} withdrawals marked as paid!')
    mark_as_paid.short_description = 'Mark as paid'
    
    def reject_withdrawals(self, request, queryset):
        """Reject selected withdrawals"""
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{updated} withdrawals rejected!')
    reject_withdrawals.short_description = 'Reject withdrawals'


# ============================================================================
# AFFILIATE TRANSACTION ADMIN
# ============================================================================

@admin.register(AffiliateTransaction)
class AffiliateTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'affiliate_code',
        'transaction_type',
        'amount_display',
        'description_short',
        'balance_after_display',
        'created_at'
    )
    list_filter = ('transaction_type', 'created_at', 'affiliate__affiliate_code')
    search_fields = ('affiliate__affiliate_code', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'balance_after')
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('affiliate', 'transaction_type', 'amount', 'description')
        }),
        ('Related Objects', {
            'fields': ('related_order', 'related_withdrawal'),
            'classes': ('collapse',)
        }),
        ('Balance', {
            'fields': ('balance_after',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def affiliate_code(self, obj):
        """Display affiliate code"""
        return obj.affiliate.affiliate_code
    affiliate_code.short_description = 'Affiliate'
    
    def amount_display(self, obj):
        """Display amount with color"""
        color = 'green' if obj.transaction_type in ['earning', 'bonus'] else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">₹{}</span>',
            color,
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def balance_after_display(self, obj):
        """Display balance after"""
        return format_html('₹{}', obj.balance_after)
    balance_after_display.short_description = 'Balance After'
    
    def description_short(self, obj):
        """Display short description"""
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'
    
    def has_add_permission(self, request):
        """Disable adding transactions manually"""
        return False


# ============================================================================
# AFFILIATE BANNER ADMIN
# ============================================================================

@admin.register(AffiliateBanner)
class AffiliateBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'size', 'banner_preview', 'is_active', 'created_at')
    list_filter = ('size', 'is_active', 'created_at')
    search_fields = ('title', 'alt_text')
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'banner_preview')
    
    fieldsets = (
        ('Banner Details', {
            'fields': ('title', 'size', 'is_active')
        }),
        ('Image', {
            'fields': ('image', 'banner_preview')
        }),
        ('Link & SEO', {
            'fields': ('link_url', 'alt_text')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def banner_preview(self, obj):
        """Display banner preview"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;">',
                obj.image.url
            )
        return 'No image'
    banner_preview.short_description = 'Preview'
