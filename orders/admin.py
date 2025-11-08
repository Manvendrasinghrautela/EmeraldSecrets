from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, Coupon


# Cart Item Inline
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'total_price')


# Cart Admin
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at', 'get_items_count')
    search_fields = ('user__username',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CartItemInline]
    
    def get_items_count(self, obj):
        return obj.items.count()
    get_items_count.short_description = 'Items Count'


# Order Item Inline
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'quantity', 'price', 'total_price')


# Order Admin
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'user__username', 'shipping_email', 'shipping_phone')
    list_editable = ('status', 'payment_status')
    date_hierarchy = 'created_at'
    readonly_fields = ('order_number', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'affiliate_code', 'created_at', 'updated_at')
        }),
        ('Shipping Information', {
            'fields': (
                ('shipping_first_name', 'shipping_last_name'),
                ('shipping_phone', 'shipping_email'),
                'shipping_address_line1',
                'shipping_address_line2',
                ('shipping_city', 'shipping_state'),
                ('shipping_postal_code', 'shipping_country')
            )
        }),
        ('Pricing', {
            'fields': ('subtotal', 'shipping_cost', 'tax', 'discount', 'total')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status', 'payment_id')
        }),
        ('Status & Notes', {
            'fields': ('status', 'notes')
        }),
    )
    
    actions = ['mark_as_processing', 'mark_as_shipped', 'mark_as_delivered']
    
    def mark_as_processing(self, request, queryset):
        queryset.update(status='processing')
    mark_as_processing.short_description = "Mark as Processing"
    
    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')
    mark_as_shipped.short_description = "Mark as Shipped"
    
    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered')
    mark_as_delivered.short_description = "Mark as Delivered"


# Coupon Admin
@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'valid_from', 'valid_to', 'is_active', 'uses_count')
    list_filter = ('discount_type', 'is_active', 'valid_from', 'valid_to')
    search_fields = ('code',)
    list_editable = ('is_active',)
    date_hierarchy = 'valid_from'
    readonly_fields = ('uses_count',)
    
    fieldsets = (
        ('Coupon Information', {
            'fields': ('code',)
        }),
        ('Discount', {
            'fields': ('discount_type', 'discount_value')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_to', 'min_purchase', 'max_uses', 'uses_count')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
