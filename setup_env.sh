#!/bin/bash
# Setup script for GCC Scraper development environment

echo "🌟 Setting up GCC Stock Exchange Scraper environment..."
echo "Advanced concurrent streaming scraper for all GCC stock exchanges"
echo "================================================"

# Check if we're on the right Python version
python_version=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ "$python_version" != "3.10" ]; then
    echo "⚠️  Warning: This project is tested with Python 3.10, you're using $python_version"
    echo "   Some features may not work as expected with older Python versions"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
    echo "   Virtual environment created at $(pwd)/venv"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip to latest version..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "   All dependencies installed successfully"
else
    echo "❌ requirements.txt not found!"
    echo "   Please ensure requirements.txt is in the project directory"
    exit 1
fi

# Make scripts executable
chmod +x scraper.py setup_env.sh

# Verify ChromeDriver installation
echo "🌐 Checking Chrome/ChromeDriver setup..."
python -c "
try:
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager
    ChromeDriverManager().install()
    print('✅ ChromeDriver is ready')
except Exception as e:
    print(f'⚠️  ChromeDriver issue: {e}')
    print('   You may need to install Google Chrome first')
" 2>/dev/null

echo ""
echo "✅ Setup complete!"
echo "================================================"
echo ""
echo "🎯 Quick Start Examples:"
echo "  # Activate environment (run this every time)"
echo "  source venv/bin/activate"
echo ""
echo "  # List all available exchanges"
echo "  python scraper.py --list"
echo ""
echo "  # Scrape single exchange (all companies)"
echo "  python scraper.py dfm"
echo ""
echo "  # Test with limited companies"
echo "  python scraper.py saudi --limit 10"
echo ""
echo "  # Scrape all exchanges"
echo "  python scraper.py --all"
echo ""
echo "  # Enable verbose logging for debugging"
echo "  python scraper.py dfm --verbose"
echo ""
echo "  # Get help with all options"
echo "  python scraper.py --help"
echo ""
echo "📊 Supported Exchanges:"
echo "  • DFM (Dubai Financial Market) - UAE"
echo "  • Saudi Exchange (Tadawul) - Saudi Arabia"
echo "  • Boursa Kuwait - Kuwait"
echo "  • ADX (Abu Dhabi Securities Exchange) - UAE"
echo "  • Bahrain Bourse - Bahrain"
echo "  • MSX (Muscat Securities Market) - Oman"
echo ""
echo "🔧 Technical Details:"
echo "  📁 Virtual environment: $(pwd)/venv"
echo "  🐍 Python version: $(python --version)"
echo "  📦 Project directory: $(pwd)"
echo ""
echo "🐛 Troubleshooting:"
echo "  • If you encounter ChromeDriver issues, make sure Chrome is installed"
echo "  • For memory issues, reduce concurrency settings in config files"
echo "  • Enable --verbose flag for detailed logging during debugging"
echo "  • Check logs/ directory for detailed execution logs"
echo ""
echo "⚡ Happy scraping with concurrent processing and streaming output!"