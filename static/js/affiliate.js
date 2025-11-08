// Affiliate Program Functions

// Copy Referral Link
function copyReferralLink() {
    const link = document.getElementById('affiliateLink');
    
    if (!link) {
        showMessage('Referral link not found', 'danger');
        return;
    }
    
    link.select();
    document.execCommand('copy');
    showMessage('Referral link copied to clipboard!', 'success');
}

// Copy Banner Code
function copyBannerCode(button) {
    const textarea = button.parentElement.querySelector('textarea');
    
    if (!textarea) return;
    
    textarea.select();
    document.execCommand('copy');
    
    const originalText = button.textContent;
    button.textContent = 'Copied!';
    setTimeout(() => {
        button.textContent = originalText;
    }, 2000);
}

// Request Withdrawal
function requestWithdrawal() {
    const amount = document.getElementById('withdrawalAmount')?.value;
    
    if (!amount || parseFloat(amount) <= 0) {
        showMessage('Please enter valid amount', 'warning');
        return;
    }
    
    if (confirmAction(`Request withdrawal of ₹${amount}?`)) {
        fetch('/affiliate/request-withdrawal/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ amount: parseFloat(amount) })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('Withdrawal request submitted!', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showMessage(data.message || 'Error processing request', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Error processing request', 'danger');
        });
    }
}

// Update Bank Details
function updateBankDetails() {
    const form = document.getElementById('bankDetailsForm');
    
    if (!form) return;
    
    const formData = new FormData(form);
    
    fetch('/affiliate/update-bank-details/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Bank details updated!', 'success');
        } else {
            showMessage(data.message || 'Error updating details', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error updating details', 'danger');
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
