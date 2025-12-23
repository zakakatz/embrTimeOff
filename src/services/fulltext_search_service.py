"""
Full-Text Search Service

Implements PostgreSQL full-text search with GIN indexes for:
- Employee directory search
- Document content search
- Combined search functionality

Features:
- Ranked search results
- Query parsing (boolean operators, phrase search)
- Search analytics tracking
- Performance optimization
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, literal_column, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class SearchType(str, Enum):
    """Types of searchable content."""
    
    EMPLOYEE = "employee"
    DOCUMENT = "document"
    DEPARTMENT = "department"
    COMBINED = "combined"


@dataclass
class SearchConfig:
    """Configuration for search behavior."""
    
    default_page_size: int = 20
    max_page_size: int = 100
    max_execution_time_ms: int = 5000
    weights: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "employee": {
            "first_name": 1.0,
            "last_name": 1.0,
            "email": 0.8,
            "job_title": 0.6,
            "department": 0.5,
        },
        "document": {
            "title": 1.0,
            "content": 0.7,
            "tags": 0.5,
        },
    })
    fuzzy_matching: bool = True
    highlight_results: bool = True


@dataclass
class SearchQuery:
    """Search query parameters."""
    
    query: str
    search_type: SearchType = SearchType.EMPLOYEE
    department_ids: List[int] = field(default_factory=list)
    location_ids: List[int] = field(default_factory=list)
    is_active: Optional[bool] = None
    page: int = 1
    page_size: int = 20
    use_phrase_search: bool = False
    use_boolean_operators: bool = True
    include_partial_matches: bool = True
    highlight: bool = True
    min_score: Optional[float] = None
    user_id: Optional[int] = None  # For analytics


@dataclass
class SearchResult:
    """Individual search result."""
    
    id: int
    result_type: str
    score: float
    rank: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    highlighted_title: Optional[str] = None
    highlighted_description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Complete search response."""
    
    query: str
    search_type: str
    results: List[SearchResult]
    page: int
    page_size: int
    total_results: int
    total_pages: int
    has_next: bool
    has_previous: bool
    execution_time_ms: int
    parsed_query: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)


# =============================================================================
# Search Service
# =============================================================================

