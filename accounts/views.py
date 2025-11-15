from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import UserProfile, Address, AccountSettings
from .forms import UserRegistrationForm, UserProfileForm, AddressForm, AccountSettingsForm
from orders.models import Order
from products.models import Wishlist
from django.http import JsonResponse


# ============================================================================
# REGISTRATION - FIXED
# ============================================================================
def register(request):
    """User registration view - Auto-fills profile on registration"""
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Validate
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
        
        # Create user with first_name and last_name
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name
        )
        
        # Auto-login after registration
        login(request, user)
        messages.success(request, f'Welcome, {first_name}! Your account has been created successfully.')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/register.html')


# ============================================================================
# LOGIN - FIXED
# ============================================================================
def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, 'Username and password are required')
            return redirect('accounts:login')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('accounts:login')
    
    return render(request, 'accounts/login.html')


# ============================================================================
# PROFILE - UPDATED TO HANDLE FORM SUBMISSION
# ============================================================================
@login_required
def profile_view(request):
    """User profile view with edit capability"""
    if request.method == 'POST':
        # Update user information
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile.html')


# ============================================================================
# PASSWORD CHANGE
# ============================================================================
@login_required
def password_change_view(request):
    """Password change view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change.html', {'form': form})


@login_required
def change_password(request):
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
    """Edit user profile"""
    try:
        profile = request.user.profile
    except:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            
            # Update User model fields
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'accounts/profile_edit.html', {'form': form, 'user': request.user})


# ============================================================================
# ADDRESS VIEWS
# ============================================================================
@login_required
def address_list(request):
    """List all user addresses"""
    addresses = request.user.addresses.filter(is_active=True).order_by('-is_default', '-created_at')
    return render(request, 'accounts/address_list.html', {'addresses': addresses})


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
            return redirect('accounts:address_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddressForm()
    
    return render(request, 'accounts/address_form.html', {'form': form, 'action': 'Add'})


@login_required
def address_edit(request, pk):
    """Edit address"""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('accounts:address_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'accounts/address_form.html', {'form': form, 'action': 'Edit', 'address': address})


@login_required
def address_delete(request, pk):
    """Delete address (soft delete)"""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        address.is_active = False
        address.save()
        messages.success(request, 'Address deleted successfully!')
        return redirect('accounts:address_list')
    
    return render(request, 'accounts/address_confirm_delete.html', {'address': address})


@login_required
def address_set_default(request, pk):
    """Set address as default"""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    # Remove default from all other addresses
    Address.objects.filter(user=request.user, address_type=address.address_type).update(is_default=False)
    
    # Set this as default
    address.is_default = True
    address.save()
    
    messages.success(request, 'Default address updated!')
    return redirect('accounts:address_list')


# ============================================================================
# ORDERS VIEWS
# ============================================================================
@login_required
def order_list(request):
    """List all user orders"""
    orders = request.user.orders.all().order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'accounts/order_list.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
    })


@login_required
def order_detail(request, order_id):
    """Order detail view"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()
    
    return render(request, 'accounts/order_detail.html', {'order': order, 'order_items': order_items})


# ============================================================================
# WISHLIST VIEWS
# ============================================================================
@login_required
def wishlist(request):
    """User wishlist"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product').order_by('-added_at')
    return render(request, 'accounts/wishlist.html', {'wishlist_items': wishlist_items})


@login_required
@require_POST
def wishlist_add(request, product_id):
    """Add product to wishlist"""
    from products.models import Product
    
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    
    if created:
        messages.success(request, f'{product.name} added to wishlist!')
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
    
    return redirect('accounts:wishlist')


@login_required
def get_wishlist_count(request):
    """Return wishlist count as JSON"""
    try:
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({'count': count})
    except:
        return JsonResponse({'count': 0})


# ============================================================================
# SETTINGS VIEWS
# ============================================================================
@login_required
def account_settings(request):
    """Account settings view"""
    settings, created = AccountSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = AccountSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully!')
            return redirect('accounts:settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AccountSettingsForm(instance=settings)
    
    return render(request, 'accounts/settings.html', {'form': form, 'settings': settings})


# ============================================================================
# DASHBOARD VIEW
# ============================================================================
@login_required
def dashboard(request):
    """User dashboard view"""
    try:
        profile = request.user.profile
    except:
        profile = UserProfile.objects.create(user=request.user)
    
    addresses = request.user.addresses.filter(is_active=True)
    recent_orders = request.user.orders.all().order_by('-created_at')[:3]
    wishlist_count = Wishlist.objects.filter(user=request.user).count()
    
    # Stats
    total_orders = request.user.orders.count()
    total_spent = sum(order.total for order in request.user.orders.all())
    pending_orders = request.user.orders.filter(status__in=['pending', 'processing']).count()
    
    return render(request, 'accounts/dashboard.html', {
        'profile': profile,
        'addresses': addresses,
        'recent_orders': recent_orders,
        'wishlist_count': wishlist_count,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'pending_orders': pending_orders,
    })
