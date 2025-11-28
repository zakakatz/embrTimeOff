/**
 * DirectorySearchInput Component
 * 
 * Search input with debouncing for the employee directory.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useDebounce } from '../../hooks/useDebounce';
import { employeeService } from '../../services/employeeService';
import styles from './EmployeeDirectory.module.css';

export function DirectorySearchInput({
  value,
  onChange,
  placeholder,
  debounceMs,
  showSuggestions,
  onSuggestionSelect,
}) {
  const [inputValue, setInputValue] = useState(value);
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isLoading, setIsLoading] = useState(false);
  
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debouncedValue = useDebounce(inputValue, debounceMs);

  // Sync external value changes
  useEffect(() => {
    setInputValue(value);
  }, [value]);

  // Trigger search on debounced value change
  useEffect(() => {
    onChange(debouncedValue);
  }, [debouncedValue, onChange]);

  // Fetch suggestions
  useEffect(() => {
    if (!showSuggestions || !inputValue || inputValue.length < 2) {
      setSuggestions([]);
      return;
    }

    const fetchSuggestions = async () => {
      setIsLoading(true);
      try {
        const results = await employeeService.getSearchSuggestions(inputValue);
        setSuggestions(results);
      } catch (error) {
        console.error('Failed to fetch suggestions:', error);
        setSuggestions([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSuggestions();
  }, [inputValue, showSuggestions]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target) &&
        !inputRef.current.contains(event.target)
      ) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = useCallback((e) => {
    setInputValue(e.target.value);
    setShowDropdown(true);
    setSelectedIndex(-1);
  }, []);

  const handleKeyDown = useCallback((e) => {
    if (!showDropdown || suggestions.length === 0) {
      if (e.key === 'Escape') {
        inputRef.current?.blur();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => 
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && suggestions[selectedIndex]) {
          handleSuggestionClick(suggestions[selectedIndex]);
        }
        break;
      case 'Escape':
        setShowDropdown(false);
        setSelectedIndex(-1);
        break;
      default:
        break;
    }
  }, [showDropdown, suggestions, selectedIndex]);

  const handleSuggestionClick = useCallback((suggestion) => {
    setInputValue(suggestion.displayText || `${suggestion.firstName} ${suggestion.lastName}`);
    setShowDropdown(false);
    setSelectedIndex(-1);
    onSuggestionSelect?.(suggestion);
  }, [onSuggestionSelect]);

  const handleClear = useCallback(() => {
    setInputValue('');
    setSuggestions([]);
    setShowDropdown(false);
    inputRef.current?.focus();
  }, []);

  const handleFocus = useCallback(() => {
    if (suggestions.length > 0) {
      setShowDropdown(true);
    }
  }, [suggestions.length]);

  return (
    <div className={styles.searchContainer}>
      <div className={styles.searchInputWrapper}>
        <span className={styles.searchIcon} aria-hidden="true">🔍</span>
        <input
          ref={inputRef}
          type="search"
          className={styles.searchInput}
          placeholder={placeholder}
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          aria-label="Search employees"
          aria-autocomplete={showSuggestions ? 'list' : 'none'}
          aria-controls={showSuggestions ? 'search-suggestions' : undefined}
          aria-expanded={showDropdown && suggestions.length > 0}
          role="combobox"
        />
        {inputValue && (
          <button
            type="button"
            className={styles.searchClear}
            onClick={handleClear}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
        {isLoading && (
          <span className={styles.searchSpinner} aria-hidden="true" />
        )}
      </div>

      {/* Suggestions Dropdown */}
      {showSuggestions && showDropdown && suggestions.length > 0 && (
        <ul
          ref={dropdownRef}
          id="search-suggestions"
          className={styles.suggestionsDropdown}
          role="listbox"
          aria-label="Search suggestions"
        >
          {suggestions.map((suggestion, index) => (
            <li
              key={suggestion.id}
              className={`${styles.suggestionItem} ${
                index === selectedIndex ? styles.suggestionItemSelected : ''
              }`}
              onClick={() => handleSuggestionClick(suggestion)}
              onMouseEnter={() => setSelectedIndex(index)}
              role="option"
              aria-selected={index === selectedIndex}
            >
              <div className={styles.suggestionAvatar}>
                {suggestion.profileImageUrl ? (
                  <img src={suggestion.profileImageUrl} alt="" />
                ) : (
                  <span>
                    {suggestion.firstName?.[0]}{suggestion.lastName?.[0]}
                  </span>
                )}
              </div>
              <div className={styles.suggestionInfo}>
                <span className={styles.suggestionName}>
                  {suggestion.firstName} {suggestion.lastName}
                </span>
                <span className={styles.suggestionMeta}>
                  {suggestion.jobTitle}
                  {suggestion.department && ` • ${suggestion.department.name}`}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

DirectorySearchInput.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  debounceMs: PropTypes.number,
  showSuggestions: PropTypes.bool,
  onSuggestionSelect: PropTypes.func,
};

DirectorySearchInput.defaultProps = {
  value: '',
  placeholder: 'Search by name, email, or job title...',
  debounceMs: 300,
  showSuggestions: true,
  onSuggestionSelect: null,
};

export default DirectorySearchInput;

