/**
 * EmployeeProfileView Component
 * 
 * Displays employee information with role-based field visibility,
 * tabbed navigation, and contextual actions.
 */

import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useEmployeeProfileData } from '../../hooks/useEmployeeProfileData';
import { usePermissions } from '../../hooks/usePermissions';
import PersonalInformation from './ProfileSections/PersonalInformation';
import JobDetails from './ProfileSections/JobDetails';
import CompensationData from './ProfileSections/CompensationData';
import EmergencyContacts from './ProfileSections/EmergencyContacts';
import OrganizationalRelationships from './ProfileSections/OrganizationalRelationships';
import ProfileActions from './ProfileActions';
import styles from './EmployeeProfileView.module.css';

const TABS = [
  { id: 'personal', label: 'Personal Information', permission: 'view_personal' },
  { id: 'job', label: 'Job Details', permission: 'view_job' },
  { id: 'compensation', label: 'Compensation', permission: 'view_compensation' },
  { id: 'emergency', label: 'Emergency Contacts', permission: 'view_emergency' },
  { id: 'organization', label: 'Organization', permission: 'view_organization' },
];

export function EmployeeProfileView({ employeeId, onEditClick }) {
  const [activeTab, setActiveTab] = useState('personal');
  const { employee, loading, error, recentChanges, refetch } = useEmployeeProfileData(employeeId);
  const { hasPermission, getFieldPermissions } = usePermissions();

  const handleTabChange = useCallback((tabId) => {
    setActiveTab(tabId);
  }, []);

  const handleKeyDown = useCallback((event, tabId) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setActiveTab(tabId);
    }
  }, []);

  // Filter tabs based on permissions
  const visibleTabs = TABS.filter(tab => hasPermission(tab.permission));

  if (loading) {
    return (
      <div className={styles.container} role="status" aria-live="polite">
        <div className={styles.loading}>
          <span className={styles.spinner} aria-hidden="true" />
          Loading employee profile...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container} role="alert">
        <div className={styles.error}>
          <h2>Error Loading Profile</h2>
          <p>{error.message}</p>
          <button onClick={refetch} className={styles.retryButton}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!employee) {
    return (
      <div className={styles.container} role="alert">
        <div className={styles.notFound}>
          <h2>Employee Not Found</h2>
          <p>The requested employee profile could not be found.</p>
        </div>
      </div>
    );
  }

  const renderTabContent = () => {
    const fieldPermissions = getFieldPermissions(activeTab);

    switch (activeTab) {
      case 'personal':
        return (
          <PersonalInformation
            employee={employee}
            fieldPermissions={fieldPermissions}
          />
        );
      case 'job':
        return (
          <JobDetails
            employee={employee}
            fieldPermissions={fieldPermissions}
          />
        );
      case 'compensation':
        return (
          <CompensationData
            employee={employee}
            fieldPermissions={fieldPermissions}
          />
        );
      case 'emergency':
        return (
          <EmergencyContacts
            employee={employee}
            fieldPermissions={fieldPermissions}
          />
        );
      case 'organization':
        return (
          <OrganizationalRelationships
            employee={employee}
            fieldPermissions={fieldPermissions}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className={styles.container}>
      {/* Profile Header */}
      <header className={styles.header}>
        <div className={styles.profileImage}>
          {employee.profileImageUrl ? (
            <img
              src={employee.profileImageUrl}
              alt={`${employee.firstName} ${employee.lastName}`}
            />
          ) : (
            <div className={styles.avatarPlaceholder} aria-hidden="true">
              {employee.firstName?.[0]}{employee.lastName?.[0]}
            </div>
          )}
        </div>
        <div className={styles.profileInfo}>
          <h1 className={styles.employeeName}>
            {employee.preferredName || employee.firstName} {employee.lastName}
          </h1>
          <p className={styles.jobTitle}>{employee.jobTitle}</p>
          <p className={styles.department}>{employee.department?.name}</p>
          <span className={styles.employeeId}>ID: {employee.employeeId}</span>
        </div>
        <ProfileActions
          employeeId={employeeId}
          onEditClick={onEditClick}
          hasEditPermission={hasPermission('edit_profile')}
        />
      </header>

      {/* Tab Navigation */}
      <nav className={styles.tabNav} role="tablist" aria-label="Profile sections">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            className={`${styles.tab} ${activeTab === tab.id ? styles.activeTab : ''}`}
            onClick={() => handleTabChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Tab Content */}
      <main
        role="tabpanel"
        id={`panel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
        className={styles.tabContent}
      >
        {renderTabContent()}
      </main>

      {/* Recent Activity */}
      {recentChanges && recentChanges.length > 0 && (
        <aside className={styles.activitySummary} aria-label="Recent profile changes">
          <h2 className={styles.activityTitle}>Recent Changes</h2>
          <ul className={styles.activityList}>
            {recentChanges.slice(0, 5).map((change) => (
              <li key={change.id} className={styles.activityItem}>
                <span className={styles.changeField}>{change.fieldName}</span>
                <span className={styles.changeDate}>
                  {new Date(change.timestamp).toLocaleDateString()}
                </span>
                <span className={styles.changeBy}>by {change.changedBy}</span>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}

EmployeeProfileView.propTypes = {
  employeeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  onEditClick: PropTypes.func,
};

EmployeeProfileView.defaultProps = {
  onEditClick: () => {},
};

export default EmployeeProfileView;

