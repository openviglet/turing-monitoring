"""
Model JSON URL checker plugin - simplified version
"""
import logging
from typing import List
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException
from .base_checker import BaseCheckerPlugin

class ModelJsonChecker(BaseCheckerPlugin):
    """
    Model json checker plugin that checks .model.json URLs.
    """
    def __init__(self, error_status_codes: List[int], logger: logging.Logger):
        self.error_status_codes = error_status_codes
        self.logger = logger

    def check(self, driver: WebDriver, url: str) -> dict:
        """
        Check a single URL by appending .model.json and getting HTTP status.
        """

        model_json_url = url.removesuffix(".html") + ".model.json"
        
        try:
            # Navigate to URL
            driver.get(model_json_url)
            
            # Get HTTP status via JavaScript
            status = driver.execute_script("""
                var xhr = new XMLHttpRequest();
                xhr.open('HEAD', window.location.href, false);
                try {
                    xhr.send();
                    return xhr.status;
                } catch (e) {
                    return 0;
                }
            """)
            
            # If JavaScript returns 0 or undefined, try getting from performance API
            if not status or status == 0:
                status = driver.execute_script("""
                    var perfEntries = performance.getEntriesByType('navigation');
                    if (perfEntries.length > 0) {
                        return perfEntries[0].responseStatus || 200;
                    }
                    return 200;
                """)
            
            return {'status_code': status}

        except TimeoutException:
            self.logger.warning(f"Timeout accessing {model_json_url}")
            return {'status_code': -1, 'error': 'Timeout'}
        except Exception as e:
            self.logger.error(f"Error checking {model_json_url}: {e}")
            return {'status_code': -1, 'error': str(e)}
