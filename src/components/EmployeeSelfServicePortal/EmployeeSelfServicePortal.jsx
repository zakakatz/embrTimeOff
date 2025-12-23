/**
 * Employee Self-Service Portal Main Interface
 * 
 * Provides employees with secure access to their personal information
 * through a self-service portal with role-based permissions.
 */

import React, { useState, useEffect, useMemo } from 'react';
import styles from './EmployeeSelfServicePortal.module.css';

/**
 * Permission indicator component
 */
function PermissionBadge({ canEdit, canView }) {
  if (!canView) {
    return (
      <span className={styles.permissionBadgeHidden}>
        🔒 Hidden
      </span>
    );
  }
  
  if (canEdit) {
    return (
      <span className={styles.permissionBadgeEditable}>
        ✏️ Editable
      </span>
    );
  }
  
  return (
    <span className={styles.permissionBadgeReadOnly}>
      👁️ View only
    </span>
  );
}

/**
 * Profile field component with permission enforcement
 */
function ProfileField({ 
  label, 
  value, 
  fieldKey,
  canEdit, 
  canView, 
  isEditing, 
  onChange,
  type = 'text',
  helpText,
}) {
  if (!canView) {
    return null;
  }
  
  return (
    <div className={styles.fieldContainer}>
      <div className={styles.fieldHeader}>
        <label className={styles.fieldLabel}>{label}</label>
        <PermissionBadge canEdit={canEdit} canView={canView} />
      </div>
      
      {isEditing && canEdit ? (
        <input
          type={type}
          value={value || ''}
          onChange={(e) => onChange(fieldKey, e.target.value)}
          className={styles.fieldInput}
        />
      ) : (
        <div className={styles.fieldValue}>
          {value || <span className={styles.emptyValue}>Not set</span>}
        </div>
      )}
      
      {helpText && (
        <p className={styles.fieldHelp}>{helpText}</p>
      )}
    </div>
  );
}

/**
 * Dashboard card component
 */
function DashboardCard({ title, icon, children, actions }) {
  return (
    <div className={styles.dashboardCard}>
      <div className={styles.cardHeader}>
        <span className={styles.cardIcon}>{icon}</span>
        <h3 className={styles.cardTitle}>{title}</h3>
      </div>
      <div className={styles.cardContent}>
        {children}
      </div>
      {actions && (
        <div className={styles.cardActions}>
          {actions}
        </div>
      )}
    </div>
  );
}

/**
 * Action item component
 */
function ActionItem({ title, description, dueDate, priority, onAction }) {
  return (
    <div className={`${styles.actionItem} ${styles[`priority${priority}`]}`}>
      <div className={styles.actionContent}>
        <h4 className={styles.actionTitle}>{title}</h4>
        <p className={styles.actionDescription}>{description}</p>
        {dueDate && (
          <span className={styles.actionDue}>Due: {dueDate}</span>
        )}
      </div>
      <button 
        className={styles.actionButton}
        onClick={onAction}
        aria-label={`Take action on ${title}`}
      >
        →
      </button>
    </div>
  );
}

/**
 * Main Employee Self-Service Portal Component
 */
