/**
 * DirectoryPagination Component
 * 
 * Pagination controls for the employee directory.
 */

import React, { useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeDirectory.module.css';

export function DirectoryPagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions,
  showPageSizeSelector,
  showItemCount,
  maxVisiblePages,
}) {
  // Calculate visible page numbers
  const pageNumbers = useMemo(() => {
    const pages = [];
    const half = Math.floor(maxVisiblePages / 2);
    
    let start = Math.max(1, currentPage - half);
    let end = Math.min(totalPages, start + maxVisiblePages - 1);
    
    // Adjust start if we're near the end
    if (end - start + 1 < maxVisiblePages) {
      start = Math.max(1, end - maxVisiblePages + 1);
    }
    
    // Add first page and ellipsis if needed
    if (start > 1) {
      pages.push(1);
      if (start > 2) {
        pages.push('...');
      }
    }
    
    // Add visible pages
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }
    
    // Add ellipsis and last page if needed
    if (end < totalPages) {
      if (end < totalPages - 1) {
        pages.push('...');
      }
      pages.push(totalPages);
    }
    
    return pages;
  }, [currentPage, totalPages, maxVisiblePages]);

  // Calculate item range being displayed
  const itemRange = useMemo(() => {
    const start = (currentPage - 1) * pageSize + 1;
    const end = Math.min(currentPage * pageSize, totalItems);
    return { start, end };
  }, [currentPage, pageSize, totalItems]);

  const handlePrevious = useCallback(() => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  }, [currentPage, onPageChange]);

  const handleNext = useCallback(() => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  }, [currentPage, totalPages, onPageChange]);

  const handlePageClick = useCallback((page) => {
    if (typeof page === 'number' && page !== currentPage) {
      onPageChange(page);
    }
  }, [currentPage, onPageChange]);

  const handlePageSizeChange = useCallback((e) => {
    const newSize = parseInt(e.target.value, 10);
    onPageSizeChange(newSize);
  }, [onPageSizeChange]);

  if (totalPages <= 1 && !showItemCount) {
    return null;
  }

  return (
    <nav
      className={styles.pagination}
      role="navigation"
      aria-label="Directory pagination"
    >
      {/* Item Count */}
      {showItemCount && (
        <div className={styles.paginationInfo}>
          Showing {itemRange.start}–{itemRange.end} of {totalItems} employees
        </div>
      )}

      {/* Page Size Selector */}
      {showPageSizeSelector && (
        <div className={styles.pageSizeSelector}>
          <label htmlFor="page-size" className={styles.pageSizeLabel}>
            Show:
          </label>
          <select
            id="page-size"
            className={styles.pageSizeSelect}
            value={pageSize}
            onChange={handlePageSizeChange}
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Page Navigation */}
      {totalPages > 1 && (
        <div className={styles.paginationControls}>
          {/* Previous Button */}
          <button
            type="button"
            className={`${styles.paginationButton} ${styles.paginationNav}`}
            onClick={handlePrevious}
            disabled={currentPage === 1}
            aria-label="Go to previous page"
          >
            ← Previous
          </button>

          {/* Page Numbers */}
          <div className={styles.pageNumbers} role="group" aria-label="Page numbers">
            {pageNumbers.map((page, index) => (
              page === '...' ? (
                <span
                  key={`ellipsis-${index}`}
                  className={styles.paginationEllipsis}
                  aria-hidden="true"
                >
                  …
                </span>
              ) : (
                <button
                  key={page}
                  type="button"
                  className={`${styles.paginationButton} ${
                    page === currentPage ? styles.paginationButtonActive : ''
                  }`}
                  onClick={() => handlePageClick(page)}
                  aria-current={page === currentPage ? 'page' : undefined}
                  aria-label={`Go to page ${page}`}
                >
                  {page}
                </button>
              )
            ))}
          </div>

          {/* Next Button */}
          <button
            type="button"
            className={`${styles.paginationButton} ${styles.paginationNav}`}
            onClick={handleNext}
            disabled={currentPage === totalPages}
            aria-label="Go to next page"
          >
            Next →
          </button>
        </div>
      )}
    </nav>
  );
}

DirectoryPagination.propTypes = {
  currentPage: PropTypes.number.isRequired,
  totalPages: PropTypes.number.isRequired,
  totalItems: PropTypes.number.isRequired,
  pageSize: PropTypes.number.isRequired,
  onPageChange: PropTypes.func.isRequired,
  onPageSizeChange: PropTypes.func,
  pageSizeOptions: PropTypes.arrayOf(PropTypes.number),
  showPageSizeSelector: PropTypes.bool,
  showItemCount: PropTypes.bool,
  maxVisiblePages: PropTypes.number,
};

DirectoryPagination.defaultProps = {
  onPageSizeChange: () => {},
  pageSizeOptions: [10, 20, 50, 100],
  showPageSizeSelector: true,
  showItemCount: true,
  maxVisiblePages: 5,
};

export default DirectoryPagination;

