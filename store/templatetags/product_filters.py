from django import template

register = template.Library()

@register.filter
def average_rating(reviews):
    if reviews.exists():
        return sum(review.rating for review in reviews) / reviews.count()
    return 0
