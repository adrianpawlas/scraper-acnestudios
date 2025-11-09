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
        Uses (source, external_id) as unique key.
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

            # Perform upsert
            response = self.client.table('products').upsert(
                formatted_products,
                on_conflict='source,external_id'
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

            # Get all external_ids from the scraped products
            scraped_external_ids = {product.get('external_id') for product in products if product.get('external_id')}

            # Delete products from this source that weren't in the current scrape
            # This removes products that are no longer available
            query = self.client.table('products').delete().eq('source', source)

            # Only delete products NOT in our scraped list
            if scraped_external_ids:
                # Use not.in_ to exclude products we just scraped
                response = query.not_.in_('external_id', list(scraped_external_ids)).execute()
                deleted_count = len(response.data) if response.data else 0
                if deleted_count > 0:
                    logger.info(f"Removed {deleted_count} old/unavailable products from {source}")
            else:
                logger.warning("No external_ids found in scraped products, skipping cleanup")

            logger.info(f"Successfully synced {len(products)} products for {source}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync products for {source}: {e}")
            return False

    def _format_product_for_db(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Format product data for database insertion."""
        # Create metadata JSON
        metadata = {
            'source': product.get('source'),
            'country': product.get('country', 'eu'),
            'original_currency': product.get('currency', 'EUR'),
            'scraped_at': None,  # Will be set by DB trigger
        }

        # Handle embedding - ensure it's a list of floats or None
        embedding = product.get('embedding')
        if embedding is not None and not isinstance(embedding, list):
            embedding = None

        formatted = {
            'source': product.get('source', 'manual'),
            'external_id': product.get('external_id', ''),
            'merchant_name': product.get('merchant_name'),
            'product_url': product.get('product_url'),
            'image_url': product.get('image_url'),
            'brand': product.get('brand'),
            'title': product.get('title'),
            'gender': product.get('gender'),
            'price': product.get('price'),
            'currency': product.get('currency', 'EUR'),
            'size': product.get('size'),
            'second_hand': product.get('second_hand', False),
            'country': product.get('country', 'eu'),
            'description': product.get('description'),
            'category': product.get('category'),
            'subcategory': product.get('subcategory'),
            'tags': product.get('tags'),
            'availability': product.get('availability', 'unknown'),
            'sku': product.get('sku'),
            'image_alt_urls': product.get('image_alt_urls'),
            'metadata': metadata,
            'embedding': embedding
        }

        # Remove None values to avoid DB issues
        return {k: v for k, v in formatted.items() if v is not None}

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
