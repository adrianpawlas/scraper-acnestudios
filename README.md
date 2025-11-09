# AI Fashion Scraper - Acne Studios

Lightweight scraper for Acne Studios that populates a Supabase products table with fashion items including SigLIP embeddings.

## Features

- **HTML Scraping**: Extracts product data from Acne Studios website
- **SigLIP Embeddings**: Local 1024-dimensional embeddings for fashion images
- **Supabase Integration**: Direct upsert to products table
- **Respectful Crawling**: Polite delays and proper User-Agent headers
- **Scheduled Runs**: GitHub Actions workflow for automated scraping

## Setup

### Prerequisites

- Python 3.11+
- Supabase account and project
- GitHub account (for scheduling)

### Installation

1. **Clone and setup virtual environment:**
   ```bash
   git clone <repository-url>
   cd scraper-acnestudios
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your values:
   # SUPABASE_URL=your_supabase_project_url
   # SUPABASE_KEY=your_supabase_service_role_key
   # USER_AGENT=Mozilla/5.0...
   # EMBEDDINGS_MODEL=google/siglip-large-patch16-384
   ```

3. **Setup Supabase database:**
   - Run `supabase_schema.sql` in your Supabase SQL editor
   - Run `migrations/20251003_add_unique_index.sql` if needed

## Usage

### Test Database Connection

```bash
python -m scraper.cli --test-db
```

### Scrape Acne Studios

```bash
# Scrape without database sync
python -m scraper.cli --sites acne_studios

# Scrape and sync to database
python -m scraper.cli --sites acne_studios --sync

**Sync behavior:**
- ✅ Upserts new/updated products (no duplicates)
- ✅ Removes products no longer available from the site
- ✅ Keeps database clean and up-to-date
```

### Scrape All Configured Sites

```bash
python -m scraper.cli --sites all --sync
```

## Configuration

### Sites Configuration (`sites.yaml`)

The scraper is configured via `sites.yaml`:

```yaml
acne_studios:
  name: "Acne Studios"
  mode: "html"
  base_url: "https://www.acnestudios.com"
  categories:
    - name: "Men's Clothing"
      url: "https://www.acnestudios.com/eu/cz/en/man/clothing/"
      gender: "men"
  # ... additional config
```

### Adding New Sites

1. Add site configuration to `sites.yaml`
2. Create scraper class in `scraper/` directory
3. Update the scraper factory in `cli.py`

## Data Structure

Products are stored with these key fields:

- `source`: "acne_studios"
- `external_id`: Unique product identifier
- `merchant_name`: "Acne Studios"
- `product_url`: Direct link to product
- `image_url`: Main product image
- `brand`: "Acne Studios"
- `title`: Product name
- `gender`: "men", "women", or "unisex"
- `price`: Numeric price
- `currency`: "EUR"
- `size`: Available sizes (comma-separated)
- `second_hand`: false (for Acne Studios)
- `embedding`: 1024-dimensional SigLIP vector

## Embeddings

The scraper generates local SigLIP embeddings for product images:

- **Model**: google/siglip-large-patch16-384
- **Dimensions**: 1024
- **Performance**: ~1-3 seconds per image
- **Storage**: VECTOR(1024) column in Supabase

### Testing Embeddings

```python
from scraper.embeddings import get_image_embedding

embedding = get_image_embedding("https://example.com/image.jpg")
print(f"Embedding dimensions: {len(embedding)}")
```

## Scheduling

### GitHub Actions

Set up automated daily scraping:

1. Add secrets to your GitHub repository:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `USER_AGENT`
   - `EMBEDDINGS_MODEL` (optional, defaults to SigLIP)

2. The workflow runs daily at 2 AM UTC and can also be triggered manually.

### Local Scheduling

Use cron or Task Scheduler:

```bash
# Daily at 2 AM
crontab -e
0 2 * * * cd /path/to/scraper && python -m scraper.cli --sites all --sync
```

## Architecture

```
scraper/
├── base.py          # Base scraper classes
├── acne_studios.py  # Acne Studios implementation
├── embeddings.py    # SigLIP embedding generation
├── database.py      # Supabase operations
├── cli.py          # Command-line interface
└── __init__.py
```

## Legal & Ethics

- Respects `robots.txt`
- Uses realistic User-Agent headers
- Implements delays between requests
- Only scrapes public product data
- No authentication bypass

## Performance

- **Embedding Generation**: ~30-45 minutes for full catalog
- **Database Operations**: Efficient upsert with conflict resolution
- **Memory Usage**: Batch processing to handle large catalogs

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
   - Verify Supabase project is active

2. **Embedding Generation Slow**
   - First run downloads the model (~1GB)
   - Subsequent runs are faster
   - GPU acceleration if available

3. **Scraping Blocked**
   - Increase delays in `sites.yaml`
   - Rotate User-Agent if needed
   - Consider proxy rotation for production

### Logs

Enable debug logging:

```bash
export PYTHONPATH=.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
python -m scraper.cli --sites acne_studios --sync
```

## Contributing

1. Follow the existing code structure
2. Add tests for new scrapers
3. Update documentation
4. Respect robots.txt and terms of service
