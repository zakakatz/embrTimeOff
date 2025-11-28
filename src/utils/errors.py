"""Custom exception classes and error response utilities."""

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, List, Optional


@dataclass
class FieldError:
    """Error details for a specific field."""
    
    field: str
    message: str
    code: str = "invalid"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for JSON response."""
        return {
            "field": self.field,
            "message": self.message,
            "code": self.code,
        }


@dataclass
class ErrorResponse:
    """Structured error response for API endpoints."""
    
    message: str
    status_code: int
    error_code: str
    details: Optional[Dict[str, Any]] = None
    field_errors: List[FieldError] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "error": {
                "message": self.message,
                "code": self.error_code,
            }
        }
        
        if self.details:
            result["error"]["details"] = self.details
        
        if self.field_errors:
            result["error"]["field_errors"] = [
                fe.to_dict() for fe in self.field_errors
            ]
        
        return result


class APIError(Exception):
    """Base exception for API errors."""
    
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred"
    
    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        field_errors: Optional[List[FieldError]] = None,
    ):
        self.message = message or self.__class__.message
        self.details = details
        self.field_errors = field_errors or []
        super().__init__(self.message)
    
    def to_response(self) -> ErrorResponse:
        """Convert exception to structured error response."""
        return ErrorResponse(
            message=self.message,
            status_code=self.status_code,
            error_code=self.error_code,
            details=self.details,
            field_errors=self.field_errors,
        )


class ValidationError(APIError):
    """Exception for request validation failures."""
    
    status_code: int = HTTPStatus.BAD_REQUEST
    error_code: str = "validation_error"
    message: str = "Request validation failed"


class NotFoundError(APIError):
    """Exception for resource not found."""
    
    status_code: int = HTTPStatus.NOT_FOUND
    error_code: str = "not_found"
    message: str = "Resource not found"


class DuplicateError(APIError):
    """Exception for duplicate resource conflicts."""
    
    status_code: int = HTTPStatus.CONFLICT
    error_code: str = "duplicate"
    message: str = "Resource already exists"


class UnauthorizedError(APIError):
    """Exception for authentication failures."""
    
    status_code: int = HTTPStatus.UNAUTHORIZED
    error_code: str = "unauthorized"
    message: str = "Authentication required"


class ForbiddenError(APIError):
    """Exception for authorization failures."""
    
    status_code: int = HTTPStatus.FORBIDDEN
    error_code: str = "forbidden"
    message: str = "Access denied"


class DatabaseError(APIError):
    """Exception for database operation failures."""
    
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "database_error"
    message: str = "Database operation failed"


def create_field_error(field: str, message: str, code: str = "invalid") -> FieldError:
    """Helper to create a field error."""
    return FieldError(field=field, message=message, code=code)


def create_validation_error(field_errors: List[FieldError]) -> ValidationError:
    """Create a validation error with field-level details."""
    return ValidationError(
        message="Request validation failed",
        field_errors=field_errors,
    )


def create_not_found_error(resource_type: str, identifier: Any) -> NotFoundError:
    """Create a not found error for a specific resource."""
    return NotFoundError(
        message=f"{resource_type} not found",
        details={"resource_type": resource_type, "identifier": str(identifier)},
    )


def create_duplicate_error(
    resource_type: str,
    field: str,
    value: Any,
) -> DuplicateError:
    """Create a duplicate error for a specific field."""
    return DuplicateError(
        message=f"{resource_type} with {field} '{value}' already exists",
        field_errors=[
            FieldError(
                field=field,
                message=f"This {field} is already in use",
                code="duplicate",
            )
        ],
    )

