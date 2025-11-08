// Shopping Cart Functions

// Add to Cart
function addToCart(productId) {
    const quantity = document.getElementById('quantity_' + productId)?.value || 1;
    
    fetch(`/orders/add-to-cart/${productId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ quantity: parseInt(quantity) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Product added to cart!', 'success');
            updateCartCount();
        } else {
            showMessage(data.message || 'Error adding to cart', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error adding to cart', 'danger');
    });
}

// Update Cart Quantity
function updateQuantity(itemId, quantity) {
    if (quantity < 1) return;
    
    fetch(`/orders/update-cart/${itemId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ quantity: parseInt(quantity) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        }
    })
    .catch(error => console.error('Error:', error));
}

// Remove from Cart
function removeFromCart(itemId) {
    if (confirmAction('Remove this item from cart?')) {
        fetch(`/orders/remove-from-cart/${itemId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        })
        .catch(error => console.error('Error:', error));
    }
}

// Apply Coupon
function applyCoupon() {
    const code = document.getElementById('coupon_code')?.value;
    
    if (!code) {
        showMessage('Please enter coupon code', 'warning');
        return;
    }
    
    fetch('/orders/apply-coupon/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ code: code })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Coupon applied!', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showMessage(data.message || 'Invalid coupon', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error applying coupon', 'danger');
    });
}

// Get CSRF Token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
