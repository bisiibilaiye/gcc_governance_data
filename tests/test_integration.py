import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import yaml

from utils.config_validator import ConfigValidator, ConfigValidationError
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, ExchangeCircuitBreakerManager
from utils.rate_limiter import AdaptiveRateLimiter, RateLimitConfig, ExchangeRateLimiterManager
from utils.streaming import StreamingProcessor, StreamingConfig
from utils import ConfigManager
from models import Company, CompanyDetails, BoardMember


class TestConfigValidation:
    """Test configuration validation system."""
    
    def test_valid_common_config(self):
        """Test validation of valid common configuration."""
        validator = ConfigValidator()
        config = {
            'scraping': {
                'max_retries': 3,
                'retry_delay_seconds': 5,
                'default_timeout': 30,
                'page_load_wait': 5
            },
            'browser': {
                'headless': True,
                'window_size': '1920,1080',
                'user_agent': 'Test Agent'
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(message)s'
            },
            'output': {
                'default_format': 'xlsx'
            }
        }
        
        errors = validator.validate_common_config(config)
        assert len(errors) == 0
        
    def test_invalid_common_config(self):
        """Test validation of invalid common configuration."""
        validator = ConfigValidator()
        config = {
            'scraping': {
                'max_retries': -1,  # Invalid
                'retry_delay_seconds': 'invalid',  # Invalid type
            },
            'browser': {
                'headless': 'yes',  # Invalid type
                'window_size': 'invalid_format'  # Invalid format
            }
            # Missing required sections
        }
        
        errors = validator.validate_common_config(config)
        assert len(errors) > 0
        assert any('Missing required section' in error for error in errors)
        
    def test_exchange_config_validation(self):
        """Test exchange configuration validation."""
        validator = ConfigValidator()
        
        # Valid config
        valid_config = {
            'exchange': {
                'name': 'Test Exchange',
                'code': 'TEST',
                'base_url': 'https://example.com'
            },
            'selectors': {
                'company_name': ['h1', 'h2'],
                'company_cards': '.company-card'
            }
        }
        
        errors = validator.validate_exchange_config(valid_config, 'test')
        assert len(errors) == 0
        
        # Invalid config
        invalid_config = {
            'exchange': {
                'name': '',  # Empty name
                'base_url': 'not-a-url'  # Invalid URL
            },
            'selectors': {
                'company_name': []  # Empty selector list
            }
        }
        
        errors = validator.validate_exchange_config(invalid_config, 'test')
        assert len(errors) > 0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_basic_functionality(self):
        """Test basic circuit breaker open/close cycle."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=1)
        breaker = CircuitBreaker(config)
        
        # Initially closed
        assert breaker.is_closed
        
        def failing_function():
            raise Exception("Test failure")
            
        # First failure
        with pytest.raises(Exception):
            breaker.call(failing_function)
        assert breaker.failure_count == 1
        assert breaker.is_closed
        
        # Second failure should open circuit
        with pytest.raises(Exception):
            breaker.call(failing_function)
        assert breaker.failure_count == 2
        assert breaker.is_open
        
        # Third call should be blocked
        with pytest.raises(Exception):  # CircuitBreakerError
            breaker.call(failing_function)
            
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        import time
        
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(config)
        
        def failing_function():
            raise Exception("Test failure")
            
        # Trigger failure to open circuit
        with pytest.raises(Exception):
            breaker.call(failing_function)
        assert breaker.is_open
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        def success_function():
            return "success"
            
        # Should transition to half-open and then closed on success
        result = breaker.call(success_function)
        assert result == "success"
        assert breaker.is_closed
        
    def test_exchange_circuit_breaker_manager(self):
        """Test exchange-specific circuit breaker management."""
        manager = ExchangeCircuitBreakerManager()
        
        # Get breaker for exchange
        breaker = manager.get_circuit_breaker('test_exchange')
        assert breaker.config.name == 'test_exchange'
        
        # Test execution with breaker
        def test_func():
            return "test_result"
            
        result = manager.execute_with_breaker('test_exchange', test_func)
        assert result == "test_result"
        
        # Test stats collection
        stats = manager.get_all_stats()
        assert 'test_exchange' in stats


class TestRateLimiting:
    """Test adaptive rate limiting system."""
    
    def test_basic_rate_limiting(self):
        """Test basic rate limiter functionality."""
        config = RateLimitConfig(requests_per_second=2.0, burst_limit=3)
        limiter = AdaptiveRateLimiter(config, "test")
        
        # Should allow burst requests initially
        start_time = time.time()
        for i in range(3):
            delay = limiter.acquire()
            # First few requests should be fast due to burst allowance
            
        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should be fast due to burst
        
    def test_adaptive_delay_adjustment(self):
        """Test adaptive delay adjustment based on success/failure."""
        config = RateLimitConfig(adaptive=True, min_delay=0.1, max_delay=2.0)
        limiter = AdaptiveRateLimiter(config, "test")
        
        initial_delay = limiter.current_delay
        
        # Record failures should increase delay
        limiter.record_failure("test_error", 500)
        limiter.record_failure("test_error", 500)
        assert limiter.current_delay > initial_delay
        
        # Record successes should decrease delay
        for _ in range(10):
            limiter.record_success()
        assert limiter.current_delay < limiter.current_delay
        
    def test_exchange_rate_limiter_manager(self):
        """Test exchange-specific rate limiter management."""
        manager = ExchangeRateLimiterManager()
        
        # Get rate limiter for exchange
        limiter = manager.get_rate_limiter('test_exchange')
        assert limiter.name == 'test_exchange'
        
        # Test rate limiting acquisition
        delay = manager.acquire_for_exchange('test_exchange')
        assert delay >= 0
        
        # Test success/failure recording
        manager.record_success_for_exchange('test_exchange')
        manager.record_failure_for_exchange('test_exchange', "test_error", 500)
        
        # Test stats collection
        stats = manager.get_all_stats()
        assert 'test_exchange' in stats


class TestStreamingProcessor:
    """Test streaming and memory management."""
    
    def test_streaming_processor_batching(self):
        """Test batch processing functionality."""
        config = StreamingConfig(chunk_size=5)
        processor = StreamingProcessor(config)
        
        urls = [f"http://example.com/{i}" for i in range(20)]
        
        def mock_process_func(url):
            return {"url": url, "processed": True}
            
        batches = list(processor.batch_process_urls(urls, mock_process_func, batch_size=5))
        
        assert len(batches) == 4  # 20 URLs / 5 per batch
        assert all(len(batch) == 5 for batch in batches[:-1])  # All full batches
        assert len(batches[-1]) == 5  # Last batch
        
    def test_memory_monitoring(self):
        """Test memory monitoring functionality."""
        from utils.streaming import MemoryMonitor
        
        monitor = MemoryMonitor(max_memory_mb=1024)
        
        # Should return True for reasonable memory usage
        within_limits = monitor.check_memory_usage()
        assert isinstance(within_limits, bool)
        
        # Test garbage collection
        monitor.force_gc()  # Should not raise exception


@pytest.mark.asyncio
class TestAsyncFunctionality:
    """Test async scraping functionality."""
    
    async def test_async_http_session(self):
        """Test async HTTP session functionality."""
        from utils.async_browser import AsyncHttpSession, AsyncScrapingConfig
        
        config = AsyncScrapingConfig(request_timeout=10)
        
        # Mock aiohttp for testing
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = asyncio.coroutine(lambda: "<html>Test</html>")
            
            mock_session_instance = MagicMock()
            mock_session_instance.get.return_value.__aenter__.return_value = mock_response
            mock_session_instance.close = asyncio.coroutine(lambda: None)
            mock_session.return_value = mock_session_instance
            
            async with AsyncHttpSession(config) as session:
                # Should create session without error
                assert session.session is not None
                
    async def test_async_scraper_rate_limiting(self):
        """Test async scraper rate limiting integration."""
        from utils.async_browser import AsyncScraper, AsyncScrapingConfig
        from utils import ConfigManager
        
        # Create temporary config
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            
            # Create minimal config files
            common_config = {
                'scraping': {'max_retries': 3, 'retry_delay_seconds': 1, 'default_timeout': 30, 'page_load_wait': 2},
                'browser': {'headless': True, 'window_size': '1920,1080'},
                'logging': {'level': 'INFO', 'format': '%(message)s'},
                'output': {'default_format': 'xlsx'}
            }
            
            with open(config_path / "common.yaml", 'w') as f:
                yaml.dump(common_config, f)
                
            exchanges_path = config_path / "exchanges"
            exchanges_path.mkdir()
            
            exchange_config = {
                'exchange': {
                    'name': 'Test Exchange',
                    'code': 'TEST',
                    'base_url': 'https://example.com'
                },
                'selectors': {
                    'company_name': ['h1'],
                    'company_cards': '.company'
                }
            }
            
            with open(exchanges_path / "test.yaml", 'w') as f:
                yaml.dump(exchange_config, f)
                
            config_manager = ConfigManager(str(config_path))
            async_config = AsyncScrapingConfig(max_concurrent_requests=2)
            
            scraper = AsyncScraper('test', config_manager.load_exchange_config('test'), async_config)
            
            # Test rate limiter creation
            rate_limiter = scraper.rate_limiter_manager.get_rate_limiter('test')
            assert rate_limiter.name == 'test'


class TestEndToEndIntegration:
    """Test end-to-end integration scenarios."""
    
    def test_config_loading_with_validation(self):
        """Test complete configuration loading with validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            
            # Create valid config files
            common_config = {
                'scraping': {'max_retries': 3, 'retry_delay_seconds': 2, 'default_timeout': 30, 'page_load_wait': 3},
                'browser': {'headless': True, 'window_size': '1920,1080', 'user_agent': 'Test Agent'},
                'logging': {'level': 'INFO', 'format': '%(asctime)s - %(message)s'},
                'output': {'default_format': 'xlsx'}
            }
            
            with open(config_path / "common.yaml", 'w') as f:
                yaml.dump(common_config, f)
                
            exchanges_path = config_path / "exchanges"
            exchanges_path.mkdir()
            
            exchange_config = {
                'exchange': {
                    'name': 'Integration Test Exchange',
                    'code': 'ITEST',
                    'base_url': 'https://example.com',
                    'listing_url': 'https://example.com/companies'
                },
                'selectors': {
                    'company_name': ['h1.company-title', 'h2.title'],
                    'company_cards': '.company-card a',
                    'sector': ['.sector', '.industry'],
                }
            }
            
            with open(exchanges_path / "itest.yaml", 'w') as f:
                yaml.dump(exchange_config, f)
                
            # Test configuration loading
            config_manager = ConfigManager(str(config_path), validate=True)
            
            # Should load without validation errors
            exchange_config_loaded = config_manager.load_exchange_config('itest')
            
            # Verify config merging worked
            assert 'scraping' in exchange_config_loaded  # From common
            assert 'exchange' in exchange_config_loaded  # From exchange
            assert exchange_config_loaded['exchange']['name'] == 'Integration Test Exchange'
            assert exchange_config_loaded['scraping']['max_retries'] == 3
            
    def test_invalid_config_handling(self):
        """Test handling of invalid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            
            # Create invalid config
            invalid_config = {
                'scraping': {
                    'max_retries': -1,  # Invalid
                    'retry_delay_seconds': 'invalid'  # Invalid type
                }
                # Missing required sections
            }
            
            with open(config_path / "common.yaml", 'w') as f:
                yaml.dump(invalid_config, f)
                
            # Should raise validation error
            with pytest.raises(ConfigValidationError):
                ConfigManager(str(config_path), validate=True)
                
    def test_data_model_serialization(self):
        """Test data model serialization for output."""
        company = Company(
            symbol="TEST",
            name="Test Company",
            exchange="TEST_EXCHANGE",
            sector="Technology"
        )
        
        company_dict = company.to_dict()
        assert company_dict['Symbol'] == "TEST"
        assert company_dict['Company Name'] == "Test Company"
        assert company_dict['Exchange'] == "TEST_EXCHANGE"
        assert company_dict['Sector'] == "Technology"
        
        details = CompanyDetails(
            symbol="TEST",
            company_name="Test Company",
            exchange="TEST_EXCHANGE",
            incorporation_date="2020-01-01",
            share_capital="1000000"
        )
        
        details_dict = details.to_dict()
        assert details_dict['Symbol'] == "TEST"
        assert details_dict['Incorporation Date'] == "2020-01-01"
        
        board_member = BoardMember(
            company_symbol="TEST",
            company_name="Test Company",
            exchange="TEST_EXCHANGE",
            name="John Doe",
            position="CEO",
            role_category="Executive"
        )
        
        member_dict = board_member.to_dict()
        assert member_dict['Company Symbol'] == "TEST"
        assert member_dict['Name'] == "John Doe"
        assert member_dict['Position'] == "CEO"


if __name__ == "__main__":
    pytest.main([__file__])