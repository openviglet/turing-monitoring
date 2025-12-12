"""
Default URL checker plugin
"""
import time
import logging
from typing import Optional, List
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from .base_checker import BaseCheckerPlugin

class ModelJsonChecker(BaseCheckerPlugin):
    """
    Model json checker plugin that uses Selenium to check URLs.
    """
    def __init__(self, error_status_codes: List[int], logger: logging.Logger):
        self.error_status_codes = error_status_codes
        self.logger = logger

    def check(self, driver: WebDriver, url: str) -> dict:
        """
        Check a single URL.
        """
        print(f"Checking Model JSON URL: {url}")
        try:
            # Navigate to URL
            driver.get(url)

            # Check HTTP status
            status = self._get_status(driver, url)

            return {'status_code': status}

        except TimeoutException:
            self.logger.warning(f"Timeout ({driver.get_page_load_timeout()}s) accessing {url}")
            return {'status_code': -1, 'error': 'Timeout'}
        except Exception as e:
            self.logger.error(f"Error navigating to {url}: {e}")
            return {'status_code': -1, 'error': str(e)}

    def _get_status(self, driver: WebDriver, url: str) -> int:
        """
        Check HTTP status with improved detection.
        """
        try:
            # First check: DNS resolution
            from urllib.parse import urlparse
            parsed = urlparse(url)
            hostname = parsed.netloc or parsed.path.split('/')[0]

            import socket
            try:
                socket.gethostbyname(hostname)
            except socket.gaierror:
                self.logger.warning(f"DNS resolution failed for {hostname}")
                return self._detect_error_status_from_patterns('dns_failure')

            # Get current URL after any redirects
            final_url = driver.current_url
            original_url = url.lower()
            current_url = final_url.lower()

            # Check if URL changed (redirect occurred)
            url_changed = (original_url != current_url)

            # Initialize status
            status = None

            # Get title and check for error patterns
            page_title = driver.title.lower() if driver.title else ''

            # Detect HTTP errors from page title
            detected_status = self._detect_http_error_from_content(page_title, current_url)
            if detected_status:
                status = detected_status

            elif url_changed:
                self.logger.info(f"URL redirect detected: {url} -> {final_url}")
                if any(err in current_url for err in ['/404', '/error', '/not-found']) or \
                   any(err in page_title for err in ['404', 'not found', 'error']):
                    detected_status = self._detect_http_error_from_content(page_title + ' ' + current_url, '')
                    status = detected_status if detected_status else 200
                else:
                    status = 200

            if status is None:
                try:
                    body_text = ''
                    for retry in range(3):
                        try:
                            body_element = driver.find_element("tag name", "body")
                            body_text = body_element.text.lower()[:1000] if body_element else ''
                            break
                        except StaleElementReferenceException:
                            if retry < 2:
                                self.logger.debug(f"Stale element detected, retry {retry + 1}/3")
                                time.sleep(0.1)
                            else:
                                self.logger.warning(f"Could not read body content (stale element): {url}")
                                body_text = ''

                    detected_status = self._detect_http_error_from_content(body_text, current_url)

                    if len(body_text) < 50:
                        if detected_status:
                            status = detected_status
                        else:
                            status = 200
                    elif len(body_text) < 200:
                        if detected_status:
                            status = detected_status
                        else:
                            status = 200
                    else:
                        first_part = body_text[:200]
                        detected_status_first = self._detect_http_error_from_content(first_part, current_url)
                        if detected_status_first:
                            status = detected_status_first
                        else:
                            status = 200
                except Exception as body_error:
                    self.logger.warning(f"Could not read body content for {url}: {body_error}")
                    status = 200
            return status

        except Exception as e:
            self.logger.warning(f"Error checking status for {url}: {e}")
            return self._detect_error_status_from_patterns('general_error')

    def _detect_http_error_from_content(self, content: str, url: str = '') -> Optional[int]:
        content_lower = content.lower()
        error_patterns = {
            400: ['400', 'bad request'],
            401: ['401', 'unauthorized', 'not authorized'],
            403: ['403', 'forbidden', 'access denied'],
            404: ['404', 'not found', 'página não encontrada', 'page not found',
                  'file not found', "doesn't exist", 'does not exist', '/404', '/not-found'],
            500: ['500', 'internal server error', 'erro interno', 'server error'],
            502: ['502', 'bad gateway', 'gateway error'],
            503: ['503', 'service unavailable', 'serviço indisponível'],
            504: ['504', 'gateway timeout']
        }

        for status_code in self.error_status_codes:
            if status_code in error_patterns:
                patterns = error_patterns[status_code]
                for pattern in patterns:
                    if pattern in content_lower or pattern in url.lower():
                        return status_code
        if self.error_status_codes:
            strict_error_indicators = ['error page', 'erro:', 'error:']
            if any(err in content_lower for err in strict_error_indicators):
                return self.error_status_codes[0]
        return None

    def _detect_error_status_from_patterns(self, error_type: str) -> int:
        if self.error_status_codes:
            return self.error_status_codes[0]
        return 404
