/**
 * CompensationData Component
 * 
 * Displays compensation information with role-based visibility.
 * Sensitive fields are masked by default.
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import styles from '../EmployeeProfileView.module.css';

function SensitiveFieldValue({ label, value, isVisible, canReveal }) {
  const [revealed, setRevealed] = useState(false);

  if (!isVisible) return null;

  const formattedValue = typeof value === 'number' 
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
    : value;

  return (
    <div className={styles.fieldGroup}>
      <dt className={styles.fieldLabel}>{label}</dt>
      <dd className={styles.fieldValue}>
        {revealed ? formattedValue : '••••••••'}
        {canReveal && (
          <button
            type="button"
            className={styles.revealButton}
            onClick={() => setRevealed(!revealed)}
            aria-label={revealed ? `Hide ${label}` : `Reveal ${label}`}
          >
            {revealed ? 'Hide' : 'Show'}
          </button>
        )}
      </dd>
    </div>
  );
}

export function CompensationData({ employee, fieldPermissions }) {
  const canView = (field) => fieldPermissions?.[field]?.canView !== false;
  const canReveal = (field) => fieldPermissions?.[field]?.canReveal === true;

  return (
    <section aria-labelledby="compensation-heading">
      <h2 id="compensation-heading" className={styles.sectionTitle}>
        Compensation
      </h2>
      
      <div className={styles.sensitiveNotice} role="alert">
        <span className={styles.noticeIcon} aria-hidden="true">🔒</span>
        <p>Compensation information is sensitive and access is logged.</p>
      </div>

      <dl className={styles.fieldGrid}>
        <SensitiveFieldValue
          label="Annual Salary"
          value={employee.salary}
          isVisible={canView('salary')}
          canReveal={canReveal('salary')}
        />
        <SensitiveFieldValue
          label="Hourly Rate"
          value={employee.hourlyRate}
          isVisible={canView('hourlyRate')}
          canReveal={canReveal('hourlyRate')}
        />
        <div className={styles.fieldGroup}>
          <dt className={styles.fieldLabel}>Pay Frequency</dt>
          <dd className={styles.fieldValue}>
            {employee.payFrequency || '—'}
          </dd>
        </div>
        <div className={styles.fieldGroup}>
          <dt className={styles.fieldLabel}>Currency</dt>
          <dd className={styles.fieldValue}>
            {employee.currency || 'USD'}
          </dd>
        </div>
      </dl>

      {canView('benefits') && (
        <>
          <h3 className={styles.subsectionTitle}>Benefits</h3>
          <dl className={styles.fieldGrid}>
            <div className={styles.fieldGroup}>
              <dt className={styles.fieldLabel}>Health Insurance</dt>
              <dd className={styles.fieldValue}>
                {employee.healthInsurancePlan || '—'}
              </dd>
            </div>
            <div className={styles.fieldGroup}>
              <dt className={styles.fieldLabel}>Retirement Plan</dt>
              <dd className={styles.fieldValue}>
                {employee.retirementPlan || '—'}
              </dd>
            </div>
            <div className={styles.fieldGroup}>
              <dt className={styles.fieldLabel}>PTO Balance</dt>
              <dd className={styles.fieldValue}>
                {employee.ptoBalance !== undefined ? `${employee.ptoBalance} hours` : '—'}
              </dd>
            </div>
          </dl>
        </>
      )}
    </section>
  );
}

CompensationData.propTypes = {
  employee: PropTypes.shape({
    salary: PropTypes.number,
    hourlyRate: PropTypes.number,
    payFrequency: PropTypes.string,
    currency: PropTypes.string,
    healthInsurancePlan: PropTypes.string,
    retirementPlan: PropTypes.string,
    ptoBalance: PropTypes.number,
  }).isRequired,
  fieldPermissions: PropTypes.object,
};

CompensationData.defaultProps = {
  fieldPermissions: {},
};

export default CompensationData;

