#!/usr/bin/env python3
"""
Command-line interface for the fashion scraper.
"""

import argparse
import logging
import sys
from typing import List, Dict, Any
from .base import load_sites_config
from .acne_studios import AcneStudiosScraper
from .database import SupabaseDB

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def get_scraper(site_name: str, site_config: Dict[str, Any]):
    """Factory function to create appropriate scraper instance."""
    if site_name == 'acne_studios':
        return AcneStudiosScraper(site_config)
    else:
        raise ValueError(f"Unknown site: {site_name}")

def scrape_site(site_name: str, site_config: Dict[str, Any], sync: bool = False) -> List[Dict[str, Any]]:
    """Scrape products from a single site."""
    logger.info(f"Starting scrape for site: {site_name}")

    try:
        scraper = get_scraper(site_name, site_config)
        products = scraper.run()

        logger.info(f"Scraped {len(products)} products from {site_name}")

        if sync:
            db = SupabaseDB()
            source = site_config.get('source', site_name)
            if db.sync_products(source, products):
                logger.info(f"Successfully synced {len(products)} products to database")
            else:
                logger.error("Failed to sync products to database")

        return products

    except Exception as e:
        logger.error(f"Failed to scrape site {site_name}: {e}")
        return []

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Fashion Product Scraper')
    parser.add_argument(
        '--sites',
        nargs='+',
        choices=['all', 'acne_studios'],
        default=['all'],
        help='Sites to scrape (default: all)'
    )
    parser.add_argument(
        '--sync',
        action='store_true',
        help='Sync scraped data to Supabase database'
    )
    parser.add_argument(
        '--config',
        default='sites.yaml',
        help='Path to sites configuration file'
    )
    parser.add_argument(
        '--test-db',
        action='store_true',
        help='Test database connection and exit'
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_sites_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config from {args.config}: {e}")
        sys.exit(1)

    # Test database connection if requested
    if args.test_db:
        try:
            db = SupabaseDB()
            if db.test_connection():
                logger.info("Database connection test passed")
                sys.exit(0)
            else:
                logger.error("Database connection test failed")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Database test failed: {e}")
            sys.exit(1)

    # Determine which sites to scrape
    if 'all' in args.sites:
        sites_to_scrape = list(config.keys())
    else:
        sites_to_scrape = args.sites

    total_products = 0

    # Scrape each site
    for site_name in sites_to_scrape:
        if site_name not in config:
            logger.warning(f"Site '{site_name}' not found in config, skipping")
            continue

        site_config = config[site_name]
        products = scrape_site(site_name, site_config, args.sync)
        total_products += len(products)

    logger.info(f"Scraping completed. Total products processed: {total_products}")

if __name__ == '__main__':
    main()
