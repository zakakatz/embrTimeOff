/**
 * Field Mapping Step Component
 * 
 * Allows users to map CSV columns to employee data fields.
 */

import React, { useState, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import styles from './Steps.module.css';

const EMPLOYEE_FIELDS = [
  { id: 'employee_id', label: 'Employee ID', required: true, description: 'Unique identifier' },
  { id: 'email', label: 'Email', required: true, description: 'Work email address' },
  { id: 'first_name', label: 'First Name', required: true, description: 'Employee first name' },
  { id: 'last_name', label: 'Last Name', required: true, description: 'Employee last name' },
  { id: 'middle_name', label: 'Middle Name', required: false, description: 'Employee middle name' },
  { id: 'preferred_name', label: 'Preferred Name', required: false, description: 'Nickname or preferred name' },
  { id: 'hire_date', label: 'Hire Date', required: true, description: 'Date of hire (YYYY-MM-DD)' },
  { id: 'job_title', label: 'Job Title', required: false, description: 'Position or role' },
  { id: 'department_id', label: 'Department ID', required: false, description: 'Department identifier' },
  { id: 'manager_id', label: 'Manager ID', required: false, description: 'Manager employee ID' },
  { id: 'location_id', label: 'Location ID', required: false, description: 'Office location identifier' },
  { id: 'employment_status', label: 'Employment Status', required: false, description: 'Active, terminated, etc.' },
  { id: 'employment_type', label: 'Employment Type', required: false, description: 'Full-time, part-time, etc.' },
  { id: 'salary', label: 'Salary', required: false, description: 'Annual salary amount' },
  { id: 'hourly_rate', label: 'Hourly Rate', required: false, description: 'Hourly pay rate' },
  { id: 'phone_number', label: 'Phone Number', required: false, description: 'Work phone' },
  { id: 'mobile_number', label: 'Mobile Number', required: false, description: 'Mobile phone' },
  { id: 'personal_email', label: 'Personal Email', required: false, description: 'Personal email address' },
  { id: 'date_of_birth', label: 'Date of Birth', required: false, description: 'Birth date (YYYY-MM-DD)' },
  { id: 'gender', label: 'Gender', required: false, description: 'Gender identity' },
  { id: 'address_line1', label: 'Address Line 1', required: false, description: 'Street address' },
  { id: 'address_line2', label: 'Address Line 2', required: false, description: 'Apt, suite, etc.' },
  { id: 'city', label: 'City', required: false, description: 'City name' },
  { id: 'state_province', label: 'State/Province', required: false, description: 'State or province' },
  { id: 'postal_code', label: 'Postal Code', required: false, description: 'ZIP or postal code' },
  { id: 'country', label: 'Country', required: false, description: 'Country name' },
];

export function FieldMappingStep({
  wizardState,
  setWizardState,
  onMappingChange,
  onNext,
  onBack,
}) {
  const { parsedData, fieldMappings } = wizardState;
  const csvHeaders = parsedData?.headers || [];

  // Local state for mappings
  const [mappings, setMappings] = useState(fieldMappings);

  // Check if all required fields are mapped
  const requiredFieldsMapped = useMemo(() => {
    const requiredFields = EMPLOYEE_FIELDS.filter((f) => f.required).map((f) => f.id);
    const mappedFields = Object.values(mappings);
    return requiredFields.every((field) => mappedFields.includes(field));
  }, [mappings]);

  // Handle mapping change
  const handleMappingChange = useCallback((csvHeader, employeeField) => {
    setMappings((prev) => {
      const newMappings = { ...prev };
      
      // Remove any existing mapping to this employee field
      Object.keys(newMappings).forEach((key) => {
        if (newMappings[key] === employeeField) {
          delete newMappings[key];
        }
      });

      // Set new mapping (or remove if empty)
      if (employeeField) {
        newMappings[csvHeader] = employeeField;
      } else {
        delete newMappings[csvHeader];
      }

      return newMappings;
    });
  }, []);

  // Auto-map unmapped fields
  const handleAutoMap = useCallback(() => {
    const newMappings = { ...mappings };
    
    csvHeaders.forEach((header) => {
      if (!newMappings[header]) {
        // Try to find a matching field
        const normalized = header.toLowerCase().replace(/[^a-z0-9]/g, '_');
        const match = EMPLOYEE_FIELDS.find((field) => {
          const fieldNorm = field.id.toLowerCase();
          return fieldNorm === normalized || 
                 field.label.toLowerCase().replace(/[^a-z0-9]/g, '_') === normalized;
        });
        if (match && !Object.values(newMappings).includes(match.id)) {
          newMappings[header] = match.id;
        }
      }
    });

    setMappings(newMappings);
  }, [csvHeaders, mappings]);

  // Clear all mappings
  const handleClearMappings = useCallback(() => {
    setMappings({});
  }, []);

  // Proceed to next step
  const handleContinue = useCallback(() => {
    onMappingChange(mappings);
    setWizardState((prev) => ({ ...prev, fieldMappings: mappings }));
    onNext();
  }, [mappings, onMappingChange, setWizardState, onNext]);

  // Get unmapped required fields
  const unmappedRequiredFields = useMemo(() => {
    const mappedFields = Object.values(mappings);
    return EMPLOYEE_FIELDS
      .filter((f) => f.required && !mappedFields.includes(f.id))
      .map((f) => f.label);
  }, [mappings]);

  return (
    <div className={styles.stepContainer}>
      {/* Instructions */}
      <div className={styles.instructions}>
        <h3 className={styles.instructionsTitle}>Map CSV Columns to Employee Fields</h3>
        <p className={styles.instructionsText}>
          Match each column from your CSV file to the corresponding employee field.
          Required fields are marked with an asterisk (*).
        </p>
        <div className={styles.instructionsActions}>
          <button
            className={styles.secondaryButton}
            onClick={handleAutoMap}
          >
            <span>🔮</span>
            Auto-Map Fields
          </button>
          <button
            className={styles.textButton}
            onClick={handleClearMappings}
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Mapping Status */}
      {unmappedRequiredFields.length > 0 && (
        <div className={styles.warning}>
          <span className={styles.warningIcon}>⚠️</span>
          <span>
            Missing required fields: {unmappedRequiredFields.join(', ')}
          </span>
        </div>
      )}

      {/* Mapping Table */}
      <div className={styles.mappingContainer}>
        <div className={styles.mappingTable}>
          <div className={styles.mappingHeader}>
            <span className={styles.mappingHeaderCell}>CSV Column</span>
            <span className={styles.mappingHeaderCell}>Sample Data</span>
            <span className={styles.mappingHeaderCell}>Map To</span>
          </div>
          {csvHeaders.map((header) => {
            const sampleValue = parsedData?.rows?.[0]?.[header] || '';
            const currentMapping = mappings[header] || '';
            
            return (
              <div key={header} className={styles.mappingRow}>
                <div className={styles.mappingCell}>
                  <span className={styles.csvColumnName}>{header}</span>
                </div>
                <div className={styles.mappingCell}>
                  <span className={styles.sampleValue}>{sampleValue || '-'}</span>
                </div>
                <div className={styles.mappingCell}>
                  <select
                    className={styles.mappingSelect}
                    value={currentMapping}
                    onChange={(e) => handleMappingChange(header, e.target.value)}
                  >
                    <option value="">-- Do not import --</option>
                    {EMPLOYEE_FIELDS.map((field) => {
                      const isUsed = Object.values(mappings).includes(field.id) && 
                                    mappings[header] !== field.id;
                      return (
                        <option
                          key={field.id}
                          value={field.id}
                          disabled={isUsed}
                        >
                          {field.label}{field.required ? ' *' : ''}{isUsed ? ' (used)' : ''}
                        </option>
                      );
                    })}
                  </select>
                  {currentMapping && (
                    <span className={styles.mappingHint}>
                      {EMPLOYEE_FIELDS.find((f) => f.id === currentMapping)?.description}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendRequired}>*</span> Required field
        </span>
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        <button
          className={styles.secondaryButton}
          onClick={onBack}
        >
          <span className={styles.buttonIcon}>←</span>
          Back
        </button>
        <button
          className={styles.primaryButton}
          onClick={handleContinue}
          disabled={!requiredFieldsMapped}
        >
          Continue to Preview
          <span className={styles.buttonIcon}>→</span>
        </button>
      </div>
    </div>
  );
}

FieldMappingStep.propTypes = {
  wizardState: PropTypes.object.isRequired,
  setWizardState: PropTypes.func.isRequired,
  onMappingChange: PropTypes.func.isRequired,
  onNext: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default FieldMappingStep;

