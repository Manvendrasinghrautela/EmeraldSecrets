# orders/views.py - COMPLETE AND CORRECTED
import json
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Address
from products.models import Product

from .models import Cart, CartItem, Order, OrderItem, Payment, Coupon
from .services.shipping import get_shipping_cost_for_cart

import razorpay

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
logger = logging.getLogger(__name__)

TWOPLACES = Decimal('0.01')
GST_RATE = Decimal(str(getattr(settings, 'GST_RATE', Decimal('0.18'))))


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0.00')


def _quantize(amount: Decimal) -> Decimal:
    return _to_decimal(amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _calculate_tax(subtotal: Decimal) -> Decimal:
    if subtotal <= 0:
        return Decimal('0.00')
    return _quantize(subtotal * GST_RATE)


def _get_discount(request, subtotal: Decimal):
    discount = Decimal('0.00')
    applied_coupon = None
    coupon_code = request.session.get('applied_coupon')

    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code)
            applied_coupon = coupon
            if coupon.discount_type == 'percentage':
                discount = (subtotal * Decimal(str(coupon.discount_value))) / Decimal('100')
            else:
                discount = Decimal(str(coupon.discount_value))
        except Coupon.DoesNotExist:
            request.session.pop('applied_coupon', None)
            applied_coupon = None

    if discount > subtotal:
        discount = subtotal

    return _quantize(discount), applied_coupon


def _get_default_address(user):
    if not user.is_authenticated:
        return None
    address = user.addresses.filter(is_active=True, is_default=True).first()
    if address:
        return address
    return user.addresses.filter(is_active=True).first()


def _calculate_order_pricing(cart_items, request=None, postal_code=None, payment_method='upi'):
    cart_items = list(cart_items)
    subtotal = Decimal('0.00')
    for item in cart_items:
        subtotal += _to_decimal(getattr(item, 'total_price', Decimal('0.00')))
    subtotal = _quantize(subtotal)

    tax = _calculate_tax(subtotal)
    shipping = _quantize(
        get_shipping_cost_for_cart(
            cart_items,
            postal_code=postal_code,
            is_cod=(payment_method == 'cod')
        )
    ) if subtotal > 0 else Decimal('0.00')

    discount = Decimal('0.00')
    applied_coupon = None
    if request:
        discount, applied_coupon = _get_discount(request, subtotal)

    total = _quantize(subtotal + tax + shipping - discount)
    if total < 0:
        total = Decimal('0.00')

    return {
        'items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'discount': discount,
        'total': total,
        'coupon': applied_coupon,
    }


def _decimal_to_str(amount: Decimal) -> str:
    return f"{_quantize(amount):.2f}"

# ============================================================================
# HELPER FUNCTIONS
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


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# CART VIEWS
# ============================================================================

@login_required
def cart_view(request):
    """View shopping cart"""
    cart = get_or_create_cart(request)
    cart_items = list(cart.orderitems.select_related('product'))
    default_address = _get_default_address(request.user)
    postal_code = default_address.postal_code if default_address else None

    pricing = _calculate_order_pricing(cart_items, request=request, postal_code=postal_code)
    gst_percent = (GST_RATE * Decimal('100')).quantize(Decimal('0.01'))

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': pricing['subtotal'],
        'shipping': pricing['shipping'],
        'tax': pricing['tax'],
        'discount': pricing['discount'],
        'total': pricing['total'],
        'applied_coupon': pricing['coupon'],
        'gst_rate_percent': gst_percent,
        'shipping_estimated': postal_code is None,
        'shipping_pin': postal_code,
    }
    return render(request, 'orders/cart.html', context)


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
            
            if not coupon.is_valid():
                messages.error(request, 'This coupon is no longer valid.')
                return redirect('orders:cart')
            
            if cart.get_subtotal() < coupon.min_purchase:
                messages.error(request, f'Minimum purchase of ₹{coupon.min_purchase} required.')
                return redirect('orders:cart')
            
            request.session['applied_coupon'] = code
            coupon.uses_count += 1
            coupon.save()
            
            # Calculate discount
            if coupon.discount_type == 'percentage':
                discount = (cart.get_subtotal() * Decimal(str(coupon.discount_value))) / Decimal("100")
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
        del request.session['applied_coupon']
        messages.success(request, 'Coupon removed.')
    
    return redirect('orders:cart')


# ============================================================================
# CHECKOUT & RAZORPAY PAYMENT
# ============================================================================

