/**
 * ManagerAssignmentField Component
 * 
 * Specialized field for searching and selecting a manager.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { profileService } from '../../../services/profileService';
import styles from '../EmployeeProfileEdit.module.css';

export function ManagerAssignmentField({
  value,
  currentManager,
  onChange,
  disabled,
  error,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedManager, setSelectedManager] = useState(currentManager);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    if (currentManager) {
      setSelectedManager(currentManager);
    }
  }, [currentManager]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target) &&
        !inputRef.current.contains(event.target)
      ) {
        setShowDropdown(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const searchManagers = useCallback(async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const results = await profileService.searchEmployees(query);
      setSearchResults(results);
    } catch (err) {
      console.error('Failed to search managers:', err);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleSearchChange = (event) => {
    const query = event.target.value;
    setSearchQuery(query);
    setShowDropdown(true);
    
    // Debounce search
    const timeoutId = setTimeout(() => {
      searchManagers(query);
    }, 300);

    return () => clearTimeout(timeoutId);
  };

  const handleSelectManager = (manager) => {
    setSelectedManager(manager);
    setSearchQuery('');
    setShowDropdown(false);
    onChange(manager.id);
  };

  const handleClearManager = () => {
    setSelectedManager(null);
    onChange(null);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setShowDropdown(false);
    }
  };

  return (
    <div className={styles.fieldGroup}>
      <label className={styles.fieldLabel}>
        Reports To
      </label>

      {selectedManager ? (
        <div className={styles.selectedManager}>
          <div className={styles.managerInfo}>
            <span className={styles.managerName}>
              {selectedManager.firstName} {selectedManager.lastName}
            </span>
            <span className={styles.managerTitle}>
              {selectedManager.jobTitle}
            </span>
          </div>
          {!disabled && (
            <button
              type="button"
              className={styles.clearButton}
              onClick={handleClearManager}
              aria-label="Remove manager"
            >
              ×
            </button>
          )}
        </div>
      ) : (
        <div className={styles.searchContainer}>
          <input
            ref={inputRef}
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            onFocus={() => setShowDropdown(true)}
            onKeyDown={handleKeyDown}
            placeholder="Search for a manager..."
            disabled={disabled}
            className={`${styles.fieldInput} ${error ? styles.hasError : ''}`}
            aria-expanded={showDropdown}
            aria-haspopup="listbox"
            aria-autocomplete="list"
          />

          {showDropdown && (
            <ul
              ref={dropdownRef}
              className={styles.searchDropdown}
              role="listbox"
            >
              {isSearching ? (
                <li className={styles.searchingMessage}>Searching...</li>
              ) : searchResults.length > 0 ? (
                searchResults.map((employee) => (
                  <li
                    key={employee.id}
                    role="option"
                    className={styles.searchResult}
                    onClick={() => handleSelectManager(employee)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        handleSelectManager(employee);
                      }
                    }}
                    tabIndex={0}
                  >
                    <span className={styles.resultName}>
                      {employee.firstName} {employee.lastName}
                    </span>
                    <span className={styles.resultTitle}>
                      {employee.jobTitle}
                    </span>
                  </li>
                ))
              ) : searchQuery.length >= 2 ? (
                <li className={styles.noResults}>No employees found</li>
              ) : (
                <li className={styles.searchHint}>
                  Type at least 2 characters to search
                </li>
              )}
            </ul>
          )}
        </div>
      )}

      {error && (
        <p className={styles.fieldError} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

ManagerAssignmentField.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  currentManager: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    firstName: PropTypes.string,
    lastName: PropTypes.string,
    jobTitle: PropTypes.string,
  }),
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  error: PropTypes.string,
};

ManagerAssignmentField.defaultProps = {
  value: null,
  currentManager: null,
  disabled: false,
  error: null,
};

export default ManagerAssignmentField;

