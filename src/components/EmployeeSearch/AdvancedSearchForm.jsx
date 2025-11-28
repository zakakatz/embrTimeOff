/**
 * AdvancedSearchForm Component
 * 
 * Form for defining advanced search criteria including
 * fuzzy matching and field-specific searches.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import styles from './EmployeeSearch.module.css';

const SEARCHABLE_FIELDS = [
  { id: 'name', label: 'Name', placeholder: 'First or last name' },
  { id: 'email', label: 'Email', placeholder: 'Email address' },
  { id: 'jobTitle', label: 'Job Title', placeholder: 'Position or title' },
  { id: 'employeeId', label: 'Employee ID', placeholder: 'ID number' },
  { id: 'phone', label: 'Phone', placeholder: 'Phone number' },
  { id: 'skills', label: 'Skills', placeholder: 'Skill or certification' },
];

export function AdvancedSearchForm({
  initialValues,
  onSearch,
  onReset,
  isSearching,
}) {
  const [fieldValues, setFieldValues] = useState({});
  const [departments, setDepartments] = useState([]);
  const [locations, setLocations] = useState([]);
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [selectedLocation, setSelectedLocation] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('active');
  const [fuzzyEnabled, setFuzzyEnabled] = useState(true);
  const [isExpanded, setIsExpanded] = useState(false);

  // Load filter options
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [depts, locs] = await Promise.all([
          employeeService.getDepartments(),
          employeeService.getLocations(),
        ]);
        setDepartments(depts);
        setLocations(locs);
      } catch (error) {
        console.error('Failed to load filter options:', error);
      }
    };

    loadOptions();
  }, []);

  // Initialize from external values
  useEffect(() => {
    if (initialValues) {
      setFieldValues(initialValues.fields || {});
      setSelectedDepartment(initialValues.department || '');
      setSelectedLocation(initialValues.location || '');
      setSelectedStatus(initialValues.status || 'active');
      setFuzzyEnabled(initialValues.fuzzy !== false);
    }
  }, [initialValues]);

  const handleFieldChange = useCallback((fieldId, value) => {
    setFieldValues((prev) => ({
      ...prev,
      [fieldId]: value,
    }));
  }, []);

  const handleSearch = useCallback(() => {
    const filters = {
      fields: Object.fromEntries(
        Object.entries(fieldValues).filter(([, value]) => value.trim())
      ),
      department: selectedDepartment,
      location: selectedLocation,
      status: selectedStatus,
      fuzzy: fuzzyEnabled,
    };

    onSearch(filters);
  }, [fieldValues, selectedDepartment, selectedLocation, selectedStatus, fuzzyEnabled, onSearch]);

  const handleReset = useCallback(() => {
    setFieldValues({});
    setSelectedDepartment('');
    setSelectedLocation('');
    setSelectedStatus('active');
    setFuzzyEnabled(true);
    onReset?.();
  }, [onReset]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSearch();
    }
  }, [handleSearch]);

  const hasActiveFilters = Object.values(fieldValues).some(v => v?.trim()) ||
    selectedDepartment || selectedLocation || selectedStatus !== 'active';

  return (
    <div className={styles.advancedSearchForm}>
      <button
        type="button"
        className={styles.advancedToggle}
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls="advanced-search-panel"
      >
        <span className={styles.advancedToggleIcon} aria-hidden="true">⚡</span>
        Advanced Search
        {hasActiveFilters && (
          <span className={styles.advancedBadge}>Active</span>
        )}
        <span className={styles.advancedChevron} aria-hidden="true">
          {isExpanded ? '▲' : '▼'}
        </span>
      </button>

      {isExpanded && (
        <div
          id="advanced-search-panel"
          className={styles.advancedPanel}
          role="region"
          aria-label="Advanced search options"
        >
          {/* Field-Specific Searches */}
          <div className={styles.advancedSection}>
            <h4 className={styles.advancedSectionTitle}>Search by Field</h4>
            <div className={styles.advancedFieldsGrid}>
              {SEARCHABLE_FIELDS.map((field) => (
                <div key={field.id} className={styles.advancedField}>
                  <label
                    htmlFor={`field-${field.id}`}
                    className={styles.advancedFieldLabel}
                  >
                    {field.label}
                  </label>
                  <input
                    id={`field-${field.id}`}
                    type="text"
                    className={styles.advancedFieldInput}
                    placeholder={field.placeholder}
                    value={fieldValues[field.id] || ''}
                    onChange={(e) => handleFieldChange(field.id, e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Filter Options */}
          <div className={styles.advancedSection}>
            <h4 className={styles.advancedSectionTitle}>Filter By</h4>
            <div className={styles.advancedFiltersGrid}>
              <div className={styles.advancedFilter}>
                <label
                  htmlFor="adv-department"
                  className={styles.advancedFilterLabel}
                >
                  Department
                </label>
                <select
                  id="adv-department"
                  className={styles.advancedFilterSelect}
                  value={selectedDepartment}
                  onChange={(e) => setSelectedDepartment(e.target.value)}
                >
                  <option value="">All Departments</option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.id}>
                      {dept.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.advancedFilter}>
                <label
                  htmlFor="adv-location"
                  className={styles.advancedFilterLabel}
                >
                  Location
                </label>
                <select
                  id="adv-location"
                  className={styles.advancedFilterSelect}
                  value={selectedLocation}
                  onChange={(e) => setSelectedLocation(e.target.value)}
                >
                  <option value="">All Locations</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.advancedFilter}>
                <label
                  htmlFor="adv-status"
                  className={styles.advancedFilterLabel}
                >
                  Status
                </label>
                <select
                  id="adv-status"
                  className={styles.advancedFilterSelect}
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="terminated">Terminated</option>
                  <option value="">All Statuses</option>
                </select>
              </div>
            </div>
          </div>

          {/* Search Options */}
          <div className={styles.advancedSection}>
            <h4 className={styles.advancedSectionTitle}>Options</h4>
            <label className={styles.advancedCheckbox}>
              <input
                type="checkbox"
                checked={fuzzyEnabled}
                onChange={(e) => setFuzzyEnabled(e.target.checked)}
              />
              <span>Enable fuzzy matching</span>
              <span className={styles.advancedHint}>
                (finds similar spellings)
              </span>
            </label>
          </div>

          {/* Actions */}
          <div className={styles.advancedActions}>
            <button
              type="button"
              className={styles.advancedResetButton}
              onClick={handleReset}
              disabled={!hasActiveFilters}
            >
              Reset
            </button>
            <button
              type="button"
              className={styles.advancedSearchButton}
              onClick={handleSearch}
              disabled={isSearching}
            >
              {isSearching ? (
                <>
                  <span className={styles.advancedSpinner} aria-hidden="true" />
                  Searching...
                </>
              ) : (
                'Search'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

AdvancedSearchForm.propTypes = {
  initialValues: PropTypes.shape({
    fields: PropTypes.object,
    department: PropTypes.string,
    location: PropTypes.string,
    status: PropTypes.string,
    fuzzy: PropTypes.bool,
  }),
  onSearch: PropTypes.func.isRequired,
  onReset: PropTypes.func,
  isSearching: PropTypes.bool,
};

AdvancedSearchForm.defaultProps = {
  initialValues: null,
  onReset: null,
  isSearching: false,
};

export default AdvancedSearchForm;

