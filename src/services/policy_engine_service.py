"""Policy engine service for evaluating employee eligibility and policy constraints."""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.employee import Employee, Location, Department
from src.models.time_off_policy import TimeOffPolicy, PolicyStatus
from src.schemas.employee_policy_info import (
    AccrualInfo,
    AccrualMethodDisplay,
    ApprovalInfo,
    BalanceInfo,
    BlackoutPeriod,
    DateConstraint,
    DocumentRequirement,
    EmployeePoliciesListResponse,
    EmployeePolicyResponse,
    NoticeRequirement,
    PolicyConstraintsResponse,
    PolicyTypeDisplay,
    RequestRules,
    UsageRestriction,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Policy Type Display Configuration
# =============================================================================

POLICY_TYPE_CONFIG = {
    "vacation": {
        "display": "Vacation",
        "icon": "beach",
        "color": "#4A90D9",
        "priority": 1,
    },
    "sick": {
        "display": "Sick Leave",
        "icon": "medical",
        "color": "#E57373",
        "priority": 2,
    },
    "personal": {
        "display": "Personal Time",
        "icon": "person",
        "color": "#81C784",
        "priority": 3,
    },
    "bereavement": {
        "display": "Bereavement",
        "icon": "heart",
        "color": "#9E9E9E",
        "priority": 6,
    },
    "parental": {
        "display": "Parental Leave",
        "icon": "family",
        "color": "#FFB74D",
        "priority": 4,
    },
    "jury_duty": {
        "display": "Jury Duty",
        "icon": "gavel",
        "color": "#7986CB",
        "priority": 7,
    },
    "floating_holiday": {
        "display": "Floating Holiday",
        "icon": "star",
        "color": "#4DB6AC",
        "priority": 5,
    },
    "unpaid": {
        "display": "Unpaid Leave",
        "icon": "calendar-x",
        "color": "#BDBDBD",
        "priority": 8,
    },
}

ACCRUAL_METHOD_DESCRIPTIONS = {
    "annual_lump_sum": "Full balance granted at the start of each year",
    "monthly_accrual": "Time-off accrues monthly throughout the year",
    "pay_period_accrual": "Time-off accrues with each pay period",
    "hours_worked": "Time-off accrues based on hours worked",
    "none": "No automatic accrual - balance granted manually",
}


class PolicyEngineService:
    """Service for policy eligibility evaluation and constraint queries."""

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session

    # =========================================================================
    # Eligibility Evaluation
    # =========================================================================

    def evaluate_employee_eligibility(
        self,
        employee: Employee,
        policy: TimeOffPolicy,
    ) -> Tuple[bool, str, Optional[date], Optional[int]]:
        """
        Evaluate if an employee is eligible for a policy.
        
        Returns:
            Tuple of (is_eligible, status_message, eligibility_start_date, waiting_period_remaining)
        """
        today = date.today()
        
        # Check if policy is active
        if policy.status != PolicyStatus.ACTIVE.value:
            return False, "Policy is not active", None, None
        
        # Check policy effective dates
        if policy.effective_date and policy.effective_date.date() > today:
            days_until = (policy.effective_date.date() - today).days
            return False, f"Policy not yet effective (starts in {days_until} days)", None, None
        
        if policy.expiry_date and policy.expiry_date.date() < today:
            return False, "Policy has expired", None, None
        
        # Check employee hire date and waiting period
        if employee.hire_date:
            days_employed = (today - employee.hire_date).days
            waiting_period = policy.waiting_period_days or 0
            
            if days_employed < waiting_period:
                remaining = waiting_period - days_employed
                eligibility_date = employee.hire_date + timedelta(days=waiting_period)
                return (
                    False,
                    f"In waiting period ({remaining} days remaining)",
                    eligibility_date,
                    remaining,
                )
            
            eligibility_start = employee.hire_date + timedelta(days=waiting_period)
        else:
            eligibility_start = today
        
        # Check eligibility criteria (JSON rules)
        if policy.eligibility_criteria:
            try:
                rules = json.loads(policy.eligibility_criteria)
                is_eligible, message = self._evaluate_eligibility_rules(employee, rules)
                if not is_eligible:
                    return False, message, None, None
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Error evaluating eligibility rules: {e}")
        
        return True, "Eligible", eligibility_start, None

    def _evaluate_eligibility_rules(
        self,
        employee: Employee,
        rules: List[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        """Evaluate eligibility rules against employee attributes."""
        for rule in rules:
            rule_type = rule.get("rule_type", "")
            field = rule.get("field", "")
            operator = rule.get("operator", "")
            value = rule.get("value")
            
            # Get employee attribute value
            emp_value = getattr(employee, field, None)
            
            # Handle location-based rules
            if field == "location_id" and employee.location:
                if operator == "in" and isinstance(value, list):
                    if employee.location_id not in value:
                        return False, f"Not in eligible locations"
                elif operator == "not_in" and isinstance(value, list):
                    if employee.location_id in value:
                        return False, f"Location not eligible"
            
            # Handle department-based rules
            elif field == "department_id" and employee.department:
                if operator == "in" and isinstance(value, list):
                    if employee.department_id not in value:
                        return False, f"Department not eligible"
            
            # Handle employment type rules
            elif field == "employment_type":
                if operator == "equals" and emp_value != value:
                    return False, f"Employment type '{emp_value}' not eligible"
                elif operator == "in" and isinstance(value, list):
                    if emp_value not in value:
                        return False, f"Employment type not eligible"
            
            # Handle tenure rules
            elif field == "tenure_years":
                if employee.hire_date:
                    tenure = (date.today() - employee.hire_date).days / 365.25
                    if operator == "gte" and tenure < value:
                        return False, f"Requires {value}+ years tenure"
                    elif operator == "lte" and tenure > value:
                        return False, f"Exceeds tenure limit"
        
        return True, "Meets all eligibility criteria"

    # =========================================================================
    # Tenure Tier Calculation
    # =========================================================================

    def calculate_tenure_tier(
        self,
        employee: Employee,
        policy: TimeOffPolicy,
    ) -> Tuple[Optional[float], Optional[float], Optional[date]]:
        """
        Calculate current and next tenure tier rates.
        
        Returns:
            Tuple of (current_rate, next_rate, next_tier_date)
        """
        if not policy.tenure_tiers or not employee.hire_date:
            return policy.base_accrual_rate, None, None
        
        try:
            tiers = json.loads(policy.tenure_tiers)
            tenure_years = (date.today() - employee.hire_date).days / 365.25
            
            current_rate = policy.base_accrual_rate
            next_rate = None
            next_tier_date = None
            
            sorted_tiers = sorted(tiers, key=lambda t: t.get("min_years", 0))
            
            for i, tier in enumerate(sorted_tiers):
                min_years = tier.get("min_years", 0)
                max_years = tier.get("max_years")
                tier_rate = tier.get("accrual_rate", policy.base_accrual_rate)
                
                if tenure_years >= min_years:
                    if max_years is None or tenure_years < max_years:
                        current_rate = tier_rate
                        
                        # Check for next tier
                        if i + 1 < len(sorted_tiers):
                            next_tier = sorted_tiers[i + 1]
                            next_rate = next_tier.get("accrual_rate")
                            next_min = next_tier.get("min_years", 0)
                            next_tier_date = employee.hire_date + timedelta(days=int(next_min * 365.25))
                        break
            
            return current_rate, next_rate, next_tier_date
            
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Error parsing tenure tiers: {e}")
            return policy.base_accrual_rate, None, None

    # =========================================================================
    # Policy Response Building
    # =========================================================================

    def build_accrual_info(
        self,
        policy: TimeOffPolicy,
        employee: Employee,
    ) -> AccrualInfo:
        """Build accrual information for display."""
        current_rate, next_rate, next_tier_date = self.calculate_tenure_tier(employee, policy)
        
        # Determine frequency description
        frequency = policy.accrual_frequency or "annually"
        frequency_map = {
            "annually": "Annually on January 1st",
            "monthly": "Monthly on the 1st",
            "bi-weekly": "Every pay period",
            "weekly": "Weekly",
        }
        frequency_desc = frequency_map.get(frequency, frequency.capitalize())
        
        return AccrualInfo(
            method=AccrualMethodDisplay(policy.accrual_method),
            method_description=ACCRUAL_METHOD_DESCRIPTIONS.get(
                policy.accrual_method,
                "Time-off accrues based on policy rules"
            ),
            annual_rate=policy.base_accrual_rate,
            current_tier_rate=current_rate,
            next_tier_rate=next_rate,
            next_tier_date=next_tier_date,
            frequency_description=frequency_desc,
            cap=policy.accrual_cap,
        )

    def build_balance_info(self, policy: TimeOffPolicy) -> BalanceInfo:
        """Build balance information for display."""
        # Max balance description
        if policy.max_balance:
            max_desc = f"Maximum {policy.max_balance:.1f} days"
        else:
            max_desc = "No maximum limit"
        
        # Carryover description
        carryover_allowed = policy.max_carryover is not None and policy.max_carryover > 0
        if carryover_allowed:
            carryover_desc = f"Up to {policy.max_carryover:.1f} days may be carried over"
            if policy.carryover_expiry_months:
                carryover_desc += f" (expires after {policy.carryover_expiry_months} months)"
            expiry = f"{policy.carryover_expiry_months} months after year-end" if policy.carryover_expiry_months else None
        else:
            carryover_desc = "No carryover allowed - use it or lose it"
            expiry = None
        
        return BalanceInfo(
            max_balance=policy.max_balance,
            max_balance_description=max_desc,
            carryover_allowed=carryover_allowed,
            max_carryover=policy.max_carryover,
            carryover_expiry=expiry,
            carryover_description=carryover_desc,
            allows_negative=policy.allow_negative_balance,
        )

    def build_request_rules(self, policy: TimeOffPolicy) -> RequestRules:
        """Build request rules for display."""
        # Min request description
        if policy.min_request_days == 0.5:
            min_desc = "Half day minimum"
        elif policy.min_request_days == 1:
            min_desc = "Full day minimum"
        else:
            min_desc = f"{policy.min_request_days:.1f} days minimum"
        
        # Max request description
        if policy.max_request_days:
            max_desc = f"Maximum {policy.max_request_days:.0f} days per request"
        else:
            max_desc = "No maximum per request"
        
        # Notice description
        if policy.advance_notice_days == 0:
            notice_desc = "No advance notice required"
        elif policy.advance_notice_days == 1:
            notice_desc = "1 day advance notice required"
        else:
            notice_desc = f"{policy.advance_notice_days} days advance notice required"
        
        # Consecutive days description
        if policy.max_consecutive_days:
            consec_desc = f"Maximum {policy.max_consecutive_days} consecutive days"
        else:
            consec_desc = "No limit on consecutive days"
        
        return RequestRules(
            min_request_days=policy.min_request_days,
            min_request_description=min_desc,
            max_request_days=policy.max_request_days,
            max_request_description=max_desc,
            advance_notice_days=policy.advance_notice_days,
            advance_notice_description=notice_desc,
            max_consecutive_days=policy.max_consecutive_days,
            consecutive_description=consec_desc,
            includes_weekends=policy.include_weekends,
            includes_holidays=policy.include_holidays,
        )

    def build_approval_info(self, policy: TimeOffPolicy) -> ApprovalInfo:
        """Build approval information for display."""
        if not policy.requires_approval:
            approval_desc = "No approval required"
        elif policy.approval_levels == 1:
            approval_desc = "Manager approval required"
        else:
            approval_desc = f"{policy.approval_levels}-level approval required"
        
        auto_approve_desc = None
        if policy.auto_approve_threshold:
            auto_approve_desc = f"Requests under {policy.auto_approve_threshold:.1f} days may be auto-approved"
        
        return ApprovalInfo(
            requires_approval=policy.requires_approval,
            approval_levels=policy.approval_levels,
            approval_description=approval_desc,
            auto_approve_threshold=policy.auto_approve_threshold,
            auto_approve_description=auto_approve_desc,
            typical_approval_time="1-2 business days",
        )

    def build_employee_policy_response(
        self,
        employee: Employee,
        policy: TimeOffPolicy,
        current_balance: Optional[float] = None,
        pending_days: Optional[float] = None,
    ) -> EmployeePolicyResponse:
        """Build complete policy response for an employee."""
        # Evaluate eligibility
        is_eligible, status, eligibility_date, waiting_remaining = self.evaluate_employee_eligibility(
            employee, policy
        )
        
        # Get policy type config
        type_config = POLICY_TYPE_CONFIG.get(
            policy.policy_type,
            {"display": policy.policy_type.title(), "icon": "calendar", "color": "#4A90D9", "priority": 99}
        )
        
        # Calculate available balance
        available = None
        if current_balance is not None:
            pending = pending_days or 0
            available = max(0, current_balance - pending)
        
        return EmployeePolicyResponse(
            id=policy.id,
            name=policy.name,
            code=policy.code,
            description=policy.description,
            policy_type=PolicyTypeDisplay(policy.policy_type),
            policy_type_display=type_config["display"],
            accrual=self.build_accrual_info(policy, employee),
            balance=self.build_balance_info(policy),
            request_rules=self.build_request_rules(policy),
            approval=self.build_approval_info(policy),
            employee_eligible=is_eligible,
            eligibility_status=status,
            eligibility_start_date=eligibility_date,
            waiting_period_remaining=waiting_remaining,
            current_balance=current_balance,
            pending_requests_days=pending_days,
            available_balance=available,
            policy_effective_date=policy.effective_date.date() if policy.effective_date else None,
            policy_expiry_date=policy.expiry_date.date() if policy.expiry_date else None,
            icon=type_config["icon"],
            color=type_config["color"],
            priority=type_config["priority"],
        )

    # =========================================================================
    # Main Query Methods
    # =========================================================================

    def get_employee_policies(
        self,
        employee_id: int,
    ) -> EmployeePoliciesListResponse:
        """
        Get all applicable policies for an employee.
        
        Evaluates eligibility based on location, employment type, tenure.
        """
        # Get employee
        employee = self.session.get(Employee, employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        # Get all active policies
        stmt = select(TimeOffPolicy).where(
            TimeOffPolicy.status == PolicyStatus.ACTIVE.value
        ).order_by(TimeOffPolicy.policy_type)
        
        policies = self.session.execute(stmt).scalars().all()
        
        # Build responses for each policy
        policy_responses = []
        total_available = 0.0
        
        for policy in policies:
            # In production, we would get actual balance from time_off_balance table
            # For now, use mock balance based on accrual rate
            mock_balance = policy.base_accrual_rate * 0.75 if policy.base_accrual_rate else 0
            mock_pending = 0.0
            
            response = self.build_employee_policy_response(
                employee=employee,
                policy=policy,
                current_balance=mock_balance,
                pending_days=mock_pending,
            )
            
            # Only include policies employee is eligible for (or in waiting period)
            policy_responses.append(response)
            
            if response.available_balance:
                total_available += response.available_balance
        
        # Sort by priority
        policy_responses.sort(key=lambda p: p.priority)
        
        # Get upcoming blackouts (mock for now)
        upcoming_blackouts = self._get_upcoming_blackouts()
        
        # Build guidance message
        guidance = self._build_guidance_message(employee, policy_responses)
        
        return EmployeePoliciesListResponse(
            employee_id=employee.id,
            employee_name=f"{employee.first_name} {employee.last_name}",
            policies=policy_responses,
            total_policies=len(policy_responses),
            total_available_days=total_available,
            upcoming_blackouts=upcoming_blackouts,
            last_updated=datetime.utcnow(),
            guidance_message=guidance,
        )

    def get_policy_constraints(
        self,
        policy_id: int,
        employee_id: int,
    ) -> PolicyConstraintsResponse:
        """
        Get detailed constraints for a specific policy.
        
        Returns blackout dates, notice requirements, usage restrictions.
        """
        # Get policy
        policy = self.session.get(TimeOffPolicy, policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        
        # Get employee for context
        employee = self.session.get(Employee, employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        # Build blackout periods
        blackout_periods = self._get_policy_blackouts(policy)
        
        # Build date constraints
        date_constraints = self._build_date_constraints(policy)
        
        # Build notice requirements
        notice_requirements = self._build_notice_requirements(policy)
        
        # Build usage restrictions
        usage_restrictions = self._build_usage_restrictions(policy)
        
        # Build documentation requirements
        doc_requirements = self._build_documentation_requirements(policy)
        
        # Build approval chain
        approval_chain = self._build_approval_chain(employee, policy)
        
        # Calculate request window
        earliest = date.today() + timedelta(days=policy.advance_notice_days)
        latest = date.today() + timedelta(days=365)  # One year out
        
        if policy.advance_notice_days > 0:
            window_desc = f"Requests must be at least {policy.advance_notice_days} days in advance"
        else:
            window_desc = "No advance notice restriction"
        
        # Build UI warnings and tips
        warnings, info_messages, tips = self._build_ui_guidance(policy, employee)
        
        return PolicyConstraintsResponse(
            policy_id=policy.id,
            policy_name=policy.name,
            policy_code=policy.code,
            blackout_periods=blackout_periods,
            date_constraints=date_constraints,
            notice_requirements=notice_requirements,
            usage_restrictions=usage_restrictions,
            documentation_requirements=doc_requirements,
            minimum_balance_required=policy.min_balance_allowed,
            allows_negative_balance=policy.allow_negative_balance,
            max_negative_allowed=-5.0 if policy.allow_negative_balance else None,
            team_coverage_required=False,  # Would come from policy config
            max_team_absent_percentage=None,
            coverage_description=None,
            earliest_request_date=earliest,
            latest_request_date=latest,
            request_window_description=window_desc,
            approval_chain=approval_chain,
            escalation_rules="Requests escalate to HR after 5 business days without response",
            special_conditions=self._get_special_conditions(policy),
            ui_warnings=warnings,
            ui_info_messages=info_messages,
            tips=tips,
            last_updated=datetime.utcnow(),
            effective_date=policy.effective_date.date() if policy.effective_date else None,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_upcoming_blackouts(self) -> List[BlackoutPeriod]:
        """Get upcoming blackout periods (mock implementation)."""
        today = date.today()
        
        # Mock blackout periods - in production, query from database
        blackouts = []
        
        # Year-end blackout
        year_end_start = date(today.year, 12, 23)
        year_end_end = date(today.year + 1, 1, 2)
        
        if year_end_start > today:
            blackouts.append(BlackoutPeriod(
                id=1,
                name="Year-End Close",
                start_date=year_end_start,
                end_date=year_end_end,
                reason="Annual financial close period",
                is_recurring=True,
                applies_to_policy_types=["vacation", "personal"],
                severity="hard",
            ))
        
        return blackouts

    def _get_policy_blackouts(self, policy: TimeOffPolicy) -> List[BlackoutPeriod]:
        """Get blackout periods for a specific policy."""
        # In production, query from blackout_period table
        return self._get_upcoming_blackouts()

    def _build_date_constraints(self, policy: TimeOffPolicy) -> List[DateConstraint]:
        """Build date constraints from policy configuration."""
        constraints = []
        
        # Add blackout as date constraint
        for blackout in self._get_policy_blackouts(policy):
            constraints.append(DateConstraint(
                constraint_type="blackout",
                start_date=blackout.start_date,
                end_date=blackout.end_date,
                name=blackout.name,
                description=f"Time-off not permitted: {blackout.reason}",
                severity=blackout.severity,
                can_request_exception=blackout.severity == "soft",
                exception_process="Contact HR to request an exception" if blackout.severity == "soft" else None,
            ))
        
        return constraints

    def _build_notice_requirements(self, policy: TimeOffPolicy) -> List[NoticeRequirement]:
        """Build notice requirements based on policy rules."""
        requirements = []
        
        base_notice = policy.advance_notice_days
        
        # Short requests
        if base_notice > 0:
            requirements.append(NoticeRequirement(
                min_days=0.5,
                max_days=3.0,
                notice_required=min(base_notice, 3),
                description=f"{min(base_notice, 3)} days notice for short requests (1-3 days)",
            ))
            
            # Medium requests
            requirements.append(NoticeRequirement(
                min_days=3.1,
                max_days=5.0,
                notice_required=base_notice,
                description=f"{base_notice} days notice for medium requests (3-5 days)",
            ))
            
            # Long requests
            if policy.max_consecutive_days and policy.max_consecutive_days > 5:
                requirements.append(NoticeRequirement(
                    min_days=5.1,
                    max_days=None,
                    notice_required=max(base_notice, 14),
                    description=f"{max(base_notice, 14)} days notice for extended requests (5+ days)",
                ))
        else:
            requirements.append(NoticeRequirement(
                min_days=0.5,
                max_days=None,
                notice_required=0,
                description="No advance notice required",
            ))
        
        return requirements

    def _build_usage_restrictions(self, policy: TimeOffPolicy) -> List[UsageRestriction]:
        """Build usage restrictions from policy configuration."""
        restrictions = []
        
        if policy.min_request_days > 0.5:
            restrictions.append(UsageRestriction(
                restriction_type="minimum_duration",
                description=f"Minimum request is {policy.min_request_days} days",
                applies_to="All requests",
                guidance="Half-day requests are not available for this policy",
            ))
        
        if policy.max_consecutive_days:
            restrictions.append(UsageRestriction(
                restriction_type="consecutive_limit",
                description=f"Maximum {policy.max_consecutive_days} consecutive days",
                applies_to="All requests",
                guidance="Split longer absences into separate requests",
            ))
        
        if not policy.allow_negative_balance:
            restrictions.append(UsageRestriction(
                restriction_type="balance_required",
                description="Sufficient balance required",
                applies_to="All requests",
                guidance="Ensure you have enough balance before submitting",
            ))
        
        return restrictions

    def _build_documentation_requirements(self, policy: TimeOffPolicy) -> List[DocumentRequirement]:
        """Build documentation requirements based on policy type."""
        requirements = []
        
        if policy.policy_type == "sick":
            requirements.append(DocumentRequirement(
                requirement_type="medical_note",
                description="Doctor's note required for absences over 3 consecutive days",
                when_required="Absences exceeding 3 consecutive days",
                how_to_submit="Upload via the time-off request form or email to HR",
                is_mandatory=True,
            ))
        
        if policy.policy_type == "bereavement":
            requirements.append(DocumentRequirement(
                requirement_type="death_certificate",
                description="Proof of relationship may be required",
                when_required="Upon request by HR",
                how_to_submit="Submit to HR within 30 days of return",
                is_mandatory=False,
            ))
        
        if policy.policy_type == "jury_duty":
            requirements.append(DocumentRequirement(
                requirement_type="jury_summons",
                description="Copy of jury summons required",
                when_required="With time-off request",
                how_to_submit="Upload with the time-off request form",
                is_mandatory=True,
            ))
        
        return requirements

    def _build_approval_chain(
        self,
        employee: Employee,
        policy: TimeOffPolicy,
    ) -> List[str]:
        """Build the approval chain for an employee's request."""
        chain = []
        
        if not policy.requires_approval:
            return ["Auto-approved"]
        
        # Add manager
        if employee.manager:
            chain.append(f"Direct Manager ({employee.manager.first_name} {employee.manager.last_name})")
        else:
            chain.append("Direct Manager")
        
        # Add additional levels if required
        if policy.approval_levels > 1:
            chain.append("Department Head")
        
        if policy.approval_levels > 2:
            chain.append("HR")
        
        return chain

    def _get_special_conditions(self, policy: TimeOffPolicy) -> List[str]:
        """Get special conditions for a policy."""
        conditions = []
        
        if policy.prorate_first_year:
            conditions.append("Balance is prorated for employees hired during the year")
        
        if policy.include_weekends:
            conditions.append("Weekends are counted against your balance")
        
        if policy.include_holidays:
            conditions.append("Holidays are counted against your balance")
        
        if policy.waiting_period_days > 0:
            conditions.append(f"{policy.waiting_period_days}-day waiting period for new employees")
        
        return conditions

    def _build_ui_guidance(
        self,
        policy: TimeOffPolicy,
        employee: Employee,
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build UI warnings, info messages, and tips."""
        warnings = []
        info_messages = []
        tips = []
        
        # Check for upcoming blackouts
        blackouts = self._get_policy_blackouts(policy)
        for blackout in blackouts:
            days_until = (blackout.start_date - date.today()).days
            if 0 < days_until <= 30:
                warnings.append(
                    f"Blackout period starting in {days_until} days: {blackout.name}"
                )
        
        # Carryover warnings
        if policy.max_carryover is not None and policy.max_carryover > 0:
            info_messages.append(
                f"Remember: Only {policy.max_carryover:.1f} days can be carried over to next year"
            )
        
        # Tips
        tips.append("Submit requests as early as possible for better approval chances")
        
        if policy.advance_notice_days > 0:
            tips.append(f"Plan ahead - {policy.advance_notice_days} days notice required")
        
        if policy.auto_approve_threshold:
            tips.append(
                f"Requests under {policy.auto_approve_threshold:.1f} days may be auto-approved"
            )
        
        return warnings, info_messages, tips

    def _build_guidance_message(
        self,
        employee: Employee,
        policies: List[EmployeePolicyResponse],
    ) -> Optional[str]:
        """Build a guidance message for the employee."""
        # Check for policies in waiting period
        waiting_policies = [p for p in policies if p.waiting_period_remaining]
        if waiting_policies:
            policy = waiting_policies[0]
            return (
                f"You're currently in a waiting period for {policy.name}. "
                f"You'll be eligible in {policy.waiting_period_remaining} days."
            )
        
        # Check for low balances
        low_balance_policies = [
            p for p in policies
            if p.available_balance is not None and p.available_balance < 2
        ]
        if low_balance_policies:
            names = ", ".join(p.name for p in low_balance_policies[:2])
            return f"Your balance is running low for: {names}. Plan your time-off accordingly."
        
        return None

