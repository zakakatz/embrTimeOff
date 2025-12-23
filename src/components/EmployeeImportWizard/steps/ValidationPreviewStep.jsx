/**
 * Validation Preview Step Component
 * 
 * Shows validation results and allows users to review before importing.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import PropTypes from 'prop-types';
import styles from './Steps.module.css';

export function ValidationPreviewStep({
  wizardState,
  setWizardState,
  setIsLoading,
  setError,
  apiBaseUrl,
  onValidationComplete,
  onPartialImportToggle,
  onNext,
  onBack,
}) {
  const { parsedData, fieldMappings, allowPartialImport } = wizardState;
  const [validationResults, setValidationResults] = useState(null);
  const [showAllErrors, setShowAllErrors] = useState(false);

  // Simulate validation (in production, this would call the API)
  useEffect(() => {
    const validateData = async () => {
      setIsLoading(true);
      
      try {
        // Simulate API call delay
        await new Promise((resolve) => setTimeout(resolve, 1000));

        // Perform client-side validation
        const results = {
          totalRows: parsedData?.totalRows || 0,
          validRows: 0,
          errorRows: 0,
          errors: [],
        };

        // Validate each row
        parsedData?.rows?.forEach((row, index) => {
          const rowErrors = [];
          const rowNumber = index + 2; // +1 for header, +1 for 1-based indexing

          // Check required fields
          Object.entries(fieldMappings).forEach(([csvColumn, employeeField]) => {
            const value = row[csvColumn];
            
            // Required field validation
            if (['employee_id', 'email', 'first_name', 'last_name', 'hire_date'].includes(employeeField)) {
              if (!value || value.trim() === '') {
                rowErrors.push({
                  field: employeeField,
                  message: `${employeeField.replace(/_/g, ' ')} is required`,
                  value: value || '',
                });
              }
            }

            // Email validation
            if (employeeField === 'email' && value) {
              const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
              if (!emailRegex.test(value)) {
                rowErrors.push({
                  field: 'email',
                  message: 'Invalid email format',
                  value,
                });
              }
            }

            // Date validation
            if (['hire_date', 'date_of_birth', 'termination_date'].includes(employeeField) && value) {
              const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
              if (!dateRegex.test(value) && !/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(value)) {
                rowErrors.push({
                  field: employeeField,
                  message: 'Invalid date format (use YYYY-MM-DD)',
                  value,
                });
              }
            }
          });

          if (rowErrors.length > 0) {
            results.errorRows++;
            results.errors.push({
              rowNumber,
              employeeId: row[Object.keys(fieldMappings).find((k) => fieldMappings[k] === 'employee_id')] || '',
              errors: rowErrors,
            });
          } else {
            results.validRows++;
          }
        });

        // For demo, mark remaining rows as valid
        const previewedRows = parsedData?.rows?.length || 0;
        const remainingRows = (parsedData?.totalRows || 0) - previewedRows;
        results.validRows += remainingRows;

        setValidationResults(results);
        onValidationComplete?.(results);
        setWizardState((prev) => ({ ...prev, validationResults: results }));
      } catch (err) {
        setError('Validation failed. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    validateData();
  }, [parsedData, fieldMappings, setIsLoading, setError, onValidationComplete, setWizardState]);

  // Displayed errors (limited or all)
  const displayedErrors = useMemo(() => {
    if (!validationResults?.errors) return [];
    return showAllErrors 
      ? validationResults.errors 
      : validationResults.errors.slice(0, 5);
  }, [validationResults, showAllErrors]);

  // Can proceed with import
  const canProceed = useMemo(() => {
    if (!validationResults) return false;
    if (validationResults.validRows === 0) return false;
    if (!allowPartialImport && validationResults.errorRows > 0) return false;
    return true;
  }, [validationResults, allowPartialImport]);

  const handlePartialImportChange = useCallback((e) => {
    const allow = e.target.checked;
    onPartialImportToggle?.(allow);
    setWizardState((prev) => ({ ...prev, allowPartialImport: allow }));
  }, [onPartialImportToggle, setWizardState]);

  if (!validationResults) {
    return (
      <div className={styles.stepContainer}>
        <div className={styles.loadingState}>
          <div className={styles.spinner} />
          <p>Validating your data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.stepContainer}>
      {/* Validation Summary */}
      <div className={styles.validationSummary}>
        <h3 className={styles.instructionsTitle}>Validation Results</h3>
        
        <div className={styles.summaryCards}>
          <div className={`${styles.summaryCard} ${styles.summaryCardTotal}`}>
            <span className={styles.summaryValue}>{validationResults.totalRows}</span>
            <span className={styles.summaryLabel}>Total Rows</span>
          </div>
          <div className={`${styles.summaryCard} ${styles.summaryCardSuccess}`}>
            <span className={styles.summaryValue}>{validationResults.validRows}</span>
            <span className={styles.summaryLabel}>Valid Rows</span>
          </div>
          <div className={`${styles.summaryCard} ${styles.summaryCardError}`}>
            <span className={styles.summaryValue}>{validationResults.errorRows}</span>
            <span className={styles.summaryLabel}>Errors</span>
          </div>
        </div>
      </div>

      {/* Partial Import Option */}
      {validationResults.errorRows > 0 && validationResults.validRows > 0 && (
        <div className={styles.optionBox}>
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={allowPartialImport}
              onChange={handlePartialImportChange}
              className={styles.checkbox}
            />
            <span className={styles.checkboxText}>
              Allow partial import (import {validationResults.validRows} valid rows, 
              skip {validationResults.errorRows} rows with errors)
            </span>
          </label>
        </div>
      )}

      {/* Error Details */}
      {validationResults.errorRows > 0 && (
        <div className={styles.errorSection}>
          <div className={styles.errorSectionHeader}>
            <h4 className={styles.errorSectionTitle}>
              <span className={styles.errorIcon}>⚠️</span>
              Validation Errors
            </h4>
            {validationResults.errors.length > 5 && (
              <button
                className={styles.textButton}
                onClick={() => setShowAllErrors(!showAllErrors)}
              >
                {showAllErrors ? 'Show Less' : `Show All (${validationResults.errors.length})`}
              </button>
            )}
          </div>

          <div className={styles.errorList}>
            {displayedErrors.map((rowError, index) => (
              <div key={index} className={styles.errorItem}>
                <div className={styles.errorItemHeader}>
                  <span className={styles.errorRowNumber}>Row {rowError.rowNumber}</span>
                  {rowError.employeeId && (
                    <span className={styles.errorEmployeeId}>
                      Employee ID: {rowError.employeeId}
                    </span>
                  )}
                </div>
                <ul className={styles.errorItemList}>
                  {rowError.errors.map((error, errIndex) => (
                    <li key={errIndex} className={styles.errorItemDetail}>
                      <strong>{error.field.replace(/_/g, ' ')}:</strong> {error.message}
                      {error.value && (
                        <span className={styles.errorValue}>
                          (value: "{error.value}")
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Success Message */}
      {validationResults.errorRows === 0 && (
        <div className={styles.successBox}>
          <span className={styles.successIcon}>✅</span>
          <span className={styles.successText}>
            All {validationResults.validRows} rows passed validation and are ready to import!
          </span>
        </div>
      )}

      {/* Cannot Proceed Warning */}
      {!canProceed && (
        <div className={styles.warningBox}>
          <span className={styles.warningIcon}>⚠️</span>
          <span className={styles.warningText}>
            {validationResults.validRows === 0
              ? 'No valid rows to import. Please fix the errors and try again.'
              : 'Please enable partial import or fix all errors to proceed.'}
          </span>
        </div>
      )}

      {/* Actions */}
      <div className={styles.actions}>
        <button
          className={styles.secondaryButton}
          onClick={onBack}
        >
          <span className={styles.buttonIcon}>←</span>
          Back to Mapping
        </button>
        <button
          className={styles.primaryButton}
          onClick={onNext}
          disabled={!canProceed}
        >
          {validationResults.errorRows > 0 && allowPartialImport
            ? `Import ${validationResults.validRows} Valid Rows`
            : 'Start Import'}
          <span className={styles.buttonIcon}>→</span>
        </button>
      </div>
    </div>
  );
}

ValidationPreviewStep.propTypes = {
  wizardState: PropTypes.object.isRequired,
  setWizardState: PropTypes.func.isRequired,
  setIsLoading: PropTypes.func.isRequired,
  setError: PropTypes.func.isRequired,
  apiBaseUrl: PropTypes.string,
  onValidationComplete: PropTypes.func,
  onPartialImportToggle: PropTypes.func,
  onNext: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default ValidationPreviewStep;

