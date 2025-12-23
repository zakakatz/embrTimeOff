"""Template engine for dynamic content rendering with conditional logic."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class TemplateError(Exception):
    """Base exception for template rendering errors."""
    pass


class TemplateSyntaxError(TemplateError):
    """Raised when template syntax is invalid."""
    pass


class TemplateRenderError(TemplateError):
    """Raised when template rendering fails."""
    pass


class FilterType(str, Enum):
    """Built-in template filters."""
    UPPER = "upper"
    LOWER = "lower"
    TITLE = "title"
    CAPITALIZE = "capitalize"
    CURRENCY = "currency"
    DATE = "date"
    DATE_SHORT = "date_short"
    DATE_LONG = "date_long"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    DEFAULT = "default"
    TRUNCATE = "truncate"
    JOIN = "join"
    LENGTH = "length"
    FIRST = "first"
    LAST = "last"
    SORT = "sort"
    REVERSE = "reverse"
    UNIQUE = "unique"


@dataclass
class TemplateBlock:
    """Represents a parsed template block."""
    block_type: str  # 'text', 'variable', 'if', 'for', 'include'
    content: str
    children: List["TemplateBlock"] = None
    else_block: List["TemplateBlock"] = None
    condition: str = None
    iterator_var: str = None
    iterable_expr: str = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.else_block is None:
            self.else_block = []


class TemplateEngine:
    """
    Template engine supporting dynamic data injection and conditional rendering.
    
    Supports:
    - Variable interpolation: {{ variable_name }}
    - Nested properties: {{ user.profile.name }}
    - Filters: {{ value | filter_name }}
    - Conditionals: {% if condition %} ... {% else %} ... {% endif %}
    - Loops: {% for item in items %} ... {% endfor %}
    - Includes: {% include 'partial_name' %}
    """
    
    # Regex patterns for parsing
    VARIABLE_PATTERN = re.compile(r'\{\{\s*(.+?)\s*\}\}')
    BLOCK_START_PATTERN = re.compile(r'\{%\s*(.+?)\s*%\}')
    IF_PATTERN = re.compile(r'^if\s+(.+)$')
    ELIF_PATTERN = re.compile(r'^elif\s+(.+)$')
    ELSE_PATTERN = re.compile(r'^else$')
    ENDIF_PATTERN = re.compile(r'^endif$')
    FOR_PATTERN = re.compile(r'^for\s+(\w+)\s+in\s+(.+)$')
    ENDFOR_PATTERN = re.compile(r'^endfor$')
    INCLUDE_PATTERN = re.compile(r'^include\s+[\'"](.+?)[\'"]$')
    
    def __init__(self, partials: Optional[Dict[str, str]] = None):
        """
        Initialize the template engine.
        
        Args:
            partials: Dictionary of partial template names to their content
        """
        self.partials = partials or {}
        self._filters = self._get_default_filters()
    
    def _get_default_filters(self) -> Dict[str, callable]:
        """Get built-in filter functions."""
        return {
            "upper": lambda x: str(x).upper() if x else "",
            "lower": lambda x: str(x).lower() if x else "",
            "title": lambda x: str(x).title() if x else "",
            "capitalize": lambda x: str(x).capitalize() if x else "",
            "currency": self._format_currency,
            "date": self._format_date,
            "date_short": lambda x: self._format_date(x, "%m/%d/%Y"),
            "date_long": lambda x: self._format_date(x, "%B %d, %Y"),
            "number": self._format_number,
            "percentage": lambda x: f"{float(x) * 100:.1f}%" if x else "0%",
            "default": lambda x, d="": d if x is None or x == "" else x,
            "truncate": self._truncate,
            "join": lambda x, sep=", ": sep.join(str(i) for i in x) if x else "",
            "length": lambda x: len(x) if x else 0,
            "first": lambda x: x[0] if x else None,
            "last": lambda x: x[-1] if x else None,
            "sort": lambda x: sorted(x) if x else [],
            "reverse": lambda x: list(reversed(x)) if x else [],
            "unique": lambda x: list(dict.fromkeys(x)) if x else [],
        }
    
    def _format_currency(self, value: Any, symbol: str = "$") -> str:
        """Format value as currency."""
        try:
            num = float(value) if value else 0
            return f"{symbol}{num:,.2f}"
        except (ValueError, TypeError):
            return str(value)
    
    def _format_date(self, value: Any, format_str: str = "%Y-%m-%d") -> str:
        """Format value as date."""
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime(format_str)
        if isinstance(value, str):
            try:
                # Try parsing ISO format
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.strftime(format_str)
            except ValueError:
                return value
        return str(value)
    
    def _format_number(self, value: Any, decimals: int = 0) -> str:
        """Format value as number with thousands separator."""
        try:
            num = float(value) if value else 0
            if decimals == 0:
                return f"{int(num):,}"
            return f"{num:,.{decimals}f}"
        except (ValueError, TypeError):
            return str(value)
    
    def _truncate(self, value: Any, length: int = 50, suffix: str = "...") -> str:
        """Truncate string to specified length."""
        text = str(value) if value else ""
        if len(text) <= length:
            return text
        return text[:length - len(suffix)] + suffix
    
    def register_filter(self, name: str, func: callable) -> None:
        """Register a custom filter function."""
        self._filters[name] = func
    
    def register_partial(self, name: str, template: str) -> None:
        """Register a partial template."""
        self.partials[name] = template
    
    def render(self, template: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.
        
        Args:
            template: The template string to render
            context: Dictionary of variables available in the template
            
        Returns:
            Rendered string
            
        Raises:
            TemplateError: If template parsing or rendering fails
        """
        try:
            # Parse template into blocks
            blocks = self._parse_template(template)
            # Render blocks
            return self._render_blocks(blocks, context)
        except TemplateError:
            raise
        except Exception as e:
            raise TemplateRenderError(f"Template rendering failed: {str(e)}")
    
    def _parse_template(self, template: str) -> List[TemplateBlock]:
        """Parse template string into blocks."""
        blocks = []
        position = 0
        
        while position < len(template):
            # Find next block tag
            block_match = self.BLOCK_START_PATTERN.search(template, position)
            var_match = self.VARIABLE_PATTERN.search(template, position)
            
            # Determine which comes first
            next_block = min(
                block_match.start() if block_match else len(template),
                var_match.start() if var_match else len(template)
            )
            
            # Add text before the match
            if next_block > position:
                text = template[position:next_block]
                if text:
                    blocks.append(TemplateBlock(block_type="text", content=text))
            
            if next_block == len(template):
                break
            
            # Handle variable
            if var_match and var_match.start() == next_block:
                blocks.append(TemplateBlock(
                    block_type="variable",
                    content=var_match.group(1)
                ))
                position = var_match.end()
                continue
            
            # Handle block tag
            if block_match and block_match.start() == next_block:
                tag_content = block_match.group(1).strip()
                position = block_match.end()
                
                # Check tag type
                if_match = self.IF_PATTERN.match(tag_content)
                for_match = self.FOR_PATTERN.match(tag_content)
                include_match = self.INCLUDE_PATTERN.match(tag_content)
                
                if if_match:
                    block, position = self._parse_if_block(template, position, if_match.group(1))
                    blocks.append(block)
                elif for_match:
                    block, position = self._parse_for_block(
                        template, position,
                        for_match.group(1),
                        for_match.group(2)
                    )
                    blocks.append(block)
                elif include_match:
                    blocks.append(TemplateBlock(
                        block_type="include",
                        content=include_match.group(1)
                    ))
        
        return blocks
    
    def _parse_if_block(
        self, template: str, position: int, condition: str
    ) -> tuple[TemplateBlock, int]:
        """Parse an if/elif/else/endif block."""
        block = TemplateBlock(
            block_type="if",
            content="",
            condition=condition
        )
        
        current_children = block.children
        depth = 1
        start = position
        
        while position < len(template) and depth > 0:
            match = self.BLOCK_START_PATTERN.search(template, position)
            if not match:
                break
            
            tag_content = match.group(1).strip()
            
            if self.IF_PATTERN.match(tag_content):
                depth += 1
                position = match.end()
            elif self.ENDIF_PATTERN.match(tag_content) and depth == 1:
                # Parse content before endif
                content = template[start:match.start()]
                current_children.extend(self._parse_template(content))
                position = match.end()
                depth = 0
            elif self.ELSE_PATTERN.match(tag_content) and depth == 1:
                # Parse content before else
                content = template[start:match.start()]
                current_children.extend(self._parse_template(content))
                current_children = block.else_block
                position = match.end()
                start = position
            elif self.ELIF_PATTERN.match(tag_content) and depth == 1:
                # Parse content before elif (treat as else with nested if)
                content = template[start:match.start()]
                current_children.extend(self._parse_template(content))
                # Create nested if in else block
                elif_condition = self.ELIF_PATTERN.match(tag_content).group(1)
                nested_if = TemplateBlock(
                    block_type="if",
                    content="",
                    condition=elif_condition
                )
                block.else_block = [nested_if]
                current_children = nested_if.children
                position = match.end()
                start = position
            elif self.ENDIF_PATTERN.match(tag_content):
                depth -= 1
                position = match.end()
            else:
                position = match.end()
        
        return block, position
    
    def _parse_for_block(
        self, template: str, position: int, iterator_var: str, iterable_expr: str
    ) -> tuple[TemplateBlock, int]:
        """Parse a for/endfor block."""
        block = TemplateBlock(
            block_type="for",
            content="",
            iterator_var=iterator_var,
            iterable_expr=iterable_expr
        )
        
        depth = 1
        start = position
        
        while position < len(template) and depth > 0:
            match = self.BLOCK_START_PATTERN.search(template, position)
            if not match:
                break
            
            tag_content = match.group(1).strip()
            
            if self.FOR_PATTERN.match(tag_content):
                depth += 1
                position = match.end()
            elif self.ENDFOR_PATTERN.match(tag_content):
                depth -= 1
                if depth == 0:
                    content = template[start:match.start()]
                    block.children = self._parse_template(content)
                position = match.end()
            else:
                position = match.end()
        
        return block, position
    
    def _render_blocks(self, blocks: List[TemplateBlock], context: Dict[str, Any]) -> str:
        """Render a list of template blocks."""
        result = []
        
        for block in blocks:
            if block.block_type == "text":
                result.append(block.content)
            elif block.block_type == "variable":
                result.append(self._render_variable(block.content, context))
            elif block.block_type == "if":
                result.append(self._render_if_block(block, context))
            elif block.block_type == "for":
                result.append(self._render_for_block(block, context))
            elif block.block_type == "include":
                result.append(self._render_include(block.content, context))
        
        return "".join(result)
    
    def _render_variable(self, expression: str, context: Dict[str, Any]) -> str:
        """Render a variable expression with optional filters."""
        # Split by pipe for filters
        parts = expression.split("|")
        var_path = parts[0].strip()
        filters = [f.strip() for f in parts[1:]]
        
        # Get value
        value = self._resolve_path(var_path, context)
        
        # Apply filters
        for filter_expr in filters:
            value = self._apply_filter(value, filter_expr)
        
        return str(value) if value is not None else ""
    
    def _resolve_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Resolve a dotted path in the context."""
        parts = path.split(".")
        value = context
        
        for part in parts:
            # Check for array indexing
            array_match = re.match(r'(\w+)\[(\d+)\]', part)
            if array_match:
                key = array_match.group(1)
                index = int(array_match.group(2))
                if isinstance(value, dict):
                    value = value.get(key, [])
                elif hasattr(value, key):
                    value = getattr(value, key)
                else:
                    return None
                if isinstance(value, (list, tuple)) and len(value) > index:
                    value = value[index]
                else:
                    return None
            elif isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _apply_filter(self, value: Any, filter_expr: str) -> Any:
        """Apply a filter to a value."""
        # Parse filter name and arguments
        match = re.match(r'(\w+)(?:\((.+)\))?', filter_expr)
        if not match:
            return value
        
        filter_name = match.group(1)
        args_str = match.group(2)
        
        if filter_name not in self._filters:
            return value
        
        filter_func = self._filters[filter_name]
        
        if args_str:
            # Parse arguments
            args = self._parse_filter_args(args_str)
            return filter_func(value, *args)
        
        return filter_func(value)
    
    def _parse_filter_args(self, args_str: str) -> List[Any]:
        """Parse filter arguments string."""
        args = []
        for arg in args_str.split(","):
            arg = arg.strip()
            # Remove quotes from string arguments
            if (arg.startswith('"') and arg.endswith('"')) or \
               (arg.startswith("'") and arg.endswith("'")):
                args.append(arg[1:-1])
            elif arg.isdigit():
                args.append(int(arg))
            elif arg.replace(".", "").isdigit():
                args.append(float(arg))
            elif arg.lower() == "true":
                args.append(True)
            elif arg.lower() == "false":
                args.append(False)
            else:
                args.append(arg)
        return args
    
    def _render_if_block(self, block: TemplateBlock, context: Dict[str, Any]) -> str:
        """Render an if block."""
        if self._evaluate_condition(block.condition, context):
            return self._render_blocks(block.children, context)
        elif block.else_block:
            return self._render_blocks(block.else_block, context)
        return ""
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition expression."""
        # Handle comparison operators
        operators = ["==", "!=", ">=", "<=", ">", "<", " and ", " or ", " not "]
        
        for op in operators:
            if op in condition:
                if op == " and ":
                    parts = condition.split(" and ", 1)
                    return self._evaluate_condition(parts[0], context) and \
                           self._evaluate_condition(parts[1], context)
                elif op == " or ":
                    parts = condition.split(" or ", 1)
                    return self._evaluate_condition(parts[0], context) or \
                           self._evaluate_condition(parts[1], context)
                elif op == " not ":
                    rest = condition.replace(" not ", "", 1).strip()
                    return not self._evaluate_condition(rest, context)
                else:
                    parts = condition.split(op, 1)
                    left = self._resolve_value(parts[0].strip(), context)
                    right = self._resolve_value(parts[1].strip(), context)
                    
                    if op == "==":
                        return left == right
                    elif op == "!=":
                        return left != right
                    elif op == ">=":
                        return left >= right
                    elif op == "<=":
                        return left <= right
                    elif op == ">":
                        return left > right
                    elif op == "<":
                        return left < right
        
        # Simple truthy check
        value = self._resolve_path(condition.strip(), context)
        return bool(value)
    
    def _resolve_value(self, expr: str, context: Dict[str, Any]) -> Any:
        """Resolve an expression to a value."""
        expr = expr.strip()
        
        # String literal
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        
        # Number literal
        if expr.isdigit():
            return int(expr)
        if expr.replace(".", "").replace("-", "").isdigit():
            return float(expr)
        
        # Boolean literal
        if expr.lower() == "true":
            return True
        if expr.lower() == "false":
            return False
        if expr.lower() == "none" or expr.lower() == "null":
            return None
        
        # Variable path
        return self._resolve_path(expr, context)
    
    def _render_for_block(self, block: TemplateBlock, context: Dict[str, Any]) -> str:
        """Render a for loop block."""
        iterable = self._resolve_path(block.iterable_expr, context)
        
        if not iterable:
            return ""
        
        result = []
        items = list(iterable) if not isinstance(iterable, list) else iterable
        
        for index, item in enumerate(items):
            # Create loop context
            loop_context = {
                **context,
                block.iterator_var: item,
                "loop": {
                    "index": index,
                    "index1": index + 1,
                    "first": index == 0,
                    "last": index == len(items) - 1,
                    "length": len(items),
                }
            }
            result.append(self._render_blocks(block.children, loop_context))
        
        return "".join(result)
    
    def _render_include(self, partial_name: str, context: Dict[str, Any]) -> str:
        """Render an included partial template."""
        if partial_name not in self.partials:
            return f"<!-- Partial '{partial_name}' not found -->"
        
        partial_template = self.partials[partial_name]
        return self.render(partial_template, context)
    
    def validate_template(self, template: str) -> List[str]:
        """
        Validate a template for syntax errors.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check for balanced block tags
        if_count = len(re.findall(r'\{%\s*if\s+', template))
        endif_count = len(re.findall(r'\{%\s*endif\s*%\}', template))
        if if_count != endif_count:
            errors.append(f"Unbalanced if/endif: {if_count} if, {endif_count} endif")
        
        for_count = len(re.findall(r'\{%\s*for\s+', template))
        endfor_count = len(re.findall(r'\{%\s*endfor\s*%\}', template))
        if for_count != endfor_count:
            errors.append(f"Unbalanced for/endfor: {for_count} for, {endfor_count} endfor")
        
        # Check for unclosed variable tags
        open_vars = len(re.findall(r'\{\{', template))
        close_vars = len(re.findall(r'\}\}', template))
        if open_vars != close_vars:
            errors.append(f"Unbalanced variable tags: {open_vars} {{ , {close_vars} }}")
        
        # Check for unclosed block tags
        open_blocks = len(re.findall(r'\{%', template))
        close_blocks = len(re.findall(r'%\}', template))
        if open_blocks != close_blocks:
            errors.append(f"Unbalanced block tags: {open_blocks} {{% , {close_blocks} %}}")
        
        return errors

