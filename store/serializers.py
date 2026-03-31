# store/serializers.py

from rest_framework import serializers
from .models import (
    Product, ProductImage, Color, Size, Style, Brand, Material,
    Order, OrderItem, Review, Wishlist, Offer
)


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Color
        fields = ['id', 'name', 'hex_code']


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Size
        fields = ['id', 'value', 'unit']


class StyleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Style
        fields = ['id', 'name', 'slug']


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Brand
        fields = ['id', 'name']


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Material
        fields = ['id', 'name']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProductImage
        fields = ['id', 'image', 'view_type', 'color']


# ── Lightweight card serializer (used for listing / search / home) ──────────
class ProductCardSerializer(serializers.ModelSerializer):
    """
    Mirrors the enriched_products dict that home() / search_products() build.
    Includes color dot data, best display image, stock info, ratings.
    """
    style        = StyleSerializer(read_only=True)
    brand        = BrandSerializer(read_only=True)
    material     = MaterialSerializer(read_only=True)
    avg_rating   = serializers.FloatField(read_only=True)
    review_count = serializers.SerializerMethodField()

    # Enriched fields — populated by the view via context
    display_image      = serializers.SerializerMethodField()
    display_color      = serializers.SerializerMethodField()
    is_out_of_stock    = serializers.SerializerMethodField()
    display_stock      = serializers.SerializerMethodField()
    all_colors         = serializers.SerializerMethodField()
    color_count        = serializers.SerializerMethodField()
    in_wishlist        = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'price', 'original_price',
            'style', 'brand', 'material',
            'avg_rating', 'review_count',
            'display_image', 'display_color',
            'is_out_of_stock', 'display_stock',
            'all_colors', 'color_count',
            'in_wishlist',
        ]

    # The view passes `enriched` dict via context: {'enriched': {product_id: entry}}
    def _entry(self, obj):
        return self.context.get('enriched', {}).get(obj.id, {})

    def get_review_count(self, obj):
        return obj.reviews.count()

    def get_display_image(self, obj):
        entry = self._entry(obj)
        request = self.context.get('request')
        url = entry.get('display_image', '')
        return request.build_absolute_uri(url) if request and url else url

    def get_display_color(self, obj):
        entry = self._entry(obj)
        color = entry.get('display_color')
        if color:
            return {'id': color.id, 'name': color.name, 'hex_code': color.hex_code}
        return None

    def get_is_out_of_stock(self, obj):
        return self._entry(obj).get('is_out_of_stock', True)

    def get_display_stock(self, obj):
        return self._entry(obj).get('display_stock', 0)

    def get_all_colors(self, obj):
        entry = self._entry(obj)
        request = self.context.get('request')
        colors = entry.get('all_colors', [])
        result = []
        for c in colors:
            img_url = c.get('img_url', '')
            result.append({
                'color_id':         c['color_id'],
                'color_name':       c['color_name'],
                'hex_code':         c['hex_code'],
                'img_url':          request.build_absolute_uri(img_url) if request and img_url else img_url,
                'in_stock':         c['in_stock'],
                'best_size_id':     c['best_size_id'],
                'best_combo_stock': c['best_combo_stock'],
            })
        return result

    def get_color_count(self, obj):
        return self._entry(obj).get('color_count', 0)

    def get_in_wishlist(self, obj):
        return obj.id in self.context.get('wishlist_product_ids', [])


# ── Full product detail serializer ──────────────────────────────────────────
class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model  = Review
        fields = ['id', 'user_name', 'rating', 'comment', 'created_at']


