"""
DFM Scraper using Concurrent Base Architecture
"""
from typing import List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import Company, CompanyDetails, BoardMember
from utils import ConfigManager, BrowserManager


class DFMScraper(BaseScraper):
    """Dubai Financial Market (DFM) scraper with concurrent processing, streaming output, and comprehensive data extraction.
    
    Features:
    - Concurrent browser pool processing (configurable)
    - Rate limiting and retry logic with exponential backoff
    - Real-time streaming to CSV with Excel conversion
    - Board member extraction with Middle Eastern title support
    - Comprehensive company details and profile information
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('dfm', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
        self.main_url = self.config['exchange']['main_url']
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs using Selenium"""
        self.logger.info(f"Extracting company URLs from {self.main_url}")
        
        # Use first browser from pool for URL extraction
        if not self.browser_managers:
            # Fallback - create temporary browser if pool not ready
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
            browser_manager.navigate_to(self.main_url)
            
            companies_xpath = self.config['selectors']['companies_section']
            companies_section = browser_manager.wait_for_element(By.XPATH, companies_xpath)
            
            links = companies_section.find_elements(By.TAG_NAME, "a")
            company_urls = []
            
            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith(self.base_url):
                    company_urls.append(href)
            
            self.logger.info(f"Found {len(company_urls)} company URLs")
            return company_urls
            
        except Exception as e:
            self.logger.error(f"Error extracting company URLs: {e}")
            return []
    
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information"""
        profile_url = f"{url}/profile"
        
        try:
            browser_manager.navigate_to(profile_url)
            
            # Extract company name
            company_name_xpath = self.config['selectors']['company_name_xpath']
            name_element = browser_manager.wait_for_element(By.XPATH, company_name_xpath, timeout=8)
            company_name = name_element.text.strip() if name_element else "Unknown"
            
            # Extract additional info from profile
            symbol = company_name  # Default fallback
            sector = ""
            isin = ""
            
            try:
                profile_info_xpath = self.config['selectors']['profile_info_xpath']
                profile_element = WebDriverWait(browser_manager.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, profile_info_xpath))
                )
                
                if profile_element:
                    text_content = profile_element.text
                    lines = text_content.split('\n') if text_content else []
                    
                    # Process lines in pairs (key-value)
                    for i in range(len(lines) - 1):
                        key = lines[i].strip().upper()
                        value = lines[i + 1].strip()
                        
                        if key and value:
                            if key in ['SYMBOL', 'CODE', 'TICKER']:
                                symbol = value
                            elif key in ['SECTOR', 'INDUSTRY']:
                                sector = value
                            elif key == 'ISIN':
                                isin = value
            except:
                pass  # Use defaults
            
            return Company(
                symbol=symbol,
                name=company_name,
                exchange=self.exchange_name,
                sector=sector,
                isin=isin
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting company info from {profile_url}: {e}")
            return None
    
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company information"""
        # DFM profile data extraction
        profile_data = self._extract_profile_data(browser_manager, url)
        
        if profile_data and profile_data.get('company_name'):
            return CompanyDetails(
                symbol=profile_data.get('symbol', ''),
                company_name=profile_data['company_name'],
                exchange=self.exchange_name,
                establishment_date=profile_data.get('established', ''),
                share_capital=profile_data.get('share_capital', ''),
                company_type=profile_data.get('company_type', ''),
                auditor=profile_data.get('auditor', ''),
                fiscal_year_end=profile_data.get('fiscal_year_end', ''),
                registrar=profile_data.get('registrar', ''),
                # DFM doesn't provide these fields
                incorporation_date=None,
                commercial_id=None,
                activity=None,
                sub_sector=None
            )
        
        return None
    
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members information"""
        profile_data = self._extract_profile_data(browser_manager, url)
        return profile_data.get('board_members', []) if profile_data else []
    
    def _extract_profile_data(self, browser_manager: BrowserManager, url: str) -> dict:
        """Extract all profile data in one navigation"""
        profile_url = f"{url}/profile"
        
        profile_data = {
            'company_name': None, 'symbol': None, 'sector': '', 'isin': '',
            'established': '', 'auditor': '', 'fiscal_year_end': '',
            'registrar': '', 'share_capital': '', 'company_type': '',
            'board_members': []
        }
        
        try:
            browser_manager.navigate_to(profile_url)
            
            # Extract company name
            company_name_xpath = self.config['selectors']['company_name_xpath']
            name_element = browser_manager.wait_for_element(By.XPATH, company_name_xpath, timeout=8)
            profile_data['company_name'] = name_element.text.strip() if name_element else "Unknown"
            
            # Extract profile sections
            self._extract_profile_section(browser_manager, profile_data, 'profile_info_xpath')
            self._extract_profile_section(browser_manager, profile_data, 'additional_info_xpath')
            
            # Set defaults
            if not profile_data['symbol']:
                profile_data['symbol'] = profile_data['company_name']
            
            # Extract board members
            self._extract_board_members(browser_manager, profile_data)
            
        except Exception as e:
            self.logger.error(f"Error extracting profile data from {profile_url}: {e}")
        
        return profile_data
    
    def _extract_profile_section(self, browser_manager: BrowserManager, profile_data: dict, xpath_key: str):
        """Extract data from a profile section"""
        try:
            section_xpath = self.config['selectors'][xpath_key]
            section_element = WebDriverWait(browser_manager.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, section_xpath))
            )
            
            if section_element and section_element.text:
                lines = section_element.text.split('\n')
                
                for i in range(len(lines) - 1):
                    key = lines[i].strip().upper()
                    value = lines[i + 1].strip()
                    
                    if key and value and len(key) < 100 and len(value) < 300:
                        # Map field names to profile data
                        if key in ['SYMBOL', 'CODE', 'TICKER']:
                            profile_data['symbol'] = value
                        elif key in ['SECTOR', 'INDUSTRY', 'BUSINESS']:
                            profile_data['sector'] = value
                        elif key == 'ISIN':
                            profile_data['isin'] = value
                        elif key in ['ESTABLISHED', 'INCORPORATION DATE', 'INCORPORATED']:
                            profile_data['established'] = value
                        elif key in ['AUDITOR', 'EXTERNAL AUDITOR']:
                            profile_data['auditor'] = value
                        elif key in ['FISCAL YEAR END', 'YEAR END', 'FINANCIAL YEAR END']:
                            profile_data['fiscal_year_end'] = value
                        elif key in ['REGISTRAR', 'SHARE REGISTRAR']:
                            profile_data['registrar'] = value
                        elif key in ['AUTHORIZED CAPITAL', 'CAPITAL', 'SHARE CAPITAL']:
                            profile_data['share_capital'] = value
                        elif key in ['COMPANY TYPE', 'TYPE', 'LEGAL FORM']:
                            profile_data['company_type'] = value
        except:
            pass  # Section might not exist
    
    def _extract_board_members(self, browser_manager: BrowserManager, profile_data: dict):
        """Extract board members from profile"""
        try:
            board_info_xpath = self.config['selectors']['board_info_xpath']
            board_element = WebDriverWait(browser_manager.driver, 8).until(
                EC.presence_of_element_located((By.XPATH, board_info_xpath))
            )
            
            if board_element and board_element.text:
                lines = board_element.text.split('\n')
                
                # Process lines in pairs (name-position)
                i = 0
                while i < len(lines) - 1:
                    name_line = lines[i].strip()
                    position_line = lines[i + 1].strip()
                    
                    # Enhanced title detection for Middle Eastern and international titles
                    name_upper = name_line.upper()
                    has_title = any(title in name_upper for title in [
                        'MR.', 'MRS.', 'MS.', 'DR.', 'H.E.', 'SHEIKH', 'SHEIKHA',
                        'H.H.', 'PROF.', 'ENG.', 'CAPTAIN', 'MAJOR', 'COLONEL'
                    ])
                    
                    # Check for proper name structure
                    is_proper_name = (
                        len(name_line.split()) >= 2 and
                        not any(word in name_upper for word in ['BOARD', 'DIRECTOR', 'CHAIRMAN', 'MEMBER', 'DEPUTY']) and
                        name_line[0].isupper()
                    )
                    
                    if (name_line and position_line and
                        (has_title or is_proper_name) and
                        len(name_line) < 100 and len(position_line) < 100):
                        
                        # Validate and standardize position
                        position_cleaned = position_line.upper()
                        valid_positions = [
                            'CHAIRMAN', 'DEPUTY', 'MEMBER', 'MEMBERS',
                            'VICE CHAIRMAN', 'BOARD MEMBER', 'BOARD MEMBERS',
                            'DIRECTOR', 'BOARD DIRECTOR'
                        ]
                        
                        if any(pos in position_cleaned for pos in valid_positions):
                            # Standardize position names
                            if 'CHAIRMAN' in position_cleaned:
                                position_cleaned = 'VICE CHAIRMAN' if 'VICE' in position_cleaned else 'CHAIRMAN'
                            elif 'DEPUTY' in position_cleaned:
                                position_cleaned = 'DEPUTY'
                            elif any(term in position_cleaned for term in ['BOARD MEMBER', 'BOARD DIRECTOR', 'MEMBERS', 'MEMBER']):
                                position_cleaned = 'MEMBER'
                            elif 'DIRECTOR' in position_cleaned:
                                position_cleaned = 'DIRECTOR'
                            else:
                                position_cleaned = 'MEMBER'
                            
                            board_member = BoardMember(
                                company_symbol=profile_data['symbol'],
                                company_name=profile_data['company_name'],
                                exchange=self.exchange_name,
                                name=name_line,
                                position=position_cleaned,
                                designation=None,
                                member_type=None,
                                role_category="Board",
                                comments=None
                            )
                            
                            profile_data['board_members'].append(board_member)
                    
                    i += 2  # Move to next pair
        except:
            pass  # Board section might not exist