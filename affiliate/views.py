# affiliate/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import models
from decimal import Decimal
import uuid
from .models import (
    AffiliateProgram, AffiliateUser, AffiliateClick, AffiliateOrder,
    AffiliateWithdrawal, AffiliateBanner
)
from orders.models import Order
from django.db.models import Sum



# ============================================================================
# PUBLIC AFFILIATE PAGES
# ============================================================================

def affiliate_home(request):
    """Affiliate program home page"""
    if request.user.is_authenticated:
        try:
            affiliate = AffiliateUser.objects.get(user=request.user)
            # User is already an affiliate - redirect to dashboard
            return redirect('affiliate:dashboard')
        except AffiliateUser.DoesNotExist:
            # User is not an affiliate yet - show the home page
            pass

    program = AffiliateProgram.objects.first()
    banners = AffiliateBanner.objects.filter(is_active=True)
    active_affiliates = AffiliateUser.objects.filter(status='active').count()
    total_commission = AffiliateOrder.objects.filter(
        affiliate__status='active',
        status__in=['confirmed', 'paid']  # adjust statuses as needed
    ).aggregate(
        total=Sum('commission_amount')
    )['total'] or 0
    
    context = {
        'program': program,
        'banners': banners,
        'active_affiliates': active_affiliates,
        'total_commission': total_commission,
    }
    return render(request, 'affiliate/home.html', context)


def affiliate_register(request):
    """Alias for affiliate_join"""
    return affiliate_join(request)


def affiliate_join(request):
    """Apply to affiliate program - single default program"""
    # Get the default program
    program = AffiliateProgram.objects.filter(is_active=True).first()
    
    if not program:
        messages.error(request, 'Affiliate program is currently closed.')
        return redirect('affiliate:home')
    
    # Check if user is already an affiliate
    if request.user.is_authenticated:
        try:
            affiliate = AffiliateUser.objects.get(user=request.user)
            messages.info(request, f'You are already an affiliate! Your code: {affiliate.affiliate_code}')
            return redirect('affiliate:dashboard')
        except AffiliateUser.DoesNotExist:
            pass
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Please login first.')
            return redirect('accounts:login')
        
        try:
            # Automatically use the default program
            affiliate_code = f"{request.user.username}_{uuid.uuid4().hex[:8]}".upper()
            affiliate = AffiliateUser.objects.create(
                user=request.user,
                program=program,
                affiliate_code=affiliate_code,
                status='pending'
            )
            messages.success(request, 'Application submitted successfully! You will be contacted soon.')
            return redirect('affiliate:dashboard')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('affiliate:join')
    
    context = {'program': program}
    return render(request, 'affiliate/join.html', context)


# ============================================================================
# AFFILIATE DASHBOARD & STATS
# ============================================================================

@login_required
def affiliate_dashboard(request):
    """Affiliate dashboard with REAL data"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        messages.info(request, 'You are not an affiliate. Join the program first.')
        return redirect('affiliate:join')
    
    # Real clicks from database
    total_clicks = AffiliateClick.objects.filter(affiliate=affiliate).count()
    
    # Real affiliate orders
    affiliate_orders = AffiliateOrder.objects.filter(affiliate=affiliate)
    total_orders = affiliate_orders.count()
    
    # Real sales amount
    total_sales = affiliate_orders.aggregate(
        total=models.Sum('order_amount')
    )['total'] or Decimal('0')
    
    # Real commission (only confirmed and paid)
    total_commission = affiliate_orders.filter(
        status__in=['confirmed', 'paid']
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # Pending commission
    pending_commission = affiliate_orders.filter(
        status='pending'
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    # Recent orders with order details
    recent_orders = affiliate_orders.select_related('order').order_by('-created_at')[:10]
    
    # Pending withdrawals
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status__in=['pending', 'approved']
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    # Available for withdrawal
    available_for_withdrawal = total_commission - pending_withdrawals
    
    # Top products by sales
    from django.db.models import Count, Sum
    top_products = Order.objects.filter(
        affiliate_code=affiliate.affiliate_code,
        status__in=['delivered', 'confirmed', 'paid']  # adjust to your app
    ).values(
        'items__product_name'
    ).annotate(
        total_quantity=Sum('items__quantity'),
        total_revenue=Sum('items__price')
    ).order_by('-total_revenue')[:5]
    
    context = {
        'affiliate': affiliate,
        'total_clicks': total_clicks,
        'total_orders': total_orders,
        'total_sales': total_sales,
        'total_commission': total_commission,
        'pending_commission': pending_commission,
        'available_for_withdrawal': available_for_withdrawal,
        'recent_orders': recent_orders,
        'pending_withdrawals': pending_withdrawals,
        'top_products': top_products,
    }
    return render(request, 'affiliate/dashboard.html', context)


@login_required
def affiliate_stats(request):
    """Affiliate statistics"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    clicks = AffiliateClick.objects.filter(affiliate=affiliate).order_by('-created_at')
    orders = AffiliateOrder.objects.filter(affiliate=affiliate).order_by('-created_at')
    
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'affiliate': affiliate,
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'total_clicks': clicks.count(),
    }
    return render(request, 'affiliate/stats.html', context)


