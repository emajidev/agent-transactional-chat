from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class FilterPaginationQuery(BaseModel):
    """Query parameters for filtering and pagination."""
    
    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")
    limit: int = Field(default=10, ge=1, le=100, description="Number of items per page")
    filter: Optional[str] = Field(default=None, description="JSON string with filter criteria")
    sort: Optional[Dict[str, int]] = Field(default=None, description="Sort criteria (field: 1 for ASC, -1 for DESC)")
    fields: Optional[str] = Field(default=None, description="Comma-separated list of fields to select")


class StandardPageDto(BaseModel):
    """Standard paginated response DTO."""
    
    data: list = Field(..., description="List of items in the current page")
    limit: int = Field(..., description="Number of items per page")
    page: int = Field(..., description="Current page number")
    total: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    
    def __init__(self, data: list, limit: int, page: int, total: int, **kwargs):
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        super().__init__(data=data, limit=limit, page=page, total=total, total_pages=total_pages, **kwargs)

