# orders/views.py - FULLY CORRECTED
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Cart, CartItem, Order, OrderItem, Payment, Coupon
from products.models import Product
from decimal import Decimal
from affiliate.models import AffiliateUser, AffiliateOrder
import json
from .utils import get_or_create_cart
from accounts.models import Address
from django.db import transaction


# ============================================================================
# HELPER FUNCTION
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
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    
    return cart


# ============================================================================
# CART VIEWS
# ============================================================================

@login_required
def cart_view(request):
    """View shopping cart"""
    cart = get_or_create_cart(request)
    # FIXED: Use orderitems consistently
    cart_items = cart.orderitems.all()
    
    subtotal = cart.subtotal
    shipping = Decimal("50") if subtotal < Decimal("500") else Decimal("0")
    tax = subtotal * Decimal("0.0665")
    total = subtotal + shipping + tax

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping': shipping,
        'tax': tax,
        'total': total,
    }
    return render(request, 'orders/cart.html', context)


def get_cart_count(request):
    """Get cart item count for display in navbar"""
    try:
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'count': 0})
            cart, created = Cart.objects.get_or_create(session_key=session_key)
        
        # FIXED: Use orderitems consistently
        count = sum(item.quantity for item in cart.orderitems.all())
        return JsonResponse({'count': count})
    except Exception as e:
        return JsonResponse({'count': 0})


@login_required
def add_to_cart(request, product_id):
    """Add product to cart"""
    product = get_object_or_404(Product, id=product_id, is_active=True)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity < 1:
        messages.error(request, 'Invalid quantity.')
        return redirect('products:product_detail', slug=product.slug)
    
    if quantity > product.stock:
        messages.error(request, f'Only {product.stock} items available.')
        return redirect('products:product_detail', slug=product.slug)
    
    cart = get_or_create_cart(request)
    
    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        if cart_item.quantity + quantity > product.stock:
            messages.error(request, f'Only {product.stock} items available in total.')
            return redirect('orders:cart')
        cart_item.quantity += quantity
        cart_item.save()
        messages.success(request, f'{product.name} quantity updated in cart!')
    else:
        messages.success(request, f'{product.name} added to cart!')
    
    return redirect('orders:cart')


@login_required
def remove_from_cart(request, product_id):
    """Remove product from cart"""
    product = get_object_or_404(Product, id=product_id)
    cart = get_or_create_cart(request)
    
    CartItem.objects.filter(cart=cart, product=product).delete()
    messages.success(request, f'{product.name} removed from cart.')
    
    return redirect('orders:cart')


@login_required
def update_cart_item(request, product_id):
    """Update cart item quantity"""
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    
    cart = get_or_create_cart(request)
    
    if quantity <= 0:
        CartItem.objects.filter(cart=cart, product=product).delete()
        messages.success(request, f'{product.name} removed from cart.')
    else:
        if quantity > product.stock:
            messages.error(request, f'Only {product.stock} items available.')
            return redirect('orders:cart')
        
        cart_item = get_object_or_404(CartItem, cart=cart, product=product)
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, f'{product.name} quantity updated.')
    
    return redirect('orders:cart')


@login_required
def clear_cart(request):
    """Clear entire cart"""
    cart = get_or_create_cart(request)
    # FIXED: Use orderitems consistently
    cart.orderitems.all().delete()
    messages.success(request, 'Cart cleared.')
    
    return redirect('orders:cart')


# ============================================================================
# COUPON VIEWS
# ============================================================================

@login_required
def apply_coupon(request):
    """Apply coupon to cart"""
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').upper()
        cart = get_or_create_cart(request)
        
        try:
            coupon = Coupon.objects.get(code=code)
            
            if not coupon.is_valid:
                messages.error(request, 'This coupon is no longer valid.')
                return redirect('orders:cart')
            
            if cart.subtotal < coupon.min_purchase:
                messages.error(request, f'Minimum purchase of ₹{coupon.min_purchase} required.')
                return redirect('orders:cart')
            
            request.session['applied_coupon'] = code
            coupon.uses_count += 1
            coupon.save()
            
            # Calculate discount
            if coupon.discount_type == 'percentage':
                discount = (cart.subtotal * Decimal(str(coupon.discount_value))) / Decimal("100")
            else:
                discount = Decimal(str(coupon.discount_value))
            
            messages.success(request, f'Coupon applied! You save ₹{discount}')
            
        except Coupon.DoesNotExist:
            messages.error(request, 'Invalid coupon code.')
    
    return redirect('orders:cart')


