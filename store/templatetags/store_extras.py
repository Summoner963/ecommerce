# store/templatetags/store_extras.py

from django import template

register = template.Library()

@register.filter
def to_range(value, max_value):
    return range(value, max_value + 1)

@register.filter
def average_rating(reviews):
    if reviews:
        return sum([review.rating for review in reviews]) / len(reviews)
    return 0

@register.filter
def multiply(value, arg):
    return value * arg

@register.simple_tag
def get_item_image(item):
    """Return the best image URL for a cart/order item."""
    if item.color:
        img = (
            item.product.images.filter(color=item.color, view_type='front').first()
            or item.product.images.filter(color=item.color).first()
        )
        if img:
            return img.image.url
    return item.product.image.url