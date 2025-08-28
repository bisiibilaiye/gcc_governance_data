"""
ADX Scraper using Concurrent Base Architecture
"""
from typing import List, Optional
import time
from urllib.parse import urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import Company, CompanyDetails, BoardMember
from utils import ConfigManager, BrowserManager


class ADXScraper(BaseScraper):
    """Abu Dhabi Securities Exchange (ADX) scraper with infinite scroll handling.
    
    Features:
    - Dynamic infinite scroll content loading
    - Multiple scrolling strategies for robust data extraction
    - Board members and executive extraction
    - Skeleton loading detection and handling
    - Symbol extraction from URL parameters
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('adx', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
        self.listing_url = self.config['exchange']['listing_url']
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs with improved scroll handling"""
        self.logger.info(f"Extracting company URLs from {self.listing_url}")
        
        # Use first browser from pool for URL extraction
        if not self.browser_managers:
            temp_browser = BrowserManager(self.config)
            temp_browser.__enter__()
            try:
                return self._extract_urls_with_browser(temp_browser)
            finally:
                temp_browser.__exit__(None, None, None)
        else:
            return self._extract_urls_with_browser(self.browser_managers[0])
    
    def _extract_urls_with_browser(self, browser_manager: BrowserManager) -> List[str]:
        """Extract URLs using specific browser manager with scrolling"""
        try:
            browser_manager.navigate_to(self.listing_url)
            
            # Wait for initial content load
            browser_manager.wait_for_element(By.CLASS_NAME, "css-zvi4ix", timeout=30)
            
            urls = set()
            scroll_count = 0
            last_url_count = 0
            max_scroll_attempts = self.config.get('navigation', {}).get('max_scroll_attempts', 15)
            scroll_wait_time = self.config.get('navigation', {}).get('scroll_wait_time', 3)
            
            while scroll_count < max_scroll_attempts:
                # Extract URLs using configured selector
                selector = self.config.get('selectors', {}).get('company_cards')
                elements = browser_manager.driver.find_elements(By.XPATH, selector)
                
                for element in elements:
                    url = element.get_attribute("href")
                    if url:
                        urls.add(url)
                        
                # Check if we found new URLs
                if len(urls) == last_url_count:
                    scroll_count += 1
                else:
                    scroll_count = 0
                    last_url_count = len(urls)
                    
                # Apply scrolling strategies from config
                strategies = self.config.get('navigation', {}).get('scroll_strategies', [])
                if strategies:
                    strategy_index = scroll_count % len(strategies)
                    scroll_script = strategies[strategy_index]
                    browser_manager.driver.execute_script(scroll_script)
                else:
                    # Default scroll
                    browser_manager.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    
                time.sleep(scroll_wait_time)
                
            self.logger.info(f"Found {len(urls)} company URLs")
            return list(urls)
            
        except Exception as e:
            self.logger.error(f"Error extracting company URLs: {e}")
            return []
    
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information from company URL"""
        try:
            browser_manager.navigate_to(url)
            
            # Extract symbol from URL
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            symbol = query_params.get("symbols", ["Unknown"])[0]
            
            # Extract company name and sector using configured selectors
            company_name = self._extract_text_with_selectors(browser_manager, 'company_name')
            sector = self._extract_text_with_selectors(browser_manager, 'sector')
            
            if not company_name:
                self.logger.warning(f"Could not extract company name from {url}")
                return None
                
            return Company(
                symbol=symbol,
                name=company_name,
                exchange=self.exchange_name,
                sector=sector
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company info from {url}: {e}")
            return None
    
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company profile information"""
        try:
            browser_manager.navigate_to(url)
            
            # Wait for page content to load
            time.sleep(3)
            
            # Wait for skeleton loading to disappear
            try:
                WebDriverWait(browser_manager.driver, 15).until_not(
                    EC.presence_of_element_located((By.CLASS_NAME, "react-loading-skeleton"))
                )
            except TimeoutException:
                self.logger.warning("Skeleton loading timeout on overview page - proceeding with extraction")
            
            # Wait for the overview content section to load
            try:
                WebDriverWait(browser_manager.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/main/div/div[6]/div/div/div/div/div[2]"))
                )
                self.logger.info("Overview content section detected")
            except TimeoutException:
                self.logger.warning("Overview content section not detected - proceeding anyway")
            
            # Additional wait for dynamic content
            time.sleep(2)
            
            # Extract symbol and name for reference
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            symbol = query_params.get("symbols", ["Unknown"])[0]
            
            company_name = self._extract_text_with_selectors(browser_manager, 'company_name')
            if not company_name:
                self.logger.warning(f"Could not extract company name from {url}")
                return None
                
            # Extract overview fields using configured selectors
            details = CompanyDetails(
                symbol=symbol,
                company_name=company_name,
                exchange=self.exchange_name,
                incorporation_date=self._extract_text_with_selectors(browser_manager, 'incorporation'),
                share_capital=self._extract_text_with_selectors(browser_manager, 'share_capital'),
                company_type=self._extract_text_with_selectors(browser_manager, 'company_type'),
                auditor=self._extract_text_with_selectors(browser_manager, 'auditor'),
                # ADX doesn't provide these fields
                establishment_date=None,
                fiscal_year_end=None,
                registrar=None,
                commercial_id=None,
                activity=None,
                sub_sector=None
            )
            
            return details
            
        except Exception as e:
            self.logger.error(f"Error extracting company details from {url}: {e}")
            return None
    
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members and executives information"""
        board_members = []
        
        try:
            # Extract basic company info for reference
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            symbol = query_params.get("symbols", ["Unknown"])[0]
            sec_code = query_params.get("secCode", [symbol])[0]
            
            # Navigate to overview first to get company name
            browser_manager.navigate_to(url)
            company_name = self._extract_text_with_selectors(browser_manager, 'company_name')
            if not company_name:
                self.logger.warning(f"Could not extract company name for board members from {url}")
                return []
                
            # Navigate directly to shareholders and board page
            shareholders_url = f"{self.base_url}/main-market/company-profile/shareholder-and-board?symbols={symbol}&secCode={sec_code}"
            self.logger.info(f"Navigating to shareholders page: {shareholders_url}")
            browser_manager.navigate_to(shareholders_url)
            
            # Check if there are tabs to navigate - some companies have separate board tab
            try:
                # Look for tabs or buttons that might lead to board members
                board_tab_selectors = [
                    "//button[contains(text(), 'Board')]",
                    "//button[contains(text(), 'BOARD')]", 
                    "//a[contains(text(), 'Board')]",
                    "//a[contains(text(), 'BOARD')]",
                    "//div[contains(@class, 'tab')][contains(text(), 'Board')]",
                    "//div[contains(@class, 'tab')][contains(text(), 'BOARD')]"
                ]
                
                board_tab_found = False
                for tab_selector in board_tab_selectors:
                    try:
                        tab_element = browser_manager.driver.find_element(By.XPATH, tab_selector)
                        if tab_element and tab_element.is_displayed():
                            self.logger.info(f"Clicking board tab: {tab_selector}")
                            tab_element.click()
                            time.sleep(3)
                            board_tab_found = True
                            break
                    except:
                        continue
                        
                if not board_tab_found:
                    self.logger.info("No separate board tab found, proceeding with current page")
                        
            except Exception as e:
                self.logger.warning(f"Error checking for board tabs: {e}")
            
            # Wait for content to load
            time.sleep(5)
            
            # Wait for skeleton loading to disappear
            try:
                WebDriverWait(browser_manager.driver, 20).until_not(
                    EC.presence_of_element_located((By.CLASS_NAME, "react-loading-skeleton"))
                )
            except TimeoutException:
                self.logger.warning("Skeleton loading timeout - proceeding with extraction")
                
            # Wait for content to appear (either financial cards or other content)
            try:
                WebDriverWait(browser_manager.driver, 15).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "financial-report_card")),
                        EC.presence_of_element_located((By.CLASS_NAME, "table")),
                        EC.presence_of_element_located((By.TAG_NAME, "main"))
                    )
                )
                self.logger.info("Page content detected")
            except TimeoutException:
                self.logger.warning("Page content not detected - proceeding anyway")
                
            # Additional wait for dynamic content
            time.sleep(3)
                
            # Extract board data from the specific section
            board_data = self._extract_board_data_from_shareholders_page(browser_manager, symbol, company_name)
            
            # Add extracted board members to the list
            board_members.extend(board_data)
                
        except Exception as e:
            self.logger.error(f"Error extracting board members from {url}: {e}")
            
        return board_members
    
    def _extract_text_with_selectors(self, browser_manager: BrowserManager, selector_key: str) -> str:
        """Extract text using multiple selector fallbacks and BeautifulSoup approach"""
        selectors = self.config.get('selectors', {}).get(selector_key, [])
        
        # First try xpath selectors
        for selector in selectors:
            try:
                element = browser_manager.driver.find_element(By.XPATH, selector)
                text = element.text.strip()
                if text:
                    return text
            except:
                continue
        
        # If xpath selectors fail, try BeautifulSoup approach like the old working code
        try:
            page_source = browser_manager.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            
            # Map selector keys to text patterns
            text_patterns = {
                'listing_date': ['listing date', 'LISTING DATE'],
                'incorporation': ['incorporation', 'INCORPORATION'],
                'share_capital': ['share capital', 'SHARE CAPITAL'],
                'company_type': ['company type', 'COMPANY TYPE'],
                'auditor': ['auditor', 'AUDITOR']
            }
            
            patterns = text_patterns.get(selector_key, [])
            for pattern in patterns:
                # Find span with the pattern text
                span_element = soup.find("span", string=pattern)
                if span_element:
                    # Get the next sibling span that contains the value
                    next_span = span_element.find_next_sibling("span")
                    if next_span:
                        text = next_span.get_text(strip=True)
                        if text:
                            self.logger.info(f"Found {selector_key} using BeautifulSoup pattern '{pattern}': {text}")
                            return text
                
                # Alternative: Look for any element containing the pattern text, then find siblings
                pattern_element = soup.find(text=lambda text: text and pattern in text.lower())
                if pattern_element:
                    parent = pattern_element.parent
                    if parent:
                        # Look for sibling elements that might contain the value
                        for sibling in parent.find_next_siblings():
                            text = sibling.get_text(strip=True)
                            if text and len(text) > 1:  # Avoid empty or single character texts
                                self.logger.info(f"Found {selector_key} using text pattern '{pattern}': {text}")
                                return text
                        
                        # Also check within parent for nested structure
                        siblings = parent.find_all()
                        for i, elem in enumerate(siblings):
                            if pattern.lower() in elem.get_text().lower():
                                # Look for the value in the next element
                                if i + 1 < len(siblings):
                                    text = siblings[i + 1].get_text(strip=True)
                                    if text and len(text) > 1:
                                        self.logger.info(f"Found {selector_key} using nested pattern '{pattern}': {text}")
                                        return text
        
        except Exception as e:
            self.logger.warning(f"Error in BeautifulSoup extraction for {selector_key}: {e}")
                
        return ""
    
    def _extract_board_data_from_shareholders_page(self, browser_manager: BrowserManager, symbol: str, company_name: str) -> List[BoardMember]:
        """Extract board members from the shareholders and board page"""
        board_members = []
        
        try:
            # Additional wait for all content to load
            time.sleep(3)
            
            # Scroll down to ensure all content is loaded
            browser_manager.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Scroll back up to the board section
            browser_manager.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
            time.sleep(2)
            
            # Try multiple approaches to get the board content
            board_section = None
            used_selector = None
            
            # First, try to get the container that holds all financial report cards
            container_selectors = [
                "/html/body/div[1]/div[1]/main/div/div[6]/div/div/div/div[1]/div",  # Original provided - try first
                "//div[contains(@class, 'shareholders-board_content')]",
                "//div[contains(@class, 'financial-report_content')]", 
                "//main//div[6]//div//div//div[1]//div",  # More specific to the board section
                "//main//div[contains(@class, 'row')]//div[contains(@class, 'col')]",  # Bootstrap grid
                "//main//div[6]//div//div//div",  # More flexible main content
            ]
            
            for selector in container_selectors:
                try:
                    board_section = WebDriverWait(browser_manager.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    used_selector = selector
                    self.logger.info(f"Found board container using selector: {selector}")
                    break
                except:
                    continue
                    
            if not board_section:
                # Try to get the entire page content as fallback
                self.logger.warning("Could not find specific board section, extracting from entire page")
                board_section = browser_manager.driver.find_element(By.TAG_NAME, "body")
                used_selector = "body"
            
            # Get HTML content
            html_content = board_section.get_attribute("outerHTML")
            soup = BeautifulSoup(html_content, "html.parser")
            
            self.logger.info(f"HTML content length: {len(html_content)}")
            
            # Debug: Save HTML content to file for inspection
            try:
                debug_file = f"debug_adx_{symbol}_board.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info(f"Debug: HTML content saved to {debug_file}")
                
                # Also save full page HTML for comparison
                full_page_html = browser_manager.driver.page_source
                debug_full_file = f"debug_adx_{symbol}_full_page.html"
                with open(debug_full_file, 'w', encoding='utf-8') as f:
                    f.write(full_page_html)
                self.logger.info(f"Debug: Full page HTML saved to {debug_full_file}")
                
            except Exception as e:
                self.logger.warning(f"Could not save debug HTML: {e}")
            
            # ADX specific extraction - look for financial-report_card structure
            board_cards = soup.find_all("div", class_="financial-report_card")
            self.logger.info(f"Found {len(board_cards)} financial-report_card elements")
            
            if board_cards:
                # Extract from structured cards
                for card in board_cards:
                    try:
                        # Get position from span within badge
                        position_span = card.find("span")
                        position = position_span.get_text(strip=True) if position_span else "Board Member"
                        
                        # Get name from p tag
                        name_p = card.find("p")
                        name = name_p.get_text(strip=True) if name_p else None
                        
                        if name and name.strip():
                            board_members.append(BoardMember(
                                company_symbol=symbol,
                                company_name=company_name,
                                exchange=self.exchange_name,
                                name=name,
                                position=position,
                                designation=None,
                                member_type=None,
                                role_category="Board",
                                comments=f"Extracted from financial-report_card"
                            ))
                            
                    except Exception as e:
                        self.logger.warning(f"Error processing board member card: {e}")
                        continue
            
            else:
                # Fallback: Try to find structured data using other methods
                self.logger.info("No financial-report_card found, trying alternative extraction")
                
                # Method 0: Look for different card structures that might contain board info
                alternative_card_selectors = [
                    "div[class*='card']",
                    "div[class*='member']", 
                    "div[class*='director']",
                    "div[class*='board']",
                    "div[class*='profile']"
                ]
                
                for card_selector in alternative_card_selectors:
                    cards = soup.select(card_selector)
                    if cards:
                        self.logger.info(f"Found {len(cards)} potential cards with selector: {card_selector}")
                        for card in cards[:10]:  # Limit to avoid noise
                            text_content = card.get_text(strip=True)
                            if text_content and 10 < len(text_content) < 200:
                                # Look for name-like patterns
                                lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                                for line in lines:
                                    # Check if this looks like a person's name
                                    words = line.split()
                                    if (2 <= len(words) <= 6 and 
                                        sum(1 for word in words if word[0].isupper()) >= 2 and
                                        not any(keyword in line.lower() for keyword in 
                                               ['click', 'view', 'download', 'percentage', 'electronic', 'certified'])):
                                        
                                        # Try to extract position from surrounding context
                                        position = "Board Member"
                                        card_html = str(card)
                                        position_keywords = ['chairman', 'vice', 'director', 'member', 'ceo', 'president', 'manager']
                                        for keyword in position_keywords:
                                            if keyword in card_html.lower():
                                                # Extract the specific position
                                                for check_line in lines:
                                                    if keyword in check_line.lower() and check_line != line:
                                                        position = check_line.strip()
                                                        break
                                                break
                                        
                                        board_members.append(BoardMember(
                                            company_symbol=symbol,
                                            company_name=company_name,
                                            exchange=self.exchange_name,
                                            name=line,
                                            position=position,
                                            designation=None,
                                            member_type=None,
                                            role_category="Board",
                                            comments=f"Extracted from {card_selector}"
                                        ))
                                        
                                        if len(board_members) >= 15:
                                            break
                            
                            if len(board_members) >= 15:
                                break
                    
                    if board_members:
                        break  # Found some members, stop trying other selectors
                
                # Method 1: Look for div elements that might contain member info
                all_divs = soup.find_all("div")
                potential_members = []
                
                for div in all_divs:
                    text = div.get_text(strip=True)
                    if text and 10 < len(text) < 200:  # Reasonable length for member info
                        # Check if contains person-like information
                        words = text.split()
                        if (len(words) >= 2 and 
                            any(word[0].isupper() for word in words[:3]) and  # Has capitalized words
                            not text.lower().startswith(('the ', 'this ', 'that ', 'click ', 'view '))):  # Not UI text
                            potential_members.append(text)
                
                self.logger.info(f"Found {len(potential_members)} potential member texts")
                
                # Method 2: Look for specific patterns
                position_keywords = [
                    'chairman', 'director', 'member', 'ceo', 'president', 'manager',
                    'vice', 'deputy', 'board', 'executive', 'independent', 'chief'
                ]
                
                # Extract structured information
                for text in potential_members[:20]:  # Limit to first 20 to avoid noise
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    
                    for line in lines:
                        # Skip obviously non-name lines
                        if (len(line.split()) < 2 or 
                            line.lower().startswith(('www.', 'http', 'email', 'phone', 'fax')) or
                            any(char.isdigit() for char in line[:5]) or  # Starts with numbers
                            len(line) > 100):  # Too long
                            continue
                        
                        words = line.split()
                        # Look for name-like patterns
                        if (len(words) >= 2 and len(words) <= 6 and
                            all(word[0].isupper() for word in words[:2]) and  # First two words capitalized
                            not any(keyword in line.lower() for keyword in position_keywords)):  # Not a position
                            
                            # This looks like a name
                            name = line
                            position = "Board Member"  # Default
                            
                            # Look for position in the same text block
                            for other_line in lines:
                                if (other_line != line and 
                                    any(keyword in other_line.lower() for keyword in position_keywords)):
                                    position = other_line.strip()
                                    break
                            
                            board_members.append(BoardMember(
                                company_symbol=symbol,
                                company_name=company_name,
                                exchange=self.exchange_name,
                                name=name,
                                position=position,
                                designation=None,
                                member_type=None,
                                role_category="Board",
                                comments=f"Extracted using selector: {used_selector}"
                            ))
                            
                            if len(board_members) >= 15:  # Reasonable limit
                                break
                    
                    if len(board_members) >= 15:
                        break
            
            # Method 3: If still no results, try a more aggressive text extraction
            if not board_members:
                all_text = soup.get_text()
                self.logger.info(f"Full page text length: {len(all_text)}")
                
                # Look for common name patterns in the full text
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                
                for line in lines:
                    # More aggressive name detection
                    words = line.split()
                    if (3 <= len(words) <= 6 and
                        sum(1 for word in words if word[0].isupper()) >= 2 and  # At least 2 capitalized
                        not any(bad in line.lower() for bad in ['click', 'view', 'download', 'contact', 'email', 'phone'])):
                        
                        board_members.append(BoardMember(
                            company_symbol=symbol,
                            company_name=company_name,
                            exchange=self.exchange_name,
                            name=line,
                            position="Board Member",
                            designation=None,
                            member_type=None,
                            role_category="Board",
                            comments="Extracted from full text"
                        ))
                        
                        if len(board_members) >= 10:
                            break
            
            # Remove duplicates based on name
            seen_names = set()
            unique_members = []
            for member in board_members:
                if member.name not in seen_names:
                    seen_names.add(member.name)
                    unique_members.append(member)
            
            self.logger.info(f"Extracted {len(unique_members)} unique board members for {symbol}")
            return unique_members
            
        except Exception as e:
            self.logger.error(f"Error extracting board data from shareholders page: {e}")
            return []
    
    def _extract_board_data(self, browser_manager: BrowserManager) -> dict:
        """Legacy method - kept for compatibility"""
        return {"board_members": [], "executives": []}
    
    def _translate_if_needed(self, text: str) -> str:
        """Placeholder for translation if needed - returns original text"""
        return text