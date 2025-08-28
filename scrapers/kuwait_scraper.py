"""
Kuwait Scraper using Concurrent Base Architecture
"""
from typing import List, Optional
import time
import re
import html
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


class KuwaitScraper(BaseScraper):
    """Boursa Kuwait scraper with auditor standardization and board member extraction.
    
    Features:
    - Auditor firm name standardization using regex patterns
    - Management tab navigation and board member extraction
    - Company details with trading information
    - Concurrent processing with rate limiting
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('kuwait', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
        self.listing_url = self.config['exchange']['listing_url']
        # Store company data for later reference
        self.companies_data = []
        self.company_urls = {}
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs and basic information from listings page"""
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
        """Extract URLs using specific browser manager"""
        try:
            browser_manager.navigate_to(self.listing_url)
            time.sleep(10)  # Wait for page to load
            
            # Extract table data
            rows = self._wait_and_find_elements(browser_manager, "table.table tbody tr")
            
            if not rows:
                self.logger.info("No rows found, retrying with longer wait...")
                time.sleep(10)
                rows = self._wait_and_find_elements(browser_manager, "table.table tbody tr")
            
            companies_data = []
            company_urls = {}
            
            for row in rows:
                try:
                    columns = row.find_elements(By.TAG_NAME, "td")
                    if len(columns) == 8:
                        # Extract row data: No, Sec.Code, Ticker, Loss Category, Name, Sector, Market Segment, Date of Listing
                        row_data = [col.text.strip() for col in columns]
                        companies_data.append(row_data)
                        
                        # Extract company URL from Name column (5th column, index 4)
                        try:
                            link_element = columns[4].find_element(By.TAG_NAME, "a")
                            company_name = link_element.text.strip()
                            company_url = link_element.get_attribute("href")
                            
                            if company_url and company_name:
                                company_urls[company_name] = company_url
                                
                        except Exception as e:
                            self.logger.warning(f"Could not extract URL for company in row: {row_data}")
                            
                except Exception as e:
                    self.logger.error(f"Error processing row: {e}")
                    continue
            
            # Store data for later use
            self.companies_data = companies_data
            self.company_urls = company_urls
            
            urls = list(company_urls.values())
            self.logger.info(f"Found {len(urls)} company URLs")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error extracting company URLs: {e}")
            return []
    
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information"""
        try:
            # Find company data from stored info
            company_name = None
            company_data = None
            
            for name, stored_url in self.company_urls.items():
                if stored_url == url:
                    company_name = name
                    # Find corresponding row data
                    for row in self.companies_data:
                        if len(row) >= 8 and row[4] == company_name:  # Name is in column 5 (index 4)
                            company_data = row
                            break
                    break
            
            if not company_name or not company_data:
                self.logger.warning(f"Could not find company data for {url}")
                return None
                
            return Company(
                symbol=company_data[2],  # Ticker (index 2)
                name=company_name,
                exchange=self.exchange_name,
                sector=company_data[5] if len(company_data) > 5 else None,  # Sector (index 5)
                market_segment=company_data[6] if len(company_data) > 6 else None,  # Market Segment (index 6)
                listing_date=company_data[7] if len(company_data) > 7 else None  # Date of Listing (index 7)
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company info from {url}: {e}")
            return None
    
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company information including auditor data"""
        try:
            # Find company name
            company_name = None
            for name, stored_url in self.company_urls.items():
                if stored_url == url:
                    company_name = name
                    break
                    
            if not company_name:
                return None
                
            # Navigate to company page
            browser_manager.navigate_to(url)
            time.sleep(3)
            
            # Click Management tab
            success = self._click_management_tab(browser_manager, company_name)
            if not success:
                return None
                
            # Extract auditor information
            auditor_info = self._extract_auditor_info(browser_manager, company_name)
            
            # Find ticker from stored data
            ticker = company_name  # Fallback
            for row in self.companies_data:
                if len(row) >= 5 and row[4] == company_name:
                    ticker = row[2]  # Ticker is at index 2
                    break
            
            return CompanyDetails(
                symbol=ticker,
                company_name=company_name,
                exchange=self.exchange_name,
                auditor=auditor_info.get('name', ''),
                # Add standardized auditor name
                registrar=auditor_info.get('standardized_name', ''),
                # Kuwait doesn't provide these fields
                incorporation_date=None,
                establishment_date=None,
                share_capital=None,
                company_type=None,
                fiscal_year_end=None,
                commercial_id=None,
                activity=None,
                sub_sector=None
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company details from {url}: {e}")
            return None
    
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members and executives"""
        board_members = []
        
        try:
            # Find company info
            company_name = None
            ticker = None
            
            for name, stored_url in self.company_urls.items():
                if stored_url == url:
                    company_name = name
                    # Find ticker
                    for row in self.companies_data:
                        if len(row) >= 5 and row[4] == company_name:
                            ticker = row[2]
                            break
                    break
                    
            if not company_name:
                self.logger.warning(f"Could not find company name for {url}")
                return []
                
            # Navigate and click management tab
            browser_manager.navigate_to(url)
            time.sleep(3)
            
            success = self._click_management_tab(browser_manager, company_name)
            if not success:
                return []
            
            # Extract board data
            board_data, auditor_data = self._extract_management_data(browser_manager, company_name)
            
            # Convert to BoardMember objects
            for member in board_data:
                board_members.append(BoardMember(
                    company_symbol=ticker or company_name,
                    company_name=company_name,
                    exchange=self.exchange_name,
                    name=member['name'],
                    position=member['position'],
                    member_type=member.get('bod_type', ''),
                    comments=member.get('comments', ''),
                    designation=None,
                    role_category="Board"
                ))
            
            # Add auditors as a special category
            for auditor in auditor_data:
                board_members.append(BoardMember(
                    company_symbol=ticker or company_name,
                    company_name=company_name,
                    exchange=self.exchange_name,
                    name=auditor['name'],
                    position=auditor['position'],
                    comments=auditor.get('comments', ''),
                    designation=None,
                    member_type=None,
                    role_category="Auditor"
                ))
                
        except Exception as e:
            self.logger.error(f"Error extracting board members from {url}: {e}")
            
        return board_members
    
    def _wait_and_find_elements(self, browser_manager: BrowserManager, selector: str, timeout: int = 10):
        """Wait for elements to be present and return them"""
        try:
            WebDriverWait(browser_manager.driver, timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
            )
            return browser_manager.driver.find_elements(By.CSS_SELECTOR, selector)
        except TimeoutException:
            self.logger.warning(f"Timeout waiting for elements: {selector}")
            return []
    
    def _click_management_tab(self, browser_manager: BrowserManager, company_name: str) -> bool:
        """Click the Management tab"""
        try:
            # Try direct link text first
            management_tabs = self._wait_and_find_elements(browser_manager, "a[href*='Management'], a[title*='Management']")
            
            if not management_tabs:
                # Try partial link text
                try:
                    management_tab = WebDriverWait(browser_manager.driver, 10).until(
                        EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Management"))
                    )
                    management_tab.click()
                    time.sleep(3)
                    return True
                except:
                    pass
                    
                # Try link text
                try:
                    management_tab = WebDriverWait(browser_manager.driver, 10).until(
                        EC.element_to_be_clickable((By.LINK_TEXT, "Management"))
                    )
                    management_tab.click()
                    time.sleep(3)
                    return True
                except:
                    pass
                    
                self.logger.error(f"Could not find Management tab for {company_name}")
                return False
            else:
                management_tabs[0].click()
                time.sleep(3)
                return True
                
        except Exception as e:
            self.logger.error(f"Could not click Management tab for {company_name}: {e}")
            return False
    
    def _extract_management_data(self, browser_manager: BrowserManager, company_name: str) -> tuple:
        """Extract board and auditor data from management page"""
        board_data = []
        auditor_data = []
        
        try:
            # Find management sections
            sections = browser_manager.driver.find_elements(
                By.CSS_SELECTOR, "div.stock-profile-table-wrapper"
            )
            
            for section in sections:
                try:
                    header = section.find_element(By.TAG_NAME, "h3").text
                    rows = section.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        
                        if "Board of Directors" in header and len(cols) >= 4:
                            board_data.append({
                                'position': cols[0].text.strip(),
                                'name': cols[1].text.strip(),
                                'bod_type': cols[2].text.strip(),
                                'comments': cols[3].text.strip()
                            })
                            
                        elif "Auditor" in header and len(cols) >= 3:
                            raw_name = cols[1].text.strip()
                            auditor_data.append({
                                'position': cols[0].text.strip(),
                                'name': raw_name,
                                'standardized_name': self._standardize_auditor_name(raw_name),
                                'comments': cols[2].text.strip() if len(cols) > 2 else ''
                            })
                            
                except Exception as e:
                    self.logger.warning(f"Error processing section in {company_name}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error extracting management data for {company_name}: {e}")
            
        return board_data, auditor_data
    
    def _extract_auditor_info(self, browser_manager: BrowserManager, company_name: str) -> dict:
        """Extract auditor information specifically"""
        try:
            sections = browser_manager.driver.find_elements(
                By.CSS_SELECTOR, "div.stock-profile-table-wrapper"
            )
            
            for section in sections:
                try:
                    header = section.find_element(By.TAG_NAME, "h3").text
                    if "Auditor" in header:
                        rows = section.find_elements(By.CSS_SELECTOR, "table tbody tr")
                        if rows and len(rows) > 0:
                            cols = rows[0].find_elements(By.TAG_NAME, "td")
                            if len(cols) >= 2:
                                raw_name = cols[1].text.strip()
                                return {
                                    'name': raw_name,
                                    'standardized_name': self._standardize_auditor_name(raw_name)
                                }
                except Exception:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Error extracting auditor info for {company_name}: {e}")
            
        return {}
    
    def _standardize_auditor_name(self, name: str) -> str:
        """Standardize auditor firm names using configuration mappings"""
        if not name:
            return name
            
        # Clean the name
        name = html.unescape(name)
        name = " ".join(name.split())
        name = name.replace(" - ", " ").replace(" – ", " ").replace("&amp;", "&")
        name = re.sub(r"\s*[\-–]\s*", " ", name)
        
        # Extract main firm name if person is mentioned
        if "from" in name.lower():
            name = name.split("from")[-1].strip()
            
        # Remove individual names at the start
        name = re.sub(r"^[^-]+ - ", "", name)
        
        # Apply firm mappings from config
        firm_mappings = self.config.get('auditor_standardization', {}).get('firm_mappings', {})
        name_lower = name.lower()
        
        for pattern, standard_name in firm_mappings.items():
            if re.search(pattern.lower(), name_lower):
                return standard_name
                
        return name.strip()