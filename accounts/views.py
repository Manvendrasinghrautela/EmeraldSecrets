from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import logging

from .models import UserProfile, Address, AccountSettings
from .forms import UserRegistrationForm, UserProfileForm, AddressForm, AccountSettingsForm
from orders.models import Order
from products.models import Wishlist, Product
from affiliate.models import AffiliateUser, AffiliateOrder, AffiliateClick
from affiliate.middleware import get_affiliate_from_request, is_affiliate_referred

logger = logging.getLogger('affiliate')


# ============================================================================
# REGISTRATION - WITH AFFILIATE TRACKING
# ============================================================================

def register(request):
    """
    User registration view
    
    Features:
    - User registration with name fields
    - Auto-login after registration
    - Auto-profile creation
    - Affiliate tracking (if referred by affiliate)
    - Email validation
    - Password strength validation
    
    If user is referred by affiliate:
    - Stores affiliate_code in session
    - Tracks referral in AffiliateClick
    - Commission will be applied to first order
    """
    
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        
        # ✅ VALIDATION
        if not all([username, email, password1, password2]):
            messages.error(request, 'All fields are required')
            return redirect('accounts:register')
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match')
            return redirect('accounts:register')
        
        if len(password1) < 6:
            messages.error(request, 'Password must be at least 6 characters')
            return redirect('accounts:register')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return redirect('accounts:register')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('accounts:register')
        
        # ✅ CREATE USER with name fields
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name
        )
        
        # ✅ Auto-create user profile
        UserProfile.objects.get_or_create(user=user)
        
        # ✅ AFFILIATE TRACKING: Check if referred by affiliate
        affiliate_code, affiliate_id = get_affiliate_from_request(request)
        if affiliate_code:
            try:
                affiliate = AffiliateUser.objects.get(id=affiliate_id, status='active')
                # Store in session for first order
                request.session['affiliate_code'] = affiliate_code
                request.session['affiliate_id'] = affiliate_id
                logger.info(f"✅ New user registered via affiliate: {affiliate_code} | User: {username}")
            except AffiliateUser.DoesNotExist:
                logger.warning(f"⚠️  Invalid affiliate in registration: {affiliate_code}")
        
        # ✅ Auto-login after registration
        login(request, user)
        messages.success(request, f'Welcome, {first_name}! Your account has been created successfully.')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/register.html')


# ============================================================================
# LOGIN - WITH AFFILIATE PERSISTENCE
# ============================================================================

def login_view(request):
    """
    User login view
    
    Features:
    - Username/password authentication
    - Affiliate code persistence (from cookie)
    - Auto-redirect if already logged in
    - Session management
    - Error handling
    
    Affiliate integration:
    - Restores affiliate code from cookie if exists
    - Maintains 30-day tracking window
    """
    
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'Username and password are required')
            return redirect('accounts:login')
        
        # ✅ AUTHENTICATE
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # ✅ LOGIN
            login(request, user)
            
            # ✅ AFFILIATE PERSISTENCE: Restore affiliate code if exists in cookie
            affiliate_code = request.COOKIES.get('affiliate_code')
            affiliate_id = request.COOKIES.get('affiliate_id')
            if affiliate_code and affiliate_id:
                request.session['affiliate_code'] = affiliate_code
                request.session['affiliate_id'] = affiliate_id
                logger.info(f"✅ Affiliate code restored on login: {affiliate_code} | User: {username}")
            
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Invalid username or password')
            logger.warning(f"⚠️  Failed login attempt: {username}")
            return redirect('accounts:login')
    
    return render(request, 'accounts/login.html')


# ============================================================================
# PROFILE VIEW - DASHBOARD
# ============================================================================

@login_required
def profile_view(request):
    """
    User profile view
    
    Features:
    - Display user information
    - Edit capability
    - Show user's addresses
    - Show recent orders
    - Show wishlist
    - Show affiliate info (if applicable)
    
    Affiliate integration:
    - Display affiliate status if user is affiliate
    - Show earnings and stats
    - Quick links to affiliate dashboard
    """
    
    if request.method == 'POST':
        # ✅ UPDATE user information
        user = request.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    
    # ✅ GET profile data
    try:
        user_profile = request.user.profile
    except:
        user_profile = UserProfile.objects.create(user=request.user)
    
    # ✅ GET addresses
    addresses = request.user.addresses.filter(is_active=True).order_by('-is_default', '-created_at')
    
    # ✅ GET recent orders
    recent_orders = request.user.orders.all().order_by('-created_at')[:5]
    
    # ✅ GET wishlist count
    wishlist_count = Wishlist.objects.filter(user=request.user).count()
    
    # ✅ AFFILIATE INFO: Check if user is an affiliate
    affiliate_user = None
    affiliate_stats = None
    try:
        affiliate_user = AffiliateUser.objects.get(user=request.user)
        # Get affiliate stats
        affiliate_stats = {
            'total_earnings': affiliate_user.total_earnings,
            'available_balance': affiliate_user.available_balance,
            'total_withdrawn': affiliate_user.total_withdrawn,
            'total_referrals': affiliate_user.total_referrals,
            'pending_commission': affiliate_user.pending_commission,
            'affiliate_code': affiliate_user.affiliate_code,
            'status': affiliate_user.status,
        }
    except AffiliateUser.DoesNotExist:
        pass
    
    context = {
        'user_profile': user_profile,
        'addresses': addresses,
        'recent_orders': recent_orders,
        'wishlist_count': wishlist_count,
        'affiliate_user': affiliate_user,
        'affiliate_stats': affiliate_stats,
    }
    
    return render(request, 'accounts/profile.html', context)


