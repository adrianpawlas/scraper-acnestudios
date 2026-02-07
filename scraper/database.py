"""
Database operations for Supabase integration.
"""

import logging
import os
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class SupabaseDB:
    """Supabase database operations for product storage."""

    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info("Connected to Supabase")

    def upsert_products(self, products: List[Dict[str, Any]]) -> bool:
        """
        Upsert products into the database.
        Uses (source, product_url) as unique key.
        """
        if not products:
            logger.warning("No products to upsert")
            return True

        try:
            # Convert products to the expected format
            formatted_products = []
            for product in products:
                formatted_product = self._format_product_for_db(product)
                formatted_products.append(formatted_product)

            # Perform upsert using the user's table constraint
            response = self.client.table('products').upsert(
                formatted_products,
                on_conflict='source,product_url'
            ).execute()

            logger.info(f"Successfully upserted {len(products)} products")
            return True

        except Exception as e:
            logger.error(f"Failed to upsert products: {e}")
            return False

    def sync_products(self, source: str, products: List[Dict[str, Any]]) -> bool:
        """
        Sync products: upsert new/updated products and remove old ones.
        This ensures the database only contains currently available products.
        """
        if not products:
            logger.warning("No products to sync")
            return True

        try:
            # First, upsert all products
            if not self.upsert_products(products):
                return False

            # Get all product_urls from the scraped products

            # Delete products from this source that weren't in the current scrape
            # This removes products that are no longer available
            query = self.client.table('products').delete().eq('source', source)

            # Get product URLs from scraped products
            scraped_product_urls = {product.get('product_url') for product in products if product.get('product_url')}

            # Only delete products NOT in our scraped list
            if scraped_product_urls:
                # Use not.in_ to exclude products we just scraped
                response = query.not_.in_('product_url', list(scraped_product_urls)).execute()
                deleted_count = len(response.data) if response.data else 0
                if deleted_count > 0:
                    logger.info(f"Removed {deleted_count} old/unavailable products from {source}")
            else:
                logger.warning("No product_urls found in scraped products, skipping cleanup")

            logger.info(f"Successfully synced {len(products)} products for {source}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync products for {source}: {e}")
            return False

    def _format_product_for_db(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Format product data for database insertion to match user's table schema."""
        import json
        import hashlib

        # Generate unique ID from product_url (since external_id might not be unique)
        product_url = product.get('product_url', '')
        if product_url:
            # Create a hash-based ID from the product URL
            id_hash = hashlib.md5(product_url.encode('utf-8')).hexdigest()
            product_id = f"{product.get('source', 'manual')}_{id_hash[:16]}"
        else:
            # Fallback if no product_url
            product_id = product.get('external_id', f"manual_{hash(product.get('title', 'unknown'))}")

        # Create metadata as text (not JSONB)
        metadata_dict = {
            'source': product.get('source'),
            'country': product.get('country', 'eu'),
            'original_currency': product.get('currency', 'EUR'),
            'external_id': product.get('external_id'),
            'merchant_name': product.get('merchant_name'),
            'scraped_at': None
        }
        metadata_text = json.dumps(metadata_dict)

        def _valid_embedding(emb):
            if emb is None or not isinstance(emb, list):
                return None
            try:
                emb = [float(x) for x in emb]
                if any(not isinstance(x, (int, float)) or str(x).lower() in ('nan', 'inf', '-inf') for x in emb):
                    return None
                return emb
            except (ValueError, TypeError):
                return None

        image_embedding = _valid_embedding(product.get('image_embedding') or product.get('embedding'))
        info_embedding = _valid_embedding(product.get('info_embedding'))

        # Format to match user's table schema exactly
        formatted = {
            'id': product_id,
            'source': product.get('source', 'manual'),
            'product_url': product.get('product_url'),
            'image_url': product.get('image_url'),
            'brand': product.get('brand'),
            'title': product.get('title'),
            'description': product.get('description'),
            'category': product.get('category'),
            'gender': product.get('gender'),
            'metadata': metadata_text,
            'size': product.get('size'),
            'second_hand': product.get('second_hand', False),
            'country': product.get('country'),
            'price': product.get('price'),  # Text: "20USD,400CZK,80PLN"
            'additional_images': product.get('additional_images'),  # JSON array string
            'image_embedding': image_embedding,
            'info_embedding': info_embedding,
        }

        # Remove None values and empty strings to avoid DB issues
        return {k: v for k, v in formatted.items() if v is not None and v != ''}

    def get_product_count(self, source: Optional[str] = None) -> int:
        """Get count of products, optionally filtered by source."""
        try:
            query = self.client.table('products').select('id', count='exact')
            if source:
                query = query.eq('source', source)

            response = query.execute()
            return response.count
        except Exception as e:
            logger.error(f"Failed to get product count: {e}")
            return 0

    def delete_products_by_source(self, source: str) -> bool:
        """Delete all products from a specific source."""
        try:
            response = self.client.table('products').delete().eq('source', source).execute()
            deleted_count = len(response.data) if response.data else 0
            logger.info(f"Deleted {deleted_count} products from source: {source}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete products from source {source}: {e}")
            return False

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            # Simple query to test connection
            response = self.client.table('products').select('id').limit(1).execute()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
