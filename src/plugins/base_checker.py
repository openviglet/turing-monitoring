"""
Base class for checker plugins
"""
from abc import ABC, abstractmethod
from selenium.webdriver.chrome.webdriver import WebDriver

class BaseCheckerPlugin(ABC):
    """Abstract base class for URL checker plugins."""

    @abstractmethod
    def check(self, driver: WebDriver, url: str) -> dict:
        """
        Check a single URL.

        Args:
            driver: The Selenium WebDriver instance to use.
            url: The URL to check.

        Returns:
            A dictionary containing the check result.
            Expected keys: 'status_code', 'error' (optional).
        """
        pass
