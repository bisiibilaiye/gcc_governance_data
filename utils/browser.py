from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
try:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_4_PLUS = True
except ImportError:
    # For Selenium 3.x compatibility
    SELENIUM_4_PLUS = False
from typing import List, Optional, Dict, Any, Callable
import time
import logging
import threading
from contextlib import contextmanager


class BrowserManager:
    """Manages browser setup, configuration, and common operations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
    def __enter__(self):
        """Context manager entry."""
        self.setup_driver()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_driver()
        
    def setup_driver(self) -> webdriver.Chrome:
        """Initialize and configure Chrome driver with performance optimizations."""
        options = webdriver.ChromeOptions()
        
        # Apply browser configuration
        browser_config = self.config.get('browser', {})
        
        if browser_config.get('headless', True):
            if SELENIUM_4_PLUS:
                options.add_argument('--headless=new')
            else:
                options.add_argument('--headless')
            
        # Add window size
        window_size = browser_config.get('window_size', '1920,1080')
        options.add_argument(f'--window-size={window_size}')
        
        # Add user agent
        user_agent = browser_config.get('user_agent', '')
        if user_agent:
            options.add_argument(f'--user-agent={user_agent}')
            
        # Base performance optimizations (always applied)
        base_options = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-web-security',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-client-side-phishing-detection',
            '--disable-sync',
            '--disable-default-apps',
            '--disable-prompt-on-repost',
            '--disable-hang-monitor',
            '--disable-background-networking',
            '--metrics-recording-only',
            '--no-first-run',
            '--safebrowsing-disable-auto-update',
            '--enable-automation',
            '--password-store=basic',
            '--use-mock-keychain',
            '--no-default-browser-check',
        ]
        
        for option in base_options:
            options.add_argument(option)
            
        # Conditional performance optimizations (can be disabled per exchange)
        if browser_config.get('disable_images', True):
            options.add_argument('--disable-images')
            self.logger.debug("Images disabled for performance")
        
        if browser_config.get('disable_css', False):
            options.add_argument('--disable-css')
            self.logger.debug("CSS disabled for performance")
            
        # Note: JavaScript is NOT disabled by default anymore since many sites need it
            
        # Add Chrome options from config
        chrome_options = self.config.get('chrome_options', [])
        for option in chrome_options:
            options.add_argument(option)
            
        # Anti-detection settings
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Set page load strategy for faster loading
        options.page_load_strategy = 'eager'  # Don't wait for all resources
        
        # Configure logging
        options.add_argument('--log-level=3')  # Suppress INFO, WARNING, ERROR
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Setup driver based on Selenium version
        if SELENIUM_4_PLUS:
            service = Service(ChromeDriverManager().install())
            # Suppress service logs
            service.log_path = '/dev/null'
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            # Selenium 3.x compatibility
            self.driver = webdriver.Chrome(options=options)
        
        # Set timeouts for faster failure
        self.driver.set_page_load_timeout(30)  # 30 second page load timeout
        self.driver.implicitly_wait(5)  # 5 second implicit wait
        
        # Execute performance optimizations
        try:
            if SELENIUM_4_PLUS:
                # Hide webdriver property
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'
                })
                
                # Enable performance optimizations
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                
                # Disable images and CSS if configured
                if browser_config.get('disable_images', True):
                    self.driver.execute_cdp_cmd('Emulation.setDefaultBackgroundColorOverride', {'color': {'r': 255, 'g': 255, 'b': 255, 'a': 1}})
                    
        except Exception as e:
            self.logger.warning(f"Could not execute performance optimizations: {e}")
        
        self.logger.info("Optimized browser driver initialized successfully")
        return self.driver
        
    def close_driver(self):
        """Close the browser driver."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Browser driver closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
                
    def navigate_to(self, url: str, wait_seconds: Optional[int] = None):
        """Navigate to URL with optional wait time."""
        if not self.driver:
            raise RuntimeError("Driver not initialized. Call setup_driver() first.")
            
        self.logger.info(f"Navigating to: {url}")
        self.driver.get(url)
        
        # Wait for page load
        wait_time = wait_seconds or self.config.get('scraping', {}).get('page_load_wait', 5)
        time.sleep(wait_time)
        
    def find_element_with_retry(self, selectors: List[str], timeout: int = 10) -> Optional[str]:
        """Try multiple selectors with retry logic to find an element."""
        max_attempts = self.config.get('scraping', {}).get('max_retries', 3)
        
        for attempt in range(max_attempts):
            for selector in selectors:
                try:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    return element.get_attribute("textContent").strip()
                except (TimeoutException, NoSuchElementException):
                    continue
                    
            if attempt < max_attempts - 1:
                retry_delay = self.config.get('scraping', {}).get('retry_delay_seconds', 2)
                time.sleep(retry_delay)
                
        return None
        
    def wait_for_element(self, by: By, selector: str, timeout: Optional[int] = None):
        """Wait for an element to be present."""
        timeout = timeout or self.config.get('scraping', {}).get('default_timeout', 30)
        
        try:
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(EC.presence_of_element_located((by, selector)))
        except TimeoutException as e:
            self.logger.error(f"Element not found: {by}={selector}. Timeout after {timeout}s")
            raise
            
    def wait_for_elements(self, by: By, selector: str, timeout: Optional[int] = None):
        """Wait for multiple elements to be present."""
        timeout = timeout or self.config.get('scraping', {}).get('default_timeout', 20)
        
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_all_elements_located((by, selector)))
        
    def click_element_with_js(self, element):
        """Click element using JavaScript (more reliable for some elements)."""
        self.driver.execute_script("arguments[0].click();", element)
        
    def scroll_to_element(self, element):
        """Scroll element into view."""
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        
    def take_screenshot(self, filename: str):
        """Take a screenshot for debugging."""
        if self.driver:
            self.driver.save_screenshot(filename)
            self.logger.info(f"Screenshot saved: {filename}")
            
    def get_page_source(self) -> str:
        """Get current page source."""
        if self.driver:
            return self.driver.page_source
        return ""