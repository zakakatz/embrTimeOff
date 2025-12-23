"""PDF generation service for creating documents from HTML templates."""

import io
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.services.document_generation.template_engine import TemplateEngine

logger = logging.getLogger(__name__)


class PageSize(str, Enum):
    """Standard page sizes."""
    A4 = "A4"
    LETTER = "Letter"
    LEGAL = "Legal"
    A3 = "A3"
    A5 = "A5"


class PageOrientation(str, Enum):
    """Page orientation options."""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass
class PageMargins:
    """Page margins configuration."""
    top: float = 25.0  # mm
    right: float = 25.0
    bottom: float = 25.0
    left: float = 25.0


@dataclass
class PDFMetadata:
    """PDF document metadata."""
    title: str = ""
    author: str = ""
    subject: str = ""
    creator: str = "Employee Management System"
    creation_date: datetime = None
    keywords: List[str] = None
    
    def __post_init__(self):
        if self.creation_date is None:
            self.creation_date = datetime.utcnow()
        if self.keywords is None:
            self.keywords = []


@dataclass
class PDFConfig:
    """PDF generation configuration."""
    page_size: PageSize = PageSize.A4
    orientation: PageOrientation = PageOrientation.PORTRAIT
    margins: PageMargins = None
    metadata: PDFMetadata = None
    header_template: Optional[str] = None
    footer_template: Optional[str] = None
    include_page_numbers: bool = True
    base_font_size: int = 12
    
    def __post_init__(self):
        if self.margins is None:
            self.margins = PageMargins()
        if self.metadata is None:
            self.metadata = PDFMetadata()


