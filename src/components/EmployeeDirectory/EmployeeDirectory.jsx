/**
 * EmployeeDirectory Component
 * 
 * Main component for the searchable employee directory with filtering,
 * sorting, pagination, and export capabilities.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import { usePermissions } from '../../hooks/usePermissions';
import { useVirtualScroll } from '../../hooks/useVirtualScroll';
import EmployeeCard from './EmployeeCard';
import DirectorySearchInput from './DirectorySearchInput';
import DirectoryFilters from './DirectoryFilters';
import DirectoryPagination from './DirectoryPagination';
import DirectoryExportButton from './DirectoryExportButton';
import styles from './EmployeeDirectory.module.css';

const DEFAULT_PAGE_SIZE = 20;
const VIRTUAL_SCROLL_THRESHOLD = 100;

export function EmployeeDirectory({
  onEmployeeSelect,
  initialFilters,
  showExport,
  enableVirtualScroll,
  containerHeight,
}) {
  // State
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({
    department: '',
    location: '',
    status: 'active',
    sortBy: 'lastName',
    sortOrder: 'asc',
    ...initialFilters,
  });
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    totalPages: 1,
    totalItems: 0,
  });
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'

  const { hasPermission } = usePermissions();

  // Virtual scroll setup (for large datasets)
  const shouldUseVirtualScroll = enableVirtualScroll && 
    employees.length > VIRTUAL_SCROLL_THRESHOLD;
  
  const virtualScroll = useVirtualScroll({
    itemCount: employees.length,
    itemHeight: viewMode === 'grid' ? 280 : 80,
    containerHeight: containerHeight || 600,
    overscan: 5,
  });

  // Fetch employees
  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await employeeService.getDirectory({
        page: pagination.page,
        pageSize: pagination.pageSize,
        search: searchQuery,
        department: filters.department,
        location: filters.location,
        status: filters.status,
        sortBy: filters.sortBy,
        sortOrder: filters.sortOrder,
      });

      setEmployees(response.data || []);
      setPagination((prev) => ({
        ...prev,
        totalPages: response.totalPages || 1,
        totalItems: response.total || 0,
      }));
    } catch (err) {
      setError(err.message || 'Failed to load employee directory');
      setEmployees([]);
    } finally {
      setLoading(false);
    }
  }, [pagination.page, pagination.pageSize, searchQuery, filters]);

  // Fetch on mount and when dependencies change
  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  // Reset to page 1 when filters or search change
  useEffect(() => {
    setPagination((prev) => ({ ...prev, page: 1 }));
  }, [searchQuery, filters.department, filters.location, filters.status]);

  // Handlers
  const handleSearchChange = useCallback((value) => {
    setSearchQuery(value);
  }, []);

  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  const handleClearFilters = useCallback(() => {
    setFilters({
      department: '',
      location: '',
      status: 'active',
      sortBy: 'lastName',
      sortOrder: 'asc',
    });
    setSearchQuery('');
  }, []);

  const handlePageChange = useCallback((page) => {
    setPagination((prev) => ({ ...prev, page }));
  }, []);

  const handlePageSizeChange = useCallback((pageSize) => {
    setPagination((prev) => ({ ...prev, pageSize, page: 1 }));
  }, []);

  const handleEmployeeClick = useCallback((employee) => {
    onEmployeeSelect?.(employee);
  }, [onEmployeeSelect]);

  const handleSuggestionSelect = useCallback((employee) => {
    onEmployeeSelect?.(employee);
  }, [onEmployeeSelect]);

  // Render employees with or without virtual scrolling
  const renderEmployees = useMemo(() => {
    if (shouldUseVirtualScroll) {
      const virtualItems = virtualScroll.getVirtualItems(employees);
      return (
        <div
          ref={virtualScroll.containerRef}
          style={virtualScroll.containerStyle}
          onScroll={virtualScroll.handleScroll}
          className={styles.virtualScrollContainer}
        >
          <div style={virtualScroll.innerStyle}>
            {virtualItems.map(({ item, index, style }) => (
              <div key={item.id} style={style}>
                <EmployeeCard
                  employee={item}
                  onClick={handleEmployeeClick}
                  compact={viewMode === 'list'}
                />
              </div>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className={`${styles.employeeGrid} ${viewMode === 'list' ? styles.employeeList : ''}`}>
        {employees.map((employee) => (
          <EmployeeCard
            key={employee.id}
            employee={employee}
            onClick={handleEmployeeClick}
            compact={viewMode === 'list'}
          />
        ))}
      </div>
    );
  }, [employees, shouldUseVirtualScroll, virtualScroll, viewMode, handleEmployeeClick]);

  return (
    <div className={styles.directory}>
      {/* Header */}
      <header className={styles.directoryHeader}>
        <h1 className={styles.directoryTitle}>Employee Directory</h1>
        <p className={styles.directorySubtitle}>
          Find and connect with colleagues across the organization
        </p>
      </header>

      {/* Search and Actions Bar */}
      <div className={styles.directoryToolbar}>
        <DirectorySearchInput
          value={searchQuery}
          onChange={handleSearchChange}
          showSuggestions={true}
          onSuggestionSelect={handleSuggestionSelect}
        />

        <div className={styles.toolbarActions}>
          {/* View Mode Toggle */}
          <div className={styles.viewToggle} role="group" aria-label="View mode">
            <button
              type="button"
              className={`${styles.viewToggleButton} ${viewMode === 'grid' ? styles.viewToggleActive : ''}`}
              onClick={() => setViewMode('grid')}
              aria-pressed={viewMode === 'grid'}
              aria-label="Grid view"
            >
              <span aria-hidden="true">▦</span>
            </button>
            <button
              type="button"
              className={`${styles.viewToggleButton} ${viewMode === 'list' ? styles.viewToggleActive : ''}`}
              onClick={() => setViewMode('list')}
              aria-pressed={viewMode === 'list'}
              aria-label="List view"
            >
              <span aria-hidden="true">☰</span>
            </button>
          </div>

          {/* Export Button */}
          {showExport && hasPermission('export_directory') && (
            <DirectoryExportButton
              filters={{ ...filters, search: searchQuery }}
              disabled={loading || employees.length === 0}
            />
          )}
        </div>
      </div>

      {/* Filters */}
      <DirectoryFilters
        filters={filters}
        onFilterChange={handleFilterChange}
        onClearFilters={handleClearFilters}
        showStatus={hasPermission('view_all_statuses')}
      />

      {/* Results Summary */}
      {!loading && (
        <div className={styles.resultsSummary} aria-live="polite">
          {pagination.totalItems > 0 ? (
            <span>
              Found <strong>{pagination.totalItems}</strong> employee
              {pagination.totalItems !== 1 ? 's' : ''}
              {searchQuery && <> matching "<em>{searchQuery}</em>"</>}
            </span>
          ) : (
            <span>No employees found</span>
          )}
        </div>
      )}

      {/* Content Area */}
      <main className={styles.directoryContent}>
        {loading ? (
          <div className={styles.loadingState} role="status" aria-live="polite">
            <div className={styles.loadingSpinner} aria-hidden="true" />
            <span>Loading employees...</span>
          </div>
        ) : error ? (
          <div className={styles.errorState} role="alert">
            <span className={styles.errorIcon} aria-hidden="true">⚠️</span>
            <h3>Unable to Load Directory</h3>
            <p>{error}</p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={fetchEmployees}
            >
              Try Again
            </button>
          </div>
        ) : employees.length === 0 ? (
          <div className={styles.emptyState}>
            <span className={styles.emptyIcon} aria-hidden="true">👥</span>
            <h3>No Employees Found</h3>
            <p>
              {searchQuery || filters.department || filters.location
                ? 'Try adjusting your search or filters'
                : 'No employees in the directory yet'}
            </p>
            {(searchQuery || filters.department || filters.location) && (
              <button
                type="button"
                className={styles.clearButton}
                onClick={handleClearFilters}
              >
                Clear Filters
              </button>
            )}
          </div>
        ) : (
          renderEmployees
        )}
      </main>

      {/* Pagination */}
      {!loading && employees.length > 0 && (
        <DirectoryPagination
          currentPage={pagination.page}
          totalPages={pagination.totalPages}
          totalItems={pagination.totalItems}
          pageSize={pagination.pageSize}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
        />
      )}
    </div>
  );
}

EmployeeDirectory.propTypes = {
  onEmployeeSelect: PropTypes.func,
  initialFilters: PropTypes.shape({
    department: PropTypes.string,
    location: PropTypes.string,
    status: PropTypes.string,
    sortBy: PropTypes.string,
    sortOrder: PropTypes.string,
  }),
  showExport: PropTypes.bool,
  enableVirtualScroll: PropTypes.bool,
  containerHeight: PropTypes.number,
};

EmployeeDirectory.defaultProps = {
  onEmployeeSelect: null,
  initialFilters: {},
  showExport: true,
  enableVirtualScroll: true,
  containerHeight: 600,
};

export default EmployeeDirectory;

