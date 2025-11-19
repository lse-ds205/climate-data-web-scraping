"""
Metadata Filtering System

Supports filtering documents by:
- Entity names (multiple with OR)
- Entity types (multiple with OR)
- Date ranges (AND between min/max, OR for multiple ranges)
- Document types (multiple with OR)
- Languages (multiple with OR)

Filters use AND logic between different fields, OR logic within each field.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


@dataclass
class DateRange:
    """Date range filter"""
    min_date: Optional[str] = None  # ISO format: '2022-01-01'
    max_date: Optional[str] = None  # ISO format: '2023-12-31'
    
    def to_sql_condition(self, field_name: str = 'submission_date') -> tuple:
        """Generate SQL condition for date range"""
        conditions = []
        params = {}
        
        if self.min_date:
            conditions.append(f"{field_name} >= :min_date")
            params['min_date'] = self.min_date
        
        if self.max_date:
            conditions.append(f"{field_name} <= :max_date")
            params['max_date'] = self.max_date
        
        if conditions:
            return (" AND ".join(conditions), params)
        return (None, {})


@dataclass
class DocumentFilter:
    """
    Filter criteria for document selection.
    
    AND logic between fields, OR logic within fields.
    Example: (entity='Australia' OR entity='Brazil') AND (date='2022' OR date='2023')
    """
    entities: Optional[List[str]] = None  # ['Australia', 'Brazil'] - OR logic
    entity_types: Optional[List[str]] = None  # ['countries', 'companies'] - OR logic
    date_ranges: Optional[List[DateRange]] = None  # Multiple date ranges - OR logic
    document_types: Optional[List[str]] = None  # ['NDC', 'BTR'] - OR logic
    languages: Optional[List[str]] = None  # ['en', 'fr'] - OR logic
    countries: Optional[List[str]] = None  # Additional country filter (if entity_type is not country)
    
    def to_sql_conditions(self) -> tuple:
        """
        Convert filter to SQL WHERE conditions.
        Returns: (WHERE clause string, parameter dict)
        """
        conditions = []
        params = {}
        
        # Entity filter (OR within, AND with others)
        if self.entities:
            entity_placeholders = [f":entity_{i}" for i in range(len(self.entities))]
            conditions.append(f"country IN ({', '.join(entity_placeholders)})")
            for i, entity in enumerate(self.entities):
                params[f'entity_{i}'] = entity
        
        # Entity type filter (handled at chunk level via chunk_data)
        # This would need to be applied during retrieval, not SQL
        
        # Date ranges (OR logic - any range can match)
        if self.date_ranges:
            date_conditions = []
            for i, date_range in enumerate(self.date_ranges):
                range_cond, range_params = date_range.to_sql_condition()
                if range_cond:
                    # Prefix parameters to avoid conflicts
                    prefixed_params = {f"date_{i}_{k}": v for k, v in range_params.items()}
                    # Replace parameter names in condition
                    for old_key, new_key in zip(range_params.keys(), prefixed_params.keys()):
                        range_cond = range_cond.replace(f":{old_key}", f":{new_key}")
                    date_conditions.append(f"({range_cond})")
                    params.update(prefixed_params)
            
            if date_conditions:
                conditions.append(f"({' OR '.join(date_conditions)})")
        
        # Document types (OR logic)
        if self.document_types:
            doc_type_placeholders = [f":doc_type_{i}" for i in range(len(self.document_types))]
            conditions.append(f"document_type IN ({', '.join(doc_type_placeholders)})")
            for i, doc_type in enumerate(self.document_types):
                params[f'doc_type_{i}'] = doc_type
        
        # Languages (OR logic)
        if self.languages:
            lang_placeholders = [f":lang_{i}" for i in range(len(self.languages))]
            conditions.append(f"language IN ({', '.join(lang_placeholders)})")
            for i, lang in enumerate(self.languages):
                params[f'lang_{i}'] = lang
        
        # Countries (additional filter)
        if self.countries:
            country_placeholders = [f":country_{i}" for i in range(len(self.countries))]
            conditions.append(f"country IN ({', '.join(country_placeholders)})")
            for i, country in enumerate(self.countries):
                params[f'country_{i}'] = country
        
        if conditions:
            where_clause = " AND ".join(conditions)
            return (where_clause, params)
        
        return (None, {})
    
    def to_chunk_filter(self) -> Dict[str, Any]:
        """
        Convert to chunk-level filter (for chunk_data JSONB queries).
        Returns filter dict for use in retrieval logic.
        """
        filter_dict = {}
        
        if self.entities:
            filter_dict['entities'] = self.entities
        
        if self.entity_types:
            filter_dict['entity_types'] = self.entity_types
        
        if self.date_ranges:
            filter_dict['date_ranges'] = [
                {'min': dr.min_date, 'max': dr.max_date} for dr in self.date_ranges
            ]
        
        if self.document_types:
            filter_dict['document_types'] = self.document_types
        
        if self.languages:
            filter_dict['languages'] = self.languages
        
        return filter_dict


def parse_date_filter(date_str: str) -> List[DateRange]:
    """
    Parse date filter string into DateRange objects.
    
    Formats supported:
    - "2022" -> min: 2022-01-01, max: 2022-12-31
    - "2022:2023" -> min: 2022-01-01, max: 2023-12-31
    - "2022-01-01:2022-12-31" -> exact range
    - "2022,2023" -> two separate ranges (OR logic)
    """
    date_ranges = []
    
    # Split by comma for multiple ranges (OR logic)
    date_parts = [part.strip() for part in date_str.split(',')]
    
    for date_part in date_parts:
        if ':' in date_part:
            # Range format
            min_str, max_str = date_part.split(':', 1)
            min_str = min_str.strip()
            max_str = max_str.strip()
            
            # Handle year-only format
            if len(min_str) == 4:
                min_date = f"{min_str}-01-01"
            else:
                min_date = min_str
            
            if len(max_str) == 4:
                max_date = f"{max_str}-12-31"
            else:
                max_date = max_str
            
            date_ranges.append(DateRange(min_date=min_date, max_date=max_date))
        else:
            # Single year or date
            date_str_clean = date_part.strip()
            if len(date_str_clean) == 4:
                # Year only
                date_ranges.append(DateRange(
                    min_date=f"{date_str_clean}-01-01",
                    max_date=f"{date_str_clean}-12-31"
                ))
            else:
                # Specific date (use as both min and max)
                date_ranges.append(DateRange(
                    min_date=date_str_clean,
                    max_date=date_str_clean
                ))
    
    return date_ranges


def apply_filters(entities: List[str], filter_obj: DocumentFilter) -> List[str]:
    """
    Apply filters to a list of entities.
    This is a placeholder - actual filtering happens at retrieval level.
    """
    # For now, just return entities (filtering happens in retrieval)
    # In the future, this could filter entities based on available documents
    return entities


if __name__ == "__main__":
    # Test date parsing
    test_cases = [
        "2022",
        "2022:2023",
        "2022-01-01:2022-12-31",
        "2022,2023",
        "2021,2022,2023"
    ]
    
    print("Date Filter Parsing Tests")
    print("=" * 50)
    for test in test_cases:
        ranges = parse_date_filter(test)
        print(f"\nInput: {test}")
        for i, dr in enumerate(ranges):
            print(f"  Range {i+1}: {dr.min_date} to {dr.max_date}")

