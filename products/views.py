# products/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import (
    Category, Collection, Product, ProductImage, 
    Wishlist, Newsletter, ContactMessage, Review
)
from orders.models import Cart, CartItem, Order, OrderItem
from accounts.models import Address
from decimal import Decimal


# ============================================================================
# HOME AND GENERAL VIEWS
# ============================================================================

def home(request):
    """Home page view"""
    featured_products = Product.objects.filter(is_active=True, is_featured=True)[:8]
    featured_collections = Collection.objects.filter(is_active=True, featured=True)[:3]
    
    context = {
        'featured_products': featured_products,
        'featured_collections': featured_collections,
    }
    return render(request, 'products/home.html', context)


def about(request):
    """About page view"""
    return render(request, 'products/about.html')


def contact(request):
    """Contact page view"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Create contact message (triggers email signals)
        ContactMessage.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )
        
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('products:home')
    
    return render(request, 'products/contact.html')


# ============================================================================
# PRODUCT VIEWS
# ============================================================================

def product_list(request):
    """List all products with filtering and pagination"""
    products = Product.objects.filter(is_active=True).order_by('-created_at')

    # Category filter
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    # Price filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Search filter
    search = request.GET.get('search')
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search) |
            Q(short_description__icontains=search)
        )

    # Sort
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'created_at', 'price', '-price', 'name']
    if sort_by in valid_sorts:
        products = products.order_by(sort_by)

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get categories for filter
    categories = Category.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'categories': categories,
        'search': search,
        'selected_category': category_slug,
    }
    return render(request, 'products/product_list.html', context)


def product_detail(request, slug):
    """Product detail view"""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # Get related products
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True
    ).exclude(id=product.id)[:4]
    
    # Get product reviews
    reviews = product.reviews.filter(is_approved=True).select_related('user').order_by('-created_at')
    review_stats = reviews.aggregate(
        average_rating=Avg('rating'),
        review_count=Count('id')
    )
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = reviews.count()

    related_products = Product.objects.filter(
        category=product.category,
        is_active=True
    ).exclude(id=product.id)[:4]
    
    # Check if user has wishlisted this product
    is_wishlist = False
    if request.user.is_authenticated:
        is_wishlist = Wishlist.objects.filter(
            user=request.user,
            product=product
        ).exists()
    
    context = {
        'product': product,
        'reviews': reviews,
        'average_rating': round(average_rating, 1),
        'review_count': review_count,
        'related_products': related_products,
        'is_wishlist': is_wishlist,
    }
    return render(request, 'products/product_detail.html', context)


# ============================================================================
# CATEGORY AND COLLECTION VIEWS
# ============================================================================

def category_list(request):
    """List all categories"""
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'categories': categories,
    }
    return render(request, 'products/category_list.html', context)


def category_detail(request, slug):
    """Category detail view with products"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = category.products.filter(is_active=True)
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'products': page_obj.object_list,
    }
    return render(request, 'products/category_detail.html', context)


def collection_list(request):
    """List all collections"""
    collections = Collection.objects.filter(is_active=True)
    
    context = {
        'collections': collections,
    }
    return render(request, 'products/collection_list.html', context)


def collection_detail(request, slug):
    """Collection detail view with products"""
    collection = get_object_or_404(Collection, slug=slug, is_active=True)
    products = collection.products.filter(is_active=True)
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'collection': collection,
        'page_obj': page_obj,
        'products': page_obj.object_list,
    }
    return render(request, 'products/collection_detail.html', context)


# ============================================================================
# REVIEW VIEWS
# ============================================================================

