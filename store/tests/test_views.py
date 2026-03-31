# store/tests/test_views.py

from django.test import TestCase, Client
from store.models import style, Product, Order

class HomeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.style = style.objects.create(name="Electronics", slug="electronics")
        self.product = Product.objects.create(
            name="Laptop",
            style=self.style,
            price=1000.00,
            description="High-end laptop",
            stock=10,
            slug="laptop"
        )

    def test_home_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop")
        self.assertContains(response, "Electronics")

    def test_style_filter(self):
        response = self.client.get('/?style=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop")

# store/tests/test_views.py

from django.contrib.auth.models import User

class CartViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.product = Product.objects.create(name="Phone", price=500.00, slug="phone", stock=5)
        self.client.login(username="testuser", password="password")

    def test_add_to_cart(self):
        response = self.client.post(f'/cart/update/{self.product.id}/add/')
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user, completed=False)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 1)

