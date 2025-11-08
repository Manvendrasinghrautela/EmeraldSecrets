from django import forms
from .models import AffiliateApplication, AffiliateWithdrawal

# Affiliate Application Form
class AffiliateApplicationForm(forms.ModelForm):
    class Meta:
        model = AffiliateApplication
        fields = ('program', 'why', 'bank_name', 'account_holder', 
                 'account_number', 'ifsc_code', 'agree_terms')
        widgets = {
            'program': forms.Select(attrs={'class': 'form-control'}),
            'why': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Tell us why you want to join',
                'rows': 4
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., State Bank of India'
            }),
            'account_holder': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'As per bank records'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your bank account number'
            }),
            'ifsc_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., SBIN0001234'
            }),
            'agree_terms': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


# Affiliate Withdrawal Form
class AffiliateWithdrawalForm(forms.ModelForm):
    class Meta:
        model = AffiliateWithdrawal
        fields = ('amount',)
        widgets = {
            'amount': forms.DecimalField(attrs={
                'class': 'form-control',
                'placeholder': 'Amount to withdraw'
            })
        }


# Affiliate Settings Form
class AffiliateSettingsForm(forms.Form):
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bank Name'
        })
    )
    account_holder = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Account Holder Name'
        })
    )
    account_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Account Number'
        })
    )
    ifsc_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'IFSC Code'
        })
    )
