from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Sum, Count,F, DecimalField, Q
from django.utils import timezone
from decimal import Decimal
import uuid
import logging

from .models import (
    AffiliateProgram, AffiliateUser, AffiliateClick, AffiliateOrder,
    AffiliateWithdrawal, AffiliateBanner
)
from orders.models import Order

logger = logging.getLogger('affiliate')


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# PUBLIC AFFILIATE PAGES
# ============================================================================

def affiliate_home(request):
    """
    Affiliate program home page
    
    Features:
    - Display program details
    - Show active banners
    - Display affiliate statistics
    - Redirect if user is already affiliate
    
    Statistics shown:
    - Active affiliates count
    - Total commissions paid out
    - Total successful orders
    """
    
    if request.user.is_authenticated:
        try:
            affiliate = AffiliateUser.objects.get(user=request.user)
            # User is already an affiliate - redirect to dashboard
            logger.info(f"✅ Authenticated affiliate redirected to dashboard: {affiliate.affiliate_code}")
            return redirect('affiliate:dashboard')
        except AffiliateUser.DoesNotExist:
            # User is not an affiliate yet - show the home page
            pass
    
    # ✅ GET program details
    program = AffiliateProgram.objects.filter(is_active=True).first()
    
    if not program:
        context = {'program': None}
        return render(request, 'affiliate/home.html', context)
    
    # ✅ GET active banners
    banners = AffiliateBanner.objects.filter(is_active=True)
    
    # ✅ PROGRAM STATISTICS
    active_affiliates = AffiliateUser.objects.filter(status='active').count()
    
    # Only count paid commissions (to show verified earnings)
    total_commissions_paid = AffiliateOrder.objects.filter(
        status='paid'  # Only completed payouts
    ).aggregate(
        total=Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # Total orders processed
    total_orders = AffiliateOrder.objects.filter(
        status__in=['confirmed', 'paid']  # Only successful orders
    ).count()
    
    context = {
        'program': program,
        'banners': banners,
        'active_affiliates': active_affiliates,
        'total_commissions_paid': total_commissions_paid,
        'total_orders': total_orders,
    }
    
    logger.info(f"✅ Affiliate home page viewed | Active affiliates: {active_affiliates}")
    
    return render(request, 'affiliate/home.html', context)


def affiliate_register(request):
    """Alias for affiliate_join"""
    return affiliate_join(request)


def affiliate_join(request):
    """
    Apply to affiliate program
    
    Features:
    - Check if user already an affiliate
    - Auto-create affiliate account with default program
    - Generate unique affiliate code
    - Set status to pending
    
    Affiliate code format: USERNAME_XXXXXXXX (uppercase)
    """
    
    # ✅ GET the default program
    program = AffiliateProgram.objects.filter(is_active=True).first()
    
    if not program:
        messages.error(request, 'Affiliate program is currently closed.')
        logger.warning("⚠️  Affiliate program inactive")
        return redirect('affiliate:home')
    
    # ✅ CHECK if user is already an affiliate
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
        messages.info(request, 'You are already part of the affiliate program.')
        return redirect('affiliate:dashboard')
    except AffiliateUser.DoesNotExist:
        pass
    
    if request.method == 'POST':
        form = AffiliateSignupForm(request.POST)
        if form.is_valid():
            try:
                # Get affiliate program
                program = AffiliateProgram.objects.first()
                
                # Create affiliate account with bank details
                affiliate = AffiliateUser.objects.create(
                    user=request.user,
                    program=program,
                    status='pending',
                    
                    # Bank Details
                    bank_name=form.cleaned_data['bank_name'],
                    account_holder_name=form.cleaned_data['account_holder_name'],
                    account_number=form.cleaned_data['account_number'],
                    ifsc_code=form.cleaned_data['ifsc_code'],
                    upi_id=form.cleaned_data['upi_id'],
                    pan_number=form.cleaned_data['pan_number'],
                )
                
                # Log the signup
                logger.info(f"New affiliate signup: {affiliate.affiliate_code} | Bank: {affiliate.bank_name}")
                
                # Send notification to admin
                send_admin_notification(
                    subject="New Affiliate Signup",
                    message=f"New affiliate {request.user.get_full_name()} joined with bank details",
                    affiliate=affiliate
                )
                
                messages.success(
                    request,
                    'Application submitted successfully! We\'ll review your bank details and approve your account within 24-48 hours.'
                )
                
                return redirect('affiliate:dashboard')
            
            except Exception as e:
                logger.error(f"Affiliate signup error: {str(e)}")
                messages.error(request, f'Error creating account: {str(e)}')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = AffiliateSignupForm()
    
    context = {'form': form}
    return render(request, 'affiliate/join.html', context)

# ============================================================================
# AFFILIATE DASHBOARD & STATS
# ============================================================================

@login_required
def affiliate_dashboard(request):
    """
    Affiliate dashboard with REAL data
    
    Features:
    - Display clicks, orders, conversion rate
    - Show earned commission (5%)
    - Show pending vs confirmed commission
    - Show available balance for withdrawal
    - Display recent orders with commission details
    - Show top products by revenue
    
    Commission breakdown:
    - Pending (7 days): Not yet approved
    - Confirmed: Approved, ready to withdraw
    - Available: Total earned - pending withdrawals
    """
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        messages.info(request, 'You are not an affiliate. Join the program first.')
        logger.info(f"⚠️  Non-affiliate tried to access dashboard")
        return redirect('affiliate:join')
    
    # ✅ REAL clicks from database
    total_clicks = AffiliateClick.objects.filter(affiliate=affiliate).count()
    
    # ✅ REAL affiliate orders
    affiliate_orders = AffiliateOrder.objects.filter(affiliate=affiliate)
    total_orders = affiliate_orders.count()
    
    # ✅ REAL sales amount (sum of all order amounts)
    total_sales = affiliate_orders.aggregate(
        total=models.Sum('order_amount')
    )['total'] or Decimal('0')
    
    # ✅ REAL commission (5%) - only confirmed and paid
    total_commission = affiliate_orders.filter(
        status__in=['confirmed', 'paid']
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # ✅ PENDING commission (5%) - waiting 7-day approval
    pending_commission = affiliate_orders.filter(
        status='pending'
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # ✅ Recent orders with order details
    recent_orders = affiliate_orders.select_related('order').order_by('-created_at')[:10]
    
    # ✅ Pending withdrawals (requested but not yet paid)
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status__in=['pending', 'approved']
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    # ✅ Available for withdrawal = earned - pending
    available_for_withdrawal = total_commission - pending_withdrawals
    
    # ✅ Top products by revenue
    top_products = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status__in=['confirmed', 'paid']
    ).values(
        'order__items__product_name'
    ).annotate(
        quantity=Sum('order__items__quantity'),
        revenue=Sum(F('order__items__price') * F('order__items__quantity'))
    ).order_by('-revenue')[:5]
    
    # ✅ Conversion rate
    conversion_rate = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
    
    context = {
        'affiliate': affiliate,
        'total_clicks': total_clicks,
        'total_orders': total_orders,
        'conversion_rate': round(conversion_rate, 2),
        'total_sales': total_sales,
        'total_commission': total_commission,  # Earned & available
        'pending_commission': pending_commission,  # Pending approval
        'available_for_withdrawal': available_for_withdrawal,  # Can withdraw
        'recent_orders': recent_orders,
        'pending_withdrawals': pending_withdrawals,
        'top_products': top_products,
    }
    
    logger.info(
        f"✅ Affiliate dashboard viewed: {affiliate.affiliate_code} | "
        f"Commission: ₹{total_commission} | "
        f"Available: ₹{available_for_withdrawal}"
    )
    
    return render(request, 'affiliate/dashboard.html', context)


@login_required
def affiliate_stats(request):
    """Display affiliate performance statistics with REAL DATA from database"""
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        messages.error(request, 'You need to join the affiliate program first.')
        return redirect('affiliate:join')
    
    # Get time period from request
    time_period = request.GET.get('period', 30)
    
    try:
        time_period = int(time_period)
    except ValueError:
        time_period = 30
    
    # Calculate date range
    if time_period == 'all':
        start_date = None
    else:
        start_date = timezone.now() - timezone.timedelta(days=time_period)
    
    # REAL DATA: Get clicks
    if start_date:
        total_clicks = AffiliateClick.objects.filter(
            affiliate=affiliate,
            created_at__gte=start_date
        ).count()
    else:
        total_clicks = AffiliateClick.objects.filter(affiliate=affiliate).count()
    
    # REAL DATA: Get orders and conversions
    if start_date:
        affiliate_orders = AffiliateOrder.objects.filter(
            affiliate=affiliate,
            created_at__gte=start_date
        )
    else:
        affiliate_orders = AffiliateOrder.objects.filter(affiliate=affiliate)
    
    total_orders = affiliate_orders.count()
    
    # REAL DATA: Get total sales
    total_sales = affiliate_orders.aggregate(
        total=Sum('order__total', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # REAL DATA: Get commissions
    total_commission = affiliate_orders.aggregate(
        total=Sum('commission_amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    pending_commission = affiliate_orders.filter(
        status='pending'
    ).aggregate(
        total=Sum('commission_amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    available_for_withdrawal = affiliate_orders.filter(
        status='confirmed'
    ).aggregate(
        total=Sum('commission_amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # REAL DATA: Get withdrawal history
    total_withdrawn = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status='paid'
    ).aggregate(
        total=Sum('amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # Calculate conversion rate
    conversion_rate = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
    
    # REAL DATA: Top performing products
    top_products = affiliate_orders.values(
        'order__items__product_name'
    ).annotate(
        quantity=Sum('order__items__quantity'),
        revenue=Sum('order__items__price')
    ).order_by('-revenue')[:5]
    
    # REAL DATA: Recent orders
    recent_orders = affiliate_orders.select_related('order').order_by('-created_at')[:10]
    
    context = {
        'affiliate': affiliate,
        'total_clicks': total_clicks,
        'total_orders': total_orders,
        'total_sales': total_sales,
        'conversion_rate': round(conversion_rate, 1),
        'total_commission': total_commission,
        'pending_commission': pending_commission,
        'available_for_withdrawal': available_for_withdrawal,
        'total_withdrawn': total_withdrawn,
        'top_products': top_products,
        'recent_orders': recent_orders,
        'time_period': time_period,
    }
    
    logger.info(f"Affiliate stats viewed: {affiliate.affiliate_code} | Earnings: ₹{total_commission}")
    
    return render(request, 'affiliate/stats.html', context)


# ============================================================================
# AFFILIATE REFERRAL TRACKING
# ============================================================================

def track_affiliate_click(request, affiliate_code):
    """
    Track affiliate click and set cookie
    
    Features:
    - Verify affiliate exists and is active
    - Record click in database
    - Set cookies for 30-day tracking window
    - Redirect to home page
    
    Cookies set:
    - affiliate_code: Used for commission calculation
    - visitor_id: Unique visitor tracking
    - affiliate_id: Database ID for quick lookup
    """
    
    try:
        # ✅ VERIFY affiliate exists and is active
        affiliate = AffiliateUser.objects.get(
            affiliate_code=affiliate_code,
            status='active'
        )
    except AffiliateUser.DoesNotExist:
        logger.warning(f"⚠️  Invalid affiliate code: {affiliate_code}")
        return redirect('products:home')
    
    # ✅ CREATE unique visitor ID
    visitor_id = str(uuid.uuid4())
    
    # ✅ RECORD click in database
    AffiliateClick.objects.create(
        affiliate=affiliate,
        visitor_id=visitor_id,
        referrer_url=request.META.get('HTTP_REFERER', ''),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
    )
    
    logger.info(
        f"✅ Affiliate click tracked: {affiliate_code} | "
        f"Visitor: {visitor_id} | "
        f"IP: {get_client_ip(request)}"
    )
    
    # ✅ SET cookies for 30-day tracking
    response = redirect('products:home')
    response.set_cookie('affiliate_code', affiliate_code, max_age=60*60*24*30)
    response.set_cookie('visitor_id', visitor_id, max_age=60*60*24*30)
    response.set_cookie('affiliate_id', str(affiliate.id), max_age=60*60*24*30)
    
    return response


# ============================================================================
# AFFILIATE LINKS & BANNERS
# ============================================================================

@login_required
def affiliate_links(request):
    """
    Affiliate referral links page
    
    Features:
    - Display affiliate referral link
    - Show available banners for sharing
    - Display click statistics
    - Provide copy-to-clipboard functionality
    """
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    # ✅ GET active banners
    banners = AffiliateBanner.objects.filter(is_active=True)
    
    # ✅ BUILD referral link
    affiliate_link = f"{request.build_absolute_uri('/affiliate/track/')}{affiliate.affiliate_code}/"
    
    # ✅ GET click stats
    total_clicks = AffiliateClick.objects.filter(affiliate=affiliate).count()
    
    context = {
        'affiliate': affiliate,
        'banners': banners,
        'affiliate_link': affiliate_link,
        'total_clicks': total_clicks,
    }
    
    logger.info(f"✅ Affiliate links page viewed: {affiliate.affiliate_code} | Clicks: {total_clicks}")
    
    return render(request, 'affiliate/links.html', context)


# ============================================================================
# PAYMENTS & WITHDRAWALS
# ============================================================================

@login_required
def affiliate_withdrawals(request):
    """Display withdrawals and request withdrawal with REAL BANK DETAILS"""
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        messages.error(request, 'You need to join the affiliate program first.')
        return redirect('affiliate:join')
    
    # REAL DATA: Get withdrawal balance
    confirmed_commissions = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status='confirmed'
    ).aggregate(
        total=Sum('commission_amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    pending_commissions = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status='pending'
    ).aggregate(
        total=Sum('commission_amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # Get total withdrawn (REAL DATA)
    total_withdrawn = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status='paid'
    ).aggregate(
        total=Sum('amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # Get pending withdrawals
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate
    ).exclude(status='paid').aggregate(
        total=Sum('amount', output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # Get withdrawal history (REAL DATA)
    withdrawal_history = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate
    ).order_by('-requested_at')
    
    # Handle withdrawal request
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'request_withdrawal':
            # VALIDATE: Minimum withdrawal amount
            amount = Decimal(request.POST.get('amount', '0'))
            payment_method = request.POST.get('payment_method')
            
            min_withdrawal = affiliate.program.min_withdrawal if hasattr(affiliate, 'program') else Decimal('1000.00')
            
            # VALIDATE: Sufficient balance
            if amount < min_withdrawal:
                messages.error(request, f'Minimum withdrawal amount is ₹{min_withdrawal}')
                return redirect('affiliate:withdrawals')
            
            if amount > confirmed_commissions:
                messages.error(request, f'Insufficient balance. Available: ₹{confirmed_commissions}')
                return redirect('affiliate:withdrawals')
            
            # VALIDATE: Payment method & Bank details provided
            if payment_method == 'bank':
                bank_name = request.POST.get('bank_name')
                account_holder = request.POST.get('account_holder')
                account_number = request.POST.get('account_number')
                ifsc_code = request.POST.get('ifsc_code')
                
                if not all([bank_name, account_holder, account_number, ifsc_code]):
                    messages.error(request, 'Please provide all bank details')
                    return redirect('affiliate:withdrawals')
                
                payment_details = f"""
                Bank: {bank_name}
                Account Holder: {account_holder}
                Account Number: {account_number}
                IFSC Code: {ifsc_code}
                """
            
            elif payment_method == 'upi':
                upi_id = request.POST.get('upi_id')
                
                if not upi_id:
                    messages.error(request, 'Please provide UPI ID')
                    return redirect('affiliate:withdrawals')
                
                payment_details = f"UPI: {upi_id}"
            
            else:
                messages.error(request, 'Invalid payment method')
                return redirect('affiliate:withdrawals')
            
            # CREATE WITHDRAWAL REQUEST
            withdrawal = AffiliateWithdrawal.objects.create(
                affiliate=affiliate,
                amount=amount,
                payment_method=payment_method,
                payment_details=payment_details,
                status='pending'
            )
            
            messages.success(request, f'Withdrawal request of ₹{amount} submitted successfully!')
            logger.info(f"Withdrawal requested: {affiliate.affiliate_code} | Amount: ₹{amount} | Method: {payment_method}")
            
            return redirect('affiliate:withdrawals')
    
    context = {
        'affiliate': affiliate,
        'available_balance': confirmed_commissions,
        'pending_balance': pending_commissions,
        'total_withdrawn': total_withdrawn,
        'pending_withdrawals': pending_withdrawals,
        'withdrawal_history': withdrawal_history,
        'min_withdrawal': affiliate.program.min_withdrawal if hasattr(affiliate, 'program') else Decimal('1000.00'),
    }
    
    return render(request, 'affiliate/withdrawals.html', context)

@login_required
@require_POST
def request_withdrawal(request):
    """
    Request withdrawal with validation
    
    Validation:
    - Amount >= minimum (₹1000)
    - Amount <= available balance
    - Sufficient commission earned
    
    Creates AffiliateWithdrawal with status='pending'
    Admin will review and approve
    """
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return JsonResponse({'error': 'Not an affiliate'}, status=400)
    
    # ✅ GET amount from form
    try:
        amount = Decimal(request.POST.get('amount', '0'))
    except:
        return JsonResponse({'error': 'Invalid amount'}, status=400)
    
    # ✅ VALIDATE minimum amount
    if amount < Decimal(str(affiliate.program.min_withdrawal)):
        return JsonResponse({
            'error': f'Minimum withdrawal amount is ₹{affiliate.program.min_withdrawal}'
        }, status=400)
    
    # ✅ CALCULATE real available balance
    total_commission = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status__in=['confirmed', 'paid']  # Only approved
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status__in=['pending', 'approved']  # Not yet paid
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    available_balance = total_commission - pending_withdrawals
    
    # ✅ VALIDATE sufficient balance
    if amount > available_balance:
        return JsonResponse({
            'error': f'Insufficient balance. Available: ₹{available_balance:.2f}'
        }, status=400)
    
    try:
        # ✅ CREATE withdrawal request
        withdrawal = AffiliateWithdrawal.objects.create(
            affiliate=affiliate,
            amount=amount,
            status='pending'  # Will be reviewed by admin
        )
        
        logger.info(
            f"✅ Withdrawal requested: {affiliate.affiliate_code} | "
            f"Amount: ₹{amount} | "
            f"Remaining: ₹{available_balance - amount} | "
            f"Status: pending"
        )
        
        messages.success(request, f'Withdrawal request of ₹{amount} submitted! You will be contacted soon.')
        return redirect('affiliate:withdrawals')
        
    except Exception as e:
        logger.error(f"❌ Error requesting withdrawal: {str(e)}")
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)


# ============================================================================
# AFFILIATE SETTINGS
# ============================================================================

@login_required
def affiliate_settings(request):
    """
    Affiliate settings page
    
    Features:
    - Update bank account information
    - Validate all fields required
    - Secure payment method storage
    """
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    if request.method == 'POST':
        # ✅ UPDATE payment information
        affiliate.bank_name = request.POST.get('bank_name', '').strip()
        affiliate.account_holder = request.POST.get('account_holder', '').strip()
        affiliate.account_number = request.POST.get('account_number', '').strip()
        affiliate.ifsc_code = request.POST.get('ifsc_code', '').strip()
        
        # ✅ VALIDATE all fields required
        if not all([affiliate.bank_name, affiliate.account_holder,
                    affiliate.account_number, affiliate.ifsc_code]):
            messages.error(request, 'All bank details are required.')
            logger.warning(f"⚠️  Incomplete bank details: {affiliate.affiliate_code}")
            return redirect('affiliate:settings')
        
        # ✅ SAVE
        affiliate.save()
        
        logger.info(f"✅ Affiliate settings updated: {affiliate.affiliate_code}")
        messages.success(request, 'Settings updated successfully!')
        return redirect('affiliate:settings')
    
    context = {'affiliate': affiliate}
    return render(request, 'affiliate/settings.html', context)


# ============================================================================
# AFFILIATE PROFILE
# ============================================================================

@login_required
def affiliate_profile(request):
    """View affiliate profile"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    context = {'affiliate': affiliate}
    return render(request, 'affiliate/profile.html', context)


# ============================================================================
# SUMMARY: COMPLETE AFFILIATE SYSTEM
# ============================================================================

"""
COMPLETE AFFILIATE PROGRAM WORKFLOW WITH 5% COMMISSION:

1. REGISTRATION (affiliate_join):
   ✅ User applies to affiliate program
   ✅ Generates unique affiliate code (USERNAME_XXXXXXXX)
   ✅ Status: pending (awaiting admin approval)
   ✅ Admin approves → status='active'

2. REFERRAL TRACKING (affiliate_links + track_affiliate_click):
   ✅ Affiliate gets unique referral link: /affiliate/track/CODE/
   ✅ Affiliate shares link, banners
   ✅ Visitor clicks → AffiliateClick recorded
   ✅ Cookies set for 30-day tracking window

3. PURCHASE & COMMISSION (payments/views.py):
   ✅ User within 30 days makes purchase: ₹1000
   ✅ Affiliate code from session
   ✅ Commission calculated: 5% = ₹50
   ✅ AffiliateOrder created (status='pending')
   ✅ Affiliate notified via email

4. AUTO-APPROVAL (Background task, 7 days):
   ✅ status: 'pending' → 'confirmed'
   ✅ Commission now earned and available

5. WITHDRAWAL (affiliate_withdrawals):
   ✅ Affiliate views dashboard:
      - Total commission: ₹250 (5 orders)
      - Pending approval: ₹50 (1 recent order)
      - Available balance: ₹200 (₹250 - ₹50)
   ✅ Requests withdrawal: ₹200
   ✅ Creates AffiliateWithdrawal (status='pending')

6. PAYMENT (Admin action):
   ✅ Admin reviews withdrawal request
   ✅ Approves and transfers funds
   ✅ status: 'pending' → 'approved' → 'paid'
   ✅ Money in affiliate's bank account

DASHBOARD SHOWS:
  Clicks: 127
  Orders: 5
  Conversion: 3.94%
  
  Commission Status:
  - Total Earned: ₹250 (5 orders × ₹50)
  - Pending (7 days): ₹50
  - Confirmed: ₹200
  
  Withdrawals:
  - Available: ₹200
  - Pending: ₹50
  - Total Paid Out: ₹1,500

COMMISSION STATES:
1. pending      - Waiting 7 days
2. confirmed    - Approved, available to withdraw
3. paid         - Already withdrawn

KEY METRICS:
- Commission Rate: 5% (automatic)
- Tracking Period: 30 days (via cookie)
- Minimum Withdrawal: ₹1,000
- Auto-approval: 7 days
- Approval Method: Automatic (no manual intervention)

LOGGING:
✅ Click tracked: affiliate_code, visitor_id, IP
✅ Commission created: order_id, amount, rate
✅ Status updated: from pending → confirmed → paid
✅ Withdrawal requested: amount, status
✅ Payment processed: amount, affiliate_code
"""