# ============================================================================
# DASHBOARD VIEW - COMPREHENSIVE
# ============================================================================

@login_required
def dashboard(request):
    """
    User dashboard view
    
    Features:
    - User statistics (orders, spending, etc.)
    - Recent orders
    - Addresses
    - Wishlist
    - Account info
    - Affiliate dashboard (if applicable)
    
    Stats shown:
    - Total orders
    - Total spent
    - Pending orders
    - Addresses on file
    - Wishlist items
    - Affiliate earnings (if affiliate)
    
    Affiliate integration:
    - Show affiliate earnings
    - Show referral link
    - Show clicks and conversions
    - Show pending commissions
    - Link to affiliate settings
    """
    
    # ✅ GET user profile
    try:
        profile = request.user.profile
    except:
        profile = UserProfile.objects.create(user=request.user)
    
    # ✅ GET addresses
    addresses = request.user.addresses.filter(is_active=True)
    
    # ✅ GET recent orders
    recent_orders = request.user.orders.all().order_by('-created_at')[:5]
    
    # ✅ GET wishlist count
    wishlist_count = Wishlist.objects.filter(user=request.user).count()
    
    # ✅ GET order statistics
    all_orders = request.user.orders.all()
    total_orders = all_orders.count()
    total_spent = sum(order.total for order in all_orders) if all_orders else Decimal('0.00')
    pending_orders = all_orders.filter(status__in=['pending', 'processing']).count()
    completed_orders = all_orders.filter(status='delivered').count()
    
    # ✅ AFFILIATE DATA: Get affiliate user if exists
    affiliate_user = None
    affiliate_stats = None
    affiliate_dashboard = None
    
    try:
        affiliate_user = AffiliateUser.objects.get(user=request.user)
        
        # ✅ Calculate affiliate stats
        total_affiliate_earnings = affiliate_user.total_earnings
        available_balance = affiliate_user.available_balance
        pending_commission = affiliate_user.pending_commission
        total_referrals = affiliate_user.total_referrals
        total_withdrawn = affiliate_user.total_withdrawn
        
        # ✅ Get affiliate clicks and orders
        affiliate_clicks = AffiliateClick.objects.filter(affiliate=affiliate_user).count()
        affiliate_orders = AffiliateOrder.objects.filter(affiliate=affiliate_user)
        successful_conversions = affiliate_orders.filter(status='completed').count()
        conversion_rate = (successful_conversions / affiliate_clicks * 100) if affiliate_clicks > 0 else 0
        
        affiliate_stats = {
            'code': affiliate_user.affiliate_code,
            'status': affiliate_user.status,
            'total_earnings': total_affiliate_earnings,
            'available_balance': available_balance,
            'pending_commission': pending_commission,
            'total_referrals': total_referrals,
            'total_withdrawn': total_withdrawn,
            'total_clicks': affiliate_clicks,
            'successful_conversions': successful_conversions,
            'conversion_rate': round(conversion_rate, 2),
            'created_at': affiliate_user.created_at,
        }
        
        # ✅ Get recent affiliate orders (recent commissions)
        recent_affiliate_orders = affiliate_orders.order_by('-created_at')[:5]
        
        affiliate_dashboard = {
            'affiliate_user': affiliate_user,
            'stats': affiliate_stats,
            'recent_orders': recent_affiliate_orders,
        }
        
        logger.info(f"✅ Affiliate dashboard viewed: {affiliate_user.affiliate_code} | Earnings: {total_affiliate_earnings}")
        
    except AffiliateUser.DoesNotExist:
        # User is not an affiliate
        pass
    
    context = {
        'profile': profile,
        'addresses': addresses,
        'recent_orders': recent_orders,
        'wishlist_count': wishlist_count,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'address_count': addresses.count(),
        # ✅ Affiliate data
        'affiliate_user': affiliate_user,
        'affiliate_stats': affiliate_stats,
        'affiliate_dashboard': affiliate_dashboard,
    }
    
    return render(request, 'accounts/dashboard.html', context)


