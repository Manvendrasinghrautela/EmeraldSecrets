from django.urls import path
from . import views


app_name = 'affiliate'


urlpatterns = [
    # ============================================================================
    # PUBLIC PAGES - No authentication required
    # ============================================================================
    
    # Home page - affiliate program landing
    # Shows program details, stats, and call-to-action
    path('', views.affiliate_home, name='home'),
    
    # Join/Register page - affiliate application
    # User can apply to become affiliate
    path('join/', views.affiliate_join, name='join'),
    
    # Alias for join (backward compatibility)
    path('register/', views.affiliate_register, name='register'),
    
    # Click tracking - 30-day cookie persistence
    # Format: /affiliate/track/ES-ABC123/
    # Sets cookies for commission calculation
    path('track/<str:affiliate_code>/', views.track_affiliate_click, name='track'),
    
    
    # ============================================================================
    # AFFILIATE DASHBOARD - Authentication required (@login_required)
    # ============================================================================
    
    # Main dashboard - real-time metrics
    # Shows: clicks, orders, conversion rate, commission, balance
    path('dashboard/', views.affiliate_dashboard, name='dashboard'),
    
    # Affiliate profile view
    # Shows: affiliate code, status, bank details, statistics
    path('profile/', views.affiliate_profile, name='profile'),
    
    # Detailed statistics page
    # Shows: commission breakdown by status, order history, analytics
    path('stats/', views.affiliate_stats, name='stats'),
    
    
    # ============================================================================
    # REFERRAL LINKS & BANNERS - Authentication required
    # ============================================================================
    
    # Affiliate referral links page
    # Shows: referral link, available banners, click count
    path('links/', views.affiliate_links, name='links'),
    
    
    # ============================================================================
    # WITHDRAWAL MANAGEMENT - Authentication required
    # ============================================================================
    
    # Withdrawals page
    # Shows: balance, pending withdrawals, withdrawal history
    # Displays: minimum requirement, available amount, previous requests
    path('withdrawals/', views.affiliate_withdrawals, name='withdrawals'),
    
    # Submit withdrawal request (POST only)
    # Creates withdrawal request with validation
    # Validates: minimum amount, sufficient balance
    path('withdrawals/request/', views.request_withdrawal, name='request_withdrawal'),
    
    
    # ============================================================================
    # SETTINGS - Authentication required
    # ============================================================================
    
    # Affiliate settings page
    # Update: bank name, account holder, account number, IFSC code
    # Used for withdrawal payments
    path('settings/', views.affiliate_settings, name='settings'),
]


# ============================================================================
# URL PATTERNS SUMMARY
# ============================================================================

