"""Email template service for dynamic content rendering."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TemplateError(Exception):
    """Exception raised for template errors."""
    pass


@dataclass
class EmailTemplate:
    """Email template definition."""
    id: str
    name: str
    subject: str
    html_template: str
    text_template: Optional[str] = None
    description: Optional[str] = None
    variables: List[str] = field(default_factory=list)
    category: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class EmailTemplateService:
    """
    Service for managing and rendering email templates.
    
    Features:
    - Variable substitution with {{ variable }} syntax
    - Conditional content with {% if condition %} syntax
    - Loop support with {% for item in items %} syntax
    - Default values with {{ variable | default:"fallback" }}
    - HTML escaping for security
    """
    
    # Regex patterns
    VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+(?:\.\w+)*)\s*(?:\|\s*(\w+)(?::"([^"]*)")?)?\s*\}\}')
    IF_PATTERN = re.compile(r'\{%\s*if\s+(\w+(?:\.\w+)*)\s*%\}(.*?)\{%\s*endif\s*%\}', re.DOTALL)
    IF_ELSE_PATTERN = re.compile(
        r'\{%\s*if\s+(\w+(?:\.\w+)*)\s*%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}',
        re.DOTALL
    )
    FOR_PATTERN = re.compile(
        r'\{%\s*for\s+(\w+)\s+in\s+(\w+(?:\.\w+)*)\s*%\}(.*?)\{%\s*endfor\s*%\}',
        re.DOTALL
    )
    
    def __init__(self):
        """Initialize the template service."""
        self._templates: Dict[str, EmailTemplate] = {}
        self._filters: Dict[str, callable] = self._get_default_filters()
        self._register_built_in_templates()
    
    def _get_default_filters(self) -> Dict[str, callable]:
        """Get default filter functions."""
        return {
            "default": lambda v, d: d if v is None or v == "" else v,
            "upper": lambda v, _: str(v).upper() if v else "",
            "lower": lambda v, _: str(v).lower() if v else "",
            "title": lambda v, _: str(v).title() if v else "",
            "capitalize": lambda v, _: str(v).capitalize() if v else "",
            "date": lambda v, fmt: self._format_date(v, fmt or "%Y-%m-%d"),
            "currency": lambda v, _: f"${float(v):,.2f}" if v else "$0.00",
            "escape": lambda v, _: self._html_escape(str(v)) if v else "",
        }
    
    def _format_date(self, value: Any, format_str: str) -> str:
        """Format a date value."""
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime(format_str)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.strftime(format_str)
            except ValueError:
                return value
        return str(value)
    
    def _html_escape(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
    
    def register_template(self, template: EmailTemplate) -> None:
        """
        Register an email template.
        
        Args:
            template: EmailTemplate to register
        """
        self._templates[template.id] = template
        logger.info(f"Registered email template: {template.id}")
    
    def get_template(self, template_id: str) -> Optional[EmailTemplate]:
        """
        Get a template by ID.
        
        Args:
            template_id: Template identifier
            
        Returns:
            EmailTemplate or None if not found
        """
        return self._templates.get(template_id)
    
    def list_templates(self, category: Optional[str] = None) -> List[EmailTemplate]:
        """
        List all templates.
        
        Args:
            category: Filter by category
            
        Returns:
            List of EmailTemplate objects
        """
        templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates
    
    def render(
        self,
        template_id: str,
        context: Dict[str, Any],
        escape_html: bool = True
    ) -> tuple[str, str, Optional[str]]:
        """
        Render a template with context data.
        
        Args:
            template_id: Template identifier
            context: Variable values
            escape_html: Whether to escape HTML in variables
            
        Returns:
            Tuple of (subject, html_content, text_content)
            
        Raises:
            TemplateError: If template not found or rendering fails
        """
        template = self._templates.get(template_id)
        if not template:
            raise TemplateError(f"Template not found: {template_id}")
        
        if not template.is_active:
            raise TemplateError(f"Template is inactive: {template_id}")
        
        try:
            subject = self._render_string(template.subject, context, escape_html=False)
            html = self._render_string(template.html_template, context, escape_html)
            text = None
            if template.text_template:
                text = self._render_string(template.text_template, context, escape_html=False)
            
            return subject, html, text
        except Exception as e:
            raise TemplateError(f"Template rendering failed: {str(e)}")
    
    def render_string(
        self,
        template_string: str,
        context: Dict[str, Any],
        escape_html: bool = True
    ) -> str:
        """
        Render a template string directly.
        
        Args:
            template_string: Template content
            context: Variable values
            escape_html: Whether to escape HTML in variables
            
        Returns:
            Rendered string
        """
        return self._render_string(template_string, context, escape_html)
    
    def _render_string(
        self,
        template: str,
        context: Dict[str, Any],
        escape_html: bool = True
    ) -> str:
        """Internal template rendering."""
        result = template
        
        # Process for loops first
        result = self._process_for_loops(result, context, escape_html)
        
        # Process if/else blocks
        result = self._process_conditionals(result, context, escape_html)
        
        # Process simple if blocks
        result = self._process_simple_conditionals(result, context, escape_html)
        
        # Process variables
        result = self._process_variables(result, context, escape_html)
        
        return result
    
    def _process_variables(
        self,
        template: str,
        context: Dict[str, Any],
        escape_html: bool
    ) -> str:
        """Process variable substitutions."""
        def replace_var(match):
            var_path = match.group(1)
            filter_name = match.group(2)
            filter_arg = match.group(3)
            
            value = self._resolve_path(var_path, context)
            
            # Apply filter if specified
            if filter_name and filter_name in self._filters:
                value = self._filters[filter_name](value, filter_arg)
            elif escape_html and value:
                value = self._html_escape(str(value))
            
            return str(value) if value is not None else ""
        
        return self.VARIABLE_PATTERN.sub(replace_var, template)
    
    def _process_conditionals(
        self,
        template: str,
        context: Dict[str, Any],
        escape_html: bool
    ) -> str:
        """Process if/else conditional blocks."""
        def replace_conditional(match):
            condition_path = match.group(1)
            true_content = match.group(2)
            false_content = match.group(3)
            
            condition_value = self._resolve_path(condition_path, context)
            
            if self._is_truthy(condition_value):
                return self._render_string(true_content, context, escape_html)
            return self._render_string(false_content, context, escape_html)
        
        return self.IF_ELSE_PATTERN.sub(replace_conditional, template)
    
    def _process_simple_conditionals(
        self,
        template: str,
        context: Dict[str, Any],
        escape_html: bool
    ) -> str:
        """Process simple if blocks (without else)."""
        def replace_simple_conditional(match):
            condition_path = match.group(1)
            content = match.group(2)
            
            condition_value = self._resolve_path(condition_path, context)
            
            if self._is_truthy(condition_value):
                return self._render_string(content, context, escape_html)
            return ""
        
        return self.IF_PATTERN.sub(replace_simple_conditional, template)
    
    def _process_for_loops(
        self,
        template: str,
        context: Dict[str, Any],
        escape_html: bool
    ) -> str:
        """Process for loop blocks."""
        def replace_loop(match):
            item_var = match.group(1)
            iterable_path = match.group(2)
            content = match.group(3)
            
            iterable = self._resolve_path(iterable_path, context)
            
            if not iterable:
                return ""
            
            result_parts = []
            items = list(iterable) if not isinstance(iterable, list) else iterable
            
            for idx, item in enumerate(items):
                loop_context = {
                    **context,
                    item_var: item,
                    "loop": {
                        "index": idx,
                        "index1": idx + 1,
                        "first": idx == 0,
                        "last": idx == len(items) - 1,
                        "length": len(items),
                    }
                }
                result_parts.append(self._render_string(content, loop_context, escape_html))
            
            return "".join(result_parts)
        
        return self.FOR_PATTERN.sub(replace_loop, template)
    
    def _resolve_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Resolve a dotted path in the context."""
        parts = path.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _is_truthy(self, value: Any) -> bool:
        """Check if a value is truthy."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (list, dict, str)):
            return len(value) > 0
        if isinstance(value, (int, float)):
            return value != 0
        return True
    
    def validate_template(self, template_string: str) -> List[str]:
        """
        Validate a template string for syntax errors.
        
        Args:
            template_string: Template to validate
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check for balanced if/endif
        if_count = len(re.findall(r'\{%\s*if\s+', template_string))
        endif_count = len(re.findall(r'\{%\s*endif\s*%\}', template_string))
        if if_count != endif_count:
            errors.append(f"Unbalanced if/endif: {if_count} if, {endif_count} endif")
        
        # Check for balanced for/endfor
        for_count = len(re.findall(r'\{%\s*for\s+', template_string))
        endfor_count = len(re.findall(r'\{%\s*endfor\s*%\}', template_string))
        if for_count != endfor_count:
            errors.append(f"Unbalanced for/endfor: {for_count} for, {endfor_count} endfor")
        
        # Check for unclosed variable tags
        open_vars = len(re.findall(r'\{\{', template_string))
        close_vars = len(re.findall(r'\}\}', template_string))
        if open_vars != close_vars:
            errors.append(f"Unbalanced variable tags: {open_vars} {{ , {close_vars} }}")
        
        return errors
    
    def extract_variables(self, template_string: str) -> List[str]:
        """
        Extract variable names used in a template.
        
        Args:
            template_string: Template to analyze
            
        Returns:
            List of variable names
        """
        variables = set()
        
        # Find all variable references
        for match in self.VARIABLE_PATTERN.finditer(template_string):
            var_path = match.group(1)
            # Get the root variable
            variables.add(var_path.split(".")[0])
        
        # Find variables in conditionals
        for match in self.IF_PATTERN.finditer(template_string):
            var_path = match.group(1)
            variables.add(var_path.split(".")[0])
        
        for match in self.IF_ELSE_PATTERN.finditer(template_string):
            var_path = match.group(1)
            variables.add(var_path.split(".")[0])
        
        # Find iterables in for loops
        for match in self.FOR_PATTERN.finditer(template_string):
            var_path = match.group(2)
            variables.add(var_path.split(".")[0])
        
        return sorted(list(variables))
    
    def _register_built_in_templates(self) -> None:
        """Register built-in email templates."""
        
        # Welcome email template
        welcome_template = EmailTemplate(
            id="welcome",
            name="Welcome Email",
            subject="Welcome to {{ company_name }}, {{ user.first_name }}!",
            category="onboarding",
            variables=["user", "company_name", "login_url"],
            html_template="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #4a90d9; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f9f9f9; }
        .button { display: inline-block; padding: 12px 24px; background: #4a90d9; color: white; text-decoration: none; border-radius: 4px; }
        .footer { padding: 20px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to {{ company_name }}!</h1>
        </div>
        <div class="content">
            <p>Hi {{ user.first_name }},</p>
            <p>Welcome to the team! We're excited to have you join us.</p>
            <p>Your account has been set up and you can log in using the button below:</p>
            <p style="text-align: center;">
                <a href="{{ login_url }}" class="button">Log In to Your Account</a>
            </p>
            {% if user.manager %}
            <p>Your manager is {{ user.manager.name }}, who will help you get started.</p>
            {% endif %}
            <p>If you have any questions, don't hesitate to reach out!</p>
        </div>
        <div class="footer">
            <p>&copy; {{ company_name }}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
""",
            text_template="""
Welcome to {{ company_name }}!

Hi {{ user.first_name }},

Welcome to the team! We're excited to have you join us.

Your account has been set up. Log in at: {{ login_url }}

{% if user.manager %}Your manager is {{ user.manager.name }}, who will help you get started.{% endif %}

If you have any questions, don't hesitate to reach out!

© {{ company_name }}. All rights reserved.
"""
        )
        
        # Password reset template
        password_reset_template = EmailTemplate(
            id="password_reset",
            name="Password Reset",
            subject="Reset Your Password",
            category="authentication",
            variables=["user", "reset_url", "expiry_hours"],
            html_template="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .content { padding: 20px; background: #f9f9f9; }
        .button { display: inline-block; padding: 12px 24px; background: #d94a4a; color: white; text-decoration: none; border-radius: 4px; }
        .warning { color: #d94a4a; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            <h2>Password Reset Request</h2>
            <p>Hi {{ user.first_name | default:"there" }},</p>
            <p>We received a request to reset your password. Click the button below to create a new password:</p>
            <p style="text-align: center;">
                <a href="{{ reset_url }}" class="button">Reset Password</a>
            </p>
            <p class="warning">This link will expire in {{ expiry_hours | default:"24" }} hours.</p>
            <p>If you didn't request a password reset, you can safely ignore this email.</p>
        </div>
    </div>
</body>
</html>
""",
            text_template="""
Password Reset Request

Hi {{ user.first_name | default:"there" }},

We received a request to reset your password.

Reset your password here: {{ reset_url }}

This link will expire in {{ expiry_hours | default:"24" }} hours.

If you didn't request a password reset, you can safely ignore this email.
"""
        )
        
        # Notification template
        notification_template = EmailTemplate(
            id="notification",
            name="General Notification",
            subject="{{ notification_title }}",
            category="notification",
            variables=["notification_title", "notification_body", "action_url", "action_text"],
            html_template="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .content { padding: 20px; background: #f9f9f9; }
        .button { display: inline-block; padding: 12px 24px; background: #4a90d9; color: white; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            <h2>{{ notification_title }}</h2>
            <p>{{ notification_body }}</p>
            {% if action_url %}
            <p style="text-align: center;">
                <a href="{{ action_url }}" class="button">{{ action_text | default:"View Details" }}</a>
            </p>
            {% endif %}
        </div>
    </div>
</body>
</html>
""",
            text_template="""
{{ notification_title }}

{{ notification_body }}

{% if action_url %}{{ action_text | default:"View Details" }}: {{ action_url }}{% endif %}
"""
        )
        
        self.register_template(welcome_template)
        self.register_template(password_reset_template)
        self.register_template(notification_template)

