/**
 * EmployeeCard Component
 * 
 * Displays individual employee information in a card format.
 */

import React from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeDirectory.module.css';

export function EmployeeCard({ employee, onClick, compact }) {
  const displayName = employee.preferredName || employee.firstName;
  const initials = `${employee.firstName?.[0] || ''}${employee.lastName?.[0] || ''}`;

  const handleClick = () => {
    onClick?.(employee);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onClick?.(employee);
    }
  };

  if (compact) {
    return (
      <div
        className={styles.cardCompact}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-label={`View profile for ${displayName} ${employee.lastName}`}
      >
        <div className={styles.avatarSmall}>
          {employee.profileImageUrl ? (
            <img
              src={employee.profileImageUrl}
              alt=""
              className={styles.avatarImage}
            />
          ) : (
            <span className={styles.avatarInitials}>{initials}</span>
          )}
        </div>
        <div className={styles.cardCompactInfo}>
          <span className={styles.cardCompactName}>
            {displayName} {employee.lastName}
          </span>
          <span className={styles.cardCompactTitle}>{employee.jobTitle}</span>
        </div>
      </div>
    );
  }

  return (
    <article
      className={styles.card}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`View profile for ${displayName} ${employee.lastName}`}
    >
      <div className={styles.cardHeader}>
        <div className={styles.avatar}>
          {employee.profileImageUrl ? (
            <img
              src={employee.profileImageUrl}
              alt=""
              className={styles.avatarImage}
            />
          ) : (
            <span className={styles.avatarInitials}>{initials}</span>
          )}
          {employee.employmentStatus === 'active' && (
            <span className={styles.statusIndicator} aria-label="Active employee" />
          )}
        </div>
        <div className={styles.cardHeaderInfo}>
          <h3 className={styles.employeeName}>
            {displayName} {employee.lastName}
          </h3>
          <p className={styles.jobTitle}>{employee.jobTitle}</p>
        </div>
      </div>

      <div className={styles.cardBody}>
        {employee.department && (
          <div className={styles.cardField}>
            <span className={styles.fieldIcon} aria-hidden="true">🏢</span>
            <span className={styles.fieldValue}>{employee.department.name}</span>
          </div>
        )}

        {employee.location && (
          <div className={styles.cardField}>
            <span className={styles.fieldIcon} aria-hidden="true">📍</span>
            <span className={styles.fieldValue}>{employee.location.name}</span>
          </div>
        )}

        {employee.email && (
          <div className={styles.cardField}>
            <span className={styles.fieldIcon} aria-hidden="true">✉️</span>
            <a
              href={`mailto:${employee.email}`}
              className={styles.fieldLink}
              onClick={(e) => e.stopPropagation()}
            >
              {employee.email}
            </a>
          </div>
        )}

        {employee.phone && (
          <div className={styles.cardField}>
            <span className={styles.fieldIcon} aria-hidden="true">📞</span>
            <a
              href={`tel:${employee.phone}`}
              className={styles.fieldLink}
              onClick={(e) => e.stopPropagation()}
            >
              {employee.phone}
            </a>
          </div>
        )}
      </div>

      {employee.manager && (
        <div className={styles.cardFooter}>
          <span className={styles.managerLabel}>Reports to:</span>
          <span className={styles.managerName}>
            {employee.manager.preferredName || employee.manager.firstName} {employee.manager.lastName}
          </span>
        </div>
      )}
    </article>
  );
}

EmployeeCard.propTypes = {
  employee: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    employeeId: PropTypes.string,
    firstName: PropTypes.string.isRequired,
    lastName: PropTypes.string.isRequired,
    preferredName: PropTypes.string,
    jobTitle: PropTypes.string,
    email: PropTypes.string,
    phone: PropTypes.string,
    profileImageUrl: PropTypes.string,
    employmentStatus: PropTypes.string,
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
      preferredName: PropTypes.string,
    }),
  }).isRequired,
  onClick: PropTypes.func,
  compact: PropTypes.bool,
};

EmployeeCard.defaultProps = {
  onClick: null,
  compact: false,
};

export default EmployeeCard;

