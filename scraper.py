#!/usr/bin/env python3
"""
GCC Scraper - Main Entry Point
Concurrent streaming scraper for GCC stock exchanges
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from utils import ConfigManager
from utils.logging_config import setup_app_logging
from scrapers.dfm_scraper import DFMScraper
from scrapers.saudi_scraper import SaudiScraper
from scrapers.kuwait_scraper import KuwaitScraper
from scrapers.adx_scraper import ADXScraper
from scrapers.bahrain_scraper import BahrainScraper
from scrapers.oman_scraper import OmanScraper


class GCCScraperApp:
    """Main application class for GCC Scraper with concurrent processing capabilities.
    
    This application provides a unified interface for scraping all GCC stock exchanges
    with concurrent processing, streaming output, and comprehensive error handling.
    
    Features:
    - Support for 6 GCC exchanges (DFM, Saudi, Kuwait, ADX, Bahrain, Oman)
    - Concurrent browser pool processing for each exchange
    - Real-time streaming output with Excel conversion
    - Professional logging with colored console output
    - Configurable rate limiting and retry logic
    
    Args:
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, verbose: bool = False) -> None:
        self.config_manager = ConfigManager()
        self.verbose = verbose
        self.logger = setup_app_logging(verbose=verbose)
        self.available_exchanges = {
            'dfm': DFMScraper,
            'saudi': SaudiScraper,
            'kuwait': KuwaitScraper,
            'adx': ADXScraper,
            'bahrain': BahrainScraper,
            'oman': OmanScraper,
        }
    
    async def scrape_exchange(self, exchange: str, max_companies: int = None):
        """Scrape a single exchange"""
        if exchange not in self.available_exchanges:
            self.logger.error(f"❌ Exchange '{exchange}' not available")
            self.logger.progress(f"Available exchanges: {', '.join(self.available_exchanges.keys())}")
            return None
        
        scraper_class = self.available_exchanges[exchange]
        
        self.logger.progress(f"🚀 Starting {exchange.upper()} scraper")
        
        async with scraper_class(self.config_manager, verbose=self.verbose) as scraper:
            result = await scraper.run_concurrent_streaming(max_companies=max_companies)
            
            self.logger.progress(f"\n📊 {exchange.upper()} RESULTS:")
            self.logger.progress(f"Status: {result.status.value}")
            self.logger.progress(f"Companies: {result.companies_processed}/{result.companies_found}")
            self.logger.progress(f"Board members: {result.board_members_extracted}")
            self.logger.progress(f"Duration: {result.duration_seconds:.2f}s")
            self.logger.progress(f"Success rate: {result.success_rate:.1f}%")
            self.logger.progress(f"Output: {result.output_file}")
            
            if result.errors:
                self.logger.warning(f"Errors: {len(result.errors)}")
                for error in result.errors[:3]:
                    self.logger.error(f"  - {error}")
            
            return result
    
    async def scrape_all_exchanges(self, max_companies: int = None):
        """Scrape all available exchanges"""
        results = {}
        
        for exchange in self.available_exchanges:
            print(f"\n{'='*60}")
            result = await self.scrape_exchange(exchange, max_companies)
            results[exchange] = result
        
        # Summary
        print(f"\n{'='*60}")
        print("🎉 ALL EXCHANGES COMPLETED")
        print(f"{'='*60}")
        
        total_companies = sum(r.companies_processed for r in results.values() if r)
        total_members = sum(r.board_members_extracted for r in results.values() if r)
        total_duration = sum(r.duration_seconds for r in results.values() if r)
        
        print(f"Total companies processed: {total_companies}")
        print(f"Total board members: {total_members}")
        print(f"Total duration: {total_duration:.2f}s")
        
        return results
    
    def list_exchanges(self):
        """List available exchanges"""
        print("Available exchanges:")
        for exchange in self.available_exchanges:
            scraper_class = self.available_exchanges[exchange]
            print(f"  {exchange.upper()}: {scraper_class.__doc__}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="GCC Stock Exchange Scraper with concurrent streaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py dfm                    # Scrape all DFM companies
  python scraper.py saudi --limit 10       # Scrape first 10 Saudi companies
  python scraper.py --all                  # Scrape all exchanges
  python scraper.py --all --limit 5        # Scrape first 5 companies from each exchange
  python scraper.py --list                 # List available exchanges
        """
    )
    
    parser.add_argument(
        'exchange', 
        nargs='?',
        help='Exchange to scrape (dfm, saudi, kuwait, adx, bahrain, oman)'
    )
    
    parser.add_argument(
        '--all', 
        action='store_true',
        help='Scrape all available exchanges'
    )
    
    parser.add_argument(
        '--limit', 
        type=int,
        help='Limit number of companies to scrape (for testing)'
    )
    
    parser.add_argument(
        '--list', 
        action='store_true',
        help='List available exchanges'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging (shows detailed debug information)'
    )
    
    args = parser.parse_args()
    
    # Install required packages if missing
    try:
        import aiofiles
        import tenacity
    except ImportError:
        print("📦 Installing required packages...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "aiofiles", "tenacity"])
        print("✅ Packages installed successfully")
    
    app = GCCScraperApp(verbose=args.verbose)
    
    if args.list:
        app.list_exchanges()
        return
    
    if args.all:
        await app.scrape_all_exchanges(max_companies=args.limit)
    elif args.exchange:
        await app.scrape_exchange(args.exchange.lower(), max_companies=args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    print("🌟 GCC Stock Exchange Scraper")
    print("Concurrent streaming with rate limiting and retries")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Scraping interrupted by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)