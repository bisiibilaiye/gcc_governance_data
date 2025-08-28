"""
Concurrent Base Scraper with Rate Limiting, Retries, and Streaming
All exchange scrapers should inherit from this base class.
"""
import asyncio
import aiofiles
import time
import csv
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from contextlib import asynccontextmanager
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

from models import Company, CompanyDetails, BoardMember, ExchangeResult, ScrapingStatus
from utils import ConfigManager, BrowserManager
from utils.logging_config import setup_scraper_logging


class BaseScraper(ABC):
    """
    Base class for all exchange scrapers with concurrent processing, 
    rate limiting, retry logic, and streaming output.
    
    This class provides a complete framework for scraping stock exchange data with:
    - Concurrent browser pool management
    - Rate limiting and retry logic with exponential backoff
    - Real-time streaming to CSV with Excel conversion
    - Professional logging with file management
    - Abstract methods for exchange-specific implementation
    
    Args:
        exchange_name (str): Name of the exchange (e.g., 'dfm', 'saudi')
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, exchange_name: str, config_manager: ConfigManager, verbose: bool = False) -> None:
        self.exchange_name = exchange_name.upper()
        self.config_manager = config_manager
        self.config = config_manager.load_exchange_config(exchange_name)
        self.logger = setup_scraper_logging(self.exchange_name, verbose=verbose)
        
        # Concurrency settings from config
        concurrency_config = self.config.get('concurrency', {})
        self.max_concurrent = concurrency_config.get('max_concurrent', 4)
        self.rate_limit_delay = concurrency_config.get('rate_limit_delay', 0.5)
        self.retry_attempts = concurrency_config.get('retry_attempts', 3)
        
        # Initialize semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Browser managers pool for concurrent processing
        self.browser_managers = []
        self.browser_pool = asyncio.Queue(maxsize=self.max_concurrent)
        
        # Results tracking
        self.result = ExchangeResult(exchange=self.exchange_name)
        self.processed_count = 0
        self.total_board_members = 0
        self.start_time = None
        
    async def __aenter__(self):
        """Async context manager entry - initialize browser pool"""
        await self.initialize_browser_pool()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup browser pool"""
        await self.cleanup_browser_pool()
    
    async def initialize_browser_pool(self):
        """Initialize pool of browser managers for concurrent processing"""
        self.logger.progress(f"🌐 Initializing browser pool with {self.max_concurrent} browsers...")
        self.logger.detail(f"Starting browser pool initialization with {self.max_concurrent} browsers")
        
        for i in range(self.max_concurrent):
            try:
                self.logger.detail(f"Starting browser {i+1}/{self.max_concurrent}")
                browser_manager = BrowserManager(self.config)
                browser_manager.__enter__()  # Initialize browser
                await self.browser_pool.put(browser_manager)
                self.browser_managers.append(browser_manager)
                self.logger.detail(f"Browser {i+1} initialized successfully")
            except Exception as e:
                self.logger.error(f"❌ Browser {i+1} failed: {e}")
                self.logger.detail(f"Failed to initialize browser {i+1}: {e}")
        
        self.logger.progress(f"🎯 Browser pool ready: {len(self.browser_managers)}/{self.max_concurrent} browsers initialized")
    
    async def cleanup_browser_pool(self):
        """Cleanup all browser managers"""
        self.logger.progress(f"🧹 Cleaning up {len(self.browser_managers)} browsers...")
        self.logger.detail("Starting browser pool cleanup")
        
        for i, browser_manager in enumerate(self.browser_managers):
            try:
                browser_manager.__exit__(None, None, None)
                self.logger.detail(f"Browser {i+1} closed successfully")
            except Exception as e:
                self.logger.warning(f"⚠️  Browser {i+1} cleanup error: {e}")
                self.logger.detail(f"Error cleaning up browser {i+1}: {e}")
        
        self.browser_managers.clear()
        self.logger.progress("🏁 Browser pool cleanup completed")
    
    @asynccontextmanager
    async def get_browser_manager(self):
        """Get browser manager from pool with automatic return"""
        browser_manager = await self.browser_pool.get()
        try:
            yield browser_manager
        finally:
            await self.browser_pool.put(browser_manager)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def process_single_company_with_retries(self, url: str, company_num: int, total: int) -> Dict[str, Any]:
        """Process a single company with retry logic and rate limiting"""
        company_code = url.split('/')[-1]
        
        async with self.semaphore:  # Rate limiting with semaphore
            try:
                self.logger.progress(f"🔄 [{company_num}/{total}] Starting: {company_code}")
                self.logger.detail(f"[{company_num}/{total}] Acquiring browser for: {company_code}")
                start_time = time.time()
                
                # Get browser from pool
                async with self.get_browser_manager() as browser_manager:
                    self.logger.detail(f"[{company_num}/{total}] Browser acquired, starting extraction")
                    
                    # Run the sync scraping in executor to avoid blocking event loop
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, 
                        self.extract_company_data_sync, 
                        browser_manager, 
                        url
                    )
                
                extraction_time = time.time() - start_time
                
                if result and 'company' in result and result['company']:
                    company = result['company']
                    board_members = result.get('board_members', [])
                    
                    self.logger.detail(f"[{company_num}/{total}] Streaming {company.name} with {len(board_members)} board members")
                    
                    # Stream data immediately
                    stream_start = time.time()
                    await self.stream_company_data(company, result.get('details'), board_members)
                    stream_time = time.time() - stream_start
                    
                    self.processed_count += 1
                    self.total_board_members += len(board_members)
                    
                    total_time = time.time() - start_time
                    self.logger.success(f"[{company_num}/{total}] {company.name} completed in {total_time:.1f}s (extract: {extraction_time:.1f}s, stream: {stream_time:.2f}s)")
                    self.logger.detail(f"[{company_num}/{total}] Successfully processed {company.name} - Total: {total_time:.1f}s, Board members: {len(board_members)}")
                    
                    # Progress summary
                    if company_num % 5 == 0 or company_num == total:
                        self.logger.progress(f"📊 Progress: {self.processed_count}/{total} companies completed, {self.total_board_members} total board members")
                    
                    return result
                else:
                    self.logger.error(f"❌ [{company_num}/{total}] Failed to extract data for {company_code}")
                    self.logger.detail(f"[{company_num}/{total}] No data extracted for {company_code}")
                    return {'error': f'No data extracted for {url}'}
                    
            except Exception as e:
                self.logger.error(f"💥 [{company_num}/{total}] Error processing {company_code}: {e}")
                self.logger.detail(f"[{company_num}/{total}] Error processing {company_code}: {e}")
                raise  # Let tenacity handle retries
            finally:
                # Rate limiting delay
                if self.rate_limit_delay > 0:
                    self.logger.detail(f"[{company_num}/{total}] Rate limiting delay: {self.rate_limit_delay}s")
                    await asyncio.sleep(self.rate_limit_delay)
    
    def extract_company_data_sync(self, browser_manager: BrowserManager, url: str) -> Dict[str, Any]:
        """
        Synchronous data extraction method - to be overridden by exchange scrapers.
        This runs in executor to avoid blocking the event loop.
        """
        try:
            # Extract basic company info
            company = self.extract_company_info_with_browser(browser_manager, url)
            if not company:
                return {}
            
            # Extract detailed info
            details = self.extract_company_details_with_browser(browser_manager, url)
            
            # Extract board members
            board_members = self.extract_board_members_with_browser(browser_manager, url)
            
            return {
                'company': company,
                'details': details,
                'board_members': board_members
            }
            
        except Exception as e:
            self.logger.error(f"Error in sync extraction for {url}: {e}")
            return {'error': str(e)}
    
    async def stream_company_data(self, company: Company, details: Optional[CompanyDetails], board_members: List[BoardMember]):
        """Stream company data to CSV files immediately using async I/O"""
        base_filename = f"{self.exchange_name.lower()}_streaming"
        
        # Stream company data
        company_file = f"outputs/{base_filename}_companies.csv"
        async with aiofiles.open(company_file, 'a', newline='', encoding='utf-8') as f:
            company_data = company.to_dict()
            row_values = [str(company_data.get(h, '')) for h in self.get_company_headers()]
            csv_line = ','.join(f'"{val.replace(chr(34), chr(34)+chr(34))}"' for val in row_values) + '\n'
            await f.write(csv_line)
        
        # Stream company details
        if details:
            details_file = f"outputs/{base_filename}_details.csv"
            async with aiofiles.open(details_file, 'a', newline='', encoding='utf-8') as f:
                details_data = details.to_dict()
                row_values = [str(details_data.get(h, '')) for h in self.get_details_headers()]
                csv_line = ','.join(f'"{val.replace(chr(34), chr(34)+chr(34))}"' for val in row_values) + '\n'
                await f.write(csv_line)
        
        # Stream board members
        if board_members:
            members_file = f"outputs/{base_filename}_members.csv"
            async with aiofiles.open(members_file, 'a', newline='', encoding='utf-8') as f:
                for member in board_members:
                    member_data = member.to_dict()
                    row_values = [str(member_data.get(h, '')) for h in self.get_members_headers()]
                    csv_line = ','.join(f'"{val.replace(chr(34), chr(34)+chr(34))}"' for val in row_values) + '\n'
                    await f.write(csv_line)
    
    async def setup_streaming_files(self):
        """Setup CSV files with headers for streaming"""
        base_filename = f"{self.exchange_name.lower()}_streaming"
        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)
        
        # Setup companies file
        companies_file = output_dir / f"{base_filename}_companies.csv"
        async with aiofiles.open(companies_file, 'w', encoding='utf-8') as f:
            headers_line = ','.join(self.get_company_headers()) + '\n'
            await f.write(headers_line)
        
        # Setup details file  
        details_file = output_dir / f"{base_filename}_details.csv"
        async with aiofiles.open(details_file, 'w', encoding='utf-8') as f:
            headers_line = ','.join(self.get_details_headers()) + '\n'
            await f.write(headers_line)
        
        # Setup members file
        members_file = output_dir / f"{base_filename}_members.csv"
        async with aiofiles.open(members_file, 'w', encoding='utf-8') as f:
            headers_line = ','.join(self.get_members_headers()) + '\n'
            await f.write(headers_line)
    
    async def run_concurrent_streaming(self, max_companies: Optional[int] = None) -> ExchangeResult:
        """
        Main method to run concurrent streaming scraping for any exchange
        """
        self.logger.info(f"🚀 Starting concurrent streaming for {self.exchange_name}")
        self.logger.info(f"⚙️  Max concurrent: {self.max_concurrent}, Rate limit: {self.rate_limit_delay}s")
        
        self.result.status = ScrapingStatus.IN_PROGRESS
        self.start_time = time.time()
        
        try:
            # Setup streaming files
            await self.setup_streaming_files()
            
            # Get company URLs
            all_urls = self.get_company_urls()
            if max_companies:
                urls = all_urls[:max_companies]
            else:
                urls = all_urls
                
            self.result.companies_found = len(urls)
            self.logger.progress(f"📊 Found {len(urls)} companies to process")
            self.logger.progress(f"⚙️  Concurrent settings: {self.max_concurrent} browsers, {self.rate_limit_delay}s delay")
            self.logger.detail(f"Processing {len(urls)} companies with {self.max_concurrent} concurrent browsers")
            
            if not urls:
                self.result.status = ScrapingStatus.FAILED
                self.result.errors.append("No company URLs found")
                return self.result
            
            self.logger.progress(f"🚀 Starting concurrent processing...")
            
            # Create concurrent tasks
            tasks = [
                self.process_single_company_with_retries(url, i+1, len(urls))
                for i, url in enumerate(urls)
            ]
            
            # Process all companies concurrently
            self.logger.detail(f"Processing {len(tasks)} companies concurrently")
            processing_start = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            processing_duration = time.time() - processing_start
            
            self.logger.progress(f"🏁 Concurrent processing completed in {processing_duration:.1f}s")
            
            # Analyze results
            successful = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Company {i+1} failed: {str(result)}"
                    self.logger.error(error_msg)
                    self.result.errors.append(error_msg)
                elif isinstance(result, dict) and 'error' not in result:
                    successful += 1
            
            # Update final results
            self.result.companies_processed = successful  
            self.result.board_members_extracted = self.total_board_members
            
            # Convert to Excel
            self.logger.progress(f"📝 Converting CSV files to Excel format...")
            conversion_start = time.time()
            excel_file = await self.convert_to_excel()
            conversion_time = time.time() - conversion_start
            self.result.output_file = str(excel_file) if excel_file else None
            
            if excel_file:
                self.logger.success(f"Excel file created: {excel_file} ({conversion_time:.1f}s)")
            else:
                self.logger.warning(f"⚠️  Excel conversion failed, CSV files retained")
            
            # Determine final status
            if successful == 0:
                self.result.status = ScrapingStatus.FAILED
            elif successful < len(urls):
                self.result.status = ScrapingStatus.PARTIAL
            else:
                self.result.status = ScrapingStatus.COMPLETED
                
        except Exception as e:
            self.logger.error(f"Critical error in concurrent streaming: {e}")
            self.result.status = ScrapingStatus.FAILED
            self.result.errors.append(f"Critical error: {str(e)}")
            
        finally:
            self.result.duration_seconds = time.time() - self.start_time
            total_time = self.result.duration_seconds
            
            self.logger.info(f"🎉 {self.exchange_name} completed in {total_time:.2f} seconds")
            self.logger.info(f"📈 Success rate: {self.result.companies_processed}/{self.result.companies_found} ({self.result.success_rate:.1f}%)")
            self.logger.info(f"👥 Total board members: {self.result.board_members_extracted}")
            if len(urls) > 0:
                self.logger.info(f"⚡ Average time per company: {total_time/len(urls):.1f}s")
            
        return self.result
    
    async def convert_to_excel(self) -> Optional[Path]:
        """Convert streamed CSV files to Excel format"""
        try:
            import pandas as pd
            from datetime import datetime
            
            base_filename = f"{self.exchange_name.lower()}_streaming"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = Path("outputs") / f"{self.exchange_name.lower()}_{timestamp}.xlsx"
            
            # Convert in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_convert_to_excel, base_filename, excel_file)
            
            return excel_file
            
        except Exception as e:
            self.logger.error(f"Error converting to Excel: {e}")
            return None
    
    def _sync_convert_to_excel(self, base_filename: str, excel_file: Path):
        """Synchronous Excel conversion"""
        import pandas as pd
        
        output_dir = Path("outputs")
        csv_files = {
            'Companies': output_dir / f"{base_filename}_companies.csv",
            'Company Details': output_dir / f"{base_filename}_details.csv", 
            'Board Members': output_dir / f"{base_filename}_members.csv"
        }
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for sheet_name, csv_file in csv_files.items():
                if csv_file.exists():
                    df = pd.read_csv(csv_file)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Cleanup CSV files
        for csv_file in csv_files.values():
            if csv_file.exists():
                csv_file.unlink()
    
    # Standard CSV headers - can be overridden by specific exchanges
    def get_company_headers(self) -> List[str]:
        return ['Symbol', 'Company Name', 'Exchange', 'Sector', 'ISIN', 'Listing Date', 'Market Segment', 'Trading Name']
    
    def get_details_headers(self) -> List[str]:
        return ['Symbol', 'Company Name', 'Exchange', 'Incorporation Date', 'Establishment Date', 'Share Capital', 'Company Type', 'Auditor', 'Fiscal Year End', 'Registrar', 'Commercial ID', 'Activity', 'Sub Sector']
    
    def get_members_headers(self) -> List[str]:
        return ['Company Symbol', 'Company Name', 'Exchange', 'Name', 'Position', 'Designation', 'Member Type', 'Role Category', 'Comments']
    
    # Abstract methods that each exchange must implement
    @abstractmethod
    def get_company_urls(self) -> List[str]:
        """Get list of company URLs for this exchange"""
        pass
    
    @abstractmethod 
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information using provided browser manager"""
        pass
    
    @abstractmethod
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company information using provided browser manager"""
        pass
    
    @abstractmethod
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members using provided browser manager"""
        pass