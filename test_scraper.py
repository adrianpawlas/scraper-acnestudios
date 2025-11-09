#!/usr/bin/env python3

import os
import sys
import logging
os.environ['USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
os.environ['EMBEDDINGS_MODEL'] = 'google/siglip-large-patch16-384'

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from scraper.acne_studios import AcneStudiosScraper

def test_scraper():
    """Test the Acne Studios scraper with a limited run."""
    print("Testing Acne Studios scraper...")

    # Create site config
    site_config = {
        'name': 'Acne Studios',
        'base_url': 'https://www.acnestudios.com',
        'categories': [{
            'name': "Men's Clothing",
            'url': 'https://www.acnestudios.com/eu/cz/en/man/clothing/',
            'gender': 'men'
        }],
        'selectors': {
            'product_container': '.product-tile',
            'product_link': 'a[href*="/eu/cz/en/"]',
            'product_title': '.product-tile__name',
            'product_price': '.product-tile__price',
            'product_image': 'img',
            'load_more_button': '.load-more, .show-more'
        },
        'product_selectors': {
            'title': 'h1, .product-title, [data-testid*="product-title"]',
            'price': '.price, .product-price, [data-testid*="price"]',
            'description': '.description, .product-description, [data-testid*="description"]',
            'images': 'img[src*="acnestudios.com"], .product-gallery img, .product-images img',
            'sizes': '.sizes, .size-options, [data-testid*="sizes"]',
            'availability': '.availability, .stock-status, [data-testid*="availability"]'
        },
        'source': 'acne_studios',
        'merchant_name': 'Acne Studios',
        'brand': 'Acne Studios',
        'currency': 'EUR',
        'country': 'eu',
        'second_hand': False,
        'delay_between_requests': 1,  # Faster for testing
        'max_pages': 1  # Only test first page
    }

    try:
        scraper = AcneStudiosScraper(site_config)

        # Debug: Let's check what the page looks like
        soup = scraper.get_soup('https://www.acnestudios.com/eu/cz/en/man/clothing/')
        if soup:
            print("Page fetched successfully")
            # Look for any product-related elements
            product_containers = soup.select('.product-tile')
            print(f"Found {len(product_containers)} .product-tile elements")

            if product_containers:
                first_product = product_containers[0]
                print(f"First product HTML: {str(first_product)[:500]}...")
            else:
                # Try other selectors
                all_divs = soup.find_all('div', class_=lambda x: x and 'product' in x.lower())
                print(f"Found {len(all_divs)} divs with 'product' in class")

                # Print some class names to understand the structure
                if all_divs:
                    sample_classes = [div.get('class') for div in all_divs[:5]]
                    print(f"Sample div classes: {sample_classes}")

                # Look for any links that might be products
                product_links = soup.find_all('a', href=lambda x: x and '/eu/cz/en/' in x)
                print(f"Found {len(product_links)} links with '/eu/cz/en/' in href")

                # Look for specific patterns from the provided HTML
                leather_jacket_link = soup.find('a', href=lambda x: x and 'leather-shirt-jacket' in x)
                if leather_jacket_link:
                    print("Found leather shirt jacket link!")
                    print(f"Link: {leather_jacket_link.get('href')}")
                    # Get the parent container
                    parent = leather_jacket_link.parent
                    print(f"Parent classes: {parent.get('class') if parent else 'No parent'}")
                    print(f"Parent HTML: {str(parent)[:300]}..." if parent else "No parent")
        else:
            print("Failed to fetch page")

        # Scrape products
        products = scraper.run()

        print(f"Successfully scraped {len(products)} products")

        # Show details of first product
        if products:
            product = products[0]
            print("\nFirst product details:")
            print(f"  Title: {product.get('title', 'N/A')}")
            print(f"  Price: {product.get('price', 'N/A')} {product.get('currency', 'N/A')}")
            print(f"  URL: {product.get('product_url', 'N/A')}")
            print(f"  Image URL: {product.get('image_url', 'N/A')}")
            print(f"  Gender: {product.get('gender', 'N/A')}")
            print(f"  Brand: {product.get('brand', 'N/A')}")
            print(f"  External ID: {product.get('external_id', 'N/A')}")
            embedding = product.get('embedding')
            if embedding:
                print(f"  Embedding: {len(embedding)}-dimensional vector")
                print(f"  Embedding sample: {embedding[:3]}...")
            else:
                print("  Embedding: None")

        return True

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_scraper()
    sys.exit(0 if success else 1)
