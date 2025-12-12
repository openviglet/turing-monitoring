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
import tempfile
import random
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

# Increase urllib3 connection pool size for parallel browsers
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
http = urllib3.PoolManager(
    maxsize=20,  # Maximum connections per host
    block=False,  # Don't block if pool is full
    retries=urllib3.Retry(3)
)


import importlib

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
        resume_from_checkpoint: bool = True,
        plugin_name: str = 'default_checker',
        skip_driver_version_check: bool = False
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
            plugin_name: The name of the checker plugin to use.
            skip_driver_version_check: Skip ChromeDriver version check and use system driver
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
        self.skip_driver_version_check = skip_driver_version_check
        
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
        
        # Load the checker plugin dynamically
        try:
            plugin_module = importlib.import_module(f"src.plugins.{plugin_name}")
            plugin_class_name = "".join(word.capitalize() for word in plugin_name.split('_'))
            plugin_class = getattr(plugin_module, plugin_class_name)
            self.checker_plugin = plugin_class(self.error_status_codes, self.logger)
            self.logger.info(f"Loaded checker plugin: {plugin_name}")
        except (ImportError, AttributeError) as e:
            self.logger.warning(f"Could not load plugin '{plugin_name}': {e}. Falling back to DefaultChecker.")
            # Load DefaultChecker dynamically only when needed as fallback
            fallback_module = importlib.import_module("src.plugins.default_checker")
            fallback_class = getattr(fallback_module, "DefaultChecker")
            self.checker_plugin = fallback_class(self.error_status_codes, self.logger)

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
        
        # Critical flags for Linux/snap/container environments
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        
        # Increase stability - prevent crashes
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-features=IsolateOrigins')
        chrome_options.add_argument('--disable-site-isolation-trials')
        
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
            # Additional flags for stability in Linux/headless/snap environments
            # Use random port for debugging to avoid conflicts
            debug_port = random.randint(9222, 9999)
            chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument('--disable-setuid-sandbox')
            chrome_options.add_argument('--no-zygote')
            # Additional stability flags for renderer connection
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            chrome_options.add_argument('--disable-crash-reporter')
        
        # Critical flags for renderer connection stability (all platforms)
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
        chrome_options.add_argument('--force-device-scale-factor=1')
        chrome_options.add_argument('--disable-blink-features')
        
        # User data directory to avoid conflicts
        user_data_dir = tempfile.mkdtemp(prefix='chrome_')
        chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
        
        return chrome_options
    
    def _create_driver(self, for_api: bool = False) -> webdriver.Chrome:
        """
        Create a new Chrome driver instance
        
        Args:
            for_api: If True, creates driver for API calls
        """
        chrome_options = self._create_chrome_options(for_api=for_api)
        
        # If skip version check, use system driver directly
        if self.skip_driver_version_check:
            self.logger.info("Skipping ChromeDriver version check - using system driver")
            try:
                # Create service with verbose logging
                service = Service(log_path='NUL' if platform.system() == 'Windows' else '/dev/null')
                service.creation_flags = 0x08000000  # CREATE_NO_WINDOW flag for Windows
                driver = webdriver.Chrome(service=service, options=chrome_options)
                self.logger.info("ChromeDriver initialized successfully from PATH (version check skipped)")
                return driver
            except Exception as e:
                self.logger.error(f"Error using system chromedriver: {e}")
                # Last resort: try without service
                try:
                    driver = webdriver.Chrome(options=chrome_options)
                    self.logger.info("ChromeDriver initialized without service")
                    return driver
                except Exception as e2:
                    self.logger.error(f"All attempts failed: {e2}")
                    raise
        
        # Normal flow: try Selenium Manager first
        try:
            # Try to install/update ChromeDriver matching Chrome version
            driver = webdriver.Chrome(service=Service(), options=chrome_options)
            self.logger.info("ChromeDriver initialized successfully via Selenium Manager")
        except Exception as e:
            self.logger.warning(f"Error using Selenium Manager: {e}")
            try:
                # Try without specifying service (use PATH or system chromedriver)
                driver = webdriver.Chrome(options=chrome_options)
                self.logger.info("ChromeDriver initialized successfully from PATH")
            except Exception as e2:
                self.logger.error(f"Error using system chromedriver: {e2}")
                self.logger.error("Please ensure Chrome/Chromium and compatible ChromeDriver are installed")
                self.logger.error("On Linux: sudo apt-get install chromium-chromedriver")
                self.logger.error("Or set skip_driver_version_check=true in config.ini to use existing driver")
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
        """Create and fill the browser pool for parallel checking"""
        self.logger.info(f"Initializing browser pool with {self.parallel_browsers} browsers...")
        print(f"🔄 Initializing {self.parallel_browsers} parallel browsers...")
        
        for _ in range(self.parallel_browsers):
            try:
                driver = self._create_driver(for_api=False)
                self.driver_pool.put(driver)
                self.worker_drivers.append(driver)  # Keep track for cleanup
            except Exception as e:
                self.logger.error(f"Failed to create a worker browser: {e}")
        
        self.logger.info(f"Browser pool initialized with {self.driver_pool.qsize()} browsers")
        print(f"✓ Browser pool ready with {self.driver_pool.qsize()} browsers\n")

    def _get_driver_from_pool(self) -> webdriver.Chrome:
        """Get a driver from the pool (blocks until one is available)"""
        return self.driver_pool.get()

    def _return_driver_to_pool(self, driver: webdriver.Chrome):
        """Return a driver to the pool"""
        self.driver_pool.put(driver)

    def _cleanup_driver_pool(self):
        """Close all worker browsers and clear the pool"""
        self.logger.info(f"Closing {len(self.worker_drivers)} worker browsers...")
        print(f"\nClosing {len(self.worker_drivers)} worker browsers...")
        
        # Close all tracked worker drivers
        for driver in self.worker_drivers:
            try:
                driver.quit()
            except:
                pass
        
        # Clear the queue
        while not self.driver_pool.empty():
            try:
                self.driver_pool.get_nowait()
            except:
                break
        
        self.worker_drivers.clear()
        self.logger.info("Worker browsers closed and pool cleared")
    
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
            
            if attempt > 1:
                self.logger.info(f"Attempt {attempt}/{self.max_attempts}: {url}")
            
            # Configure page timeout
            driver.set_page_load_timeout(self.page_load_timeout)
            
            # Set script timeout to prevent hanging on JavaScript
            driver.set_script_timeout(self.page_load_timeout)

            # Use the plugin to check the URL
            result = self.checker_plugin.check(driver, url)
            status = result.get('status_code')
            
            # If error status and attempts remain, try again
            if status in self.error_status_codes and attempt < self.max_attempts:
                self.logger.info(f"Status {status} on attempt {attempt} - retrying...")
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url,
                'status_code': status,
                'page': page,
                'attempts': attempt,
                'timestamp': datetime.now().isoformat(),
                'error': result.get('error')
            }
            
        except WebDriverException as e:
            error_msg = str(e)
            self.logger.error(f"WebDriverException accessing {url}: {error_msg[:100]}")
            
            if 'Failed to establish a new connection' in error_msg or \
               'NewConnectionError' in error_msg or \
               'invalid session id' in error_msg.lower():
                self.logger.error(f"WebDriver connection lost - driver may have crashed")
                return {
                    'url': url, 'status_code': -1, 'page': page, 'attempts': attempt,
                    'error': 'WebDriver connection lost'
                }
            
            status_code = -1
            if status_code in self.error_status_codes and attempt < self.max_attempts:
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url, 'status_code': status_code, 'page': page, 'attempts': attempt,
                'error': str(e)[:200]
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected error checking {url}: {e}")
            
            status_code = -1
            if status_code in self.error_status_codes and attempt < self.max_attempts:
                return self._check_url_with_driver(driver, url, page, attempt=attempt + 1)
            
            return {
                'url': url, 'status_code': status_code, 'page': page, 'attempts': attempt,
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

    def fetch_page(self, page: int) -> Optional[Dict]:
        """
        Fetch API page and extract results
        
        Args:
            page: Page number to fetch
            
        Returns:
            Dictionary with API response or None on error
        """
        try:
            # Use 'p' parameter for pagination (not 'page')
            url = f"{self.base_url}?locale={self.locale}&p={page}"
            self.driver.get(url)
            
            # Wait for body text to be present
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: d.find_element("tag name", "body").text.strip()
            )
            
            pre_element = self.driver.find_element("tag name", "pre")
            json_text = pre_element.text
            return json.loads(json_text)
            
        except TimeoutException:
            self.logger.error(f"Timeout fetching page {page}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching page {page}: {e}")
            return None

    def extract_urls_from_results(self, data: Dict) -> List[str]:
        """
        Extract URLs from API response
        
        Args:
            data: API response data
            
        Returns:
            List of URLs
        """
        if not data:
            self.logger.warning("extract_urls_from_results: Received empty or None data")
            return []
        
        results = data.get('results', {})
        if not results or not isinstance(results, dict):
            self.logger.warning("extract_urls_from_results: 'results' key not found or is not a dict")
            return []
        
        documents = results.get('document', [])
        if not documents:
            self.logger.warning("extract_urls_from_results: No documents found in results")
            return []
        
        urls = []
        try:
            for document in documents:
                # URL is in the 'source' field
                url = document.get('source')
                if url:
                    urls.append(url)
                        
        except Exception as e:
            self.logger.error(f"Error extracting URLs: {e}")
        
        self.logger.info(f"extract_urls_from_results: Extracted {len(urls)} URLs")
        return urls
    
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
