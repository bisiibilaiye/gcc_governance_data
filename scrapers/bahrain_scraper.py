"""
Bahrain Scraper using Concurrent Base Architecture
"""
from typing import List, Optional
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import Company, CompanyDetails, BoardMember
from utils import ConfigManager, BrowserManager


class BahrainScraper(BaseScraper):
    """Bahrain Bourse scraper with sector-based company organization.
    
    Features:
    - Sector-based company categorization from table headers
    - Overview tab navigation for board member extraction
    - Dynamic content loading with BeautifulSoup parsing
    - Random delay patterns for natural scraping behavior
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('bahrain', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
        self.summary_url = self.config['exchange']['summary_url']
        # Store company data for later reference
        self.companies_data = []
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs from summary page"""
        self.logger.info(f"Extracting company URLs from {self.summary_url}")
        
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
            browser_manager.navigate_to(self.summary_url)
            
            # Wait for table to load
            table_selector = self.config['selectors']['companies_table']
            browser_manager.wait_for_element(By.CSS_SELECTOR, table_selector, timeout=20)
            
            # Extra delay for dynamic content
            time.sleep(5)
            
            # Get page source and parse with BeautifulSoup
            html = browser_manager.get_page_source()
            soup = BeautifulSoup(html, "html.parser")
            
            table = soup.find("table", id="bhbTable")
            if not table:
                self.logger.error("Could not find companies table")
                return []
                
            tbody = table.find("tbody")
            if not tbody:
                self.logger.error("Could not find table body")
                return []
            
            companies_data = []
            current_sector = None
            
            for row in tbody.find_all("tr"):
                row_classes = row.get("class", [])
                
                # Check if this is a sector header row
                if "tbl-data" in row_classes:
                    td = row.find("td")
                    if td and td.has_attr("colspan"):
                        current_sector = td.get_text(strip=True)
                        continue
                
                # Process company rows
                tds = row.find_all("td")
                if tds:
                    a = tds[0].find("a")
                    if a:
                        company_name = a.get_text(strip=True)
                        company_url = a.get("href")
                        if company_url and company_url.startswith("/"):
                            company_url = self.base_url + company_url
                            
                        companies_data.append({
                            "name": company_name,
                            "url": company_url,
                            "sector": current_sector
                        })
            
            # Store company data for later use
            self.companies_data = companies_data
            urls = [comp["url"] for comp in companies_data if comp["url"]]
            
            self.logger.info(f"Found {len(urls)} company URLs")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error extracting company URLs: {e}")
            return []
    
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information"""
        try:
            # Find company data from stored data
            company_data = None
            for comp in self.companies_data:
                if comp['url'] == url:
                    company_data = comp
                    break
                    
            if not company_data:
                self.logger.warning(f"Could not find company data for {url}")
                return None
                
            return Company(
                symbol=company_data['name'],  # Bahrain uses name as symbol
                name=company_data['name'],
                exchange=self.exchange_name,
                sector=company_data.get('sector')
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company info from {url}: {e}")
            return None
    
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company information"""
        try:
            # Find company data
            company_data = None
            for comp in self.companies_data:
                if comp['url'] == url:
                    company_data = comp
                    break
                    
            if not company_data:
                return None
                
            return CompanyDetails(
                symbol=company_data['name'],
                company_name=company_data['name'],
                exchange=self.exchange_name,
                sub_sector=company_data.get('sector'),
                # Bahrain doesn't provide these fields
                incorporation_date=None,
                establishment_date=None,
                share_capital=None,
                company_type=None,
                auditor=None,
                fiscal_year_end=None,
                registrar=None,
                commercial_id=None,
                activity=None
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company details from {url}: {e}")
            return None
    
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members from company page"""
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
                
            browser_manager.navigate_to(url)
            
            # Wait for page to load
            browser_manager.wait_for_element(By.TAG_NAME, "body", timeout=15)
            time.sleep(3)
            
            # Click Overview tab
            try:
                overview_tab = WebDriverWait(browser_manager.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.nav-link[href='#overview'][data-toggle='pill']"))
                )
                browser_manager.driver.execute_script("arguments[0].click();", overview_tab)
                self.logger.info(f"Successfully clicked Overview tab for {company_data['name']}")
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Could not click Overview tab for {company_data['name']}: {e}")
                return []
            
            # Wait for overview content
            try:
                overview_content = WebDriverWait(browser_manager.driver, 10).until(
                    EC.visibility_of_element_located((By.ID, "overview"))
                )
                
                # Look for board information
                board_section = overview_content.find_elements(
                    By.XPATH, 
                    ".//div[contains(@id, 'CompaniesDirectors') or contains(@class, 'directors')]"
                )
                
                if not board_section:
                    self.logger.info(f"No board information found for {company_data['name']}")
                    return []
                
                board_div = board_section[0]
                board_tables = board_div.find_elements(By.TAG_NAME, "table")
                
                if not board_tables:
                    self.logger.info(f"No board table found for {company_data['name']}")
                    return []
                
                # Process the board table
                board_table = board_tables[0]
                board_html = board_table.get_attribute("outerHTML")
                board_soup = BeautifulSoup(board_html, "html.parser")
                
                # Find table rows
                rows = []
                tbody = board_soup.find("tbody")
                if tbody:
                    rows = tbody.find_all("tr")
                else:
                    rows = board_soup.find_all("tr")
                
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 3:
                        continue
                        
                    member_name = cols[0].get_text(strip=True)
                    member_type = cols[1].get_text(strip=True)
                    role = cols[2].get_text(strip=True)
                    
                    # Skip header rows or empty data
                    if not member_name or member_name.lower() in ["name", "board member", "director"]:
                        continue
                    
                    board_members.append(BoardMember(
                        company_symbol=company_data['name'],
                        company_name=company_data['name'],
                        exchange=self.exchange_name,
                        name=member_name,
                        position=role,
                        member_type=member_type,
                        designation=None,
                        role_category="Board",
                        comments=None
                    ))
                
            except Exception as e:
                self.logger.error(f"Error extracting board details for {company_data['name']}: {e}")
            
            # Apply random delay
            delay_range = self.config.get('scraping', {}).get('random_delay_range', [2, 4])
            time.sleep(random.uniform(delay_range[0], delay_range[1]))
            
        except Exception as e:
            self.logger.error(f"Error processing {url}: {e}")
            
        return board_members