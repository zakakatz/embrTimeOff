/**
 * SearchSuggestions Component
 * 
 * Displays real-time search suggestions as the user types.
 */

import React from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeSearch.module.css';

export function SearchSuggestions({
  suggestions,
  selectedIndex,
  onSelect,
  onHover,
  isLoading,
  query,
}) {
  if (isLoading) {
    return (
      <div className={styles.suggestionsContainer} role="status">
        <div className={styles.suggestionsLoading}>
          <span className={styles.suggestionsSpinner} aria-hidden="true" />
          Searching...
        </div>
      </div>
    );
  }

  if (!suggestions || suggestions.length === 0) {
    if (query && query.length >= 2) {
      return (
        <div className={styles.suggestionsContainer}>
          <div className={styles.suggestionsEmpty}>
            No suggestions found for "{query}"
          </div>
        </div>
      );
    }
    return null;
  }

  return (
    <ul
      className={styles.suggestionsList}
      role="listbox"
      aria-label="Search suggestions"
    >
      {suggestions.map((suggestion, index) => (
        <li
          key={suggestion.id}
          className={`${styles.suggestionItem} ${
            index === selectedIndex ? styles.suggestionItemActive : ''
          }`}
          onClick={() => onSelect(suggestion)}
          onMouseEnter={() => onHover(index)}
          role="option"
          aria-selected={index === selectedIndex}
        >
          <div className={styles.suggestionAvatar}>
            {suggestion.profileImageUrl ? (
              <img src={suggestion.profileImageUrl} alt="" />
            ) : (
              <span className={styles.suggestionInitials}>
                {suggestion.firstName?.[0]}{suggestion.lastName?.[0]}
              </span>
            )}
          </div>
          <div className={styles.suggestionContent}>
            <div className={styles.suggestionName}>
              <HighlightMatch
                text={`${suggestion.firstName} ${suggestion.lastName}`}
                query={query}
              />
            </div>
            <div className={styles.suggestionMeta}>
              {suggestion.jobTitle && (
                <span className={styles.suggestionJobTitle}>
                  {suggestion.jobTitle}
                </span>
              )}
              {suggestion.department && (
                <span className={styles.suggestionDepartment}>
                  {suggestion.department.name}
                </span>
              )}
            </div>
          </div>
          {suggestion.relevanceScore && (
            <div className={styles.suggestionScore}>
              {Math.round(suggestion.relevanceScore * 100)}% match
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * Helper component to highlight matching text
 */
function HighlightMatch({ text, query }) {
  if (!query || !text) return <span>{text}</span>;

  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'gi'));

  return (
    <span>
      {parts.map((part, index) => (
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={index} className={styles.highlightMatch}>{part}</mark>
        ) : (
          <span key={index}>{part}</span>
        )
      ))}
    </span>
  );
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

SearchSuggestions.propTypes = {
  suggestions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      firstName: PropTypes.string.isRequired,
      lastName: PropTypes.string.isRequired,
      jobTitle: PropTypes.string,
      profileImageUrl: PropTypes.string,
      relevanceScore: PropTypes.number,
      department: PropTypes.shape({
        name: PropTypes.string,
      }),
    })
  ),
  selectedIndex: PropTypes.number,
  onSelect: PropTypes.func.isRequired,
  onHover: PropTypes.func.isRequired,
  isLoading: PropTypes.bool,
  query: PropTypes.string,
};

SearchSuggestions.defaultProps = {
  suggestions: [],
  selectedIndex: -1,
  isLoading: false,
  query: '',
};

export default SearchSuggestions;