@login_required
def remove_coupon(request):
    """Remove applied coupon"""
    if 'applied_coupon' in request.session:
        code = request.session['applied_coupon']
        del request.session['applied_coupon']
        messages.success(request, 'Coupon removed.')
    
    return redirect('orders:cart')


# ============================================================================
# CHECKOUT VIEWS
# ============================================================================

@login_required
def checkout(request):
    """Checkout page with affiliate tracking"""
    affiliate_code = None
    
    cart = get_or_create_cart(request)
    cart_items = cart.orderitems.all()
    
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('orders:cart')
    
    addresses = request.user.addresses.filter(is_active=True)
    
    if request.method == 'POST':
        address_id = request.POST.get('address', '').strip()
        payment_method = request.POST.get('payment_method', 'card')
        
        # ====== VALIDATE ADDRESS ======
        if not address_id:
            messages.error(request, 'Please select a shipping address.')
            context = {
                'cart': cart,
                'cart_items': cart_items,
                'addresses': addresses,
                'subtotal': cart.subtotal,
                'shipping': Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0"),
                'tax': cart.subtotal * Decimal("0.0665"),
                'total': cart.total,
            }
            return render(request, 'orders/checkout.html', context)
        
        # Convert to integer and validate
        try:
            address_id = int(address_id)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid address format. Please select a valid address.')
            context = {
                'cart': cart,
                'cart_items': cart_items,
                'addresses': addresses,
                'subtotal': cart.subtotal,
                'shipping': Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0"),
                'tax': cart.subtotal * Decimal("0.0665"),
                'total': cart.total,
            }
            return render(request, 'orders/checkout.html', context)
        
        # Get address and verify it belongs to user
        try:
            address = Address.objects.get(id=address_id, user=request.user, is_active=True)
        except Address.DoesNotExist:
            messages.error(request, 'Address not found or is inactive. Please select a valid address.')
            context = {
                'cart': cart,
                'cart_items': cart_items,
                'addresses': addresses,
                'subtotal': cart.subtotal,
                'shipping': Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0"),
                'tax': cart.subtotal * Decimal("0.0665"),
                'total': cart.total,
            }
            return render(request, 'orders/checkout.html', context)

        # Get address and verify ownership
        try:
            address = Address.objects.get(id=address_id, user=request.user, is_active=True)
        except Address.DoesNotExist:
            messages.error(request, 'Selected address not found. Please choose a valid address.')
            context = {
                'cart': cart,
                'cart_items': cart_items,
                'addresses': addresses,
                'subtotal': cart.subtotal,
                'shipping': Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0"),
                'tax': cart.subtotal * Decimal("0.0665"),
                'total': cart.total,
            }
            return render(request, 'orders/checkout.html', context)        
        
        # ====== CALCULATE TOTALS ======
        shipping_cost = Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0")
        tax = cart.subtotal * Decimal("0.0665")
        
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
        
        # Get affiliate code
        affiliate_code = request.GET.get('ref') or request.COOKIES.get('affiliate_code')
        
        # ====== CREATE ORDER ======
        try:
            with transaction.atomic():
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
                
                # Track affiliate
                if affiliate_code:
                    try:
                        from affiliate.models import AffiliateUser, AffiliateOrder, AffiliateTransaction
                        
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
                
                # Create payment
                Payment.objects.create(
                    order=order,
                    payment_method=payment_method,
                    amount=total,
                )
                
                # Send email and cleanup
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
    
    # ====== GET REQUEST ======
    subtotal = cart.subtotal
    shipping = Decimal("50") if subtotal < Decimal("500") else Decimal("0")
    tax = subtotal * Decimal("0.0665")
    
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
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'addresses': addresses,  # ← IMPORTANT: Make sure this is in context
        'subtotal': subtotal,
        'shipping': shipping,
        'tax': tax,
        'discount': discount,
        'total': total,
        'applied_coupon': applied_coupon,
    }
    
    return render(request, 'orders/checkout.html', context)
    """
    Checkout page with affiliate tracking
    - Handles cart review and order creation
    - Tracks affiliate commissions
    - Integrates coupon discounts
    """
    # Initialize affiliate_code at function start (FIXES UnboundLocalError)
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
        address_id = request.POST.get('address')
        payment_method = request.POST.get('payment_method', 'card')
        
        # Validate address selection
        if not address_id or not address_id.isdigit():
            messages.error(request, 'Please select a valid shipping address.')
            context = {
                'cart': cart,
                'cart_items': cart_items,
                'addresses': addresses,
                'subtotal': cart.subtotal,
                'shipping': Decimal("50") if cart.subtotal < Decimal("500") else Decimal("0"),
                'tax': cart.subtotal * Decimal("0.0665"),
                'total': cart.total,
            }
            return render(request, 'orders/checkout.html', context)
        
        # Get shipping address
        address = get_object_or_404(Address, id=address_id, user=request.user)
        
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
        # Try from GET parameter first (if coming from affiliate link), then from cookie
        affiliate_code = request.GET.get('ref') or request.COOKIES.get('affiliate_code')
        
        # ====== CREATE ORDER ======
        try:
            with transaction.atomic():  # Ensure all related records are created together
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
                    shipping_address_line2=address.address_line2,
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
                        from affiliate.models import AffiliateUser, AffiliateOrder, AffiliateClick, AffiliateTransaction
                        
                        # Get the active affiliate
                        affiliate = AffiliateUser.objects.get(
                            affiliate_code=affiliate_code,
                            status='active'
                        )
                        
                        # Record the click/visit
                        AffiliateClick.objects.create(
                            affiliate=affiliate,
                            visitor_id=request.session.session_key or '',
                            ip_address=get_client_ip(request),
                        )
                        
                        # Calculate commission (based on program rate)
                        program = affiliate.program
                        commission_rate = Decimal(str(program.commission_rate)) / Decimal("100")
                        commission_amount = total * commission_rate
                        
                        # Create affiliate order record
                        affiliate_order = AffiliateOrder.objects.create(
                            affiliate=affiliate,
                            order=order,
                            order_amount=total,
                            commission_rate=program.commission_rate,
                            commission_amount=commission_amount,
                            status='pending'  # Approved when order delivered
                        )
                        
                        # Create transaction record for accounting
                        old_balance = affiliate.available_balance
                        new_balance = old_balance + commission_amount
                        
                        AffiliateTransaction.objects.create(
                            affiliate=affiliate,
                            transaction_type='earning',
                            amount=commission_amount,
                            description=f"Commission from Order #{order.order_number}",
                            related_order=affiliate_order,
                            balance_after=new_balance
                        )
                        
                        # Update affiliate statistics
                        affiliate.total_clicks += 1
                        affiliate.total_orders += 1
                        affiliate.total_sales += total
                        affiliate.total_referrals += 1
                        affiliate.save()
                        
                    except AffiliateUser.DoesNotExist:
                        # Affiliate code is invalid or inactive - continue without tracking
                        pass
                    except Exception as e:
                        # Log affiliate tracking errors but don't block order
                        print(f"Affiliate tracking error: {str(e)}")
                
                # ====== CREATE PAYMENT RECORD ======
                Payment.objects.create(
                    order=order,
                    payment_method=payment_method,
                    amount=total,
                )
                
                # ====== CLEANUP ======
                # Send confirmation email
                order.send_order_confirmation_email()
                
                # Clear cart items
                cart_items.delete()
                
                # Remove coupon from session
                if 'applied_coupon' in request.session:
                    del request.session['applied_coupon']
                
                # Clear affiliate code cookie
                response = redirect('orders:order_detail', order_id=order.id)
                response.delete_cookie('affiliate_code')
                
                messages.success(request, f'Order #{order.order_number} placed successfully!')
                return response
                
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
            return redirect('orders:checkout')
    
    # ====== GET REQUEST - DISPLAY CHECKOUT PAGE ======
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
    
    # Build context for template
    context = {
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
    
    return render(request, 'orders/checkout.html', context)


# def get_client_ip(request):
#     """Get client IP address from request"""
#     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#     if x_forwarded_for:
#         ip = x_forwarded_for.split(',')[0]
#     else:
#         ip = request.META.get('REMOTE_ADDR')
#     return ip

# ============================================================================
# AJAX VIEWS
# ============================================================================

@require_POST
def add_to_cart_ajax(request, product_id):
    """Add product to cart via AJAX"""
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        
        # Get or create cart
        cart = get_or_create_cart(request)
        
        # Get quantity from request
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))
        
        # Check if item already in cart
        cart_item, created = cart.orderitems.get_or_create(
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Product added to cart',
            'cart_count': cart.orderitems.count()
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


def cart_count(request):
    """Get cart item count"""
    cart = get_or_create_cart(request)
    count = cart.orderitems.count()
    return JsonResponse({'count': count})


# ============================================================================
# ORDER VIEWS
# ============================================================================

@login_required
def order_list(request):
    """List user orders"""
    orders = request.user.orders.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_detail(request, order_id):
    """Order detail view"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()
    payments = order.payments.all()
    
    context = {
        'order': order,
        'order_items': order_items,
        'payments': payments,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def cancel_order(request, order_id):
    """Cancel order"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status in ['delivered', 'refunded']:
        messages.error(request, 'Cannot cancel delivered or refunded orders.')
        return redirect('orders:order_detail', order_id=order.id)
    
    order.status = 'cancelled'
    order.save()
    
    messages.success(request, 'Order cancelled successfully.')
    return redirect('orders:order_detail', order_id=order.id)


@login_required
def download_invoice(request, order_id):
    """Download order invoice as PDF"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
        from django.http import HttpResponse
        
        order = get_object_or_404(Order, id=order_id, user=request.user)
        order_items = order.items.all()
        
        # Create response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_number}.pdf"'
        
        # Create PDF
        doc = SimpleDocTemplate(response, pagesize=letter)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        title = Paragraph(f"Invoice - Order #{order.order_number}", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Order info
        info = Paragraph(f"Order Date: {order.created_at.strftime('%Y-%m-%d')}<br/>Status: {order.get_status_display()}", styles['Normal'])
        elements.append(info)
        elements.append(Spacer(1, 12))
        
        # Items table
        data = [['Product', 'Quantity', 'Price', 'Total']]
        for item in order_items:
            data.append([
                item.product_name,
                str(item.quantity),
                f"₹{item.price}",
                f"₹{item.total_price}"
            ])
        
        table = Table(data)
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        # Totals
        totals = Paragraph(f"<b>Subtotal:</b> ₹{order.subtotal}<br/><b>Shipping:</b> ₹{order.shipping_cost}<br/><b>Tax:</b> ₹{order.tax}<br/><b>Discount:</b> ₹{order.discount}<br/><b>Total:</b> ₹{order.total}", styles['Normal'])
        elements.append(totals)
        
        # Build PDF
        doc.build(elements)
        
        return response
    
    except ImportError:
        messages.error(request, 'PDF generation not available. Please contact support.')
        return redirect('orders:order_detail', order_id=order_id)


# ============================================================================
# PAYMENT VIEWS
# ============================================================================

@login_required
def payment_status(request, order_id):
    """Check payment status"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    payment = order.payments.first()
    
    if payment:
        return JsonResponse({
            'status': payment.payment_status,
            'amount': str(payment.amount),
            'method': payment.payment_method,
        })
    
    return JsonResponse({'status': 'pending'})
