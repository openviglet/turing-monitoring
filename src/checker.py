"""
URLChecker - URL validation using Selenium with parallel processing and browser reuse
"""

import json
import time
import platform
import logging
import os
import subprocess
import psutil
import urllib3
from datetime import datetime
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

# Increase urllib3 connection pool size for parallel browsers
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
http = urllib3.PoolManager(
    maxsize=20,  # Maximum connections per host
    block=False,  # Don't block if pool is full
    retries=urllib3.Retry(3)
)


class URLChecker:
    """URL validator using real Chrome browsers via Selenium with parallel processing and browser reuse"""
    
    @staticmethod
    def kill_orphan_browsers():
        """
        Kill all orphan Chrome and ChromeDriver processes
        Excludes current process tree to avoid killing browsers just launched
        """
        killed_count = 0
        
        try:
            print("\n🧹 Cleaning up orphan browser processes...")
            
            # Get current process and all its children/grandchildren
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)
            protected_pids = {current_pid}
            
            try:
                # Recursively get all children of current process
                for child in current_process.children(recursive=True):
                    protected_pids.add(child.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid']):
                try:
                    pid = proc.info['pid']
                    ppid = proc.info.get('ppid')
                    
                    # Skip if process is in protected tree
                    if pid in protected_pids:
                        continue
                    
                    # Skip if parent is in protected tree
                    if ppid and ppid in protected_pids:
                        continue
                    
                    proc_name = proc.info['name'].lower() if proc.info['name'] else ''
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # Check if it's a Chrome/ChromeDriver process launched by Selenium
                    is_selenium_chrome = False
                    
                    # ChromeDriver processes
                    if 'chromedriver' in proc_name:
                        is_selenium_chrome = True
                    
                    # Chrome processes with remote-debugging or automation flags
                    elif 'chrome' in proc_name:
                        if any(flag in cmdline.lower() for flag in [
                            '--remote-debugging',
                            '--test-type',
                            '--enable-automation',
                            '--disable-blink-features=automationcontrolled'
                        ]):
                            is_selenium_chrome = True
                    
                    if is_selenium_chrome:
                        proc.kill()
                        killed_count += 1
                        print(f"  ✓ Killed: {proc_name} (PID: {pid})")
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if killed_count > 0:
                print(f"✓ Cleaned up {killed_count} orphan browser process(es)")
                time.sleep(1)  # Give OS time to clean up
            else:
                print("✓ No orphan browser processes found")
                
        except Exception as e:
            print(f"⚠️  Warning: Could not clean up browser processes: {e}")
        
        print()
    
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
        parallel_browsers: int = 3,
        error_status_codes: List[int] = None,
        resume_from_checkpoint: bool = True
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
            error_status_codes: List of status codes to consider as failures (e.g., [404, 500])
            resume_from_checkpoint: Resume from last checkpoint if available (default: True)
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
        self.error_status_codes = error_status_codes if error_status_codes else [404]
        self.resume_from_checkpoint = resume_from_checkpoint
        
        self.failed_urls = []
        self.total_urls_checked = 0
        self.driver = None  # Main driver for API calls
        self.logger = logging.getLogger(__name__)
        self.lock = Lock()  # Thread-safe operations
        
        # Checkpoint file for persistence
        self.checkpoint_dir = 'checkpoints'
        self.checkpoint_file = os.path.join(self.checkpoint_dir, 'checker_progress.json')
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
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
            chrome_options.page_load_strategy = 'none'  # Don't wait for page load - fastest possible
        
        # Common optimizations
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        
        # Prevent hanging on slow connections
        chrome_options.add_argument('--dns-prefetch-disable')
        chrome_options.add_argument('--disable-features=NetworkService')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        
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
            service = Service(
                ChromeDriverManager().install(),
                service_args=['--verbose', '--log-path=chromedriver.log']
            )
            # Set command timeout to prevent hanging
            service.start()
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            self.logger.warning(f"Error using webdriver-manager: {e}")
            try:
                service = Service(service_args=['--verbose', '--log-path=chromedriver.log'])
                service.start()
                driver = webdriver.Chrome(service=service, options=chrome_options)
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
    
    def _detect_http_error_from_content(self, content: str, url: str = '') -> Optional[int]:
        """
        Detect HTTP error status code from page content dynamically
        Only returns status codes that are in error_status_codes
        
        Args:
            content: Page content (title, body text, or URL)
            url: Current URL
            
        Returns:
            Detected status code if it's in error_status_codes, None otherwise
        """
        content_lower = content.lower()
        
        # Define error patterns for each common HTTP status code
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
        
        # Check for each configured error status code
        for status_code in self.error_status_codes:
            if status_code in error_patterns:
                patterns = error_patterns[status_code]
                for pattern in patterns:
                    if pattern in content_lower or pattern in url.lower():
                        return status_code
        
        # Check for generic "error" patterns only if we have error codes configured
        # Be more strict - only flag as error if it's clearly an error page, not just containing the word "error"
        if self.error_status_codes:
            strict_error_indicators = ['error page', 'erro:', 'error:']
            if any(err in content_lower for err in strict_error_indicators):
                # Return the first configured error code as default
                return self.error_status_codes[0]
        
        return None
    
    def _detect_error_status_from_patterns(self, error_type: str) -> int:
        """
        Detect appropriate status code based on error type
        Returns the first configured error status code, or 404 as fallback
        
        Args:
            error_type: Type of error (dns_failure, general_error, etc.)
            
        Returns:
            Status code from configured errors
        """
        if self.error_status_codes:
            # Return first configured error code
            return self.error_status_codes[0]
        # Fallback if no error codes configured (shouldn't happen)
        return 404
    
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
            
            # Set script timeout to prevent hanging on JavaScript
            driver.set_script_timeout(self.page_load_timeout)
            
            # Navigate to URL with explicit timeout handling
            try:
                driver.get(url)
                # No delay needed - page_load_strategy 'eager' waits for DOM ready
            except TimeoutException:
                self.logger.warning(f"Timeout ({self.page_load_timeout}s) accessing {url}")
                # Even with timeout, check if we got any response
            except Exception as e:
                error_msg = str(e)
                # Check if it's a connection/read timeout
                if 'Read timed out' in error_msg or 'HTTPConnectionPool' in error_msg:
                    self.logger.error(f"Connection timeout to {url}: {error_msg}")
                    # Stop page load to prevent hanging
                    try:
                        driver.execute_script("window.stop();")
                    except:
                        pass
                    # Try to refresh driver if multiple timeouts
                    if attempt < self.max_attempts:
                        return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
                    return {
                        'url': url,
                        'status_code': -1,
                        'page': page,
                        'attempts': attempt
                    }
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
                    # DNS failed - likely 404 or similar, detect from error_status_codes
                    status = self._detect_error_status_from_patterns('dns_failure')
                    return {
                        'url': url,
                        'status_code': status,
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
                
                # Detect HTTP errors from page title
                detected_status = self._detect_http_error_from_content(page_title, current_url)
                if detected_status:
                    status = detected_status
                
                # If URL changed (redirect), check if redirected to error page
                # Don't flag as error just because URL changed
                elif url_changed:
                    self.logger.info(f"URL redirect detected: {url} -> {final_url}")
                    # Only flag as error if redirected to error indicators
                    if any(err in current_url for err in ['/404', '/error', '/not-found']) or \
                       any(err in page_title for err in ['404', 'not found', 'error']):
                        # Redirect to error page - detect which error
                        detected_status = self._detect_http_error_from_content(page_title + ' ' + current_url, '')
                        status = detected_status if detected_status else 200
                    else:
                        # Normal redirect (301, 302) - consider as success
                        status = 200
                
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
                        detected_status = self._detect_http_error_from_content(body_text, current_url)
                        
                        # Check if body is very small (likely error page)
                        if len(body_text) < 50:
                            # Very small page - check for error
                            if detected_status:
                                status = detected_status
                            else:
                                # Very small but no error text - could be minimal page, assume OK
                                status = 200
                        elif len(body_text) < 200:
                            # Small content - only mark as error if has clear error indicators
                            if detected_status:
                                status = detected_status
                            else:
                                status = 200
                        else:
                            # Normal sized page - check for prominent error messages
                            # Only flag as error if error indicators appear in first 200 chars
                            first_part = body_text[:200]
                            detected_status_first = self._detect_http_error_from_content(first_part, current_url)
                            if detected_status_first:
                                status = detected_status_first
                            else:
                                status = 200
                            
                    except Exception as body_error:
                        # If can't get body but page loaded, assume success
                        self.logger.warning(f"Could not read body content for {url}: {body_error}")
                        status = 200
                    
            except Exception as e:
                self.logger.warning(f"Error checking status for {url}: {e}")
                # If there was a general error, try to detect from configured errors
                status = self._detect_error_status_from_patterns('general_error')
            
            # If error status and attempts remain, try again
            if status in self.error_status_codes and attempt < self.max_attempts:
                self.logger.info(f"Status {status} on attempt {attempt} - retrying...")
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': status,
                'page': page,
                'attempts': attempt,
                'timestamp': datetime.now().isoformat()
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
            
            # Return as generic error - will be checked against error_status_codes
            # Only retry if -1 is in error_status_codes (which is unlikely)
            status_code = -1
            if status_code in self.error_status_codes and attempt < self.max_attempts:
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': status_code,
                'page': page,
                'attempts': attempt,
                'error': str(e)[:200]
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected error checking {url}: {e}")
            
            # Return as generic error - only retry if -1 is in error_status_codes
            status_code = -1
            if status_code in self.error_status_codes and attempt < self.max_attempts:
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': status_code,
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
                if status in self.error_status_codes:
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
                        if result['status_code'] in self.error_status_codes:
                            self.failed_urls.append(result)
                            self.logger.info(f"Failed URL added to checkpoint: {result['url']} (status: {result['status_code']})")
                            
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
            
            if status in self.error_status_codes:
                self.logger.warning(f"Error URL: {url} (status: {status}, attempts: {attempts})")
                print(f"❌ Status: {status} (after {attempts} attempts)")
                self.failed_urls.append(result)
                self.logger.info(f"Failed URL added to checkpoint: {url} (status: {status})")
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
    
    def _save_checkpoint(self, current_page: int, last_completed_page: int):
        """Save current progress to checkpoint file"""
        try:
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'base_url': self.base_url,
                'locale': self.locale,
                'current_page': current_page,
                'last_completed_page': last_completed_page,
                'total_urls_checked': self.total_urls_checked,
                'failed_urls': self.failed_urls,
                'error_status_codes': self.error_status_codes
            }
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Checkpoint saved: page {current_page}, total checked: {self.total_urls_checked}, failed: {len(self.failed_urls)}")
        except Exception as e:
            self.logger.warning(f"Failed to save checkpoint: {e}")
    
    def _load_checkpoint(self) -> Optional[Dict]:
        """Load checkpoint from file if it exists and matches current configuration"""
        try:
            if not os.path.exists(self.checkpoint_file):
                return None
            
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
            
            # Verify checkpoint matches current configuration
            if (checkpoint.get('base_url') == self.base_url and
                checkpoint.get('locale') == self.locale and
                checkpoint.get('error_status_codes') == self.error_status_codes):
                return checkpoint
            else:
                self.logger.info("Checkpoint found but configuration changed, starting fresh")
                return None
        except Exception as e:
            self.logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    def _clear_checkpoint(self):
        """Clear checkpoint file after successful completion"""
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
                self.logger.info("Checkpoint cleared")
        except Exception as e:
            self.logger.warning(f"Failed to clear checkpoint: {e}")
    
    def run(self) -> List[Dict]:
        """
        Execute verification of all URLs
        
        Returns:
            List of URLs that failed verification
        """
        # Clean up any orphan browser processes before starting
        self.kill_orphan_browsers()
        
        # Try to load checkpoint
        checkpoint = None
        start_page = 1
        
        if self.resume_from_checkpoint:
            checkpoint = self._load_checkpoint()
            if checkpoint:
                start_page = checkpoint.get('current_page', 1)
                self.total_urls_checked = checkpoint.get('total_urls_checked', 0)
                self.failed_urls = checkpoint.get('failed_urls', [])
                
                print("\n" + "=" * 80)
                print("♻️  RESUMING FROM CHECKPOINT")
                print("=" * 80)
                print(f"  Last checkpoint: {checkpoint.get('timestamp')}")
                print(f"  Resuming from page: {start_page}")
                print(f"  URLs checked so far: {self.total_urls_checked}")
                print(f"  Failed URLs so far: {len(self.failed_urls)}")
                print("=" * 80)
                
                self.logger.info(f"Resuming from checkpoint: page {start_page}")
        
        page = start_page
        
        print("\n" + "=" * 80)
        print("Starting URL verification with real browser (Selenium)...")
        if self.parallel_browsers > 1:
            print(f"⚡ Parallel mode: {self.parallel_browsers} simultaneous browsers (with reuse)")
        print(f"📋 Error status codes configured: {', '.join(map(str, self.error_status_codes))}")
        print(f"🔄 Resume from checkpoint: {'Enabled' if self.resume_from_checkpoint else 'Disabled'}")
        print("=" * 80)
        
        self.logger.info("Starting URL verification")
        self.logger.info(f"Error status codes: {self.error_status_codes}")
        
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
                
                # Save checkpoint after processing each page
                self._save_checkpoint(current_page=page + 1, last_completed_page=page)
                
                # Check if more pages exist
                if not self.has_more_pages(data):
                    self.logger.info(f"Last page ({page}) processed")
                    print(f"\n✓ Last page ({page}) processed.")
                    break
                
                page += 1
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            print(f"💾 Checkpoint saved at page {page}")
            print("   Run again to resume from this point")
            self.logger.info(f"User interrupted at page {page}")
            raise
        
        finally:
            # Close worker browsers
            if self.parallel_browsers > 1:
                self._cleanup_driver_pool()
            
            # Close main browser
            if self.driver:
                self.logger.info("Closing main browser...")
                print("\nClosing main browser...")
                self.driver.quit()
        
        # Clear checkpoint on successful completion
        self._clear_checkpoint()
        
        print("\n" + "=" * 80)
        print(f"✓ Verification completed!")
        print(f"  Total URLs checked: {self.total_urls_checked}")
        print(f"  URLs with error status ({', '.join(map(str, self.error_status_codes))}): {len(self.failed_urls)}")
        if self.parallel_browsers > 1:
            print(f"  Parallel browsers used: {self.parallel_browsers} (reused)")
        print("=" * 80)
        
        self.logger.info(f"Verification completed - Total: {self.total_urls_checked}, Failed: {len(self.failed_urls)}")
        
        return self.failed_urls
