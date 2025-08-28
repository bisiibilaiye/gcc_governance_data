"""
Saudi Scraper using Concurrent Base Architecture
"""
from typing import List, Optional
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import Company, CompanyDetails, BoardMember
from utils import ConfigManager, BrowserManager


class SaudiScraper(BaseScraper):
    """Saudi Exchange (Tadawul) scraper with concurrent processing and pagination support.
    
    Features:
    - Advanced pagination handling for multi-page company listings
    - Cookie consent automation
    - Concurrent browser pool processing
    - Management tab extraction for board members
    - Rate limiting for respectful scraping
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('saudi', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
        self.directory_url = self.config['exchange']['directory_url']
        # Store company data for later reference
        self.companies_data = {}
        self.company_urls = {}
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs using Selenium with pagination support"""
        self.logger.info(f"Extracting company URLs from {self.directory_url}")
        
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
            browser_manager.navigate_to(self.directory_url)
            
            # Initial wait and handle cookie consent
            time.sleep(self.config.get('navigation', {}).get('initial_wait', 10))
            self._handle_cookie_consent(browser_manager)
            
            # Find companies list with multiple selectors
            companies_found = False
            list_selector = None
            
            selectors = self.config.get('selectors', {}).get('company_list_selectors', [])
            for selector in selectors:
                companies_list = self._wait_and_find_elements(browser_manager, selector, timeout=30)
                
                if companies_list:
                    self.logger.info(f"Found {len(companies_list)} companies with selector: {selector}")
                    companies_found = True
                    list_selector = selector
                    break
            
            if not companies_found:
                self.logger.error("Could not find companies with any selector")
                return []
            
            # Extract URLs with pagination
            all_data = []
            all_company_urls = {}
            page = 1
            
            while True:
                self.logger.info(f"Scraping companies on page {page}...")
                
                # Re-query the company list to avoid stale elements
                companies_list = browser_manager.driver.find_elements(By.CSS_SELECTOR, list_selector)
                count = len(companies_list)
                self.logger.info(f"Found {count} companies on page {page}")
                
                # Process each company on current page
                for i in range(count):
                    try:
                        # Re-fetch to avoid stale references
                        companies_list = browser_manager.driver.find_elements(By.CSS_SELECTOR, list_selector)
                        li = companies_list[i]
                        
                        company_data = self._extract_company_data_from_element(li)
                        if company_data:
                            all_data.append(company_data)
                            if company_data.get('profile_url'):
                                all_company_urls[company_data['name']] = company_data['profile_url']
                                
                    except Exception as e:
                        self.logger.error(f"Error processing company at index {i}: {e}")
                        continue
                
                # Try pagination
                if not self._click_next_page(browser_manager, page):
                    break
                    
                page += 1
                time.sleep(self.config.get('navigation', {}).get('pagination_wait', 8))
            
            # Store data for later use
            self.companies_data = {data['name']: data for data in all_data}
            self.company_urls = all_company_urls
            
            urls = list(all_company_urls.values())
            self.logger.info(f"Total companies scraped: {len(urls)}")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error extracting company URLs: {e}")
            return []
    
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information"""
        try:
            # Find company data from stored info
            company_data = None
            company_name = None
            
            for name, stored_url in self.company_urls.items():
                if stored_url == url:
                    company_name = name
                    company_data = self.companies_data.get(name)
                    break
            
            if not company_data:
                self.logger.warning(f"Could not find company data for {url}")
                return None
                
            return Company(
                symbol=company_data.get('symbol', ''),
                name=company_data.get('name', ''),
                exchange=self.exchange_name,
                trading_name=company_data.get('trading_name', ''),
                isin=company_data.get('isin_code', '')
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company info from {url}: {e}")
            return None
    
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company profile information"""
        try:
            if not url:
                return None
                
            browser_manager.navigate_to(url)
            time.sleep(self.config.get('navigation', {}).get('profile_wait', 8))
            
            # Find profile container
            container = self._find_profile_container(browser_manager)
            if not container:
                return None
            
            # Extract company details
            company_details = self._extract_company_details_from_container(container)
            
            # Find company name from stored data
            company_name = None
            for name, stored_url in self.company_urls.items():
                if stored_url == url:
                    company_name = name
                    break
            
            if not company_name:
                return None
                
            return CompanyDetails(
                symbol=company_details.get('Symbol', ''),
                company_name=company_name,
                exchange=self.exchange_name,
                establishment_date=company_details.get('Date Established', ''),
                fiscal_year_end=company_details.get('Financial Year End', ''),
                auditor=company_details.get('External Auditors', ''),
                # Saudi doesn't provide these fields
                incorporation_date=None,
                commercial_id=None,
                activity=None,
                sub_sector=None,
                registrar=None,
                share_capital=None,
                company_type=None
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company details from {url}: {e}")
            return None
    
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members and management information"""
        board_members = []
        
        try:
            if not url:
                return []
                
            # Find company name
            company_name = None
            for name, stored_url in self.company_urls.items():
                if stored_url == url:
                    company_name = name
                    break
            
            if not company_name:
                return []
                
            browser_manager.navigate_to(url)
            time.sleep(self.config.get('navigation', {}).get('profile_wait', 8))
            
            # Find profile container
            container = self._find_profile_container(browser_manager)
            if not container:
                return []
            
            # Extract management details
            management_details = self._extract_management_details(browser_manager, container)
            
            # Convert to BoardMember objects
            for member in management_details:
                board_members.append(BoardMember(
                    company_symbol=company_name,
                    company_name=company_name,
                    exchange=self.exchange_name,
                    name=member['name'],
                    position=member['role'],
                    designation=member.get('designation', ''),
                    member_type=None,
                    role_category="Management",
                    comments=None
                ))
                
        except Exception as e:
            self.logger.error(f"Error extracting board members from {url}: {e}")
            
        return board_members
    
    def _handle_cookie_consent(self, browser_manager: BrowserManager):
        """Handle cookie consent popups"""
        try:
            cookie_buttons = browser_manager.driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Accept') or contains(text(), 'Agree') or contains(text(), 'OK') or contains(text(), 'I understand')]"
            )
            if cookie_buttons:
                self.logger.info("Found cookie consent button, clicking...")
                cookie_buttons[0].click()
                time.sleep(3)
        except Exception as e:
            self.logger.info(f"No cookie consent found or error: {e}")
    
    def _wait_and_find_elements(self, browser_manager: BrowserManager, selector: str, timeout: int = 20):
        """Wait for elements with timeout"""
        try:
            WebDriverWait(browser_manager.driver, timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
            )
            return browser_manager.driver.find_elements(By.CSS_SELECTOR, selector)
        except TimeoutException:
            self.logger.warning(f"Timeout waiting for elements: {selector}")
            return []
    
    def _extract_company_data_from_element(self, element) -> Optional[dict]:
        """Extract company data from a list element"""
        try:
            # Extract company name
            try:
                company_name = element.find_element(By.CSS_SELECTOR, ".company-name p").get_attribute("innerText").strip()
            except:
                try:
                    company_name = element.find_element(By.CSS_SELECTOR, "[class*='company'] p").get_attribute("innerText").strip()
                except:
                    company_name = "Unknown"
            
            # Extract price change
            try:
                price_change = element.find_element(By.CSS_SELECTOR, ".company-name div[class^='price']").get_attribute("innerText").strip()
            except:
                price_change = ""
            
            # Extract details
            detail_dict = {}
            try:
                detail_elements = element.find_elements(By.CSS_SELECTOR, ".symbol-name-code .col-box")
                for detail in detail_elements:
                    try:
                        label = detail.find_element(By.CSS_SELECTOR, ".col-name").get_attribute("innerText").strip().replace("\t", "").replace("\n", "")
                        value = detail.find_element(By.CSS_SELECTOR, ".col-value").get_attribute("innerText").strip()
                        detail_dict[label] = value
                    except:
                        continue
            except:
                pass
            
            # Extract profile link
            try:
                profile_link = element.find_element(By.XPATH, ".//a[contains(@href, 'profile')]").get_attribute("href")
            except:
                profile_link = ""
            
            return {
                'name': company_name,
                'price_change': price_change,
                'symbol': detail_dict.get('Symbol', ''),
                'trading_name': detail_dict.get('Trading Name', ''),
                'isin_code': detail_dict.get('ISIN Code', ''),
                'profile_url': profile_link
            }
            
        except Exception as e:
            self.logger.warning(f"Error extracting company data: {e}")
            return None
    
    def _click_next_page(self, browser_manager: BrowserManager, page: int) -> bool:
        """Click next page button"""
        try:
            selectors = self.config.get('selectors', {}).get('pagination_selectors', [])
            
            for selector in selectors:
                try:
                    next_elements = browser_manager.driver.find_elements(By.CSS_SELECTOR, selector)
                    if next_elements:
                        next_li = next_elements[0]
                        
                        # Check if disabled
                        if "disable" in next_li.get_attribute("class"):
                            self.logger.info("Next button found but disabled. Pagination complete.")
                            return False
                        
                        # Try to find clickable element
                        try:
                            next_button = next_li.find_element(By.TAG_NAME, "a")
                        except:
                            next_button = next_li
                        
                        self.logger.info("Clicking next button...")
                        next_button.click()
                        return True
                        
                except Exception as e:
                    self.logger.warning(f"Error with pagination selector {selector}: {e}")
                    continue
            
            self.logger.info("No next button found with any selector. Pagination complete.")
            return False
            
        except Exception as e:
            self.logger.error(f"Error during pagination: {e}")
            return False
    
    def _find_profile_container(self, browser_manager: BrowserManager):
        """Find the profile container using multiple selectors"""
        selectors = self.config.get('selectors', {}).get('profile_container_selectors', [])
        
        for selector in selectors:
            try:
                container = WebDriverWait(browser_manager.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if container:
                    return container
            except:
                continue
                
        self.logger.error("Profile container not found with any selector")
        return None
    
    def _extract_company_details_from_container(self, container) -> dict:
        """Extract company details from profile container"""
        company_details = {}
        
        try:
            details_containers = container.find_elements(By.CSS_SELECTOR, "div.company_management_tab_dtl")
            if details_containers:
                details_container = details_containers[0]
                items = details_container.find_elements(By.CSS_SELECTOR, "ul > li")
                
                for item in items:
                    try:
                        key = item.find_element(By.TAG_NAME, "h4").text.strip()
                        value = item.find_element(By.TAG_NAME, "p").text.strip()
                        
                        # Only store relevant fields
                        if key in ["Date Established", "Financial Year End", "Listing Date", "External Auditors", "ISIN CODE"]:
                            company_details[key] = value
                    except:
                        continue
        except:
            pass
            
        return company_details
    
    def _extract_management_details(self, browser_manager: BrowserManager, container) -> List[dict]:
        """Extract management details from profile container"""
        management_details = []
        
        try:
            # Find and click management tab
            tab_found = False
            tab_selectors = self.config.get('selectors', {}).get('management_tabs', [])
            
            for selector in tab_selectors:
                tabs = container.find_elements(By.CSS_SELECTOR, selector)
                for tab in tabs:
                    tab_text = tab.text
                    if "BOARD OF DIRECTORS" in tab_text.upper() or "EXECUTIVES" in tab_text.upper():
                        browser_manager.scroll_to_element(tab)
                        time.sleep(1)
                        browser_manager.driver.execute_script("arguments[0].click();", tab)
                        tab_found = True
                        time.sleep(self.config.get('navigation', {}).get('tab_wait', 5))
                        break
                if tab_found:
                    break
            
            if tab_found:
                management_containers = container.find_elements(By.CSS_SELECTOR, "div.company_management_tab_dtl")
                if len(management_containers) >= 2:
                    management_container = management_containers[1]
                    items = management_container.find_elements(By.CSS_SELECTOR, "ul > li")
                    
                    for item in items:
                        try:
                            h4_elements = item.find_elements(By.TAG_NAME, "h4")
                            if not h4_elements:
                                continue
                                
                            role = h4_elements[0].text.strip()
                            
                            p_tags = item.find_elements(By.TAG_NAME, "p")
                            for p in p_tags:
                                try:
                                    name_elements = p.find_elements(By.TAG_NAME, "strong")
                                    if not name_elements:
                                        continue
                                    
                                    name = name_elements[0].text.strip()
                                    designation = p.text.replace(name, "").strip()
                                    
                                    management_details.append({
                                        'role': role,
                                        'name': name,
                                        'designation': designation
                                    })
                                    
                                except Exception as e:
                                    self.logger.warning(f"Error extracting name/designation: {e}")
                                    
                        except Exception as e:
                            self.logger.warning(f"Error processing management item: {e}")
            else:
                self.logger.warning("Management tab not found")
                
        except Exception as e:
            self.logger.error(f"Error extracting management details: {e}")
            
        return management_details