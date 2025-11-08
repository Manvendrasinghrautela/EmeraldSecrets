// Search Functions

// Search Products
function searchProducts(query) {
    if (!query || query.trim() === '') {
        showMessage('Please enter search term', 'warning');
        return;
    }
    
    window.location.href = `/products/search/?q=${encodeURIComponent(query)}`;
}

// Auto-complete Search
function initAutoComplete() {
    const searchInput = document.querySelector('.search-form input');
    
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const query = e.target.value;
            
            if (query.length < 2) return;
            
            fetch(`/products/search-suggestions/?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    showSuggestions(data.suggestions, searchInput);
                })
                .catch(error => console.log('Search error:', error));
        });
    }
}

// Show Suggestions
function showSuggestions(suggestions, inputElement) {
    const container = document.getElementById('searchSuggestions');
    
    if (!container) {
        const div = document.createElement('div');
        div.id = 'searchSuggestions';
        div.className = 'search-suggestions';
        inputElement.parentElement.appendChild(div);
    }
    
    const suggestionsList = document.getElementById('searchSuggestions');
    
    if (suggestions.length === 0) {
        suggestionsList.style.display = 'none';
        return;
    }
    
    suggestionsList.innerHTML = suggestions.map(suggestion => 
        `<div class="suggestion-item" onclick="selectSuggestion('${suggestion}')">${suggestion}</div>`
    ).join('');
    
    suggestionsList.style.display = 'block';
}

// Select Suggestion
function selectSuggestion(term) {
    document.querySelector('.search-form input').value = term;
    searchProducts(term);
}

// Initialize on Load
document.addEventListener('DOMContentLoaded', initAutoComplete);