export default function EmployeeSelfServicePortal({ 
  employeeId,
  onProfileUpdate,
  onNavigate,
}) {
  // State
  const [employee, setEmployee] = useState(null);
  const [permissions, setPermissions] = useState({});
  const [isEditing, setIsEditing] = useState(false);
  const [editedFields, setEditedFields] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Mock data - would come from API
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Mock employee data
        setEmployee({
          id: employeeId || 1,
          employeeId: 'EMP001',
          firstName: 'John',
          lastName: 'Smith',
          preferredName: 'Johnny',
          email: 'john.smith@company.com',
          phone: '+1-555-0100',
          mobilePhone: '+1-555-0101',
          jobTitle: 'Senior Software Engineer',
          department: 'Engineering',
          location: 'San Francisco HQ',
          manager: 'Jane Doe',
          hireDate: '2020-03-15',
          address: '123 Main St, San Francisco, CA 94105',
          emergencyContact: 'Mary Smith - +1-555-0199',
          profilePhoto: null,
        });
        
        // Mock permissions
        setPermissions({
          firstName: { canView: true, canEdit: false },
          lastName: { canView: true, canEdit: false },
          preferredName: { canView: true, canEdit: true },
          email: { canView: true, canEdit: false },
          phone: { canView: true, canEdit: true },
          mobilePhone: { canView: true, canEdit: true },
          jobTitle: { canView: true, canEdit: false },
          department: { canView: true, canEdit: false },
          location: { canView: true, canEdit: false },
          manager: { canView: true, canEdit: false },
          hireDate: { canView: true, canEdit: false },
          address: { canView: true, canEdit: true },
          emergencyContact: { canView: true, canEdit: true },
          salary: { canView: false, canEdit: false },
        });
        
        setError(null);
      } catch (err) {
        setError('Failed to load profile data');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, [employeeId]);
  
  // Dashboard data
  const dashboardData = useMemo(() => ({
    upcomingTimeOff: [
      { id: 1, type: 'Vacation', startDate: '2025-01-15', endDate: '2025-01-20', status: 'approved' },
      { id: 2, type: 'Personal', startDate: '2025-02-01', endDate: '2025-02-01', status: 'pending' },
    ],
    recentChanges: [
      { id: 1, field: 'Phone Number', date: '2024-11-28', status: 'completed' },
      { id: 2, field: 'Emergency Contact', date: '2024-11-25', status: 'completed' },
    ],
    pendingActions: [
      { id: 1, title: 'Complete Annual Review', description: 'Self-assessment due', dueDate: '2025-01-10', priority: 'High' },
      { id: 2, title: 'Update Emergency Contact', description: 'Verification required', dueDate: '2025-01-05', priority: 'Medium' },
    ],
    timeOffBalance: {
      vacation: { used: 10, available: 5, total: 15 },
      sick: { used: 2, available: 8, total: 10 },
      personal: { used: 1, available: 2, total: 3 },
    },
  }), []);
  
  // Count editable fields
  const editableFieldsCount = useMemo(() => {
    return Object.values(permissions).filter(p => p.canEdit).length;
  }, [permissions]);
  
  // Handle field change
  const handleFieldChange = (fieldKey, value) => {
    setEditedFields(prev => ({
      ...prev,
      [fieldKey]: value,
    }));
  };
  
  // Handle save
  const handleSave = async () => {
    try {
      // In real implementation, call API
      console.log('Saving changes:', editedFields);
      
      // Update local state
      setEmployee(prev => ({
        ...prev,
        ...editedFields,
      }));
      
      setIsEditing(false);
      setEditedFields({});
      
      if (onProfileUpdate) {
        onProfileUpdate(editedFields);
      }
    } catch (err) {
      setError('Failed to save changes');
    }
  };
  
  // Handle cancel
  const handleCancel = () => {
    setIsEditing(false);
    setEditedFields({});
  };
  
  // Get current value (edited or original)
  const getValue = (fieldKey) => {
    return editedFields[fieldKey] !== undefined 
      ? editedFields[fieldKey] 
      : employee?.[fieldKey];
  };
  
  // Render loading state
  if (isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>Loading your profile...</p>
      </div>
    );
  }
  
  // Render error state
  if (error) {
    return (
      <div className={styles.errorContainer}>
        <span className={styles.errorIcon}>⚠️</span>
        <p>{error}</p>
        <button onClick={() => window.location.reload()} className={styles.retryButton}>
          Try Again
        </button>
      </div>
    );
  }
  
  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <div className={styles.profileSummary}>
            <div className={styles.avatar}>
              {employee?.profilePhoto ? (
                <img src={employee.profilePhoto} alt="Profile" />
              ) : (
                <span>{employee?.firstName?.[0]}{employee?.lastName?.[0]}</span>
              )}
            </div>
            <div className={styles.headerInfo}>
              <h1 className={styles.employeeName}>
                {employee?.firstName} {employee?.lastName}
                {employee?.preferredName && (
                  <span className={styles.preferredName}>({employee.preferredName})</span>
                )}
              </h1>
              <p className={styles.jobInfo}>
                {employee?.jobTitle} • {employee?.department}
              </p>
              <p className={styles.employeeId}>
                Employee ID: {employee?.employeeId}
              </p>
            </div>
          </div>
          
          <div className={styles.headerActions}>
            {isEditing ? (
              <>
                <button 
                  className={styles.cancelButton}
                  onClick={handleCancel}
                >
                  Cancel
                </button>
                <button 
                  className={styles.saveButton}
                  onClick={handleSave}
                  disabled={Object.keys(editedFields).length === 0}
                >
                  Save Changes
                </button>
              </>
            ) : (
              <button 
                className={styles.editButton}
                onClick={() => setIsEditing(true)}
                disabled={editableFieldsCount === 0}
              >
                ✏️ Edit Profile
              </button>
            )}
          </div>
        </div>
        
        {/* Permission Notice */}
        <div className={styles.permissionNotice}>
          <span className={styles.noticeIcon}>ℹ️</span>
          <span>
            You can edit {editableFieldsCount} field(s). Fields marked "View only" require HR assistance to update.
          </span>
        </div>
      </header>
      
      {/* Navigation Tabs */}
      <nav className={styles.tabNav}>
        <button 
          className={`${styles.tab} ${activeTab === 'overview' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'profile' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          My Profile
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'timeoff' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('timeoff')}
        >
          Time Off
        </button>
      </nav>
      
      {/* Main Content */}
      <main className={styles.main}>
        {activeTab === 'overview' && (
          <div className={styles.dashboard}>
            {/* Time Off Balance */}
            <DashboardCard title="Time Off Balance" icon="🏖️">
              <div className={styles.balanceGrid}>
                {Object.entries(dashboardData.timeOffBalance).map(([type, balance]) => (
                  <div key={type} className={styles.balanceItem}>
                    <span className={styles.balanceType}>
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </span>
                    <div className={styles.balanceBar}>
                      <div 
                        className={styles.balanceUsed}
                        style={{ width: `${(balance.used / balance.total) * 100}%` }}
                      />
                    </div>
                    <span className={styles.balanceNumbers}>
                      {balance.available} days remaining
                    </span>
                  </div>
                ))}
              </div>
            </DashboardCard>
            
            {/* Upcoming Time Off */}
            <DashboardCard 
              title="Upcoming Time Off" 
              icon="📅"
              actions={
                <button className={styles.linkButton}>Request Time Off →</button>
              }
            >
              {dashboardData.upcomingTimeOff.length > 0 ? (
                <ul className={styles.eventList}>
                  {dashboardData.upcomingTimeOff.map(item => (
                    <li key={item.id} className={styles.eventItem}>
                      <span className={styles.eventType}>{item.type}</span>
                      <span className={styles.eventDates}>
                        {item.startDate} - {item.endDate}
                      </span>
                      <span className={`${styles.eventStatus} ${styles[item.status]}`}>
                        {item.status}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={styles.emptyMessage}>No upcoming time off scheduled</p>
              )}
            </DashboardCard>
            
            {/* Pending Actions */}
            <DashboardCard title="Action Items" icon="📋">
              {dashboardData.pendingActions.length > 0 ? (
                <div className={styles.actionList}>
                  {dashboardData.pendingActions.map(action => (
                    <ActionItem
                      key={action.id}
                      title={action.title}
                      description={action.description}
                      dueDate={action.dueDate}
                      priority={action.priority}
                      onAction={() => console.log('Action clicked:', action.id)}
                    />
                  ))}
                </div>
              ) : (
                <p className={styles.emptyMessage}>No pending actions</p>
              )}
            </DashboardCard>
            
            {/* Recent Changes */}
            <DashboardCard title="Recent Profile Changes" icon="📝">
              {dashboardData.recentChanges.length > 0 ? (
                <ul className={styles.changeList}>
                  {dashboardData.recentChanges.map(change => (
                    <li key={change.id} className={styles.changeItem}>
                      <span className={styles.changeField}>{change.field}</span>
                      <span className={styles.changeDate}>{change.date}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={styles.emptyMessage}>No recent changes</p>
              )}
            </DashboardCard>
          </div>
        )}
        
        {activeTab === 'profile' && (
          <div className={styles.profileSection}>
            {/* Personal Information */}
            <section className={styles.profileGroup}>
              <h2 className={styles.groupTitle}>Personal Information</h2>
              <div className={styles.fieldsGrid}>
                <ProfileField
                  label="First Name"
                  value={getValue('firstName')}
                  fieldKey="firstName"
                  canEdit={permissions.firstName?.canEdit}
                  canView={permissions.firstName?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
                <ProfileField
                  label="Last Name"
                  value={getValue('lastName')}
                  fieldKey="lastName"
                  canEdit={permissions.lastName?.canEdit}
                  canView={permissions.lastName?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
                <ProfileField
                  label="Preferred Name"
                  value={getValue('preferredName')}
                  fieldKey="preferredName"
                  canEdit={permissions.preferredName?.canEdit}
                  canView={permissions.preferredName?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                  helpText="This name will be used in day-to-day communications"
                />
              </div>
            </section>
            
            {/* Contact Information */}
            <section className={styles.profileGroup}>
              <h2 className={styles.groupTitle}>Contact Information</h2>
              <div className={styles.fieldsGrid}>
                <ProfileField
                  label="Email"
                  value={getValue('email')}
                  fieldKey="email"
                  canEdit={permissions.email?.canEdit}
                  canView={permissions.email?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                  type="email"
                />
                <ProfileField
                  label="Phone"
                  value={getValue('phone')}
                  fieldKey="phone"
                  canEdit={permissions.phone?.canEdit}
                  canView={permissions.phone?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                  type="tel"
                />
                <ProfileField
                  label="Mobile Phone"
                  value={getValue('mobilePhone')}
                  fieldKey="mobilePhone"
                  canEdit={permissions.mobilePhone?.canEdit}
                  canView={permissions.mobilePhone?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                  type="tel"
                />
                <ProfileField
                  label="Address"
                  value={getValue('address')}
                  fieldKey="address"
                  canEdit={permissions.address?.canEdit}
                  canView={permissions.address?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
              </div>
            </section>
            
            {/* Employment Information */}
            <section className={styles.profileGroup}>
              <h2 className={styles.groupTitle}>Employment Information</h2>
              <div className={styles.fieldsGrid}>
                <ProfileField
                  label="Job Title"
                  value={getValue('jobTitle')}
                  fieldKey="jobTitle"
                  canEdit={permissions.jobTitle?.canEdit}
                  canView={permissions.jobTitle?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
                <ProfileField
                  label="Department"
                  value={getValue('department')}
                  fieldKey="department"
                  canEdit={permissions.department?.canEdit}
                  canView={permissions.department?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
                <ProfileField
                  label="Location"
                  value={getValue('location')}
                  fieldKey="location"
                  canEdit={permissions.location?.canEdit}
                  canView={permissions.location?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
                <ProfileField
                  label="Manager"
                  value={getValue('manager')}
                  fieldKey="manager"
                  canEdit={permissions.manager?.canEdit}
                  canView={permissions.manager?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                />
                <ProfileField
                  label="Hire Date"
                  value={getValue('hireDate')}
                  fieldKey="hireDate"
                  canEdit={permissions.hireDate?.canEdit}
                  canView={permissions.hireDate?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                  type="date"
                />
              </div>
            </section>
            
            {/* Emergency Contact */}
            <section className={styles.profileGroup}>
              <h2 className={styles.groupTitle}>Emergency Contact</h2>
              <div className={styles.fieldsGrid}>
                <ProfileField
                  label="Emergency Contact"
                  value={getValue('emergencyContact')}
                  fieldKey="emergencyContact"
                  canEdit={permissions.emergencyContact?.canEdit}
                  canView={permissions.emergencyContact?.canView}
                  isEditing={isEditing}
                  onChange={handleFieldChange}
                  helpText="Include name and phone number"
                />
              </div>
            </section>
            
            {/* Help Section */}
            <div className={styles.helpSection}>
              <h3 className={styles.helpTitle}>Need to update locked fields?</h3>
              <p className={styles.helpText}>
                Some fields like your name, email, and employment details require HR assistance to modify.
                Contact HR through the Help Desk or submit a request.
              </p>
              <button className={styles.helpButton}>
                Contact HR →
              </button>
            </div>
          </div>
        )}
        
        {activeTab === 'timeoff' && (
          <div className={styles.timeOffSection}>
            <p className={styles.comingSoon}>
              Time Off management interface coming soon...
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

