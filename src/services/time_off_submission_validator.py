"""Time-off request submission validation logic.

Provides validation logic that evaluates time-off requests against policy
constraints and calculates balance projections to ensure requests meet all
requirements before being submitted.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
from uuid import UUID

from src.schemas.time_off_submission import (
    AccrualSchedule,
    BalanceCalculationInput,
    BalanceProjection,
    BlackoutPeriod,
    PendingRequestSummary,
    PolicyViolation,
    RequestValidationResult,
    ViolationSeverity,
    ViolationType,
)


# =============================================================================
# Policy Configuration Interface
# =============================================================================

@dataclass
class PolicyRules:
    """
    Policy rules provided by external policy engine.
    
    Contains the constraints and limits that requests must comply with.
    """
    
    policy_id: UUID
    policy_name: str
    
    # Balance constraints
    allow_negative_balance: bool = False
    max_negative_balance: Decimal = Decimal("0")
    
    # Notice period constraints
    minimum_notice_days: int = 0
    maximum_advance_days: int = 365
    
    # Duration constraints
    minimum_hours: Decimal = Decimal("0.5")
    maximum_hours: Optional[Decimal] = None
    minimum_increment_hours: Decimal = Decimal("0.5")
    maximum_consecutive_days: Optional[int] = None
    
    # Blackout periods
    blackout_periods: List[BlackoutPeriod] = None
    
    # Request type specific rules
    request_type: str = "vacation"
    requires_approval: bool = True
    approval_levels: int = 1
    
    def __post_init__(self):
        if self.blackout_periods is None:
            self.blackout_periods = []


class BalanceProvider(Protocol):
    """Protocol for balance data providers."""
    
    def get_current_balance(
        self,
        employee_id: UUID,
        policy_id: UUID,
        as_of_date: date,
    ) -> Decimal:
        """Get current balance for an employee and policy."""
        ...
    
    def get_scheduled_accruals(
        self,
        employee_id: UUID,
        policy_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[AccrualSchedule]:
        """Get scheduled accruals for a date range."""
        ...
    
    def get_pending_requests(
        self,
        employee_id: UUID,
        policy_id: UUID,
        exclude_request_id: Optional[UUID] = None,
    ) -> List[PendingRequestSummary]:
        """Get pending time-off requests."""
        ...


# =============================================================================
# Balance Validation
# =============================================================================

class BalanceValidator:
    """
    Validates request balance and calculates projections.
    
    Calculates projected balances by aggregating current balances
    with scheduled accruals, then subtracting pending and new
    request hours.
    """
    
    def __init__(self, balance_provider: Optional[BalanceProvider] = None):
        self.balance_provider = balance_provider
    
    def calculate_balance_projection(
        self,
        employee_id: UUID,
        policy_id: UUID,
        request_start_date: date,
        request_hours: Decimal,
        current_balance: Optional[Decimal] = None,
        scheduled_accruals: Optional[List[AccrualSchedule]] = None,
        pending_requests: Optional[List[PendingRequestSummary]] = None,
        exclude_request_id: Optional[UUID] = None,
    ) -> BalanceProjection:
        """
        Calculate the balance projection for a request.
        
        Args:
            employee_id: ID of the employee
            policy_id: ID of the policy
            request_start_date: Start date of the request
            request_hours: Hours being requested
            current_balance: Optional pre-fetched current balance
            scheduled_accruals: Optional pre-fetched accruals
            pending_requests: Optional pre-fetched pending requests
            exclude_request_id: Request ID to exclude from pending calculation
        
        Returns:
            BalanceProjection with calculated values
        """
        today = date.today()
        
        # Get current balance
        if current_balance is None and self.balance_provider:
            current_balance = self.balance_provider.get_current_balance(
                employee_id, policy_id, today
            )
        elif current_balance is None:
            current_balance = Decimal("0")
        
        # Get scheduled accruals up to request start date
        total_accruals = Decimal("0")
        if scheduled_accruals:
            for accrual in scheduled_accruals:
                if accrual.accrual_date <= request_start_date:
                    total_accruals += accrual.accrual_hours
        elif self.balance_provider:
            accruals = self.balance_provider.get_scheduled_accruals(
                employee_id, policy_id, today, request_start_date
            )
            total_accruals = sum(a.accrual_hours for a in accruals)
        
        # Calculate projected balance
        projected_balance = current_balance + total_accruals
        
        # Get pending requests
        total_pending = Decimal("0")
        if pending_requests:
            for pending in pending_requests:
                if exclude_request_id and pending.request_id == exclude_request_id:
                    continue
                total_pending += pending.hours_requested
        elif self.balance_provider:
            pending_list = self.balance_provider.get_pending_requests(
                employee_id, policy_id, exclude_request_id
            )
            total_pending = sum(p.hours_requested for p in pending_list)
        
        # Calculate available balance
        available_balance = projected_balance - total_pending
        
        # Calculate balance after request
        balance_after_request = available_balance - request_hours
        
        return BalanceProjection(
            policy_id=policy_id,
            current_balance=current_balance,
            scheduled_accruals=total_accruals,
            projected_balance=projected_balance,
            pending_requests=total_pending,
            available_balance=available_balance,
            calculation_date=today,
            request_hours=request_hours,
            balance_after_request=balance_after_request,
        )
    
    def validate_balance(
        self,
        balance_projection: BalanceProjection,
        policy_rules: PolicyRules,
    ) -> List[PolicyViolation]:
        """
        Validate balance against policy rules.
        
        Args:
            balance_projection: The calculated balance projection
            policy_rules: Policy rules to validate against
        
        Returns:
            List of policy violations (if any)
        """
        violations = []
        
        if balance_projection.balance_after_request is None:
            return violations
        
        balance_after = balance_projection.balance_after_request
        
        # Check for negative balance
        if balance_after < Decimal("0"):
            if not policy_rules.allow_negative_balance:
                violations.append(PolicyViolation(
                    violation_type=ViolationType.NEGATIVE_BALANCE,
                    message=(
                        f"Request would result in a negative balance of "
                        f"{balance_after} hours. Current available: "
                        f"{balance_projection.available_balance} hours, "
                        f"Requested: {balance_projection.request_hours} hours"
                    ),
                    field="hours_requested",
                    severity=ViolationSeverity.ERROR,
                    policy_id=policy_rules.policy_id,
                    policy_name=policy_rules.policy_name,
                    threshold_value="0",
                    actual_value=str(balance_after),
                ))
            elif abs(balance_after) > policy_rules.max_negative_balance:
                violations.append(PolicyViolation(
                    violation_type=ViolationType.NEGATIVE_BALANCE,
                    message=(
                        f"Request would exceed maximum allowed negative balance. "
                        f"Projected: {balance_after} hours, "
                        f"Maximum allowed: -{policy_rules.max_negative_balance} hours"
                    ),
                    field="hours_requested",
                    severity=ViolationSeverity.ERROR,
                    policy_id=policy_rules.policy_id,
                    policy_name=policy_rules.policy_name,
                    threshold_value=str(-policy_rules.max_negative_balance),
                    actual_value=str(balance_after),
                ))
            else:
                # Negative but within allowed limit - warning only
                violations.append(PolicyViolation(
                    violation_type=ViolationType.NEGATIVE_BALANCE,
                    message=(
                        f"Request will result in a negative balance of "
                        f"{balance_after} hours"
                    ),
                    field="hours_requested",
                    severity=ViolationSeverity.WARNING,
                    policy_id=policy_rules.policy_id,
                    policy_name=policy_rules.policy_name,
                ))
        
        return violations


# =============================================================================
# Blackout Date Validation
# =============================================================================

class BlackoutDateValidator:
    """
    Validates request dates against blackout periods.
    
    Checks request dates against policy-defined restricted
    periods and generates appropriate violations.
    """
    
    def validate_blackout_dates(
        self,
        start_date: date,
        end_date: date,
        blackout_periods: List[BlackoutPeriod],
        policy_id: Optional[UUID] = None,
        department_id: Optional[int] = None,
    ) -> List[PolicyViolation]:
        """
        Check request dates against blackout periods.
        
        Args:
            start_date: Request start date
            end_date: Request end date
            blackout_periods: List of blackout periods to check
            policy_id: Optional policy ID to filter blackouts
            department_id: Optional department ID to filter blackouts
        
        Returns:
            List of policy violations for blackout conflicts
        """
        violations = []
        
        for blackout in blackout_periods:
            # Check if blackout applies to this policy/department
            if blackout.policy_id and policy_id and blackout.policy_id != policy_id:
                continue
            if blackout.department_id and department_id and blackout.department_id != department_id:
                continue
            
            # Check for overlap
            if blackout.overlaps_with(start_date, end_date):
                overlapping_dates = blackout.get_overlapping_dates(start_date, end_date)
                
                # Determine severity based on enforcement
                severity = (
                    ViolationSeverity.ERROR
                    if blackout.is_enforced
                    else ViolationSeverity.WARNING
                )
                
                # Format message
                dates_str = self._format_date_range(overlapping_dates)
                message = (
                    f"Request includes dates during a blackout period "
                    f"({blackout.start_date.isoformat()} to {blackout.end_date.isoformat()})"
                )
                if blackout.reason:
                    message += f": {blackout.reason}"
                message += f". Affected dates: {dates_str}"
                
                violations.append(PolicyViolation(
                    violation_type=ViolationType.BLACKOUT_DATE,
                    message=message,
                    field="dates",
                    severity=severity,
                    threshold_value=f"{blackout.start_date} to {blackout.end_date}",
                    actual_value=dates_str,
                ))
        
        return violations
    
    def _format_date_range(self, dates: List[date]) -> str:
        """Format a list of dates for display."""
        if not dates:
            return ""
        if len(dates) == 1:
            return dates[0].isoformat()
        if len(dates) <= 3:
            return ", ".join(d.isoformat() for d in dates)
        return f"{dates[0].isoformat()} to {dates[-1].isoformat()} ({len(dates)} days)"


# =============================================================================
# Notice Period Validation
# =============================================================================

class NoticePeriodValidator:
    """
    Validates request submission timing against policy requirements.
    
    Ensures requests are submitted within required timeframes
    as defined by policy rules.
    """
    
    def validate_notice_period(
        self,
        submission_date: date,
        request_start_date: date,
        minimum_notice_days: int,
        maximum_advance_days: int,
        policy_id: Optional[UUID] = None,
        policy_name: Optional[str] = None,
    ) -> List[PolicyViolation]:
        """
        Validate that request is submitted with proper notice.
        
        Args:
            submission_date: Date request is being submitted
            request_start_date: Requested start date
            minimum_notice_days: Required minimum notice in days
            maximum_advance_days: Maximum advance booking in days
            policy_id: Optional policy ID for violation context
            policy_name: Optional policy name for violation message
        
        Returns:
            List of policy violations for notice period issues
        """
        violations = []
        
        days_notice = (request_start_date - submission_date).days
        
        # Check minimum notice
        if minimum_notice_days > 0 and days_notice < minimum_notice_days:
            violations.append(PolicyViolation(
                violation_type=ViolationType.MINIMUM_NOTICE,
                message=(
                    f"Request must be submitted at least {minimum_notice_days} days "
                    f"in advance. You are submitting {days_notice} days before the "
                    f"requested start date."
                ),
                field="start_date",
                severity=ViolationSeverity.ERROR,
                policy_id=policy_id,
                policy_name=policy_name,
                threshold_value=f"{minimum_notice_days} days",
                actual_value=f"{days_notice} days",
            ))
        
        # Check maximum advance booking
        if maximum_advance_days > 0 and days_notice > maximum_advance_days:
            violations.append(PolicyViolation(
                violation_type=ViolationType.MINIMUM_NOTICE,
                message=(
                    f"Request cannot be submitted more than {maximum_advance_days} days "
                    f"in advance. You are submitting {days_notice} days before the "
                    f"requested start date."
                ),
                field="start_date",
                severity=ViolationSeverity.ERROR,
                policy_id=policy_id,
                policy_name=policy_name,
                threshold_value=f"max {maximum_advance_days} days",
                actual_value=f"{days_notice} days",
            ))
        
        # Check for past dates
        if request_start_date < submission_date:
            violations.append(PolicyViolation(
                violation_type=ViolationType.MINIMUM_NOTICE,
                message="Request start date cannot be in the past",
                field="start_date",
                severity=ViolationSeverity.ERROR,
                policy_id=policy_id,
                policy_name=policy_name,
            ))
        
        return violations


# =============================================================================
# Duration and Increment Validation
# =============================================================================

class DurationValidator:
    """
    Validates request duration against policy constraints.
    
    Checks minimum increment requirements and maximum duration
    constraints as specified in policy rules.
    """
    
    def validate_duration(
        self,
        start_date: date,
        end_date: date,
        hours_requested: Decimal,
        minimum_hours: Decimal,
        maximum_hours: Optional[Decimal],
        minimum_increment_hours: Decimal,
        maximum_consecutive_days: Optional[int],
        policy_id: Optional[UUID] = None,
        policy_name: Optional[str] = None,
    ) -> List[PolicyViolation]:
        """
        Validate request duration and increment.
        
        Args:
            start_date: Request start date
            end_date: Request end date
            hours_requested: Total hours requested
            minimum_hours: Minimum hours per request
            maximum_hours: Maximum hours per request (None = no limit)
            minimum_increment_hours: Minimum increment (e.g., 0.5 for half-hours)
            maximum_consecutive_days: Maximum days in a row (None = no limit)
            policy_id: Optional policy ID for violation context
            policy_name: Optional policy name for violation message
        
        Returns:
            List of policy violations for duration issues
        """
        violations = []
        
        # Check minimum hours
        if hours_requested < minimum_hours:
            violations.append(PolicyViolation(
                violation_type=ViolationType.MINIMUM_INCREMENT,
                message=(
                    f"Request must be for at least {minimum_hours} hours. "
                    f"Requested: {hours_requested} hours"
                ),
                field="hours_requested",
                severity=ViolationSeverity.ERROR,
                policy_id=policy_id,
                policy_name=policy_name,
                threshold_value=f"min {minimum_hours} hours",
                actual_value=f"{hours_requested} hours",
            ))
        
        # Check maximum hours
        if maximum_hours is not None and hours_requested > maximum_hours:
            violations.append(PolicyViolation(
                violation_type=ViolationType.MAXIMUM_DURATION,
                message=(
                    f"Request cannot exceed {maximum_hours} hours. "
                    f"Requested: {hours_requested} hours"
                ),
                field="hours_requested",
                severity=ViolationSeverity.ERROR,
                policy_id=policy_id,
                policy_name=policy_name,
                threshold_value=f"max {maximum_hours} hours",
                actual_value=f"{hours_requested} hours",
            ))
        
        # Check minimum increment
        if minimum_increment_hours > Decimal("0"):
            remainder = hours_requested % minimum_increment_hours
            if remainder != Decimal("0"):
                violations.append(PolicyViolation(
                    violation_type=ViolationType.MINIMUM_INCREMENT,
                    message=(
                        f"Request hours must be in increments of {minimum_increment_hours}. "
                        f"Requested: {hours_requested} hours"
                    ),
                    field="hours_requested",
                    severity=ViolationSeverity.ERROR,
                    policy_id=policy_id,
                    policy_name=policy_name,
                    threshold_value=f"{minimum_increment_hours} hour increments",
                    actual_value=f"{hours_requested} hours",
                ))
        
        # Check maximum consecutive days
        if maximum_consecutive_days is not None:
            days = (end_date - start_date).days + 1
            if days > maximum_consecutive_days:
                violations.append(PolicyViolation(
                    violation_type=ViolationType.MAXIMUM_DURATION,
                    message=(
                        f"Request cannot exceed {maximum_consecutive_days} consecutive days. "
                        f"Requested: {days} days"
                    ),
                    field="dates",
                    severity=ViolationSeverity.ERROR,
                    policy_id=policy_id,
                    policy_name=policy_name,
                    threshold_value=f"max {maximum_consecutive_days} days",
                    actual_value=f"{days} days",
                ))
        
        return violations


# =============================================================================
# Composite Request Validator
# =============================================================================

class TimeOffRequestSubmissionValidator:
    """
    Composite validator for time-off request submissions.
    
    Coordinates all validation checks and returns comprehensive
    validation results.
    """
    
    def __init__(self, balance_provider: Optional[BalanceProvider] = None):
        self.balance_validator = BalanceValidator(balance_provider)
        self.blackout_validator = BlackoutDateValidator()
        self.notice_validator = NoticePeriodValidator()
        self.duration_validator = DurationValidator()
    
    def validate_request(
        self,
        employee_id: UUID,
        start_date: date,
        end_date: date,
        hours_requested: Decimal,
        policy_rules: PolicyRules,
        submission_date: Optional[date] = None,
        current_balance: Optional[Decimal] = None,
        scheduled_accruals: Optional[List[AccrualSchedule]] = None,
        pending_requests: Optional[List[PendingRequestSummary]] = None,
        exclude_request_id: Optional[UUID] = None,
        department_id: Optional[int] = None,
    ) -> RequestValidationResult:
        """
        Perform comprehensive validation of a time-off request.
        
        Args:
            employee_id: ID of the requesting employee
            start_date: Requested start date
            end_date: Requested end date
            hours_requested: Total hours requested
            policy_rules: Policy rules to validate against
            submission_date: Date of submission (defaults to today)
            current_balance: Optional pre-fetched balance
            scheduled_accruals: Optional pre-fetched accruals
            pending_requests: Optional pre-fetched pending requests
            exclude_request_id: Request ID to exclude from pending
            department_id: Optional department for blackout filtering
        
        Returns:
            RequestValidationResult with all validation outcomes
        """
        if submission_date is None:
            submission_date = date.today()
        
        result = RequestValidationResult(
            is_valid=True,
            violations=[],
            warnings=[],
            validated_at=datetime.utcnow().isoformat(),
            employee_id=employee_id,
        )
        
        # Basic date validation
        if end_date < start_date:
            result.add_violation(
                ViolationType.MAXIMUM_DURATION,
                "End date cannot be before start date",
                "end_date",
                ViolationSeverity.ERROR,
            )
            # Return early - other validations won't make sense
            return result
        
        # Balance validation
        balance_projection = self.balance_validator.calculate_balance_projection(
            employee_id=employee_id,
            policy_id=policy_rules.policy_id,
            request_start_date=start_date,
            request_hours=hours_requested,
            current_balance=current_balance,
            scheduled_accruals=scheduled_accruals,
            pending_requests=pending_requests,
            exclude_request_id=exclude_request_id,
        )
        result.balance_projection = balance_projection
        
        balance_violations = self.balance_validator.validate_balance(
            balance_projection, policy_rules
        )
        for violation in balance_violations:
            result.violations.append(violation)
            if violation.severity == ViolationSeverity.ERROR:
                result.is_valid = False
        
        # Blackout date validation
        blackout_violations = self.blackout_validator.validate_blackout_dates(
            start_date=start_date,
            end_date=end_date,
            blackout_periods=policy_rules.blackout_periods,
            policy_id=policy_rules.policy_id,
            department_id=department_id,
        )
        for violation in blackout_violations:
            result.violations.append(violation)
            if violation.severity == ViolationSeverity.ERROR:
                result.is_valid = False
        
        # Notice period validation
        notice_violations = self.notice_validator.validate_notice_period(
            submission_date=submission_date,
            request_start_date=start_date,
            minimum_notice_days=policy_rules.minimum_notice_days,
            maximum_advance_days=policy_rules.maximum_advance_days,
            policy_id=policy_rules.policy_id,
            policy_name=policy_rules.policy_name,
        )
        for violation in notice_violations:
            result.violations.append(violation)
            if violation.severity == ViolationSeverity.ERROR:
                result.is_valid = False
        
        # Duration validation
        duration_violations = self.duration_validator.validate_duration(
            start_date=start_date,
            end_date=end_date,
            hours_requested=hours_requested,
            minimum_hours=policy_rules.minimum_hours,
            maximum_hours=policy_rules.maximum_hours,
            minimum_increment_hours=policy_rules.minimum_increment_hours,
            maximum_consecutive_days=policy_rules.maximum_consecutive_days,
            policy_id=policy_rules.policy_id,
            policy_name=policy_rules.policy_name,
        )
        for violation in duration_violations:
            result.violations.append(violation)
            if violation.severity == ViolationSeverity.ERROR:
                result.is_valid = False
        
        # Add advisory warnings
        self._add_advisory_warnings(result, balance_projection, policy_rules)
        
        return result
    
    def _add_advisory_warnings(
        self,
        result: RequestValidationResult,
        balance_projection: BalanceProjection,
        policy_rules: PolicyRules,
    ) -> None:
        """Add advisory warnings that don't block submission."""
        # Low balance warning
        if balance_projection.balance_after_request is not None:
            if (
                balance_projection.balance_after_request > Decimal("0")
                and balance_projection.balance_after_request < Decimal("8")
            ):
                result.add_warning(
                    f"After this request, you will have only "
                    f"{balance_projection.balance_after_request} hours remaining"
                )
        
        # High utilization warning
        if balance_projection.utilization_percentage > Decimal("80"):
            result.add_warning(
                f"You have used {balance_projection.utilization_percentage}% "
                f"of your {policy_rules.policy_name} balance"
            )
    
    def quick_balance_check(
        self,
        employee_id: UUID,
        policy_id: UUID,
        hours_requested: Decimal,
        allow_negative: bool = False,
        current_balance: Optional[Decimal] = None,
    ) -> Tuple[bool, str]:
        """
        Quick check if balance can accommodate a request.
        
        Args:
            employee_id: ID of the employee
            policy_id: ID of the policy
            hours_requested: Hours to request
            allow_negative: Whether negative balance is allowed
            current_balance: Optional pre-fetched balance
        
        Returns:
            Tuple of (can_accommodate, message)
        """
        projection = self.balance_validator.calculate_balance_projection(
            employee_id=employee_id,
            policy_id=policy_id,
            request_start_date=date.today(),
            request_hours=hours_requested,
            current_balance=current_balance,
        )
        
        can_accommodate = projection.can_accommodate(hours_requested, allow_negative)
        
        if can_accommodate:
            message = (
                f"Balance sufficient: {projection.available_balance} hours available, "
                f"{hours_requested} hours requested"
            )
        else:
            message = (
                f"Insufficient balance: {projection.available_balance} hours available, "
                f"{hours_requested} hours requested"
            )
        
        return can_accommodate, message

