#!/usr/bin/env python3
"""
Script to extract all image URLs from a single Acne Studios product page.
This helps identify which image should be used as the main product image.
"""

import re
import requests
import logging
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import yaml
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductImageExtractor:
    """Extract all images from a product page for manual inspection."""

    def __init__(self, config_path: str = "sites.yaml"):
        """Initialize with site configuration."""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)['acne_studios']

        self.base_url = self.config['base_url']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        })

    def get_soup(self, url: str, timeout: int = 30) -> BeautifulSoup:
        """Fetch URL and return BeautifulSoup object."""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'lxml')
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def extract_all_images(self, product_url: str) -> dict:
        """Extract all images from a product page."""
        soup = self.get_soup(product_url)
        if not soup:
            return None

        selectors = self.config.get('product_selectors', {})

        # Extract title for context
        title = self.extract_text(soup, selectors.get('title', 'h1, .product-title'))
        logger.info(f"Product title: {title}")

        # Get all product images using various selectors
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
            'img[data-lazy-src]',
            'img[data-original]',
            # Also try broader selectors
            'img',
        ]

        for selector in image_selectors:
            elements = soup.select(selector)
            logger.info(f"Selector '{selector}' found {len(elements)} images")

            for img in elements:
                img_data = self._extract_image_info(img)
                if img_data and img_data['url'] not in [i['url'] for i in all_images]:
                    all_images.append(img_data)

        # Remove duplicates and sort by URL for consistency
        unique_images = []
        seen_urls = set()
        for img in all_images:
            if img['url'] not in seen_urls:
                unique_images.append(img)
                seen_urls.add(img['url'])

        return {
            'title': title,
            'product_url': product_url,
            'images': unique_images,
            'total_images': len(unique_images)
        }

    def _extract_image_info(self, img_element) -> dict:
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

    def extract_text(self, element, selector: str) -> str:
        """Extract text from element using CSS selector."""
        if not element:
            return None

        found = element.select_one(selector)
        if found:
            return found.get_text(strip=True)
        return None

    def display_images(self, product_data: dict):
        """Display all extracted images in a readable format."""
        if not product_data:
            print("Failed to extract product data.")
            return

        print("\n" + "="*80)
        print(f"PRODUCT: {product_data['title']}")
        print(f"URL: {product_data['product_url']}")
        print(f"TOTAL IMAGES FOUND: {product_data['total_images']}")
        print("="*80)

        preferred_found = False
        for i, img in enumerate(product_data['images'], 1):
            is_preferred = bool(re.search(r'_[YB]\.jpg', img['url']))
            if is_preferred:
                preferred_found = True
                print(f"\n--- IMAGE {i} ⭐ PREFERRED ---")
            else:
                print(f"\n--- IMAGE {i} ---")
            print(f"URL: {img['url']}")
            if img['alt']:
                print(f"Alt text: {img['alt']}")
            if img['title']:
                print(f"Title: {img['title']}")
            if img['classes']:
                print(f"CSS classes: {', '.join(img['classes'])}")
            print(f"Attributes tried: {img['attributes_tried']}")

        print(f"\n{'='*80}")
        if preferred_found:
            print("⭐ Images marked with ⭐ are the preferred ones (product-only: _Y.jpg or _B.jpg).")
            print("The scraper will use these images and skip products without them.")
        else:
            print("❌ No preferred images found (_Y.jpg or _B.jpg). This product would be skipped.")
        print("\nCopy any image URL above and paste it into a browser to view the image.")

def main():
    """Main function to run the image extraction."""
    if len(sys.argv) != 2:
        print("Usage: python extract_product_images.py <product_url>")
        print("Example: python extract_product_images.py 'https://www.acnestudios.com/eu/cz/en/leather-shirt-jacket-red-black/B70160-BBI.html'")
        sys.exit(1)

    product_url = sys.argv[1]

    # Validate URL format
    if not product_url.startswith('http'):
        print("Error: Please provide a valid URL starting with http:// or https://")
        sys.exit(1)

    try:
        extractor = ProductImageExtractor()
        product_data = extractor.extract_all_images(product_url)

        if product_data:
            extractor.display_images(product_data)
        else:
            print("Failed to extract images from the product page.")

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()