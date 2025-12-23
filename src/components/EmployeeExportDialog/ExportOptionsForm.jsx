/**
 * Export Options Form Component
 * 
 * Allows users to configure export options including field selection,
 * filters, and format settings.
 */

import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import styles from './ExportOptionsForm.module.css';

const EMPLOYMENT_STATUSES = [
  { id: 'active', label: 'Active' },
  { id: 'terminated', label: 'Terminated' },
  { id: 'on_leave', label: 'On Leave' },
  { id: 'suspended', label: 'Suspended' },
];

export function ExportOptionsForm({
  options,
  onChange,
  availableFields,
  departments,
  locations,
}) {
  const [activeTab, setActiveTab] = useState('fields');

  // Handle field selection toggle
  const handleFieldToggle = useCallback((fieldId) => {
    const currentFields = options.fields || [];
    const newFields = currentFields.includes(fieldId)
      ? currentFields.filter((f) => f !== fieldId)
      : [...currentFields, fieldId];
    
    onChange({ fields: newFields, includeAllFields: false });
  }, [options.fields, onChange]);

  // Handle select all fields
  const handleSelectAllFields = useCallback(() => {
    onChange({
      fields: availableFields.map((f) => f.id),
      includeAllFields: true,
    });
  }, [availableFields, onChange]);

  // Handle deselect all fields
  const handleDeselectAllFields = useCallback(() => {
    onChange({ fields: [], includeAllFields: false });
  }, [onChange]);

  // Handle include all toggle
  const handleIncludeAllToggle = useCallback((e) => {
    const includeAll = e.target.checked;
    onChange({
      includeAllFields: includeAll,
      fields: includeAll ? availableFields.map((f) => f.id) : [],
    });
  }, [availableFields, onChange]);

  // Handle filter change
  const handleFilterChange = useCallback((filterKey, value) => {
    onChange({
      filters: {
        ...options.filters,
        [filterKey]: value,
      },
    });
  }, [options.filters, onChange]);

  // Handle multi-select filter
  const handleMultiSelectFilter = useCallback((filterKey, value, checked) => {
    const currentValues = options.filters?.[filterKey] || [];
    const newValues = checked
      ? [...currentValues, value]
      : currentValues.filter((v) => v !== value);
    
    handleFilterChange(filterKey, newValues);
  }, [options.filters, handleFilterChange]);

  // Handle format options
  const handleFormatChange = useCallback((key, value) => {
    onChange({ [key]: value });
  }, [onChange]);

  // Group fields by sensitivity
  const { regularFields, sensitiveFields } = useMemo(() => {
    const regular = [];
    const sensitive = [];
    
    availableFields.forEach((field) => {
      if (field.isSensitive) {
        sensitive.push(field);
      } else {
        regular.push(field);
      }
    });
    
    return { regularFields: regular, sensitiveFields: sensitive };
  }, [availableFields]);

  return (
    <div className={styles.form}>
      {/* Tabs */}
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'fields' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('fields')}
        >
          <span className={styles.tabIcon}>📋</span>
          Fields
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'filters' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('filters')}
        >
          <span className={styles.tabIcon}>🔍</span>
          Filters
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'format' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('format')}
        >
          <span className={styles.tabIcon}>⚙️</span>
          Format
        </button>
      </div>

      {/* Tab Content */}
      <div className={styles.tabContent}>
        {/* Fields Tab */}
        {activeTab === 'fields' && (
          <div className={styles.fieldsTab}>
            <div className={styles.fieldActions}>
              <label className={styles.selectAllLabel}>
                <input
                  type="checkbox"
                  checked={options.includeAllFields}
                  onChange={handleIncludeAllToggle}
                  className={styles.checkbox}
                />
                <span>Include all fields</span>
              </label>
              <div className={styles.fieldActionButtons}>
                <button
                  className={styles.linkButton}
                  onClick={handleSelectAllFields}
                >
                  Select All
                </button>
                <span className={styles.separator}>|</span>
                <button
                  className={styles.linkButton}
                  onClick={handleDeselectAllFields}
                >
                  Deselect All
                </button>
              </div>
            </div>

            {/* Regular Fields */}
            <div className={styles.fieldSection}>
              <h4 className={styles.fieldSectionTitle}>Standard Fields</h4>
              <div className={styles.fieldGrid}>
                {regularFields.map((field) => (
                  <label key={field.id} className={styles.fieldLabel}>
                    <input
                      type="checkbox"
                      checked={options.includeAllFields || options.fields?.includes(field.id)}
                      onChange={() => handleFieldToggle(field.id)}
                      disabled={options.includeAllFields}
                      className={styles.checkbox}
                    />
                    <span className={styles.fieldName}>{field.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Sensitive Fields */}
            {sensitiveFields.length > 0 && (
              <div className={styles.fieldSection}>
                <h4 className={styles.fieldSectionTitle}>
                  <span className={styles.sensitiveIcon}>🔒</span>
                  Sensitive Fields
                </h4>
                <p className={styles.sensitiveWarning}>
                  These fields contain sensitive information. Export with caution.
                </p>
                <div className={styles.fieldGrid}>
                  {sensitiveFields.map((field) => (
                    <label key={field.id} className={styles.fieldLabel}>
                      <input
                        type="checkbox"
                        checked={options.includeAllFields || options.fields?.includes(field.id)}
                        onChange={() => handleFieldToggle(field.id)}
                        disabled={options.includeAllFields}
                        className={styles.checkbox}
                      />
                      <span className={styles.fieldName}>
                        {field.label}
                        <span className={styles.sensitiveTag}>Sensitive</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filters Tab */}
        {activeTab === 'filters' && (
          <div className={styles.filtersTab}>
            {/* Active Status */}
            <div className={styles.filterGroup}>
              <h4 className={styles.filterGroupTitle}>Employee Status</h4>
              <label className={styles.filterLabel}>
                <input
                  type="checkbox"
                  checked={options.filters?.isActive !== false}
                  onChange={(e) => handleFilterChange('isActive', e.target.checked ? true : null)}
                  className={styles.checkbox}
                />
                <span>Active employees only</span>
              </label>
            </div>

            {/* Employment Status */}
            <div className={styles.filterGroup}>
              <h4 className={styles.filterGroupTitle}>Employment Status</h4>
              <div className={styles.filterOptions}>
                {EMPLOYMENT_STATUSES.map((status) => (
                  <label key={status.id} className={styles.filterLabel}>
                    <input
                      type="checkbox"
                      checked={options.filters?.employmentStatus?.includes(status.id)}
                      onChange={(e) => 
                        handleMultiSelectFilter('employmentStatus', status.id, e.target.checked)
                      }
                      className={styles.checkbox}
                    />
                    <span>{status.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Departments */}
            {departments.length > 0 && (
              <div className={styles.filterGroup}>
                <h4 className={styles.filterGroupTitle}>Departments</h4>
                <div className={styles.filterOptions}>
                  {departments.map((dept) => (
                    <label key={dept.id} className={styles.filterLabel}>
                      <input
                        type="checkbox"
                        checked={options.filters?.departmentIds?.includes(dept.id)}
                        onChange={(e) =>
                          handleMultiSelectFilter('departmentIds', dept.id, e.target.checked)
                        }
                        className={styles.checkbox}
                      />
                      <span>{dept.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Locations */}
            {locations.length > 0 && (
              <div className={styles.filterGroup}>
                <h4 className={styles.filterGroupTitle}>Locations</h4>
                <div className={styles.filterOptions}>
                  {locations.map((loc) => (
                    <label key={loc.id} className={styles.filterLabel}>
                      <input
                        type="checkbox"
                        checked={options.filters?.locationIds?.includes(loc.id)}
                        onChange={(e) =>
                          handleMultiSelectFilter('locationIds', loc.id, e.target.checked)
                        }
                        className={styles.checkbox}
                      />
                      <span>{loc.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* No filters message */}
            {departments.length === 0 && locations.length === 0 && (
              <p className={styles.noFiltersMessage}>
                Additional filter options will appear when department and location data is available.
              </p>
            )}
          </div>
        )}

        {/* Format Tab */}
        {activeTab === 'format' && (
          <div className={styles.formatTab}>
            {/* Include Headers */}
            <div className={styles.formatGroup}>
              <label className={styles.filterLabel}>
                <input
                  type="checkbox"
                  checked={options.includeHeaders}
                  onChange={(e) => handleFormatChange('includeHeaders', e.target.checked)}
                  className={styles.checkbox}
                />
                <span>Include column headers in first row</span>
              </label>
            </div>

            {/* Delimiter */}
            <div className={styles.formatGroup}>
              <label className={styles.formatLabel}>
                <span className={styles.formatLabelText}>Field Delimiter</span>
                <select
                  value={options.delimiter}
                  onChange={(e) => handleFormatChange('delimiter', e.target.value)}
                  className={styles.formatSelect}
                >
                  <option value=",">Comma (,)</option>
                  <option value=";">Semicolon (;)</option>
                  <option value="\t">Tab</option>
                  <option value="|">Pipe (|)</option>
                </select>
              </label>
            </div>

            {/* Filename Prefix */}
            <div className={styles.formatGroup}>
              <label className={styles.formatLabel}>
                <span className={styles.formatLabelText}>Filename Prefix</span>
                <input
                  type="text"
                  value={options.filenamePrefix}
                  onChange={(e) => handleFormatChange('filenamePrefix', e.target.value)}
                  placeholder="employees_export"
                  className={styles.formatInput}
                />
              </label>
              <p className={styles.formatHint}>
                The final filename will be: {options.filenamePrefix}_YYYY-MM-DD.csv
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

ExportOptionsForm.propTypes = {
  options: PropTypes.shape({
    fields: PropTypes.arrayOf(PropTypes.string),
    includeAllFields: PropTypes.bool,
    filters: PropTypes.object,
    includeHeaders: PropTypes.bool,
    delimiter: PropTypes.string,
    filenamePrefix: PropTypes.string,
  }).isRequired,
  onChange: PropTypes.func.isRequired,
  availableFields: PropTypes.array.isRequired,
  departments: PropTypes.array,
  locations: PropTypes.array,
};

export default ExportOptionsForm;

