/**
 * RecentSearches Component
 * 
 * Displays and manages user's recent search history.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import styles from './EmployeeSearch.module.css';

export function RecentSearches({ onSelect, onClear, maxItems }) {
  const [recentSearches, setRecentSearches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(true);

  // Fetch recent searches
  useEffect(() => {
    const fetchRecent = async () => {
      setLoading(true);
      try {
        const searches = await employeeService.getRecentSearches(maxItems);
        setRecentSearches(searches);
      } catch (error) {
        console.error('Failed to fetch recent searches:', error);
        setRecentSearches([]);
      } finally {
        setLoading(false);
      }
    };

    fetchRecent();
  }, [maxItems]);

  const handleClear = useCallback(async () => {
    try {
      await employeeService.clearRecentSearches();
      setRecentSearches([]);
      onClear?.();
    } catch (error) {
      console.error('Failed to clear recent searches:', error);
    }
  }, [onClear]);

  const handleSelect = useCallback((search) => {
    onSelect(search);
  }, [onSelect]);

  const formatTimeAgo = (timestamp) => {
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className={styles.recentSearches}>
        <div className={styles.recentSearchesLoading}>
          Loading recent searches...
        </div>
      </div>
    );
  }

  if (recentSearches.length === 0) {
    return null;
  }

  return (
    <div className={styles.recentSearches}>
      <div className={styles.recentSearchesHeader}>
        <button
          type="button"
          className={styles.recentSearchesToggle}
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
          aria-controls="recent-searches-list"
        >
          <span className={styles.recentSearchesIcon} aria-hidden="true">🕐</span>
          Recent Searches
          <span className={styles.recentSearchesChevron} aria-hidden="true">
            {isExpanded ? '▲' : '▼'}
          </span>
        </button>
        <button
          type="button"
          className={styles.recentSearchesClear}
          onClick={handleClear}
          aria-label="Clear all recent searches"
        >
          Clear all
        </button>
      </div>

      {isExpanded && (
        <ul
          id="recent-searches-list"
          className={styles.recentSearchesList}
          role="list"
          aria-label="Recent searches"
        >
          {recentSearches.map((search) => (
            <li key={search.id} className={styles.recentSearchItem}>
              <button
                type="button"
                className={styles.recentSearchButton}
                onClick={() => handleSelect(search)}
              >
                <span className={styles.recentSearchQuery}>
                  {search.query}
                </span>
                {search.filters && Object.keys(search.filters).length > 0 && (
                  <span className={styles.recentSearchFilters}>
                    {Object.entries(search.filters)
                      .filter(([, value]) => value)
                      .map(([key]) => key)
                      .join(', ')}
                  </span>
                )}
                <span className={styles.recentSearchTime}>
                  {formatTimeAgo(search.timestamp)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

RecentSearches.propTypes = {
  onSelect: PropTypes.func.isRequired,
  onClear: PropTypes.func,
  maxItems: PropTypes.number,
};

RecentSearches.defaultProps = {
  onClear: null,
  maxItems: 10,
};

export default RecentSearches;