@login_required
def create_review(request, product_id):
    """Create a product review"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        title = request.POST.get('title', '')
        comment = request.POST.get('comment')
        
        if not rating or not comment:
            messages.error(request, 'Please provide both rating and review comment.')
            return redirect('products:product_detail', slug=product.slug)

        # Check if user already reviewed this product
        existing_review = Review.objects.filter(
            product=product,
            user=request.user
        ).exists()
        
        if existing_review:
            messages.error(request, 'You have already reviewed this product.')
            return redirect('products:product_detail', slug=product.slug)
        
        # Create review
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            title=title,
            comment=comment,
            is_approved=True
        )
        
        messages.success(request, 'Your review has been submitted and is awaiting approval.')
        return redirect('products:product_detail', slug=product.slug)
    
    context = {
        'product': product,
        'reviews': reviews,
    }
    return render(request, 'products/create_review.html', context)


# ============================================================================
# WISHLIST VIEWS
# ============================================================================

@login_required
@require_POST
def wishlist_toggle(request, product_id):
    """Add/Remove product from wishlist (AJAX-compatible)"""
    product = get_object_or_404(Product, id=product_id)
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if not created:
        wishlist_item.delete()
        added = False
        message = f'{product.name} removed from wishlist.'
    else:
        added = True
        message = f'{product.name} added to wishlist!'
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'message': message})
    
    # Non-AJAX response
    messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'products:product_list'))


# ============================================================================
# NEWSLETTER VIEWS
# ============================================================================

@require_POST
def newsletter_subscribe(request):
    """Subscribe to newsletter"""
    email = request.POST.get('email')
    
    if not email:
        messages.error(request, 'Please enter a valid email.')
        return redirect('products:home')
    
    newsletter, created = Newsletter.objects.get_or_create(email=email)
    
    if created:
        messages.success(request, 'Successfully subscribed to our newsletter!')
    else:
        if newsletter.is_active:
            messages.info(request, 'You are already subscribed.')
        else:
            newsletter.is_active = True
            newsletter.save()
            messages.success(request, 'Welcome back! Your subscription is active again.')
    
    return redirect('products:home')


@require_POST
def newsletter_unsubscribe(request):
    """Unsubscribe from newsletter"""
    email = request.POST.get('email')
    
    try:
        newsletter = Newsletter.objects.get(email=email)
        newsletter.is_active = False
        newsletter.save()
        messages.success(request, 'You have been unsubscribed from our newsletter.')
    except Newsletter.DoesNotExist:
        messages.error(request, 'Email not found in our subscription list.')
    
    return redirect('products:home')


# ============================================================================
# SEARCH VIEWS
# ============================================================================

def search(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(is_active=True)

    if query:
        terms = query.split()
        q = Q()
        for term in terms:
            q |= (
                Q(name__icontains=term) |
                Q(short_description__icontains=term) |
                Q(description__icontains=term) |
                Q(category__name__icontains=term)
            )
        products = products.filter(q).distinct()

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'query': query,
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'results_count': paginator.count,  # Total count of results

    }
    return render(request, 'products/search.html', context)


# ============================================================================
# CART HELPER FUNCTION
# ============================================================================

def get_or_create_cart(request):
    """Get or create cart for user or session"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart


# ============================================================================
# CART VIEWS
# ============================================================================

def cart_view(request):
    """View shopping cart"""
    cart = get_or_create_cart(request)
    cart_items = cart.orderitems.all()  # FIXED: Changed from cart.items to cart.orderitems
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': cart.subtotal,
        'shipping': cart.shipping,
        'tax': cart.tax,
        'total': cart.total,
    }
    return render(request, 'products/cart.html', context)


@require_POST
def add_to_cart(request, item_id):  # FIXED: Changed parameter name to match URL
    """Add product to cart"""
    product = get_object_or_404(Product, id=item_id)
    quantity = int(request.POST.get('quantity', 1))
    
    cart = get_or_create_cart(request)
    
    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    messages.success(request, f'{product.name} added to cart!')
    return redirect('products:cart')


@require_POST
def remove_from_cart(request, item_id):
    """Remove item from cart (using CartItem ID)"""
    cart = get_or_create_cart(request)
    # Filter by the user's cart, not all items
    cart_item = get_object_or_404(cart.orderitems, id=item_id)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f'{product_name} removed from cart!')
    return redirect('products:cart')


