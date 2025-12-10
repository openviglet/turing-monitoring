"""
Checker Service - Manages URL checking operations
"""

import time
import queue
import logging
import warnings
from datetime import datetime
from threading import Thread
from ..checker import URLChecker

# Suppress urllib3 connection pool warnings
warnings.filterwarnings('ignore', message='Connection pool is full')
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)


# Global singleton instance to survive Streamlit reruns
_checker_service_instance = None


class CheckerService:
    """Service for managing URL checking operations"""
    
    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)"""
        global _checker_service_instance
        if _checker_service_instance is None:
            _checker_service_instance = super(CheckerService, cls).__new__(cls)
            _checker_service_instance._initialized = False
        return _checker_service_instance
    
    def __init__(self):
        # Only initialize once
        if self._initialized:
            return
        
        self.status_queue = queue.Queue()
        self.checker = None
        self.stop_requested = False
        self.check_thread = None
        self._initialized = True
        print("🔧 CheckerService singleton initialized")
    
    def start_check(self, config):
        """Start URL checking in background thread"""
        if self.is_running():
            raise RuntimeError("Checker is already running")
        
        self.stop_requested = False
        self.check_thread = Thread(target=self._run_check, args=(config,))
        self.check_thread.daemon = False  # Non-daemon to survive session changes
        self.check_thread.start()
    
    def stop_check(self):
        """Stop URL checking"""
        self.stop_requested = True
        
        # Give threads time to finish current operations
        time.sleep(0.2)
        
        if self.checker:
            try:
                # Close all browsers immediately to stop operations
                if hasattr(self.checker, 'worker_drivers'):
                    for driver in self.checker.worker_drivers:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                    self.checker.worker_drivers.clear()
                
                if hasattr(self.checker, 'driver') and self.checker.driver:
                    try:
                        self.checker.driver.quit()
                    except Exception:
                        pass
                    self.checker.driver = None
            except Exception:
                pass
        
        # Wait for thread to finish
        if self.check_thread and self.check_thread.is_alive():
            self.check_thread.join(timeout=2.0)
    
    def is_running(self):
        """Check if checker is currently running"""
        return self.check_thread is not None and self.check_thread.is_alive()
    
    def get_updates(self, max_updates=10):
        """Get updates from queue (non-blocking)"""
        updates = []
        try:
            for _ in range(max_updates):
                update = self.status_queue.get(timeout=0.01)
                updates.append(update)
        except queue.Empty:
            pass
        return updates
    
    def _run_check(self, config):
        """Internal method to run check (runs in background thread)"""
        try:
            # Create checker with config
            self.checker = URLChecker(
                base_url=config['base_url'],
                locale=config['locale'],
                page_load_timeout=config['page_load_timeout'],
                element_wait_timeout=config['element_wait_timeout'],
                headless=config['headless'],
                max_attempts=config['max_attempts'],
                retry_delay=config['retry_delay'],
                page_delay=config['page_delay'],
                url_check_delay=config['url_check_delay'],
                disable_images=config['disable_images'],
                parallel_browsers=config['parallel_browsers'],
                error_status_codes=config.get('error_status_codes', [404]),
                resume_from_checkpoint=config.get('resume_from_checkpoint', True)
            )
            
            # Monkey patch to send updates to queue
            original_check = self.checker._check_url_with_driver
            original_fetch = self.checker.fetch_page
            
            def monitored_check(driver, url, page, attempt=1):
                if self.stop_requested:
                    raise KeyboardInterrupt("Stop requested by user")
                
                # Only send checking status for first attempt
                if attempt == 1:
                    self.status_queue.put({
                        'type': 'checking',
                        'url': url,
                        'page': page,
                        'attempt': attempt,
                        'timestamp': datetime.now()
                    })
                
                start_time = time.time()
                result = original_check(driver, url, page, attempt)
                response_time = time.time() - start_time
                
                # Only send result if this is the FINAL attempt
                if attempt == result['attempts']:
                    self.status_queue.put({
                        'type': 'result',
                        'url': url,
                        'status': result['status_code'],
                        'page': page,
                        'attempts': result['attempts'],
                        'response_time': response_time,
                        'timestamp': datetime.now()
                    })
                
                return result
            
            def monitored_fetch(page):
                if self.stop_requested:
                    raise KeyboardInterrupt("Stop requested by user")
                
                result = original_fetch(page)
                
                if result:
                    try:
                        pagination = result.get('queryContext', {})
                        self.status_queue.put({
                            'type': 'page_update',
                            'page': pagination.get('page', page),
                            'total_pages': pagination.get('pageCount', 0),
                            'total_urls': pagination.get('count', 0),
                            'timestamp': datetime.now()
                        })
                    except:
                        self.status_queue.put({
                            'type': 'page_update',
                            'page': page,
                            'total_pages': 0,
                            'total_urls': 0,
                            'timestamp': datetime.now()
                        })
                
                return result
            
            self.checker._check_url_with_driver = monitored_check
            self.checker.fetch_page = monitored_fetch
            
            # Run check
            failed_urls = self.checker.run()
            
            if not self.stop_requested:
                self.status_queue.put({
                    'type': 'complete',
                    'total_checked': self.checker.total_urls_checked,
                    'total_failed': len(failed_urls),
                    'failed_urls': failed_urls
                })
            else:
                self.status_queue.put({
                    'type': 'stopped',
                    'total_checked': self.checker.total_urls_checked,
                    'total_failed': len(self.checker.failed_urls)
                })
            
        except KeyboardInterrupt:
            self.status_queue.put({
                'type': 'stopped',
                'total_checked': self.checker.total_urls_checked if self.checker else 0,
                'total_failed': len(self.checker.failed_urls) if self.checker else 0
            })
        except Exception as e:
            if not self.stop_requested:
                self.status_queue.put({
                    'type': 'error',
                    'error': str(e)
                })
        finally:
            self.check_thread = None
