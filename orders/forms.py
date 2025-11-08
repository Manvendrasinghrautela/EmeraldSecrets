from django import forms
from .models import Order, OrderItem, Coupon

# Order Form
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('shipping_first_name', 'shipping_last_name', 'shipping_phone', 
                 'shipping_email', 'shipping_address_line1', 'shipping_address_line2',
                 'shipping_city', 'shipping_state', 'shipping_postal_code', 
                 'shipping_country', 'payment_method', 'order_notes')
        widgets = {
            'shipping_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'shipping_address_line1': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_address_line2': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_city': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_state': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_country': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'order_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
        }


# Coupon Form
class CouponForm(forms.Form):
    code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter coupon code'
        })
    )


# Shipping Method Form
class ShippingMethodForm(forms.Form):
    SHIPPING_CHOICES = [
        ('standard', 'Standard Shipping - FREE (5-7 days)'),
        ('express', 'Express Shipping - ₹150 (2-3 days)'),
        ('overnight', 'Overnight Shipping - ₹300 (Next day)'),
    ]
    
    shipping_method = forms.ChoiceField(
        choices=SHIPPING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )


# Payment Method Form
class PaymentMethodForm(forms.Form):
    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('upi', 'UPI Payment'),
        ('card', 'Credit/Debit Card'),
        ('wallet', 'Digital Wallet'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