@require_POST
def update_cart(request, item_id):
    """Update cart item quantity (using CartItem ID)"""
    cart = get_or_create_cart(request)
    # Filter by the user's cart, not all items
    cart_item = get_object_or_404(cart.orderitems, id=item_id)
    action = request.POST.get('action', 'set')
    
    if action == 'increase':
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, 'Cart updated!')
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
            messages.success(request, 'Cart updated!')
        else:
            cart_item.delete()
            messages.info(request, 'Item removed from cart.')
            return redirect('products:cart')
    elif action == 'set':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Cart updated!')
        else:
            cart_item.delete()
            messages.info(request, 'Item removed from cart.')
            return redirect('products:cart')
    else:
        messages.warning(request, 'Unknown action.')

    return redirect('products:cart')


# ============================================================================
# CHECKOUT VIEWS
# ============================================================================

@login_required
def checkout(request):
    """Checkout page"""
    # Get user cart
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('products:cart')
    
    # Initialize affiliate_code at function start
    affiliate_code = None
    
    # Get cart and items
    cart = get_or_create_cart(request)
    cart_items = cart.orderitems.all()
    
    # Redirect if cart is empty
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('orders:cart')
    
    # Get user's shipping addresses
    addresses = request.user.addresses.filter(is_active=True)
    
    if request.method == 'POST':
        # ====== ORDER SUBMISSION ======
        address_id = request.POST.get('address', '').strip()
        payment_method = request.POST.get('payment_method', 'card')
        
        # ====== VALIDATE ADDRESS SELECTION ======
        if not address_id:
            messages.error(request, 'Please select a shipping address.')
            context = get_checkout_context(cart, cart_items, addresses)
            return render(request, 'orders/checkout.html', context)
        
        # Convert to integer and validate format
        try:
            address_id = int(address_id)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid address format. Please select a valid address.')
            context = get_checkout_context(cart, cart_items, addresses)
            return render(request, 'orders/checkout.html', context)
        
        # ====== GET AND VERIFY ADDRESS ======
        try:
            address = Address.objects.get(id=address_id, user=request.user, is_active=True)
        except Address.DoesNotExist:
            messages.error(request, 'Selected address not found. Please choose a valid address.')
            context = get_checkout_context(cart, cart_items, addresses)
            return render(request, 'orders/checkout.html', context)
        
        # ====== VALIDATE ADDRESS HAS REQUIRED FIELDS ======
        required_fields = ['first_name', 'last_name', 'phone', 'email', 
                          'address_line1', 'city', 'state', 'postal_code', 'country']
        missing_fields = [field for field in required_fields if not getattr(address, field, None)]
        
        if missing_fields:
            messages.error(request, f'Selected address is incomplete. Missing: {", ".join(missing_fields)}. Please edit or add a new address.')
            context = get_checkout_context(cart, cart_items, addresses)
            return render(request, 'orders/checkout.html', context)
        
        # ====== CALCULATE TOTALS ======
        shipping_cost = Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0")
        tax = cart.subtotal * Decimal("0.0665")
        
        # Calculate discount from coupon
        discount = Decimal("0")
        if 'applied_coupon' in request.session:
            coupon_code = request.session['applied_coupon']
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                if coupon.discount_type == 'percentage':
                    discount = (cart.subtotal * Decimal(str(coupon.discount_value))) / Decimal("100")
                else:
                    discount = Decimal(str(coupon.discount_value))
            except Coupon.DoesNotExist:
                pass
        
        total = cart.subtotal + shipping_cost + tax - discount
        
        # ====== GET AFFILIATE CODE ======
        affiliate_code = request.GET.get('ref') or request.COOKIES.get('affiliate_code')
        
        # ====== CREATE ORDER ======
        try:
            with transaction.atomic():
                # Create order
                order = Order.objects.create(
                    user=request.user,
                    subtotal=cart.subtotal,
                    shipping_cost=shipping_cost,
                    tax=tax,
                    discount=discount,
                    total=total,
                    shipping_first_name=address.first_name,
                    shipping_last_name=address.last_name,
                    shipping_phone=address.phone,
                    shipping_email=address.email,
                    shipping_address_line1=address.address_line1,
                    shipping_address_line2=address.address_line2 or '',
                    shipping_city=address.city,
                    shipping_state=address.state,
                    shipping_postal_code=address.postal_code,
                    shipping_country=address.country,
                    payment_method=payment_method,
                    affiliate_code=affiliate_code,
                )
                
                # Create order items
                for cart_item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        product_name=cart_item.product.name,
                        product_sku=cart_item.product.sku or '',
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                    )
                
                # ====== TRACK AFFILIATE COMMISSION ======
                if affiliate_code:
                    try:
                        affiliate = AffiliateUser.objects.get(
                            affiliate_code=affiliate_code,
                            status='active'
                        )
                        
                        program = affiliate.program
                        commission_rate = Decimal(str(program.commission_rate)) / Decimal("100")
                        commission_amount = total * commission_rate
                        
                        affiliate_order = AffiliateOrder.objects.create(
                            affiliate=affiliate,
                            order=order,
                            order_amount=total,
                            commission_rate=program.commission_rate,
                            commission_amount=commission_amount,
                            status='pending'
                        )
                        
                        AffiliateTransaction.objects.create(
                            affiliate=affiliate,
                            transaction_type='earning',
                            amount=commission_amount,
                            description=f"Commission from Order #{order.order_number}",
                            related_order=affiliate_order,
                            balance_after=affiliate.available_balance + commission_amount
                        )
                        
                        affiliate.total_referrals += 1
                        affiliate.save()
                        
                    except AffiliateUser.DoesNotExist:
                        pass
                
                # ====== CREATE PAYMENT RECORD ======
                Payment.objects.create(
                    order=order,
                    payment_method=payment_method,
                    amount=total,
                )
                
                # ====== CLEANUP ======
                order.send_order_confirmation_email()
                cart_items.delete()
                
                if 'applied_coupon' in request.session:
                    del request.session['applied_coupon']
                
                messages.success(request, f'Order #{order.order_number} placed successfully!')
                response = redirect('orders:order_detail', order_id=order.id)
                response.delete_cookie('affiliate_code')
                return response
                
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
            return redirect('orders:checkout')
    
    # ====== GET REQUEST - DISPLAY CHECKOUT PAGE ======
    context = get_checkout_context(cart, cart_items, addresses)
    return render(request, 'orders/checkout.html', context)


def get_checkout_context(cart, cart_items, addresses):
    """Helper function to build checkout context"""
    subtotal = cart.subtotal
    shipping = Decimal("50") if subtotal < Decimal("500") else Decimal("0")
    tax = subtotal * Decimal("0.0665")
    
    # Get coupon discount if applied
    discount = Decimal("0")
    applied_coupon = None
    if 'applied_coupon' in request.session:
        coupon_code = request.session['applied_coupon']
        try:
            applied_coupon = Coupon.objects.get(code=coupon_code)
            if applied_coupon.discount_type == 'percentage':
                discount = (subtotal * Decimal(str(applied_coupon.discount_value))) / Decimal("100")
            else:
                discount = Decimal(str(applied_coupon.discount_value))
        except Coupon.DoesNotExist:
            pass
    
    total = subtotal + shipping + tax - discount
    
    return {
        'cart': cart,
        'cart_items': cart_items,
        'addresses': addresses,
        'subtotal': subtotal,
        'shipping': shipping,
        'tax': tax,
        'discount': discount,
        'total': total,
        'applied_coupon': applied_coupon,
    }
