/**
 * SavedSearches Component
 * 
 * Displays and manages saved search configurations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { employeeService } from '../../services/employeeService';
import styles from './EmployeeSearch.module.css';

export function SavedSearches({ onSelect, onSave, currentSearch }) {
  const [savedSearches, setSavedSearches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [error, setError] = useState(null);

  // Fetch saved searches
  useEffect(() => {
    const fetchSaved = async () => {
      setLoading(true);
      try {
        const searches = await employeeService.getSavedSearches();
        setSavedSearches(searches);
      } catch (err) {
        console.error('Failed to fetch saved searches:', err);
        setSavedSearches([]);
      } finally {
        setLoading(false);
      }
    };

    fetchSaved();
  }, []);

  const handleSave = useCallback(async () => {
    if (!saveName.trim()) {
      setError('Please enter a name for this search');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const saved = await employeeService.saveSearch({
        name: saveName.trim(),
        query: currentSearch.query,
        filters: currentSearch.filters,
      });

      setSavedSearches((prev) => [saved, ...prev]);
      setSaveName('');
      setShowSaveForm(false);
      onSave?.(saved);
    } catch (err) {
      setError('Failed to save search. Please try again.');
      console.error('Save error:', err);
    } finally {
      setIsSaving(false);
    }
  }, [saveName, currentSearch, onSave]);

  const handleDelete = useCallback(async (searchId) => {
    try {
      await employeeService.deleteSavedSearch(searchId);
      setSavedSearches((prev) => prev.filter((s) => s.id !== searchId));
    } catch (err) {
      console.error('Failed to delete saved search:', err);
    }
  }, []);

  const handleSelect = useCallback((search) => {
    onSelect({
      query: search.query,
      filters: search.filters,
    });
  }, [onSelect]);

  const canSaveCurrentSearch = currentSearch && 
    (currentSearch.query || Object.values(currentSearch.filters || {}).some(v => v));

  if (loading) {
    return (
      <div className={styles.savedSearches}>
        <div className={styles.savedSearchesLoading}>
          Loading saved searches...
        </div>
      </div>
    );
  }

  return (
    <div className={styles.savedSearches}>
      <div className={styles.savedSearchesHeader}>
        <button
          type="button"
          className={styles.savedSearchesToggle}
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
          aria-controls="saved-searches-list"
        >
          <span className={styles.savedSearchesIcon} aria-hidden="true">⭐</span>
          Saved Searches
          {savedSearches.length > 0 && (
            <span className={styles.savedSearchesBadge}>{savedSearches.length}</span>
          )}
          <span className={styles.savedSearchesChevron} aria-hidden="true">
            {isExpanded ? '▲' : '▼'}
          </span>
        </button>
        {canSaveCurrentSearch && (
          <button
            type="button"
            className={styles.savedSearchesSaveButton}
            onClick={() => setShowSaveForm(!showSaveForm)}
            aria-expanded={showSaveForm}
          >
            {showSaveForm ? 'Cancel' : '+ Save Current'}
          </button>
        )}
      </div>

      {/* Save Form */}
      {showSaveForm && (
        <div className={styles.saveSearchForm}>
          <input
            type="text"
            className={styles.saveSearchInput}
            placeholder="Enter a name for this search..."
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            aria-label="Search name"
          />
          <button
            type="button"
            className={styles.saveSearchButton}
            onClick={handleSave}
            disabled={isSaving || !saveName.trim()}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
          {error && (
            <div className={styles.saveSearchError} role="alert">
              {error}
            </div>
          )}
        </div>
      )}

      {/* Saved Searches List */}
      {isExpanded && (
        <div id="saved-searches-list">
          {savedSearches.length === 0 ? (
            <div className={styles.savedSearchesEmpty}>
              <p>No saved searches yet.</p>
              <p className={styles.savedSearchesHint}>
                Save your frequently used searches for quick access.
              </p>
            </div>
          ) : (
            <ul className={styles.savedSearchesList} role="list">
              {savedSearches.map((search) => (
                <li key={search.id} className={styles.savedSearchItem}>
                  <button
                    type="button"
                    className={styles.savedSearchButton}
                    onClick={() => handleSelect(search)}
                  >
                    <span className={styles.savedSearchName}>{search.name}</span>
                    <span className={styles.savedSearchDetails}>
                      {search.query && (
                        <span className={styles.savedSearchQuery}>
                          "{search.query}"
                        </span>
                      )}
                      {search.filters && Object.keys(search.filters).length > 0 && (
                        <span className={styles.savedSearchFilters}>
                          +{Object.keys(search.filters).filter(k => search.filters[k]).length} filters
                        </span>
                      )}
                    </span>
                  </button>
                  <button
                    type="button"
                    className={styles.savedSearchDelete}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(search.id);
                    }}
                    aria-label={`Delete "${search.name}" saved search`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

SavedSearches.propTypes = {
  onSelect: PropTypes.func.isRequired,
  onSave: PropTypes.func,
  currentSearch: PropTypes.shape({
    query: PropTypes.string,
    filters: PropTypes.object,
  }),
};

SavedSearches.defaultProps = {
  onSave: null,
  currentSearch: null,
};

export default SavedSearches;

