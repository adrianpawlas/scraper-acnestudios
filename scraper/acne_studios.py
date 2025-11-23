"""
Acne Studios scraper implementation for HTML-based product extraction.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper, ProductData
from .embeddings import get_image_embedding

logger = logging.getLogger(__name__)

class AcneStudiosScraper(BaseScraper):
    """Scraper for Acne Studios website."""

    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)
        self.base_url = site_config['base_url']
        self.max_pages = site_config.get('max_pages', 50)

    def scrape_category(self, category_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape products from a category page."""
        category_url = category_config['url']
        gender = category_config.get('gender', 'unisex')

        # Load all products at once by setting sz to a high number (300+ for 298 products)
        current_url = f"{category_url.rstrip('/')}?sz=300"
        logger.info(f"Scraping products: {current_url}")

        soup = self.get_soup(current_url)
        if not soup:
            logger.error("Failed to load category page")
            return []

        # Extract all products from the page
        products = self._extract_products_from_page(soup, gender)

        # Remove duplicates based on external_id
        unique_products = []
        seen_ids = set()
        for product in products:
            product_id = product.get('external_id')
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_products.append(product)


        logger.info(f"Found {len(unique_products)} products in category {category_config['name']}")
        return unique_products

    def _extract_products_from_page(self, soup: BeautifulSoup, gender: str) -> List[Dict[str, Any]]:
        """Extract product information from a category page."""
        products = []
        selectors = self.config.get('categories', [{}])[0].get('selectors', {})

        # Find all product containers
        product_containers = soup.select(selectors.get('product_container', '.product-tile'))
        logger.info(f"Found {len(product_containers)} product containers")

        for i, container in enumerate(product_containers):
            try:
                # Extract basic product info from listing
                product_link = self.extract_attribute(container, selectors.get('product_link', 'a'), 'href')
                logger.debug(f"Container {i}: product_link = {product_link}")
                if not product_link:
                    logger.debug(f"Container {i}: No product link, skipping")
                    continue

                product_url = urljoin(self.base_url, product_link)

                title = self.extract_text(container, selectors.get('product_title', '.product-tile__name'))
                logger.debug(f"Container {i}: title = {title}")
                if not title:
                    # Try to get title from data attributes
                    data_ga4 = container.get('data-ga4-item')
                    if data_ga4:
                        import json
                        try:
                            data = json.loads(data_ga4)
                            title = data.get('item_name')
                            logger.debug(f"Container {i}: Got title from data attributes: {title}")
                        except:
                            pass

                    if not title:
                        logger.debug(f"Container {i}: No title found, HTML: {str(container)[:200]}...")
                        continue

                price_text = self.extract_text(container, selectors.get('product_price', '.price'))
                price = self.extract_price(price_text) if price_text else None

                # Try multiple attributes for lazy-loaded images
                image_url = None
                img_element = container.select_one(selectors.get('product_image', 'img'))
                if img_element:
                    # Try data-src first (common lazy loading attribute)
                    image_url = img_element.get('data-src')
                    if not image_url:
                        # Try data-lazy-src
                        image_url = img_element.get('data-lazy-src')
                    if not image_url:
                        # Try data-original
                        image_url = img_element.get('data-original')
                    if not image_url:
                        # Fall back to src
                        image_url = img_element.get('src')

                    # Skip placeholder/base64 images
                    if image_url and (image_url.startswith('data:') or 'placeholder' in image_url.lower()):
                        image_url = None

                if image_url:
                    image_url = urljoin(self.base_url, image_url)

                # Generate external ID from URL
                external_id = self._extract_external_id(product_url)

                # Create basic product data
                product_data = ProductData.create_product(
                    external_id=external_id,
                    title=title,
                    product_url=product_url,
                    image_url=image_url,
                    price=price,
                    currency=self.config.get('currency', 'EUR'),
                    gender=gender,
                    source=self.config.get('source', 'acne_studios'),
                    merchant_name=self.config.get('merchant_name', 'Acne Studios'),
                    brand=self.config.get('brand', 'Acne Studios'),
                    second_hand=self.config.get('second_hand', False),
                    country=self.config.get('country', 'eu')
                )

                # Scrape additional details from product page
                detailed_data = self.scrape_product_details(product_url)
                if detailed_data:
                    product_data.update(detailed_data)

                products.append(product_data)

            except Exception as e:
                logger.warning(f"Failed to extract product from container: {e}")
                continue

        return products

    def scrape_product_details(self, product_url: str) -> Optional[Dict[str, Any]]:
        """Scrape detailed information from individual product page."""
        soup = self.get_soup(product_url)
        if not soup:
            return None

        selectors = self.config.get('product_selectors', {})

        try:
            # Extract detailed information
            description = self.extract_text(soup, selectors.get('description', '.description'))

            # Extract sizes
            sizes = self.extract_multiple_texts(soup, selectors.get('sizes', '.sizes'))
            size_str = ', '.join(sizes) if sizes else None

            # Extract availability
            availability = self.extract_text(soup, selectors.get('availability', '.availability'))
            availability = availability.lower() if availability else 'unknown'

            # Extract SKU
            sku = self.extract_text(soup, selectors.get('sku', '.sku'))

            # Extract category from breadcrumbs
            category_text = self.extract_text(soup, selectors.get('category', '.breadcrumb'))
            category = self._parse_category(category_text) if category_text else None

            # Extract color
            color = self.extract_text(soup, selectors.get('color', '.color'))

            # Get all product images
            image_elements = soup.select(selectors.get('images', '.product-gallery img'))
            image_urls = []
            for img in image_elements[:5]:  # Limit to first 5 images
                img_url = img.get('src')
                if img_url:
                    img_url = urljoin(self.base_url, img_url)
                    image_urls.append(img_url)

            # Generate embedding for main image if available
            embedding = None
            if image_urls:
                main_image_url = image_urls[0]
                logger.info(f"Generating embedding for: {main_image_url}")
                embedding = get_image_embedding(main_image_url)

            return {
                'description': description,
                'size': size_str,
                'availability': availability,
                'sku': sku,
                'category': category,
                'tags': [color] if color else None,
                'image_alt_urls': image_urls[1:] if len(image_urls) > 1 else None,
                'embedding': embedding
            }

        except Exception as e:
            logger.error(f"Failed to scrape product details from {product_url}: {e}")
            return None

    def _has_more_products(self, soup: BeautifulSoup, current_count: int) -> bool:
        """Check if there are more products to load."""
        selectors = self.config.get('categories', [{}])[0].get('selectors', {})

        # Check for load more button
        load_more = soup.select_one(selectors.get('load_more_button', '.load-more'))
        if load_more and load_more.get_text(strip=True).lower() in ['load more', 'show more']:
            logger.info("Found 'Load more' button, continuing pagination")
            return True

        # Try to extract total count from page text
        # Look for patterns like "Showing X of Y" or "Men's Clothing (Y) Y items"
        page_text = soup.get_text()

        # Check for "Showing X of Y" pattern
        import re
        showing_match = re.search(r'Showing\s+(\d+)\s+of\s+(\d+)', page_text, re.IGNORECASE)
        if showing_match:
            shown_count = int(showing_match.group(1))
            total_count = int(showing_match.group(2))
            logger.info(f"Page shows {shown_count} of {total_count} products")
            return shown_count < total_count

        # Check for "(X) X items" pattern - like "Men's Clothing (308) 308 items"
        items_match = re.search(r'\((\d+)\)\s*\d*\s*items?', page_text, re.IGNORECASE)
        if items_match:
            total_count = int(items_match.group(1))
            logger.info(f"Total products available: {total_count}")
            return current_count < total_count

        # Check for progress bar or loading indicators
        progress_bar = soup.select_one('.progress-bar--status, [role="progressbar"]')
        if progress_bar:
            # If there's a progress bar, there might be more content loading
            logger.info("Found progress bar, assuming more content available")
            return True

        # Check if we got fewer products than expected on this page
        # If we got less than items_per_page, we've reached the end
        if current_count % 28 != 0:
            logger.info(f"Got {current_count % 28} products on last page, reached end")
            return False

        # If we can't determine and we got a full page, assume there might be more
        # But be conservative - only continue if we haven't exceeded reasonable limits
        if current_count >= 308:  # Based on user's mention of 308 items
            logger.info(f"Reached {current_count} products, likely at end")
            return False

        logger.info(f"Assuming more products available (current: {current_count})")
        return current_count > 0

    def _extract_external_id(self, product_url: str) -> str:
        """Extract external ID from product URL."""
        # Example URL: https://www.acnestudios.com/eu/cz/en/leather-shirt-jacket-red-black/B70160-BBI.html
        # Extract the product code part
        match = re.search(r'/([A-Z0-9-]+)\.html', product_url)
        if match:
            return match.group(1)

        # Fallback: use URL path as ID
        from urllib.parse import urlparse
        path = urlparse(product_url).path
        return path.strip('/').replace('/', '-')

    def _parse_category(self, breadcrumb_text: str) -> Optional[str]:
        """Parse category from breadcrumb text."""
        if not breadcrumb_text:
            return None

        # Split by common separators and take the last meaningful part
        parts = re.split(r'[>/]', breadcrumb_text)
        for part in reversed(parts):
            part = part.strip()
            if part and len(part) > 2 and part.lower() not in ['home', 'acne studios']:
                return part

        return None
