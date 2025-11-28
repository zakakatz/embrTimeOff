/**
 * DirectoryExportButton Component
 * 
 * Button for exporting employee directory data.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import styles from './EmployeeDirectory.module.css';

const EXPORT_FORMATS = [
  { id: 'csv', label: 'CSV', icon: '📊', description: 'Comma-separated values' },
  { id: 'xlsx', label: 'Excel', icon: '📑', description: 'Microsoft Excel format' },
  { id: 'pdf', label: 'PDF', icon: '📄', description: 'Portable document format' },
];

const EXPORT_FIELDS = [
  { id: 'name', label: 'Name', default: true },
  { id: 'email', label: 'Email', default: true },
  { id: 'phone', label: 'Phone', default: true },
  { id: 'jobTitle', label: 'Job Title', default: true },
  { id: 'department', label: 'Department', default: true },
  { id: 'location', label: 'Location', default: false },
  { id: 'manager', label: 'Manager', default: false },
  { id: 'hireDate', label: 'Hire Date', default: false },
  { id: 'employeeId', label: 'Employee ID', default: false },
];

export function DirectoryExportButton({ filters, disabled }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState('csv');
  const [selectedFields, setSelectedFields] = useState(
    EXPORT_FIELDS.filter(f => f.default).map(f => f.id)
  );
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState(null);
  
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target) &&
        !buttonRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const toggleField = useCallback((fieldId) => {
    setSelectedFields((prev) => {
      if (prev.includes(fieldId)) {
        return prev.filter((id) => id !== fieldId);
      }
      return [...prev, fieldId];
    });
  }, []);

  const handleExport = useCallback(async () => {
    if (selectedFields.length === 0) {
      setError('Please select at least one field to export');
      return;
    }

    setIsExporting(true);
    setError(null);

    try {
      const blob = await employeeService.exportDirectory({
        format: selectedFormat,
        filters,
        fields: selectedFields,
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `employee-directory.${selectedFormat}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setIsOpen(false);
    } catch (err) {
      setError('Failed to export directory. Please try again.');
      console.error('Export error:', err);
    } finally {
      setIsExporting(false);
    }
  }, [selectedFormat, selectedFields, filters]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      buttonRef.current?.focus();
    }
  }, []);

  return (
    <div className={styles.exportContainer}>
      <button
        ref={buttonRef}
        type="button"
        className={styles.exportButton}
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label="Export directory"
      >
        <span className={styles.exportIcon} aria-hidden="true">📥</span>
        Export
        <span className={styles.exportChevron} aria-hidden="true">
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {isOpen && (
        <div
          ref={dropdownRef}
          className={styles.exportDropdown}
          role="dialog"
          aria-label="Export options"
          onKeyDown={handleKeyDown}
        >
          <div className={styles.exportSection}>
            <h4 className={styles.exportSectionTitle}>Format</h4>
            <div className={styles.exportFormats}>
              {EXPORT_FORMATS.map((format) => (
                <button
                  key={format.id}
                  type="button"
                  className={`${styles.exportFormatOption} ${
                    selectedFormat === format.id ? styles.exportFormatSelected : ''
                  }`}
                  onClick={() => setSelectedFormat(format.id)}
                  aria-pressed={selectedFormat === format.id}
                >
                  <span className={styles.exportFormatIcon} aria-hidden="true">
                    {format.icon}
                  </span>
                  <span className={styles.exportFormatLabel}>{format.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className={styles.exportSection}>
            <h4 className={styles.exportSectionTitle}>Fields to Include</h4>
            <div className={styles.exportFields}>
              {EXPORT_FIELDS.map((field) => (
                <label key={field.id} className={styles.exportFieldOption}>
                  <input
                    type="checkbox"
                    checked={selectedFields.includes(field.id)}
                    onChange={() => toggleField(field.id)}
                    className={styles.exportFieldCheckbox}
                  />
                  <span className={styles.exportFieldLabel}>{field.label}</span>
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className={styles.exportError} role="alert">
              {error}
            </div>
          )}

          <div className={styles.exportActions}>
            <button
              type="button"
              className={styles.exportCancelButton}
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className={styles.exportSubmitButton}
              onClick={handleExport}
              disabled={isExporting || selectedFields.length === 0}
            >
              {isExporting ? (
                <>
                  <span className={styles.exportSpinner} aria-hidden="true" />
                  Exporting...
                </>
              ) : (
                `Export ${selectedFormat.toUpperCase()}`
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

DirectoryExportButton.propTypes = {
  filters: PropTypes.object,
  disabled: PropTypes.bool,
};

DirectoryExportButton.defaultProps = {
  filters: {},
  disabled: false,
};

export default DirectoryExportButton;

