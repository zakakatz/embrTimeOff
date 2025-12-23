"""File validation service for uploaded documents."""

import hashlib
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Validation error severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FileValidationError(Exception):
    """Exception raised for file validation failures."""
    pass


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    filename: str
    file_size: int
    content_type: str
    issues: List[ValidationIssue] = field(default_factory=list)
    file_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def has_errors(self) -> bool:
        return any(i.severity == ValidationSeverity.ERROR for i in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)


@dataclass
class FileValidationConfig:
    """Configuration for file validation."""
    max_file_size: int = 10 * 1024 * 1024  # 10MB default
    min_file_size: int = 1  # Minimum 1 byte
    allowed_extensions: Set[str] = field(default_factory=lambda: {
        ".pdf", ".csv", ".xlsx", ".xls", ".doc", ".docx",
        ".jpg", ".jpeg", ".png", ".gif", ".txt", ".json"
    })
    allowed_mime_types: Set[str] = field(default_factory=lambda: {
        "application/pdf",
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg",
        "image/png",
        "image/gif",
        "text/plain",
        "application/json",
    })
    check_content_type: bool = True
    compute_hash: bool = True
    hash_algorithm: str = "sha256"
    scan_for_malware: bool = False
    max_filename_length: int = 255
    blocked_patterns: List[str] = field(default_factory=lambda: [
        "..\\", "../", ".exe", ".dll", ".bat", ".cmd", ".sh"
    ])


