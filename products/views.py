# products/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg
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
    reviews = product.reviews.filter(is_approved=True).order_by('-created_at')
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = reviews.count()
    
    # Check if user has wishlisted this product
    is_wishlist = False
    if request.user.is_authenticated:
        is_wishlist = Wishlist.objects.filter(
            user=request.user,
            product=product
        ).exists()
    
    context = {
        'product': product,
        'related_products': related_products,
        'reviews': reviews,
        'average_rating': average_rating,
        'review_count': review_count,
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
            comment=comment
        )
        
        messages.success(request, 'Your review has been submitted and is awaiting approval.')
        return redirect('products:product_detail', slug=product.slug)
    
    context = {
        'product': product,
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
    
    cart_items = cart.orderitems.all()  # FIXED: Changed from cart.items to cart.orderitems
    
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('products:cart')
    
    # Get user addresses
    addresses = request.user.addresses.filter(is_active=True)
    default_address = addresses.filter(is_default=True).first()
    
    if request.method == 'POST':
        # Process order
        address_id = request.POST.get('address')
        payment_method = request.POST.get('payment_method', 'card')
        
        if not address_id:
            messages.error(request, 'Please select a shipping address.')
            return render(request, 'products/checkout.html', {
                'cart': cart,
                'cart_items': cart_items,
                'addresses': addresses,
                'default_address': default_address,
            })
        
        address = get_object_or_404(Address, id=address_id, user=request.user)
        
        # Create order
        order = Order.objects.create(
            user=request.user,
            subtotal=cart.subtotal,
            shipping_cost=cart.shipping,
            tax=cart.tax,
            total=cart.total,
            shipping_first_name=address.first_name,
            shipping_last_name=address.last_name,
            shipping_phone=address.phone,
            shipping_email=address.email,
            shipping_address_line1=address.address_line1,
            shipping_address_line2=address.address_line2,
            shipping_city=address.city,
            shipping_state=address.state,
            shipping_postal_code=address.postal_code,
            shipping_country=address.country,
            payment_method=payment_method,
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
        
        # Send order confirmation email
        try:
            order.send_order_confirmation_email()
        except:
            pass
        
        # Clear cart
        cart_items.delete()
        
        messages.success(request, f'Order #{order.order_number} placed successfully!')
        return redirect('orders:order_detail', order_id=order.id)
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'addresses': addresses,
        'default_address': default_address,
    }
    return render(request, 'products/checkout.html', context)
