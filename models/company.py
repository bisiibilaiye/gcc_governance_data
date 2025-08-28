from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Company:
    """Core company information."""
    symbol: str
    name: str
    exchange: str
    sector: Optional[str] = None
    isin: Optional[str] = None
    listing_date: Optional[str] = None
    market_segment: Optional[str] = None
    trading_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for pandas DataFrame."""
        return {
            'Symbol': self.symbol,
            'Company Name': self.name,
            'Exchange': self.exchange,
            'Sector': self.sector,
            'ISIN': self.isin,
            'Listing Date': self.listing_date,
            'Market Segment': self.market_segment,
            'Trading Name': self.trading_name,
        }


@dataclass
class CompanyDetails:
    """Detailed company profile information."""
    symbol: str
    company_name: str
    exchange: str
    incorporation_date: Optional[str] = None
    establishment_date: Optional[str] = None
    share_capital: Optional[str] = None
    company_type: Optional[str] = None
    auditor: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    registrar: Optional[str] = None
    commercial_id: Optional[str] = None
    activity: Optional[str] = None
    sub_sector: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for pandas DataFrame."""
        return {
            'Symbol': self.symbol,
            'Company Name': self.company_name,
            'Exchange': self.exchange,
            'Incorporation Date': self.incorporation_date,
            'Establishment Date': self.establishment_date,
            'Share Capital': self.share_capital,
            'Company Type': self.company_type,
            'Auditor': self.auditor,
            'Fiscal Year End': self.fiscal_year_end,
            'Registrar': self.registrar,
            'Commercial ID': self.commercial_id,
            'Activity': self.activity,
            'Sub Sector': self.sub_sector,
        }