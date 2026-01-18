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

    def _determine_category_and_gender(self, category_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Determine gender and category based on category name.

        Returns:
            tuple: (gender, category)
            - gender: "men", "women", or None
            - category: "accessory", "footwear", None (for clothing), or "other"
        """
        category_lower = category_name.lower()

        # Gender detection
        if 'men' in category_lower and 'women' not in category_lower:
            gender = 'men'
        elif 'women' in category_lower:
            gender = 'women'
        else:
            gender = None  # unisex becomes null

        # Category detection
        if 'bag' in category_lower or 'scarf' in category_lower or 'scarves' in category_lower:
            category = 'accessory'
        elif 'shoe' in category_lower:
            category = 'footwear'
        elif 'clothing' in category_lower:
            category = None  # clothing is default, no category needed
        else:
            category = 'other'

        return gender, category

    def scrape_category(self, category_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape products from a category page."""
        category_url = category_config['url']
        category_name = category_config['name']

        # Determine gender and category using smart logic
        gender, category = self._determine_category_and_gender(category_name)

        # Use the URL as-is (already includes ?sz parameter for loading all products)
        current_url = category_url
        logger.info(f"Scraping products: {current_url}")

        soup = self.get_soup(current_url)
        if not soup:
            logger.error("Failed to load category page")
            return []

        # Extract all products from the page
        products = self._extract_products_from_page(soup, gender, category)

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

    def _extract_products_from_page(self, soup: BeautifulSoup, gender: Optional[str], category: Optional[str]) -> List[Dict[str, Any]]:
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
                    category=category,
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

            # Get all product images using multiple selectors (similar to extraction script)
            all_images = []

            # Try different selectors to find all images
            image_selectors = [
                selectors.get('images', '.product-gallery img'),
                'img[src*="acnestudios.com"]',
                '.product-gallery img',
                '.product-images img',
                '.gallery img',
                '.swiper img',
                '.carousel img',
                'img[data-src]',
            ]

            for selector in image_selectors:
                elements = soup.select(selector)
                for img in elements:
                    img_data = self._extract_image_info(img)
                    if img_data and img_data['url'] not in [i['url'] for i in all_images]:
                        all_images.append(img_data)

            # Extract URLs and remove duplicates
            image_urls = []
            seen_urls = set()
            for img in all_images:
                if img['url'] not in seen_urls and not any(skip in img['url'].lower() for skip in ['icon', 'logo', 'arrow', 'svg']):
                    image_urls.append(img['url'])
                    seen_urls.add(img['url'])

            # Generate embedding for main image if available
            # Look for the image with '_Y.jpg' suffix (the preferred image)
            embedding = None
            main_image_url = None
            alt_urls = []

            if image_urls:
                # First try to find the image with '_Y.jpg' suffix
                y_image_url = None
                for img_url in image_urls:
                    if '_Y.jpg' in img_url:
                        y_image_url = img_url
                        break

                if y_image_url:
                    # Found the _Y image, use it as main
                    main_image_url = y_image_url
                    # Put all other images in alt_urls
                    alt_urls = [url for url in image_urls if url != y_image_url]
                    logger.info(f"Found _Y image as main: {main_image_url}")
                elif len(image_urls) >= 2:
                    # Fallback: Use second image as main image if no _Y image found
                    main_image_url = image_urls[1]
                    alt_urls = [image_urls[0]] + image_urls[2:]
                    logger.info(f"Using second image as fallback (no _Y image found): {main_image_url}")
                else:
                    # Only one image available, use it as main
                    main_image_url = image_urls[0]
                    logger.info(f"Only one image available: {main_image_url}")

                logger.info(f"Generating embedding for: {main_image_url}")
                embedding = get_image_embedding(main_image_url)

            return {
                'description': description,
                'size': size_str,
                'availability': availability,
                'sku': sku,
                'category': category,
                'tags': [color] if color else None,
                'image_url': main_image_url,  # Update main image URL to use second image
                'image_alt_urls': alt_urls if alt_urls else None,
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

    def _extract_image_info(self, img_element) -> Optional[Dict[str, Any]]:
        """Extract image information from an img element."""
        # Try different attributes for the image URL
        img_url = None
        attributes_tried = []

        # Priority order for image attributes
        for attr in ['data-src', 'data-lazy-src', 'data-original', 'src']:
            url = img_element.get(attr)
            attributes_tried.append(f"{attr}='{url}'")
            if url and not url.startswith('data:') and not 'placeholder' in url.lower():
                img_url = url
                break

        if not img_url:
            return None

        # Make URL absolute
        img_url = urljoin(self.base_url, img_url)

        # Extract additional metadata
        alt_text = img_element.get('alt', '')
        title_text = img_element.get('title', '')
        classes = img_element.get('class', [])

        return {
            'url': img_url,
            'alt': alt_text,
            'title': title_text,
            'classes': classes,
            'attributes_tried': attributes_tried
        }

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
