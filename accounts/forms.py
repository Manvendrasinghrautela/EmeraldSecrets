from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import UserProfile, Address, AccountSettings
from products.models import Wishlist

# User Registration Form
class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=30, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=30, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm Password'
        })
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


# User Login Form
class UserLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


# User Profile Form
class UserProfileForm(forms.ModelForm):
    """User profile form"""
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = UserProfile
        fields = ('phone', 'date_of_birth', 'profile_image', 
                 'receive_promotional_emails', 'receive_order_updates')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
            'receive_promotional_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_order_updates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

    def save(self, commit=True, user=None):
        profile = super().save(commit=False)
        if user:
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            if commit:
                user.save()
                profile.save()
        return profile


# Address Form
class AddressForm(forms.ModelForm):
    """Address form with proper field configuration"""
    
    class Meta:
        model = Address
        fields = ('first_name', 'last_name', 'phone', 'email', 
                 'address_line1', 'address_line2', 'city', 'state', 
                 'postal_code', 'country', 'address_type', 'is_default')
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name',
                'required': True
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name',
                'required': True
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address',
                'required': True
            }),
            'address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street Address',
                'required': True
            }),
            'address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apartment, suite, etc. (optional)',
                'required': False
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City',
                'required': True
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State',
                'required': True
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal Code / PIN Code',
                'required': True
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country',
                'value': 'India',
                'required': True
            }),
            'address_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set fields as required (NOT blank)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['phone'].required = True
        self.fields['email'].required = True
        self.fields['address_line1'].required = True
        self.fields['city'].required = True
        self.fields['state'].required = True
        self.fields['postal_code'].required = True
        self.fields['country'].required = True
        self.fields['address_type'].required = True
        
        # address_line2 is optional
        self.fields['address_line2'].required = False
        
        # is_default is optional (checkbox)
        self.fields['is_default'].required = False
    
    def clean_phone(self):
        """Accept any phone number format"""
        phone = self.cleaned_data.get('phone')
        # Accept any phone format - no validation
        return phone
    
    def clean_postal_code(self):
        """Accept any postal code format"""
        postal_code = self.cleaned_data.get('postal_code')
        # Accept any postal code format - no validation
        return postal_code

# Password Change Form
class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

class AccountSettingsForm(forms.ModelForm):
    """Account settings form"""
    class Meta:
        model = AccountSettings
        fields = ('email_on_order', 'email_on_shipment', 'email_on_delivery',
                 'email_promotions', 'show_profile_publicly', 'show_reviews_publicly')
        widgets = {
            'email_on_order': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_shipment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_delivery': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_promotions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_profile_publicly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_reviews_publicly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