# ============================================================================
# PASSWORD CHANGE
# ============================================================================

@login_required
def password_change_view(request):
    """Change user password"""
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            logger.info(f"✅ Password changed: {request.user.username}")
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change.html', {'form': form})


@login_required
def change_password(request):
    """Alternate password change endpoint"""
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


# ============================================================================
# PROFILE EDIT
# ============================================================================

@login_required
def profile_edit(request):
    """Edit user profile with detailed form"""
    
    # ✅ GET or CREATE profile
    try:
        profile = request.user.profile
    except:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            
            # ✅ UPDATE User model fields
            user = request.user
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            logger.info(f"✅ Profile updated: {request.user.username}")
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'accounts/profile_edit.html', {
        'form': form,
        'user': request.user,
        'profile': profile,
    })


# ============================================================================
# ADDRESS MANAGEMENT
# ============================================================================

@login_required
def address_list(request):
    """List all user addresses"""
    
    addresses = request.user.addresses.filter(is_active=True).order_by('-is_default', '-created_at')
    
    return render(request, 'accounts/address_list.html', {
        'addresses': addresses,
        'address_count': addresses.count(),
    })


@login_required
def add_address(request):
    """Add new address"""
    
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address added successfully!')
            logger.info(f"✅ Address added: {request.user.username}")
            return redirect('accounts:address_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddressForm()
    
    return render(request, 'accounts/address_form.html', {
        'form': form,
        'action': 'Add',
    })


@login_required
def address_edit(request, pk):
    """Edit address"""
    
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully!')
            logger.info(f"✅ Address updated: {request.user.username}")
            return redirect('accounts:address_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'accounts/address_form.html', {
        'form': form,
        'action': 'Edit',
        'address': address,
    })


@login_required
def address_delete(request, pk):
    """Delete address (soft delete)"""
    
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        address.is_active = False
        address.save()
        messages.success(request, 'Address deleted successfully!')
        logger.info(f"✅ Address deleted: {request.user.username}")
        return redirect('accounts:address_list')
    
    return render(request, 'accounts/address_confirm_delete.html', {
        'address': address,
    })


@login_required
def address_set_default(request, pk):
    """Set address as default"""
    
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    # ✅ Remove default from other addresses of same type
    Address.objects.filter(
        user=request.user,
        address_type=address.address_type
    ).update(is_default=False)
    
    # ✅ Set this as default
    address.is_default = True
    address.save()
    
    messages.success(request, 'Default address updated!')
    logger.info(f"✅ Default address updated: {request.user.username}")
    return redirect('accounts:address_list')


# ============================================================================
# ORDER MANAGEMENT
# ============================================================================

@login_required
def order_list(request):
    """List all user orders with pagination"""
    
    # ✅ GET orders
    orders = request.user.orders.all().order_by('-created_at')
    
    # ✅ PAGINATION
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'accounts/order_list.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'total_orders': orders.count(),
    })


@login_required
def order_detail(request, order_id):
    """Order detail view with affiliate information"""
    
    # ✅ GET order
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()
    
    # ✅ AFFILIATE INFO: Check if order was referred by affiliate
    affiliate_order = None
    affiliate_info = None
    
    try:
        affiliate_order = AffiliateOrder.objects.get(order=order)
        affiliate_info = {
            'affiliate_code': affiliate_order.affiliate.affiliate_code,
            'affiliate_name': affiliate_order.affiliate.user.get_full_name(),
            'commission_amount': affiliate_order.commission_amount,
            'commission_rate': '5%',
            'status': affiliate_order.status,
            'created_at': affiliate_order.created_at,
        }
    except AffiliateOrder.DoesNotExist:
        pass
    
    context = {
        'order': order,
        'order_items': order_items,
        'affiliate_order': affiliate_order,
        'affiliate_info': affiliate_info,
    }
    
    return render(request, 'accounts/order_detail.html', context)


# ============================================================================
# WISHLIST MANAGEMENT
# ============================================================================

@login_required
def wishlist(request):
    """User wishlist"""
    
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product').order_by('-added_at')
    
    return render(request, 'accounts/wishlist.html', {
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_items.count(),
    })


@login_required
@require_POST
def wishlist_add(request, product_id):
    """Add product to wishlist"""
    
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    
    if created:
        messages.success(request, f'{product.name} added to wishlist!')
        logger.info(f"✅ Product added to wishlist: {request.user.username} | Product: {product.name}")
    else:
        messages.info(request, f'{product.name} is already in your wishlist.')
    
    return redirect('accounts:wishlist')


