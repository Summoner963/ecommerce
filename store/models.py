from django.conf import settings
from django.utils.timezone import now
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.utils.text import slugify


# Color Model
class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^#(?:[0-9a-fA-F]{3}){1,2}$', message="Enter a valid HEX color code.")],
    )  # Optional for color preview

    def __str__(self):
        return self.name




# ── NEW: Style Model (replaces style) ──
class Style(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to='style_icons/', null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return Product.objects.filter(style=self).count()


# ── NEW: Brand Model ──
class Brand(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    logo = models.FileField(upload_to='brand_logos/', null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ── NEW: Size Model ──
class Size(models.Model):
    UNIT_CHOICES = [
        ('L', 'Liters'),
        ('kg', 'Kilograms'),
        ('other', 'Other'),
    ]
    value = models.DecimalField(max_digits=6, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='L')

    def __str__(self):
        return f"{self.value} {self.unit}"

    class Meta:
        unique_together = ('value', 'unit')
        ordering = ['unit', 'value']


# ── NEW: Material Model ──
class Material(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


# Product Model
class Product(models.Model):
    name = models.CharField(max_length=255)
    style = models.ForeignKey(Style, related_name='products', on_delete=models.CASCADE)
    brand = models.ForeignKey(Brand, related_name='products', on_delete=models.SET_NULL, null=True, blank=True)
    sizes = models.ManyToManyField(Size, related_name='products', blank=True)
    material = models.ForeignKey(Material, related_name='products', on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    description = models.TextField()
    image = models.ImageField(upload_to='products/')
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(default=now)
    is_active = models.BooleanField(default=True)
    colors = models.ManyToManyField(Color, related_name='products', blank=True)

    def clean(self):
        if self.original_price and self.price > self.original_price:
            raise ValueError("The selling price cannot exceed the original price.")

    def __str__(self):
        return self.name

# ── REMOVE ColorStock entirely, ADD ColorSizeStock ──

class ColorSizeStock(models.Model):
    product = models.ForeignKey(Product, related_name='color_size_stocks', on_delete=models.CASCADE)
    color   = models.ForeignKey(Color,   related_name='color_size_stocks', on_delete=models.CASCADE)
    size    = models.ForeignKey(Size,    related_name='color_size_stocks', on_delete=models.CASCADE)
    stock   = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('product', 'color', 'size')

    def __str__(self):
        return f"{self.product.name} | {self.color.name} | {self.size} → {self.stock}"
    
# ProductImage Model
class ProductImage(models.Model):
    VIEW_CHOICES = [
        ('front', 'Front'),
        ('back',  'Back'),
        ('side',  'Side'),
        ('other', 'Other'),
    ]
    product   = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    color     = models.ForeignKey(Color, related_name='images', on_delete=models.CASCADE)
    image     = models.ImageField(upload_to='products/')
    view_type = models.CharField(max_length=10, choices=VIEW_CHOICES, default='front')
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color', 'view_type'],
                name='unique_image_per_color_view'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.color.name} ({self.view_type})"
    
# Custom User Manager
class UserManager(BaseUserManager):
    def create_user(self, email, name, phone=None, address=None, password=None):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            name=name,
            phone=phone or "",
            address=address or "",
        )
        user.set_password(password)
        user.is_active = True
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, phone=None, address=None, password=None):
        user = self.create_user(
            email=email,
            name=name,
            phone=phone,
            address=address,
            password=password,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# User Model
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    groups = models.ManyToManyField(
        Group,
        related_name="custom_user_set",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="custom_user_set",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.email} ({'Verified' if self.is_verified else 'Unverified'})"

class VerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    expiry = models.DateTimeField()
    
# Order Model
class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=now)
    completed = models.BooleanField(default=False)
    STATUS_CHOICES = [
        ('P', 'Pending'),
        ('S', 'Shipped'),
        ('D', 'Delivered'),
        ('C', 'Canceled')
    ]
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P')
    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('esewa', 'eSewa'),
        ('khalti', 'Khalti'),
    ]
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, blank=False)

    def total_cost(self):
        return sum(item.product.price * item.quantity for item in self.items.all())

    def __str__(self):
        return f"Order {self.id} - {self.user.email}"


# In OrderItem, add size field:
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.ForeignKey(Size, on_delete=models.SET_NULL, null=True, blank=True)  # NEW
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        size_str = str(self.size) if self.size else 'No Size'
        color_str = self.color.name if self.color else 'No Color'
        return f"{self.quantity} of {self.product.name} ({color_str}, {size_str})"

# Wishlist Model
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    products = models.ManyToManyField(Product)

    def __str__(self):
        return f"{self.user.email}'s Wishlist"


# Review Model
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])  # 1-5 scale
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.product.name} ({self.rating}/5)"


# Offer Model
class Offer(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    valid_until = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='offers')

    def __str__(self):
        return self.title


# ContactMessage Model
class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"
