"""
Streamlit URL Checker - Main checking logic with queue-based updates
"""

import time
import queue
from datetime import datetime
from ..checker import URLChecker


class StreamlitURLChecker:
    """URL Checker with Streamlit UI and real-time updates"""
    
    def __init__(self):
        self.status_queue = queue.Queue()
        self.checker = None
        self.stop_requested = False
        
    def stop(self):
        """Request stop of checker"""
        self.stop_requested = True
        if self.checker:
            try:
                # Close all browsers immediately
                if hasattr(self.checker, 'driver') and self.checker.driver:
                    self.checker.driver.quit()
                if hasattr(self.checker, 'worker_drivers'):
                    for driver in self.checker.worker_drivers:
                        try:
                            driver.quit()
                        except:
                            pass
            except:
                pass
        
    def run_check(self, config):
        """Run URL check in background thread"""
        try:
            self.stop_requested = False
            
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
                resume_from_checkpoint=config.get('resume_from_checkpoint', True),
                plugin_name=config.get('plugin_name', 'default_checker'),
                skip_driver_version_check=config.get('skip_driver_version_check', False)
            )
            
            # Monkey patch to send updates to queue and check stop
            original_check = self.checker._check_url_with_driver
            original_fetch = self.checker.fetch_page
            
            def monitored_check(driver, url, page, attempt=1):
                # Check if stop requested
                if self.stop_requested:
                    raise KeyboardInterrupt("Stop requested by user")
                
                # Only send checking status for first attempt to avoid spam
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
                
                # Only send result if this is the FINAL attempt (no more retries)
                # This prevents counting the same failure multiple times
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
                # Check if stop requested
                if self.stop_requested:
                    raise KeyboardInterrupt("Stop requested by user")
                
                # Call original fetch
                result = original_fetch(page)
                
                # Extract total pages from result
                if result:
                    try:
                        pagination = result.get('queryContext', {})
                        total_pages = pagination.get('pageCount', 0)
                        current_page = pagination.get('page', page)
                        total_urls = pagination.get('count', 0)
                        
                        # Send page update with pagination info
                        self.status_queue.put({
                            'type': 'page_update',
                            'page': current_page,
                            'total_pages': total_pages,
                            'total_urls': total_urls,
                            'timestamp': datetime.now()
                        })
                    except:
                        # Fallback without pagination info
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
