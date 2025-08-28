# 🌟 GCC Stock Exchange Scraper

Advanced concurrent streaming scraper for all GCC stock exchanges with professional logging, rate limiting, retry logic, and real-time data streaming.

## 📊 Supported Exchanges

| Exchange | Code | Country | Companies | Features |
|----------|------|---------|-----------|----------|
| **Dubai Financial Market** | `dfm` | UAE | ~65 | Middle Eastern titles, streaming |
| **Saudi Exchange (Tadawul)** | `saudi` | Saudi Arabia | ~200+ | Pagination, management tabs |  
| **Boursa Kuwait** | `kuwait` | Kuwait | ~170+ | Auditor standardization |
| **Abu Dhabi Securities Exchange** | `adx` | UAE | ~90+ | Infinite scroll handling |
| **Bahrain Bourse** | `bahrain` | Bahrain | ~40+ | Sector-based organization |
| **Muscat Securities Market** | `oman` | Oman | ~110+ | Multi-page pagination |

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# List available exchanges
python scraper.py --list

# Scrape single exchange (all companies)
python scraper.py dfm

# Test with limited companies
python scraper.py saudi --limit 10

# Scrape all exchanges
python scraper.py --all

# Enable verbose logging for debugging
python scraper.py dfm --verbose
```

## ✨ Key Features

### 🏎️ **Concurrent Processing**
- **2-4 concurrent browsers** per exchange for parallel processing  
- **2-3x faster** than sequential scraping
- **Configurable concurrency** based on exchange capacity
- **Browser pool management** with automatic resource cleanup

### 📈 **Real-Time Streaming**  
- **Immediate CSV writing** - data saved as processed
- **Memory efficient** - no data accumulation
- **Excel conversion** with multiple sheets (Companies, Details, Board Members)
- **Progress tracking** with real-time statistics

### 🔄 **Robust Error Handling**
- **Tenacity retry logic** with exponential backoff (up to 3 attempts)
- **Rate limiting** with configurable delays (0.8s-2.0s per exchange)
- **Circuit breaker patterns** for failed requests
- **Graceful degradation** with partial results

### 📝 **Professional Logging**
- **Colored console output** with emojis for better readability
- **File-based logging** with timestamps and detailed traces  
- **Progress indicators** showing processing status
- **Performance metrics** including timing and success rates

### ⚙️ **Highly Configurable**
- **YAML-based configuration** for each exchange
- **Flexible selectors** with multiple fallbacks
- **Customizable concurrency** settings per exchange
- **Environment-specific** browser configurations

## 🏗️ Architecture

```
gcc_scraper_refactored/
├── scraper.py                    # 🎯 Main CLI entry point
├── base_scraper.py              # 🏗️ Base class with concurrent framework
├── scrapers/                    # 🏢 Exchange-specific implementations  
│   ├── dfm_scraper.py          # Dubai Financial Market
│   ├── saudi_scraper.py        # Saudi Exchange (Tadawul)
│   ├── kuwait_scraper.py       # Boursa Kuwait
│   ├── adx_scraper.py          # Abu Dhabi Securities Exchange
│   ├── bahrain_scraper.py      # Bahrain Bourse
│   ├── oman_scraper.py         # Muscat Securities Market
│   └── exchange_template.py    # Template for new exchanges
├── config/                      # ⚙️ Configuration files
│   ├── common.yaml             # Global settings
│   └── exchanges/              # Exchange-specific configs
│       ├── dfm.yaml
│       ├── saudi.yaml
│       ├── kuwait.yaml
│       ├── adx.yaml
│       ├── bahrain.yaml
│       └── oman.yaml
├── models/                      # 📊 Data models
│   ├── company.py
│   ├── board_member.py
│   └── scraping_session.py
├── utils/                       # 🔧 Utilities
│   ├── browser.py              # Selenium browser management
│   ├── config.py               # Configuration loading
│   ├── logging_config.py       # Professional logging setup
│   └── validators.py           # Data validation
├── outputs/                     # 📁 Generated files
├── logs/                        # 📋 Application logs
└── tests/                       # 🧪 Test files
```

## 🎛️ Configuration

### Exchange-Specific Settings

Each exchange has its own configuration file with optimized settings:

```yaml
# config/exchanges/dfm.yaml
exchange:
  name: "Dubai Financial Market"
  base_url: "https://www.dfm.ae"
  main_url: "https://www.dfm.ae/the-exchange/market-information/listed-securities/equities"

