"""API endpoints for location management."""

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Location
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Constants
# =============================================================================

# Valid timezone patterns (simplified validation)
VALID_TIMEZONES = {
    "UTC", "GMT",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Toronto", "America/Vancouver", "America/Mexico_City", "America/Sao_Paulo",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Rome",
    "Europe/Amsterdam", "Europe/Brussels", "Europe/Warsaw", "Europe/Moscow",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Singapore", "Asia/Seoul",
    "Asia/Mumbai", "Asia/Dubai", "Asia/Jakarta", "Asia/Bangkok", "Asia/Manila",
    "Australia/Sydney", "Australia/Melbourne", "Australia/Perth", "Australia/Brisbane",
    "Pacific/Auckland", "Pacific/Honolulu",
    "Africa/Cairo", "Africa/Lagos", "Africa/Johannesburg",
}


# =============================================================================
# Enums
# =============================================================================

class LocationType(str, Enum):
    """Type of location."""
    
    OFFICE = "office"
    WAREHOUSE = "warehouse"
    RETAIL = "retail"
    REMOTE = "remote"
    DATA_CENTER = "data_center"
    FACTORY = "factory"
    BRANCH = "branch"
    HEADQUARTERS = "headquarters"


class OverrideType(str, Enum):
    """Type of location override."""
    
    HOLIDAY_CALENDAR = "holiday_calendar"
    WORK_SCHEDULE = "work_schedule"
    OPERATING_HOURS = "operating_hours"
    POLICY = "policy"


# =============================================================================
# Request Models
# =============================================================================

class GeographicCoordinates(BaseModel):
    """Geographic coordinates for a location."""
    
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    
    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is within bounds."""
        if not -90.0 <= v <= 90.0:
            raise ValueError("Latitude must be between -90 and 90")
        return round(v, 6)
    
    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is within bounds."""
        if not -180.0 <= v <= 180.0:
            raise ValueError("Longitude must be between -180 and 180")
        return round(v, 6)


class AddressInfo(BaseModel):
    """Address information for a location."""
    
    street_address: str = Field(..., min_length=1, max_length=255)
    street_address_2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state_province: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: str = Field(..., min_length=2, max_length=100)
    
    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        """Validate country is not empty."""
        if not v or not v.strip():
            raise ValueError("Country is required")
        return v.strip()


