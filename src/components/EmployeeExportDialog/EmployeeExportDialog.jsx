/**
 * Employee Export Dialog Component
 * 
 * Provides customizable employee data export with field selection,
 * filtering options, and format configuration.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeExportDialog.module.css';
import { ExportOptionsForm } from './ExportOptionsForm';
import { ExportProgressDisplay } from './ExportProgressDisplay';

const EXPORT_STATES = {
  CONFIGURE: 'configure',
  EXPORTING: 'exporting',
  COMPLETED: 'completed',
  ERROR: 'error',
};

const DEFAULT_EXPORT_OPTIONS = {
  fields: [],
  includeAllFields: false,
  filters: {
    departmentIds: [],
    locationIds: [],
    employmentStatus: [],
    isActive: true,
  },
  format: 'csv',
  includeHeaders: true,
  delimiter: ',',
  filenamePrefix: 'employees_export',
};

export function EmployeeExportDialog({
  isOpen,
  onClose,
  onExportComplete,
  apiBaseUrl = '/api/employees',
  availableFields = [],
  departments = [],
  locations = [],
}) {
  const [exportState, setExportState] = useState(EXPORT_STATES.CONFIGURE);
  const [exportOptions, setExportOptions] = useState(DEFAULT_EXPORT_OPTIONS);
  const [exportProgress, setExportProgress] = useState({ percentage: 0, status: '' });
  const [exportResult, setExportResult] = useState(null);
  const [error, setError] = useState(null);

  // Reset dialog state
  const resetDialog = useCallback(() => {
    setExportState(EXPORT_STATES.CONFIGURE);
    setExportOptions(DEFAULT_EXPORT_OPTIONS);
    setExportProgress({ percentage: 0, status: '' });
    setExportResult(null);
    setError(null);
  }, []);

  // Handle close
  const handleClose = useCallback(() => {
    resetDialog();
    onClose?.();
  }, [resetDialog, onClose]);

  // Handle export options change
  const handleOptionsChange = useCallback((newOptions) => {
    setExportOptions((prev) => ({ ...prev, ...newOptions }));
  }, []);

  // Start export
  const handleStartExport = useCallback(async () => {
    setExportState(EXPORT_STATES.EXPORTING);
    setExportProgress({ percentage: 0, status: 'Preparing export...' });
    setError(null);

    try {
      // Simulate progress
      const progressSteps = [
        { percentage: 20, status: 'Fetching employee data...' },
        { percentage: 50, status: 'Applying filters...' },
        { percentage: 75, status: 'Generating CSV...' },
        { percentage: 90, status: 'Finalizing export...' },
      ];

      for (const step of progressSteps) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        setExportProgress(step);
      }

      // Simulate API call and file generation
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Generate mock CSV content
      const selectedFields = exportOptions.includeAllFields
        ? availableFields.map((f) => f.id)
        : exportOptions.fields;

      const headers = selectedFields.join(exportOptions.delimiter);
      const mockData = [
        selectedFields.map((f) => `sample_${f}_1`).join(exportOptions.delimiter),
        selectedFields.map((f) => `sample_${f}_2`).join(exportOptions.delimiter),
        selectedFields.map((f) => `sample_${f}_3`).join(exportOptions.delimiter),
      ];

      const csvContent = exportOptions.includeHeaders
        ? [headers, ...mockData].join('\n')
        : mockData.join('\n');

      // Create and trigger download
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `${exportOptions.filenamePrefix}_${timestamp}.csv`;

      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      // Set result
      const result = {
        filename,
        totalRecords: 3, // Mock count
        exportedFields: selectedFields,
        generatedAt: new Date().toISOString(),
      };

      setExportResult(result);
      setExportProgress({ percentage: 100, status: 'Export complete!' });
      setExportState(EXPORT_STATES.COMPLETED);
      onExportComplete?.(result);
    } catch (err) {
      setError(err.message || 'Export failed. Please try again.');
      setExportState(EXPORT_STATES.ERROR);
    }
  }, [exportOptions, availableFields, onExportComplete]);

  // Retry export
  const handleRetry = useCallback(() => {
    setExportState(EXPORT_STATES.CONFIGURE);
    setError(null);
  }, []);

  // Get filtered field count for display
  const selectedFieldCount = useMemo(() => {
    return exportOptions.includeAllFields
      ? availableFields.length
      : exportOptions.fields.length;
  }, [exportOptions, availableFields]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div
        className={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-dialog-title"
      >
        {/* Header */}
        <header className={styles.header}>
          <h2 id="export-dialog-title" className={styles.title}>
            <span className={styles.titleIcon}>📊</span>
            Export Employees
          </h2>
          <button
            className={styles.closeButton}
            onClick={handleClose}
            aria-label="Close export dialog"
          >
            ×
          </button>
        </header>

        {/* Content */}
        <div className={styles.content}>
          {error && (
            <div className={styles.error} role="alert">
              <span className={styles.errorIcon}>⚠️</span>
              <span className={styles.errorMessage}>{error}</span>
              <button
                className={styles.errorDismiss}
                onClick={() => setError(null)}
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}

          {exportState === EXPORT_STATES.CONFIGURE && (
            <ExportOptionsForm
              options={exportOptions}
              onChange={handleOptionsChange}
              availableFields={availableFields}
              departments={departments}
              locations={locations}
            />
          )}

          {(exportState === EXPORT_STATES.EXPORTING ||
            exportState === EXPORT_STATES.COMPLETED) && (
            <ExportProgressDisplay
              progress={exportProgress}
              result={exportResult}
              isComplete={exportState === EXPORT_STATES.COMPLETED}
            />
          )}

          {exportState === EXPORT_STATES.ERROR && (
            <div className={styles.errorState}>
              <div className={styles.errorStateIcon}>❌</div>
              <h3 className={styles.errorStateTitle}>Export Failed</h3>
              <p className={styles.errorStateText}>
                An error occurred while generating the export.
                Please try again or contact support if the problem persists.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className={styles.footer}>
          {exportState === EXPORT_STATES.CONFIGURE && (
            <>
              <div className={styles.footerInfo}>
                <span className={styles.footerInfoText}>
                  {selectedFieldCount} field{selectedFieldCount !== 1 ? 's' : ''} selected
                </span>
              </div>
              <div className={styles.footerActions}>
                <button
                  className={styles.secondaryButton}
                  onClick={handleClose}
                >
                  Cancel
                </button>
                <button
                  className={styles.primaryButton}
                  onClick={handleStartExport}
                  disabled={selectedFieldCount === 0}
                >
                  <span className={styles.buttonIcon}>📥</span>
                  Export
                </button>
              </div>
            </>
          )}

          {exportState === EXPORT_STATES.EXPORTING && (
            <div className={styles.footerCentered}>
              <span className={styles.footerInfoText}>
                Please wait while your export is being generated...
              </span>
            </div>
          )}

          {exportState === EXPORT_STATES.COMPLETED && (
            <div className={styles.footerActions}>
              <button
                className={styles.secondaryButton}
                onClick={resetDialog}
              >
                Export Another
              </button>
              <button
                className={styles.primaryButton}
                onClick={handleClose}
              >
                Done
              </button>
            </div>
          )}

          {exportState === EXPORT_STATES.ERROR && (
            <div className={styles.footerActions}>
              <button
                className={styles.secondaryButton}
                onClick={handleClose}
              >
                Cancel
              </button>
              <button
                className={styles.primaryButton}
                onClick={handleRetry}
              >
                <span className={styles.buttonIcon}>🔄</span>
                Try Again
              </button>
            </div>
          )}
        </footer>
      </div>
    </div>
  );
}

EmployeeExportDialog.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onExportComplete: PropTypes.func,
  apiBaseUrl: PropTypes.string,
  availableFields: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      description: PropTypes.string,
      isSensitive: PropTypes.bool,
    })
  ),
  departments: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.number.isRequired,
      name: PropTypes.string.isRequired,
    })
  ),
  locations: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.number.isRequired,
      name: PropTypes.string.isRequired,
    })
  ),
};

EmployeeExportDialog.defaultProps = {
  availableFields: [
    { id: 'employee_id', label: 'Employee ID', isSensitive: false },
    { id: 'email', label: 'Email', isSensitive: false },
    { id: 'first_name', label: 'First Name', isSensitive: false },
    { id: 'last_name', label: 'Last Name', isSensitive: false },
    { id: 'job_title', label: 'Job Title', isSensitive: false },
    { id: 'department_id', label: 'Department', isSensitive: false },
    { id: 'hire_date', label: 'Hire Date', isSensitive: false },
    { id: 'employment_status', label: 'Status', isSensitive: false },
    { id: 'salary', label: 'Salary', isSensitive: true },
    { id: 'phone_number', label: 'Phone', isSensitive: true },
  ],
  departments: [],
  locations: [],
};

export default EmployeeExportDialog;

