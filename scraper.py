#!/usr/bin/env python3
"""
ClawHunt Problem #125 - Production Web Scraper
Flexible CLI scraper: input URL list → structured CSV output
"""

import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class Scraper:
    def __init__(self, timeout=15, delay=0.5, retry=2, headers=None, cookies=None):
        self.timeout = timeout
        self.delay = delay
        self.retry = retry
        self.session = requests.Session()

        # Set default headers
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        if headers:
            default_headers.update(headers)
        self.session.headers.update(default_headers)

        # Set cookies if provided
        if cookies:
            self.session.cookies.update(cookies)

    def fetch_url(self, url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Fetch URL with retry logic. Returns (response, error_message)"""
        for attempt in range(self.retry + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                return response, None
            except requests.exceptions.SSLError as e:
                if attempt == self.retry:
                    return None, f"SSL Error: {str(e)}"
            except requests.exceptions.Timeout:
                if attempt == self.retry:
                    return None, f"Timeout after {self.timeout}s"
            except requests.exceptions.ConnectionError as e:
                if attempt == self.retry:
                    return None, f"Connection Error: {str(e)}"
            except requests.exceptions.RequestException as e:
                if attempt == self.retry:
                    return None, f"Request Error: {str(e)}"

            # Wait before retry
            if attempt < self.retry:
                time.sleep(1)

        return None, "Unknown error"

    def extract_default_fields(self, url: str, response: requests.Response) -> Dict[str, any]:
        """Extract default fields from HTML response"""
        # Handle encoding
        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            # Try to detect encoding
            try:
                from charset_normalizer import from_bytes
                detected = from_bytes(response.content).best()
                content = str(detected) if detected else response.text
            except:
                content = response.content.decode('utf-8', errors='ignore')

        soup = BeautifulSoup(content, 'html.parser')

        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''

        # Extract first h1
        h1_tag = soup.find('h1')
        h1 = h1_tag.get_text(strip=True) if h1_tag else ''

        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        meta_description = meta_desc.get('content', '').strip() if meta_desc else ''

        # Word count (visible text)
        text = soup.get_text(separator=' ', strip=True)
        word_count = len(re.findall(r'\w+', text))

        # Links count
        links = soup.find_all('a', href=True)
        links_count = len(links)

        # Crawled timestamp
        crawled_at = datetime.utcnow().isoformat() + 'Z'

        return {
            'url': url,
            'status_code': response.status_code,
            'title': title,
            'h1': h1,
            'meta_description': meta_description,
            'word_count': word_count,
            'links_count': links_count,
            'crawled_at': crawled_at
        }

    def extract_custom_fields(self, response: requests.Response, field_selectors: Dict[str, str]) -> Dict[str, str]:
        """Extract custom fields using CSS selectors"""
        # Handle encoding
        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                from charset_normalizer import from_bytes
                detected = from_bytes(response.content).best()
                content = str(detected) if detected else response.text
            except:
                content = response.content.decode('utf-8', errors='ignore')

        soup = BeautifulSoup(content, 'html.parser')
        results = {}

        for field_name, selector in field_selectors.items():
            elements = soup.select(selector)
            if elements:
                # Join multiple elements with space
                results[field_name] = ' '.join([el.get_text(strip=True) for el in elements])
            else:
                results[field_name] = ''

        return results

    def scrape_url(self, url: str, custom_fields: Optional[Dict[str, str]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Scrape a single URL. Returns (data_dict, error_message)"""
        response, error = self.fetch_url(url)

        if error:
            return None, error

        if response.status_code >= 400:
            return None, f"HTTP {response.status_code}"

        try:
            if custom_fields:
                data = {'url': url, 'status_code': response.status_code}
                data.update(self.extract_custom_fields(response, custom_fields))
                data['crawled_at'] = datetime.utcnow().isoformat() + 'Z'
            else:
                data = self.extract_default_fields(url, response)

            # Delay between requests
            time.sleep(self.delay)

            return data, None
        except Exception as e:
            return None, f"Parsing error: {str(e)}"


def parse_custom_fields(fields_str: str) -> Dict[str, str]:
    """Parse --fields string into dict of field_name: css_selector"""
    fields = {}
    for pair in fields_str.split(','):
        if '=' not in pair:
            print(f"Warning: Invalid field format '{pair}', expected 'name=selector'", file=sys.stderr)
            continue
        name, selector = pair.split('=', 1)
        fields[name.strip()] = selector.strip()
    return fields


def load_urls_from_file(file_path: str) -> List[str]:
    """Load URLs from txt or csv file"""
    urls = []
    path = Path(file_path)

    if not path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix.lower() == '.csv':
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():
                    urls.append(row[0].strip())
        else:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)

    return urls


