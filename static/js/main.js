// Main JavaScript - Global Functions

document.addEventListener('DOMContentLoaded', function() {
    console.log('Emerald Secrets loaded successfully');
    
    // Initialize tooltips
    initTooltips();
    
    // Initialize notifications
    initNotifications();
    
    // Update cart count
    updateCartCount();
    
    // Update wishlist count
    updateWishlistCount();
});

// Tooltips
function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.getAttribute('data-tooltip');
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.top = (rect.top - 40) + 'px';
            tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltip = document.querySelector('.tooltip');
            if (tooltip) tooltip.remove();
        });
    });
}

// Notifications
function initNotifications() {
    const notifications = document.querySelectorAll('[data-notification]');
    notifications.forEach(notif => {
        setTimeout(() => {
            notif.style.display = 'none';
        }, 5000);
    });
}

// Cart Count - Using URLs from window.URLS
function updateCartCount() {
    if (typeof window.URLS === 'undefined' || !window.URLS.cartCount) {
        console.log('Cart count URL not available');
        return;
    }
    
    fetch(window.URLS.cartCount)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            const cartBadge = document.getElementById('cartCount');
            if (cartBadge) {
                cartBadge.textContent = data.count;
            }
        })
        .catch(error => console.log('Cart count error:', error));
}

// Wishlist Count - Using URLs from window.URLS
function updateWishlistCount() {
    if (typeof window.URLS === 'undefined' || !window.URLS.wishlistCount) {
        console.log('Wishlist count URL not available');
        return;
    }
    
    fetch(window.URLS.wishlistCount)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            const wishlistBadge = document.getElementById('wishlistCount');
            if (wishlistBadge) {
                wishlistBadge.textContent = data.count;
            }
        })
        .catch(error => console.log('Wishlist count error:', error));
}

// Show Message
function showMessage(message, type = 'info') {
    const div = document.createElement('div');
    div.className = `alert alert-${type}`;
    div.textContent = message;
    document.body.insertBefore(div, document.body.firstChild);
    setTimeout(() => div.remove(), 5000);
}

// Format Currency
function formatCurrency(amount) {
    return '₹' + parseFloat(amount).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Confirm Action
function confirmAction(message) {
    return confirm(message);
}

// Scroll to Top
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Add Event Listeners
window.addEventListener('scroll', function() {
    const scrollBtn = document.getElementById('scrollToTop');
    if (scrollBtn) {
        if (window.pageYOffset > 300) {
            scrollBtn.style.display = 'block';
        } else {
            scrollBtn.style.display = 'none';
        }
    }
});
