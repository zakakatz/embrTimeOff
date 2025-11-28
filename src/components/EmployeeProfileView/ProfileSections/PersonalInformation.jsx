/**
 * PersonalInformation Component
 * 
 * Displays personal information fields with role-based visibility.
 */

import React from 'react';
import PropTypes from 'prop-types';
import { formatDate } from '../../../utils/validation';
import styles from '../EmployeeProfileView.module.css';

function FieldValue({ label, value, isVisible, isSensitive }) {
  if (!isVisible) return null;

  return (
    <div className={styles.fieldGroup}>
      <dt className={styles.fieldLabel}>{label}</dt>
      <dd className={styles.fieldValue}>
        {isSensitive ? '••••••••' : (value || '—')}
      </dd>
    </div>
  );
}

export function PersonalInformation({ employee, fieldPermissions }) {
  const canView = (field) => fieldPermissions?.[field]?.canView !== false;
  const isSensitive = (field) => fieldPermissions?.[field]?.isSensitive === true;

  return (
    <section aria-labelledby="personal-info-heading">
      <h2 id="personal-info-heading" className={styles.sectionTitle}>
        Personal Information
      </h2>
      
      <dl className={styles.fieldGrid}>
        <FieldValue
          label="First Name"
          value={employee.firstName}
          isVisible={canView('firstName')}
        />
        <FieldValue
          label="Middle Name"
          value={employee.middleName}
          isVisible={canView('middleName')}
        />
        <FieldValue
          label="Last Name"
          value={employee.lastName}
          isVisible={canView('lastName')}
        />
        <FieldValue
          label="Preferred Name"
          value={employee.preferredName}
          isVisible={canView('preferredName')}
        />
        <FieldValue
          label="Date of Birth"
          value={formatDate(employee.dateOfBirth)}
          isVisible={canView('dateOfBirth')}
          isSensitive={isSensitive('dateOfBirth')}
        />
        <FieldValue
          label="Gender"
          value={employee.gender}
          isVisible={canView('gender')}
        />
        <FieldValue
          label="Email"
          value={employee.email}
          isVisible={canView('email')}
        />
        <FieldValue
          label="Personal Email"
          value={employee.personalEmail}
          isVisible={canView('personalEmail')}
          isSensitive={isSensitive('personalEmail')}
        />
        <FieldValue
          label="Phone Number"
          value={employee.phoneNumber}
          isVisible={canView('phoneNumber')}
        />
        <FieldValue
          label="Mobile Number"
          value={employee.mobileNumber}
          isVisible={canView('mobileNumber')}
        />
      </dl>

      {canView('address') && (
        <>
          <h3 className={styles.subsectionTitle}>Address</h3>
          <dl className={styles.fieldGrid}>
            <FieldValue
              label="Street Address"
              value={employee.addressLine1}
              isVisible={canView('addressLine1')}
            />
            <FieldValue
              label="Address Line 2"
              value={employee.addressLine2}
              isVisible={canView('addressLine2')}
            />
            <FieldValue
              label="City"
              value={employee.city}
              isVisible={canView('city')}
            />
            <FieldValue
              label="State/Province"
              value={employee.stateProvince}
              isVisible={canView('stateProvince')}
            />
            <FieldValue
              label="Postal Code"
              value={employee.postalCode}
              isVisible={canView('postalCode')}
            />
            <FieldValue
              label="Country"
              value={employee.country}
              isVisible={canView('country')}
            />
          </dl>
        </>
      )}
    </section>
  );
}

PersonalInformation.propTypes = {
  employee: PropTypes.shape({
    firstName: PropTypes.string,
    middleName: PropTypes.string,
    lastName: PropTypes.string,
    preferredName: PropTypes.string,
    dateOfBirth: PropTypes.string,
    gender: PropTypes.string,
    email: PropTypes.string,
    personalEmail: PropTypes.string,
    phoneNumber: PropTypes.string,
    mobileNumber: PropTypes.string,
    addressLine1: PropTypes.string,
    addressLine2: PropTypes.string,
    city: PropTypes.string,
    stateProvince: PropTypes.string,
    postalCode: PropTypes.string,
    country: PropTypes.string,
  }).isRequired,
  fieldPermissions: PropTypes.object,
};

PersonalInformation.defaultProps = {
  fieldPermissions: {},
};

export default PersonalInformation;

