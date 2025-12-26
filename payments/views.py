from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from decimal import Decimal
import razorpay
import json
import logging

from orders.models import Order
from affiliate.models import AffiliateUser, AffiliateOrder, AffiliateClick
from affiliate.middleware import get_affiliate_from_request

logger = logging.getLogger('affiliate')

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


# ============================================================================
# PAYMENT INITIATION
# ============================================================================

@login_required
def initiate_payment(request):
    """
    Display payment initiation page and create Razorpay order
    
    Features:
    - Get order details from session/POST
    - Create Razorpay order
    - Display payment form
    - Include affiliate code if applicable
    
    Affiliate integration:
    - Check if order is affiliate-referred
    - Store affiliate info for commission calculation
    - Pass to payment callback
    """
    
    if request.method == 'POST':
        # ✅ GET order details from POST
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # ✅ CREATE Razorpay order
        razorpay_order = razorpay_client.order.create({
            'amount': int(order.total * 100),  # Amount in paise
            'currency': 'INR',
            'payment_capture': '1',
            'notes': {
                'order_id': str(order.id),
                'user_email': request.user.email,
            }
        })
        
        # ✅ Save Razorpay order ID to your order
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        # ✅ AFFILIATE: Get affiliate info from request
        affiliate_code = request.session.get('affiliate_code')
        affiliate_id = request.session.get('affiliate_id')
        
        if affiliate_code and affiliate_id:
            logger.info(f"✅ Payment initiated with affiliate: {affiliate_code} | Order: {order.id}")
        
        context = {
            'order': order,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': int(order.total * 100),
            'currency': 'INR',
            'user_name': request.user.get_full_name() or request.user.username,
            'user_email': request.user.email,
            'user_phone': request.user.profile.phone if hasattr(request.user, 'profile') else '',
            # ✅ AFFILIATE: Pass to template
            'affiliate_code': affiliate_code,
        }
        
        return render(request, 'payments/payment.html', context)
    
    # ✅ GET request - show form to enter amount or select order
    orders = Order.objects.filter(user=request.user, payment_status='pending')
    return render(request, 'payments/initiate.html', {'orders': orders})


# ============================================================================
# PAYMENT CALLBACK WITH AFFILIATE COMMISSION
# ============================================================================

