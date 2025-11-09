"""
Base scraper classes and utilities for fashion product scraping.
"""

import logging
import requests
import time
import re
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import yaml
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Base class for all fashion scrapers."""

    def __init__(self, site_config: Dict[str, Any]):
        self.config = site_config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        })
        self.delay = site_config.get('delay_between_requests', 1)

    def get_soup(self, url: str, timeout: int = 30) -> Optional[BeautifulSoup]:
        """Fetch URL and return BeautifulSoup object."""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()

            # Add delay between requests
            time.sleep(self.delay)

            return BeautifulSoup(response.content, 'lxml')
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def extract_text(self, element, selector: str) -> Optional[str]:
        """Extract text from element using CSS selector."""
        if not element:
            return None
        found = element.select_one(selector)
        return found.get_text(strip=True) if found else None

    def extract_attribute(self, element, selector: str, attr: str) -> Optional[str]:
        """Extract attribute from element using CSS selector."""
        if not element:
            return None
        found = element.select_one(selector)
        return found.get(attr) if found and found.get(attr) else None

    def extract_multiple_texts(self, element, selector: str) -> List[str]:
        """Extract multiple text elements."""
        if not element:
            return []
        elements = element.select(selector)
        return [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]

    def extract_price(self, text: str) -> Optional[float]:
        """Extract numeric price from text."""
        if not text:
            return None

        # Remove currency symbols and find numeric values
        text = re.sub(r'[^\d.,]', '', text)
        # Handle European number format (comma as decimal separator)
        if ',' in text and '.' in text:
            # Assume last dot/comma is decimal separator
            parts = re.split(r'[,.]', text)
            if len(parts) >= 2:
                integer_part = ''.join(parts[:-1])
                decimal_part = parts[-1]
                price_str = f"{integer_part}.{decimal_part}"
            else:
                price_str = text.replace(',', '.')
        else:
            price_str = text.replace(',', '.')

        try:
            return float(price_str)
        except ValueError:
            return None

    @abstractmethod
    def scrape_category(self, category_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape products from a category page."""
        pass

    @abstractmethod
    def scrape_product_details(self, product_url: str) -> Optional[Dict[str, Any]]:
        """Scrape detailed product information from product page."""
        pass

    def run(self) -> List[Dict[str, Any]]:
        """Run the scraper for all configured categories."""
        all_products = []

        for category in self.config.get('categories', []):
            logger.info(f"Scraping category: {category['name']}")
            products = self.scrape_category(category)
            all_products.extend(products)

        return all_products

class ProductData:
    """Helper class to standardize product data structure."""

    @staticmethod
    def create_product(
        external_id: str,
        title: str,
        product_url: str,
        image_url: str,
        price: Optional[float] = None,
        currency: str = "EUR",
        gender: Optional[str] = None,
        size: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create standardized product data dictionary."""
        return {
            'source': kwargs.get('source', 'manual'),
            'external_id': external_id,
            'merchant_name': kwargs.get('merchant_name'),
            'product_url': product_url,
            'image_url': image_url,
            'brand': kwargs.get('brand'),
            'title': title,
            'gender': gender,
            'price': price,
            'currency': currency,
            'size': size,
            'second_hand': kwargs.get('second_hand', False),
            'country': kwargs.get('country', 'eu'),
            **kwargs  # Allow additional fields
        }

def load_sites_config(config_path: str = "sites.yaml") -> Dict[str, Any]:
    """Load sites configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
