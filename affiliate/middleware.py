from django.utils.deprecation import MiddlewareMixin
from affiliate.models import AffiliateUser, AffiliateClick


class AffiliateTrackingMiddleware(MiddlewareMixin):
    """Track affiliate referral links"""
    
    def process_request(self, request):
        # Check if URL has ?ref= parameter
        ref_code = request.GET.get('ref')
        
        if ref_code:
            try:
                affiliate = AffiliateUser.objects.get(
                    affiliate_code=ref_code,
                    status='active'
                )
                
                # Store affiliate code in cookie (30 days)
                request.affiliate_code = ref_code
                
                # Track the click
                AffiliateClick.objects.create(
                    affiliate=affiliate,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    referrer=request.META.get('HTTP_REFERER', ''),
                    session_key=request.session.session_key or ''
                )
                
            except AffiliateUser.DoesNotExist:
                pass
        
        return None
    
    def process_response(self, request, response):
        # Set cookie if affiliate code was found
        if hasattr(request, 'affiliate_code'):
            response.set_cookie(
                'affiliate_code',
                request.affiliate_code,
                max_age=30*24*60*60,  # 30 days
                httponly=True
            )
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