@csrf_exempt
def payment_callback(request):
    """
    Handle Razorpay payment callback
    
    Features:
    - Verify payment signature
    - Update order status
    - Send confirmation emails
    - Track analytics
    
    Affiliate integration:
    - Calculate 5% commission if affiliate-referred
    - Create AffiliateOrder record
    - Update affiliate earnings
    - Send affiliate notification
    - Update click-to-order conversion
    """
    
    if request.method == 'POST':
        try:
            # ✅ GET payment details from callback
            payment_id = request.POST.get('razorpay_payment_id')
            order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')
            
            # ✅ VERIFY payment signature
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
            
            # ✅ GET the order
            order = Order.objects.get(razorpay_order_id=order_id)
            
            if payment_verified:
                # ✅ UPDATE order status
                order.payment_status = 'completed'
                order.razorpay_payment_id = payment_id
                order.razorpay_signature = signature
                order.status = 'confirmed'
                order.save()
                
                # ============================================================
                # ✅ AFFILIATE COMMISSION: 5% CALCULATION AND TRACKING
                # ============================================================
                
                # Get affiliate code from session
                affiliate_code = request.session.get('affiliate_code')
                affiliate_id = request.session.get('affiliate_id')
                
                if affiliate_code and affiliate_id:
                    try:
                        # ✅ GET affiliate user
                        affiliate = AffiliateUser.objects.get(
                            id=affiliate_id,
                            affiliate_code=affiliate_code,
                            status='active'
                        )
                        
                        # ✅ CALCULATE 5% commission
                        commission_amount = Decimal(str(order.total)) * Decimal('0.05')
                        
                        # ✅ CREATE AffiliateOrder record
                        affiliate_order = AffiliateOrder.objects.create(
                            affiliate=affiliate,
                            order=order,
                            commission_amount=commission_amount,
                            commission_rate=Decimal('5.00'),
                            status='pending',  # Auto-approved after 7 days
                            notes=f'Order placed on {order.created_at.strftime("%Y-%m-%d %H:%M:%S")}'
                        )
                        
                        # ✅ UPDATE affiliate pending commission
                        affiliate.pending_commission += commission_amount
                        affiliate.save()
                        
                        # ✅ LOG commission creation
                        logger.info(
                            f"✅ Commission created: {affiliate_code} | "
                            f"Order: {order.id} | "
                            f"Amount: ₹{commission_amount} (5% of ₹{order.total}) | "
                            f"Status: pending"
                        )
                        
                        # ✅ CREATE AffiliateTransaction for audit trail
                        from affiliate.models import AffiliateTransaction
                        AffiliateTransaction.objects.create(
                            affiliate=affiliate,
                            transaction_type='commission_earned',
                            amount=commission_amount,
                            description=f'Commission on order {order.id}',
                            reference_id=order.id,
                            reference_type='order',
                            notes=f'5% commission: ₹{order.total} × 0.05 = ₹{commission_amount}'
                        )
                        
                        # ✅ SEND affiliate notification email (if enabled)
                        if settings.AFFILIATE_EMAIL_NOTIFICATIONS.get('send_commission_earned', True):
                            send_affiliate_commission_email(affiliate, order, commission_amount)
                        
                    except AffiliateUser.DoesNotExist:
                        logger.warning(f"⚠️  Affiliate not found: {affiliate_code}")
                    except Exception as e:
                        logger.error(f"❌ Error processing affiliate commission: {str(e)}")
                
                # ============================================================
                # END AFFILIATE COMMISSION
                # ============================================================
                
                # ✅ SEND confirmation email to customer
                send_order_confirmation_email(order)
                
                # ✅ SEND notification email to admin
                send_admin_notification_email(order, affiliate_code if affiliate_code else None)
                
                # ✅ LOG successful payment
                logger.info(f"✅ Payment successful: Order {order.id} | Amount: ₹{order.total}")
                
                # ✅ REDIRECT to success page with order summary
                return redirect('payments:payment_success', order_id=order.id)
            
            else:
                # ✅ Payment verification failed
                order.payment_status = 'failed'
                order.save()
                logger.warning(f"⚠️  Payment verification failed: Order {order.id}")
                return redirect('payments:payment_failure', order_id=order.id)
                
        except Exception as e:
            logger.error(f"❌ Payment callback error: {str(e)}")
            return redirect('payments:payment_failure')
    
    return JsonResponse({'status': 'invalid request'}, status=400)


# ============================================================================
# PAYMENT SUCCESS VIEW
# ============================================================================

@login_required
def payment_success(request, order_id):
    """
    Display order confirmation and summary after successful payment
    
    Features:
    - Show order details
    - Show order items
    - Display commission info if applicable
    - Download invoice option
    
    Affiliate integration:
    - Show commission amount (5%)
    - Show commission status (pending/completed)
    - Show affiliate info if referred
    """
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # ✅ GET affiliate order info if exists
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
        logger.info(f"✅ Payment success page viewed: Order {order.id} | Affiliate: {affiliate_info['affiliate_code']}")
    except AffiliateOrder.DoesNotExist:
        logger.info(f"✅ Payment success page viewed: Order {order.id} | No affiliate")
    
    context = {
        'order': order,
        'order_items': order.items.select_related('product'),
        # ✅ Affiliate info
        'affiliate_order': affiliate_order,
        'affiliate_info': affiliate_info,
    }
    
    return render(request, 'payments/success.html', context)


# ============================================================================
# PAYMENT FAILURE VIEW
# ============================================================================

@login_required
def payment_failure(request, order_id=None):
    """
    Display payment failure page
    
    Features:
    - Show failed order details
    - Provide retry option
    - Log failure
    """
    
    order = None
    if order_id:
        order = get_object_or_404(Order, id=order_id, user=request.user)
        logger.warning(f"⚠️  Payment failed: Order {order.id} | Amount: ₹{order.total}")
    
    context = {'order': order}
    return render(request, 'payments/failure.html', context)


# ============================================================================
# INVOICE GENERATION
# ============================================================================

