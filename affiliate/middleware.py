from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from affiliate.models import AffiliateUser, AffiliateClick
import logging

logger = logging.getLogger('affiliate')


class AffiliateTrackingMiddleware(MiddlewareMixin):
    """
    Track affiliate referral links and store affiliate code in session/cookie
    
    This middleware:
    1. Checks for ?ref= parameter in URL
    2. Validates affiliate code and status
    3. Creates click tracking record
    4. Sets cookie for 30-day tracking window
    5. Stores code in session for payment integration
    6. Logs all tracking activity
    
    Usage:
    - Visit: http://example.com/?ref=ES-ABC123
    - Affiliate code automatically tracked
    - Commission calculated at checkout
    """
    
    def process_request(self, request):
        """
        Process incoming request to track affiliate referrals
        
        Args:
            request: Django request object
        
        Returns:
            None (continue to next middleware/view)
        """
        
        # Get affiliate code from URL parameter (?ref=CODE)
        ref_code = request.GET.get('ref') or request.GET.get('affiliate_code')
        
        if ref_code:
            try:
                # ✅ Validate affiliate exists and is active
                affiliate = AffiliateUser.objects.get(
                    affiliate_code=ref_code,
                    status='active'
                )
                
                # ✅ Store affiliate code in request for later use
                request.affiliate_code = ref_code
                request.affiliate_id = affiliate.id
                
                # ✅ Track the click for analytics
                click = AffiliateClick.objects.create(
                    affiliate=affiliate,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    referrer_url=request.META.get('HTTP_REFERER', '')[:500],
                    session_key=request.session.session_key or ''
                )
                
                # ✅ Store in session for payment processing
                request.session['affiliate_code'] = ref_code
                request.session['affiliate_id'] = affiliate.id
                request.session['affiliate_name'] = affiliate.user.get_full_name() or affiliate.user.username
                request.session.set_expiry(settings.AFFILIATE_COOKIE_DURATION * 24 * 60 * 60)  # 30 days
                
                logger.info(
                    f"✅ Affiliate click tracked: {ref_code} | "
                    f"IP: {self.get_client_ip(request)} | "
                    f"Session: {request.session.session_key}"
                )
                
            except AffiliateUser.DoesNotExist:
                logger.warning(f"⚠️  Invalid or inactive affiliate code: {ref_code}")
            except Exception as e:
                logger.error(f"❌ Error tracking affiliate: {str(e)}")
        
        return None
    
    def process_response(self, request, response):
        """
        Set cookie to persist affiliate tracking across browser restarts
        
        Args:
            request: Django request object
            response: Django response object
        
        Returns:
            Modified response with cookie set
        """
        
        # ✅ Set persistent cookie if affiliate code found
        if hasattr(request, 'affiliate_code'):
            try:
                affiliate_code = request.affiliate_code
                max_age = settings.AFFILIATE_COOKIE_DURATION * 24 * 60 * 60  # 30 days default
                
                response.set_cookie(
                    'affiliate_code',
                    affiliate_code,
                    max_age=max_age,
                    httponly=True,  # ✅ Security: Don't expose to JavaScript
                    samesite='Lax',  # ✅ Security: CSRF protection
                    path='/'  # Available site-wide
                )
                
                response.set_cookie(
                    'affiliate_id',
                    str(request.affiliate_id),
                    max_age=max_age,
                    httponly=True,
                    samesite='Lax',
                    path='/'
                )
                
                logger.info(f"✅ Affiliate cookie set for: {affiliate_code}")
                
            except Exception as e:
                logger.error(f"❌ Error setting affiliate cookie: {str(e)}")
        
        return response
    
    @staticmethod
    def get_client_ip(request):
        """
        Get the real client IP address from request
        
        Handles:
        - Direct connection (REMOTE_ADDR)
        - Behind proxy (X-Forwarded-For header)
        - Load balancer (multiple IPs)
        
        Args:
            request: Django request object
        
        Returns:
            str: IP address
        """
        
        # ✅ Check for X-Forwarded-For header (proxy/load balancer)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        
        if x_forwarded_for:
            # Get first IP if multiple are present
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            # ✅ Direct connection - use REMOTE_ADDR
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        return ip


# ============================================================================
# OPTIONAL: Enhanced Affiliate Tracking Middleware with Revenue Tracking
# ============================================================================

class AffiliateRevenueTrackingMiddleware(MiddlewareMixin):
    """
    Extended middleware for advanced affiliate tracking
    
    Additional features:
    - Track user journey through site
    - Monitor affiliate-sourced page views
    - Track conversion funnel
    - Calculate ROI per affiliate
    """
    
    def process_request(self, request):
        """Enhanced tracking with page analytics"""
        
        # Check if this is an affiliate-sourced visitor
        affiliate_code = request.session.get('affiliate_code') or request.COOKIES.get('affiliate_code')
        
        if affiliate_code and request.user.is_authenticated:
            try:
                # Store affiliate info in request for views
                affiliate = AffiliateUser.objects.get(affiliate_code=affiliate_code)
                request.affiliate_source = affiliate
                request.is_affiliate_referred = True
                
            except AffiliateUser.DoesNotExist:
                request.is_affiliate_referred = False
        else:
            request.is_affiliate_referred = False
        
        return None


