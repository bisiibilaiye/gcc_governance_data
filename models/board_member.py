from dataclasses import dataclass
from typing import Optional


@dataclass
class BoardMember:
    """Board member or executive information."""
    company_symbol: str
    company_name: str
    exchange: str
    name: str
    position: str
    designation: Optional[str] = None
    member_type: Optional[str] = None  # Board Member, Executive, Independent, etc.
    role_category: Optional[str] = None  # Board, Executive, Audit Committee, etc.
    comments: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for pandas DataFrame."""
        return {
            'Company Symbol': self.company_symbol,
            'Company Name': self.company_name,
            'Exchange': self.exchange,
            'Name': self.name,
            'Position': self.position,
            'Designation': self.designation,
            'Member Type': self.member_type,
            'Role Category': self.role_category,
            'Comments': self.comments,
        }