class PDFService:
    """
    Service for generating PDF documents from HTML templates.
    
    Supports:
    - HTML to PDF conversion
    - Custom headers and footers
    - Dynamic content injection via templates
    - Multiple page sizes and orientations
    - CSS styling
    - Page numbering
    """
    
    # Default CSS styles for PDF documents
    DEFAULT_STYLES = """
        @page {
            size: %(page_size)s %(orientation)s;
            margin: %(margin_top)smm %(margin_right)smm %(margin_bottom)smm %(margin_left)smm;
            @top-center {
                content: element(header);
            }
            @bottom-center {
                content: element(footer);
            }
        }
        
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: %(font_size)spt;
            line-height: 1.5;
            color: #333;
        }
        
        h1 { font-size: 24pt; margin-bottom: 12pt; color: #1a1a1a; }
        h2 { font-size: 18pt; margin-bottom: 10pt; color: #2a2a2a; }
        h3 { font-size: 14pt; margin-bottom: 8pt; color: #3a3a3a; }
        
        p { margin-bottom: 10pt; }
        
        table {
            width: 100%%;
            border-collapse: collapse;
            margin-bottom: 16pt;
        }
        
        th, td {
            border: 1px solid #ddd;
            padding: 8pt;
            text-align: left;
        }
        
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        
        tr:nth-child(even) {
            background-color: #fafafa;
        }
        
        .header {
            position: running(header);
            padding-bottom: 10pt;
            border-bottom: 1px solid #eee;
        }
        
        .footer {
            position: running(footer);
            padding-top: 10pt;
            border-top: 1px solid #eee;
            font-size: 10pt;
            color: #666;
        }
        
        .page-break {
            page-break-after: always;
        }
        
        .no-break {
            page-break-inside: avoid;
        }
    """
    
    def __init__(self, template_engine: Optional[TemplateEngine] = None):
        """
        Initialize the PDF service.
        
        Args:
            template_engine: Template engine for content rendering
        """
        self.template_engine = template_engine or TemplateEngine()
        self._pdf_generator = None
        self._initialize_generator()
    
    def _initialize_generator(self) -> None:
        """Initialize the PDF generation backend."""
        # Try to use weasyprint if available
        try:
            import weasyprint
            self._pdf_generator = "weasyprint"
            logger.info("Using WeasyPrint for PDF generation")
        except ImportError:
            # Fall back to reportlab if available
            try:
                import reportlab
                self._pdf_generator = "reportlab"
                logger.info("Using ReportLab for PDF generation")
            except ImportError:
                self._pdf_generator = "mock"
                logger.warning(
                    "No PDF library available. Install weasyprint or reportlab "
                    "for actual PDF generation. Using mock generator."
                )
    
    def generate(
        self,
        html_content: str,
        config: Optional[PDFConfig] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generate a PDF from HTML content.
        
        Args:
            html_content: HTML string or template
            config: PDF configuration options
            context: Template context for dynamic content
            
        Returns:
            PDF file content as bytes
        """
        config = config or PDFConfig()
        context = context or {}
        
        # Add default context variables
        context.setdefault("generated_at", datetime.utcnow())
        context.setdefault("page_size", config.page_size.value)
        
        # Render template if context provided
        rendered_html = self.template_engine.render(html_content, context)
        
        # Build complete HTML document
        full_html = self._build_html_document(rendered_html, config, context)
        
        # Generate PDF using available backend
        if self._pdf_generator == "weasyprint":
            return self._generate_weasyprint(full_html, config)
        elif self._pdf_generator == "reportlab":
            return self._generate_reportlab(full_html, config)
        else:
            return self._generate_mock(full_html, config)
    
    def generate_from_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        config: Optional[PDFConfig] = None
    ) -> bytes:
        """
        Generate a PDF from a named template.
        
        Args:
            template_name: Name of the template to use
            context: Template context for dynamic content
            config: PDF configuration options
            
        Returns:
            PDF file content as bytes
        """
        template = self._get_template(template_name)
        return self.generate(template, config, context)
    
    def _build_html_document(
        self,
        body_content: str,
        config: PDFConfig,
        context: Dict[str, Any]
    ) -> str:
        """Build a complete HTML document with styles, header, and footer."""
        # Render header if provided
        header_html = ""
        if config.header_template:
            header_content = self.template_engine.render(
                config.header_template, context
            )
            header_html = f'<div class="header">{header_content}</div>'
        
        # Render footer if provided
        footer_html = ""
        if config.footer_template:
            footer_content = self.template_engine.render(
                config.footer_template, context
            )
            footer_html = f'<div class="footer">{footer_content}</div>'
        elif config.include_page_numbers:
            footer_html = '''
                <div class="footer">
                    <span>Generated on {{ generated_at | date }}</span>
                    <span style="float: right;">Page <span class="page-number"></span></span>
                </div>
            '''
            footer_html = self.template_engine.render(footer_html, context)
        
        # Build CSS with configuration
        styles = self.DEFAULT_STYLES % {
            "page_size": config.page_size.value,
            "orientation": config.orientation.value,
            "margin_top": config.margins.top,
            "margin_right": config.margins.right,
            "margin_bottom": config.margins.bottom,
            "margin_left": config.margins.left,
            "font_size": config.base_font_size,
        }
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="title" content="{config.metadata.title}">
            <meta name="author" content="{config.metadata.author}">
            <style>
                {styles}
            </style>
        </head>
        <body>
            {header_html}
            <main>
                {body_content}
            </main>
            {footer_html}
        </body>
        </html>
        """
    
    def _generate_weasyprint(self, html: str, config: PDFConfig) -> bytes:
        """Generate PDF using WeasyPrint."""
        try:
            from weasyprint import HTML, CSS
            
            pdf_file = io.BytesIO()
            doc = HTML(string=html)
            doc.write_pdf(pdf_file)
            pdf_file.seek(0)
            return pdf_file.read()
        except Exception as e:
            logger.error(f"WeasyPrint PDF generation failed: {e}")
            raise
    
    def _generate_reportlab(self, html: str, config: PDFConfig) -> bytes:
        """Generate PDF using ReportLab (basic HTML support)."""
        try:
            from reportlab.lib.pagesizes import A4, LETTER, LEGAL, A3, A5, landscape
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import mm
            
            # Map page sizes
            page_sizes = {
                PageSize.A4: A4,
                PageSize.LETTER: LETTER,
                PageSize.LEGAL: LEGAL,
                PageSize.A3: A3,
                PageSize.A5: A5,
            }
            
            page_size = page_sizes.get(config.page_size, A4)
            if config.orientation == PageOrientation.LANDSCAPE:
                page_size = landscape(page_size)
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=page_size,
                leftMargin=config.margins.left * mm,
                rightMargin=config.margins.right * mm,
                topMargin=config.margins.top * mm,
                bottomMargin=config.margins.bottom * mm,
            )
            
            # Parse HTML content (basic parsing)
            styles = getSampleStyleSheet()
            story = self._parse_html_for_reportlab(html, styles)
            
            # Set metadata
            doc.title = config.metadata.title
            doc.author = config.metadata.author
            doc.subject = config.metadata.subject
            
            doc.build(story)
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            logger.error(f"ReportLab PDF generation failed: {e}")
            raise
    
    def _parse_html_for_reportlab(self, html: str, styles) -> list:
        """Parse HTML content for ReportLab (basic implementation)."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import mm
        import re
        
        story = []
        
        # Extract body content
        body_match = re.search(r'<main>(.*?)</main>', html, re.DOTALL)
        if body_match:
            content = body_match.group(1)
        else:
            content = html
        
        # Split by paragraphs and headings
        blocks = re.split(r'(<h[1-6][^>]*>.*?</h[1-6]>|<p[^>]*>.*?</p>)', content, flags=re.DOTALL)
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # Heading
            h_match = re.match(r'<h([1-6])[^>]*>(.*?)</h\1>', block, re.DOTALL)
            if h_match:
                level = int(h_match.group(1))
                text = self._strip_html_tags(h_match.group(2))
                style_name = f'Heading{level}' if level <= 6 else 'Normal'
                if style_name in styles:
                    story.append(Paragraph(text, styles[style_name]))
                else:
                    story.append(Paragraph(text, styles['Normal']))
                story.append(Spacer(1, 6 * mm))
                continue
            
            # Paragraph
            p_match = re.match(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if p_match:
                text = self._strip_html_tags(p_match.group(1))
                story.append(Paragraph(text, styles['Normal']))
                story.append(Spacer(1, 4 * mm))
                continue
            
            # Plain text
            text = self._strip_html_tags(block)
            if text:
                story.append(Paragraph(text, styles['Normal']))
                story.append(Spacer(1, 4 * mm))
        
        return story
    
    def _strip_html_tags(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re
        clean = re.sub(r'<[^>]+>', '', text)
        return clean.strip()
    
    def _generate_mock(self, html: str, config: PDFConfig) -> bytes:
        """Generate a mock PDF for testing when no PDF library is available."""
        logger.warning("Using mock PDF generator - output is not a valid PDF")
        
        # Create a simple text representation
        content = f"""