class FileValidator:
    """
    Service for validating uploaded files.
    
    Validates:
    - File type (extension and MIME type)
    - File size limits
    - Content integrity
    - Filename security (path traversal prevention)
    - Optional malware scanning
    """
    
    # Magic bytes for common file types
    MAGIC_BYTES = {
        b'%PDF': 'application/pdf',
        b'\x89PNG': 'image/png',
        b'\xff\xd8\xff': 'image/jpeg',
        b'GIF87a': 'image/gif',
        b'GIF89a': 'image/gif',
        b'PK\x03\x04': 'application/zip',  # Also xlsx, docx
        b'\xd0\xcf\x11\xe0': 'application/msword',  # Old Office format
    }
    
    def __init__(self, config: Optional[FileValidationConfig] = None):
        """
        Initialize the file validator.
        
        Args:
            config: Validation configuration
        """
        self.config = config or FileValidationConfig()
    
    def validate(
        self,
        file_content: bytes,
        filename: str,
        declared_content_type: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a file.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            declared_content_type: Content-Type header value if provided
            
        Returns:
            ValidationResult with issues if any
        """
        issues = []
        file_size = len(file_content)
        
        # Validate filename
        filename_issues = self._validate_filename(filename)
        issues.extend(filename_issues)
        
        # Validate file size
        size_issues = self._validate_size(file_size)
        issues.extend(size_issues)
        
        # Get extension and detect content type
        extension = self._get_extension(filename)
        detected_type = self._detect_content_type(file_content, filename)
        
        # Validate extension
        ext_issues = self._validate_extension(extension)
        issues.extend(ext_issues)
        
        # Validate content type
        if self.config.check_content_type:
            type_issues = self._validate_content_type(
                detected_type,
                declared_content_type,
                extension
            )
            issues.extend(type_issues)
        
        # Compute file hash
        file_hash = None
        if self.config.compute_hash:
            file_hash = self._compute_hash(file_content)
        
        # Check for potentially malicious content
        security_issues = self._security_check(file_content, filename)
        issues.extend(security_issues)
        
        # Build metadata
        metadata = {
            "extension": extension,
            "detected_mime_type": detected_type,
            "declared_mime_type": declared_content_type,
        }
        
        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        return ValidationResult(
            is_valid=is_valid,
            filename=filename,
            file_size=file_size,
            content_type=detected_type or declared_content_type or "application/octet-stream",
            issues=issues,
            file_hash=file_hash,
            metadata=metadata,
        )
    
    def validate_file_path(self, file_path: str) -> ValidationResult:
        """
        Validate a file from disk.
        
        Args:
            file_path: Path to the file
            
        Returns:
            ValidationResult
        """
        if not os.path.exists(file_path):
            return ValidationResult(
                is_valid=False,
                filename=os.path.basename(file_path),
                file_size=0,
                content_type="",
                issues=[ValidationIssue(
                    code="FILE_NOT_FOUND",
                    message=f"File not found: {file_path}",
                    severity=ValidationSeverity.ERROR,
                )],
            )
        
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Get declared content type from file extension
        declared_type, _ = mimetypes.guess_type(filename)
        
        return self.validate(content, filename, declared_type)
    
    def _validate_filename(self, filename: str) -> List[ValidationIssue]:
        """Validate filename for security issues."""
        issues = []
        
        if not filename:
            issues.append(ValidationIssue(
                code="EMPTY_FILENAME",
                message="Filename is empty",
                severity=ValidationSeverity.ERROR,
            ))
            return issues
        
        # Check length
        if len(filename) > self.config.max_filename_length:
            issues.append(ValidationIssue(
                code="FILENAME_TOO_LONG",
                message=f"Filename exceeds maximum length of {self.config.max_filename_length}",
                severity=ValidationSeverity.ERROR,
                details={"max_length": self.config.max_filename_length, "actual_length": len(filename)},
            ))
        
        # Check for blocked patterns (path traversal, etc.)
        for pattern in self.config.blocked_patterns:
            if pattern in filename.lower():
                issues.append(ValidationIssue(
                    code="BLOCKED_PATTERN",
                    message=f"Filename contains blocked pattern: {pattern}",
                    severity=ValidationSeverity.ERROR,
                    details={"pattern": pattern},
                ))
        
        # Check for null bytes
        if '\x00' in filename:
            issues.append(ValidationIssue(
                code="NULL_BYTE",
                message="Filename contains null byte",
                severity=ValidationSeverity.ERROR,
            ))
        
        # Check for control characters
        if any(ord(c) < 32 for c in filename):
            issues.append(ValidationIssue(
                code="CONTROL_CHARACTERS",
                message="Filename contains control characters",
                severity=ValidationSeverity.WARNING,
            ))
        
        return issues
    
    def _validate_size(self, size: int) -> List[ValidationIssue]:
        """Validate file size."""
        issues = []
        
        if size < self.config.min_file_size:
            issues.append(ValidationIssue(
                code="FILE_TOO_SMALL",
                message=f"File is too small (minimum: {self.config.min_file_size} bytes)",
                severity=ValidationSeverity.ERROR,
                details={"min_size": self.config.min_file_size, "actual_size": size},
            ))
        
        if size > self.config.max_file_size:
            issues.append(ValidationIssue(
                code="FILE_TOO_LARGE",
                message=f"File exceeds maximum size of {self._format_size(self.config.max_file_size)}",
                severity=ValidationSeverity.ERROR,
                details={"max_size": self.config.max_file_size, "actual_size": size},
            ))
        
        return issues
    
    def _validate_extension(self, extension: str) -> List[ValidationIssue]:
        """Validate file extension."""
        issues = []
        
        if not extension:
            issues.append(ValidationIssue(
                code="NO_EXTENSION",
                message="File has no extension",
                severity=ValidationSeverity.WARNING,
            ))
        elif extension.lower() not in self.config.allowed_extensions:
            issues.append(ValidationIssue(
                code="INVALID_EXTENSION",
                message=f"File extension '{extension}' is not allowed",
                severity=ValidationSeverity.ERROR,
                details={
                    "extension": extension,
                    "allowed": list(self.config.allowed_extensions),
                },
            ))
        
        return issues
    
    def _validate_content_type(
        self,
        detected_type: Optional[str],
        declared_type: Optional[str],
        extension: str
    ) -> List[ValidationIssue]:
        """Validate content type."""
        issues = []
        
        # Check if detected type is allowed
        if detected_type and detected_type not in self.config.allowed_mime_types:
            issues.append(ValidationIssue(
                code="INVALID_CONTENT_TYPE",
                message=f"Content type '{detected_type}' is not allowed",
                severity=ValidationSeverity.ERROR,
                details={"content_type": detected_type},
            ))
        
        # Check for type mismatch
        if detected_type and declared_type:
            if detected_type != declared_type:
                # Some types are equivalent
                equivalent_types = {
                    ("application/zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ("application/zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                }
                
                type_pair = (detected_type, declared_type)
                is_equivalent = type_pair in equivalent_types or tuple(reversed(type_pair)) in equivalent_types
                
                if not is_equivalent:
                    issues.append(ValidationIssue(
                        code="CONTENT_TYPE_MISMATCH",
                        message=f"Declared content type '{declared_type}' does not match detected type '{detected_type}'",
                        severity=ValidationSeverity.WARNING,
                        details={"declared": declared_type, "detected": detected_type},
                    ))
        
        # Check extension matches content type
        expected_type, _ = mimetypes.guess_type(f"file{extension}")
        if expected_type and detected_type and expected_type != detected_type:
            # Some leniency for zip-based formats
            if not (detected_type == "application/zip" and extension in (".xlsx", ".docx")):
                issues.append(ValidationIssue(
                    code="EXTENSION_CONTENT_MISMATCH",
                    message=f"File extension '{extension}' suggests '{expected_type}' but content is '{detected_type}'",
                    severity=ValidationSeverity.WARNING,
                    details={"extension": extension, "expected": expected_type, "detected": detected_type},
                ))
        
        return issues
    
    def _detect_content_type(self, content: bytes, filename: str) -> Optional[str]:
        """Detect content type from file content using magic bytes."""
        if not content:
            return None
        
        # Check magic bytes
        for magic, mime_type in self.MAGIC_BYTES.items():
            if content.startswith(magic):
                # Special handling for zip-based formats
                if mime_type == "application/zip":
                    ext = self._get_extension(filename)
                    if ext == ".xlsx":
                        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    elif ext == ".docx":
                        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                return mime_type
        
        # Try to detect CSV
        if self._looks_like_csv(content):
            return "text/csv"
        
        # Try to detect JSON
        if self._looks_like_json(content):
            return "application/json"
        
        # Fall back to mimetypes
        guessed_type, _ = mimetypes.guess_type(filename)
        return guessed_type
    
    def _looks_like_csv(self, content: bytes) -> bool:
        """Check if content looks like CSV."""
        try:
            # Check first few lines
            text = content[:1024].decode('utf-8', errors='ignore')
            lines = text.split('\n')[:5]
            if len(lines) < 2:
                return False
            
            # Check for consistent delimiter
            for delimiter in [',', ';', '\t']:
                counts = [line.count(delimiter) for line in lines if line.strip()]
                if len(counts) >= 2 and all(c == counts[0] and c > 0 for c in counts):
                    return True
            
            return False
        except Exception:
            return False
    
    def _looks_like_json(self, content: bytes) -> bool:
        """Check if content looks like JSON."""
        try:
            text = content.decode('utf-8', errors='ignore').strip()
            return (text.startswith('{') and text.endswith('}')) or \
                   (text.startswith('[') and text.endswith(']'))
        except Exception:
            return False
    
    def _security_check(self, content: bytes, filename: str) -> List[ValidationIssue]:
        """Perform security checks on file content."""
        issues = []
        
        # Check for embedded scripts in certain file types
        ext = self._get_extension(filename)
        
        if ext in (".html", ".htm", ".svg"):
            # Check for script tags
            if b'<script' in content.lower():
                issues.append(ValidationIssue(
                    code="EMBEDDED_SCRIPT",
                    message="File contains embedded script tags",
                    severity=ValidationSeverity.ERROR,
                ))
            
            # Check for event handlers
            event_handlers = [b'onclick', b'onerror', b'onload', b'onmouseover']
            for handler in event_handlers:
                if handler in content.lower():
                    issues.append(ValidationIssue(
                        code="EVENT_HANDLER",
                        message=f"File contains event handler: {handler.decode()}",
                        severity=ValidationSeverity.WARNING,
                    ))
                    break
        
        # Check for executable content markers
        if content.startswith(b'MZ'):  # Windows executable
            issues.append(ValidationIssue(
                code="EXECUTABLE_CONTENT",
                message="File appears to be a Windows executable",
                severity=ValidationSeverity.ERROR,
            ))
        
        if content.startswith(b'\x7fELF'):  # Linux executable
            issues.append(ValidationIssue(
                code="EXECUTABLE_CONTENT",
                message="File appears to be a Linux executable",
                severity=ValidationSeverity.ERROR,
            ))
        
        return issues
    
    def _compute_hash(self, content: bytes) -> str:
        """Compute hash of file content."""
        if self.config.hash_algorithm == "md5":
            return hashlib.md5(content).hexdigest()
        elif self.config.hash_algorithm == "sha1":
            return hashlib.sha1(content).hexdigest()
        elif self.config.hash_algorithm == "sha512":
            return hashlib.sha512(content).hexdigest()
        else:  # Default to sha256
            return hashlib.sha256(content).hexdigest()
    
    def _get_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        _, ext = os.path.splitext(filename)
        return ext.lower()
    
    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

