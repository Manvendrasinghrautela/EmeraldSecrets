from .models import Cart

def get_or_create_cart(request):
    """Gets the cart for the user, or creates one if not present."""
    cart = None
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user, is_active=True)
    else:
        # handle anonymous cart logic. Example (if you use session-based carts):
        cart_id = request.session.get('cart_id')
        if cart_id:
            cart = Cart.objects.filter(id=cart_id, is_active=True).first()
        if not cart:
            cart = Cart.objects.create(is_active=True)
            request.session['cart_id'] = cart.id
    return cart
