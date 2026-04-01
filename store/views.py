# store/views.py

import base64
import hashlib
import hmac
from itertools import product
import json
import logging
import random
from datetime import datetime, timedelta

import django
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError
from django.db.models import Q, Avg, Min, Max
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import stripe
from django.templatetags.static import static

def get_image_url(image_field):
    """Get the correct URL for an image - static or media"""
    if image_field and str(image_field).startswith('images/products/'):
        # This is a static file reference
        return static(str(image_field))
    else:
        # This is a media file
        return image_field.url if image_field else ''
from .models import (
    ColorSizeStock, Product, ProductImage, Color, Offer, Style, Brand, Size, Material,
    VerificationCode, Wishlist, Order, OrderItem, Review, ContactMessage
)
from .forms import ReviewForm
from .recommendation import get_recommendations

logger = logging.getLogger(__name__)
User = get_user_model()

def send_verification_code(email):
    code = random.randint(100000, 999999)
    expiry = now() + timedelta(hours=1)

    # Create or update verification code for the user
    user = User.objects.get(email=email)
    VerificationCode.objects.update_or_create(user=user, defaults={"code": code, "expiry": expiry})

    # Send verification email
    send_mail(
        "Verification Code",
        f"Your verification code is {code}. It expires in 1 hour.",
        "noreply@yourecommerce.com",
        [email],
        fail_silently=False,
    )

def register(request):
    if request.method == "POST":
        email = request.POST["email"]
        name = request.POST.get("name", "")  # Optional
        phone = request.POST.get("phone", "")  # Optional
        address = request.POST.get("address", "")  # Optional
        password = request.POST["password"]

        # Check if the email already exists
        if User.objects.filter(email=email).exists():
            return render(request, "account/register.html", {"error": "Email already registered."})

        try:
            # Create a new user with required fields
            user = User.objects.create_user(
                email=email,
                name=name,
                phone=phone,
                address=address,
                password=password,
            )

            # Send a verification code
            send_verification_code(email)

            return redirect("store:verify_email", email=email)
        except IntegrityError as e:
            return render(request, "account/register.html", {"error": "An error occurred while creating the account."})
        except TypeError as e:
            return render(request, "account/register.html", {"error": "Invalid data. Please try again."})

    return render(request, "account/register.html")

def verify_email(request, email):
    if request.method == "POST":
        code = request.POST["code"]
        try:
            user = User.objects.get(email=email)
            verification = VerificationCode.objects.filter(
                user=user, 
                code=code, 
                expiry__gt=now()
            ).first()

            if verification:
                user.is_active = True
                user.is_verified = True
                user.save()
                
                # Explicitly specify the backend
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                verification.delete()
                messages.success(request, "Email verified successfully!")
                return redirect("store:home")
            else:
                messages.error(request, "Invalid or expired verification code.")
                return render(request, "account/verify_email.html", {"email": email})
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("register")

    return render(request, "account/verify_email.html", {"email": email})

def resend_verification_email(request, email):
    try:
        send_verification_code(email)  # Use your existing `send_verification_code` function
        messages.success(request, "A new verification code has been sent to your email.")
    except User.DoesNotExist:
        messages.error(request, "No user found with the provided email.")
    return redirect("store:verify_email", email=email)


# ─────────────────────────────────────────────────────────
# REPLACE your existing home() function in views.py with this
# ─────────────────────────────────────────────────────────

"""
THE ROOT BUG EXPLAINED:
  color_stocks = queryset.order_by('-stock')
  for cs in color_stocks:       # Django starts fetching rows
      if cs.stock > 0:
          best_color = cs.color
          break                 # ← stops iteration early!
  # Now color_stocks internal cache = only rows fetched before break
  # e.g. if black (stock=50) is first, cache = [black only]
  # Then: sum(cs.stock for cs in color_stocks) = 50 (only black counted!)
  # Other colors like red(stock=30), blue(stock=20) are MISSING from sum
  # But the check: total_color_stock == 0  →  50 != 0  →  in stock  ✓
  # 
  # HOWEVER if NO ColorStock rows exist yet (product.stock=0 on old field)
  # color_stocks.exists() = False → falls back to product.stock == 0 → True → OUT OF STOCK
  #
  # FIX: list(color_stocks) at the start converts to Python list immediately,
  # no partial cache issue, and all subsequent operations work on full data.
"""

