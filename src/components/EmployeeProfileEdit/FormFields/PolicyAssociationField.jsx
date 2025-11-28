/**
 * PolicyAssociationField Component
 * 
 * Displays and manages policy associations for an employee.
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { profileService } from '../../../services/profileService';
import styles from '../EmployeeProfileEdit.module.css';

export function PolicyAssociationField({ employeeId, disabled }) {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchPolicies() {
      try {
        const data = await profileService.getEmployeePolicies(employeeId);
        setPolicies(data);
      } catch (err) {
        setError('Failed to load policies');
      } finally {
        setLoading(false);
      }
    }

    if (employeeId) {
      fetchPolicies();
    }
  }, [employeeId]);

  if (loading) {
    return (
      <div className={styles.fieldGroup}>
        <label className={styles.fieldLabel}>Assigned Policies</label>
        <div className={styles.loadingPolicies}>Loading policies...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.fieldGroup}>
        <label className={styles.fieldLabel}>Assigned Policies</label>
        <div className={styles.policyError}>{error}</div>
      </div>
    );
  }

  return (
    <div className={`${styles.fieldGroup} ${styles.fullWidth}`}>
      <label className={styles.fieldLabel}>Assigned Policies</label>
      
      {policies.length === 0 ? (
        <p className={styles.noPolicies}>No policies assigned.</p>
      ) : (
        <ul className={styles.policyList}>
          {policies.map((policy) => (
            <li key={policy.id} className={styles.policyItem}>
              <div className={styles.policyInfo}>
                <span className={styles.policyName}>{policy.name}</span>
                <span className={styles.policyType}>{policy.type}</span>
              </div>
              <span
                className={`${styles.policyStatus} ${
                  policy.isActive ? styles.active : styles.inactive
                }`}
              >
                {policy.isActive ? 'Active' : 'Inactive'}
              </span>
            </li>
          ))}
        </ul>
      )}

      {!disabled && (
        <button
          type="button"
          className={styles.managePoliciesButton}
          onClick={() => {
            // Open policy management modal
            console.log('Manage policies clicked');
          }}
        >
          Manage Policies
        </button>
      )}
    </div>
  );
}

PolicyAssociationField.propTypes = {
  employeeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  disabled: PropTypes.bool,
};

PolicyAssociationField.defaultProps = {
  disabled: false,
};

export default PolicyAssociationField;