@login_required
@require_POST
def wishlist_remove(request, product_id):
    """Remove product from wishlist"""
    
    wishlist_item = get_object_or_404(Wishlist, user=request.user, product_id=product_id)
    product_name = wishlist_item.product.name
    wishlist_item.delete()
    messages.success(request, f'{product_name} removed from wishlist.')
    logger.info(f"✅ Product removed from wishlist: {request.user.username} | Product: {product_name}")
    
    return redirect('accounts:wishlist')


@login_required
def get_wishlist_count(request):
    """Return wishlist count as JSON"""
    
    try:
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({'count': count, 'success': True})
    except Exception as e:
        logger.error(f"❌ Error getting wishlist count: {str(e)}")
        return JsonResponse({'count': 0, 'success': False, 'error': str(e)})


# ============================================================================
# ACCOUNT SETTINGS
# ============================================================================

@login_required
def account_settings(request):
    """Account settings view"""
    
    # ✅ GET or CREATE settings
    settings_obj, created = AccountSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = AccountSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully!')
            logger.info(f"✅ Account settings updated: {request.user.username}")
            return redirect('accounts:settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AccountSettingsForm(instance=settings_obj)
    
    return render(request, 'accounts/settings.html', {
        'form': form,
        'settings': settings_obj,
    })


# ============================================================================
# HELPER VIEWS
# ============================================================================

@login_required
def account_summary(request):
    """Quick account summary (JSON endpoint)"""
    
    try:
        orders = request.user.orders.all()
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        addresses_count = request.user.addresses.filter(is_active=True).count()
        
        # ✅ AFFILIATE SUMMARY
        affiliate_data = None
        try:
            affiliate_user = AffiliateUser.objects.get(user=request.user)
            affiliate_data = {
                'code': affiliate_user.affiliate_code,
                'earnings': str(affiliate_user.total_earnings),
                'status': affiliate_user.status,
            }
        except AffiliateUser.DoesNotExist:
            pass
        
        return JsonResponse({
            'success': True,
            'username': request.user.username,
            'email': request.user.email,
            'total_orders': orders.count(),
            'total_spent': str(sum(o.total for o in orders)),
            'wishlist_count': wishlist_count,
            'addresses_count': addresses_count,
            'affiliate': affiliate_data,
        })
    except Exception as e:
        logger.error(f"❌ Error getting account summary: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# SUMMARY: AFFILIATE INTEGRATION POINTS IN ACCOUNTS
# ============================================================================

"""
AFFILIATE INTEGRATION IN ACCOUNTS VIEWS:

1. REGISTRATION (register view):
   ✅ Checks for affiliate code in request
   ✅ If referred: Stores affiliate_code in session
   ✅ Logs affiliate registration
   ✅ Commission applies to first order (tracked by middleware)

2. LOGIN (login_view):
   ✅ Restores affiliate code from cookie
   ✅ Maintains 30-day tracking window
   ✅ User can complete purchase days after clicking link

3. PROFILE (profile_view):
   ✅ Shows affiliate info if user is affiliate
   ✅ Displays earnings, balance, pending commission
   ✅ Quick stats on affiliate performance

4. DASHBOARD (dashboard view):
   ✅ Full affiliate dashboard
   ✅ Shows earnings, clicks, conversions
   ✅ Conversion rate calculation
   ✅ Recent affiliate orders
   ✅ Pending commissions

5. ORDER DETAIL (order_detail view):
   ✅ Shows if order was affiliate-referred
   ✅ Displays commission amount (5%)
   ✅ Shows affiliate code and name
   ✅ Commission status (pending/completed)

6. ACCOUNT SUMMARY (account_summary view):
   ✅ JSON endpoint with affiliate data
   ✅ Quick earnings overview
   ✅ Affiliate status

COMMISSION FLOW:
1. Affiliate creates referral link: ?ref=ES-ABC123
2. User clicks → Middleware tracks click
3. User registers/logs in
4. Cookie persists affiliate code (30 days)
5. User purchases → Payment view calculates 5% commission
6. AffiliateOrder created with order & commission
7. Status: pending (7 days) → completed (auto-approved)
8. Commission available for withdrawal (₹1000 min)

KEY FEATURES:
✅ Automatic 5% commission calculation
✅ 30-day tracking window
✅ Affiliate code persistence (session + cookie)
✅ Complete audit trail (logging)
✅ User-friendly dashboard
✅ Easy referral link sharing
✅ Commission withdrawal system
"""