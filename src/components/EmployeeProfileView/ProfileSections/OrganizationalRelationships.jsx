/**
 * OrganizationalRelationships Component
 * 
 * Displays department, manager, and team relationships.
 */

import React from 'react';
import PropTypes from 'prop-types';
import styles from '../EmployeeProfileView.module.css';

export function OrganizationalRelationships({ employee, fieldPermissions }) {
  const canView = (field) => fieldPermissions?.[field]?.canView !== false;

  return (
    <section aria-labelledby="organization-heading">
      <h2 id="organization-heading" className={styles.sectionTitle}>
        Organizational Relationships
      </h2>

      {/* Department Information */}
      {canView('department') && employee.department && (
        <div className={styles.orgSection}>
          <h3 className={styles.subsectionTitle}>Department</h3>
          <dl className={styles.fieldGrid}>
            <div className={styles.fieldGroup}>
              <dt className={styles.fieldLabel}>Department Name</dt>
              <dd className={styles.fieldValue}>{employee.department.name}</dd>
            </div>
            <div className={styles.fieldGroup}>
              <dt className={styles.fieldLabel}>Department Code</dt>
              <dd className={styles.fieldValue}>{employee.department.code}</dd>
            </div>
            {employee.department.description && (
              <div className={styles.fieldGroup}>
                <dt className={styles.fieldLabel}>Description</dt>
                <dd className={styles.fieldValue}>{employee.department.description}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {/* Manager Information */}
      {canView('manager') && (
        <div className={styles.orgSection}>
          <h3 className={styles.subsectionTitle}>Reports To</h3>
          {employee.manager ? (
            <div className={styles.managerCard}>
              <div className={styles.managerAvatar}>
                {employee.manager.profileImageUrl ? (
                  <img
                    src={employee.manager.profileImageUrl}
                    alt={`${employee.manager.firstName} ${employee.manager.lastName}`}
                  />
                ) : (
                  <span aria-hidden="true">
                    {employee.manager.firstName?.[0]}{employee.manager.lastName?.[0]}
                  </span>
                )}
              </div>
              <div className={styles.managerInfo}>
                <p className={styles.managerName}>
                  {employee.manager.preferredName || employee.manager.firstName}{' '}
                  {employee.manager.lastName}
                </p>
                <p className={styles.managerTitle}>{employee.manager.jobTitle}</p>
                <a
                  href={`mailto:${employee.manager.email}`}
                  className={styles.managerEmail}
                >
                  {employee.manager.email}
                </a>
              </div>
            </div>
          ) : (
            <p className={styles.emptyMessage}>No manager assigned.</p>
          )}
        </div>
      )}

      {/* Direct Reports */}
      {canView('directReports') && employee.directReports && employee.directReports.length > 0 && (
        <div className={styles.orgSection}>
          <h3 className={styles.subsectionTitle}>
            Direct Reports ({employee.directReports.length})
          </h3>
          <ul className={styles.reportsList}>
            {employee.directReports.map((report) => (
              <li key={report.id} className={styles.reportItem}>
                <div className={styles.reportAvatar}>
                  {report.firstName?.[0]}{report.lastName?.[0]}
                </div>
                <div className={styles.reportInfo}>
                  <p className={styles.reportName}>
                    {report.preferredName || report.firstName} {report.lastName}
                  </p>
                  <p className={styles.reportTitle}>{report.jobTitle}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Team Members */}
      {canView('teamMembers') && employee.teamMembers && employee.teamMembers.length > 0 && (
        <div className={styles.orgSection}>
          <h3 className={styles.subsectionTitle}>
            Team Members ({employee.teamMembers.length})
          </h3>
          <ul className={styles.reportsList}>
            {employee.teamMembers.map((member) => (
              <li key={member.id} className={styles.reportItem}>
                <div className={styles.reportAvatar}>
                  {member.firstName?.[0]}{member.lastName?.[0]}
                </div>
                <div className={styles.reportInfo}>
                  <p className={styles.reportName}>
                    {member.preferredName || member.firstName} {member.lastName}
                  </p>
                  <p className={styles.reportTitle}>{member.jobTitle}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

OrganizationalRelationships.propTypes = {
  employee: PropTypes.shape({
    department: PropTypes.shape({
      name: PropTypes.string,
      code: PropTypes.string,
      description: PropTypes.string,
    }),
    manager: PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
      firstName: PropTypes.string,
      lastName: PropTypes.string,
      preferredName: PropTypes.string,
      jobTitle: PropTypes.string,
      email: PropTypes.string,
      profileImageUrl: PropTypes.string,
    }),
    directReports: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        firstName: PropTypes.string,
        lastName: PropTypes.string,
        preferredName: PropTypes.string,
        jobTitle: PropTypes.string,
      })
    ),
    teamMembers: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        firstName: PropTypes.string,
        lastName: PropTypes.string,
        preferredName: PropTypes.string,
        jobTitle: PropTypes.string,
      })
    ),
  }).isRequired,
  fieldPermissions: PropTypes.object,
};

OrganizationalRelationships.defaultProps = {
  fieldPermissions: {},
};

export default OrganizationalRelationships;

