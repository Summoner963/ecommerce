# store/urls.py

from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    
    path("register/", views.register, name="register"),
    path("verify_email/<str:email>/", views.verify_email, name="verify_email"),
    path("resend-verification/<str:email>/", views.resend_verification_email, name="resend_verification_email"),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    # Home and style-related views
    path('', views.home, name='home'),
    path('style/<slug:slug>/', views.style_detail, name='style_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product'),
    path('product/<int:product_id>/defaults/', views.get_product_defaults, name='product_defaults'),
    path('product/<int:product_id>/images/', views.get_color_images, name='get_color_images'),
    path('admin/orders-by-email/', views.orders_by_email, name='orders_by_email'),
    path('products/', views.product_list, name='product_list'),

    # Cart-related views
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/update/<int:product_id>/<str:action>/', views.update_cart, name='update_cart'),
    path('success/', views.success_view, name='success'),
    path('cancel/', views.cancel_view, name='cancel'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    
    # Wishlist-related views
    path('wishlist/', views.view_wishlist, name='view_wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),

    # Search and profile views
    path('search/', views.search_products, name='search'),
    path('order-history/', views.order_history, name='order_history'),
    path('profile/', views.user_profile, name='profile'),


    # Utility views
    path('cart/count/', views.cart_count, name='cart_count'),
    path('wishlist/count/', views.wishlist_count, name='wishlist_count'),

    # Review-related views
    path('product/<slug:product_slug>/add-review/', views.add_review, name='add_review'),
    path('product/<slug:product_slug>/delete-review/<int:review_id>/', views.delete_review, name='delete_review'),
    path('product/<slug:product_slug>/edit-review/<int:review_id>/', views.edit_review, name='edit_review'),

    # Payment gateways
    path('payment/esewa/initiate/', views.initiate_esewa_payment, name='initiate_esewa'),
    path('payment/esewa/callback/', views.esewa_callback, name='esewa_callback'),
    path('payment/esewa/failed/', views.esewa_failed, name='esewa_failed'),
    path('payment/khalti/initiate/', views.initiate_khalti_payment, name='initiate_khalti'),
    path('payment/khalti/callback/', views.khalti_callback, name='khalti_callback'),
    path('payment/khalti/failed/', views.khalti_failed, name='khalti_failed'),

    # Static pages
    path('about-us/', views.about, name='about'),
    path('contact-us/', views.contact, name='contact'),
]
