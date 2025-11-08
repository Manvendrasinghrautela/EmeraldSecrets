from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Add this import for product collection views
from products import views as product_views

urlpatterns = [
    path('', product_views.home, name='home'),

    path('admin/', admin.site.urls),

    # Direct top-level collections URLs
    path('collections/', product_views.collection_list, name='collection_list_root'),
    path('collections/<slug:slug>/', product_views.collection_detail, name='collection_detail_root'),

    # Products app (includes /products/collections/ for all current links)
    path('products/', include(('products.urls', 'products'), namespace='products')),

    # Other apps
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('affiliate/', include(('affiliate.urls', 'affiliate'), namespace='affiliate')),
]

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