@login_required
def download_invoice(request, order_id):
    """
    Generate and download PDF invoice for an order
    
    Features:
    - Generate professional PDF invoice
    - Include order details
    - Include items and pricing
    - Include company details
    
    Affiliate integration:
    - Show if order was affiliate-referred
    - Show commission amount in invoice
    - Show affiliate code
    """
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from io import BytesIO
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # ✅ CREATE PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # ✅ ADD custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2D7A6E'),
        spaceAfter=30,
    )
    
    # ✅ INVOICE title
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # ✅ COMPANY details
    company_info = f"""
    <b>Emerald Secrets</b><br/>
    Email: {settings.COMPANY_EMAIL}<br/>
    Website: {settings.SITE_URL}
    """
    elements.append(Paragraph(company_info, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # ✅ ORDER details
    order_info = [
        ['Invoice No:', f'INV-{order.id:06d}'],
        ['Order Date:', order.created_at.strftime('%B %d, %Y')],
        ['Payment Status:', order.payment_status.upper()],
        ['Payment ID:', order.razorpay_payment_id or 'N/A'],
    ]
    
    order_table = Table(order_info, colWidths=[2*inch, 4*inch])
    order_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(order_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ✅ CUSTOMER details
    elements.append(Paragraph("<b>Bill To:</b>", styles['Heading3']))
    customer_info = f"""
    {order.user.get_full_name() or order.user.username}<br/>
    {order.shipping_address}<br/>
    Email: {order.user.email}
    """
    elements.append(Paragraph(customer_info, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # ✅ AFFILIATE INFO (if applicable)
    try:
        affiliate_order = AffiliateOrder.objects.get(order=order)
        elements.append(Paragraph("<b>Referral Information:</b>", styles['Heading3']))
        affiliate_info_text = f"""
        Referred By: {affiliate_order.affiliate.user.get_full_name()}<br/>
        Affiliate Code: {affiliate_order.affiliate.affiliate_code}<br/>
        Commission Applied: ₹{affiliate_order.commission_amount:.2f} (5%)
        """
        elements.append(Paragraph(affiliate_info_text, styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
    except AffiliateOrder.DoesNotExist:
        pass
    
    # ✅ ORDER items table
    elements.append(Paragraph("<b>Order Items:</b>", styles['Heading3']))
    elements.append(Spacer(1, 0.1*inch))
    
    items_data = [['Product', 'Quantity', 'Price', 'Total']]
    for item in order.items.all():
        items_data.append([
            item.product_name,
            str(item.quantity),
            f'₹{item.price:.2f}',
            f'₹{item.total_price:.2f}'
        ])
    
    # ✅ ADD totals
    items_data.append(['', '', 'Subtotal:', f'₹{order.subtotal:.2f}'])
    if order.discount > 0:
        items_data.append(['', '', 'Discount:', f'-₹{order.discount:.2f}'])
    items_data.append(['', '', 'Shipping:', f'₹{order.shipping_cost:.2f}'])
    items_data.append(['', '', '<b>Total:</b>', f'<b>₹{order.total:.2f}</b>'])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -5), 1, colors.black),
        ('LINEABOVE', (2, -4), (-1, -4), 1, colors.black),
        ('LINEABOVE', (2, -1), (-1, -1), 2, colors.black),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # ✅ THANK you message
    thank_you = Paragraph(
        "<i>Thank you for your purchase!</i>",
        styles['Normal']
    )
    elements.append(thank_you)
    
    # ✅ BUILD PDF
    doc.build(elements)
    
    # ✅ GET PDF value
    pdf = buffer.getvalue()
    buffer.close()
    
    # ✅ CREATE response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'
    response.write(pdf)
    
    logger.info(f"✅ Invoice downloaded: Order {order.id}")
    
    return response


# ============================================================================
# EMAIL NOTIFICATIONS
# ============================================================================

def send_order_confirmation_email(order):
    """
    Send order confirmation email to customer
    
    Includes:
    - Order summary
    - Items ordered
    - Affiliate info if applicable
    - Download invoice link
    """
    
    try:
        # ✅ CHECK if affiliate-referred
        affiliate_info_context = None
        try:
            affiliate_order = AffiliateOrder.objects.get(order=order)
            affiliate_info_context = {
                'affiliate_code': affiliate_order.affiliate.affiliate_code,
                'commission_amount': affiliate_order.commission_amount,
            }
        except AffiliateOrder.DoesNotExist:
            pass
        
        subject = f'Order Confirmation - {order.id}'
        html_message = render_to_string('emails/order_confirmation.html', {
            'order': order,
            'order_items': order.items.all(),
            'affiliate_info': affiliate_info_context,
        })
        
        send_mail(
            subject,
            'Your order has been confirmed.',
            settings.DEFAULT_FROM_EMAIL,
            [order.user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        logger.info(f"✅ Order confirmation email sent: {order.user.email}")
        
    except Exception as e:
        logger.error(f"❌ Error sending order confirmation email: {str(e)}")


def send_admin_notification_email(order, affiliate_code=None):
    """
    Send new order notification to admin
    
    Includes:
    - Order details
    - Payment status
    - Affiliate info if applicable
    """
    
    try:
        # ✅ BUILD message
        message = f"""
        New order received!
        
        Order ID: {order.id}
        Customer: {order.user.get_full_name() or order.user.username}
        Email: {order.user.email}
        Amount: ₹{order.total}
        Payment Status: {order.payment_status}
        Order Date: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # ✅ ADD affiliate info if applicable
        if affiliate_code:
            message += f"""
        
        AFFILIATE REFERRAL:
        Affiliate Code: {affiliate_code}
        Commission Rate: 5%
        Commission Amount: ₹{Decimal(str(order.total)) * Decimal('0.05'):.2f}
        """
        
        subject = f'New Order Received - {order.id}'
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=True,
        )
        
        logger.info(f"✅ Admin notification email sent")
        
    except Exception as e:
        logger.error(f"❌ Error sending admin notification: {str(e)}")


def send_affiliate_commission_email(affiliate, order, commission_amount):
    """
    Send commission notification email to affiliate
    
    Includes:
    - Commission amount
    - Order details
    - Commission status (pending/completed)
    - Link to affiliate dashboard
    """
    
    try:
        subject = f'Commission Earned - Order {order.id}'
        html_message = render_to_string('emails/affiliate_commission.html', {
            'affiliate': affiliate,
            'order': order,
            'commission_amount': commission_amount,
            'commission_rate': '5%',
            'site_url': settings.SITE_URL,
        })
        
        send_mail(
            subject,
            f'You earned ₹{commission_amount} commission!',
            settings.DEFAULT_FROM_EMAIL,
            [affiliate.user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        logger.info(f"✅ Affiliate commission email sent: {affiliate.affiliate_code}")
        
    except Exception as e:
        logger.error(f"❌ Error sending affiliate commission email: {str(e)}")


# ============================================================================
# SUMMARY: 5% AFFILIATE COMMISSION FLOW IN PAYMENTS
# ============================================================================

"""
COMPLETE 5% AFFILIATE COMMISSION FLOW:

1. PAYMENT INITIATION (initiate_payment):
   ✅ Get order details
   ✅ Check for affiliate_code in session
   ✅ Create Razorpay order
   ✅ Display payment form with affiliate info

2. PAYMENT PROCESSING (payment_callback):
   ✅ Verify payment signature
   ✅ Update order status to 'completed'
   
   AFFILIATE COMMISSION CALCULATION:
   ✅ Get affiliate_code from session
   ✅ Get affiliate user from database
   ✅ Calculate 5%: commission = order_total × 0.05
   ✅ Create AffiliateOrder record:
      - affiliate: AffiliateUser
      - order: Order
      - commission_amount: ₹50 (for ₹1000)
      - commission_rate: 5%
      - status: 'pending' (auto-approved after 7 days)
   
   AFFILIATE UPDATES:
   ✅ Update affiliate.pending_commission += ₹50
   ✅ Create AffiliateTransaction (audit log)
   ✅ Send commission notification email
   
   EMAIL NOTIFICATIONS:
   ✅ Send order confirmation to customer
   ✅ Send admin notification (with affiliate info)

3. SUCCESS PAGE (payment_success):
   ✅ Display order confirmation
   ✅ Show commission info if affiliate-referred
   ✅ Link to download invoice

4. INVOICE GENERATION (download_invoice):
   ✅ Generate PDF invoice
   ✅ Include affiliate info if applicable
   ✅ Show commission amount

COMMISSION DETAILS:
- Rate: 5% (automatic)
- Calculation: order_total × 0.05
- Status: pending (7 days) → completed (auto-approved)
- Storage: AffiliateOrder model
- Tracking: AffiliateTransaction model
- Notification: Email to affiliate + admin

EXAMPLE:
Order Total: ₹1000
Commission: 5% = ₹50
Status: pending (7 days)
Auto-approved: ₹50 credited to affiliate.total_earnings
Withdrawal: Available after approval (₹1000 minimum)

LOGS:
✅ Payment initiated with affiliate
✅ Commission created
✅ Payment successful
✅ Invoice generated
✅ Emails sent
"""