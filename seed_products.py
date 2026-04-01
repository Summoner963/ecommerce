import os
import django
from pathlib import Path

# Setup Django context
BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')
django.setup()

from django.core.files import File
from django.utils.text import slugify
from store.models import Color, Style, Brand, Size, Material, Product, ProductImage, ColorSizeStock

STATIC_PRODUCT_DIR = BASE_DIR / 'store' / 'static' / 'images' / 'products'

# Helper functions

def open_image_file(relative_path):
    src = STATIC_PRODUCT_DIR / relative_path
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {src}")
    return open(src, 'rb')


def get_or_create_color(name, hex_code=None):
    color, _ = Color.objects.get_or_create(name=name, defaults={'hex_code': hex_code or ''})
    if hex_code and color.hex_code != hex_code:
        color.hex_code = hex_code
        color.save()
    return color


def get_or_create_style(name):
    slug = slugify(name)
    style, _ = Style.objects.get_or_create(name=name, defaults={'slug': slug})
    return style


def get_or_create_brand(name):
    slug = slugify(name)
    brand, _ = Brand.objects.get_or_create(name=name, defaults={'slug': slug})
    return brand


def get_or_create_material(name):
    material, _ = Material.objects.get_or_create(name=name)
    return material


def get_or_create_size(value, unit='other'):
    size, _ = Size.objects.get_or_create(value=value, unit=unit)
    return size


def create_product(product_def):
    product, created = Product.objects.get_or_create(
        slug=product_def['slug'],
        defaults={
            'name': product_def['name'],
            'description': product_def['description'],
            'price': product_def['price'],
            'original_price': product_def.get('original_price') or product_def['price'],
            'style': product_def['style'],
            'brand': product_def['brand'],
            'material': product_def['material'],
            'is_active': product_def.get('is_active', True),
        }
    )

    if created:
        print(f"Created Product: {product.name}")
    else:
        print(f"Product already exists, updating: {product.name}")
        product.name = product_def['name']
        product.description = product_def['description']
        product.price = product_def['price']
        product.original_price = product_def.get('original_price', product_def['price'])
        product.style = product_def['style']
        product.brand = product_def['brand']
        product.material = product_def['material']
        product.is_active = product_def.get('is_active', True)

    # set main image
    main_image_path = product_def['main_image']
    with open_image_file(main_image_path) as imgfile:
        product.image = f"products/{os.path.basename(main_image_path)}"
    product.save()

    # colors and sizes
    product.colors.set(product_def['colors'])
    product.sizes.set(product_def['sizes'])

    # color-size stocks
    for color in product_def['colors']:
        for size in product_def['sizes']:
            css, _ = ColorSizeStock.objects.get_or_create(product=product, color=color, size=size)
            css.stock = product_def.get('stock_per_combo', 50)
            css.save()

    # product images
    for image_def in product_def['images']:
        color = image_def['color']
        view_type = image_def.get('view_type', 'front')
        is_default = image_def.get('is_default', False)
        image_path = image_def['file']

        # copy and save image record
        with open_image_file(image_path) as imgfile:
            img_obj, img_created = ProductImage.objects.get_or_create(
                product=product,
                color=color,
                view_type=view_type,
                defaults={'is_default': is_default}
            )
            img_obj.is_default = is_default
            if not img_obj.image:
                img_obj.image = f"products/{os.path.basename(image_path)}"
            img_obj.save()

    return product


# Core seed data

