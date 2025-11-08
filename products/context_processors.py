def cart_context(request):
    """Add cart count to all templates"""
    from .models import Cart
    
    cart_count = 0
    
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.total_items
        except Cart.DoesNotExist:
            cart_count = 0
    else:
        session_key = request.session.session_key
        if session_key:
            try:
                cart = Cart.objects.get(session_key=session_key)
                cart_count = cart.total_items
            except Cart.DoesNotExist:
                cart_count = 0
    
    return {
        'cart_count': cart_count
    }
