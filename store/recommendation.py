"""
Content-based product recommendation engine.
Uses TF-IDF on product name + description to compute cosine similarity.
"""

import logging

logger = logging.getLogger(__name__)


def get_recommendations(product, n=4):
    """
    Return up to `n` products similar to `product` based on
    name + description + style TF-IDF cosine similarity.
    Falls back to name-token similarity, then style-based if sklearn fails.
    """
    from .models import Product

    product = Product.objects.filter(id=product.id).first()
    if not product or n <= 0:
        return []

    all_products = list(Product.objects.filter(is_active=True))
    if len(all_products) <= 1:
        return []

    def style_fallback():
        """Return same-style products excluding the current one."""
        return list(
            Product.objects.filter(style=product.style, is_active=True)
            .exclude(id=product.id)[:n]
        )

    def name_similarity_fallback():
        """Rank by shared name tokens, fall back to style if nothing matches."""
        candidates = list(
            Product.objects.filter(is_active=True).exclude(id=product.id)
        )
        target_tokens = set(product.name.lower().split())

        def similarity_score(c):
            other_tokens = set(c.name.lower().split())
            return len(target_tokens & other_tokens)

        candidates.sort(key=similarity_score, reverse=True)
        return candidates[:n] if candidates else style_fallback()

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError as e:
        logger.warning(f"sklearn missing ({e}), using name similarity fallback")
        return name_similarity_fallback()

    try:
        # Include style name in corpus for better style-aware similarity
        corpus = [
            f"{p.name} {p.description} {p.style.name if p.style else ''}"
            for p in all_products
        ]
        vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(corpus)

        product_ids = [p.id for p in all_products]
        if product.id not in product_ids:
            return style_fallback()

        idx = product_ids.index(product.id)
        cosine_scores = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()

        similar_indices = [i for i in cosine_scores.argsort()[::-1] if i != idx]
        recommended = [all_products[i] for i in similar_indices[:n]]

        return recommended if recommended else style_fallback()

    except Exception as e:
        logger.warning(f"Recommendation engine TF-IDF failed, falling back: {e}")
        return name_similarity_fallback()