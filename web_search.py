import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Optional
import time
from urllib.parse import quote_plus, urlparse
import re

logger = logging.getLogger(__name__)

class WebSearcher:
    """Handles web searching via DuckDuckGo HTML and URL content fetching"""

    def __init__(self):
        self.search_base_url = "https://html.duckduckgo.com/html/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 15

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Search DuckDuckGo HTML and return list of results with URLs and snippets

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of dicts with 'url', 'title', 'snippet' keys
        """
        try:
            logger.info("Searching DuckDuckGo for: %s", query)

            # DuckDuckGo HTML requires POST request
            response = requests.post(
                self.search_base_url,
                data={'q': query},
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # DuckDuckGo HTML uses result divs with class 'result'
            result_divs = soup.find_all('div', class_='result', limit=max_results * 2)

            for result_div in result_divs:
                try:
                    # Find the title/link
                    link_tag = result_div.find('a', class_='result__a')
                    if not link_tag:
                        continue

                    url = link_tag.get('href', '')
                    title = link_tag.get_text(strip=True)

                    # Find the snippet/description
                    snippet = ''
                    snippet_tag = result_div.find('a', class_='result__snippet')
                    if snippet_tag:
                        snippet = snippet_tag.get_text(strip=True)

                    if url and url.startswith('http'):
                        results.append({
                            'url': url,
                            'title': title or 'No title',
                            'snippet': snippet or 'No description available'
                        })

                        if len(results) >= max_results:
                            break

                except Exception as e:
                    logger.debug("Error parsing search result: %s", str(e))
                    continue

            logger.info("Found %d search results", len(results))
            return results

        except requests.exceptions.RequestException as e:
            logger.error("Error searching DuckDuckGo: %s", str(e))
            return []
        except Exception as e:
            logger.error("Unexpected error during search: %s", str(e))
            return []

    def fetch_url_content(self, url: str) -> Optional[Dict[str, str]]:
        """Fetch and extract main content from a URL

        Args:
            url: URL to fetch

        Returns:
            Dict with 'url', 'title', 'content' keys or None if failed
        """
        try:
            logger.debug("Fetching content from: %s", url)
            response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Extract title
            title = ''
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Extract main content
            content = ''

            # Try to find main content areas
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_=re.compile('content|main|article', re.I)) or
                soup.find('body')
            )

            if main_content:
                # Extract all paragraphs
                paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3'])
                texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                content = ' '.join(texts)

            # Limit content length
            max_content_length = 5000
            if len(content) > max_content_length:
                content = content[:max_content_length] + '...'

            if not content:
                logger.warning("No content extracted from %s", url)
                return None

            return {
                'url': url,
                'title': title,
                'content': content
            }

        except requests.exceptions.RequestException as e:
            logger.warning("Error fetching URL %s: %s", url, str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error fetching URL %s: %s", url, str(e))
            return None

    def fetch_multiple_urls(self, urls: List[str], max_urls: int = 5) -> List[Dict[str, str]]:
        """Fetch content from multiple URLs with rate limiting

        Args:
            urls: List of URLs to fetch
            max_urls: Maximum number of URLs to fetch

        Returns:
            List of dicts with 'url', 'title', 'content' keys
        """
        results = []

        for i, url in enumerate(urls[:max_urls]):
            if i > 0:
                time.sleep(1)  # Rate limiting

            content = self.fetch_url_content(url)
            if content:
                results.append(content)

        logger.info("Successfully fetched %d URLs out of %d", len(results), min(len(urls), max_urls))
        return results

    def verify_url_exists(self, url: str) -> bool:
        """Verify that a URL is accessible

        Args:
            url: URL to verify

        Returns:
            True if URL is accessible, False otherwise
        """
        try:
            response = requests.head(url, headers=self.headers, timeout=5, allow_redirects=True)
            return response.status_code == 200
        except:
            try:
                # Try GET request if HEAD fails
                response = requests.get(url, headers=self.headers, timeout=5, allow_redirects=True)
                return response.status_code == 200
            except:
                return False
