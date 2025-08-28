from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class ScrapingStatus(Enum):
    """Scraping session status."""
    STARTED = "started"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ExchangeResult:
    """Results for a single exchange scraping."""
    exchange: str
    companies_found: int = 0
    companies_processed: int = 0
    board_members_extracted: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    status: ScrapingStatus = ScrapingStatus.STARTED
    output_file: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.companies_found == 0:
            return 0.0
        return (self.companies_processed / self.companies_found) * 100


@dataclass 
class ScrapingSession:
    """Overall scraping session tracking."""
    session_id: str
    start_time: datetime
    exchanges: List[str]
    results: Dict[str, ExchangeResult] = field(default_factory=dict)
    end_time: Optional[datetime] = None
    status: ScrapingStatus = ScrapingStatus.STARTED
    
    def add_exchange_result(self, result: ExchangeResult):
        """Add result for an exchange."""
        self.results[result.exchange] = result
        
    def get_overall_stats(self) -> Dict:
        """Get overall session statistics."""
        total_companies = sum(r.companies_found for r in self.results.values())
        total_processed = sum(r.companies_processed for r in self.results.values())
        total_board_members = sum(r.board_members_extracted for r in self.results.values())
        total_errors = sum(len(r.errors) for r in self.results.values())
        
        duration = None
        if self.end_time and self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            
        return {
            'session_id': self.session_id,
            'total_exchanges': len(self.exchanges),
            'total_companies_found': total_companies,
            'total_companies_processed': total_processed,
            'total_board_members': total_board_members,
            'total_errors': total_errors,
            'overall_success_rate': (total_processed / total_companies * 100) if total_companies > 0 else 0,
            'duration_seconds': duration,
            'status': self.status.value,
        }