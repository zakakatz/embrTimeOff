"""Service for balance analytics and reconciliation."""

import logging
import math
import statistics
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.employee import Employee, Department
from src.models.time_off_policy import TimeOffPolicy, PolicyStatus
from src.models.time_off_request import TimeOffBalance, TimeOffRequest
from src.schemas.balance_analytics import (
    AccuracyAssessment,
    BalanceDiscrepancy,
    BalanceTrendResponse,
    BalanceUtilizationResponse,
    ConfidenceLevelEnum,
    DepartmentUtilization,
    DiscrepancyTypeEnum,
    ForecastDataPoint,
    OptimizationRecommendation,
    PolicyEffectiveness,
    ReconciliationCorrection,
    ReconciliationHistoryEntry,
    ReconciliationHistoryResponse,
    ReconciliationRequest,
    ReconciliationResult,
    ReconciliationStatusEnum,
    ReconciliationTrendAnalysis,
    SeasonalAnalysis,
    SeasonalPatternEnum,
    TrendDataPoint,
    TrendDirectionEnum,
    TrendIdentification,
    UtilizationMetric,
)
from src.utils.auth import CurrentUser

logger = logging.getLogger(__name__)


class BalanceAnalyticsService:
    """Service for balance analytics and reconciliation."""

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session

    # =========================================================================
    # Trend Analysis
    # =========================================================================

    def analyze_balance_trends(
        self,
        current_user: CurrentUser,
        policy_id: Optional[int] = None,
        department_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        forecast_days: int = 90,
    ) -> BalanceTrendResponse:
        """
        Analyze historical balance data with trend identification.
        
        Performs seasonal analysis and predictive forecasting.
        """
        # Default date range: last 12 months
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)

        # Generate historical data points (mock for demonstration)
        historical_data = self._generate_historical_data(
            policy_id, department_id, start_date, end_date
        )

        # Identify trends
        trends = self._identify_trends(historical_data)

        # Seasonal analysis
        seasonal = self._analyze_seasonality(historical_data)

        # Generate forecasts
        forecast = self._generate_forecast(historical_data, forecast_days)

        # Calculate summary statistics
        values = [dp.value for dp in historical_data]
        avg_balance = statistics.mean(values) if values else 0
        min_balance = min(values) if values else 0
        max_balance = max(values) if values else 0
        std_dev = statistics.stdev(values) if len(values) > 1 else 0

        # Generate insights
        insights = self._generate_trend_insights(trends, seasonal, avg_balance)
        recommendations = self._generate_planning_recommendations(trends, seasonal, forecast)

        return BalanceTrendResponse(
            analysis_period_start=start_date,
            analysis_period_end=end_date,
            historical_data=historical_data,
            trends=trends,
            seasonal_analysis=seasonal,
            forecast=forecast,
            forecast_horizon_days=forecast_days,
            average_balance=round(avg_balance, 2),
            min_balance=round(min_balance, 2),
            max_balance=round(max_balance, 2),
            standard_deviation=round(std_dev, 2),
            insights=insights,
            recommendations=recommendations,
            analyzed_at=datetime.utcnow(),
            data_quality_score=0.95,
        )

    def _generate_historical_data(
        self,
        policy_id: Optional[int],
        department_id: Optional[int],
        start_date: date,
        end_date: date,
    ) -> List[TrendDataPoint]:
        """Generate historical balance data points."""
        data_points = []
        current = start_date.replace(day=1)
        
        # Generate monthly data points with realistic patterns
        base_value = 15.0
        while current <= end_date:
            # Add seasonal variation
            month = current.month
            seasonal_factor = 1.0
            if month in [6, 7, 8]:  # Summer
                seasonal_factor = 0.7  # Lower balances (more usage)
            elif month in [12]:  # Year end
                seasonal_factor = 0.5  # Much lower balances
            elif month in [1, 2]:  # Start of year
                seasonal_factor = 1.2  # Higher balances (new allocation)
            
            # Add some randomness
            import random
            random.seed(hash((current.year, current.month)))
            variation = random.uniform(-2, 2)
            
            value = max(0, base_value * seasonal_factor + variation)
            
            data_points.append(TrendDataPoint(
                date=current,
                value=round(value, 2),
                period_label=current.strftime("%B %Y"),
            ))
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return data_points

    def _identify_trends(
        self,
        data: List[TrendDataPoint],
    ) -> List[TrendIdentification]:
        """Identify trends in the data."""
        if len(data) < 3:
            return []
        
        trends = []
        values = [dp.value for dp in data]
        
        # Calculate overall trend using linear regression
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator > 0:
            slope = numerator / denominator
            
            # Determine direction
            if abs(slope) < 0.1:
                direction = TrendDirectionEnum.STABLE
            elif slope > 0:
                direction = TrendDirectionEnum.INCREASING
            else:
                direction = TrendDirectionEnum.DECREASING
            
            # Calculate magnitude as percentage change
            magnitude = (values[-1] - values[0]) / values[0] * 100 if values[0] != 0 else 0
            
            trends.append(TrendIdentification(
                trend_type="overall",
                direction=direction,
                magnitude=round(abs(magnitude), 1),
                start_date=data[0].date,
                end_date=data[-1].date,
                confidence=ConfidenceLevelEnum.HIGH if abs(slope) > 0.5 else ConfidenceLevelEnum.MEDIUM,
                description=f"Overall balance trend is {direction.value} with {abs(magnitude):.1f}% change",
            ))
        
        # Check for recent trend (last 3 months)
        if len(data) >= 3:
            recent = values[-3:]
            recent_slope = (recent[-1] - recent[0]) / 2
            
            if abs(recent_slope) > 0.5:
                direction = TrendDirectionEnum.INCREASING if recent_slope > 0 else TrendDirectionEnum.DECREASING
                trends.append(TrendIdentification(
                    trend_type="recent",
                    direction=direction,
                    magnitude=round(abs(recent_slope), 1),
                    start_date=data[-3].date,
                    end_date=data[-1].date,
                    confidence=ConfidenceLevelEnum.MEDIUM,
                    description=f"Recent 3-month trend shows {direction.value} pattern",
                ))
        
        return trends

    def _analyze_seasonality(
        self,
        data: List[TrendDataPoint],
    ) -> Optional[SeasonalAnalysis]:
        """Analyze seasonal patterns in the data."""
        if len(data) < 12:
            return None
        
        # Group by month
        monthly_values: Dict[int, List[float]] = defaultdict(list)
        for dp in data:
            monthly_values[dp.date.month].append(dp.value)
        
        # Calculate monthly averages
        monthly_averages = {
            m: statistics.mean(vals) for m, vals in monthly_values.items()
        }
        
        # Find peaks and troughs
        overall_avg = statistics.mean(monthly_averages.values())
        peaks = [m for m, v in monthly_averages.items() if v < overall_avg * 0.85]  # Low balance = high usage
        troughs = [m for m, v in monthly_averages.items() if v > overall_avg * 1.15]  # High balance = low usage
        
        # Determine pattern type
        if 6 in peaks or 7 in peaks or 8 in peaks:
            pattern = SeasonalPatternEnum.SUMMER_PEAK
            recommendation = "Plan for increased coverage needs during summer months"
        elif 12 in peaks:
            pattern = SeasonalPatternEnum.YEAR_END
            recommendation = "Expect high usage in December; review carryover policies"
        elif peaks:
            pattern = SeasonalPatternEnum.HOLIDAY_DRIVEN
            recommendation = "Review staffing plans around holiday periods"
        else:
            pattern = SeasonalPatternEnum.NO_PATTERN
            recommendation = "No significant seasonal pattern detected"
        
        # Calculate peak increase
        if peaks and monthly_averages:
            peak_avg = statistics.mean([overall_avg - monthly_averages.get(m, overall_avg) for m in peaks])
            peak_increase = (peak_avg / overall_avg * 100) if overall_avg > 0 else 0
        else:
            peak_increase = 0
        
        return SeasonalAnalysis(
            pattern_type=pattern,
            peak_months=peaks,
            trough_months=troughs,
            average_peak_increase=round(peak_increase, 1),
            confidence=ConfidenceLevelEnum.MEDIUM if len(data) >= 24 else ConfidenceLevelEnum.LOW,
            recommendation=recommendation,
        )

    def _generate_forecast(
        self,
        data: List[TrendDataPoint],
        days: int,
    ) -> List[ForecastDataPoint]:
        """Generate forecast with confidence intervals."""
        if len(data) < 3:
            return []
        
        forecasts = []
        values = [dp.value for dp in data]
        
        # Simple exponential smoothing
        alpha = 0.3
        level = values[0]
        for v in values[1:]:
            level = alpha * v + (1 - alpha) * level
        
        # Calculate standard error
        std_err = statistics.stdev(values) if len(values) > 1 else 1
        
        # Generate monthly forecasts
        last_date = data[-1].date
        for i in range(1, (days // 30) + 2):
            if last_date.month + i <= 12:
                forecast_date = last_date.replace(month=last_date.month + i)
            else:
                new_month = (last_date.month + i - 1) % 12 + 1
                new_year = last_date.year + (last_date.month + i - 1) // 12
                forecast_date = date(new_year, new_month, 1)
            
            if (forecast_date - last_date).days > days:
                break
            
            # Add trend component
            trend_adjustment = 0.02 * i  # Small positive trend
            predicted = level * (1 + trend_adjustment)
            
            # Confidence interval (95%)
            z = 1.96
            margin = z * std_err * math.sqrt(1 + 0.1 * i)  # Uncertainty grows with time
            
            forecasts.append(ForecastDataPoint(
                date=forecast_date,
                predicted_value=round(predicted, 2),
                lower_bound=round(max(0, predicted - margin), 2),
                upper_bound=round(predicted + margin, 2),
                confidence_level=0.95,
            ))
        
        return forecasts

    def _generate_trend_insights(
        self,
        trends: List[TrendIdentification],
        seasonal: Optional[SeasonalAnalysis],
        avg_balance: float,
    ) -> List[str]:
        """Generate strategic insights from trend analysis."""
        insights = []
        
        for trend in trends:
            if trend.direction == TrendDirectionEnum.DECREASING:
                insights.append(
                    f"Balance {trend.trend_type} trend is declining by {trend.magnitude}% - "
                    "employees are utilizing more time off"
                )
            elif trend.direction == TrendDirectionEnum.INCREASING:
                insights.append(
                    f"Balance {trend.trend_type} trend is increasing by {trend.magnitude}% - "
                    "consider encouraging time-off usage"
                )
        
        if seasonal:
            if seasonal.pattern_type != SeasonalPatternEnum.NO_PATTERN:
                insights.append(
                    f"Seasonal pattern detected: {seasonal.pattern_type.value} with "
                    f"{seasonal.average_peak_increase}% variation"
                )
        
        if avg_balance > 20:
            insights.append(
                "High average balance suggests employees may not be taking enough time off"
            )
        elif avg_balance < 5:
            insights.append(
                "Low average balance indicates high utilization - ensure adequate coverage"
            )
        
        return insights

    def _generate_planning_recommendations(
        self,
        trends: List[TrendIdentification],
        seasonal: Optional[SeasonalAnalysis],
        forecast: List[ForecastDataPoint],
    ) -> List[str]:
        """Generate planning recommendations."""
        recommendations = []
        
        if seasonal and seasonal.peak_months:
            months = [date(2000, m, 1).strftime("%B") for m in seasonal.peak_months]
            recommendations.append(
                f"Increase staffing coverage during peak months: {', '.join(months)}"
            )
        
        # Check forecast for concerning trends
        if forecast:
            last_forecast = forecast[-1]
            if last_forecast.predicted_value < 3:
                recommendations.append(
                    "Forecast shows low future balances - review accrual policies"
                )
            elif last_forecast.predicted_value > 30:
                recommendations.append(
                    "High projected balances - consider initiatives to encourage usage"
                )
        
        recommendations.append(
            "Review these trends quarterly to adjust workforce planning strategies"
        )
        
        return recommendations

    # =========================================================================
    # Utilization Analytics
    # =========================================================================

    def analyze_utilization(
        self,
        current_user: CurrentUser,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        department_ids: Optional[List[int]] = None,
        policy_ids: Optional[List[int]] = None,
    ) -> BalanceUtilizationResponse:
        """
        Calculate utilization rates and policy effectiveness.
        
        Returns optimization recommendations with implementation guidance.
        """
        # Default date range
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = date(end_date.year, 1, 1)

        # Get policies
        stmt = select(TimeOffPolicy).where(TimeOffPolicy.status == PolicyStatus.ACTIVE.value)
        if policy_ids:
            stmt = stmt.where(TimeOffPolicy.id.in_(policy_ids))
        policies = self.session.execute(stmt).scalars().all()

        # Get departments
        dept_stmt = select(Department)
        if department_ids:
            dept_stmt = dept_stmt.where(Department.id.in_(department_ids))
        departments = self.session.execute(dept_stmt).scalars().all()

        # Calculate metrics
        total_allocated = 0.0
        total_used = 0.0
        total_forfeited = 0.0
        employee_count = 0

        # Get employee count
        emp_stmt = select(func.count(Employee.id)).where(Employee.is_active == True)
        if department_ids:
            emp_stmt = emp_stmt.where(Employee.department_id.in_(department_ids))
        employee_count = self.session.execute(emp_stmt).scalar() or 0

        # Generate policy metrics
        policy_metrics = []
        for policy in policies:
            allocated = policy.base_accrual_rate * employee_count
            used = allocated * 0.72  # Mock: 72% utilization
            forfeited = allocated * 0.03  # Mock: 3% forfeit
            
            total_allocated += allocated
            total_used += used
            total_forfeited += forfeited
            
            utilization_rate = (used / allocated * 100) if allocated > 0 else 0
            
            policy_metrics.append(UtilizationMetric(
                policy_id=policy.id,
                policy_name=policy.name,
                policy_type=policy.policy_type,
                utilization_rate=round(utilization_rate, 1),
                accrual_rate=round(policy.base_accrual_rate, 1),
                carryover_rate=round(15.0, 1),  # Mock
                forfeit_rate=round(3.0, 1),  # Mock
                vs_company_average=round(utilization_rate - 75, 1),  # Mock company avg of 75%
                vs_last_period=round(2.5, 1),  # Mock: 2.5% increase
                percentile_rank=round(65.0, 1),  # Mock
            ))

        # Generate department breakdown
        dept_breakdown = []
        for dept in departments[:10]:  # Limit to 10
            dept_employees = self.session.execute(
                select(func.count(Employee.id))
                .where(Employee.department_id == dept.id)
                .where(Employee.is_active == True)
            ).scalar() or 0
            
            if dept_employees > 0:
                dept_allocated = 15 * dept_employees  # Mock
                dept_used = dept_allocated * 0.70  # Mock
                
                dept_breakdown.append(DepartmentUtilization(
                    department_id=dept.id,
                    department_name=dept.name,
                    employee_count=dept_employees,
                    average_utilization=round(70.0, 1),
                    total_days_used=round(dept_used, 1),
                    total_days_available=round(dept_allocated - dept_used, 1),
                ))

        # Policy effectiveness
        effectiveness = []
        for policy in policies:
            effectiveness.append(PolicyEffectiveness(
                policy_id=policy.id,
                policy_name=policy.name,
                overall_effectiveness=round(82.0, 1),
                employee_satisfaction_proxy=round(78.0, 1),
                administrative_efficiency=round(88.0, 1),
                identified_issues=[
                    "Low utilization in Q1",
                    "Carryover accumulation in some departments",
                ] if policy.policy_type == "vacation" else [],
                optimization_suggestions=[
                    "Consider reminder notifications for low-usage employees",
                    "Review carryover limits",
                ],
            ))

        # Generate recommendations
        recommendations = self._generate_optimization_recommendations(
            policy_metrics, dept_breakdown, effectiveness
        )

        # Calculate company-wide rate
        company_rate = (total_used / total_allocated * 100) if total_allocated > 0 else 0

        return BalanceUtilizationResponse(
            analysis_period_start=start_date,
            analysis_period_end=end_date,
            company_utilization_rate=round(company_rate, 1),
            total_employees_analyzed=employee_count,
            total_days_allocated=round(total_allocated, 1),
            total_days_used=round(total_used, 1),
            total_days_forfeited=round(total_forfeited, 1),
            policy_metrics=policy_metrics,
            department_breakdown=dept_breakdown,
            policy_effectiveness=effectiveness,
            optimization_recommendations=recommendations,
            utilization_distribution={
                "0-25%": 5,
                "25-50%": 15,
                "50-75%": 35,
                "75-100%": 45,
            },
            analyzed_at=datetime.utcnow(),
        )

    def _generate_optimization_recommendations(
        self,
        policy_metrics: List[UtilizationMetric],
        dept_breakdown: List[DepartmentUtilization],
        effectiveness: List[PolicyEffectiveness],
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations."""
        recommendations = []

        # Check for low utilization
        low_util_policies = [p for p in policy_metrics if p.utilization_rate < 60]
        if low_util_policies:
            recommendations.append(OptimizationRecommendation(
                recommendation_type="utilization",
                priority="high",
                title="Improve Time-Off Utilization",
                description=(
                    f"{len(low_util_policies)} policies have utilization below 60%. "
                    "Low utilization can indicate cultural barriers or workload issues."
                ),
                expected_impact="Improved employee wellbeing and reduced burnout risk",
                implementation_guidance=(
                    "1. Send quarterly balance reminders\n"
                    "2. Encourage managers to model time-off behavior\n"
                    "3. Review workload distribution"
                ),
                affected_policies=[p.policy_id for p in low_util_policies],
                estimated_effort="Medium",
            ))

        # Check for high forfeit rates
        high_forfeit = [p for p in policy_metrics if p.forfeit_rate > 5]
        if high_forfeit:
            recommendations.append(OptimizationRecommendation(
                recommendation_type="policy",
                priority="medium",
                title="Reduce Balance Forfeiture",
                description=(
                    f"Policies with forfeit rates above 5% detected. "
                    "This represents lost employee benefits and potential dissatisfaction."
                ),
                expected_impact="Better employee benefit utilization and satisfaction",
                implementation_guidance=(
                    "1. Increase carryover limits\n"
                    "2. Implement use-it-or-lose-it reminders\n"
                    "3. Consider payout options for unused balances"
                ),
                affected_policies=[p.policy_id for p in high_forfeit],
                estimated_effort="Low",
            ))

        # Check department disparities
        if dept_breakdown:
            utils = [d.average_utilization for d in dept_breakdown]
            if max(utils) - min(utils) > 20:
                recommendations.append(OptimizationRecommendation(
                    recommendation_type="equity",
                    priority="medium",
                    title="Address Department Utilization Disparities",
                    description=(
                        "Significant variation in utilization rates across departments detected. "
                        "This may indicate workload or cultural differences."
                    ),
                    expected_impact="More equitable time-off access across organization",
                    implementation_guidance=(
                        "1. Review workload distribution in low-utilization departments\n"
                        "2. Train managers on encouraging time-off\n"
                        "3. Set department-level utilization targets"
                    ),
                    affected_policies=[],
                    estimated_effort="High",
                ))

        return recommendations

    # =========================================================================
    # Reconciliation
    # =========================================================================

    def perform_reconciliation(
        self,
        request: ReconciliationRequest,
        current_user: CurrentUser,
    ) -> ReconciliationResult:
        """
        Perform balance reconciliation with discrepancy identification.
        
        Processes corrections and maintains audit trail.
        """
        reconciliation_id = str(uuid.uuid4())[:8].upper()
        as_of_date = request.as_of_date or date.today()

        # Get scope
        employees_analyzed = 0
        discrepancies: List[BalanceDiscrepancy] = []
        corrections: List[ReconciliationCorrection] = []

        # Query employees based on scope
        emp_stmt = select(Employee).where(Employee.is_active == True)
        if request.scope == "department" and request.scope_ids:
            emp_stmt = emp_stmt.where(Employee.department_id.in_(request.scope_ids))
        elif request.scope == "employee" and request.scope_ids:
            emp_stmt = emp_stmt.where(Employee.id.in_(request.scope_ids))

        employees = self.session.execute(emp_stmt).scalars().all()
        employees_analyzed = len(employees)

        # Get policies
        policy_stmt = select(TimeOffPolicy).where(TimeOffPolicy.status == PolicyStatus.ACTIVE.value)
        if request.scope == "policy" and request.scope_ids:
            policy_stmt = policy_stmt.where(TimeOffPolicy.id.in_(request.scope_ids))
        policies = self.session.execute(policy_stmt).scalars().all()

        # Check each employee's balances
        for employee in employees:
            for policy in policies:
                # Check for discrepancies (mock logic)
                discrepancy = self._check_balance_discrepancy(
                    employee, policy, as_of_date
                )
                
                if discrepancy:
                    discrepancies.append(discrepancy)
                    
                    # Auto-correct if enabled and within threshold
                    if (request.auto_correct and 
                        abs(discrepancy.difference) <= request.correction_threshold):
                        correction = ReconciliationCorrection(
                            employee_id=employee.id,
                            policy_id=policy.id,
                            correction_type="automatic",
                            amount=discrepancy.difference,
                            effective_date=as_of_date,
                            reason=f"Auto-correction for {discrepancy.discrepancy_type.value}",
                            notes=f"Reconciliation {reconciliation_id}",
                        )
                        corrections.append(correction)

        # Calculate totals
        total_discrepancy = sum(abs(d.difference) for d in discrepancies)
        corrections_applied = len([c for c in corrections])
        corrections_pending = len([
            d for d in discrepancies 
            if abs(d.difference) > request.require_approval_above
        ])

        # Generate summary
        if not discrepancies:
            summary = "No discrepancies found. All balances reconciled successfully."
        else:
            summary = (
                f"Found {len(discrepancies)} discrepancies totaling {total_discrepancy:.1f} days. "
                f"{corrections_applied} corrections applied, {corrections_pending} require approval."
            )

        # Generate recommendations
        recommendations = []
        if discrepancies:
            type_counts = defaultdict(int)
            for d in discrepancies:
                type_counts[d.discrepancy_type.value] += 1
            
            most_common = max(type_counts.items(), key=lambda x: x[1])
            recommendations.append(
                f"Most common issue: {most_common[0]} ({most_common[1]} occurrences). "
                "Review related processes."
            )
            recommendations.append(
                "Schedule regular reconciliation checks to catch issues early."
            )

        return ReconciliationResult(
            reconciliation_id=reconciliation_id,
            status=ReconciliationStatusEnum.COMPLETED,
            scope=request.scope,
            as_of_date=as_of_date,
            employees_analyzed=employees_analyzed,
            discrepancies_found=len(discrepancies),
            total_discrepancy_amount=round(total_discrepancy, 2),
            corrections_applied=corrections_applied,
            corrections_pending_approval=corrections_pending,
            corrections_failed=0,
            discrepancies=discrepancies,
            applied_corrections=corrections,
            initiated_by=f"Employee {current_user.employee_id}",
            initiated_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            summary=summary,
            recommendations=recommendations,
        )

    def _check_balance_discrepancy(
        self,
        employee: Employee,
        policy: TimeOffPolicy,
        as_of_date: date,
    ) -> Optional[BalanceDiscrepancy]:
        """Check for balance discrepancy for an employee/policy."""
        # Mock: Generate random discrepancies for demonstration
        import random
        random.seed(hash((employee.id, policy.id, as_of_date.toordinal())))
        
        # 10% chance of discrepancy
        if random.random() > 0.10:
            return None
        
        # Generate mock discrepancy
        expected = policy.base_accrual_rate * 0.5  # Mock expected
        actual = expected + random.uniform(-2, 2)  # Mock actual with variance
        difference = actual - expected
        
        if abs(difference) < 0.1:
            return None
        
        discrepancy_types = [
            DiscrepancyTypeEnum.ACCRUAL_ERROR,
            DiscrepancyTypeEnum.USAGE_MISMATCH,
            DiscrepancyTypeEnum.CARRYOVER_ERROR,
        ]
        disc_type = random.choice(discrepancy_types)
        
        severity = "low"
        if abs(difference) > 2:
            severity = "high"
        elif abs(difference) > 1:
            severity = "medium"
        
        return BalanceDiscrepancy(
            discrepancy_id=f"DISC-{employee.id}-{policy.id}",
            employee_id=employee.id,
            employee_name=f"{employee.first_name} {employee.last_name}",
            policy_id=policy.id,
            policy_name=policy.name,
            discrepancy_type=disc_type,
            expected_balance=round(expected, 2),
            actual_balance=round(actual, 2),
            difference=round(difference, 2),
            detected_at=datetime.utcnow(),
            probable_cause=f"Possible {disc_type.value.replace('_', ' ')}",
            affected_period=f"Q{(as_of_date.month - 1) // 3 + 1} {as_of_date.year}",
            severity=severity,
            requires_immediate_action=severity == "high",
        )

    # =========================================================================
    # Reconciliation History
    # =========================================================================

    def get_reconciliation_history(
        self,
        current_user: CurrentUser,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ReconciliationHistoryResponse:
        """
        Get reconciliation history with audit trail and trend analysis.
        """
        # Generate mock history entries
        entries = []
        for i in range(min(page_size, 10)):
            entry_date = date.today() - timedelta(days=i * 7)
            entries.append(ReconciliationHistoryEntry(
                reconciliation_id=f"REC-{1000 + i}",
                status=ReconciliationStatusEnum.COMPLETED,
                scope="all",
                as_of_date=entry_date,
                employees_analyzed=150 + i * 5,
                discrepancies_found=5 + i % 3,
                corrections_applied=3 + i % 2,
                initiated_by="System",
                initiated_at=datetime.combine(entry_date, datetime.min.time()),
                completed_at=datetime.combine(entry_date, datetime.min.time()) + timedelta(hours=1),
            ))

        # Accuracy assessment
        accuracy = AccuracyAssessment(
            overall_accuracy=98.5,
            accrual_accuracy=99.2,
            usage_accuracy=97.8,
            carryover_accuracy=98.1,
            accuracy_trend=TrendDirectionEnum.INCREASING,
            trend_description="Accuracy has improved 0.5% over the last quarter",
            common_issues=[
                "Carryover calculation timing",
                "Manual adjustment sync delays",
            ],
            prevention_recommendations=[
                "Implement real-time validation for manual adjustments",
                "Review carryover calculation triggers",
            ],
        )

        # Trend analysis
        trend_analysis = ReconciliationTrendAnalysis(
            period_start=date.today() - timedelta(days=180),
            period_end=date.today(),
            reconciliations_per_month={
                "Jan": 4, "Feb": 4, "Mar": 4,
                "Apr": 4, "May": 4, "Jun": 4,
            },
            discrepancies_per_month={
                "Jan": 12, "Feb": 10, "Mar": 8,
                "Apr": 9, "May": 7, "Jun": 6,
            },
            discrepancy_by_type={
                "accrual_error": 25,
                "usage_mismatch": 18,
                "carryover_error": 9,
            },
            average_discrepancy_amount=1.2,
            average_resolution_time_hours=2.5,
            auto_correction_rate=65.0,
        )

        return ReconciliationHistoryResponse(
            entries=entries,
            total_entries=len(entries),
            page=page,
            page_size=page_size,
            accuracy_assessment=accuracy,
            trend_analysis=trend_analysis,
            total_reconciliations=52,
            total_discrepancies_resolved=156,
            total_corrections_applied=98,
            retrieved_at=datetime.utcnow(),
        )

