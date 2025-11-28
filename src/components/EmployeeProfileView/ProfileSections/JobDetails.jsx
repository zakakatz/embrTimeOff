/**
 * JobDetails Component
 * 
 * Displays job-related information with role-based visibility.
 */

import React from 'react';
import PropTypes from 'prop-types';
import { formatDate } from '../../../utils/validation';
import styles from '../EmployeeProfileView.module.css';

function FieldValue({ label, value, isVisible }) {
  if (!isVisible) return null;

  return (
    <div className={styles.fieldGroup}>
      <dt className={styles.fieldLabel}>{label}</dt>
      <dd className={styles.fieldValue}>{value || '—'}</dd>
    </div>
  );
}

export function JobDetails({ employee, fieldPermissions }) {
  const canView = (field) => fieldPermissions?.[field]?.canView !== false;

  const formatEmploymentType = (type) => {
    const types = {
      full_time: 'Full Time',
      part_time: 'Part Time',
      contractor: 'Contractor',
      intern: 'Intern',
    };
    return types[type] || type;
  };

  const formatStatus = (status) => {
    const statuses = {
      active: 'Active',
      inactive: 'Inactive',
      terminated: 'Terminated',
    };
    return statuses[status] || status;
  };

  return (
    <section aria-labelledby="job-details-heading">
      <h2 id="job-details-heading" className={styles.sectionTitle}>
        Job Details
      </h2>
      
      <dl className={styles.fieldGrid}>
        <FieldValue
          label="Employee ID"
          value={employee.employeeId}
          isVisible={canView('employeeId')}
        />
        <FieldValue
          label="Job Title"
          value={employee.jobTitle}
          isVisible={canView('jobTitle')}
        />
        <FieldValue
          label="Employment Type"
          value={formatEmploymentType(employee.employmentType)}
          isVisible={canView('employmentType')}
        />
        <FieldValue
          label="Employment Status"
          value={formatStatus(employee.employmentStatus)}
          isVisible={canView('employmentStatus')}
        />
        <FieldValue
          label="Hire Date"
          value={formatDate(employee.hireDate)}
          isVisible={canView('hireDate')}
        />
        <FieldValue
          label="Termination Date"
          value={formatDate(employee.terminationDate)}
          isVisible={canView('terminationDate') && employee.terminationDate}
        />
      </dl>

      <h3 className={styles.subsectionTitle}>Work Location</h3>
      <dl className={styles.fieldGrid}>
        <FieldValue
          label="Location"
          value={employee.location?.name}
          isVisible={canView('location')}
        />
        <FieldValue
          label="Location Code"
          value={employee.location?.code}
          isVisible={canView('location')}
        />
        <FieldValue
          label="Timezone"
          value={employee.location?.timezone}
          isVisible={canView('location')}
        />
      </dl>

      <h3 className={styles.subsectionTitle}>Work Schedule</h3>
      <dl className={styles.fieldGrid}>
        <FieldValue
          label="Schedule Name"
          value={employee.workSchedule?.name}
          isVisible={canView('workSchedule')}
        />
        <FieldValue
          label="Hours per Week"
          value={employee.workSchedule?.hoursPerWeek}
          isVisible={canView('workSchedule')}
        />
        <FieldValue
          label="Days per Week"
          value={employee.workSchedule?.daysPerWeek}
          isVisible={canView('workSchedule')}
        />
        <FieldValue
          label="Flexible Schedule"
          value={employee.workSchedule?.isFlexible ? 'Yes' : 'No'}
          isVisible={canView('workSchedule')}
        />
      </dl>
    </section>
  );
}

JobDetails.propTypes = {
  employee: PropTypes.shape({
    employeeId: PropTypes.string,
    jobTitle: PropTypes.string,
    employmentType: PropTypes.string,
    employmentStatus: PropTypes.string,
    hireDate: PropTypes.string,
    terminationDate: PropTypes.string,
    location: PropTypes.shape({
      name: PropTypes.string,
      code: PropTypes.string,
      timezone: PropTypes.string,
    }),
    workSchedule: PropTypes.shape({
      name: PropTypes.string,
      hoursPerWeek: PropTypes.number,
      daysPerWeek: PropTypes.number,
      isFlexible: PropTypes.bool,
    }),
  }).isRequired,
  fieldPermissions: PropTypes.object,
};

JobDetails.defaultProps = {
  fieldPermissions: {},
};

export default JobDetails;

