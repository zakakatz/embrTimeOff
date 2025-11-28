/**
 * DirectoryFilters Component
 * 
 * Provides filtering options for the employee directory.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import styles from './EmployeeDirectory.module.css';

export function DirectoryFilters({
  filters,
  onFilterChange,
  onClearFilters,
  showStatus,
}) {
  const [departments, setDepartments] = useState([]);
  const [locations, setLocations] = useState([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  // Fetch filter options
  useEffect(() => {
    const fetchFilterOptions = async () => {
      setLoading(true);
      try {
        const [depts, locs] = await Promise.all([
          employeeService.getDepartments(),
          employeeService.getLocations(),
        ]);
        setDepartments(depts);
        setLocations(locs);
      } catch (error) {
        console.error('Failed to load filter options:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchFilterOptions();
  }, []);

  const handleFilterChange = useCallback((field, value) => {
    onFilterChange({ ...filters, [field]: value });
  }, [filters, onFilterChange]);

  const hasActiveFilters = filters.department || filters.location || 
    (showStatus && filters.status && filters.status !== 'active');

  const activeFilterCount = [
    filters.department,
    filters.location,
    showStatus && filters.status && filters.status !== 'active',
  ].filter(Boolean).length;

  return (
    <div className={styles.filters}>
      <div className={styles.filtersHeader}>
        <button
          type="button"
          className={styles.filtersToggle}
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
          aria-controls="directory-filters"
        >
          <span className={styles.filtersIcon} aria-hidden="true">⚙️</span>
          Filters
          {activeFilterCount > 0 && (
            <span className={styles.filterBadge}>{activeFilterCount}</span>
          )}
          <span className={styles.chevron} aria-hidden="true">
            {isExpanded ? '▲' : '▼'}
          </span>
        </button>

        {hasActiveFilters && (
          <button
            type="button"
            className={styles.clearFilters}
            onClick={onClearFilters}
            aria-label="Clear all filters"
          >
            Clear all
          </button>
        )}
      </div>

      {isExpanded && (
        <div
          id="directory-filters"
          className={styles.filtersPanel}
          role="group"
          aria-label="Directory filters"
        >
          {loading ? (
            <div className={styles.filtersLoading}>Loading filters...</div>
          ) : (
            <div className={styles.filtersGrid}>
              {/* Department Filter */}
              <div className={styles.filterGroup}>
                <label htmlFor="filter-department" className={styles.filterLabel}>
                  Department
                </label>
                <select
                  id="filter-department"
                  className={styles.filterSelect}
                  value={filters.department || ''}
                  onChange={(e) => handleFilterChange('department', e.target.value)}
                >
                  <option value="">All Departments</option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.id}>
                      {dept.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Location Filter */}
              <div className={styles.filterGroup}>
                <label htmlFor="filter-location" className={styles.filterLabel}>
                  Location
                </label>
                <select
                  id="filter-location"
                  className={styles.filterSelect}
                  value={filters.location || ''}
                  onChange={(e) => handleFilterChange('location', e.target.value)}
                >
                  <option value="">All Locations</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              {showStatus && (
                <div className={styles.filterGroup}>
                  <label htmlFor="filter-status" className={styles.filterLabel}>
                    Status
                  </label>
                  <select
                    id="filter-status"
                    className={styles.filterSelect}
                    value={filters.status || 'active'}
                    onChange={(e) => handleFilterChange('status', e.target.value)}
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="terminated">Terminated</option>
                    <option value="">All Statuses</option>
                  </select>
                </div>
              )}

              {/* Sort By */}
              <div className={styles.filterGroup}>
                <label htmlFor="filter-sort" className={styles.filterLabel}>
                  Sort By
                </label>
                <select
                  id="filter-sort"
                  className={styles.filterSelect}
                  value={`${filters.sortBy || 'lastName'}-${filters.sortOrder || 'asc'}`}
                  onChange={(e) => {
                    const [sortBy, sortOrder] = e.target.value.split('-');
                    onFilterChange({ ...filters, sortBy, sortOrder });
                  }}
                >
                  <option value="lastName-asc">Name (A-Z)</option>
                  <option value="lastName-desc">Name (Z-A)</option>
                  <option value="department-asc">Department (A-Z)</option>
                  <option value="hireDate-desc">Newest First</option>
                  <option value="hireDate-asc">Oldest First</option>
                  <option value="jobTitle-asc">Job Title (A-Z)</option>
                </select>
              </div>
            </div>
          )}

          {/* Active Filters Summary */}
          {hasActiveFilters && (
            <div className={styles.activeFilters} aria-label="Active filters">
              {filters.department && (
                <span className={styles.filterTag}>
                  {departments.find(d => d.id === filters.department)?.name || 'Department'}
                  <button
                    type="button"
                    className={styles.filterTagRemove}
                    onClick={() => handleFilterChange('department', '')}
                    aria-label="Remove department filter"
                  >
                    ×
                  </button>
                </span>
              )}
              {filters.location && (
                <span className={styles.filterTag}>
                  {locations.find(l => l.id === filters.location)?.name || 'Location'}
                  <button
                    type="button"
                    className={styles.filterTagRemove}
                    onClick={() => handleFilterChange('location', '')}
                    aria-label="Remove location filter"
                  >
                    ×
                  </button>
                </span>
              )}
              {showStatus && filters.status && filters.status !== 'active' && (
                <span className={styles.filterTag}>
                  Status: {filters.status}
                  <button
                    type="button"
                    className={styles.filterTagRemove}
                    onClick={() => handleFilterChange('status', 'active')}
                    aria-label="Remove status filter"
                  >
                    ×
                  </button>
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

DirectoryFilters.propTypes = {
  filters: PropTypes.shape({
    department: PropTypes.string,
    location: PropTypes.string,
    status: PropTypes.string,
    sortBy: PropTypes.string,
    sortOrder: PropTypes.string,
  }).isRequired,
  onFilterChange: PropTypes.func.isRequired,
  onClearFilters: PropTypes.func.isRequired,
  showStatus: PropTypes.bool,
};

DirectoryFilters.defaultProps = {
  showStatus: true,
};

export default DirectoryFilters;