class FullTextSearchService:
    """
    Full-text search service using PostgreSQL.
    
    Provides:
    - Configurable search across multiple entity types
    - Ranked results with relevance scoring
    - Query parsing for boolean operators
    - Search analytics and performance tracking
    """
    
    def __init__(
        self,
        db: Session,
        config: Optional[SearchConfig] = None,
    ):
        self.db = db
        self.config = config or SearchConfig()
        self._tsquery_regex = re.compile(r'[^\w\s\-&|!:*()]', re.UNICODE)
    
    def search(self, query: SearchQuery) -> SearchResponse:
        """
        Execute a full-text search.
        
        Args:
            query: Search query parameters
            
        Returns:
            SearchResponse with ranked results
        """
        start_time = time.time()
        
        try:
            # Parse and validate query
            parsed_query = self._parse_query(query)
            
            # Execute search based on type
            if query.search_type == SearchType.EMPLOYEE:
                results, total = self._search_employees(query, parsed_query)
            elif query.search_type == SearchType.DOCUMENT:
                results, total = self._search_documents(query, parsed_query)
            elif query.search_type == SearchType.DEPARTMENT:
                results, total = self._search_departments(query, parsed_query)
            elif query.search_type == SearchType.COMBINED:
                results, total = self._search_combined(query, parsed_query)
            else:
                results, total = [], 0
            
            # Calculate pagination
            total_pages = (total + query.page_size - 1) // query.page_size if total > 0 else 0
            
            # Track search for analytics
            self._track_search(query, total, results)
            
            # Get suggestions if few results
            suggestions = []
            if total < 3 and query.query:
                suggestions = self.get_query_suggestions(query.query, limit=3)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return SearchResponse(
                query=query.query,
                search_type=query.search_type.value,
                results=results,
                page=query.page,
                page_size=query.page_size,
                total_results=total,
                total_pages=total_pages,
                has_next=query.page < total_pages,
                has_previous=query.page > 1,
                execution_time_ms=execution_time_ms,
                parsed_query=parsed_query,
                suggestions=suggestions,
            )
            
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return SearchResponse(
                query=query.query,
                search_type=query.search_type.value,
                results=[],
                page=query.page,
                page_size=query.page_size,
                total_results=0,
                total_pages=0,
                has_next=False,
                has_previous=False,
                execution_time_ms=execution_time_ms,
                parsed_query=None,
                suggestions=[],
            )
    
    def _parse_query(self, query: SearchQuery) -> str:
        """
        Parse query string into tsquery format.
        
        Supports:
        - Boolean operators: AND, OR, -, NOT
        - Phrase search with quotes
        - Prefix matching with *
        """
        raw_query = query.query.strip()
        
        if not raw_query:
            return ""
        
        # Handle phrase search (quoted strings)
        if query.use_phrase_search and '"' in raw_query:
            # Extract phrases and treat them as contiguous
            phrases = re.findall(r'"([^"]+)"', raw_query)
            remaining = re.sub(r'"[^"]*"', '', raw_query).strip()
            
            terms = []
            for phrase in phrases:
                # Join phrase words with <-> for phrase matching
                phrase_terms = phrase.split()
                if len(phrase_terms) > 1:
                    terms.append("(" + " <-> ".join(
                        self._sanitize_term(t) for t in phrase_terms
                    ) + ")")
                elif phrase_terms:
                    terms.append(self._sanitize_term(phrase_terms[0]))
            
            # Add remaining terms
            if remaining:
                for term in remaining.split():
                    terms.append(self._process_term(term, query))
            
            return " & ".join(terms) if terms else ""
        
        # Handle boolean operators
        if query.use_boolean_operators:
            terms = []
            raw_terms = raw_query.split()
            i = 0
            
            while i < len(raw_terms):
                term = raw_terms[i]
                
                # Handle NOT / -
                if term.upper() == "NOT" or term.startswith("-"):
                    if term.startswith("-"):
                        negated_term = term[1:]
                        if negated_term:
                            terms.append(f"!{self._sanitize_term(negated_term)}")
                    elif i + 1 < len(raw_terms):
                        i += 1
                        terms.append(f"!{self._sanitize_term(raw_terms[i])}")
                        
                # Handle OR
                elif term.upper() == "OR":
                    if terms and i + 1 < len(raw_terms):
                        last_term = terms.pop()
                        i += 1
                        next_term = self._process_term(raw_terms[i], query)
                        terms.append(f"({last_term} | {next_term})")
                        
                # Handle AND (explicit)
                elif term.upper() == "AND":
                    pass  # AND is default, skip
                    
                # Regular term
                else:
                    terms.append(self._process_term(term, query))
                
                i += 1
            
            return " & ".join(terms) if terms else ""
        
        # Simple query - AND all terms
        terms = [
            self._process_term(term, query)
            for term in raw_query.split()
            if term.strip()
        ]
        return " & ".join(terms) if terms else ""
    
    def _process_term(self, term: str, query: SearchQuery) -> str:
        """Process a single search term."""
        sanitized = self._sanitize_term(term)
        
        # Add prefix matching if enabled
        if query.include_partial_matches and sanitized and not sanitized.endswith(":*"):
            return f"{sanitized}:*"
        
        return sanitized
    
    def _sanitize_term(self, term: str) -> str:
        """Sanitize a search term for tsquery."""
        # Remove special characters except those used in tsquery
        sanitized = self._tsquery_regex.sub('', term)
        return sanitized.strip().lower()
    
    def _search_employees(
        self,
        query: SearchQuery,
        parsed_query: str,
    ) -> tuple[List[SearchResult], int]:
        """Search employee directory."""
        if not parsed_query:
            return [], 0
        
        try:
            # Build the tsquery
            tsquery = func.to_tsquery('english', parsed_query)
            
            # Build the search query
            # Using plainto_tsquery as fallback for simpler queries
            search_expression = text("""
                (
                    to_tsvector('english', 
                        COALESCE(first_name, '') || ' ' || 
                        COALESCE(last_name, '') || ' ' || 
                        COALESCE(email, '') || ' ' ||
                        COALESCE(job_title, '')
                    ) @@ to_tsquery('english', :query)
                )
            """)
            
            rank_expression = text("""
                ts_rank_cd(
                    to_tsvector('english', 
                        COALESCE(first_name, '') || ' ' || 
                        COALESCE(last_name, '') || ' ' || 
                        COALESCE(email, '') || ' ' ||
                        COALESCE(job_title, '')
                    ),
                    to_tsquery('english', :query)
                )
            """)
            
            # Base query
            base_query = self.db.query(
                Employee,
                rank_expression.bindparams(query=parsed_query).label('rank')
            ).filter(
                search_expression.bindparams(query=parsed_query)
            )
            
            # Apply filters
            if query.department_ids:
                base_query = base_query.filter(
                    Employee.department_id.in_(query.department_ids)
                )
            
            if query.location_ids:
                base_query = base_query.filter(
                    Employee.location_id.in_(query.location_ids)
                )
            
            if query.is_active is not None:
                base_query = base_query.filter(Employee.is_active == query.is_active)
            
            # Get total count
            total = base_query.count()
            
            # Apply pagination and ordering
            offset = (query.page - 1) * query.page_size
            results = base_query.order_by(
                text('rank DESC')
            ).offset(offset).limit(query.page_size).all()
            
            # Convert to SearchResult
            search_results = []
            for i, (employee, rank) in enumerate(results):
                # Create highlighted versions if enabled
                highlighted_title = None
                if query.highlight:
                    highlighted_title = self._highlight_match(
                        f"{employee.first_name} {employee.last_name}",
                        query.query
                    )
                
                search_results.append(SearchResult(
                    id=employee.id,
                    result_type="employee",
                    score=float(rank) if rank else 0.0,
                    rank=offset + i + 1,
                    title=f"{employee.first_name} {employee.last_name}",
                    subtitle=employee.job_title,
                    description=employee.email,
                    highlighted_title=highlighted_title,
                    highlighted_description=None,
                    metadata={
                        "employee_id": employee.id,
                        "email": employee.email,
                        "department_id": employee.department_id,
                        "location_id": employee.location_id,
                        "is_active": employee.is_active,
                    }
                ))
            
            return search_results, total
            
        except Exception as e:
            logger.error(f"Employee search error: {e}", exc_info=True)
            # Fallback to simple ILIKE search
            return self._search_employees_fallback(query)
    
    def _search_employees_fallback(
        self,
        query: SearchQuery,
    ) -> tuple[List[SearchResult], int]:
        """Fallback ILIKE search for employees."""
        search_term = f"%{query.query}%"
        
        base_query = self.db.query(Employee).filter(
            (Employee.first_name.ilike(search_term)) |
            (Employee.last_name.ilike(search_term)) |
            (Employee.email.ilike(search_term)) |
            (Employee.job_title.ilike(search_term))
        )
        
        if query.department_ids:
            base_query = base_query.filter(
                Employee.department_id.in_(query.department_ids)
            )
        
        if query.is_active is not None:
            base_query = base_query.filter(Employee.is_active == query.is_active)
        
        total = base_query.count()
        offset = (query.page - 1) * query.page_size
        results = base_query.offset(offset).limit(query.page_size).all()
        
        search_results = []
        for i, employee in enumerate(results):
            search_results.append(SearchResult(
                id=employee.id,
                result_type="employee",
                score=0.5,  # Default score for fallback
                rank=offset + i + 1,
                title=f"{employee.first_name} {employee.last_name}",
                subtitle=employee.job_title,
                description=employee.email,
                metadata={
                    "employee_id": employee.id,
                    "email": employee.email,
                    "department_id": employee.department_id,
                    "is_active": employee.is_active,
                }
            ))
        
        return search_results, total
    
    def _search_documents(
        self,
        query: SearchQuery,
        parsed_query: str,
    ) -> tuple[List[SearchResult], int]:
        """Search documents (placeholder - implement when document model exists)."""
        # Document search would be implemented similarly to employee search
        # when a Document model exists
        logger.info(f"Document search not implemented. Query: {query.query}")
        return [], 0
    
    def _search_departments(
        self,
        query: SearchQuery,
        parsed_query: str,
    ) -> tuple[List[SearchResult], int]:
        """Search departments."""
        from src.models.employee import Department
        
        if not parsed_query:
            return [], 0
        
        search_term = f"%{query.query}%"
        
        base_query = self.db.query(Department).filter(
            Department.name.ilike(search_term)
        )
        
        total = base_query.count()
        offset = (query.page - 1) * query.page_size
        results = base_query.offset(offset).limit(query.page_size).all()
        
        search_results = []
        for i, dept in enumerate(results):
            search_results.append(SearchResult(
                id=dept.id,
                result_type="department",
                score=0.8,
                rank=offset + i + 1,
                title=dept.name,
                subtitle=None,
                description=None,
                metadata={
                    "department_id": dept.id,
                }
            ))
        
        return search_results, total
    
    def _search_combined(
        self,
        query: SearchQuery,
        parsed_query: str,
    ) -> tuple[List[SearchResult], int]:
        """Search across all entity types."""
        all_results = []
        total = 0
        
        # Search each type
        emp_results, emp_total = self._search_employees(query, parsed_query)
        all_results.extend(emp_results)
        total += emp_total
        
        dept_results, dept_total = self._search_departments(query, parsed_query)
        all_results.extend(dept_results)
        total += dept_total
        
        # Sort by score
        all_results.sort(key=lambda r: r.score, reverse=True)
        
        # Apply pagination to combined results
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        paginated = all_results[start:end]
        
        # Re-rank
        for i, result in enumerate(paginated):
            result.rank = start + i + 1
        
        return paginated, total
    
    def _highlight_match(self, text: str, query: str) -> str:
        """
        Highlight matching terms in text.
        
        Uses <mark> tags for highlighting.
        """
        if not text or not query:
            return text
        
        highlighted = text
        for term in query.split():
            term = term.strip().lower()
            if len(term) < 2:
                continue
            
            # Case-insensitive replacement with highlighting
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted = pattern.sub(
                lambda m: f"<mark>{m.group()}</mark>",
                highlighted
            )
        
        return highlighted
    
    def _track_search(
        self,
        query: SearchQuery,
        total_results: int,
        results: List[SearchResult],
    ) -> None:
        """Track search for analytics."""
        try:
            # This would insert into a search_analytics table
            # For now, just log
            logger.info(
                f"Search tracked: query='{query.query}', "
                f"type={query.search_type.value}, "
                f"results={total_results}, "
                f"user_id={query.user_id}"
            )
        except Exception as e:
            logger.error(f"Failed to track search: {e}")
    
    def track_click(
        self,
        search_id: int,
        result_type: str,
        result_id: int,
        result_position: int,
    ) -> None:
        """Track click on a search result."""
        try:
            logger.info(
                f"Click tracked: search_id={search_id}, "
                f"result={result_type}:{result_id}, "
                f"position={result_position}"
            )
            # Would insert into search_click_analytics table
        except Exception as e:
            logger.error(f"Failed to track click: {e}")
    
    def get_query_suggestions(self, prefix: str, limit: int = 5) -> List[str]:
        """
        Get query suggestions based on prefix.
        
        Uses historical searches and common terms.
        """
        if len(prefix) < 2:
            return []
        
        suggestions = []
        
        try:
            # Get matching employee names
            search_term = f"{prefix}%"
            employees = self.db.query(
                Employee.first_name,
                Employee.last_name
            ).filter(
                (Employee.first_name.ilike(search_term)) |
                (Employee.last_name.ilike(search_term))
            ).limit(limit).all()
            
            for first, last in employees:
                name = f"{first} {last}"
                if name.lower().startswith(prefix.lower()):
                    suggestions.append(name)
        except Exception as e:
            logger.error(f"Failed to get suggestions: {e}")
        
        return suggestions[:limit]
    
    def get_popular_searches(
        self,
        search_type: Optional[SearchType] = None,
        days: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get most popular search queries."""
        # This would query from search_analytics table
        # Returning placeholder data
        return [
            {"query": "manager", "count": 150, "avg_results": 25.5},
            {"query": "engineering", "count": 120, "avg_results": 45.0},
            {"query": "remote", "count": 85, "avg_results": 30.2},
        ][:limit]
    
    def get_search_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Get search performance metrics."""
        # This would aggregate from search_analytics table
        # Returning placeholder metrics
        return {
            "total_searches": 5420,
            "unique_users": 245,
            "avg_execution_time_ms": 85.3,
            "p95_execution_time_ms": 250.0,
            "avg_results_per_search": 15.7,
            "zero_result_rate": 0.08,
            "click_through_rate": 0.42,
        }


# =============================================================================
# Dependency Injection
# =============================================================================

@lru_cache()
def get_search_config() -> SearchConfig:
    """Get cached search configuration."""
    return SearchConfig()


def get_search_service(
    db: Session = Depends(get_db),
    config: SearchConfig = Depends(get_search_config),
) -> FullTextSearchService:
    """Get search service instance."""
    return FullTextSearchService(db=db, config=config)