def home(request):
    styles           = Style.objects.all()
    brands           = Brand.objects.all()
    materials        = Material.objects.all()
    sizes            = Size.objects.all()
    available_colors = Color.objects.filter(products__isnull=False).distinct()

    products = Product.objects.filter(is_active=True).annotate(
        avg_rating=Avg('reviews__rating')
    )
    offers = Offer.objects.filter(valid_until__gte=django.utils.timezone.now())
    price_range = Product.objects.filter(is_active=True).aggregate(
        min=Min('price'), max=Max('price')
    )

    selected_styles    = request.GET.getlist('styles')
    selected_brands    = request.GET.getlist('brands')
    selected_colors    = request.GET.getlist('colors')
    selected_materials = request.GET.getlist('materials')
    selected_sizes     = request.GET.getlist('sizes')

    if selected_styles:    products = products.filter(style_id__in=selected_styles)
    if selected_brands:    products = products.filter(brand_id__in=selected_brands)
    if selected_colors:    products = products.filter(colors__id__in=selected_colors)
    if selected_materials: products = products.filter(material_id__in=selected_materials)
    if selected_sizes:     products = products.filter(sizes__id__in=selected_sizes)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price: products = products.filter(price__gte=min_price)
    if max_price: products = products.filter(price__lte=max_price)

    min_rating = request.GET.get('min_rating')
    if min_rating: products = products.filter(avg_rating__gte=min_rating)

    products = products.distinct()

    if request.user.is_authenticated:
        wishlist = Wishlist.objects.filter(user=request.user).first()
        wishlist_product_ids = list(wishlist.products.values_list('id', flat=True)) if wishlist else []
    else:
        wishlist_product_ids = request.session.get('wishlist', [])

    enriched_products = []
    for product in products:
        css_rows = list(
            ColorSizeStock.objects
            .filter(product=product)
            .select_related('color', 'size')
        )

        # Per-color total stock
        color_stock_lookup = {}
        for r in css_rows:
            color_stock_lookup[r.color_id] = color_stock_lookup.get(r.color_id, 0) + r.stock

        # Per-color best (size_id, stock) — highest stock combo for each color
        color_best_size = {}
        for r in css_rows:
            existing = color_best_size.get(r.color_id)
            if existing is None or r.stock > existing['stock']:
                color_best_size[r.color_id] = {'size_id': r.size_id, 'stock': r.stock}

        total_stock     = sum(r.stock for r in css_rows)
        is_out_of_stock = (total_stock == 0)

        # Best combo overall: highest stock across all color+size combos
        best_combo = max(css_rows, key=lambda r: r.stock) if css_rows else None

        all_product_colors = list(product.colors.all())

        if best_combo and best_combo.stock > 0:
            best_color       = best_combo.color
            best_size        = best_combo.size
            best_combo_stock = best_combo.stock
        else:
            # All OOS — show first color/size but mark OOS
            best_color = all_product_colors[0] if all_product_colors else None
            best_size  = None
            if best_color:
                for r in css_rows:
                    if r.color_id == best_color.id:
                        best_size = r.size
                        break
            best_combo_stock = 0
        
        if best_size is None and list(product.sizes.all()):
            best_size = list(product.sizes.all())[0]
        
        # Display image for best color
        display_image_url = get_image_url(product.image)
        if best_color:
            best_img = (
                ProductImage.objects
                .filter(product=product, color=best_color, view_type='front')
                .first()
                or ProductImage.objects
                .filter(product=product, color=best_color)
                .first()
            )
            if best_img:
                display_image_url = get_image_url(best_img.image)

        # Color dot data — each dot carries its own best size+stock for JS
        all_colors_data = []
        for color in all_product_colors:
            total_for_color = color_stock_lookup.get(color.id, 0)
            best_for_color  = color_best_size.get(color.id, {})
            color_img = (
                ProductImage.objects
                .filter(product=product, color=color, view_type='front')
                .first()
                or ProductImage.objects
                .filter(product=product, color=color)
                .first()
            )
            all_colors_data.append({
                'color_id':         color.id,
                'color_name':       color.name,
                'hex_code':         color.hex_code or '#cccccc',
                'img_url':          get_image_url(color_img.image) if color_img else get_image_url(product.image),
                'in_stock':         total_for_color > 0,
                'best_size_id':     best_for_color.get('size_id', ''),
                'best_combo_stock': best_for_color.get('stock', 0),
            })

        enriched_products.append({
            'product':            product,
            'display_color':      best_color,
            'display_size':       best_size,
            'display_combo_stock': best_combo_stock,
            'display_image':      display_image_url,
            'is_out_of_stock':    is_out_of_stock,
            'display_stock':      total_stock,
            'all_colors':         all_colors_data[:5],
            'color_count':        len(all_colors_data),
        })

    availability = request.GET.get('availability', '')
    if availability == 'in_stock':
        enriched_products = [p for p in enriched_products if not p['is_out_of_stock']]
    elif availability == 'out_of_stock':
        enriched_products = [p for p in enriched_products if p['is_out_of_stock']]

    return render(request, 'store/home.html', {
        'styles':               styles,
        'brands':               brands,
        'materials':            materials,
        'sizes':                sizes,
        'available_colors':     available_colors,
        'products':             products,
        'offers':               offers,
        'price_range':          price_range,
        'selected_styles':      selected_styles,
        'selected_brands':      selected_brands,
        'selected_colors':      selected_colors,
        'selected_materials':   selected_materials,
        'selected_sizes':       selected_sizes,
        'wishlist_product_ids': wishlist_product_ids,
        'enriched_products':    enriched_products,
    })
    
