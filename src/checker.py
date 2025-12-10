"""
URLChecker - URL validation using Selenium with parallel processing and browser reuse
"""

import json
import time
import platform
import logging
from typing import List, Dict, Optional
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


class URLChecker:
    """URL validator using real Chrome browsers via Selenium with parallel processing and browser reuse"""
    
    def __init__(
        self,
        base_url: str,
        locale: str = 'pt',
        page_load_timeout: int = 15,
        element_wait_timeout: int = 10,
        headless: bool = False,
        max_attempts: int = 3,
        retry_delay: float = 2,
        page_delay: float = 0.5,
        url_check_delay: float = 0.3,
        disable_images: bool = True,
        parallel_browsers: int = 3
    ):
        """
        Initialize URL checker with parallel processing support and browser reuse
        
        Args:
            base_url: Turing API base URL
            locale: Locale for requests (default: 'pt')
            page_load_timeout: Page load timeout (seconds)
            element_wait_timeout: Element wait timeout (seconds)
            headless: Run in headless mode (no GUI)
            max_attempts: Maximum retry attempts per URL
            retry_delay: Delay between retries (seconds)
            page_delay: Delay between API pages (seconds)
            url_check_delay: Delay between URL checks (seconds)
            disable_images: Disable image loading
            parallel_browsers: Number of parallel browsers (1-5)
        """
        self.base_url = base_url
        self.locale = locale
        self.page_load_timeout = page_load_timeout
        self.element_wait_timeout = element_wait_timeout
        self.headless = headless
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.page_delay = page_delay
        self.url_check_delay = url_check_delay
        self.disable_images = disable_images
        self.parallel_browsers = max(1, min(5, parallel_browsers))  # Limit 1-5
        
        self.failed_urls = []
        self.total_urls_checked = 0
        self.driver = None  # Main driver for API calls
        self.logger = logging.getLogger(__name__)
        self.lock = Lock()  # Thread-safe operations
        
        # Browser pool for reuse
        self.driver_pool = Queue()
        self.worker_drivers = []  # Track all worker drivers for cleanup
        
        self._setup_driver()
        
        # Log parallel configuration
        if self.parallel_browsers > 1:
            self.logger.info(f"Parallel mode enabled: {self.parallel_browsers} browsers (reused)")
            print(f"⚡ Parallel mode: {self.parallel_browsers} simultaneous browsers (with reuse)")
        else:
            self.logger.info("Sequential mode (no parallelization)")
    
    def _create_chrome_options(self, for_api: bool = False) -> Options:
        """
        Create Chrome options for browser instances
        
        Args:
            for_api: If True, creates options for API calls (less aggressive blocking)
                    If False, creates options for URL checking (maximum blocking)
        """
        chrome_options = Options()
        
        # Options to appear as a normal browser
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Normal user agent
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Accept insecure certificates
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        
        # Disable webdriver detection
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        
        if for_api:
            # API calls - Allow JavaScript but block heavy resources
            prefs = {
                'profile.managed_default_content_settings.images': 2,          # Block images
                'profile.managed_default_content_settings.stylesheets': 2,     # Block CSS
                'profile.managed_default_content_settings.javascript': 1,      # ALLOW JavaScript (needed for API)
                'profile.managed_default_content_settings.cookies': 1,         # Allow cookies
                'profile.managed_default_content_settings.plugins': 2,
                'profile.managed_default_content_settings.popups': 2,
                'profile.managed_default_content_settings.geolocation': 2,
                'profile.managed_default_content_settings.notifications': 2,
                'profile.managed_default_content_settings.media_stream': 2,
                'profile.managed_default_content_settings.fonts': 2,
            }
            chrome_options.add_experimental_option('prefs', prefs)
            chrome_options.page_load_strategy = 'normal'  # Wait for complete load
        else:
            # URL checking - BLOCK EVERYTHING
            prefs = {
                'profile.managed_default_content_settings.images': 2,          # Block images
                'profile.managed_default_content_settings.stylesheets': 2,     # Block CSS
                'profile.managed_default_content_settings.javascript': 2,      # Block JavaScript
                'profile.managed_default_content_settings.cookies': 2,         # Block cookies
                'profile.managed_default_content_settings.plugins': 2,
                'profile.managed_default_content_settings.popups': 2,
                'profile.managed_default_content_settings.geolocation': 2,
                'profile.managed_default_content_settings.notifications': 2,
                'profile.managed_default_content_settings.media_stream': 2,
                'profile.managed_default_content_settings.fonts': 2,
            }
            chrome_options.add_experimental_option('prefs', prefs)
            chrome_options.add_argument('--disable-javascript')  # Extra JS blocking
            chrome_options.page_load_strategy = 'eager'  # Return as soon as DOM is loaded (faster)
        
        # Common optimizations
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        
        # Performance optimizations - reduce overhead
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-breakpad')
        chrome_options.add_argument('--disable-client-side-phishing-detection')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-hang-monitor')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        chrome_options.add_argument('--disable-prompt-on-repost')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--force-color-profile=srgb')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--safebrowsing-disable-auto-update')
        chrome_options.add_argument('--enable-automation')
        chrome_options.add_argument('--password-store=basic')
        chrome_options.add_argument('--use-mock-keychain')
        
        # Maximum performance - minimal caching
        chrome_options.add_argument('--disk-cache-size=1')
        chrome_options.add_argument('--media-cache-size=1')
        chrome_options.add_argument('--aggressive-cache-discard')
        
        # Headless configuration
        if self.headless or platform.system() == 'Linux':
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
        
        return chrome_options
    
    def _create_driver(self, for_api: bool = False) -> webdriver.Chrome:
        """
        Create a new Chrome driver instance
        
        Args:
            for_api: If True, creates driver for API calls
        """
        chrome_options = self._create_chrome_options(for_api=for_api)
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            self.logger.warning(f"Error using webdriver-manager: {e}")
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                self.logger.error(f"Error using system chromedriver: {e2}")
                raise
        
        # Remove webdriver property to avoid detection
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        
        return driver
    
    def _setup_driver(self):
        """Configure main Chrome driver for API calls"""
        self.logger.info("Configuring Chrome browser...")
        self.logger.info(f"Operating system: {platform.system()}")
        
        # Main driver for API - needs JavaScript
        self.driver = self._create_driver(for_api=True)
        self.logger.info("Main browser configured successfully!")
    
    def _initialize_driver_pool(self):
        """Initialize pool of reusable browser drivers for URL checking"""
        if self.parallel_browsers <= 1:
            return
        
        self.logger.info(f"Initializing pool of {self.parallel_browsers} reusable browsers...")
        print(f"🚀 Opening {self.parallel_browsers} browsers for reuse (optimized for speed)...")
        
        for i in range(self.parallel_browsers):
            # Worker drivers for URL checking - maximum blocking
            driver = self._create_driver(for_api=False)
            self.worker_drivers.append(driver)
            self.driver_pool.put(driver)
        
        self.logger.info(f"Browser pool initialized with {self.parallel_browsers} instances")
        print(f"✓ {self.parallel_browsers} browsers ready!\n")
    
    def _get_driver_from_pool(self) -> webdriver.Chrome:
        """Get a driver from the pool (blocks if none available)"""
        return self.driver_pool.get()
    
    def _return_driver_to_pool(self, driver: webdriver.Chrome):
        """Return a driver to the pool for reuse"""
        self.driver_pool.put(driver)
    
    def _cleanup_driver_pool(self):
        """Close all drivers in the pool"""
        if not self.worker_drivers:
            return
        
        self.logger.info(f"Closing {len(self.worker_drivers)} worker browsers...")
        print(f"\n🔒 Closing {len(self.worker_drivers)} worker browsers...")
        
        for driver in self.worker_drivers:
            try:
                driver.quit()
            except Exception as e:
                self.logger.warning(f"Error closing worker driver: {e}")
        
        self.worker_drivers.clear()
        self.logger.info("All worker browsers closed")
    
    def fetch_page(self, page: int) -> Optional[Dict]:
        """
        Fetch specific API page
        
        Args:
            page: Page number
            
        Returns:
            Dictionary with page data or None on error
        """
        url = f"{self.base_url}?q=*&p={page}&_setlocale={self.locale}"
        
        try:
            if page > 1:
                time.sleep(self.page_delay)
            
            self.logger.info(f"Accessing API page {page}...")
            print(f"Accessing API page {page}...")
            
            self.driver.get(url)
            
            # Wait for specific element
            try:
                WebDriverWait(self.driver, self.element_wait_timeout).until(
                    lambda d: d.find_element("tag name", "pre")
                )
            except TimeoutException:
                self.logger.warning(f"Timeout waiting for element on page {page}")
            
            # Get JSON from page
            pre_element = self.driver.find_element("tag name", "pre")
            json_text = pre_element.text
            
            return json.loads(json_text)
            
        except Exception as e:
            self.logger.error(f"Error fetching page {page}: {e}")
            return None
    
    def extract_urls_from_results(self, data: Dict) -> List[str]:
        """
        Extract URLs from API results
        
        Args:
            data: Data returned by API
            
        Returns:
            List of extracted URLs
        """
        urls = []
        
        try:
            results = data.get('results', {}).get('document', [])
            for document in results:
                fields = document.get('fields', {})
                url = fields.get('url')
                
                if url:
                    if isinstance(url, list):
                        url = url[0] if url else None
                    if url:
                        urls.append(url)
                        
        except Exception as e:
            self.logger.error(f"Error extracting URLs: {e}")
        
        return urls
    
    def _check_url_with_driver(
        self, 
        driver: webdriver.Chrome,
        url: str, 
        page: int,
        attempt: int = 1
    ) -> Dict[str, any]:
        """
        Check URL HTTP status with retry attempts using a specific driver
        
        Args:
            driver: Chrome driver instance
            url: URL to check
            page: API page number of origin
            attempt: Current attempt number
            
        Returns:
            Dictionary with check information (url, status_code, page, attempts)
        """
        try:
            # Delay between checks (only for retries)
            if attempt > 1:
                time.sleep(self.retry_delay)
            # No delay for first attempt - start immediately
            
            if attempt > 1:
                self.logger.info(f"Attempt {attempt}/{self.max_attempts}: {url}")
            
            # Configure page timeout
            driver.set_page_load_timeout(self.page_load_timeout)
            
            # Navigate to URL
            try:
                driver.get(url)
                # No delay needed - page_load_strategy 'eager' waits for DOM ready
            except TimeoutException:
                self.logger.warning(f"Timeout ({self.page_load_timeout}s) accessing {url}")
                # Even with timeout, check if we got any response
            except StaleElementReferenceException as e:
                self.logger.warning(f"Stale element on navigation to {url}, retrying...")
                if attempt < self.max_attempts:
                    return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
                return {
                    'url': url,
                    'status_code': -1,
                    'page': page,
                    'attempts': attempt
                }
            except Exception as e:
                self.logger.error(f"Error navigating to {url}: {e}")
                if attempt < self.max_attempts:
                    return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
                return {
                    'url': url,
                    'status_code': -1,
                    'page': page,
                    'attempts': attempt
                }
            
            # Check HTTP status - WITH improved detection
            try:
                # First check: DNS resolution
                from urllib.parse import urlparse
                parsed = urlparse(url)
                hostname = parsed.netloc or parsed.path.split('/')[0]
                
                # Try DNS resolution
                import socket
                try:
                    socket.gethostbyname(hostname)
                except socket.gaierror:
                    self.logger.warning(f"DNS resolution failed for {hostname}")
                    return {
                        'url': url,
                        'status_code': 404,
                        'page': page,
                        'attempts': attempt
                    }
                
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
                
                # Very specific error patterns in title
                if page_title.strip() in ['404', '404 not found', 'page not found', 'not found', 
                                           '403', '403 forbidden', 'forbidden',
                                           '500', '500 internal server error', 'server error',
                                           'error', 'error page']:
                    status = 404
                    
                # Check if redirected to error page
                elif any(err in current_url for err in ['/404', '/error', '/not-found', '/oops']):
                    status = 404
                    
                # Check if domain is completely different AND has error indicators
                # (Some sites redirect to CDN domains, which is OK)
                elif parsed.netloc and parsed.netloc not in current_url:
                    # Only flag as error if redirected to completely different domain AND has error indicators
                    if any(err in current_url for err in ['error', '404', 'notfound']) or \
                       any(err in page_title for err in ['error', '404', 'not found']):
                        self.logger.warning(f"Redirected to error page: {parsed.netloc} -> {current_url}")
                        status = 404
                
                # If URL changed (redirect), report as non-200 status
                # This will flag 302, 301, and other redirects
                elif url_changed:
                    self.logger.info(f"URL redirect detected: {url} -> {final_url}")
                    status = 302  # Mark as redirect
                
                # Check body content if status not yet determined
                if status is None:
                    try:
                        # Retry logic for stale element reference
                        body_text = ''
                        for retry in range(3):  # Try up to 3 times
                            try:
                                body_element = driver.find_element("tag name", "body")
                                body_text = body_element.text.lower()[:1000] if body_element else ''
                                break  # Success - exit retry loop
                            except StaleElementReferenceException:
                                if retry < 2:  # Not last attempt
                                    self.logger.debug(f"Stale element detected, retry {retry + 1}/3")
                                    time.sleep(0.1)  # Brief wait before retry
                                else:
                                    # Last attempt failed - log and continue with empty body
                                    self.logger.warning(f"Could not read body content (stale element): {url}")
                                    body_text = ''
                        
                        # Enhanced error detection in content
                        error_indicators = [
                            '404', 'not found', 'página não encontrada', 
                            'page not found', 'file not found',
                            'this page doesn\'t exist', 'does not exist',
                            'error 404', 'http 404', 'erro 404'
                        ]
                        
                        # Check if body is very small (likely error page)
                        if len(body_text) < 50:
                            # Very small page - check for error indicators
                            if any(err in body_text for err in error_indicators):
                                status = 404
                            else:
                                # Very small but no error text - could be minimal page, assume OK
                                status = 200
                        elif len(body_text) < 200:
                            # Small content - only mark as error if has clear error indicators
                            if any(err in body_text for err in error_indicators):
                                status = 404
                            else:
                                status = 200
                        else:
                            # Normal sized page - check for prominent error messages
                            # Only flag as error if error indicators appear in first 200 chars
                            first_part = body_text[:200]
                            if any(err in first_part for err in error_indicators):
                                status = 404
                            else:
                                status = 200
                            
                    except Exception as body_error:
                        # If can't get body but page loaded, assume success
                        self.logger.warning(f"Could not read body content for {url}: {body_error}")
                        status = 200
                    
            except Exception as e:
                self.logger.warning(f"Error checking status for {url}: {e}")
                # If there was a general error, mark as error
                status = 404
            
            # If not 200 and attempts remain, try again
            if status != 200 and attempt < self.max_attempts:
                self.logger.info(f"Status {status} on attempt {attempt} - retrying...")
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': status,
                'page': page,
                'attempts': attempt
            }
            
        except WebDriverException as e:
            error_msg = str(e)
            self.logger.error(f"WebDriverException accessing {url}: {error_msg[:100]}")
            
            # Check if it's a connection error (driver crashed/disconnected)
            if 'Failed to establish a new connection' in error_msg or \
               'NewConnectionError' in error_msg or \
               'invalid session id' in error_msg.lower():
                self.logger.error(f"WebDriver connection lost - driver may have crashed")
                # Don't retry with same driver as it's dead
                return {
                    'url': url,
                    'status_code': -1,
                    'page': page,
                    'attempts': attempt,
                    'error': 'WebDriver connection lost'
                }
            
            if attempt < self.max_attempts:
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': -1,
                'page': page,
                'attempts': attempt,
                'error': str(e)[:200]
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected error checking {url}: {e}")
            
            if attempt < self.max_attempts:
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': -1,
                'page': page,
                'attempts': attempt,
                'error': str(e)
            }
    
    def _check_url_task(self, url: str, page: int, index: int, total: int) -> Dict[str, any]:
        """
        Task for checking a single URL (reuses driver from pool)
        
        Args:
            url: URL to check
            page: API page number
            index: URL index in current batch
            total: Total URLs in batch
            
        Returns:
            Result dictionary
        """
        driver = None
        max_driver_retries = 2
        driver_retry_count = 0
        
        try:
            # Get driver from pool with retry logic
            while driver_retry_count < max_driver_retries:
                try:
                    driver = self._get_driver_from_pool()
                    
                    # Test if driver is still alive
                    _ = driver.current_url
                    break  # Driver is alive, proceed
                    
                except WebDriverException as e:
                    self.logger.warning(f"Driver from pool is dead, recreating... (attempt {driver_retry_count + 1})")
                    driver_retry_count += 1
                    
                    # Driver is dead, create a new one
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    
                    if driver_retry_count < max_driver_retries:
                        driver = self._create_driver(for_api=False)
                    else:
                        # Give up and return error
                        return {
                            'url': url,
                            'status_code': -1,
                            'page': page,
                            'attempts': 1,
                            'error': 'Failed to get working driver from pool'
                        }
            
            # Check URL
            result = self._check_url_with_driver(driver, url, page)
            
            # Thread-safe console output
            with self.lock:
                status = result['status_code']
                attempts = result.get('attempts', 1)
                
                print(f"  [{index}/{total}] ", end="")
                if status != 200:
                    print(f"❌ {url} Status: {status} (after {attempts} attempts)")
                else:
                    if attempts > 1:
                        print(f"✓ {url} Status: {status} (after {attempts} attempts)")
                    else:
                        print(f"✓ {url} Status: {status}")
            
            return result
            
        finally:
            # Return driver to pool for reuse (only if it's still alive)
            if driver:
                try:
                    # Quick test to see if driver is still responsive
                    _ = driver.current_url
                    self._return_driver_to_pool(driver)
                except:
                    # Driver is dead, don't return it to pool
                    self.logger.warning("Driver died during check, not returning to pool")
                    try:
                        driver.quit()
                    except:
                        pass
                    # Create new driver and add to pool
                    try:
                        new_driver = self._create_driver(for_api=False)
                        self._return_driver_to_pool(new_driver)
                    except Exception as e:
                        self.logger.error(f"Failed to create replacement driver: {e}")
                self._return_driver_to_pool(driver)
    
    def check_urls_parallel(self, urls: List[str], page: int) -> List[Dict]:
        """
        Check multiple URLs in parallel
        
        Args:
            urls: List of URLs to check
            page: API page number
            
        Returns:
            List of results
        """
        results = []
        total = len(urls)
        
        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=self.parallel_browsers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self._check_url_task, url, page, i+1, total): url 
                for i, url in enumerate(urls)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Update counters (thread-safe)
                    with self.lock:
                        self.total_urls_checked += 1
                        if result['status_code'] != 200:
                            self.failed_urls.append(result)
                            
                except Exception as e:
                    url = future_to_url[future]
                    self.logger.error(f"Error processing {url}: {e}")
        
        return results
    
    def check_urls_sequential(self, urls: List[str], page: int):
        """
        Check URLs sequentially (original method)
        
        Args:
            urls: List of URLs to check
            page: API page number
        """
        for i, url in enumerate(urls, 1):
            print(f"  [{i}/{len(urls)}] {url}", end=" ")
            result = self._check_url_with_driver(self.driver, url, page)
            self.total_urls_checked += 1
            
            status = result['status_code']
            attempts = result.get('attempts', 1)
            
            if status != 200:
                self.logger.warning(f"Problematic URL: {url} (status: {status}, attempts: {attempts})")
                print(f"❌ Status: {status} (after {attempts} attempts)")
                self.failed_urls.append(result)
            else:
                if attempts > 1:
                    print(f"✓ Status: {status} (after {attempts} attempts)")
                else:
                    print(f"✓ Status: {status}")
    
    def has_more_pages(self, data: Dict) -> bool:
        """
        Check if more pages are available in API
        
        Args:
            data: Data returned by API
            
        Returns:
            True if more pages exist, False otherwise
        """
        try:
            pagination = data.get('queryContext', {})
            total_pages = pagination.get('pageCount', 0)
            current_page = pagination.get('page', 0)
            return current_page < total_pages
        except:
            return False
    
    def run(self) -> List[Dict]:
        """
        Execute verification of all URLs
        
        Returns:
            List of URLs that failed verification
        """
        page = 1
        
        print("\n" + "=" * 80)
        print("Starting URL verification with real browser (Selenium)...")
        if self.parallel_browsers > 1:
            print(f"⚡ Parallel mode: {self.parallel_browsers} simultaneous browsers (with reuse)")
        print("=" * 80)
        
        self.logger.info("Starting URL verification")
        
        try:
            # Initialize browser pool for parallel execution
            if self.parallel_browsers > 1:
                self._initialize_driver_pool()
            
            while True:
                print(f"\n{'='*80}")
                print(f"PAGE {page}")
                print(f"{'='*80}")
                
                # Fetch page
                data = self.fetch_page(page)
                if not data:
                    self.logger.error(f"Could not fetch page {page}")
                    print(f"Could not fetch page {page}. Ending.")
                    break
                
                # Extract URLs
                urls = self.extract_urls_from_results(data)
                self.logger.info(f"Found {len(urls)} URLs on page {page}")
                print(f"✓ Found {len(urls)} URLs on page {page}\n")
                
                # Check URLs (parallel or sequential)
                if self.parallel_browsers > 1 and len(urls) > 1:
                    self.check_urls_parallel(urls, page)
                else:
                    self.check_urls_sequential(urls, page)
                
                # Check if more pages exist
                if not self.has_more_pages(data):
                    self.logger.info(f"Last page ({page}) processed")
                    print(f"\n✓ Last page ({page}) processed.")
                    break
                
                page += 1
        
        finally:
            # Close worker browsers
            if self.parallel_browsers > 1:
                self._cleanup_driver_pool()
            
            # Close main browser
            if self.driver:
                self.logger.info("Closing main browser...")
                print("\nClosing main browser...")
                self.driver.quit()
        
        print("\n" + "=" * 80)
        print(f"✓ Verification completed!")
        print(f"  Total URLs checked: {self.total_urls_checked}")
        print(f"  Problematic URLs: {len(self.failed_urls)}")
        if self.parallel_browsers > 1:
            print(f"  Parallel browsers used: {self.parallel_browsers} (reused)")
        print("=" * 80)
        
        self.logger.info(f"Verification completed - Total: {self.total_urls_checked}, Failed: {len(self.failed_urls)}")
        
        return self.failed_urls
