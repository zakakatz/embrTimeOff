/**
 * OrganizationalChartControls Component
 * 
 * Chart controls including zoom, pan, search, filter, and export.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import styles from './OrganizationalChart.module.css';

const EXPORT_FORMATS = [
  { id: 'png', label: 'PNG Image', icon: '🖼️' },
  { id: 'svg', label: 'SVG Vector', icon: '📐' },
  { id: 'csv', label: 'CSV Data', icon: '📊' },
  { id: 'json', label: 'JSON Data', icon: '📄' },
];

export function OrganizationalChartControls({
  zoom,
  onZoomIn,
  onZoomOut,
  onResetView,
  searchQuery,
  searchResults,
  onSearch,
  onSearchSelect,
  departments,
  selectedDepartment,
  onDepartmentChange,
  onExport,
  onRefresh,
  isLoading,
  showSearch,
  showFilter,
  showExport,
  showZoom,
}) {
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const searchInputRef = useRef(null);
  const searchResultsRef = useRef(null);
  const exportMenuRef = useRef(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchResultsRef.current && !searchResultsRef.current.contains(e.target) &&
          !searchInputRef.current?.contains(e.target)) {
        setShowSearchResults(false);
      }
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) {
        setShowExportMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchChange = useCallback((e) => {
    const value = e.target.value;
    onSearch?.(value);
    setShowSearchResults(value.length >= 2);
  }, [onSearch]);

  const handleSearchResultClick = useCallback((result) => {
    onSearchSelect?.(result);
    setShowSearchResults(false);
    if (searchInputRef.current) {
      searchInputRef.current.value = '';
    }
    onSearch?.('');
  }, [onSearchSelect, onSearch]);

  const handleExportClick = useCallback((format) => {
    onExport?.(format);
    setShowExportMenu(false);
  }, [onExport]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      setShowSearchResults(false);
      setShowExportMenu(false);
    }
  }, []);

  const zoomPercentage = Math.round(zoom * 100);

  return (
    <div className={styles.controls} onKeyDown={handleKeyDown}>
      {/* Search */}
      {showSearch && (
        <div className={styles.controlGroup}>
          <div className={styles.searchContainer}>
            <span className={styles.searchIcon} aria-hidden="true">🔍</span>
            <input
              ref={searchInputRef}
              type="search"
              className={styles.searchInput}
              placeholder="Search in chart..."
              value={searchQuery}
              onChange={handleSearchChange}
              onFocus={() => searchQuery.length >= 2 && setShowSearchResults(true)}
              aria-label="Search employees in chart"
              aria-autocomplete="list"
              aria-controls="chart-search-results"
              aria-expanded={showSearchResults && searchResults.length > 0}
            />
            
            {/* Search Results Dropdown */}
            {showSearchResults && searchResults.length > 0 && (
              <ul
                ref={searchResultsRef}
                id="chart-search-results"
                className={styles.searchResults}
                role="listbox"
              >
                {searchResults.map((result) => (
                  <li
                    key={result.id}
                    className={styles.searchResultItem}
                    onClick={() => handleSearchResultClick(result)}
                    role="option"
                  >
                    <span className={styles.searchResultName}>
                      {result.firstName} {result.lastName}
                    </span>
                    <span className={styles.searchResultTitle}>
                      {result.jobTitle}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Department Filter */}
      {showFilter && departments && departments.length > 0 && (
        <div className={styles.controlGroup}>
          <label htmlFor="dept-filter" className={styles.controlLabel}>
            Department:
          </label>
          <select
            id="dept-filter"
            className={styles.filterSelect}
            value={selectedDepartment || ''}
            onChange={(e) => onDepartmentChange?.(e.target.value || null)}
          >
            <option value="">All Departments</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Spacer */}
      <div className={styles.controlSpacer} />

      {/* Zoom Controls */}
      {showZoom && (
        <div className={styles.controlGroup}>
          <div className={styles.zoomControls}>
            <button
              type="button"
              className={styles.zoomButton}
              onClick={onZoomOut}
              disabled={zoom <= 0.25}
              aria-label="Zoom out"
              title="Zoom out"
            >
              −
            </button>
            <span className={styles.zoomLevel} aria-label={`Zoom level ${zoomPercentage}%`}>
              {zoomPercentage}%
            </span>
            <button
              type="button"
              className={styles.zoomButton}
              onClick={onZoomIn}
              disabled={zoom >= 2}
              aria-label="Zoom in"
              title="Zoom in"
            >
              +
            </button>
            <button
              type="button"
              className={styles.controlButton}
              onClick={onResetView}
              aria-label="Reset view"
              title="Reset view"
            >
              ⟲
            </button>
          </div>
        </div>
      )}

      {/* Refresh */}
      <div className={styles.controlGroup}>
        <button
          type="button"
          className={styles.controlButton}
          onClick={onRefresh}
          disabled={isLoading}
          aria-label="Refresh chart"
          title="Refresh"
        >
          {isLoading ? (
            <span className={styles.refreshSpinner}>⟳</span>
          ) : (
            '↻'
          )}
        </button>
      </div>

      {/* Export */}
      {showExport && (
        <div className={styles.controlGroup}>
          <div className={styles.exportContainer}>
            <button
              type="button"
              className={styles.exportButton}
              onClick={() => setShowExportMenu(!showExportMenu)}
              aria-expanded={showExportMenu}
              aria-haspopup="menu"
              aria-label="Export chart"
            >
              <span aria-hidden="true">📥</span>
              Export
              <span className={styles.exportChevron} aria-hidden="true">
                {showExportMenu ? '▲' : '▼'}
              </span>
            </button>

            {showExportMenu && (
              <div
                ref={exportMenuRef}
                className={styles.exportMenu}
                role="menu"
                aria-label="Export formats"
              >
                {EXPORT_FORMATS.map((format) => (
                  <button
                    key={format.id}
                    type="button"
                    className={styles.exportMenuItem}
                    onClick={() => handleExportClick(format.id)}
                    role="menuitem"
                  >
                    <span className={styles.exportMenuIcon} aria-hidden="true">
                      {format.icon}
                    </span>
                    {format.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

OrganizationalChartControls.propTypes = {
  zoom: PropTypes.number,
  onZoomIn: PropTypes.func,
  onZoomOut: PropTypes.func,
  onResetView: PropTypes.func,
  searchQuery: PropTypes.string,
  searchResults: PropTypes.array,
  onSearch: PropTypes.func,
  onSearchSelect: PropTypes.func,
  departments: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      name: PropTypes.string.isRequired,
    })
  ),
  selectedDepartment: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onDepartmentChange: PropTypes.func,
  onExport: PropTypes.func,
  onRefresh: PropTypes.func,
  isLoading: PropTypes.bool,
  showSearch: PropTypes.bool,
  showFilter: PropTypes.bool,
  showExport: PropTypes.bool,
  showZoom: PropTypes.bool,
};

OrganizationalChartControls.defaultProps = {
  zoom: 1,
  onZoomIn: null,
  onZoomOut: null,
  onResetView: null,
  searchQuery: '',
  searchResults: [],
  onSearch: null,
  onSearchSelect: null,
  departments: [],
  selectedDepartment: null,
  onDepartmentChange: null,
  onExport: null,
  onRefresh: null,
  isLoading: false,
  showSearch: true,
  showFilter: true,
  showExport: true,
  showZoom: true,
};

export default OrganizationalChartControls;

