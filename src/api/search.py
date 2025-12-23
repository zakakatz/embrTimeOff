"""
Full-Text Search API Endpoints

Provides search endpoints for employee directory and documents
with ranking, pagination, and analytics.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.fulltext_search_service import (
    FullTextSearchService,
    SearchConfig,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
    get_search_service,
)

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SearchRequest(BaseModel):
    """Search request body."""
    
    query: str = Field(..., min_length=1, max_length=500, description="Search query text")
    search_type: str = Field(default="employee", description="Type: employee, document, department, combined")
    
    # Filters
    department_ids: List[int] = Field(default_factory=list, description="Filter by department IDs")
    location_ids: List[int] = Field(default_factory=list, description="Filter by location IDs")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Results per page")
    
    # Search options
    use_phrase_search: bool = Field(default=False, description="Enable phrase search with quotes")
    use_boolean_operators: bool = Field(default=True, description="Enable AND/OR operators")
    include_partial_matches: bool = Field(default=True, description="Include prefix matches")
    highlight: bool = Field(default=True, description="Highlight matching terms")
    min_score: Optional[float] = Field(None, ge=0, le=1, description="Minimum relevance score")


class SearchResultResponse(BaseModel):
    """Individual search result."""
    
    id: int
    type: str
    score: float
    rank: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    highlighted_title: Optional[str] = None
    highlighted_description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponseModel(BaseModel):
    """Search response."""
    
    query: str
    search_type: str
    results: List[SearchResultResponse]
    
    # Pagination
    page: int
    page_size: int
    total_results: int
    total_pages: int
    has_next: bool
    has_previous: bool
    
    # Performance
    execution_time_ms: int
    parsed_query: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)


class ClickTrackRequest(BaseModel):
    """Request to track a search result click."""
    
    search_id: int
    result_type: str
    result_id: int
    result_position: int


class PopularSearchResponse(BaseModel):
    """Popular search query."""
    
    query: str
    count: int
    avg_results: float


class SearchMetricsResponse(BaseModel):
    """Search performance metrics."""
    
    total_searches: int
    unique_users: int
    avg_execution_time_ms: float
    p95_execution_time_ms: float
    avg_results_per_search: float
    zero_result_rate: float
    click_through_rate: float
    period_start: datetime
    period_end: datetime


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "",
    response_model=SearchResponseModel,
    summary="Execute search",
    description="Execute a full-text search with ranking and pagination",
)
async def execute_search(
    request: SearchRequest,
    search_service: FullTextSearchService = Depends(get_search_service),
) -> SearchResponseModel:
    """
    Execute a full-text search.
    
    Supports:
    - Employee directory search (name, email, job title)
    - Document search (title, content, metadata)
    - Combined search across all types
    - Boolean operators (AND, OR, -)
    - Phrase search with quotes
    - Partial/prefix matching
    """
    try:
        search_type = SearchType(request.search_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search type: {request.search_type}. "
                   f"Valid types: {[t.value for t in SearchType]}"
        )
    
    query = SearchQuery(
        query=request.query,
        search_type=search_type,
        department_ids=request.department_ids,
        location_ids=request.location_ids,
        is_active=request.is_active,
        page=request.page,
        page_size=request.page_size,
        use_phrase_search=request.use_phrase_search,
        use_boolean_operators=request.use_boolean_operators,
        include_partial_matches=request.include_partial_matches,
        highlight=request.highlight,
        min_score=request.min_score,
    )
    
    response = search_service.search(query)
    
    # Check execution time
    if response.execution_time_ms > 500:
        # Log slow query but still return results
        import logging
        logging.warning(
            f"Slow search query: {response.execution_time_ms}ms - '{request.query}'"
        )
    
    return SearchResponseModel(
        query=response.query,
        search_type=response.search_type,
        results=[
            SearchResultResponse(
                id=r.id,
                type=r.result_type,
                score=r.score,
                rank=r.rank,
                title=r.title,
                subtitle=r.subtitle,
                description=r.description,
                highlighted_title=r.highlighted_title,
                highlighted_description=r.highlighted_description,
                metadata=r.metadata,
            )
            for r in response.results
        ],
        page=response.page,
        page_size=response.page_size,
        total_results=response.total_results,
        total_pages=response.total_pages,
        has_next=response.has_next,
        has_previous=response.has_previous,
        execution_time_ms=response.execution_time_ms,
        parsed_query=response.parsed_query,
        suggestions=response.suggestions,
    )


@router.get(
    "/employees",
    response_model=SearchResponseModel,
    summary="Search employees",
    description="Quick search endpoint for employee directory",
)
async def search_employees(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    search_service: FullTextSearchService = Depends(get_search_service),
) -> SearchResponseModel:
    """Quick employee search endpoint."""
    request = SearchRequest(
        query=q,
        search_type="employee",
        department_ids=[department_id] if department_id else [],
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return await execute_search(request, search_service)


@router.get(
    "/documents",
    response_model=SearchResponseModel,
    summary="Search documents",
    description="Quick search endpoint for documents",
)
async def search_documents(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department_id: Optional[int] = Query(None),
    search_service: FullTextSearchService = Depends(get_search_service),
) -> SearchResponseModel:
    """Quick document search endpoint."""
    request = SearchRequest(
        query=q,
        search_type="document",
        department_ids=[department_id] if department_id else [],
        page=page,
        page_size=page_size,
    )
    return await execute_search(request, search_service)


@router.post(
    "/track-click",
    summary="Track search result click",
    description="Track when a user clicks on a search result",
)
async def track_click(
    request: ClickTrackRequest,
    search_service: FullTextSearchService = Depends(get_search_service),
) -> Dict[str, Any]:
    """Track a click on a search result for analytics."""
    search_service.track_click(
        search_id=request.search_id,
        result_type=request.result_type,
        result_id=request.result_id,
        result_position=request.result_position,
    )
    
    return {"status": "tracked"}


# =============================================================================
# Analytics Endpoints
# =============================================================================

@router.get(
    "/analytics/popular",
    response_model=List[PopularSearchResponse],
    summary="Get popular searches",
    description="Get most popular search queries",
)
async def get_popular_searches(
    search_type: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    search_service: FullTextSearchService = Depends(get_search_service),
) -> List[PopularSearchResponse]:
    """Get most popular search queries."""
    type_filter = None
    if search_type:
        try:
            type_filter = SearchType(search_type)
        except ValueError:
            pass
    
    popular = search_service.get_popular_searches(
        search_type=type_filter,
        days=days,
        limit=limit,
    )
    
    return [
        PopularSearchResponse(
            query=p["query"],
            count=p["count"],
            avg_results=p["avg_results"],
        )
        for p in popular
    ]


@router.get(
    "/analytics/metrics",
    response_model=SearchMetricsResponse,
    summary="Get search metrics",
    description="Get search performance metrics",
)
async def get_search_metrics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    search_service: FullTextSearchService = Depends(get_search_service),
) -> SearchMetricsResponse:
    """Get search performance metrics."""
    from datetime import timedelta
    
    if not end_date:
        end_date = datetime.now(timezone.utc)
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    metrics = search_service.get_search_metrics(start_date, end_date)
    
    return SearchMetricsResponse(
        total_searches=metrics["total_searches"],
        unique_users=metrics["unique_users"],
        avg_execution_time_ms=metrics["avg_execution_time_ms"],
        p95_execution_time_ms=metrics["p95_execution_time_ms"],
        avg_results_per_search=metrics["avg_results_per_search"],
        zero_result_rate=metrics["zero_result_rate"],
        click_through_rate=metrics["click_through_rate"],
        period_start=start_date,
        period_end=end_date,
    )


@router.get(
    "/suggestions",
    summary="Get query suggestions",
    description="Get search query suggestions based on input",
)
async def get_suggestions(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(5, ge=1, le=10),
    search_service: FullTextSearchService = Depends(get_search_service),
) -> List[str]:
    """Get query suggestions for autocomplete."""
    return search_service.get_query_suggestions(q, limit)


@router.get(
    "/config",
    summary="Get search configuration",
    description="Get current search configuration",
)
async def get_search_config(
    search_service: FullTextSearchService = Depends(get_search_service),
) -> Dict[str, Any]:
    """Get search configuration."""
    config = search_service.config
    
    return {
        "default_page_size": config.default_page_size,
        "max_page_size": config.max_page_size,
        "max_execution_time_ms": config.max_execution_time_ms,
        "weights": config.weights,
        "fuzzy_matching": config.fuzzy_matching,
        "highlight_results": config.highlight_results,
        "search_types": [t.value for t in SearchType],
    }