@login_required
def checkout(request):
    """Checkout page"""
    cart = get_or_create_cart(request)
    cart_items = list(cart.orderitems.select_related('product'))
    
    if not cart_items:
        messages.error(request, 'Your cart is empty.')
        return redirect('orders:cart')

    addresses = request.user.addresses.filter(is_active=True)
    default_address = _get_default_address(request.user)
    postal_code = default_address.postal_code if default_address else None

    pricing = _calculate_order_pricing(
        cart_items,
        request=request,
        postal_code=postal_code,
    )
    gst_percent = (GST_RATE * Decimal('100')).quantize(Decimal('0.01'))

    context = {
        'cart': cart,
        'cart_items': pricing['items'],
        'addresses': addresses,
        'subtotal': pricing['subtotal'],
        'shipping': pricing['shipping'],
        'tax': pricing['tax'],
        'discount': pricing['discount'],
        'total': pricing['total'],
        'applied_coupon': pricing['coupon'],
        'gst_rate_percent': gst_percent,
        'shipping_estimated': postal_code is None,
        'shipping_pin': postal_code,
    }
    
    return render(request, 'orders/checkout.html', context)


@login_required
def create_order(request):
    """Create order and initiate Razorpay payment"""
    if request.method == 'POST':
        cart = get_or_create_cart(request)
        cart_items = list(cart.orderitems.select_related('product'))
        
        if not cart_items:
            messages.error(request, 'Your cart is empty.')
            return redirect('orders:cart')
        
        payment_method = request.POST.get('payment_method', 'upi')
        if payment_method not in ('card', 'upi'):
            payment_method = 'upi'
        
        # Get address
        address_id = request.POST.get('address')
        if not address_id:
            messages.error(request, 'Please select a shipping address.')
            return redirect('orders:checkout')
        
        try:
            address = Address.objects.get(id=address_id, user=request.user, is_active=True)
        except Address.DoesNotExist:
            messages.error(request, 'Selected address not found.')
            return redirect('orders:checkout')
        
        pricing = _calculate_order_pricing(
            cart_items,
            request=request,
            postal_code=address.postal_code,
            payment_method=payment_method,
        )
        
        if pricing['total'] <= 0:
            messages.error(request, 'Unable to calculate a payable total for this order.')
            return redirect('orders:checkout')
        
        # Get affiliate code
        affiliate_code = request.GET.get('ref') or request.COOKIES.get('affiliate_code')
        
        # Create Order
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    status='pending',
                    payment_status='pending',
                    payment_method=payment_method,
                    subtotal=pricing['subtotal'],
                    shipping_cost=pricing['shipping'],
                    tax=pricing['tax'],
                    discount=pricing['discount'],
                    total=pricing['total'],
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
                    affiliate_code=affiliate_code,
                )
                
                # Create Order Items
                for cart_item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        product_name=cart_item.product.name,
                        product_sku=cart_item.product.sku or '',
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                    )
                
                # Create Razorpay Order
                razorpay_order = razorpay_client.order.create({
                    'amount': int(pricing['total'] * 100),  # Amount in paise
                    'currency': 'INR',
                    'payment_capture': '1',
                    'notes': {
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                    }
                })
                
                # Save Razorpay Order ID
                order.razorpay_order_id = razorpay_order['id']
                order.save()
                
                # Track affiliate if present
                if affiliate_code:
                    try:
                        from affiliate.models import AffiliateUser, AffiliateOrder, AffiliateTransaction
                        
                        affiliate = AffiliateUser.objects.get(
                            affiliate_code=affiliate_code,
                            status='active'
                        )
                        
                        program = affiliate.program
                        order_total = pricing['total']  
                        commission_rate = Decimal(str(program.commission_rate)) / Decimal("100")
                        commission_amount = order_total * commission_rate
                        
                        AffiliateOrder.objects.create(
                            affiliate=affiliate,
                            order=order,
                            order_amount=order_total,
                            commission_rate=program.commission_rate,
                            commission_amount=commission_amount,
                            status='pending'
                        )
                        
                        affiliate.total_referrals += 1
                        affiliate.save()
                        
                    except AffiliateUser.DoesNotExist:
                        pass
                
                # Redirect to payment page
                return redirect('orders:payment', order_id=order.id)
                
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
            return redirect('orders:checkout')
    
    return redirect('orders:checkout')


@login_required
def payment_page(request, order_id):
    """Display Razorpay payment page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    context = {
        'order': order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': order.razorpay_order_id,
        'amount': int(order.total * 100),
        'currency': 'INR',
        'user_name': f"{order.shipping_first_name} {order.shipping_last_name}",
        'user_email': order.shipping_email,
        'user_phone': order.shipping_phone,
    }
    
    return render(request, 'payments/payment.html', context)



@csrf_exempt
def payment_callback(request):
    """Handle Razorpay payment callback"""
    if request.method == 'POST':
        try:
            payment_id = request.POST.get('razorpay_payment_id')
            order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            try:
                razorpay_client.utility.verify_payment_signature(params_dict)
                payment_verified = True
            except razorpay.errors.SignatureVerificationError:
                payment_verified = False
            
            # Get the order
            order = Order.objects.get(razorpay_order_id=order_id)
            
            if payment_verified:
                # Update order
                order.payment_status = 'completed'
                order.razorpay_payment_id = payment_id
                order.razorpay_signature = signature
                order.status = 'confirmed'
                order.save()

                try:
                    order.send_order_confirmation_email()
                except Exception as exc:
                    logger.warning("Failed to send order confirmation email for order %s: %s", order.id, exc)
                
                # Clear cart
                cart = Cart.objects.filter(user=order.user).first()
                if cart:
                    cart.orderitems.all().delete()
                
                # Clear coupon
                if hasattr(request, 'session') and 'applied_coupon' in request.session:
                    del request.session['applied_coupon']
                
                return redirect('orders:order_success', order_id=order.id)
            else:
                order.payment_status = 'failed'
                order.save()
                return redirect('orders:order_failure', order_id=order.id)
                
        except Exception as e:
            print(f"Payment callback error: {e}")
            return redirect('orders:order_failure')
    
    return JsonResponse({'status': 'invalid request'}, status=400)


@login_required
def order_success(request, order_id):
    """Display order success page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    gst_percent = (GST_RATE * Decimal('100')).quantize(Decimal('0.01'))
    context = {
        'order': order,
        'order_items': order.items.select_related('product'),
        'gst_rate_percent': gst_percent,
    }
    return render(request, 'orders/order_success.html', context)


