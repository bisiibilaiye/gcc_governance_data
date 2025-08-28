"""
Oman Scraper using Concurrent Base Architecture
"""
from typing import List, Optional
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import Company, CompanyDetails, BoardMember
from utils import ConfigManager, BrowserManager


class OmanScraper(BaseScraper):
    """Muscat Securities Market (MSX) scraper with multi-page pagination support.
    
    Features:
    - Advanced pagination with disabled state detection
    - Profile page parameter appending (&se=2)
    - Company details extraction from configured XPath selectors
    - Board member hierarchy extraction from structured lists
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('oman', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
        self.companies_url = self.config['exchange']['companies_url']
        # Store company data for later reference
        self.companies_data = []
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs with pagination handling"""
        self.logger.info(f"Extracting company URLs from {self.companies_url}")
        
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
        """Extract URLs using specific browser manager with pagination"""
        try:
            browser_manager.navigate_to(self.companies_url)
            
            all_company_info = []
            
            # Process all pages
            while True:
                page_companies = self._get_company_info_from_page(browser_manager)
                all_company_info.extend(page_companies)
                
                if self._is_last_page(browser_manager):
                    break
                    
                self._click_next_page(browser_manager)
                time.sleep(self.config.get('navigation', {}).get('pagination_wait', 5))
            
            # Store company data for later use
            self.companies_data = all_company_info
            urls = [comp["url"] for comp in all_company_info if comp["url"]]
            
            self.logger.info(f"Found {len(urls)} company URLs across all pages")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error extracting company URLs: {e}")
            return []
    
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information"""
        try:
            # Find company data from stored info
            company_data = None
            for comp in self.companies_data:
                if comp['url'] == url:
                    company_data = comp
                    break
                    
            if not company_data:
                self.logger.warning(f"Could not find company data for {url}")
                return None
                
            return Company(
                symbol=company_data['symbol'],
                name=company_data['name'],
                exchange=self.exchange_name
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company info from {url}: {e}")
            return None
    
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company profile information"""
        try:
            # Find company data
            company_data = None
            for comp in self.companies_data:
                if comp['url'] == url:
                    company_data = comp
                    break
                    
            if not company_data:
                return None
            
            # Navigate to profile page with &se=2 parameter
            profile_url = url + "&se=2"
            browser_manager.navigate_to(profile_url)
            time.sleep(10)
            
            # Extract profile information using configured selectors
            profile_selectors = self.config.get('selectors', {}).get('profile_selectors', {})
            
            profile_data = {}
            for field, xpath in profile_selectors.items():
                try:
                    element = browser_manager.driver.find_element(By.XPATH, xpath)
                    profile_data[field] = element.text.strip()
                except Exception:
                    profile_data[field] = None
                    
            return CompanyDetails(
                symbol=company_data['symbol'],
                company_name=company_data['name'],
                exchange=self.exchange_name,
                sub_sector=profile_data.get('sub_sector'),
                commercial_id=profile_data.get('commercial_id'),
                activity=profile_data.get('activity'),
                establishment_date=profile_data.get('established_in'),
                auditor=profile_data.get('auditor'),
                # Oman doesn't provide these fields
                incorporation_date=None,
                share_capital=None,
                company_type=None,
                fiscal_year_end=None,
                registrar=None
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company details from {url}: {e}")
            return None
    
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board member information"""
        board_members = []
        
        try:
            # Find company data
            company_data = None
            for comp in self.companies_data:
                if comp['url'] == url:
                    company_data = comp
                    break
                    
            if not company_data:
                self.logger.warning(f"Could not find company data for {url}")
                return []
            
            # Navigate to profile page
            profile_url = url + "&se=2"
            browser_manager.navigate_to(profile_url)
            time.sleep(5)
            
            # Extract board information
            board_section_xpath = self.config.get('selectors', {}).get('board_section', '')
            
            try:
                board_section = browser_manager.driver.find_element(By.XPATH, board_section_xpath)
                positions = board_section.find_elements(By.XPATH, ".//li")
                
                for position in positions:
                    try:
                        designation_element = position.find_element(By.XPATH, "./span")
                        name_element = position.find_element(By.XPATH, "./p/span")
                        
                        designation = designation_element.text.strip()
                        name = name_element.text.strip()
                        
                        if designation and name:
                            board_members.append(BoardMember(
                                company_symbol=company_data['symbol'],
                                company_name=company_data['name'],
                                exchange=self.exchange_name,
                                name=name,
                                position=designation,
                                designation=None,
                                member_type=None,
                                role_category="Board",
                                comments=None
                            ))
                            
                    except Exception as e:
                        self.logger.warning(f"Error processing board position: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"Error extracting board info for {company_data['name']}: {e}")
                
        except Exception as e:
            self.logger.error(f"Error processing {url}: {e}")
            
        return board_members
    
    def _get_company_info_from_page(self, browser_manager: BrowserManager) -> List[dict]:
        """Extract company information from current page"""
        company_info_list = []
        
        try:
            companies_xpath = self.config.get('selectors', {}).get('companies_grid', '')
            rows = browser_manager.driver.find_elements(By.XPATH, companies_xpath)
            
            for row in rows:
                try:
                    symbol_element = row.find_element(By.XPATH, ".//td[1]/a")
                    name_element = row.find_element(By.XPATH, ".//td[2]/a")
                    
                    symbol = symbol_element.text.strip()
                    name = name_element.text.strip()
                    url = symbol_element.get_attribute("href").strip()
                    
                    company_info_list.append({
                        "symbol": symbol,
                        "name": name,
                        "url": url
                    })
                    
                except Exception as e:
                    self.logger.warning(f"Error extracting company from row: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error extracting companies from page: {e}")
            
        return company_info_list
    
    def _is_last_page(self, browser_manager: BrowserManager) -> bool:
        """Check if current page is the last page"""
        try:
            next_button_xpath = self.config.get('selectors', {}).get('next_button', '')
            next_button = browser_manager.driver.find_element(By.XPATH, next_button_xpath)
            
            disabled_class = self.config.get('selectors', {}).get('disabled_class', 'k-state-disabled')
            return disabled_class in next_button.get_attribute("class")
            
        except Exception:
            return True  # Assume last page if button not found
    
    def _click_next_page(self, browser_manager: BrowserManager) -> bool:
        """Click the next page button"""
        try:
            next_button_xpath = self.config.get('selectors', {}).get('next_button', '')
            next_button = WebDriverWait(browser_manager.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, next_button_xpath))
            )
            
            browser_manager.scroll_to_element(next_button)
            next_button.click()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to click next page button: {e}")
            return False