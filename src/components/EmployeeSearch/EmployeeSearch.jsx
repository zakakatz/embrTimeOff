/**
 * EmployeeSearch Component
 * 
 * Sophisticated search interface with fuzzy matching, field-specific searches,
 * search suggestions, recent history, and saved searches.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import { useDebounce } from '../../hooks/useDebounce';
import { usePermissions } from '../../hooks/usePermissions';
import SearchSuggestions from './SearchSuggestions';
import AdvancedSearchForm from './AdvancedSearchForm';
import RecentSearches from './RecentSearches';
import SavedSearches from './SavedSearches';
import SearchResultsDisplay from './SearchResultsDisplay';
import styles from './EmployeeSearch.module.css';

export function EmployeeSearch({
  onEmployeeSelect,
  showSuggestions,
  showRecentSearches,
  showSavedSearches,
  showAdvancedSearch,
  autoFocus,
}) {
  // State
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [results, setResults] = useState([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const [showSuggestionsDropdown, setShowSuggestionsDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isFetchingSuggestions, setIsFetchingSuggestions] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState({});

  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const debouncedQuery = useDebounce(query, 200);

  const { hasPermission } = usePermissions();

  // Auto-focus on mount
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  // Fetch suggestions when query changes
  useEffect(() => {
    if (!showSuggestions || !debouncedQuery || debouncedQuery.length < 2) {
      setSuggestions([]);
      return;
    }

    const fetchSuggestions = async () => {
      setIsFetchingSuggestions(true);
      try {
        const data = await employeeService.getSearchSuggestions(debouncedQuery);
        setSuggestions(data);
        setShowSuggestionsDropdown(true);
      } catch (error) {
        console.error('Failed to fetch suggestions:', error);
        setSuggestions([]);
      } finally {
        setIsFetchingSuggestions(false);
      }
    };

    fetchSuggestions();
  }, [debouncedQuery, showSuggestions]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setShowSuggestionsDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Execute search
  const executeSearch = useCallback(async (searchQuery, filters = {}) => {
    setIsSearching(true);
    setSearchError(null);
    setHasSearched(true);
    setShowSuggestionsDropdown(false);

    try {
      const response = await employeeService.searchEmployees({
        query: searchQuery,
        filters: { ...advancedFilters, ...filters },
        fuzzy: true,
        limit: 50,
      });

      setResults(response.data || response);
    } catch (error) {
      setSearchError(error.message || 'Search failed. Please try again.');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [advancedFilters]);

  // Handlers
  const handleInputChange = useCallback((e) => {
    setQuery(e.target.value);
    setSelectedSuggestionIndex(-1);
    if (e.target.value.length >= 2) {
      setShowSuggestionsDropdown(true);
    }
  }, []);

  const handleKeyDown = useCallback((e) => {
    if (showSuggestionsDropdown && suggestions.length > 0) {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedSuggestionIndex((prev) =>
            prev < suggestions.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedSuggestionIndex((prev) => (prev > 0 ? prev - 1 : -1));
          break;
        case 'Enter':
          e.preventDefault();
          if (selectedSuggestionIndex >= 0) {
            handleSuggestionSelect(suggestions[selectedSuggestionIndex]);
          } else {
            executeSearch(query);
          }
          break;
        case 'Escape':
          setShowSuggestionsDropdown(false);
          break;
        default:
          break;
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeSearch(query);
    }
  }, [showSuggestionsDropdown, suggestions, selectedSuggestionIndex, query, executeSearch]);

  const handleSuggestionSelect = useCallback((suggestion) => {
    setQuery(`${suggestion.firstName} ${suggestion.lastName}`);
    setShowSuggestionsDropdown(false);
    onEmployeeSelect?.(suggestion);
  }, [onEmployeeSelect]);

  const handleSuggestionHover = useCallback((index) => {
    setSelectedSuggestionIndex(index);
  }, []);

  const handleSearch = useCallback(() => {
    executeSearch(query);
  }, [executeSearch, query]);

  const handleClearSearch = useCallback(() => {
    setQuery('');
    setResults([]);
    setHasSearched(false);
    setSuggestions([]);
    inputRef.current?.focus();
  }, []);

  const handleRecentSearchSelect = useCallback((search) => {
    setQuery(search.query);
    setAdvancedFilters(search.filters || {});
    executeSearch(search.query, search.filters);
  }, [executeSearch]);

  const handleSavedSearchSelect = useCallback((search) => {
    setQuery(search.query);
    setAdvancedFilters(search.filters || {});
    executeSearch(search.query, search.filters);
  }, [executeSearch]);

  const handleAdvancedSearch = useCallback((filters) => {
    setAdvancedFilters(filters);
    executeSearch(query, filters);
  }, [executeSearch, query]);

  const handleAdvancedReset = useCallback(() => {
    setAdvancedFilters({});
  }, []);

  const handleFocus = useCallback(() => {
    if (suggestions.length > 0) {
      setShowSuggestionsDropdown(true);
    }
  }, [suggestions.length]);

  return (
    <div className={styles.searchPage}>
      {/* Header */}
      <header className={styles.searchHeader}>
        <h1 className={styles.searchTitle}>Employee Search</h1>
        <p className={styles.searchSubtitle}>
          Find employees by name, email, job title, or other criteria
        </p>
      </header>

      {/* Main Search Input */}
      <div className={styles.searchContainer} ref={containerRef}>
        <div className={styles.searchInputWrapper}>
          <span className={styles.searchIcon} aria-hidden="true">🔍</span>
          <input
            ref={inputRef}
            type="search"
            className={styles.searchInput}
            placeholder="Search by name, email, job title..."
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            aria-label="Search employees"
            aria-autocomplete="list"
            aria-controls="search-suggestions"
            aria-expanded={showSuggestionsDropdown && suggestions.length > 0}
            role="combobox"
          />
          {query && (
            <button
              type="button"
              className={styles.clearButton}
              onClick={handleClearSearch}
              aria-label="Clear search"
            >
              ×
            </button>
          )}
          <button
            type="button"
            className={styles.searchButton}
            onClick={handleSearch}
            disabled={isSearching}
          >
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Suggestions Dropdown */}
        {showSuggestions && showSuggestionsDropdown && (
          <div id="search-suggestions">
            <SearchSuggestions
              suggestions={suggestions}
              selectedIndex={selectedSuggestionIndex}
              onSelect={handleSuggestionSelect}
              onHover={handleSuggestionHover}
              isLoading={isFetchingSuggestions}
              query={query}
            />
          </div>
        )}
      </div>

      {/* Advanced Search */}
      {showAdvancedSearch && (
        <AdvancedSearchForm
          initialValues={advancedFilters}
          onSearch={handleAdvancedSearch}
          onReset={handleAdvancedReset}
          isSearching={isSearching}
        />
      )}

      {/* Sidebar: Recent & Saved Searches */}
      <div className={styles.searchLayout}>
        <aside className={styles.searchSidebar}>
          {showRecentSearches && (
            <RecentSearches
              onSelect={handleRecentSearchSelect}
              maxItems={10}
            />
          )}
          {showSavedSearches && hasPermission('save_searches') && (
            <SavedSearches
              onSelect={handleSavedSearchSelect}
              currentSearch={{ query, filters: advancedFilters }}
            />
          )}
        </aside>

        {/* Search Results */}
        <main className={styles.searchMain}>
          {hasSearched && (
            <SearchResultsDisplay
              results={results}
              query={query}
              loading={isSearching}
              error={searchError}
              onEmployeeSelect={onEmployeeSelect}
              onRetry={handleSearch}
              showRelevance={true}
              highlightMatches={true}
            />
          )}

          {!hasSearched && (
            <div className={styles.searchWelcome}>
              <span className={styles.welcomeIcon} aria-hidden="true">👥</span>
              <h2>Find Your Colleagues</h2>
              <p>
                Use the search bar above to find employees. You can search by:
              </p>
              <ul className={styles.welcomeList}>
                <li>Name (first, last, or preferred)</li>
                <li>Email address</li>
                <li>Job title or department</li>
                <li>Employee ID</li>
                <li>Location</li>
              </ul>
              <p className={styles.welcomeTip}>
                💡 Tip: Use Advanced Search for more specific criteria
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

EmployeeSearch.propTypes = {
  onEmployeeSelect: PropTypes.func,
  showSuggestions: PropTypes.bool,
  showRecentSearches: PropTypes.bool,
  showSavedSearches: PropTypes.bool,
  showAdvancedSearch: PropTypes.bool,
  autoFocus: PropTypes.bool,
};

EmployeeSearch.defaultProps = {
  onEmployeeSelect: null,
  showSuggestions: true,
  showRecentSearches: true,
  showSavedSearches: true,
  showAdvancedSearch: true,
  autoFocus: false,
};

export default EmployeeSearch;