class ProductDetailSerializer(serializers.ModelSerializer):
    style    = StyleSerializer(read_only=True)
    brand    = BrandSerializer(read_only=True)
    material = MaterialSerializer(read_only=True)
    colors   = ColorSerializer(many=True, read_only=True)
    sizes    = SizeSerializer(many=True, read_only=True)
    images   = ProductImageSerializer(many=True, read_only=True)
    reviews  = ReviewSerializer(many=True, read_only=True)
    avg_rating          = serializers.FloatField(read_only=True)
    discount_percentage = serializers.SerializerMethodField()

    # Stock map: {color_id: {size_id: stock}}
    stock_map           = serializers.SerializerMethodField()
    colors_with_stock   = serializers.SerializerMethodField()
    sizes_with_stock    = serializers.SerializerMethodField()
    default_color       = serializers.SerializerMethodField()
    default_size        = serializers.SerializerMethodField()
    initial_combo_stock = serializers.SerializerMethodField()
    in_wishlist         = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'original_price',
            'style', 'brand', 'material',
            'colors', 'sizes', 'images', 'reviews',
            'avg_rating', 'discount_percentage',
            'stock_map', 'colors_with_stock', 'sizes_with_stock',
            'default_color', 'default_size', 'initial_combo_stock',
            'in_wishlist',
        ]

    def get_discount_percentage(self, obj):
        if obj.original_price and obj.price:
            return round((obj.original_price - obj.price) / obj.original_price * 100, 2)
        return None

    def get_stock_map(self, obj):
        return self.context.get('stock_map_json', {})

    def get_colors_with_stock(self, obj):
        return self.context.get('colors_with_stock_data', [])

    def get_sizes_with_stock(self, obj):
        return self.context.get('sizes_with_stock_data', [])

    def get_default_color(self, obj):
        color = self.context.get('default_color')
        if color:
            return {'id': color.id, 'name': color.name, 'hex_code': color.hex_code}
        return None

    def get_default_size(self, obj):
        size = self.context.get('default_size')
        if size:
            return {'id': size.id, 'value': size.value, 'unit': size.unit}
        return None

    def get_initial_combo_stock(self, obj):
        return self.context.get('initial_combo_stock', 0)

    def get_in_wishlist(self, obj):
        return obj.id in self.context.get('wishlist_product_ids', [])


# ── Cart / Order serializers ─────────────────────────────────────────────────
class OrderItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source='product.name', read_only=True)
    product_slug  = serializers.CharField(source='product.slug', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    color_name    = serializers.CharField(source='color.name', read_only=True, default=None)
    size_label    = serializers.SerializerMethodField()
    image_url     = serializers.SerializerMethodField()
    subtotal      = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            'id', 'product_name', 'product_slug', 'product_price',
            'color_name', 'size_label', 'image_url',
            'quantity', 'subtotal',
        ]

    def get_size_label(self, obj):
        if obj.size:
            return f"{obj.size.value} {obj.size.unit}"
        return None

    def get_image_url(self, obj):
        request = self.context.get('request')
        image_url = obj.product.image.url
        if obj.color:
            color_image = (
                obj.product.images.filter(color=obj.color, view_type='front').first()
                or obj.product.images.filter(color=obj.color).first()
            )
            if color_image:
                image_url = color_image.image.url
        return request.build_absolute_uri(image_url) if request else image_url

    def get_subtotal(self, obj):
        return obj.product.price * obj.quantity


class OrderSerializer(serializers.ModelSerializer):
    items       = OrderItemSerializer(many=True, read_only=True)
    total_cost  = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = ['id', 'created_at', 'completed', 'status', 'payment_method', 'items', 'total_cost']

    def get_total_cost(self, obj):
        return obj.total_cost()


# ── Wishlist serializer ──────────────────────────────────────────────────────
class WishlistSerializer(serializers.ModelSerializer):
    products = ProductCardSerializer(many=True, read_only=True)

    class Meta:
        model  = Wishlist
        fields = ['id', 'products']


# ── Offer serializer ─────────────────────────────────────────────────────────
class OfferSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source='product.name', read_only=True)
    product_slug  = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model  = Offer
        fields = ['id', 'title', 'discount_percentage', 'valid_until', 'product_name', 'product_slug', 'product_image']

    def get_product_image(self, obj):
        request = self.context.get('request')
        url = obj.product.image.url
        return request.build_absolute_uri(url) if request else url