# ============================================================================
# AFFILIATE REFERRAL TRACKING
# ============================================================================

def track_affiliate_click(request, affiliate_code):
    """Track affiliate click and set cookie"""
    try:
        affiliate = AffiliateUser.objects.get(affiliate_code=affiliate_code, status='active')
    except AffiliateUser.DoesNotExist:
        return redirect('products:home')
    
    visitor_id = str(uuid.uuid4())
    AffiliateClick.objects.create(
        affiliate=affiliate,
        visitor_id=visitor_id,
        referrer_url=request.META.get('HTTP_REFERER', '')
    )
    
    response = redirect('products:home')
    response.set_cookie('affiliate_code', affiliate_code, max_age=60*60*24*30)  # 30 days
    response.set_cookie('visitor_id', visitor_id, max_age=60*60*24*30)
    
    return response


# ============================================================================
# AFFILIATE LINKS & BANNERS
# ============================================================================

@login_required
def affiliate_links(request):
    """Affiliate referral links page"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    banners = AffiliateBanner.objects.filter(is_active=True)
    affiliate_link = f"{request.build_absolute_uri('/affiliate/track/')}{affiliate.affiliate_code}/"
    
    context = {
        'affiliate': affiliate,
        'banners': banners,
        'affiliate_link': affiliate_link,
    }
    return render(request, 'affiliate/links.html', context)


# ============================================================================
# PAYMENTS & WITHDRAWALS
# ============================================================================

@login_required
def affiliate_withdrawals(request):
    """Affiliate withdrawals page"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    # Real commission from confirmed/paid orders
    total_commission = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status__in=['confirmed', 'paid']
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status__in=['pending', 'approved']
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    available_balance = total_commission - pending_withdrawals
    
    withdrawals = AffiliateWithdrawal.objects.filter(affiliate=affiliate).order_by('-requested_at')
    
    paginator = Paginator(withdrawals, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'affiliate': affiliate,
        'total_commission': total_commission,
        'available_balance': available_balance,
        'page_obj': page_obj,
        'withdrawals': page_obj.object_list,
        'min_withdrawal': affiliate.program.min_withdrawal,
    }
    return render(request, 'affiliate/withdrawals.html', context)


@login_required
@require_POST
def request_withdrawal(request):
    """Request withdrawal"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return JsonResponse({'error': 'Not an affiliate'}, status=400)
    
    amount = Decimal(request.POST.get('amount', '0'))
    
    if amount < Decimal(str(affiliate.program.min_withdrawal)):
        return JsonResponse({
            'error': f'Minimum withdrawal amount is ₹{affiliate.program.min_withdrawal}'
        }, status=400)
    
    # Real commission calculation
    total_commission = AffiliateOrder.objects.filter(
        affiliate=affiliate,
        status__in=['confirmed', 'paid']
    ).aggregate(
        total=models.Sum('commission_amount')
    )['total'] or Decimal('0')
    
    pending_withdrawals = AffiliateWithdrawal.objects.filter(
        affiliate=affiliate,
        status__in=['pending', 'approved']
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    available_balance = total_commission - pending_withdrawals
    
    if amount > available_balance:
        return JsonResponse({'error': 'Insufficient balance'}, status=400)
    
    withdrawal = AffiliateWithdrawal.objects.create(
        affiliate=affiliate,
        amount=amount
    )
    
    messages.success(request, f'Withdrawal request of ₹{amount} submitted!')
    return redirect('affiliate:withdrawals')


# ============================================================================
# AFFILIATE SETTINGS
# ============================================================================

@login_required
def affiliate_settings(request):
    """Affiliate settings page"""
    try:
        affiliate = AffiliateUser.objects.get(user=request.user)
    except AffiliateUser.DoesNotExist:
        return redirect('affiliate:join')
    
    if request.method == 'POST':
        affiliate.bank_name = request.POST.get('bank_name', '')
        affiliate.account_holder = request.POST.get('account_holder', '')
        affiliate.account_number = request.POST.get('account_number', '')
        affiliate.ifsc_code = request.POST.get('ifsc_code', '')
        affiliate.save()
        
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