def seed():
    # common entities
    # All products are bags according to your request
    style_bag = get_or_create_style('Bags')

    brand_nike = get_or_create_brand('Nike')
    brand_generic = get_or_create_brand('Generic')

    material_leather = get_or_create_material('Leather')
    material_canvas = get_or_create_material('Canvas')
    material_synthetic = get_or_create_material('Synthetic')

    size_5L = get_or_create_size(5, 'L')
    size_10L = get_or_create_size(10, 'L')
    size_15L = get_or_create_size(15, 'L')

    color_black = get_or_create_color('Black', '#000000')
    color_blue = get_or_create_color('Blue', '#0000FF')
    color_red = get_or_create_color('Red', '#FF0000')
    color_brown = get_or_create_color('Brown', '#8B4513')
    color_green = get_or_create_color('Green', '#008000')

    products = [
        {
            'name': 'Formal Leather Bag',
            'slug': 'formal-leather-bag',
            'description': 'Premium formal bag available in black, blue, and brown.',
            'price': 139.99,
            'original_price': 199.99,
            'style': style_bag,
            'brand': brand_generic,
            'material': material_leather,
            'main_image': 'formal_black.webp',
            'colors': [color_black, color_blue, color_brown],
            'sizes': [size_5L, size_10L, size_15L],
            'stock_per_combo': 100,
            'images': [
                {'color': color_black, 'view_type': 'front', 'file': 'formal_black.webp', 'is_default': True},
                {'color': color_blue, 'view_type': 'front', 'file': 'formal_blue.webp'},
                {'color': color_brown, 'view_type': 'front', 'file': 'formal_brown.webp'},
            ]
        },
        {
            'name': 'Heritage Travel Bag',
            'slug': 'heritage-travel-bag',
            'description': 'Heritage travel bag with classic black and red versions.',
            'price': 129.99,
            'original_price': 289.99,
            'style': style_bag,
            'brand': brand_nike,
            'material': material_synthetic,
            'main_image': 'NIKE_HERITAGE_BLACK_FRONT.avif',
            'colors': [color_black, color_red],
            'sizes': [size_5L, size_10L, size_15L],
            'stock_per_combo': 80,
            'images': [
                {'color': color_black, 'view_type': 'front', 'file': 'NIKE_HERITAGE_BLACK_FRONT.avif', 'is_default': True},
                {'color': color_black, 'view_type': 'back', 'file': 'NIKE_HERITAGE_BLACK_BACK.avif'},
                {'color': color_black, 'view_type': 'side', 'file': 'NIKE_HERITAGE_BLACK_SIDE.avif'},
                {'color': color_red, 'view_type': 'front', 'file': 'NIKE_HERITAGE_RED_FRONT.avif', 'is_default': True},
                {'color': color_red, 'view_type': 'back', 'file': 'NIKE_HERITAGE_RED_BACK.avif'},
                {'color': color_red, 'view_type': 'side', 'file': 'NIKE_HERITAGE_RED_SIDE.avif'},
            ]
        },
        {
            'name': 'Varsity Elite Bag',
            'slug': 'varsity-elite-bag',
            'description': 'Varsity Elite bag in blue and red options.',
            'price': 139.99,
            'original_price': 229.99,
            'style': style_bag,
            'brand': brand_nike,
            'material': material_synthetic,
            'main_image': 'NIKE_VARSITY_ELITE_BLUE_FRONT.avif',
            'colors': [color_blue, color_red],
            'sizes': [size_5L, size_10L, size_15L],
            'stock_per_combo': 90,
            'images': [
                {'color': color_blue, 'view_type': 'front', 'file': 'NIKE_VARSITY_ELITE_BLUE_FRONT.avif', 'is_default': True},
                {'color': color_blue, 'view_type': 'back', 'file': 'NIKE_VARSITY_ELITE_BLUE_BACK.avif'},
                {'color': color_blue, 'view_type': 'side', 'file': 'NIKE_VARSITY_ELITE_BLUE_SIDE.avif'},
                {'color': color_red, 'view_type': 'front', 'file': 'NIKE_VARSITY_ELITE_RED_FRONT.avif', 'is_default': True},
                {'color': color_red, 'view_type': 'back', 'file': 'NIKE_VARSITY_ELITE_RED_BACK.avif'},
                {'color': color_red, 'view_type': 'side', 'file': 'NIKE_VARSITY_ELITE_RED_SIDE.avif'},
            ]
        },
        {
            'name': 'Naruto Bag',
            'slug': 'naruto-bag',
            'description': 'Anime-designed Naruto bag in sleek black.',
            'price': 39.99,
            'original_price': 59.99,
            'style': style_bag,
            'brand': brand_generic,
            'material': material_canvas,
            'main_image': 'naruto_bag_black.jpg',
            'colors': [color_black],
            'sizes': [size_5L, size_10L],
            'stock_per_combo': 60,
            'images': [{'color': color_black, 'view_type': 'front', 'file': 'naruto_bag_black.jpg', 'is_default': True}],
        },
        {
            'name': 'OnePiece Tote Bag',
            'slug': 'onepiece-tote-bag',
            'description': 'OnePiece-themed travel tote bag in sleek black.',
            'price': 34.99,
            'original_price': 49.99,
            'style': style_bag,
            'brand': brand_generic,
            'material': material_canvas,
            'main_image': 'onepiece_bag_black.jpg',
            'colors': [color_black],
            'sizes': [size_5L, size_10L],
            'stock_per_combo': 55,
            'images': [{'color': color_black, 'view_type': 'front', 'file': 'onepiece_bag_black.jpg', 'is_default': True}],
        },
        {
            'name': 'Sports Duffel Bag',
            'slug': 'sports-duffel-bag',
            'description': 'Sports duffel bag with black and red colors.',
            'price': 89.99,
            'original_price': 119.99,
            'style': style_bag,
            'brand': brand_generic,
            'material': material_synthetic,
            'main_image': 'sports_black.jpg',
            'colors': [color_black, color_red],
            'sizes': [size_5L, size_10L, size_15L],
            'stock_per_combo': 85,
            'images': [
                {'color': color_black, 'view_type': 'front', 'file': 'sports_black.jpg', 'is_default': True},
                {'color': color_red, 'view_type': 'front', 'file': 'sports_red.jpg', 'is_default': False},
            ]
        },
        {
            'name': 'Travel Gear Bag',
            'slug': 'travel-gear-bag',
            'description': 'Practical travel bag in green.',
            'price': 49.99,
            'original_price': 69.99,
            'style': style_bag,
            'brand': brand_generic,
            'material': material_canvas,
            'main_image': 'travel_green.jpg',
            'colors': [color_green],
            'sizes': [size_5L, size_10L],
            'stock_per_combo': 45,
            'images': [{'color': color_green, 'view_type': 'front', 'file': 'travel_green.jpg', 'is_default': True}],
        },
    ]

    for pd in products:
        create_product(pd)

    print('Seeding complete.')


if __name__ == '__main__':
    seed()
