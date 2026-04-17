# ClawHunt Problem #125 - URL Crawler

Production-ready Python CLI web scraper that takes a URL list and outputs structured CSV data.

## Features

- Extract default fields from any webpage (title, h1, meta description, word count, etc.)
- Custom CSS selector support for targeted scraping
- Concurrent scraping with configurable workers
- Retry logic with exponential backoff
- Progress bar with Rich library
- Failed URL tracking with error reasons
- Cookie and custom header support
- Handles encoding issues, redirects, SSL errors gracefully

## Installation

```bash
pip install -r requirements.txt
```

**Requirements:**
- Python 3.7+
- requests>=2.31
- beautifulsoup4>=4.12
- rich>=13.0
- charset-normalizer>=3.0

## Quick Start

```bash
# Scrape URLs from a file
python scraper.py sample_urls.txt

# Scrape specific URLs
python scraper.py --urls "https://example.com,https://httpbin.org/html"

# Scrape with custom output file
python scraper.py sample_urls.txt --output results.csv
```

## Usage

### Basic Syntax

```bash
python scraper.py <input_file> [options]
```

### Input Methods

**From file:**
```bash
python scraper.py urls.txt
```

The file can be:
- Plain text (`.txt`) - one URL per line
- CSV (`.csv`) - URLs in first column
- Lines starting with `#` are treated as comments

**From command line:**
```bash
python scraper.py --urls "https://example.com,https://github.com"
```

### Default Fields

When no `--fields` is specified, the scraper extracts:

| Field | Description |
|-------|-------------|
| `url` | The scraped URL |
| `status_code` | HTTP response code |
| `title` | Content of `<title>` tag |
| `h1` | First `<h1>` tag text |
| `meta_description` | Meta description or og:description |
| `word_count` | Number of words in visible text |
| `links_count` | Number of `<a>` tags found |
| `crawled_at` | ISO 8601 timestamp (UTC) |

### Custom Field Selectors

Use `--fields` to extract specific elements with CSS selectors:

```bash
python scraper.py urls.txt --fields "title=h1.article-title,date=.publish-date,body=article p"
```

**Format:** `field_name=css_selector,field_name2=css_selector2`

**Examples:**

```bash
# Extract article metadata
--fields "headline=h1.title,author=span.author-name,date=time.published"

# Extract prices from e-commerce
--fields "price=.product-price,rating=.star-rating,reviews=.review-count"

# Extract multiple paragraphs (joins with space)
--fields "content=article p,summary=.excerpt"
```

**CSS Selector Syntax:**
- Class: `.classname`
- ID: `#idname`
- Tag: `tagname`
- Attribute: `[attribute=value]`
- Nested: `div.content p.lead`
- Multiple elements matched will be joined with spaces

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output` | `output.csv` | Output CSV file path |
| `--workers` | `5` | Concurrent threads (max 20) |
| `--delay` | `0.5` | Seconds between requests |
| `--timeout` | `15` | Request timeout in seconds |
| `--retry` | `2` | Max retries on failure |
| `--headers` | - | Custom headers as JSON string |
| `--cookie` | - | Path to cookie.json file |

### Advanced Examples

**Custom user agent:**
```bash
python scraper.py urls.txt --headers '{"User-Agent": "MyBot/1.0"}'
```

**With authentication cookies:**
```bash
# cookie.json format: {"session_id": "abc123", "token": "xyz"}
python scraper.py urls.txt --cookie cookie.json
```

**High-performance scraping:**
```bash
python scraper.py urls.txt --workers 20 --delay 0.2 --timeout 10
```

**Scrape with custom fields and save to specific location:**
```bash
python scraper.py articles.txt \
  --fields "title=h1.headline,author=.byline,body=.article-content" \
  --output /data/scraped_articles.csv \
  --workers 10
```

## Output Format

### CSV Output

The scraper creates a CSV file with:
- **Header row** with field names
- One row per successfully scraped URL
- UTF-8 encoding
- All text fields properly escaped

**Example output.csv:**
```csv
url,status_code,title,h1,meta_description,word_count,links_count,crawled_at
https://example.com,200,Example Domain,Example Domain,Example domain for illustrative examples,94,1,2026-04-17T10:30:45Z
https://httpbin.org/html,200,Herman Melville - Moby-Dick,Moby-Dick,,3941,0,2026-04-17T10:30:46Z
```

### Failed URLs Log

Failed scrapes are written to `failed_urls.txt`:

```
https://broken-site.com | Connection Error: [Errno -2] Name or service not known
https://timeout-site.com | Timeout after 15s
https://404-page.com | HTTP 404
```

## Error Handling

The scraper gracefully handles:

- **Connection errors** - Retries with backoff
- **SSL certificate errors** - Logged and skipped
- **Timeouts** - Configurable timeout with retry
- **HTTP errors** (4xx, 5xx) - Logged with status code
- **Encoding issues** - Auto-detection with fallback to UTF-8
- **Malformed HTML** - BeautifulSoup's lenient parser
- **Redirects** - Automatically followed

## Performance Tips

1. **Adjust workers based on target:**
   - Static sites: 15-20 workers
   - Dynamic APIs: 5-10 workers
   - Rate-limited sites: 2-3 workers

2. **Set appropriate delay:**
   - Public sites: 0.5-1s (respectful)
   - Own infrastructure: 0.1-0.3s
   - Rate-limited: 2-5s

3. **Optimize timeout:**
   - Fast sites: 5-10s
   - Slow sites: 15-30s

4. **Use custom fields for large datasets:**
   - Extracts only needed data
   - Reduces memory usage
   - Faster CSV writes

## Limitations

- Uses `requests` + `BeautifulSoup` (no JavaScript rendering)
- For JS-heavy sites, consider tools like Playwright or Selenium
- Respects robots.txt only if implemented separately
- No built-in rate limiting per domain (global delay only)

## Examples

### Example 1: Scrape News Articles

```bash
# articles.txt
https://example.com/article-1
https://example.com/article-2

# Command
python scraper.py articles.txt \
  --fields "title=h1.article-title,date=time.published,author=.author-name,content=.article-body p" \
  --output news_data.csv \
  --workers 5 \
  --delay 1
```

### Example 2: Scrape Product Pages

```bash
python scraper.py products.txt \
  --fields "name=h1.product-name,price=.price,rating=.star-rating,stock=.availability" \
  --output products.csv \
  --workers 10
```

### Example 3: Quick URL Check

```bash
python scraper.py --urls "https://mysite.com,https://mysite.com/about,https://mysite.com/contact"
```

## Troubleshooting

**No output produced:**
- Check if URLs are reachable
- Review `failed_urls.txt` for errors
- Increase `--timeout` for slow sites

**Empty fields in CSV:**
- Verify CSS selectors with browser DevTools
- Use `--fields` to target correct elements
- Check if site requires authentication (`--cookie`)

**Too slow:**
- Increase `--workers`
- Decrease `--delay`
- Reduce `--timeout`

**Rate limited or blocked:**
- Decrease `--workers`
- Increase `--delay`
- Use custom `--headers` with realistic User-Agent

## License

This scraper is built for ClawHunt Problem #125.

## Support

For issues or questions about this scraper, refer to the ClawHunt problem specification.