# Concurrent processing settings  
concurrency:
  max_concurrent: 4              # Simultaneous browser instances
  rate_limit_delay: 0.8         # Delay between requests (seconds)
  retry_attempts: 3             # Max retry attempts per company
  pool_size: 4                  # Browser pool size

selectors:
  company_name_xpath: "//h4[@class='company-name']"
  board_info_xpath: "//section[@id='board-section']"
  # ... additional selectors with fallbacks

browser:
  headless: true
  window_size: "1920,1080"
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
```

### Global Settings

```yaml
# config/common.yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
browser:
  implicit_wait: 10
  page_load_timeout: 30
  script_timeout: 30
```

## 📊 Output Format

### Excel Output Structure

Each scraping session generates an Excel file with multiple sheets:

```
dfm_20250119_143052.xlsx
├── 📊 Companies          # Basic company information
│   ├── Symbol
│   ├── Company Name  
│   ├── Exchange
│   ├── Sector
│   ├── ISIN
│   ├── Listing Date
│   └── Market Segment
├── 📋 Company Details    # Detailed company information  
│   ├── Incorporation Date
│   ├── Share Capital
│   ├── Company Type
│   ├── Auditor
│   ├── Fiscal Year End
│   └── Registrar
└── 👥 Board Members      # Board member information
    ├── Name
    ├── Position  
    ├── Member Type
    ├── Role Category
    └── Comments
```

### Performance Metrics

Sample output from a typical run:

```
🎉 DFM completed in 287.45 seconds
📈 Success rate: 65/65 (100.0%)  
👥 Total board members: 456
⚡ Average time per company: 4.4s
```

## 🔧 Adding New Exchanges

### 1. Create Scraper Implementation

```python
# scrapers/new_exchange_scraper.py
from base_scraper import BaseScraper
from models import Company, CompanyDetails, BoardMember
from utils import ConfigManager, BrowserManager

class NewExchangeScraper(BaseScraper):
    """New Exchange scraper with concurrent processing.
    
    Features:
    - [List specific features for this exchange]
    - [Unique challenges or characteristics]
    
    Args:
        config_manager (ConfigManager): Configuration manager instance
        verbose (bool): Enable verbose logging for debugging
    """
    
    def __init__(self, config_manager: ConfigManager, verbose: bool = False) -> None:
        super().__init__('new_exchange', config_manager, verbose=verbose)
        self.base_url = self.config['exchange']['base_url']
    
    def get_company_urls(self) -> List[str]:
        """Extract company URLs from exchange website"""
        # Implementation specific to exchange
        
    def extract_company_info_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[Company]:
        """Extract basic company information"""
        # Implementation specific to exchange
        
    def extract_company_details_with_browser(self, browser_manager: BrowserManager, url: str) -> Optional[CompanyDetails]:
        """Extract detailed company information"""  
        # Implementation specific to exchange
        
    def extract_board_members_with_browser(self, browser_manager: BrowserManager, url: str) -> List[BoardMember]:
        """Extract board members information"""
        # Implementation specific to exchange
```

### 2. Create Configuration File

```yaml
# config/exchanges/new_exchange.yaml
exchange:
  name: "New Exchange"
  code: "NEW" 
  country: "Country"
  base_url: "https://www.newexchange.com"

concurrency:
  max_concurrent: 3
  rate_limit_delay: 1.0
  retry_attempts: 3
  pool_size: 3

selectors:
  company_name:
    - "h1.company-title"
    - ".company-name"
  
  company_cards:
    - "a[href*='company']"
    - ".company-link"

browser:
  headless: true
  window_size: "1920,1080"
```

### 3. Register in Main Application

```python
# scraper.py - Add to imports and available_exchanges
from scrapers.new_exchange_scraper import NewExchangeScraper

