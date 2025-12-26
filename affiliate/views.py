from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Sum, Count,F
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
    if request.user.is_authenticated:
        try:
            affiliate = AffiliateUser.objects.get(user=request.user)
            messages.info(request, f'You are already an affiliate! Your code: {affiliate.affiliate_code}')
            logger.info(f"⚠️  User already affiliate: {affiliate.affiliate_code}")
            return redirect('affiliate:dashboard')
        except AffiliateUser.DoesNotExist:
            pass
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Please login first.')
            return redirect('accounts:login')
        
        try:
            # ✅ GENERATE unique affiliate code
            affiliate_code = f"{request.user.username.upper()}_{uuid.uuid4().hex[:8].upper()}"
            
            # ✅ CREATE affiliate user
            affiliate = AffiliateUser.objects.create(
                user=request.user,
                program=program,
                affiliate_code=affiliate_code,
                status='pending'  # Awaiting admin approval
            )
            
            logger.info(
                f"✅ Affiliate application submitted: {affiliate_code} | "
                f"User: {request.user.username} | "
                f"Status: pending"
            )
            
            messages.success(request, f'Application submitted successfully! Your code: {affiliate_code}. You will be contacted soon.')
            return redirect('affiliate:dashboard')
            
        except Exception as e:
            logger.error(f"❌ Error creating affiliate: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
            return redirect('affiliate:join')
    
    context = {'program': program}
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
    """
    Affiliate statistics with commission breakdown
    
    Features:
    - Show status breakdown (pending, confirmed, paid, failed)
    - Show commission breakdown by status
    - Show conversion analytics
    - Paginated order list
    """
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    # ✅ GET all affiliate orders
    all_orders = AffiliateOrder.objects.filter(affiliate=affiliate).order_by('-created_at')
    
    # ✅ STATUS BREAKDOWN
    pending_orders = all_orders.filter(status='pending').count()
    confirmed_orders = all_orders.filter(status='confirmed').count()
    paid_orders = all_orders.filter(status='paid').count()
    failed_orders = all_orders.filter(status='failed').count()
    
    # ✅ COMMISSION BREAKDOWN by status
    pending_commission = all_orders.filter(status='pending').aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    confirmed_commission = all_orders.filter(status='confirmed').aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    paid_commission = all_orders.filter(status='paid').aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # ✅ PAGINATION
    paginator = Paginator(all_orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # ✅ CLICK stats
    total_clicks = AffiliateClick.objects.filter(affiliate=affiliate).count()
    click_to_order_ratio = (all_orders.count() / total_clicks * 100) if total_clicks > 0 else 0
    
    context = {
        'affiliate': affiliate,
        "affiliate_link": affiliate.referral_link,
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'total_clicks': total_clicks,
        'click_to_order_ratio': round(click_to_order_ratio, 2),
        # ✅ Status breakdown
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'paid_orders': paid_orders,
        'failed_orders': failed_orders,
        # ✅ Commission breakdown
        'pending_commission': pending_commission,
        'confirmed_commission': confirmed_commission,
        'paid_commission': paid_commission,
        'total_earned': pending_commission + confirmed_commission + paid_commission,
    }
    
    logger.info(f"✅ Affiliate stats viewed: {affiliate.affiliate_code}")
    
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
    """
    Affiliate withdrawals page
    
    Features:
    - Show total commission earned (5%)
    - Show pending withdrawals
    - Calculate available balance
    - Display withdrawal history
    - Show minimum withdrawal requirement
    
    Balance calculation:
    - Total Commission: earned & approved commissions only
    - Pending Withdrawals: requested but not yet paid
    - Available Balance: Total - Pending
    """
    
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    # ✅ REAL commission from confirmed/paid orders ONLY
    # These are the orders that are approved and available
    total_commission = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status__in=['confirmed', 'paid']  # Only approved commissions
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # ✅ PENDING withdrawals (requested but not yet paid)
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status__in=['pending', 'approved']  # Requested but not transferred
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    # ✅ AVAILABLE BALANCE for withdrawal
    # Formula: Total Commission - Pending Withdrawals
    available_balance = total_commission - pending_withdrawals
    
    # ✅ Check if user can withdraw
    can_withdraw = available_balance >= affiliate.program.min_withdrawal
    
    # ✅ GET withdrawal history
    withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate
    ).order_by('-requested_at')
    
    # ✅ PAGINATION
    paginator = Paginator(withdrawals, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # ✅ WITHDRAWAL STATS
    total_withdrawn = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status='paid'
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    context = {
        'affiliate': affiliate,
        'total_commission': total_commission,  # Earned (confirmed + paid)
        'pending_withdrawals': pending_withdrawals,  # Requested
        'available_balance': available_balance,  # Can withdraw
        'can_withdraw': can_withdraw,
        'total_withdrawn': total_withdrawn,  # Already paid out
        'page_obj': page_obj,
        'withdrawals': page_obj.object_list,
        'min_withdrawal': affiliate.program.min_withdrawal,
    }
    
    logger.info(
        f"✅ Withdrawal page viewed: {affiliate.affiliate_code} | "
        f"Balance: ₹{available_balance} | "
        f"Can withdraw: {can_withdraw}"
    )
    
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