@login_required
def order_failure(request, order_id=None):
    """Display payment failure page"""
    order = None
    if order_id:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {'order': order}
    return render(request, 'orders/order_failure.html', context)


# ============================================================================
# ORDER VIEWS
# ============================================================================

@login_required
def order_list(request):
    """List user orders"""
    orders = request.user.orders.all().order_by('-created_at')
    
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
    """Generate and download PDF invoice"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from io import BytesIO
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Invoice title
    elements.append(Paragraph("<b>INVOICE</b>", styles['Title']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Order details
    order_info = [
        ['Invoice No:', f'INV-{order.id:06d}'],
        ['Order No:', order.order_number],
        ['Date:', order.created_at.strftime('%B %d, %Y')],
        ['Payment ID:', order.razorpay_payment_id or 'N/A'],
    ]
    
    order_table = Table(order_info, colWidths=[2*inch, 4*inch])
    elements.append(order_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Customer details
    elements.append(Paragraph("<b>Bill To:</b>", styles['Heading3']))
    customer_info = f"{order.shipping_first_name} {order.shipping_last_name}<br/>{order.shipping_address_line1}<br/>{order.shipping_city}, {order.shipping_state} {order.shipping_postal_code}"
    elements.append(Paragraph(customer_info, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Order items
    items_data = [['Product', 'Quantity', 'Price', 'Total']]
    for item in order.items.all():
        items_data.append([
            item.product_name,
            str(item.quantity),
            f'₹{item.price:.2f}',
            f'₹{item.total_price:.2f}'
        ])
    
    items_data.append(['', '', 'Subtotal:', f'₹{order.subtotal:.2f}'])
    items_data.append(['', '', 'Shipping:', f'₹{order.shipping_cost:.2f}'])
    items_data.append(['', '', '<b>Total:</b>', f'<b>₹{order.total:.2f}</b>'])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -4), 1, colors.black),
    ]))
    
    elements.append(items_table)
    
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_number}.pdf"'
    response.write(pdf)
    
    return response


# ============================================================================
# AJAX VIEWS
# ============================================================================


@login_required
@require_POST
def shipping_quote(request):
    """Return live shipping quote and totals for selected address"""
    cart = get_or_create_cart(request)
    cart_items = list(cart.orderitems.select_related('product'))
    if not cart_items:
        return JsonResponse({'error': 'Cart is empty'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (AttributeError, ValueError, TypeError):
        payload = request.POST

    address_id = payload.get('address_id')
    if not address_id:
        return JsonResponse({'error': 'address_id is required'}, status=400)

    payment_method = payload.get('payment_method', 'upi')
    address = get_object_or_404(Address, id=address_id, user=request.user, is_active=True)

    pricing = _calculate_order_pricing(
        cart_items,
        request=request,
        postal_code=address.postal_code,
        payment_method=payment_method,
    )

    data = {
        'subtotal': _decimal_to_str(pricing['subtotal']),
        'shipping': _decimal_to_str(pricing['shipping']),
        'tax': _decimal_to_str(pricing['tax']),
        'discount': _decimal_to_str(pricing['discount']),
        'total': _decimal_to_str(pricing['total']),
        'postal_code': address.postal_code,
        'estimated': False,
        'coupon': pricing['coupon'].code if pricing['coupon'] else None,
    }
    return JsonResponse(data)


@require_POST
def add_to_cart_ajax(request, product_id):
    """Add product to cart via AJAX"""
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        cart = get_or_create_cart(request)
        
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))
        
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
        return JsonResponse({'success': False, 'message': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


def cart_count(request):
    """Get cart item count"""
    cart = get_or_create_cart(request)
    count = cart.orderitems.count()
    return JsonResponse({'count': count})


@login_required
def payment_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return JsonResponse({
        'status': order.payment_status,
        'razorpay_payment_id': order.razorpay_payment_id,
        'amount': str(order.total),
    })