"""
COMPLETE AFFILIATE URL STRUCTURE:

PUBLIC PAGES (No login required):
  GET  /affiliate/                    → affiliate_home()
       Show program details and stats
       Redirect to dashboard if already affiliate
  
  GET  /affiliate/join/              → affiliate_join()
       Application form (if not authenticated, shows login prompt)
  
  GET  /affiliate/register/          → affiliate_register() [alias]
  
  GET  /affiliate/track/<code>/      → track_affiliate_click()
       Tracking link - sets 30-day cookies
       Redirects to home page


AUTHENTICATED PAGES (Login required):
  GET  /affiliate/dashboard/         → affiliate_dashboard()
       Real-time metrics
       ├─ Clicks: 127
       ├─ Orders: 5
       ├─ Conversion: 3.94%
       ├─ Commission (5%): ₹250
       ├─ Pending: ₹50
       ├─ Available: ₹200
       └─ Recent orders + top products
  
  GET  /affiliate/profile/           → affiliate_profile()
       Show affiliate information
       └─ Code, status, earnings, bank details
  
  GET  /affiliate/stats/             → affiliate_stats()
       Detailed statistics
       ├─ Status breakdown: pending, confirmed, paid, failed
       ├─ Commission breakdown by status
       ├─ Click-to-order ratio
       └─ Paginated order history
  
  GET  /affiliate/links/             → affiliate_links()
       Referral links & banners
       ├─ Referral link: /affiliate/track/CODE/
       ├─ Available banners (HTML/embed code)
       └─ Click statistics
  
  GET  /affiliate/withdrawals/       → affiliate_withdrawals()
       Withdrawal management
       ├─ Total earned: ₹250
       ├─ Pending requests: ₹50
       ├─ Available balance: ₹200
       └─ Withdrawal history + form
  
  POST /affiliate/withdrawals/request/ → request_withdrawal()
       Submit withdrawal request
       Validates:
       ├─ Minimum ₹1000
       ├─ Sufficient balance
       └─ Creates AffiliateWithdrawal (status=pending)
  
  GET  /affiliate/settings/          → affiliate_settings()
       Affiliate settings
       └─ Update: bank name, account holder, account number, IFSC
  
  POST /affiliate/settings/          → affiliate_settings()
       Save settings with validation


COMMISSION FLOW THROUGH URLs:

1. User clicks referral link:
   GET /affiliate/track/ES-ABC123/
   ├─ Track click in AffiliateClick
   ├─ Set cookies (30 days)
   └─ Redirect to home

2. User makes purchase (in payments/views.py):
   ├─ Affiliate code from request.session['affiliate_code']
   ├─ Calculate 5% commission
   ├─ Create AffiliateOrder (status='pending')
   └─ Send email to affiliate

3. Affiliate checks dashboard:
   GET /affiliate/dashboard/
   ├─ Show pending commission
   ├─ After 7 days: status changes to 'confirmed'
   └─ Display available balance

4. Affiliate requests withdrawal:
   GET /affiliate/withdrawals/
   POST /affiliate/withdrawals/request/
   ├─ Validate balance
   ├─ Create AffiliateWithdrawal
   └─ Redirect to withdrawals page


INTEGRATION WITH OTHER APPS:

accounts/urls.py:
  GET /accounts/profile/
      └─ May show affiliate link if user is affiliate

payments/urls.py:
  POST /payments/callback/
       └─ Creates AffiliateOrder on successful payment

products/urls.py:
  └─ Referral link redirects to product home


URL NAMING CONVENTION:

app_name = 'affiliate'

Usage in templates:
  {% url 'affiliate:home' %}              → /affiliate/
  {% url 'affiliate:join' %}              → /affiliate/join/
  {% url 'affiliate:dashboard' %}         → /affiliate/dashboard/
  {% url 'affiliate:links' %}             → /affiliate/links/
  {% url 'affiliate:withdrawals' %}       → /affiliate/withdrawals/
  {% url 'affiliate:track' code=code %}   → /affiliate/track/CODE/

Usage in views:
  redirect('affiliate:home')
  redirect('affiliate:dashboard')


MIDDLEWARE INTEGRATION:

affiliate/middleware.py:
  Extracts affiliate code from URL parameter: ?ref=ES-ABC123
  Stores in: request.session['affiliate_code']
  
  In track_affiliate_click view:
    Explicit tracking via URL path: /affiliate/track/CODE/
    Sets cookies for 30-day persistence


SECURITY NOTES:

✅ Public pages (home, join, track) - No authentication
✅ Tracking endpoint - No authentication (public referral link)
✅ Dashboard, stats, links, settings - @login_required
✅ Withdrawals - @login_required + @require_POST for form submission
✅ All views validate affiliate ownership (filter by request.user)


PERFORMANCE:

✅ Track click view:
   - Fast redirect (no template rendering)
   - Async-safe click recording
   - Cookie setting overhead minimal

✅ Dashboard view:
   - Uses select_related('order') to avoid N+1 queries
   - Aggregation for sum calculations
   - Pagination for large datasets

✅ Withdrawal view:
   - Single database query for balance calculation
   - Pagination for history (10 per page)


TESTING URLS:

python manage.py shell
from django.urls import reverse
from django.test import Client

# Test public URLs
reverse('affiliate:home')              # /affiliate/
reverse('affiliate:join')              # /affiliate/join/
reverse('affiliate:track', args=['ES-ABC123'])  # /affiliate/track/ES-ABC123/

# Test authenticated URLs
reverse('affiliate:dashboard')         # /affiliate/dashboard/
reverse('affiliate:stats')             # /affiliate/stats/
reverse('affiliate:links')             # /affiliate/links/
reverse('affiliate:withdrawals')       # /affiliate/withdrawals/

# Test POST
client = Client()
client.post(reverse('affiliate:request_withdrawal'), {'amount': '500'})
"""