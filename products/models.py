"""
Products App Models - Updated with Email Notification and Review Model
Contains models for Categories, Products, Collections, Product Images, and Reviews
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required



class Category(models.Model):
    """Product Categories (e.g., Face Care, Hair Care, Body Care)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:category_detail', kwargs={'slug': self.slug})


class Collection(models.Model):
    """Product Collections (e.g., The Glow Collection, Detox Collection)"""
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to='collections/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-featured', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:collection_detail', kwargs={'slug': self.slug})


class Product(models.Model):
    """Main Product Model"""
    SIZE_CHOICES = [
        ('50ml', '50ml'),
        ('100ml', '100ml'),
        ('200ml', '200ml'),
        ('50g', '50g'),
        ('100g', '100g'),
        ('200g', '200g'),
    ]

    ORIGIN_CHOICES = [
        ('India', 'India'),
        ('International', 'International'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    
    # Categorization
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    collection = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Inventory
    stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    
    # Product Details
    size = models.CharField(max_length=50, choices=SIZE_CHOICES, default='100ml')
    ingredients = models.TextField(blank=True, help_text="List of ingredients")
    origin = models.CharField(max_length=50, choices=ORIGIN_CHOICES, default='India')
    shelf_life = models.CharField(max_length=50, blank=True, help_text="e.g., 12 Months")
    
    # Benefits (for display on product page)
    benefits = models.TextField(blank=True, help_text="Key benefits, one per line")
    
    # Images
    main_image = models.ImageField(upload_to='products/', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'is_featured']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            self.sku = f"ES-{self.slug[:20].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:product_detail', kwargs={'slug': self.slug})

    @property
    def discount_percentage(self):
        """Calculate discount percentage if compare_at_price exists"""
        if self.compare_at_price and self.compare_at_price > self.price:
            return int(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return 0

    @property
    def in_stock(self):
        """Check if product is in stock"""
        return self.stock > 0
    
    @property
    def average_rating(self):
        """Calculate average rating from approved reviews"""
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return round(reviews.aggregate(models.Avg('rating'))['rating__avg'], 1)
        return 0
    
    @property
    def review_count(self):
        """Get count of approved reviews"""
        return self.reviews.filter(is_approved=True).count()

    def notify_subscribers_about_new_product(self):
        """
        Send email to all newsletter subscribers and active users about new product
        """
        # Check if email notifications are enabled
        send_emails = getattr(settings, 'SEND_NOTIFICATION_EMAILS', False)
        if not send_emails:
            return
        
        try:
            # Get all newsletter subscribers
            newsletter_emails = list(Newsletter.objects.filter(
                is_active=True
            ).values_list('email', flat=True))
            
            # Get all active users' emails (if user profile model exists)
            try:
                user_emails = list(User.objects.filter(
                    is_active=True,
                    profile__receive_promotional_emails=True
                ).values_list('email', flat=True))
            except:
                user_emails = []
            
            # Combine and remove duplicates
            all_emails = list(set(newsletter_emails + user_emails))
            
            if not all_emails:
                return
            
            # Prepare email content
            subject = f'🌿 New Product Launch: {self.name}'
            
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            site_name = getattr(settings, 'SITE_NAME', 'Emerald Secrets')
            
            context = {
                'product_name': self.name,
                'product_description': self.short_description or self.description[:200],
                'product_price': self.price,
                'product_url': f"{site_url}{self.get_absolute_url()}",
                'site_name': site_name,
            }
            
            # Render email template
            try:
                message = render_to_string('emails/new_product_notification.html', context)
            except:
                message = f"New product available: {self.name} - {self.short_description or self.description[:100]}"
            
            # Send email to all subscribers
            send_mail(
                subject=subject,
                message=self.short_description or self.description[:100],
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
                recipient_list=all_emails,
                html_message=message,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending product notification: {str(e)}")

class Cart(models.Model):
    """Shopping Cart"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='productcart', null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"Cart for {self.user.username}"
        return f"Cart {self.session_key}"

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def tax(self):
        return self.subtotal * Decimal('0.18')  # 18% tax

    @property
    def shipping(self):
        return Decimal('50.00') if self.subtotal > 0 else Decimal('0.00')

    @property
    def total(self):
        return self.subtotal + self.tax + self.shipping


class CartItem(models.Model):
    """Cart Items"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='productitems')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_cartitems')
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cart', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def total_price(self):
        return self.product.price * self.quantity

class ProductImage(models.Model):
    """Additional product images for gallery"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"


class Review(models.Model):
    """
    Product Review Model
    Allows users to leave ratings and reviews for products
    """
    RATING_CHOICES = [(i, i) for i in range(1, 6)]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'user']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'

    def __str__(self):
        return f"Review for {self.product.name} by {self.user.username} - {self.rating}★"
    
    def save(self, *args, **kwargs):
        """Send notification email when review is approved"""
        is_new = self.pk is None
        old_approved_status = None
        
        if not is_new:
            try:
                old_review = Review.objects.get(pk=self.pk)
                old_approved_status = old_review.is_approved
            except Review.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Send email if review is newly approved
        if not is_new and old_approved_status == False and self.is_approved == True:
            self.send_approval_email()
    
    def send_approval_email(self):
        """Send email to user when their review is approved"""
        send_emails = getattr(settings, 'SEND_NOTIFICATION_EMAILS', False)
        if not send_emails:
            return
            
        try:
            site_name = getattr(settings, 'SITE_NAME', 'Emerald Secrets')
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            subject = f'Your review has been approved - {site_name}'
            
            context = {
                'user_name': self.user.get_full_name() or self.user.username,
                'product_name': self.product.name,
                'rating': self.rating,
                'product_url': f"{site_url}{self.product.get_absolute_url()}",
                'site_name': site_name,
            }
            
            try:
                message = render_to_string('emails/review_approved.html', context)
            except:
                message = f'Your review for {self.product.name} has been approved!'
            
            send_mail(
                subject=subject,
                message=f'Your review for {self.product.name} has been approved!',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
                recipient_list=[self.user.email],
                html_message=message,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending review approval email: {str(e)}")


class Wishlist(models.Model):
    """User Wishlist"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'product']
        ordering = ['-added_at']
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

@require_POST
@login_required
def toggle_wishlist(request, product_id):
    try:
        product = Product.objects.get(pk=product_id)
        wishlist, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        if not created:
            wishlist.delete()
            return JsonResponse({'success': True, 'added': False})
        return JsonResponse({'success': True, 'added': True})
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
class Newsletter(models.Model):
    """Newsletter Subscriptions"""
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = 'Newsletter Subscription'
        verbose_name_plural = 'Newsletter Subscriptions'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Send welcome email when newsletter subscription is created"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        send_emails = getattr(settings, 'SEND_NOTIFICATION_EMAILS', False)
        if is_new and send_emails:
            self.send_welcome_email()
    
    def send_welcome_email(self):
        """Send welcome email to new subscriber"""
        try:
            site_name = getattr(settings, 'SITE_NAME', 'Emerald Secrets')
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            subject = f'Welcome to {site_name} Newsletter!'
            
            context = {
                'email': self.email,
                'site_name': site_name,
                'site_url': site_url,
            }
            
            try:
                message = render_to_string('emails/newsletter_welcome.html', context)
            except:
                message = f'Thank you for subscribing to {site_name} newsletter!'
            
            send_mail(
                subject=subject,
                message=f'Thank you for subscribing to {site_name} newsletter!',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
                recipient_list=[self.email],
                html_message=message,
                fail_silently=True,
            )
            
            # Send notification to admin
            self.send_admin_notification()
        except Exception as e:
            print(f"Error sending welcome email: {str(e)}")
    
    def send_admin_notification(self):
        """Notify admin about new subscription"""
        try:
            admin_email = getattr(settings, 'ADMIN_EMAIL', None)
            if not admin_email:
                return
                
            subject = f'New Newsletter Subscription - {self.email}'
            
            message = f"""
            A new user has subscribed to the newsletter.
            
            Email: {self.email}
            Subscribed at: {self.subscribed_at}
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
                recipient_list=[admin_email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending admin notification: {str(e)}")


class ContactMessage(models.Model):
    """Contact Us Messages"""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'

    def __str__(self):
        return f"{self.name} - {self.subject}"

    def save(self, *args, **kwargs):
        """Send confirmation email to user and notification to admin"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        send_emails = getattr(settings, 'SEND_NOTIFICATION_EMAILS', False)
        if is_new and send_emails:
            self.send_confirmation_email()
            self.send_admin_notification()
    
    def send_confirmation_email(self):
        """Send confirmation email to user"""
        try:
            site_name = getattr(settings, 'SITE_NAME', 'Emerald Secrets')
            
            subject = f'Message Received - {site_name}'
            
            context = {
                'name': self.name,
                'subject': self.subject,
                'site_name': site_name,
            }
            
            try:
                message = render_to_string('emails/contact_confirmation.html', context)
            except:
                message = f'Thank you for contacting {site_name}. We will get back to you soon!'
            
            send_mail(
                subject=subject,
                message=f'Thank you for contacting {site_name}. We will get back to you soon!',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
                recipient_list=[self.email],
                html_message=message,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending confirmation email: {str(e)}")
    
    def send_admin_notification(self):
        """Notify admin about new contact message"""
        try:
            admin_email = getattr(settings, 'ADMIN_EMAIL', None)
            if not admin_email:
                return
                
            subject = f'New Contact Message - {self.name}'
            
            message = f"""
            You have received a new contact message.
            
            Name: {self.name}
            Email: {self.email}
            Phone: {self.phone}
            Subject: {self.subject}
            
            Message:
            {self.message}
            
            Reply to: {self.email}
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@emeraldsecrets.com'),
                recipient_list=[admin_email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending admin notification: {str(e)}")
