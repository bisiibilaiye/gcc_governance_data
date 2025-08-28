from typing import Dict, Any, List
import logging
from models import Company, CompanyDetails, BoardMember


class DataValidator:
    """Validates extracted data against configuration rules."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Get validation rules
        validation_config = config.get('data_validation', {})
        self.required_company_fields = validation_config.get('required_company_fields', [])
        self.required_board_fields = validation_config.get('required_board_fields', [])
        
    def validate_company(self, company: Company) -> bool:
        """Validate that company has required fields."""
        if not company:
            return False
            
        company_dict = company.to_dict()
        
        for field in self.required_company_fields:
            # Map config field names to Company attribute names
            field_mapping = {
                'name': 'Company Name',
                'symbol': 'Symbol',
                'sector': 'Sector',
                'isin': 'ISIN'
            }
            
            mapped_field = field_mapping.get(field, field)
            value = company_dict.get(mapped_field)
            
            if not value or (isinstance(value, str) and not value.strip()):
                self.logger.warning(f"Company missing required field '{field}': {company.name}")
                return False
                
        return True
        
    def validate_company_details(self, details: CompanyDetails) -> bool:
        """Validate company details object."""
        if not details:
            return False
            
        # Basic validation - ensure we have company name and symbol
        if not details.company_name or not details.symbol:
            self.logger.warning("CompanyDetails missing company_name or symbol")
            return False
            
        return True
        
    def validate_board_member(self, member: BoardMember) -> bool:
        """Validate that board member has required fields."""
        if not member:
            return False
            
        member_dict = member.to_dict()
        
        for field in self.required_board_fields:
            # Map config field names to BoardMember attribute names
            field_mapping = {
                'name': 'Name',
                'position': 'Position',
                'company_name': 'Company Name'
            }
            
            mapped_field = field_mapping.get(field, field)
            value = member_dict.get(mapped_field)
            
            if not value or (isinstance(value, str) and not value.strip()):
                self.logger.warning(f"Board member missing required field '{field}': {member.name}")
                return False
                
        return True
        
    def validate_data_consistency(self, companies: List[Company], 
                                 company_details: List[CompanyDetails],
                                 board_members: List[BoardMember]) -> Dict[str, Any]:
        """Validate consistency across different data types."""
        issues = []
        
        # Check if we have details for all companies
        company_symbols = {c.symbol for c in companies}
        details_symbols = {d.symbol for d in company_details}
        
        missing_details = company_symbols - details_symbols
        if missing_details:
            issues.append(f"Missing company details for symbols: {missing_details}")
            
        # Check if board members reference valid companies
        board_company_symbols = {m.company_symbol for m in board_members}
        orphaned_board_members = board_company_symbols - company_symbols
        if orphaned_board_members:
            issues.append(f"Board members reference unknown companies: {orphaned_board_members}")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'stats': {
                'companies': len(companies),
                'company_details': len(company_details),
                'board_members': len(board_members),
                'companies_with_details': len(details_symbols),
                'companies_with_board_members': len(board_company_symbols)
            }
        }