import razorpay
from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
import json

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def initiate_payment(request):
    """Create Razorpay order"""
    if request.method == "POST":
        try:
            # Get amount and currency from request
            amount = int(request.POST.get('amount')) * 100  # Convert to paise
            currency = 'INR'
            
            # Create Razorpay Order
            razorpay_order = razorpay_client.order.create({
                'amount': amount,
                'currency': currency,
                'payment_capture': '1'  # Auto capture
            })
            
            order_id = razorpay_order['id']
            order_status = razorpay_order['status']
            
            if order_status == 'created':
                # Save order details in your database here (optional)
                context = {
                    'order_id': order_id,
                    'amount': amount,
                    'currency': currency,
                    'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                }
                return render(request, 'payments/payment.html', context)
            
        except Exception as e:
            return HttpResponseBadRequest(f"Error: {str(e)}")
    
    return render(request, 'payments/initiate.html')


@csrf_exempt
def payment_callback(request):
    """Handle payment callback from Razorpay"""
    if request.method == "POST":
        try:
            # Get payment details from request
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
                
                # Payment successful - Update your database here
                # For example: Update order status, send confirmation email
                
                return render(request, 'payments/success.html', {
                    'payment_id': payment_id,
                    'order_id': order_id
                })
                
            except razorpay.errors.SignatureVerificationError:
                # Payment verification failed
                return render(request, 'payments/failure.html', {
                    'error': 'Payment verification failed'
                })
                
        except Exception as e:
            return render(request, 'payments/failure.html', {
                'error': str(e)
            })
    
    return HttpResponseBadRequest("Invalid request method")