%%PDF-1.4
%Mock PDF Document

Title: {config.metadata.title}
Author: {config.metadata.author}
Page Size: {config.page_size.value}
Orientation: {config.orientation.value}
Generated: {datetime.utcnow().isoformat()}

--- Content Preview ---
{self._strip_html_tags(html)[:2000]}

%%EOF
"""
        return content.encode('utf-8')
    
    def _get_template(self, template_name: str) -> str:
        """Get a built-in template by name."""
        templates = {
            "employee_report": self._get_employee_report_template(),
            "time_off_summary": self._get_time_off_summary_template(),
            "org_chart": self._get_org_chart_template(),
            "audit_report": self._get_audit_report_template(),
        }
        
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        return templates[template_name]
    
    def _get_employee_report_template(self) -> str:
        """Employee report template."""
        return """
        <h1>Employee Report</h1>
        <p>Generated: {{ generated_at | date_long }}</p>
        
        {% if employee %}
        <section class="no-break">
            <h2>Personal Information</h2>
            <table>
                <tr>
                    <th>Name</th>
                    <td>{{ employee.first_name }} {{ employee.last_name }}</td>
                </tr>
                <tr>
                    <th>Employee ID</th>
                    <td>{{ employee.employee_id }}</td>
                </tr>
                <tr>
                    <th>Email</th>
                    <td>{{ employee.email }}</td>
                </tr>
                <tr>
                    <th>Department</th>
                    <td>{{ employee.department.name | default("N/A") }}</td>
                </tr>
                <tr>
                    <th>Title</th>
                    <td>{{ employee.job_title | default("N/A") }}</td>
                </tr>
                <tr>
                    <th>Start Date</th>
                    <td>{{ employee.start_date | date }}</td>
                </tr>
            </table>
        </section>
        {% endif %}
        
        {% if employee.manager %}
        <section class="no-break">
            <h2>Reporting Structure</h2>
            <table>
                <tr>
                    <th>Manager</th>
                    <td>{{ employee.manager.first_name }} {{ employee.manager.last_name }}</td>
                </tr>
                <tr>
                    <th>Manager Email</th>
                    <td>{{ employee.manager.email }}</td>
                </tr>
            </table>
        </section>
        {% endif %}
        """
    
    def _get_time_off_summary_template(self) -> str:
        """Time-off summary template."""
        return """
        <h1>Time-Off Summary Report</h1>
        <p>Employee: {{ employee.first_name }} {{ employee.last_name }}</p>
        <p>Period: {{ period_start | date }} - {{ period_end | date }}</p>
        
        <h2>Balance Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Available</th>
                    <th>Used</th>
                    <th>Pending</th>
                </tr>
            </thead>
            <tbody>
            {% for balance in balances %}
                <tr>
                    <td>{{ balance.type }}</td>
                    <td>{{ balance.available }}</td>
                    <td>{{ balance.used }}</td>
                    <td>{{ balance.pending }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        
        {% if requests %}
        <h2>Recent Requests</h2>
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Start Date</th>
                    <th>End Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
            {% for request in requests %}
                <tr>
                    <td>{{ request.type }}</td>
                    <td>{{ request.start_date | date }}</td>
                    <td>{{ request.end_date | date }}</td>
                    <td>{{ request.status }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}
        """
    
    def _get_org_chart_template(self) -> str:
        """Organization chart template."""
        return """
        <h1>Organizational Chart</h1>
        <p>Department: {{ department.name }}</p>
        <p>Generated: {{ generated_at | date_long }}</p>
        
        <h2>Team Structure</h2>
        {% for member in team_members %}
        <div class="no-break" style="margin-left: {{ member.level | multiply(20) }}px;">
            <strong>{{ member.name }}</strong>
            {% if member.title %} - {{ member.title }}{% endif %}
            {% if member.direct_reports > 0 %}
                <span style="color: #666;">({{ member.direct_reports }} direct reports)</span>
            {% endif %}
        </div>
        {% endfor %}
        """
    
    def _get_audit_report_template(self) -> str:
        """Audit report template."""
        return """
        <h1>Audit Trail Report</h1>
        <p>Entity: {{ entity_type }} #{{ entity_id }}</p>
        <p>Period: {{ start_date | date }} - {{ end_date | date }}</p>
        
        <h2>Change History</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Action</th>
                    <th>User</th>
                    <th>Field</th>
                    <th>Old Value</th>
                    <th>New Value</th>
                </tr>
            </thead>
            <tbody>
            {% for entry in audit_entries %}
                <tr>
                    <td>{{ entry.timestamp | date }}</td>
                    <td>{{ entry.action }}</td>
                    <td>{{ entry.user_name }}</td>
                    <td>{{ entry.field_name }}</td>
                    <td>{{ entry.old_value | truncate(30) }}</td>
                    <td>{{ entry.new_value | truncate(30) }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        
        <p class="footer">Total changes: {{ audit_entries | length }}</p>
        """
    
    def register_template(self, name: str, template: str) -> None:
        """Register a custom template."""
        self.template_engine.register_partial(name, template)