def style_detail(request, slug):
    style    = get_object_or_404(Style, slug=slug)
    products = Product.objects.filter(style=style, is_active=True).annotate(
        avg_rating=Avg('reviews__rating')
    )
    return render(request, 'store/product_detail.html', {
        'data1':    style,
        'data2': products,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    reviews = product.reviews.select_related('user').all()
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    colors = list(product.colors.all())
    sizes  = list(product.sizes.all())

    # Full stock map: {(color_id, size_id): stock}
    css_rows = list(
        ColorSizeStock.objects
        .filter(product=product)
        .select_related('color', 'size')
    )
    stock_map = {(r.color_id, r.size_id): r.stock for r in css_rows}

    # Per-color total stock (across all sizes)
    color_total_stock = {}
    for r in css_rows:
        color_total_stock[r.color_id] = color_total_stock.get(r.color_id, 0) + r.stock

    # Per-size total stock (across all colors)
    size_total_stock = {}
    for r in css_rows:
        size_total_stock[r.size_id] = size_total_stock.get(r.size_id, 0) + r.stock

    colors_with_stock = [
        {'color': c, 'stock': color_total_stock.get(c.id, 0), 'in_stock': color_total_stock.get(c.id, 0) > 0}
        for c in colors
    ]
    sizes_with_stock = [
        {'size': s, 'stock': size_total_stock.get(s.id, 0), 'in_stock': size_total_stock.get(s.id, 0) > 0}
        for s in sizes
    ]

    # Default color: first in-stock
    default_color = next(
        (e['color'] for e in colors_with_stock if e['in_stock']),
        colors[0] if colors else None
    )

    # Default size: first size that's in-stock for the default color
    default_size = None
    if default_color:
        for s in sizes:
            if stock_map.get((default_color.id, s.id), 0) > 0:
                default_size = s
                break
    if default_size is None and sizes:
        default_size = sizes[0]

    images_by_color_raw = {
        c.name: list(c.images.filter(product=product)) for c in colors
    }
    images_by_color = {
        color_name: [
            {'url': get_image_url(img.image), 'alt': product.name}
            for img in imgs
        ]
        for color_name, imgs in images_by_color_raw.items()
    }
    default_color_images = images_by_color.get(default_color.name, []) if default_color else []

    # stock_map_json for JS: {"color_id": {"size_id": stock, ...}, ...}
    stock_map_json = {}
    for (color_id, size_id), stock in stock_map.items():
        stock_map_json.setdefault(str(color_id), {})[str(size_id)] = stock

    # Initial stock for the default color+size combo
    initial_combo_stock = 0
    if default_color and default_size:
        initial_combo_stock = stock_map.get((default_color.id, default_size.id), 0)

    raw_recommendations = get_recommendations(product, n=4)
    recommendations = [
        {
            'product': rec,
            'image_url': get_image_url(rec.image),
        }
        for rec in raw_recommendations
    ]    
    discount_percentage = (
        round((product.original_price - product.price) / product.original_price * 100, 2)
        if product.original_price and product.price else None
    )

    can_review = False
    already_reviewed = False
    if request.user.is_authenticated:
        already_reviewed = Review.objects.filter(user=request.user, product=product).exists()
        can_review = (
            not already_reviewed and
            OrderItem.objects.filter(
                order__user=request.user, order__status='D', product=product
            ).exists()
        )

    user_wishlist_products = []
    if request.user.is_authenticated:
        wl = Wishlist.objects.filter(user=request.user).first()
        if wl:
            user_wishlist_products = list(wl.products.all())

    return render(request, 'store/product_detail.html', {
        'product':              product,
        'reviews':              reviews,
        'avg_rating':           avg_rating,
        'avg_rating_range':     range(1, 6),
        'colors':               colors,
        'colors_with_stock':    colors_with_stock,
        'sizes_with_stock':     sizes_with_stock,
        'stock_map_json':       stock_map_json,
        'initial_combo_stock':  initial_combo_stock,
        'default_color':        default_color,
        'default_size':         default_size,
        'default_color_images': default_color_images,
        'images_by_color':      images_by_color,
        'product_image_url': get_image_url(product.image),
        'recommendations':      recommendations,
        'discount_percentage':  discount_percentage,
        'can_review':           can_review,
        'already_reviewed':     already_reviewed,
        'user_wishlist_products': user_wishlist_products,
        'selected_color_slug':  request.GET.get('color', ''),
        'selected_size_id':     request.GET.get('size', ''),
    })
    
def get_color_images(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    color_id = request.GET.get('color', None)
    if color_id:
        try:
            color = get_object_or_404(Color, id=color_id)
            product_images = product.images.filter(color=color)
        except Exception:
            return JsonResponse({'error': 'No images found for this color'}, status=404)
    else:
        product_images = product.images.all()

    image_data = [
        {'url': get_image_url(img.image)}  # ← fixed line
        for img in product_images
    ]
    return JsonResponse({'images': image_data})

def product_list(request):
    products         = Product.objects.filter(is_active=True).annotate(avg_rating=Avg('reviews__rating'))
    styles           = Style.objects.all()
    brands           = Brand.objects.all()
    materials        = Material.objects.all()
    sizes            = Size.objects.all()
    available_colors = Color.objects.filter(products__isnull=False).distinct()

    price_range = Product.objects.filter(is_active=True).aggregate(
        min=Min('price'),
        max=Max('price')
    )

    filters = {}

    if 'styles' in request.GET:
        filters['style_id__in'] = request.GET.getlist('styles')

    if 'brands' in request.GET:
        filters['brand_id__in'] = request.GET.getlist('brands')

    if 'sizes' in request.GET:
        filters['sizes__id__in'] = request.GET.getlist('sizes')

    if 'materials' in request.GET:
        filters['material_id__in'] = request.GET.getlist('materials')

    if request.GET.get('min_price'):
        filters['price__gte'] = request.GET.get('min_price')
    if request.GET.get('max_price'):
        filters['price__lte'] = request.GET.get('max_price')

    if 'colors' in request.GET:
        filters['colors__id__in'] = request.GET.getlist('colors')

    if request.GET.get('min_rating'):
        filters['avg_rating__gte'] = request.GET.get('min_rating')

    if request.GET.get('availability') == 'in_stock':
        filters['stock__gt'] = 0
    elif request.GET.get('availability') == 'out_of_stock':
        filters['stock'] = 0

    if filters:
        products = products.filter(**filters).distinct()

    paginator = Paginator(products, 12)
    page = request.GET.get('page', 1)
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    return render(request, 'store/product_list.html', {
        'products':        products,
        'styles':          styles,
        'brands':          brands,
        'materials':       materials,
        'sizes':           sizes,
        'available_colors':available_colors,
        'price_range':     price_range,
    })

def get_product_defaults(request, product_id):
    """
    Returns the best (color_id, size_id) combo for a product — 
    the combo with the most stock. Used by home/wishlist quick-add buttons.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)
    css_rows = list(
        ColorSizeStock.objects
        .filter(product=product)
        .select_related('color', 'size')
        .order_by('-stock')
    )
    if not css_rows:
        return JsonResponse({'color_id': None, 'size_id': None, 'stock': 0})
    
    best = css_rows[0]  # highest stock row
    return JsonResponse({
        'color_id': best.color_id,
        'size_id':  best.size_id,
        'stock':    best.stock,
        'color_name': best.color.name,
        'size_label': f"{best.size.value} {best.size.unit}",
    })
    
@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            return JsonResponse({'success': False, 'error': 'Quantity must be at least 1'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid quantity'}, status=400)

    color_id = request.POST.get('color')
    size_id  = request.POST.get('size')

    color = None
    size  = None

    if color_id:
        try:
            color = Color.objects.get(id=color_id)
            if not product.colors.filter(id=color.id).exists():
                return JsonResponse({'success': False, 'error': 'Invalid color for this product'}, status=400)
        except Color.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Color not found'}, status=404)

    if size_id:
        try:
            size = Size.objects.get(id=size_id)
            if not product.sizes.filter(id=size.id).exists():
                return JsonResponse({'success': False, 'error': 'Invalid size for this product'}, status=400)
        except Size.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Size not found'}, status=404)

    # Stock check: must have BOTH color and size to check a specific combo
    if color and size:
        css = ColorSizeStock.objects.filter(product=product, color=color, size=size).first()
        available_stock = css.stock if css else 0
        if available_stock == 0:
            return JsonResponse({
                'success': False,
                'error': f'Out of stock for {color.name} / {size}'
            }, status=400)
    elif color:
        available_stock = sum(
            r.stock for r in ColorSizeStock.objects.filter(product=product, color=color)
        )
        if available_stock == 0:
            return JsonResponse({'success': False, 'error': f'Out of stock for {color.name}'}, status=400)
    else:
        available_stock = sum(
            r.stock for r in ColorSizeStock.objects.filter(product=product)
        )
        if available_stock == 0:
            return JsonResponse({'success': False, 'error': 'Product is out of stock'}, status=400)

    if quantity > available_stock:
        return JsonResponse({
            'success': False,
            'error': f'Only {available_stock} available for this combination'
        }, status=400)

    order, _ = Order.objects.get_or_create(user=request.user, completed=False)

    # Each unique (product, color, size) = separate cart line item
    order_item, item_created = OrderItem.objects.get_or_create(
        order=order,
        product=product,
        color=color,
        size=size,
        defaults={'quantity': quantity}
    )

    if not item_created:
        new_qty = order_item.quantity + quantity
        if new_qty > available_stock:
            return JsonResponse({
                'success': False,
                'error': f'Only {available_stock - order_item.quantity} more available for this combination'
            }, status=400)
        order_item.quantity = new_qty
        order_item.save()

    cart_count = order.items.count()
    return JsonResponse({
        'success': True,
        'cart_count': cart_count,
        'message': 'Added to cart!'
    })


@login_required
def view_cart(request):
    try:
        order = Order.objects.get(user=request.user, completed=False)
        order_items = []
        for item in order.items.select_related('product', 'color', 'size').all():
            image_url = get_image_url(item.product.image)
            if item.color:
                color_image = (
                    item.product.images.filter(color=item.color, view_type='front').first()
                    or item.product.images.filter(color=item.color).first()
                )
                if color_image:
                    image_url = get_image_url(color_image.image)

            # Build query string for update_cart URLs so each combo is targeted correctly
            combo_params = []
            if item.color: combo_params.append(f'color={item.color.id}')
            if item.size:  combo_params.append(f'size={item.size.id}')
            combo_qs = '?' + '&'.join(combo_params) if combo_params else ''

            order_items.append({
                'item':       item,
                'image_url':  image_url,
                'size_label': f"{item.size.value} {item.size.unit}" if item.size else None,
                'combo_qs':   combo_qs,  # appended to update/remove URLs in template
            })

        return render(request, 'store/cart.html', {
            'order':       order,
            'order_items': order_items,
            'total_price': order.total_cost(),
        })

    except Order.DoesNotExist:
        return render(request, 'store/cart.html', {
            'order':       None,
            'order_items': [],
            'total_price': 0,
        })

@login_required
def update_cart(request, product_id, action):
    product = get_object_or_404(Product, id=product_id)

    # Color+size passed as query params so each combo's buttons target it specifically
    color_id = request.GET.get('color')
    size_id  = request.GET.get('size')

    try:
        order = Order.objects.get(user=request.user, completed=False)

        qs = order.items.filter(product=product)
        if color_id:
            qs = qs.filter(color_id=color_id)
        if size_id:
            qs = qs.filter(size_id=size_id)

        order_item = qs.first()
        if not order_item:
            messages.error(request, "Item not found in cart.")
            return redirect('store:view_cart')

        if action == 'increase':
            css = ColorSizeStock.objects.filter(
                product=product,
                color=order_item.color,
                size=order_item.size
            ).first()
            available = css.stock if css else 0
            if order_item.quantity + 1 > available:
                messages.error(request, f"Only {available} available for this combination.")
                return redirect('store:view_cart')
            order_item.quantity += 1
            order_item.save()

        elif action == 'decrease':
            order_item.quantity -= 1
            if order_item.quantity <= 0:
                return redirect('store:view_cart')
            order_item.save()

        elif action == 'remove':
            order_item.delete()
            messages.success(request, f"{product.name} removed from cart.")
            return redirect('store:view_cart')

        messages.success(request, "Cart updated.")
        return redirect('store:view_cart')

    except Order.DoesNotExist:
        messages.error(request, "No active order found.")
        return redirect('store:view_cart')

def _deduct_stock_for_order(order):
    """
    Deduct ColorSizeStock for every item in a completed order.
    Called after payment is confirmed — Stripe, eSewa, and Khalti all use this.
    Uses F() expression to avoid race conditions and clamps at 0.
    """
    from django.db.models import F
    for item in order.items.select_related('product', 'color', 'size').all():
        if item.color and item.size:
            # Exact combo stock — the normal path
            updated = ColorSizeStock.objects.filter(
                product=item.product,
                color=item.color,
                size=item.size,
                stock__gte=item.quantity   # only deduct if enough stock exists
            ).update(stock=F('stock') - item.quantity)

            if not updated:
                # Stock went negative or combo missing — clamp to 0
                ColorSizeStock.objects.filter(
                    product=item.product,
                    color=item.color,
                    size=item.size,
                ).update(stock=0)

        elif item.color:
            # Color but no size (legacy item) — deduct from highest-stock row for that color
            css = ColorSizeStock.objects.filter(
                product=item.product,
                color=item.color,
            ).order_by('-stock').first()
            if css:
                css.stock = max(0, css.stock - item.quantity)
                css.save()

        elif item.size:
            # Size but no color — deduct from highest-stock row for that size
            css = ColorSizeStock.objects.filter(
                product=item.product,
                size=item.size,
            ).order_by('-stock').first()
            if css:
                css.stock = max(0, css.stock - item.quantity)
                css.save()

@login_required
def payment_success(request):
    try:
        # Get the active order
        order = Order.objects.get(user=request.user, completed=False)
        _deduct_stock_for_order(order)
        # Mark the order as completed
        order.completed = True
        order.save()

        # Optionally, clear the cart items (if you want a clean cart for the next order)
        order.items.all().delete()

        # Redirect to a payment success page
        return render(request, 'store/payment_success.html', {
            'order': order
        })
    except Order.DoesNotExist:
        # If no active order is found, redirect to the cart page or handle gracefully
        return redirect('store:order_history')

def success_view(request):
    return render(request, 'store/success.html')

def cancel_view(request):
    return render(request, 'store/cancel.html')

def view_wishlist(request):
    """Displays the wishlist for logged-in or non-logged-in users."""
    context = {}
    
    if request.user.is_authenticated:
        # Ensure `request.user` is a valid `User` instance
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        context['wishlist_products'] = wishlist.products.all()
    else:
        # Fetch wishlist data from session
        wishlist_product_ids = request.session.get('wishlist', [])
        context['wishlist_products'] = Product.objects.filter(id__in=wishlist_product_ids)

    # Add additional context for rendering
    context['wishlist_count'] = len(context['wishlist_products'])
    
    return render(request, 'store/wishlist.html', context)

# ─────────────────────────────────────────────────────────
# REPLACE your existing add_to_wishlist() function in views.py with this
# ─────────────────────────────────────────────────────────
# Also add require_POST to the imports at the top if not already there:
#   from django.views.decorators.http import require_POST

@require_POST
def add_to_wishlist(request, product_id):
    """Toggle product in wishlist. Always returns JSON (no redirect)."""
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)

        if wishlist.products.filter(id=product_id).exists():
            wishlist.products.remove(product)
            status = 'removed'
            message = f'{product.name} removed from wishlist'
        else:
            wishlist.products.add(product)
            status = 'added'
            message = f'{product.name} added to wishlist'

        wishlist_count = wishlist.products.count()

    else:
        # Session-based wishlist for guests
        wishlist_ids = request.session.get('wishlist', [])

        if product_id in wishlist_ids:
            wishlist_ids.remove(product_id)
            status = 'removed'
            message = f'{product.name} removed from wishlist'
        else:
            wishlist_ids.append(product_id)
            status = 'added'
            message = f'{product.name} added to wishlist'

        request.session['wishlist'] = wishlist_ids
        wishlist_count = len(wishlist_ids)

    return JsonResponse({
        'status': status,
        'message': message,
        'wishlist_count': wishlist_count,
    })
def remove_from_wishlist(request, product_id):
    """Removes a product from the wishlist for logged-in or non-logged-in users."""
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        wishlist = Wishlist.objects.filter(user=request.user).first()
        if wishlist:
            wishlist.products.remove(product)
    else:
        # Handle wishlist in session for non-logged-in users
        wishlist_product_ids = request.session.get('wishlist', [])
        if product_id in wishlist_product_ids:
            wishlist_product_ids.remove(product_id)
            request.session['wishlist'] = wishlist_product_ids

    # For AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success', 
            'message': 'Product removed from wishlist'
        })

    return redirect('store:view_wishlist')

def search_products(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return redirect('store:home')

    # ── Broad multi-field search ──────────────────────────────────────────────
    # Splits query into individual words and matches ANY of them across many
    # fields: name, description, style, brand, material, color names, tags, etc.
    words = query.split()

    # Start with all active products
    products = Product.objects.filter(is_active=True).annotate(
        avg_rating=Avg('reviews__rating')
    )
#words=["red","nike","shoes"]
    # Build one big OR filter across all meaningful fields for each word
    combined = Q()
    for word in words:
        combined |= (
            Q(name__icontains=word)                   # product name
            | Q(description__icontains=word)          # product description
            | Q(style__name__icontains=word)          # style e.g. "casual", "fancy"
            | Q(brand__name__icontains=word)          # brand e.g. "Nike", "Adidas"
            | Q(material__name__icontains=word)       # material e.g. "polyester", "nylon"
            | Q(colors__name__icontains=word)         # color names e.g. "red", "blue"
            | Q(sizes__value__icontains=word)         # size values
            | Q(colors__hex_code__icontains=word)     # hex codes (edge case)
        )

    products = products.filter(combined).distinct()

    # ── Wishlist IDs (same logic as home view) ────────────────────────────────
    if request.user.is_authenticated:
        wishlist = Wishlist.objects.filter(user=request.user).first()
        wishlist_product_ids = list(wishlist.products.values_list('id', flat=True)) if wishlist else []
    else:
        wishlist_product_ids = request.session.get('wishlist', [])

    # ── Enrich products exactly like home view ────────────────────────────────
    enriched_products = []
    for product in products:
        css_rows = list(
            ColorSizeStock.objects
            .filter(product=product)
            .select_related('color', 'size')
        )

        color_stock_lookup = {}
        for r in css_rows:
            color_stock_lookup[r.color_id] = color_stock_lookup.get(r.color_id, 0) + r.stock

        color_best_size = {}
        for r in css_rows:
            existing = color_best_size.get(r.color_id)
            if existing is None or r.stock > existing['stock']:
                color_best_size[r.color_id] = {'size_id': r.size_id, 'stock': r.stock}

        total_stock     = sum(r.stock for r in css_rows)
        is_out_of_stock = (total_stock == 0)

        best_combo = max(css_rows, key=lambda r: r.stock) if css_rows else None
        all_product_colors = list(product.colors.all())

        if best_combo and best_combo.stock > 0:
            best_color       = best_combo.color
            best_size        = best_combo.size
            best_combo_stock = best_combo.stock
        else:
            best_color = all_product_colors[0] if all_product_colors else None
            best_size  = None
            if best_color:
                for r in css_rows:
                    if r.color_id == best_color.id:
                        best_size = r.size
                        break
            best_combo_stock = 0

        if best_size is None and list(product.sizes.all()):
            best_size = list(product.sizes.all())[0]

        display_image_url = get_image_url(product.image)
        if best_color:
            best_img = (
                ProductImage.objects
                .filter(product=product, color=best_color, view_type='front')
                .first()
                or ProductImage.objects
                .filter(product=product, color=best_color)
                .first()
            )
            if best_img:
                display_image_url = get_image_url(best_img.image)

        all_colors_data = []
        for color in all_product_colors:
            total_for_color = color_stock_lookup.get(color.id, 0)
            best_for_color  = color_best_size.get(color.id, {})
            color_img = (
                ProductImage.objects
                .filter(product=product, color=color, view_type='front')
                .first()
                or ProductImage.objects
                .filter(product=product, color=color)
                .first()
            )
            all_colors_data.append({
                'color_id':         color.id,
                'color_name':       color.name,
                'hex_code':         color.hex_code or '#cccccc',
                'img_url':          get_image_url(color_img.image) if color_img else get_image_url(product.image),
                'in_stock':         total_for_color > 0,
                'best_size_id':     best_for_color.get('size_id', ''),
                'best_combo_stock': best_for_color.get('stock', 0),
            })

        enriched_products.append({
            'product':             product,
            'display_color':       best_color,
            'display_size':        best_size,
            'display_combo_stock': best_combo_stock,
            'display_image':       display_image_url,
            'is_out_of_stock':     is_out_of_stock,
            'display_stock':       total_stock,
            'all_colors':          all_colors_data[:5],
            'color_count':         len(all_colors_data),
        })

    return render(request, 'store/search_results.html', {
        'query':               query,
        'enriched_products':   enriched_products,
        'wishlist_product_ids': wishlist_product_ids,
    })

# store/views.py
def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Check if user exists and credentials are correct
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # Check if user is verified
            if not user.is_verified:
                messages.error(request, "Please verify your email before logging in.")
                return redirect('verify_email', email=email)
            
            login(request, user)
            messages.success(request, "Successfully logged in!")
            return redirect('store:home')
        else:
            messages.error(request, "Invalid email or password.")
    
    return render(request, 'account/login.html')


def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('store:home')


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user, completed=True).order_by('-created_at').prefetch_related('items__product', 'items__color', 'items__size')
    return render(request, 'store/order_history.html', {'orders': orders})

@login_required
def user_profile(request):
    if request.method == 'POST':
        phone   = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        request.user.phone   = phone
        request.user.address = address
        request.user.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('store:profile')

    orders = Order.objects.filter(user=request.user, completed=True).order_by('-created_at')
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    return render(request, 'store/profile.html', {
        'orders':          orders,
        'wishlist':        wishlist,
        'pending_count':   orders.filter(status='P').count(),
        'delivered_count': orders.filter(status='D').count(),
        'shipping_count':  orders.filter(status='S').count(),
        'canceled_count':  orders.filter(status='C').count(),
        'user':            request.user,
    })

@staff_member_required
def orders_by_email(request):
    query = request.GET.get('email')
    orders = None

    if query:
        orders = Order.objects.filter(user__email__icontains=query).order_by('-created_at')

    return render(request, 'admin/orders_by_email.html', {
        'orders': orders,
        'query': query,
    })

@login_required
def add_review(request, product_slug):
    product = get_object_or_404(Product, slug=product_slug)
    user = request.user
    already_reviewed = Review.objects.filter(user=user, product=product).exists()

    has_delivered = OrderItem.objects.filter(
        order__user=user,
        order__status='D',
        product=product
    ).exists()

    if already_reviewed:
        messages.error(request, "You have already reviewed this product.")
        return redirect('store:product', slug=product_slug)

    if not has_delivered:
        messages.error(request, "You can only review products that have been delivered to you.")
        return redirect('store:product', slug=product_slug)

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Invalid rating. Please select 1–5 stars.")
            return render(request, 'store/add_review.html', {'product': product})

        Review.objects.create(user=user, product=product, rating=rating, comment=comment)
        messages.success(request, "Your review has been added. Thank you!")
        return redirect('store:product', slug=product_slug)

    return render(request, 'store/add_review.html', {'product': product})


@login_required
def edit_review(request, product_slug, review_id):
    product = get_object_or_404(Product, slug=product_slug)           # FIX 1: was missing
    review  = get_object_or_404(Review, id=review_id, user=request.user, product=product)

    if request.method == 'POST':
        rating  = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()

        # FIX 2: validate and save rating (was completely missing)
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Invalid rating. Please select 1–5 stars.")
            return render(request, 'store/add_review.html', {'product': product, 'review': review})

        review.rating  = rating   # FIX 2: actually update the rating
        review.comment = comment
        review.save()
        messages.success(request, "Your review has been updated.")
        return redirect('store:product', slug=product_slug)

    # FIX 3: pass both product AND review so template has everything it needs
    return render(request, 'store/add_review.html', {'product': product, 'review': review})


@login_required
def delete_review(request, product_slug, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)

    if request.method == 'POST':
        review.delete()
        messages.success(request, "Your review has been deleted.")
        return redirect('store:product', slug=product_slug)

    return render(request, 'store/confirm_delete_review.html', {'review': review})

def cart_count(request):
    """Returns the count of items in the user's cart."""
    if request.user.is_authenticated:
        cart = Order.objects.filter(user=request.user, completed=False).first()
        count = sum(item.quantity for item in cart.items.all()) if cart else 0
    else:
        count = 0
    return JsonResponse({'count': count})

def wishlist_count(request):
    """Returns the count of products in the user's wishlist."""
    try:
        # Ensure request.user is resolved and authenticated
        user = request.user if request.user.is_authenticated else None
        if user:
            wishlist = Wishlist.objects.filter(user=user).first()
            count = wishlist.products.count() if wishlist else 0
        else:
            count = 0
    except Wishlist.DoesNotExist:
        count = 0

    return JsonResponse({'count': count})

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(request):
    if request.method == 'POST':
        try:
            order = Order.objects.get(user=request.user, completed=False)
            line_items = []
            for item in order.items.all():
                line_items.append({
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {'name': item.product.name},
                        'unit_amount': int(item.product.price * 100),
                    },
                    'quantity': item.quantity,
                })
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=request.build_absolute_uri(reverse('store:payment_success')),
                cancel_url=request.build_absolute_uri(reverse('store:cancel')),
            )
            order.payment_method = 'stripe'
            order.save()
            return JsonResponse({'id': session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# ─────────────── eSewa v2 (HMAC-SHA256) ───────────────

def _esewa_hmac(message):

    """Generate HMAC-SHA256 signature for eSewa v2 in Base64 format."""
    # 1. Get your secret key from settings
    secret = settings.ESEWA_SECRET_KEY.encode('utf-8')
    
    # 2. Generate the HMAC using raw bytes (.digest() instead of .hexdigest())
    hmac_sha256 = hmac.new(secret, message.encode('utf-8'), hashlib.sha256).digest()
    
    # 3. Convert those bytes into a Base64 string
    hash_in_base64 = base64.b64encode(hmac_sha256).decode('utf-8')
    
    return hash_in_base64

@login_required
def initiate_esewa_payment(request):
    """Redirect user to eSewa v2 sandbox payment page."""
    try:
        order = Order.objects.get(user=request.user, completed=False)
    except Order.DoesNotExist:
        messages.error(request, 'No active order found.')
        return redirect('store:view_cart')

    amount = str(int(order.total_cost()))  # paisa not needed for eSewa v2 (uses rupees)
    tax_amount = '0'
    product_service_charge = '0'
    product_delivery_charge = '0'
    total_amount = amount
    transaction_uuid = f"esewa-{order.id}-{int(datetime.now().timestamp())}"
    product_code = settings.ESEWA_MERCHANT_ID
    success_url = request.build_absolute_uri(reverse('store:esewa_callback'))
    failure_url = request.build_absolute_uri(reverse('store:esewa_failed'))

    # Build the HMAC signature string
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    signature = _esewa_hmac(message)

    context = {
        'esewa_url': f"{settings.ESEWA_BASE_URL}/api/epay/main/v2/form",
        'amount': amount,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
        'transaction_uuid': transaction_uuid,
        'product_code': product_code,
        'product_service_charge': product_service_charge,
        'product_delivery_charge': product_delivery_charge,
        'success_url': success_url,
        'failure_url': failure_url,
        'signed_field_names': 'total_amount,transaction_uuid,product_code',
        'signature': signature,
    }
    return render(request, 'store/esewa_payment.html', context)


@csrf_exempt
def esewa_callback(request):
    """Handle eSewa v2 payment success/failure callback."""
    encoded_data = request.GET.get('data', '')
    if not encoded_data:
        messages.error(request, 'eSewa payment verification failed: no data received.')
        return redirect('store:esewa_failed')

    try:
        decoded = base64.b64decode(encoded_data).decode('utf-8')
        data = json.loads(decoded)

        status = data.get('status', '')
        transaction_uuid = data.get('transaction_uuid', '')
        total_amount = data.get('total_amount', '')
        product_code = data.get('product_code', '')
        signature = data.get('signature', '')

        # Verify HMAC
        message = f"transaction_code={data.get('transaction_code','')},status={status},total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code},signed_field_names={data.get('signed_field_names','')}"
        expected_sig = _esewa_hmac(message)

        if signature != expected_sig or status != 'COMPLETE':
            messages.error(request, 'eSewa payment verification failed.')
            return redirect('store:esewa_failed')

        # Extract order id from transaction_uuid: "esewa-<order_id>-<ts>"
        parts = transaction_uuid.split('-')
        order_id = int(parts[1]) if len(parts) >= 2 else None
        if order_id:
            order = Order.objects.filter(id=order_id, user=request.user).first()
            if order and not order.completed:
                _deduct_stock_for_order(order) 
                order.completed = True
                order.payment_method = 'esewa'
                order.status = 'P'
                order.save()
        messages.success(request, 'eSewa payment successful! Your order has been placed.')
        return redirect('store:payment_success')

    except Exception as e:
        logger.error(f'eSewa callback error: {e}')
        messages.error(request, 'eSewa payment processing error.')
        return redirect('store:esewa_failed')


def esewa_failed(request):
    return render(request, 'store/esewa_failed.html')


# ─────────────── Khalti v2 (PIDX-based) ───────────────

@login_required
def initiate_khalti_payment(request):
    """Call Khalti v2 API to get payment URL (PIDX flow)."""
    try:
        order = Order.objects.get(user=request.user, completed=False)
    except Order.DoesNotExist:
        messages.error(request, 'No active order found.')
        return redirect('store:view_cart')

    amount_paisa = int(order.total_cost() * 100)  # Khalti uses paisa
    return_url = request.build_absolute_uri(reverse('store:khalti_callback'))
    website_url = request.build_absolute_uri('/')

    payload = {
        'return_url': return_url,
        'website_url': website_url,
        'amount': amount_paisa,
        'purchase_order_id': f'order-{order.id}',
        'purchase_order_name': f'Order #{order.id}',
        'customer_info': {
            'name': request.user.name,
            'email': request.user.email,
        },
    }
    headers = {
        'Authorization': f'Key {settings.KHALTI_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    resp = requests.post(
        f'{settings.KHALTI_BASE_URL}/epayment/initiate/',
        json=payload,
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        resp_data = resp.json()
        pidx = resp_data.get('pidx')
        payment_url = resp_data.get('payment_url')
        if pidx and payment_url:
            # Save pidx in session for callback verification
            request.session['khalti_pidx'] = pidx
            request.session['khalti_order_id'] = order.id
            return redirect(payment_url)
    messages.error(request, f'Khalti payment initiation failed: {resp.text}')
    return redirect('store:view_cart')


@login_required
def khalti_callback(request):
    """Verify Khalti payment via PIDX lookup."""
    pidx = request.GET.get('pidx') or request.session.get('khalti_pidx')
    order_id = request.session.get('khalti_order_id')

    if not pidx:
        messages.error(request, 'Khalti payment verification failed: missing PIDX.')
        return redirect('store:khalti_failed')

    headers = {
        'Authorization': f'Key {settings.KHALTI_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    resp = requests.post(
        f'{settings.KHALTI_BASE_URL}/epayment/lookup/',
        json={'pidx': pidx},
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'Completed':
            if order_id:
                order = Order.objects.filter(id=order_id, user=request.user).first()
                if order and not order.completed:
                    _deduct_stock_for_order(order)
                    order.completed = True
                    order.payment_method = 'khalti'
                    order.status = 'P'
                    order.save()
            # Clear session keys
            request.session.pop('khalti_pidx', None)
            request.session.pop('khalti_order_id', None)
            messages.success(request, 'Khalti payment successful! Your order has been placed.')
            return redirect('store:payment_success')

    messages.error(request, 'Khalti payment verification failed.')
    return redirect('store:khalti_failed')


def khalti_failed(request):
    return render(request, 'store/khalti_failed.html')


# ─────────────── About & Contact ───────────────

def about(request):    
    return render(request, 'store/about.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and subject and message:
            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message,
            )
            messages.success(request, "Thank you for your message! We'll get back to you soon.")
            return redirect('store:contact')
        else:
            messages.error(request, 'All fields are required.')

    return render(request, 'store/contact.html')