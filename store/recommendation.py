"""
Content-based product recommendation engine.
Uses TF-IDF on product name + description to compute cosine similarity.
"""

import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def get_recommendations(product, n=4):
    """
    Return up to `n` products similar to `product` based on
    name + description TF-IDF cosine similarity.
    Falls back to same-style products if sklearn fails.
    """
    try:
        from .models import Product

        # Fetch all active products
        all_products = list(Product.objects.filter(is_active=True))

        if len(all_products) < 2:
            return []

        # Build corpus: combine name + description for each product
        corpus = [f"{p.name} {p.description}" for p in all_products]

        # Build TF-IDF matrix
        vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(corpus)

        # Find the index of the current product
        product_ids = [p.id for p in all_products]
        if product.id not in product_ids:
            return []

        idx = product_ids.index(product.id)

        # Compute cosine similarity between current product and all others
        cosine_scores = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()

        # Get indices sorted by similarity descending, exclude self
        similar_indices = [
            i for i in cosine_scores.argsort()[::-1]
            if i != idx
        ]

        # Return top-n as Product objects
        return [all_products[i] for i in similar_indices[:n]]

    except Exception as e:
        logger.warning(f"Recommendation engine failed, falling back: {e}")
        from .models import Product
        return list(
            Product.objects.filter(style=product.style, is_active=True)
            .exclude(id=product.id)[:n]
        )
