/**
 * EmployeeProfileEdit Component
 * 
 * Form-based interface for editing employee profiles with
 * dynamic fields, real-time validation, and approval workflows.
 */

import React, { useState, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useEmployeeProfileData } from '../../hooks/useEmployeeProfileData';
import { usePermissions } from '../../hooks/usePermissions';
import { profileService } from '../../services/profileService';
import { validateField, validateForm } from '../../utils/validation';
import { logAuditEvent } from '../../utils/auditTrailIntegration';
import DynamicFormField from './FormFields/DynamicFormField';
import ManagerAssignmentField from './FormFields/ManagerAssignmentField';
import PolicyAssociationField from './FormFields/PolicyAssociationField';
import ApprovalWorkflowModal from '../common/ApprovalWorkflowModal';
import styles from './EmployeeProfileEdit.module.css';

const FORM_SECTIONS = [
  { id: 'personal', title: 'Personal Information' },
  { id: 'contact', title: 'Contact Information' },
  { id: 'employment', title: 'Employment Details' },
  { id: 'organization', title: 'Organization' },
];

export function EmployeeProfileEdit({ employeeId, onSave, onCancel }) {
  const { employee, loading, error } = useEmployeeProfileData(employeeId);
  const { getEditableFields } = usePermissions();
  
  const [formData, setFormData] = useState({});
  const [originalData, setOriginalData] = useState({});
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [pendingChanges, setPendingChanges] = useState(null);
  const [activeSection, setActiveSection] = useState('personal');

  // Initialize form data when employee loads
  useEffect(() => {
    if (employee) {
      setFormData(employee);
      setOriginalData(employee);
    }
  }, [employee]);

  const handleFieldChange = useCallback((fieldName, value) => {
    setFormData((prev) => ({
      ...prev,
      [fieldName]: value,
    }));

    // Validate field on change
    const fieldError = validateField(fieldName, value);
    setErrors((prev) => ({
      ...prev,
      [fieldName]: fieldError,
    }));
  }, []);

  const handleFieldBlur = useCallback((fieldName) => {
    setTouched((prev) => ({
      ...prev,
      [fieldName]: true,
    }));

    // Validate on blur
    const fieldError = validateField(fieldName, formData[fieldName]);
    setErrors((prev) => ({
      ...prev,
      [fieldName]: fieldError,
    }));
  }, [formData]);

  const getChangedFields = useCallback(() => {
    const changes = {};
    Object.keys(formData).forEach((key) => {
      if (JSON.stringify(formData[key]) !== JSON.stringify(originalData[key])) {
        changes[key] = {
          previous: originalData[key],
          current: formData[key],
        };
      }
    });
    return changes;
  }, [formData, originalData]);

  const checkSensitiveFields = useCallback((changes) => {
    const sensitiveFields = ['salary', 'hourlyRate', 'managerId', 'departmentId'];
    return Object.keys(changes).some((field) => sensitiveFields.includes(field));
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();

    // Validate entire form
    const formErrors = validateForm(formData);
    if (Object.keys(formErrors).length > 0) {
      setErrors(formErrors);
      // Mark all fields as touched to show errors
      const allTouched = Object.keys(formData).reduce((acc, key) => {
        acc[key] = true;
        return acc;
      }, {});
      setTouched(allTouched);
      return;
    }

    const changes = getChangedFields();
    if (Object.keys(changes).length === 0) {
      onCancel?.();
      return;
    }

    // Check if approval is required for sensitive fields
    if (checkSensitiveFields(changes)) {
      setPendingChanges(changes);
      setShowApprovalModal(true);
      return;
    }

    await submitChanges(changes);
  };

  const submitChanges = async (changes, approvalData = null) => {
    setSubmitting(true);

    try {
      // Check for conflicts
      const conflictCheck = await profileService.checkConflicts(employeeId, changes);
      if (conflictCheck.hasConflicts) {
        setErrors((prev) => ({
          ...prev,
          _form: `Conflict detected: ${conflictCheck.message}`,
        }));
        return;
      }

      // Submit changes
      const result = await profileService.updateEmployee(employeeId, formData, approvalData);

      // Log audit trail
      await logAuditEvent({
        action: 'profile_updated',
        employeeId,
        changes,
        approvalId: result.approvalId,
      });

      onSave?.(result);
    } catch (err) {
      setErrors((prev) => ({
        ...prev,
        _form: err.message || 'Failed to save changes. Please try again.',
      }));
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprovalSubmit = async (approvalData) => {
    setShowApprovalModal(false);
    await submitChanges(pendingChanges, approvalData);
  };

  const editableFields = getEditableFields();

  if (loading) {
    return (
      <div className={styles.container} role="status" aria-live="polite">
        <div className={styles.loading}>Loading profile...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container} role="alert">
        <div className={styles.error}>{error.message}</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Edit Profile</h1>
        <p className={styles.subtitle}>
          {employee?.firstName} {employee?.lastName}
        </p>
      </header>

      <form onSubmit={handleSubmit} className={styles.form} noValidate>
        {errors._form && (
          <div className={styles.formError} role="alert">
            {errors._form}
          </div>
        )}

        {/* Section Navigation */}
        <nav className={styles.sectionNav} aria-label="Form sections">
          {FORM_SECTIONS.map((section) => (
            <button
              key={section.id}
              type="button"
              className={`${styles.sectionButton} ${activeSection === section.id ? styles.activeSection : ''}`}
              onClick={() => setActiveSection(section.id)}
            >
              {section.title}
            </button>
          ))}
        </nav>

        {/* Personal Information Section */}
        {activeSection === 'personal' && (
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>Personal Information</legend>
            
            <div className={styles.fieldGrid}>
              <DynamicFormField
                name="firstName"
                label="First Name"
                type="text"
                value={formData.firstName || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.firstName ? errors.firstName : null}
                required
                disabled={!editableFields.includes('firstName')}
              />
              <DynamicFormField
                name="middleName"
                label="Middle Name"
                type="text"
                value={formData.middleName || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.middleName ? errors.middleName : null}
                disabled={!editableFields.includes('middleName')}
              />
              <DynamicFormField
                name="lastName"
                label="Last Name"
                type="text"
                value={formData.lastName || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.lastName ? errors.lastName : null}
                required
                disabled={!editableFields.includes('lastName')}
              />
              <DynamicFormField
                name="preferredName"
                label="Preferred Name"
                type="text"
                value={formData.preferredName || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.preferredName ? errors.preferredName : null}
                disabled={!editableFields.includes('preferredName')}
              />
              <DynamicFormField
                name="dateOfBirth"
                label="Date of Birth"
                type="date"
                value={formData.dateOfBirth || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.dateOfBirth ? errors.dateOfBirth : null}
                disabled={!editableFields.includes('dateOfBirth')}
              />
              <DynamicFormField
                name="gender"
                label="Gender"
                type="select"
                value={formData.gender || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.gender ? errors.gender : null}
                options={[
                  { value: '', label: 'Select...' },
                  { value: 'male', label: 'Male' },
                  { value: 'female', label: 'Female' },
                  { value: 'non-binary', label: 'Non-binary' },
                  { value: 'prefer-not-to-say', label: 'Prefer not to say' },
                ]}
                disabled={!editableFields.includes('gender')}
              />
            </div>
          </fieldset>
        )}

        {/* Contact Information Section */}
        {activeSection === 'contact' && (
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>Contact Information</legend>
            
            <div className={styles.fieldGrid}>
              <DynamicFormField
                name="email"
                label="Work Email"
                type="email"
                value={formData.email || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.email ? errors.email : null}
                required
                disabled={!editableFields.includes('email')}
              />
              <DynamicFormField
                name="personalEmail"
                label="Personal Email"
                type="email"
                value={formData.personalEmail || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.personalEmail ? errors.personalEmail : null}
                disabled={!editableFields.includes('personalEmail')}
              />
              <DynamicFormField
                name="phoneNumber"
                label="Phone Number"
                type="tel"
                value={formData.phoneNumber || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.phoneNumber ? errors.phoneNumber : null}
                disabled={!editableFields.includes('phoneNumber')}
              />
              <DynamicFormField
                name="mobileNumber"
                label="Mobile Number"
                type="tel"
                value={formData.mobileNumber || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.mobileNumber ? errors.mobileNumber : null}
                disabled={!editableFields.includes('mobileNumber')}
              />
            </div>

            <h3 className={styles.subheading}>Address</h3>
            <div className={styles.fieldGrid}>
              <DynamicFormField
                name="addressLine1"
                label="Street Address"
                type="text"
                value={formData.addressLine1 || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.addressLine1 ? errors.addressLine1 : null}
                disabled={!editableFields.includes('addressLine1')}
                fullWidth
              />
              <DynamicFormField
                name="city"
                label="City"
                type="text"
                value={formData.city || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.city ? errors.city : null}
                disabled={!editableFields.includes('city')}
              />
              <DynamicFormField
                name="stateProvince"
                label="State/Province"
                type="text"
                value={formData.stateProvince || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.stateProvince ? errors.stateProvince : null}
                disabled={!editableFields.includes('stateProvince')}
              />
              <DynamicFormField
                name="postalCode"
                label="Postal Code"
                type="text"
                value={formData.postalCode || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.postalCode ? errors.postalCode : null}
                disabled={!editableFields.includes('postalCode')}
              />
              <DynamicFormField
                name="country"
                label="Country"
                type="text"
                value={formData.country || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.country ? errors.country : null}
                disabled={!editableFields.includes('country')}
              />
            </div>
          </fieldset>
        )}

        {/* Employment Section */}
        {activeSection === 'employment' && (
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>Employment Details</legend>
            
            <div className={styles.fieldGrid}>
              <DynamicFormField
                name="jobTitle"
                label="Job Title"
                type="text"
                value={formData.jobTitle || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.jobTitle ? errors.jobTitle : null}
                disabled={!editableFields.includes('jobTitle')}
              />
              <DynamicFormField
                name="employmentType"
                label="Employment Type"
                type="select"
                value={formData.employmentType || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.employmentType ? errors.employmentType : null}
                options={[
                  { value: '', label: 'Select...' },
                  { value: 'full_time', label: 'Full Time' },
                  { value: 'part_time', label: 'Part Time' },
                  { value: 'contractor', label: 'Contractor' },
                  { value: 'intern', label: 'Intern' },
                ]}
                disabled={!editableFields.includes('employmentType')}
              />
              <DynamicFormField
                name="hireDate"
                label="Hire Date"
                type="date"
                value={formData.hireDate || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.hireDate ? errors.hireDate : null}
                required
                disabled={!editableFields.includes('hireDate')}
              />
            </div>
          </fieldset>
        )}

        {/* Organization Section */}
        {activeSection === 'organization' && (
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>Organization</legend>
            
            <div className={styles.fieldGrid}>
              <ManagerAssignmentField
                value={formData.managerId}
                currentManager={formData.manager}
                onChange={(value) => handleFieldChange('managerId', value)}
                disabled={!editableFields.includes('managerId')}
                error={touched.managerId ? errors.managerId : null}
              />
              <DynamicFormField
                name="departmentId"
                label="Department"
                type="select"
                value={formData.departmentId || ''}
                onChange={handleFieldChange}
                onBlur={handleFieldBlur}
                error={touched.departmentId ? errors.departmentId : null}
                options={[{ value: '', label: 'Select department...' }]}
                disabled={!editableFields.includes('departmentId')}
              />
              <PolicyAssociationField
                employeeId={employeeId}
                disabled={!editableFields.includes('policies')}
              />
            </div>
          </fieldset>
        )}

        {/* Form Actions */}
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.cancelButton}
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className={styles.saveButton}
            disabled={submitting}
          >
            {submitting ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>

      {/* Approval Modal */}
      {showApprovalModal && (
        <ApprovalWorkflowModal
          isOpen={showApprovalModal}
          onClose={() => setShowApprovalModal(false)}
          onSubmit={handleApprovalSubmit}
          changes={pendingChanges}
          employeeId={employeeId}
        />
      )}
    </div>
  );
}

EmployeeProfileEdit.propTypes = {
  employeeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  onSave: PropTypes.func,
  onCancel: PropTypes.func,
};

EmployeeProfileEdit.defaultProps = {
  onSave: () => {},
  onCancel: () => {},
};

export default EmployeeProfileEdit;

