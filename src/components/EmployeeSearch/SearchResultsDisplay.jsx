/**
 * SearchResultsDisplay Component
 * 
 * Displays search results with relevance scoring and contextual information.
 */

import React, { useCallback } from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeSearch.module.css';

export function SearchResultsDisplay({
  results,
  query,
  loading,
  error,
  onEmployeeSelect,
  onRetry,
  showRelevance,
  highlightMatches,
}) {
  const handleEmployeeClick = useCallback((employee) => {
    onEmployeeSelect?.(employee);
  }, [onEmployeeSelect]);

  if (loading) {
    return (
      <div className={styles.resultsContainer} role="status" aria-live="polite">
        <div className={styles.resultsLoading}>
          <div className={styles.resultsSpinner} aria-hidden="true" />
          <span>Searching employees...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.resultsContainer} role="alert">
        <div className={styles.resultsError}>
          <span className={styles.errorIcon} aria-hidden="true">⚠️</span>
          <h3>Search Failed</h3>
          <p>{error}</p>
          {onRetry && (
            <button
              type="button"
              className={styles.retryButton}
              onClick={onRetry}
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className={styles.resultsContainer}>
        <div className={styles.resultsEmpty}>
          <span className={styles.emptyIcon} aria-hidden="true">🔍</span>
          <h3>No Results Found</h3>
          <p>
            {query
              ? `No employees match "${query}". Try different keywords or adjust your filters.`
              : 'Enter a search query to find employees.'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.resultsContainer}>
      <div className={styles.resultsHeader}>
        <span className={styles.resultsCount}>
          {results.length} result{results.length !== 1 ? 's' : ''} found
          {query && <> for "<strong>{query}</strong>"</>}
        </span>
        {showRelevance && (
          <span className={styles.resultsSortInfo}>
            Sorted by relevance
          </span>
        )}
      </div>

      <ul className={styles.resultsList} role="list" aria-label="Search results">
        {results.map((employee, index) => (
          <li key={employee.id} className={styles.resultItem}>
            <button
              type="button"
              className={styles.resultButton}
              onClick={() => handleEmployeeClick(employee)}
              aria-label={`View profile for ${employee.firstName} ${employee.lastName}`}
            >
              {/* Rank indicator */}
              <span className={styles.resultRank} aria-hidden="true">
                {index + 1}
              </span>

              {/* Avatar */}
              <div className={styles.resultAvatar}>
                {employee.profileImageUrl ? (
                  <img
                    src={employee.profileImageUrl}
                    alt=""
                    className={styles.avatarImage}
                  />
                ) : (
                  <span className={styles.avatarInitials}>
                    {employee.firstName?.[0]}{employee.lastName?.[0]}
                  </span>
                )}
                {employee.employmentStatus === 'active' && (
                  <span className={styles.statusDot} aria-label="Active" />
                )}
              </div>

              {/* Employee Info */}
              <div className={styles.resultInfo}>
                <div className={styles.resultName}>
                  {highlightMatches ? (
                    <HighlightedText
                      text={`${employee.firstName} ${employee.lastName}`}
                      query={query}
                    />
                  ) : (
                    `${employee.firstName} ${employee.lastName}`
                  )}
                  {employee.preferredName && employee.preferredName !== employee.firstName && (
                    <span className={styles.resultPreferredName}>
                      ({employee.preferredName})
                    </span>
                  )}
                </div>

                <div className={styles.resultMeta}>
                  {employee.jobTitle && (
                    <span className={styles.resultJobTitle}>
                      {highlightMatches ? (
                        <HighlightedText text={employee.jobTitle} query={query} />
                      ) : (
                        employee.jobTitle
                      )}
                    </span>
                  )}
                  {employee.department && (
                    <span className={styles.resultDepartment}>
                      {employee.department.name}
                    </span>
                  )}
                  {employee.location && (
                    <span className={styles.resultLocation}>
                      📍 {employee.location.name}
                    </span>
                  )}
                </div>

                {/* Contact Info */}
                <div className={styles.resultContact}>
                  {employee.email && (
                    <span className={styles.resultEmail}>
                      ✉️ {employee.email}
                    </span>
                  )}
                  {employee.phone && (
                    <span className={styles.resultPhone}>
                      📞 {employee.phone}
                    </span>
                  )}
                </div>

                {/* Manager Info */}
                {employee.manager && (
                  <div className={styles.resultManager}>
                    Reports to: {employee.manager.firstName} {employee.manager.lastName}
                  </div>
                )}
              </div>

              {/* Relevance Score */}
              {showRelevance && employee.relevanceScore != null && (
                <div className={styles.resultRelevance}>
                  <div
                    className={styles.relevanceBar}
                    style={{ width: `${Math.round(employee.relevanceScore * 100)}%` }}
                    aria-hidden="true"
                  />
                  <span className={styles.relevanceText}>
                    {Math.round(employee.relevanceScore * 100)}% match
                  </span>
                </div>
              )}

              {/* Profile Completeness */}
              {employee.profileCompleteness != null && (
                <div className={styles.resultCompleteness}>
                  <span
                    className={styles.completenessIndicator}
                    style={{
                      '--completeness': `${employee.profileCompleteness}%`
                    }}
                    aria-label={`Profile ${employee.profileCompleteness}% complete`}
                  >
                    {employee.profileCompleteness}%
                  </span>
                </div>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Helper component to highlight matching text
 */
function HighlightedText({ text, query }) {
  if (!query || !text) return <span>{text}</span>;

  const words = query.toLowerCase().split(/\s+/).filter(w => w.length > 0);
  if (words.length === 0) return <span>{text}</span>;

  const pattern = new RegExp(`(${words.map(escapeRegExp).join('|')})`, 'gi');
  const parts = text.split(pattern);

  return (
    <span>
      {parts.map((part, index) => (
        words.some(w => part.toLowerCase() === w) ? (
          <mark key={index} className={styles.highlight}>{part}</mark>
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

SearchResultsDisplay.propTypes = {
  results: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      firstName: PropTypes.string.isRequired,
      lastName: PropTypes.string.isRequired,
      preferredName: PropTypes.string,
      jobTitle: PropTypes.string,
      email: PropTypes.string,
      phone: PropTypes.string,
      profileImageUrl: PropTypes.string,
      employmentStatus: PropTypes.string,
      relevanceScore: PropTypes.number,
      profileCompleteness: PropTypes.number,
      department: PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        name: PropTypes.string,
      }),
      location: PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        name: PropTypes.string,
      }),
      manager: PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        firstName: PropTypes.string,
        lastName: PropTypes.string,
      }),
    })
  ),
  query: PropTypes.string,
  loading: PropTypes.bool,
  error: PropTypes.string,
  onEmployeeSelect: PropTypes.func,
  onRetry: PropTypes.func,
  showRelevance: PropTypes.bool,
  highlightMatches: PropTypes.bool,
};

SearchResultsDisplay.defaultProps = {
  results: [],
  query: '',
  loading: false,
  error: null,
  onEmployeeSelect: null,
  onRetry: null,
  showRelevance: true,
  highlightMatches: true,
};

export default SearchResultsDisplay;

