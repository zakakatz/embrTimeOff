/**
 * OrganizationalChartNode Component
 * 
 * Renders individual employee nodes within the organizational chart.
 */

import React, { useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import styles from './OrganizationalChart.module.css';

export function OrganizationalChartNode({
  node,
  isExpanded,
  isSelected,
  isHighlighted,
  isLoading,
  hasChildren,
  childCount,
  onToggle,
  onSelect,
  onNavigate,
  showQuickView,
  compact,
}) {
  const nodeRef = useRef(null);
  
  const displayName = node.preferredName || node.firstName;
  const fullName = `${displayName} ${node.lastName}`;
  const initials = `${node.firstName?.[0] || ''}${node.lastName?.[0] || ''}`;

  const handleClick = useCallback((e) => {
    e.stopPropagation();
    onSelect?.(node);
  }, [node, onSelect]);

  const handleToggle = useCallback((e) => {
    e.stopPropagation();
    onToggle?.(node.id, hasChildren && !node.directReports?.length);
  }, [node.id, hasChildren, node.directReports, onToggle]);

  const handleDoubleClick = useCallback((e) => {
    e.stopPropagation();
    onNavigate?.(node.id);
  }, [node.id, onNavigate]);

  const handleKeyDown = useCallback((e) => {
    switch (e.key) {
      case 'Enter':
        onSelect?.(node);
        break;
      case ' ':
        e.preventDefault();
        onToggle?.(node.id);
        break;
      case 'ArrowRight':
        if (!isExpanded && hasChildren) {
          onToggle?.(node.id);
        }
        break;
      case 'ArrowLeft':
        if (isExpanded) {
          onToggle?.(node.id);
        }
        break;
      default:
        break;
    }
  }, [node, isExpanded, hasChildren, onSelect, onToggle]);

  if (compact) {
    return (
      <div
        ref={nodeRef}
        className={`${styles.nodeCompact} ${isSelected ? styles.nodeSelected : ''} ${isHighlighted ? styles.nodeHighlighted : ''}`}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        onKeyDown={handleKeyDown}
        role="treeitem"
        tabIndex={0}
        aria-expanded={hasChildren ? isExpanded : undefined}
        aria-selected={isSelected}
        aria-label={`${fullName}, ${node.jobTitle || 'Employee'}`}
      >
        <div className={styles.nodeCompactAvatar}>
          {node.profileImageUrl ? (
            <img src={node.profileImageUrl} alt="" />
          ) : (
            <span>{initials}</span>
          )}
        </div>
        <span className={styles.nodeCompactName}>{fullName}</span>
        {hasChildren && (
          <button
            className={styles.nodeCompactToggle}
            onClick={handleToggle}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isLoading ? '⟳' : isExpanded ? '−' : '+'}
          </button>
        )}
      </div>
    );
  }

  return (
    <article
      ref={nodeRef}
      className={`
        ${styles.node}
        ${isSelected ? styles.nodeSelected : ''}
        ${isHighlighted ? styles.nodeHighlighted : ''}
        ${isLoading ? styles.nodeLoading : ''}
      `}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onKeyDown={handleKeyDown}
      role="treeitem"
      tabIndex={0}
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-selected={isSelected}
      aria-label={`${fullName}, ${node.jobTitle || 'Employee'}${hasChildren ? `, ${childCount} direct reports` : ''}`}
      data-node-id={node.id}
    >
      {/* Avatar */}
      <div className={styles.nodeAvatar}>
        {node.profileImageUrl ? (
          <img
            src={node.profileImageUrl}
            alt=""
            className={styles.nodeAvatarImage}
          />
        ) : (
          <span className={styles.nodeAvatarInitials}>{initials}</span>
        )}
        {node.employmentStatus === 'active' && (
          <span className={styles.nodeStatusIndicator} aria-label="Active" />
        )}
      </div>

      {/* Info */}
      <div className={styles.nodeInfo}>
        <h4 className={styles.nodeName}>{fullName}</h4>
        {node.jobTitle && (
          <p className={styles.nodeTitle}>{node.jobTitle}</p>
        )}
        {node.department && (
          <p className={styles.nodeDepartment}>{node.department.name}</p>
        )}
      </div>

      {/* Quick Actions */}
      {showQuickView && (
        <div className={styles.nodeActions}>
          {node.email && (
            <a
              href={`mailto:${node.email}`}
              className={styles.nodeActionButton}
              onClick={(e) => e.stopPropagation()}
              aria-label="Send email"
              title="Send email"
            >
              ✉️
            </a>
          )}
          {node.phone && (
            <a
              href={`tel:${node.phone}`}
              className={styles.nodeActionButton}
              onClick={(e) => e.stopPropagation()}
              aria-label="Call"
              title="Call"
            >
              📞
            </a>
          )}
        </div>
      )}

      {/* Expand/Collapse Toggle */}
      {hasChildren && (
        <button
          className={styles.nodeToggle}
          onClick={handleToggle}
          aria-label={isExpanded ? `Collapse ${fullName}'s team` : `Expand ${fullName}'s team`}
          title={`${childCount} direct report${childCount !== 1 ? 's' : ''}`}
        >
          {isLoading ? (
            <span className={styles.nodeToggleSpinner} aria-hidden="true">⟳</span>
          ) : (
            <>
              <span className={styles.nodeToggleIcon} aria-hidden="true">
                {isExpanded ? '▼' : '▶'}
              </span>
              <span className={styles.nodeToggleCount}>{childCount}</span>
            </>
          )}
        </button>
      )}

      {/* Loading overlay */}
      {isLoading && (
        <div className={styles.nodeLoadingOverlay} aria-hidden="true">
          <span className={styles.nodeLoadingSpinner} />
        </div>
      )}
    </article>
  );
}

OrganizationalChartNode.propTypes = {
  node: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    firstName: PropTypes.string.isRequired,
    lastName: PropTypes.string.isRequired,
    preferredName: PropTypes.string,
    jobTitle: PropTypes.string,
    email: PropTypes.string,
    phone: PropTypes.string,
    profileImageUrl: PropTypes.string,
    employmentStatus: PropTypes.string,
    directReports: PropTypes.array,
    department: PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
      name: PropTypes.string,
    }),
  }).isRequired,
  isExpanded: PropTypes.bool,
  isSelected: PropTypes.bool,
  isHighlighted: PropTypes.bool,
  isLoading: PropTypes.bool,
  hasChildren: PropTypes.bool,
  childCount: PropTypes.number,
  onToggle: PropTypes.func,
  onSelect: PropTypes.func,
  onNavigate: PropTypes.func,
  showQuickView: PropTypes.bool,
  compact: PropTypes.bool,
};

OrganizationalChartNode.defaultProps = {
  isExpanded: false,
  isSelected: false,
  isHighlighted: false,
  isLoading: false,
  hasChildren: false,
  childCount: 0,
  onToggle: null,
  onSelect: null,
  onNavigate: null,
  showQuickView: true,
  compact: false,
};

export default OrganizationalChartNode;