class CreateLocationRequest(BaseModel):
    """Request to create a new location."""
    
    code: str = Field(
        ...,
        min_length=2,
        max_length=20,
        description="Unique location code",
        pattern=r"^[A-Z0-9_-]+$",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Location name")
    location_type: LocationType = Field(default=LocationType.OFFICE)
    
    # Address
    address: AddressInfo
    
    # Geographic data
    coordinates: Optional[GeographicCoordinates] = None
    
    # Timezone
    timezone: str = Field(..., description="IANA timezone identifier")
    
    # Capacity and configuration
    capacity: Optional[int] = Field(None, ge=0, description="Maximum capacity")
    operating_hours: Optional[str] = Field(
        None,
        max_length=255,
        description="Operating hours (e.g., '9:00-17:00 Mon-Fri')",
    )
    
    # Contact information
    phone_number: Optional[str] = Field(None, max_length=30)
    emergency_contact_info: Optional[str] = Field(None, max_length=255)
    
    # Regulatory info
    regulatory_jurisdiction: Optional[str] = Field(None, max_length=100)
    tax_jurisdiction: Optional[str] = Field(None, max_length=100)
    
    # Metadata
    facility_amenities: Optional[List[str]] = Field(
        None,
        description="List of facility amenities",
    )
    
    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate location code format."""
        if not re.match(r"^[A-Z0-9_-]+$", v):
            raise ValueError("Code must contain only uppercase letters, numbers, underscores, and hyphens")
        return v.upper()
    
    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is recognized."""
        if v not in VALID_TIMEZONES:
            # Also accept standard offset formats
            if not re.match(r"^[A-Za-z]+/[A-Za-z_]+$", v):
                raise ValueError(f"Invalid timezone: {v}")
        return v


class LocationOverrideRequest(BaseModel):
    """Request to create a location-specific override."""
    
    location_id: int = Field(..., description="Target location ID")
    override_type: OverrideType = Field(..., description="Type of override")
    
    # Override configuration
    configuration: Dict[str, Any] = Field(
        ...,
        description="Override configuration parameters",
    )
    
    # Validity period
    effective_date: Optional[datetime] = Field(None, description="When override takes effect")
    expiration_date: Optional[datetime] = Field(None, description="When override expires")
    
    # Reason and approval
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for override")
    requires_approval: bool = Field(default=False, description="Whether approval is required")
    
    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration is not empty."""
        if not v:
            raise ValueError("Configuration cannot be empty")
        return v


# =============================================================================
# Response Models
# =============================================================================

class LocationResponse(BaseModel):
    """Response for a location."""
    
    id: int
    code: str
    name: str
    location_type: str
    
    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    # Geographic
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinates_validated: bool = Field(default=False)
    
    # Timezone
    timezone: Optional[str] = None
    timezone_valid: bool = Field(default=True)
    
    # Configuration
    capacity: Optional[int] = None
    operating_hours: Optional[str] = None
    
    # Contact
    phone_number: Optional[str] = None
    emergency_contact_info: Optional[str] = None
    
    # Regulatory
    regulatory_jurisdiction: Optional[str] = None
    tax_jurisdiction: Optional[str] = None
    
    # Metadata
    facility_amenities: Optional[List[str]] = None
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LocationOverrideResponse(BaseModel):
    """Response for a location override."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    location_id: int
    location_name: str
    override_type: str
    
    configuration: Dict[str, Any]
    
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    
    reason: str
    status: str = Field(default="active")
    requires_approval: bool = Field(default=False)
    approval_status: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of validation."""
    
    field: str
    is_valid: bool
    message: Optional[str] = None
    validated_value: Optional[Any] = None


class CreateLocationResponse(BaseModel):
    """Response after creating a location."""
    
    location: LocationResponse
    validation_results: List[ValidationResult] = Field(default_factory=list)
    message: str = Field(default="Location created successfully")


# =============================================================================
# Helper Functions
# =============================================================================

def validate_geographic_coordinates(
    lat: Optional[float],
    lon: Optional[float],
) -> tuple[bool, str]:
    """Validate geographic coordinates."""
    if lat is None or lon is None:
        return True, "Coordinates not provided"
    
    if not -90.0 <= lat <= 90.0:
        return False, f"Invalid latitude: {lat}. Must be between -90 and 90."
    
    if not -180.0 <= lon <= 180.0:
        return False, f"Invalid longitude: {lon}. Must be between -180 and 180."
    
    # Check for null island (0, 0) which is often an error
    if lat == 0 and lon == 0:
        return False, "Coordinates (0, 0) detected - likely invalid"
    
    return True, "Coordinates validated"


def validate_timezone(tz: str) -> tuple[bool, str]:
    """Validate timezone string."""
    if not tz:
        return False, "Timezone is required"
    
    if tz in VALID_TIMEZONES:
        return True, f"Timezone {tz} is valid"
    
    # Check IANA format
    if re.match(r"^[A-Za-z]+/[A-Za-z_]+$", tz):
        return True, f"Timezone {tz} has valid IANA format"
    
    return False, f"Unrecognized timezone: {tz}"


def validate_override_configuration(
    override_type: OverrideType,
    config: Dict[str, Any],
) -> tuple[bool, str]:
    """Validate override configuration based on type."""
    if override_type == OverrideType.HOLIDAY_CALENDAR:
        required_keys = ["calendar_id"]
        if not any(k in config for k in required_keys):
            return False, "Holiday calendar override requires calendar_id"
        return True, "Holiday calendar configuration valid"
    
    elif override_type == OverrideType.WORK_SCHEDULE:
        if "schedule_id" not in config and "custom_hours" not in config:
            return False, "Work schedule override requires schedule_id or custom_hours"
        return True, "Work schedule configuration valid"
    
    elif override_type == OverrideType.OPERATING_HOURS:
        if "hours" not in config:
            return False, "Operating hours override requires hours specification"
        return True, "Operating hours configuration valid"
    
    elif override_type == OverrideType.POLICY:
        if "policy_id" not in config and "policy_overrides" not in config:
            return False, "Policy override requires policy_id or policy_overrides"
        return True, "Policy configuration valid"
    
    return True, "Configuration accepted"


# =============================================================================
# Dependency Injection
# =============================================================================

def get_current_user(
    request: Request,
    x_user_id: Annotated[Optional[str], Header(alias="X-User-ID")] = None,
    x_employee_id: Annotated[Optional[int], Header(alias="X-Employee-ID")] = None,
    x_user_role: Annotated[Optional[str], Header(alias="X-User-Role")] = None,
) -> CurrentUser:
    """Get current user from request headers."""
    user_id = None
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            pass
    
    roles = [UserRole.EMPLOYEE]
    if x_user_role:
        try:
            roles = [UserRole(x_user_role)]
        except ValueError:
            pass
    
    return get_mock_current_user(
        user_id=user_id,
        employee_id=x_employee_id,
        roles=roles,
    )


def require_admin(current_user: CurrentUser) -> CurrentUser:
    """Require admin role."""
    if not any(r in current_user.roles for r in [UserRole.ADMIN, UserRole.HR]):
        raise ForbiddenError(message="Admin access required")
    return current_user


# =============================================================================
# Router Setup
# =============================================================================

admin_locations_router = APIRouter(
    prefix="/api/admin",
    tags=["Location Management"],
)


# =============================================================================
# Endpoints
# =============================================================================

@admin_locations_router.post(
    "/locations",
    response_model=CreateLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Location",
    description="Create a new organizational location.",
)
async def create_location(
    request: CreateLocationRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CreateLocationResponse:
    """
    Create a new location.
    
    - Validates geographic coordinates
    - Validates timezone configuration
    - Generates unique location ID
    - Returns created location with validation results
    """
    # Check permissions
    require_admin(current_user)
    
    validation_results = []
    
    # Check for duplicate code
    existing = session.execute(
        select(Location).where(Location.code == request.code)
    ).scalar_one_or_none()
    
    if existing:
        raise ValidationError(
            message=f"Location with code '{request.code}' already exists",
            field_errors=[{"field": "code", "message": "Code already in use"}],
        )
    
    # Validate coordinates
    lat = request.coordinates.latitude if request.coordinates else None
    lon = request.coordinates.longitude if request.coordinates else None
    coord_valid, coord_msg = validate_geographic_coordinates(lat, lon)
    validation_results.append(ValidationResult(
        field="coordinates",
        is_valid=coord_valid,
        message=coord_msg,
        validated_value={"latitude": lat, "longitude": lon} if lat and lon else None,
    ))
    
    if not coord_valid and request.coordinates:
        raise ValidationError(
            message=coord_msg,
            field_errors=[{"field": "coordinates", "message": coord_msg}],
        )
    
    # Validate timezone
    tz_valid, tz_msg = validate_timezone(request.timezone)
    validation_results.append(ValidationResult(
        field="timezone",
        is_valid=tz_valid,
        message=tz_msg,
        validated_value=request.timezone,
    ))
    
    if not tz_valid:
        raise ValidationError(
            message=tz_msg,
            field_errors=[{"field": "timezone", "message": tz_msg}],
        )
    
    # Build full address string
    address_parts = [request.address.street_address]
    if request.address.street_address_2:
        address_parts.append(request.address.street_address_2)
    full_address = ", ".join(address_parts)
    
    # Convert amenities to JSON string
    amenities_str = None
    if request.facility_amenities:
        import json
        amenities_str = json.dumps(request.facility_amenities)
    
    # Create location
    location = Location(
        code=request.code,
        name=request.name,
        location_type=request.location_type.value,
        address=full_address,
        city=request.address.city,
        state=request.address.state_province,
        postal_code=request.address.postal_code,
        country=request.address.country,
        timezone=request.timezone,
        capacity=request.capacity,
        operating_hours=request.operating_hours,
        emergency_contact_info=request.emergency_contact_info,
        regulatory_jurisdiction=request.regulatory_jurisdiction,
        tax_jurisdiction=request.tax_jurisdiction,
        facility_amenities=amenities_str,
        is_active=True,
    )
    
    session.add(location)
    session.commit()
    session.refresh(location)
    
    # Build response
    amenities_list = None
    if location.facility_amenities:
        try:
            import json
            amenities_list = json.loads(location.facility_amenities)
        except (json.JSONDecodeError, TypeError):
            amenities_list = None
    
    location_response = LocationResponse(
        id=location.id,
        code=location.code,
        name=location.name,
        location_type=location.location_type or "office",
        address=location.address,
        city=location.city,
        state_province=location.state,
        postal_code=location.postal_code,
        country=location.country,
        timezone=location.timezone,
        timezone_valid=tz_valid,
        capacity=location.capacity,
        operating_hours=location.operating_hours,
        emergency_contact_info=location.emergency_contact_info,
        regulatory_jurisdiction=location.regulatory_jurisdiction,
        tax_jurisdiction=location.tax_jurisdiction,
        facility_amenities=amenities_list,
        is_active=location.is_active,
        created_at=datetime.utcnow(),
        coordinates_validated=coord_valid if request.coordinates else False,
    )
    
    return CreateLocationResponse(
        location=location_response,
        validation_results=validation_results,
        message="Location created successfully",
    )


@admin_locations_router.get(
    "/locations",
    response_model=List[LocationResponse],
    summary="List Locations",
    description="List all organizational locations.",
)
async def list_locations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(False, description="Include inactive locations"),
) -> List[LocationResponse]:
    """List all locations."""
    query = select(Location)
    if not include_inactive:
        query = query.where(Location.is_active == True)
    
    query = query.order_by(Location.name)
    
    result = session.execute(query)
    locations = list(result.scalars())
    
    response = []
    for loc in locations:
        amenities_list = None
        if loc.facility_amenities:
            try:
                import json
                amenities_list = json.loads(loc.facility_amenities)
            except (json.JSONDecodeError, TypeError):
                pass
        
        response.append(LocationResponse(
            id=loc.id,
            code=loc.code,
            name=loc.name,
            location_type=loc.location_type or "office",
            address=loc.address,
            city=loc.city,
            state_province=loc.state,
            postal_code=loc.postal_code,
            country=loc.country,
            timezone=loc.timezone,
            timezone_valid=loc.timezone in VALID_TIMEZONES if loc.timezone else False,
            capacity=loc.capacity,
            operating_hours=loc.operating_hours,
            emergency_contact_info=loc.emergency_contact_info,
            regulatory_jurisdiction=loc.regulatory_jurisdiction,
            tax_jurisdiction=loc.tax_jurisdiction,
            facility_amenities=amenities_list,
            is_active=loc.is_active,
            created_at=loc.created_at or datetime.utcnow(),
            updated_at=loc.updated_at,
        ))
    
    return response


@admin_locations_router.get(
    "/locations/{location_id}",
    response_model=LocationResponse,
    summary="Get Location",
    description="Get a specific location by ID.",
)
async def get_location(
    location_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    """Get a specific location."""
    location = session.get(Location, location_id)
    if not location:
        raise NotFoundError(message=f"Location {location_id} not found")
    
    amenities_list = None
    if location.facility_amenities:
        try:
            import json
            amenities_list = json.loads(location.facility_amenities)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return LocationResponse(
        id=location.id,
        code=location.code,
        name=location.name,
        location_type=location.location_type or "office",
        address=location.address,
        city=location.city,
        state_province=location.state,
        postal_code=location.postal_code,
        country=location.country,
        timezone=location.timezone,
        timezone_valid=location.timezone in VALID_TIMEZONES if location.timezone else False,
        capacity=location.capacity,
        operating_hours=location.operating_hours,
        emergency_contact_info=location.emergency_contact_info,
        regulatory_jurisdiction=location.regulatory_jurisdiction,
        tax_jurisdiction=location.tax_jurisdiction,
        facility_amenities=amenities_list,
        is_active=location.is_active,
        created_at=location.created_at or datetime.utcnow(),
        updated_at=location.updated_at,
    )


@admin_locations_router.post(
    "/location-overrides",
    response_model=LocationOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Location Override",
    description="Create a location-specific configuration override.",
)
async def create_location_override(
    request: LocationOverrideRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> LocationOverrideResponse:
    """
    Create a location-specific override.
    
    - Validates target location exists
    - Validates override configuration is compatible
    - Supports holiday calendar, work schedule, and policy overrides
    """
    # Check permissions
    require_admin(current_user)
    
    # Validate location exists
    location = session.get(Location, request.location_id)
    if not location:
        raise NotFoundError(message=f"Location {request.location_id} not found")
    
    # Validate configuration
    config_valid, config_msg = validate_override_configuration(
        request.override_type,
        request.configuration,
    )
    
    if not config_valid:
        raise ValidationError(
            message=config_msg,
            field_errors=[{"field": "configuration", "message": config_msg}],
        )
    
    # Validate date range
    if request.effective_date and request.expiration_date:
        if request.expiration_date <= request.effective_date:
            raise ValidationError(
                message="Expiration date must be after effective date",
                field_errors=[{"field": "expiration_date", "message": "Must be after effective date"}],
            )
    
    # In a real implementation, would store in database
    # For now, return the override response
    return LocationOverrideResponse(
        location_id=location.id,
        location_name=location.name,
        override_type=request.override_type.value,
        configuration=request.configuration,
        effective_date=request.effective_date,
        expiration_date=request.expiration_date,
        reason=request.reason,
        status="pending_approval" if request.requires_approval else "active",
        requires_approval=request.requires_approval,
        approval_status="pending" if request.requires_approval else "approved",
        created_by=str(current_user.user_id) if current_user.user_id else None,
    )


@admin_locations_router.put(
    "/locations/{location_id}",
    response_model=LocationResponse,
    summary="Update Location",
    description="Update an existing location.",
)
async def update_location(
    location_id: int,
    request: CreateLocationRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    """Update a location."""
    require_admin(current_user)
    
    location = session.get(Location, location_id)
    if not location:
        raise NotFoundError(message=f"Location {location_id} not found")
    
    # Check for duplicate code if changed
    if request.code != location.code:
        existing = session.execute(
            select(Location).where(
                Location.code == request.code,
                Location.id != location_id,
            )
        ).scalar_one_or_none()
        
        if existing:
            raise ValidationError(
                message=f"Location code '{request.code}' already in use",
                field_errors=[{"field": "code", "message": "Code already in use"}],
            )
    
    # Validate timezone
    tz_valid, tz_msg = validate_timezone(request.timezone)
    if not tz_valid:
        raise ValidationError(
            message=tz_msg,
            field_errors=[{"field": "timezone", "message": tz_msg}],
        )
    
    # Update fields
    location.code = request.code
    location.name = request.name
    location.location_type = request.location_type.value
    location.city = request.address.city
    location.state = request.address.state_province
    location.postal_code = request.address.postal_code
    location.country = request.address.country
    location.timezone = request.timezone
    location.capacity = request.capacity
    location.operating_hours = request.operating_hours
    location.emergency_contact_info = request.emergency_contact_info
    location.regulatory_jurisdiction = request.regulatory_jurisdiction
    location.tax_jurisdiction = request.tax_jurisdiction
    
    if request.facility_amenities:
        import json
        location.facility_amenities = json.dumps(request.facility_amenities)
    
    address_parts = [request.address.street_address]
    if request.address.street_address_2:
        address_parts.append(request.address.street_address_2)
    location.address = ", ".join(address_parts)
    
    session.commit()
    session.refresh(location)
    
    amenities_list = None
    if location.facility_amenities:
        try:
            import json
            amenities_list = json.loads(location.facility_amenities)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return LocationResponse(
        id=location.id,
        code=location.code,
        name=location.name,
        location_type=location.location_type or "office",
        address=location.address,
        city=location.city,
        state_province=location.state,
        postal_code=location.postal_code,
        country=location.country,
        timezone=location.timezone,
        timezone_valid=tz_valid,
        capacity=location.capacity,
        operating_hours=location.operating_hours,
        emergency_contact_info=location.emergency_contact_info,
        regulatory_jurisdiction=location.regulatory_jurisdiction,
        tax_jurisdiction=location.tax_jurisdiction,
        facility_amenities=amenities_list,
        is_active=location.is_active,
        created_at=location.created_at or datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@admin_locations_router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate Location",
    description="Deactivate a location (soft delete).",
)
async def deactivate_location(
    location_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    """Deactivate a location."""
    require_admin(current_user)
    
    location = session.get(Location, location_id)
    if not location:
        raise NotFoundError(message=f"Location {location_id} not found")
    
    location.is_active = False
    session.commit()