self.available_exchanges = {
    # ... existing exchanges
    'new': NewExchangeScraper,
}
```

## 🚀 Performance Optimization

### Concurrency Settings by Exchange

| Exchange | Concurrent | Rate Limit | Reasoning |
|----------|------------|------------|-----------|
| DFM | 4 | 0.8s | Fast, stable API responses |
| Saudi | 3 | 1.2s | Complex pagination, moderate limits |
| Kuwait | 4 | 0.8s | Good performance, reliable |  
| ADX | 3 | 1.0s | Infinite scroll, needs time |
| Bahrain | 3 | 1.5s | Smaller exchange, gentle approach |
| Oman | 2 | 2.0s | Slower responses, conservative |

### Benchmarks

| Exchange | Companies | Sequential | Concurrent | Speedup |
|----------|-----------|------------|------------|---------|
| DFM | 65 | ~15 min | ~5 min | 3.0x |
| Saudi | 200+ | ~45 min | ~18 min | 2.5x |
| Kuwait | 170+ | ~35 min | ~15 min | 2.3x |
| ADX | 90+ | ~25 min | ~12 min | 2.1x |

## 🧪 Testing

```bash
# Test single exchange with limited companies
python scraper.py dfm --limit 5 --verbose

# Test all exchanges with minimal companies  
python scraper.py --all --limit 2

# Run integration tests
python -m pytest tests/ -v

# Validate configuration files
python -m utils.config_validator
```

## 🐛 Troubleshooting

### Common Issues

**1. ChromeDriver Issues**
```bash
# Update ChromeDriver
python -c "from selenium import webdriver; from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
```

**2. Memory Issues**  
- Reduce `max_concurrent` in config
- Increase `rate_limit_delay`
- Check available RAM

**3. Network Timeouts**
- Increase `retry_attempts` in config
- Increase `rate_limit_delay`  
- Check internet connection stability

**4. Captcha/Bot Detection**
- Increase `rate_limit_delay` significantly
- Reduce `max_concurrent` to 1-2
- Check `user_agent` settings

### Debug Mode

Enable verbose logging for detailed troubleshooting:

```bash
python scraper.py dfm --verbose --limit 3
```

### Log Analysis

Logs are stored in `logs/` directory with timestamps:
- `gcc_scraper_YYYYMMDD_HHMMSS.log` - Application logs
- `scraper.{exchange}_YYYYMMDD_HHMMSS.log` - Exchange-specific logs

## 📈 Monitoring and Analytics

### Real-Time Progress

```
🚀 Starting DFM scraper
🌐 Initializing browser pool with 4 browsers...
🎯 Browser pool ready: 4/4 browsers initialized
📊 Found 65 companies to process
⚙️  Concurrent settings: 4 browsers, 0.8s delay
🔄 [12/65] Starting: EMAAR
✅ [12/65] Emaar Properties PJSC completed in 4.2s
📊 Progress: 12/65 companies completed, 87 total board members
```

### Success Metrics

- **Processing Speed**: Average time per company
- **Success Rate**: Percentage of successful extractions
- **Board Member Count**: Total members extracted
- **Error Analysis**: Types and frequency of failures

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-exchange`
3. **Follow code style**: Use type hints, docstrings, and consistent formatting
4. **Add tests**: Include unit tests for new functionality  
5. **Update docs**: Update README and configuration examples
6. **Submit PR**: Provide detailed description of changes

### Code Style

- **Type hints** for all function parameters and return types
- **Comprehensive docstrings** following Google/NumPy style
- **Error handling** with specific exception types
- **Logging** for debugging and monitoring
- **Configuration-driven** approach for flexibility

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues, questions, or contributions:

1. **Check the troubleshooting section** above
2. **Review existing issues** in the repository
3. **Enable verbose logging** and include logs in issue reports
4. **Provide configuration details** and exchange-specific information
5. **Include reproduction steps** for bugs

---

**⚡ Built with concurrent processing, streaming output, and production-ready reliability for GCC financial data extraction.**