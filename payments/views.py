# payments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from orders.models import Order
import razorpay
import json

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required
def initiate_payment(request):
    """
    Display payment initiation page and create Razorpay order
    """
    if request.method == 'POST':
        # Get order details from POST
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            'amount': int(order.total * 100),  # Amount in paise
            'currency': 'INR',
            'payment_capture': '1',
            'notes': {
                'order_id': str(order.id),
                'user_email': request.user.email,
            }
        })
        
        # Save Razorpay order ID to your order
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        context = {
            'order': order,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': int(order.total * 100),
            'currency': 'INR',
            'user_name': request.user.get_full_name() or request.user.username,
            'user_email': request.user.email,
            'user_phone': request.user.profile.phone if hasattr(request.user, 'profile') else '',
        }
        
        return render(request, 'payments/payment.html', context)
    
    # GET request - show form to enter amount or select order
    orders = Order.objects.filter(user=request.user, payment_status='pending')
    return render(request, 'payments/initiate.html', {'orders': orders})


@csrf_exempt
def payment_callback(request):
    """
    Handle Razorpay payment callback
    """
    if request.method == 'POST':
        try:
            # Get payment details from callback
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
                # Update order status
                order.payment_status = 'completed'
                order.razorpay_payment_id = payment_id
                order.razorpay_signature = signature
                order.status = 'confirmed'
                order.save()
                
                # Send confirmation email to customer
                send_order_confirmation_email(order)
                
                # Send notification email to admin
                send_admin_notification_email(order)
                
                # Redirect to success page with order summary
                return redirect('payments:payment_success', order_id=order.id)
            else:
                # Payment verification failed
                order.payment_status = 'failed'
                order.save()
                return redirect('payments:payment_failure', order_id=order.id)
                
        except Exception as e:
            print(f"Payment callback error: {e}")
            return redirect('payments:payment_failure')
    
    return JsonResponse({'status': 'invalid request'}, status=400)


@login_required
def payment_success(request, order_id):
    """
    Display order confirmation and summary after successful payment
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {
        'order': order,
        'order_items': order.items.select_related('product'),
    }
    return render(request, 'payments/success.html', context)


@login_required
def payment_failure(request, order_id=None):
    """
    Display payment failure page
    """
    order = None
    if order_id:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {'order': order}
    return render(request, 'payments/failure.html', context)


@login_required
def download_invoice(request, order_id):
    """
    Generate and download PDF invoice for an order
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from io import BytesIO
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Add custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2D7A6E'),
        spaceAfter=30,
    )
    
    # Invoice title
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Company details
    company_info = f"""
    <b>Emerald Secrets</b><br/>
    Email: {settings.COMPANY_EMAIL}<br/>
    Website: {settings.SITE_URL}
    """
    elements.append(Paragraph(company_info, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Order details
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
    
    # Customer details
    elements.append(Paragraph("<b>Bill To:</b>", styles['Heading3']))
    customer_info = f"""
    {order.user.get_full_name() or order.user.username}<br/>
    {order.shipping_address}<br/>
    Email: {order.user.email}
    """
    elements.append(Paragraph(customer_info, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Order items table
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
    
    # Add totals
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
    
    # Thank you message
    thank_you = Paragraph(
        "<i>Thank you for your purchase!</i>",
        styles['Normal']
    )
    elements.append(thank_you)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF value
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'
    response.write(pdf)
    
    return response


def send_order_confirmation_email(order):
    """Send order confirmation email to customer"""
    subject = f'Order Confirmation - {order.id}'
    html_message = render_to_string('emails/order_confirmation.html', {
        'order': order,
        'order_items': order.items.all(),
    })
    
    send_mail(
        subject,
        'Your order has been confirmed.',
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email],
        html_message=html_message,
        fail_silently=True,
    )


def send_admin_notification_email(order):
    """Send new order notification to admin"""
    subject = f'New Order Received - {order.id}'
    message = f"""
    New order received!
    
    Order ID: {order.id}
    Customer: {order.user.get_full_name() or order.user.username}
    Amount: ₹{order.total}
    Payment Status: {order.payment_status}
    
    View order in admin panel.
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMIN_EMAIL],
        fail_silently=True,
    )
