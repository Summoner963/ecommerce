from django.contrib import admin
from .models import (
    Color, ColorSizeStock, Style, Brand, Size, Material,
    Product, ProductImage,
    User, VerificationCode,
    Order, OrderItem,
    Wishlist, Review, Offer, ContactMessage,
)


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code')
    search_fields = ('name',)


@admin.register(Style)
class StyleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'product_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('value', 'unit')
    list_filter = ('unit',)
    ordering = ('unit', 'value')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ('color', 'view_type', 'image', 'is_default')


class ColorSizeStockInline(admin.TabularInline):
    model = ColorSizeStock
    extra = 1
    fields = ('color', 'size', 'stock')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'style', 'brand', 'material', 'price', 'is_active', 'created_at')
    list_filter = ('is_active', 'style', 'brand', 'material')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('colors', 'sizes')
    inlines = [ColorSizeStockInline, ProductImageInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'description', 'image', 'is_active')
        }),
        ('Classification', {
            'fields': ('style', 'brand', 'material', 'sizes', 'colors')
        }),
        ('Pricing', {
            'fields': ('price', 'original_price')
        }),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'color', 'size', 'quantity', 'item_total')
    fields = ('product', 'color', 'size', 'quantity', 'item_total')

    def item_total(self, obj):
        return f"Rs.{obj.product.price * obj.quantity}"
    item_total.short_description = "Total"


def make_status_action(status_code, status_label):
    def action_fn(modeladmin, request, queryset):
        updated = queryset.update(status=status_code)
        modeladmin.message_user(request, f"{updated} order(s) marked as {status_label}.")
    action_fn.__name__ = f'mark_{status_code}'
    action_fn.short_description = f"Mark selected orders as → {status_label}"
    return action_fn


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(completed=True)

    list_display = ('id', 'user', 'user_phone', 'user_address', 'status', 'payment_method', 'created_at', 'order_total')
    list_display_links = ('id', 'user')
    list_filter = ('status', 'payment_method')
    search_fields = ('user__email', 'user__phone', 'user__address')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'order_total', 'user_phone', 'user_address', 'completed')

    fieldsets = (
        ('Order Info',     {'fields': ('user', 'created_at', 'completed', 'order_total')}),
        ('Status & Payment', {'fields': ('status', 'payment_method')}),
        ('Customer Contact', {'fields': ('user_phone', 'user_address'), 'classes': ('collapse',)}),
    )

    actions = [
        make_status_action('P', 'Pending'),
        make_status_action('S', 'Shipped'),
        make_status_action('D', 'Delivered'),
        make_status_action('C', 'Canceled'),
    ]

    def user_phone(self, obj):   return obj.user.phone   or "—"
    def user_address(self, obj): return obj.user.address or "—"
    def order_total(self, obj):  return f"Rs.{obj.total_cost()}"

    user_phone.short_description   = "Phone"
    user_address.short_description = "Address"
    order_total.short_description  = "Total"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('user__email', 'product__name')


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'discount_percentage', 'valid_until')
    list_filter = ('valid_until',)
    search_fields = ('title', 'product__name')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at')
    search_fields = ('name', 'email', 'subject')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'is_verified', 'is_staff', 'is_active')
    list_filter = ('is_verified', 'is_staff', 'is_active')
    search_fields = ('email', 'name')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__email',)