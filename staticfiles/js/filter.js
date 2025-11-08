// Product Filter Functions

// Apply Filters
function applyFilters() {
    const category = document.getElementById('categoryFilter')?.value;
    const minPrice = document.getElementById('minPrice')?.value;
    const maxPrice = document.getElementById('maxPrice')?.value;
    const sort = document.getElementById('sortFilter')?.value;
    
    const params = new URLSearchParams();
    
    if (category) params.append('category', category);
    if (minPrice) params.append('min_price', minPrice);
    if (maxPrice) params.append('max_price', maxPrice);
    if (sort) params.append('sort', sort);
    
    window.location.search = params.toString();
}

// Price Range Filter
function setPriceRange() {
    const minInput = document.getElementById('minPrice');
    const maxInput = document.getElementById('maxPrice');
    
    if (minInput && maxInput) {
        minInput.addEventListener('change', applyFilters);
        maxInput.addEventListener('change', applyFilters);
    }
}

// Category Filter
function setCategoryFilter() {
    const categorySelect = document.getElementById('categoryFilter');
    if (categorySelect) {
        categorySelect.addEventListener('change', applyFilters);
    }
}

// Sort Filter
function setSortFilter() {
    const sortSelect = document.getElementById('sortFilter');
    if (sortSelect) {
        sortSelect.addEventListener('change', applyFilters);
    }
}

// Clear Filters
function clearFilters() {
    window.location.href = window.location.pathname;
}

// Initialize Filters
document.addEventListener('DOMContentLoaded', function() {
    setPriceRange();
    setCategoryFilter();
    setSortFilter();
});