def main():
    parser = argparse.ArgumentParser(
        description='ClawHunt #125 - Flexible web scraper CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py urls.txt
  python scraper.py --urls "https://example.com,https://httpbin.org/html"
  python scraper.py urls.txt --fields "title=h1.main-title,date=time.published"
  python scraper.py urls.txt --output results.csv --workers 10 --delay 1
        """
    )

    parser.add_argument('input_file', nargs='?', help='Input file with URLs (txt or csv)')
    parser.add_argument('--urls', help='Comma-separated URLs (alternative to file)')
    parser.add_argument('--fields', help='Custom CSS selectors: "name1=selector1,name2=selector2"')
    parser.add_argument('--output', default='output.csv', help='Output CSV file (default: output.csv)')
    parser.add_argument('--workers', type=int, default=5, help='Concurrent threads (default: 5, max: 20)')
    parser.add_argument('--delay', type=float, default=0.5, help='Seconds between requests (default: 0.5)')
    parser.add_argument('--timeout', type=int, default=15, help='Request timeout in seconds (default: 15)')
    parser.add_argument('--headers', help='Custom headers as JSON string')
    parser.add_argument('--cookie', help='Path to cookie.json file')
    parser.add_argument('--retry', type=int, default=2, help='Max retries on failure (default: 2)')

    args = parser.parse_args()

    # Validate input
    if not args.input_file and not args.urls:
        parser.error("Either input_file or --urls must be provided")

    # Load URLs
    if args.urls:
        urls = [u.strip() for u in args.urls.split(',') if u.strip()]
    else:
        urls = load_urls_from_file(args.input_file)

    if not urls:
        print("Error: No URLs to scrape", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(urls)} URLs to scrape")

    # Parse custom fields
    custom_fields = None
    if args.fields:
        custom_fields = parse_custom_fields(args.fields)
        print(f"Using custom fields: {list(custom_fields.keys())}")

    # Parse headers
    headers = None
    if args.headers:
        try:
            headers = json.loads(args.headers)
        except json.JSONDecodeError:
            print("Error: Invalid JSON in --headers", file=sys.stderr)
            sys.exit(1)

    # Load cookies
    cookies = None
    if args.cookie:
        try:
            with open(args.cookie, 'r') as f:
                cookies = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading cookies: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate workers
    workers = min(max(1, args.workers), 20)

    # Initialize scraper
    scraper = Scraper(
        timeout=args.timeout,
        delay=args.delay,
        retry=args.retry,
        headers=headers,
        cookies=cookies
    )

    # Scrape URLs with progress bar
    results = []
    failed_urls = []

    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Scraping...", total=len(urls))

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(scraper.scrape_url, url, custom_fields): url for url in urls}

                for future in as_completed(futures):
                    url = futures[future]
                    data, error = future.result()

                    if error:
                        failed_urls.append((url, error))
                    else:
                        results.append(data)

                    progress.update(task, advance=1)
    else:
        # Fallback to simple progress
        print("Scraping URLs...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(scraper.scrape_url, url, custom_fields): url for url in urls}

            completed = 0
            for future in as_completed(futures):
                url = futures[future]
                data, error = future.result()

                if error:
                    failed_urls.append((url, error))
                else:
                    results.append(data)

                completed += 1
                print(f"Progress: {completed}/{len(urls)}", end='\r')
        print()

    # Write results to CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n✓ Successfully scraped {len(results)} URLs")
        print(f"✓ Output written to: {args.output}")
    else:
        print("\n✗ No successful scrapes", file=sys.stderr)

    # Write failed URLs
    if failed_urls:
        with open('failed_urls.txt', 'w', encoding='utf-8') as f:
            for url, error in failed_urls:
                f.write(f"{url} | {error}\n")

        print(f"✗ Failed: {len(failed_urls)} URLs (see failed_urls.txt)")

    # Exit with appropriate code
    sys.exit(0 if results else 1)


if __name__ == '__main__':
    main()
