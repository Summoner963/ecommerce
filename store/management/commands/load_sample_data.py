# store/management/commands/load_sample_data.py

from django.core.management.base import BaseCommand
from store.models import style, Product

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        style.objects.all().delete()
        Product.objects.all().delete()

        electronics = style.objects.create(name="Electronics", slug="electronics")
        fashion = style.objects.create(name="Fashion", slug="fashion")

        Product.objects.create(
            name="Smartphone", style=electronics, price=699.99,
            description="Latest smartphone with advanced features.", stock=50, slug="smartphone"
        )
        Product.objects.create(
            name="Headphones", style=electronics, price=199.99,
            description="Noise-canceling headphones.", stock=30, slug="headphones"
        )
        Product.objects.create(
            name="Jacket", style=fashion, price=89.99,
            description="Stylish winter jacket.", stock=20, slug="jacket"
        )
        self.stdout.write(self.style.SUCCESS('Sample data loaded successfully!'))