# ============================================================================
# HELPER FUNCTIONS FOR AFFILIATE TRACKING
# ============================================================================

def get_affiliate_from_request(request):
    """
    Extract affiliate information from request
    
    Priority order:
    1. Session variable (most recent)
    2. Cookie (persistent)
    3. URL parameter (fresh)
    
    Args:
        request: Django request object
    
    Returns:
        tuple: (affiliate_code, affiliate_id) or (None, None)
    """
    
    # Check session first (most reliable)
    affiliate_code = request.session.get('affiliate_code')
    affiliate_id = request.session.get('affiliate_id')
    
    if affiliate_code and affiliate_id:
        return affiliate_code, affiliate_id
    
    # Check cookie if session not found
    if not affiliate_code:
        affiliate_code = request.COOKIES.get('affiliate_code')
        affiliate_id = request.COOKIES.get('affiliate_id')
    
    # Check URL parameter as last resort
    if not affiliate_code:
        affiliate_code = request.GET.get('ref')
        if affiliate_code:
            affiliate_id = None
    
    return affiliate_code, affiliate_id


def is_affiliate_referred(request):
    """
    Check if current request is from an affiliate
    
    Args:
        request: Django request object
    
    Returns:
        bool: True if referred by affiliate
    """
    
    affiliate_code, _ = get_affiliate_from_request(request)
    return bool(affiliate_code)


def get_affiliate_object(request):
    """
    Get AffiliateUser object from request
    
    Args:
        request: Django request object
    
    Returns:
        AffiliateUser object or None
    """
    
    affiliate_code, affiliate_id = get_affiliate_from_request(request)
    
    if not affiliate_code:
        return None
    
    try:
        if affiliate_id:
            return AffiliateUser.objects.get(id=affiliate_id, status='active')
        else:
            return AffiliateUser.objects.get(affiliate_code=affiliate_code, status='active')
    except AffiliateUser.DoesNotExist:
        return None


# ============================================================================
# SUMMARY OF AFFILIATE TRACKING FLOW
# ============================================================================

"""
AFFILIATE TRACKING FLOW:

1. User clicks referral link:
   http://example.com/?ref=ES-ABC123

2. Middleware intercepts request:
   ├─ AffiliateTrackingMiddleware.process_request()
   ├─ Validates affiliate code (must exist & be active)
   ├─ Creates AffiliateClick record
   ├─ Stores in request object
   └─ Stores in session (30 days)

3. Middleware sets cookie on response:
   └─ AffiliateTrackingMiddleware.process_response()
   └─ Sets persistent cookie (30 days)
   └─ httponly=True for security
   └─ samesite='Lax' for CSRF protection

4. User browses site:
   ├─ Cookie persists across page views
   ├─ Session maintained in Django
   └─ Affiliate code available to all views

5. User makes purchase:
   ├─ Payment success view triggered
   ├─ Payment code retrieves affiliate_code from session
   ├─ Calculates 5% commission
   ├─ Creates AffiliateOrder record
   └─ Updates affiliate.total_earnings

6. Commission tracked:
   ├─ Status: pending (7 days)
   ├─ Status: completed (auto-approved after 7 days)
   └─ Available for withdrawal

7. Withdrawal request:
   ├─ Affiliate requests payment
   ├─ Admin approves
   ├─ Payment processed
   └─ Affiliate.total_withdrawn updated


COOKIE & SESSION DURATION:
- Cookie duration: 30 days (from settings.AFFILIATE_COOKIE_DURATION)
- Session duration: 30 days
- Tracking window: User can purchase within 30 days of click


SECURITY FEATURES:
✅ httponly=True: Cookie not accessible via JavaScript (XSS protection)
✅ samesite='Lax': CSRF protection
✅ SSL/HTTPS recommended: Set SECURE_COOKIE=True in production
✅ Affiliate code validation: Only active affiliates tracked
✅ Logging: All tracking activity logged for audit


EXAMPLE REQUESTS:

1. Initial referral click:
   GET http://example.com/?ref=ES-ABC123
   
   Middleware:
   - Validates ES-ABC123 exists and is active
   - Creates AffiliateClick record
   - Sets session['affiliate_code'] = 'ES-ABC123'
   - Sets cookie affiliate_code = 'ES-ABC123'

2. User comes back next day:
   GET http://example.com/
   
   Middleware:
   - No ?ref parameter in URL
   - Checks cookie: affiliate_code = 'ES-ABC123' ✓
   - Loads from session if exists
   - Still tracked as affiliate-referred user

3. User purchases:
   POST /checkout/
   
   Payment view:
   - Gets affiliate_code from request.session or request.COOKIES
   - Calculates 5% commission
   - Creates AffiliateOrder
   - Affiliate earns commission ✅


HELPER FUNCTIONS:

get_affiliate_from_request(request)
- Returns: (affiliate_code, affiliate_id)
- Usage: In views and forms

is_affiliate_referred(request)
- Returns: bool
- Usage: Check if order is affiliate-sourced

get_affiliate_object(request)
- Returns: AffiliateUser or None
- Usage: Get affiliate data for order
"""