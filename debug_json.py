#!/usr/bin/env python3
"""Debug JSON serialization issues."""

import sys
import os
sys.path.append('.')

from scraper.base import load_sites_config
from scraper.acne_studios import AcneStudiosScraper
from scraper.database import SupabaseDB
import json

def debug_json_issue():
    # Load config
    config = load_sites_config()
    acne_config = config['acne_studios']

    # Create scraper
    scraper = AcneStudiosScraper(acne_config)

    # Scrape just a few products for testing (limit to 3)
    category = acne_config['categories'][0]  # Men's Clothing
    all_products = scraper.scrape_category(category)

    if all_products:
        products = all_products[:3]  # Just test first 3
        print(f'Testing with {len(products)} products')

        for i, product in enumerate(products):
            print(f'\n--- Product {i+1} ---')
            print(f'Keys: {list(product.keys())}')

            # Check embedding
            embedding = product.get('embedding')
            if embedding:
                print(f'Embedding type: {type(embedding)}')
                print(f'Embedding length: {len(embedding) if isinstance(embedding, list) else "N/A"}')
                if isinstance(embedding, list) and len(embedding) >= 5:
                    print(f'First 5 values: {embedding[:5]}')
                    print(f'All values are float? {all(isinstance(x, float) for x in embedding[:10])}')
                else:
                    print(f'Embedding value: {embedding}')
            else:
                print('No embedding')

            # Test JSON serialization
            try:
                json_str = json.dumps(product, default=str)
                print('JSON serialization: SUCCESS')
                # Test parsing it back
                parsed = json.loads(json_str)
                print('JSON parsing: SUCCESS')
            except Exception as e:
                print(f'JSON serialization FAILED: {e}')
                # Find problematic values
                problematic = []
                for k, v in product.items():
                    try:
                        json.dumps({k: v}, default=str)
                    except:
                        problematic.append((k, type(v), str(v)[:100]))
                if problematic:
                    print(f'Problematic fields: {problematic}')
    else:
        print('No products scraped')

if __name__ == "__main__":
    debug_json_issue()
