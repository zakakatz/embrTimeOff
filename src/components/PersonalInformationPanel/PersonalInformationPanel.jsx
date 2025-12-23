/**
 * PersonalInformationPanel Component
 * 
 * Enhanced personal information panel with field-level permissions,
 * inline editing, real-time validation, and emergency contacts management.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import PropTypes from 'prop-types';
import { validateField, formatDate } from '../../utils/validation';
import styles from './PersonalInformationPanel.module.css';

// Field configuration with metadata
const PERSONAL_FIELDS = [
  { name: 'firstName', label: 'First Name', type: 'text', required: true, category: 'name' },
  { name: 'middleName', label: 'Middle Name', type: 'text', category: 'name' },
  { name: 'lastName', label: 'Last Name', type: 'text', required: true, category: 'name' },
  { name: 'preferredName', label: 'Preferred Name', type: 'text', category: 'name' },
  { name: 'dateOfBirth', label: 'Date of Birth', type: 'date', category: 'personal', sensitive: true },
  { name: 'gender', label: 'Gender', type: 'select', options: ['Male', 'Female', 'Non-binary', 'Prefer not to say'], category: 'personal' },
];

const CONTACT_FIELDS = [
  { name: 'email', label: 'Work Email', type: 'email', required: true, category: 'contact' },
  { name: 'personalEmail', label: 'Personal Email', type: 'email', category: 'contact', sensitive: true },
  { name: 'phoneNumber', label: 'Work Phone', type: 'tel', category: 'contact' },
  { name: 'mobileNumber', label: 'Mobile Number', type: 'tel', category: 'contact' },
];

const ADDRESS_FIELDS = [
  { name: 'addressLine1', label: 'Street Address', type: 'text', category: 'address' },
  { name: 'addressLine2', label: 'Address Line 2', type: 'text', category: 'address' },
  { name: 'city', label: 'City', type: 'text', category: 'address' },
  { name: 'stateProvince', label: 'State/Province', type: 'text', category: 'address' },
  { name: 'postalCode', label: 'Postal Code', type: 'text', category: 'address' },
  { name: 'country', label: 'Country', type: 'text', category: 'address' },
];

// Permission indicator component
function PermissionIndicator({ canEdit, canView, isSensitive }) {
  if (!canView) return null;

  let indicatorClass = styles.permissionIndicator;
  let label = '';
  let icon = '';

  if (!canEdit) {
    indicatorClass += ` ${styles.readOnly}`;
    label = 'Read-only';
    icon = '🔒';
  } else if (isSensitive) {
    indicatorClass += ` ${styles.sensitive}`;
    label = 'Sensitive field';
    icon = '⚠️';
  } else {
    indicatorClass += ` ${styles.editable}`;
    label = 'Editable';
    icon = '✏️';
  }

  return (
    <span className={indicatorClass} title={label} aria-label={label}>
      {icon}
    </span>
  );
}

PermissionIndicator.propTypes = {
  canEdit: PropTypes.bool,
  canView: PropTypes.bool,
  isSensitive: PropTypes.bool,
};

// Editable field component with inline editing
function EditableField({
  field,
  value,
  permission,
  isEditing,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onChange,
  error,
  pendingValue,
}) {
  const { name, label, type, required, options, sensitive } = field;
  const { canView, canEdit, isSensitive } = permission || { canView: true, canEdit: false };

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && type !== 'textarea') {
        onSaveEdit(name);
      } else if (e.key === 'Escape') {
        onCancelEdit(name);
      }
    },
    [name, type, onSaveEdit, onCancelEdit]
  );

  if (!canView) return null;

  const displayValue = useMemo(() => {
    if ((sensitive || isSensitive) && !isEditing) {
      return '••••••••';
    }
    if (type === 'date' && value) {
      return formatDate(value);
    }
    return value || '—';
  }, [value, sensitive, isSensitive, isEditing, type]);

  const currentValue = isEditing ? pendingValue : value;

  return (
    <div
      className={`${styles.fieldContainer} ${error ? styles.hasError : ''} ${isEditing ? styles.editing : ''}`}
      data-field={name}
    >
      <div className={styles.fieldHeader}>
        <label htmlFor={`field-${name}`} className={styles.fieldLabel}>
          {label}
          {required && <span className={styles.required}>*</span>}
        </label>
        <PermissionIndicator canEdit={canEdit} canView={canView} isSensitive={isSensitive || sensitive} />
      </div>

      <div className={styles.fieldContent}>
        {isEditing && canEdit ? (
          <div className={styles.editingWrapper}>
            {type === 'select' ? (
              <select
                id={`field-${name}`}
                value={currentValue || ''}
                onChange={(e) => onChange(name, e.target.value)}
                onKeyDown={handleKeyDown}
                className={`${styles.input} ${styles.select}`}
                aria-describedby={error ? `error-${name}` : undefined}
                aria-invalid={!!error}
                autoFocus
              >
                <option value="">Select...</option>
                {options?.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            ) : type === 'textarea' ? (
              <textarea
                id={`field-${name}`}
                value={currentValue || ''}
                onChange={(e) => onChange(name, e.target.value)}
                onKeyDown={handleKeyDown}
                className={`${styles.input} ${styles.textarea}`}
                rows={3}
                aria-describedby={error ? `error-${name}` : undefined}
                aria-invalid={!!error}
                autoFocus
              />
            ) : (
              <input
                id={`field-${name}`}
                type={type}
                value={currentValue || ''}
                onChange={(e) => onChange(name, e.target.value)}
                onKeyDown={handleKeyDown}
                className={styles.input}
                aria-describedby={error ? `error-${name}` : undefined}
                aria-invalid={!!error}
                autoFocus
              />
            )}

            <div className={styles.editActions}>
              <button
                type="button"
                onClick={() => onSaveEdit(name)}
                className={`${styles.actionBtn} ${styles.saveBtn}`}
                aria-label={`Save ${label}`}
                disabled={!!error}
              >
                ✓
              </button>
              <button
                type="button"
                onClick={() => onCancelEdit(name)}
                className={`${styles.actionBtn} ${styles.cancelBtn}`}
                aria-label={`Cancel editing ${label}`}
              >
                ✕
              </button>
            </div>
          </div>
        ) : (
          <div className={styles.displayWrapper}>
            <span className={styles.fieldValue}>{displayValue}</span>
            {canEdit && (
              <button
                type="button"
                onClick={() => onStartEdit(name)}
                className={styles.editBtn}
                aria-label={`Edit ${label}`}
              >
                Edit
              </button>
            )}
          </div>
        )}

        {error && (
          <div id={`error-${name}`} className={styles.errorMessage} role="alert">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

EditableField.propTypes = {
  field: PropTypes.shape({
    name: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    type: PropTypes.string.isRequired,
    required: PropTypes.bool,
    options: PropTypes.arrayOf(PropTypes.string),
    sensitive: PropTypes.bool,
  }).isRequired,
  value: PropTypes.any,
  permission: PropTypes.shape({
    canView: PropTypes.bool,
    canEdit: PropTypes.bool,
    isSensitive: PropTypes.bool,
  }),
  isEditing: PropTypes.bool,
  onStartEdit: PropTypes.func.isRequired,
  onCancelEdit: PropTypes.func.isRequired,
  onSaveEdit: PropTypes.func.isRequired,
  onChange: PropTypes.func.isRequired,
  error: PropTypes.string,
  pendingValue: PropTypes.any,
};

// Emergency contact component
function EmergencyContactCard({
  contact,
  index,
  canEdit,
  onEdit,
  onDelete,
  isEditing,
  editingContact,
  onSaveContact,
  onCancelContact,
  onContactChange,
  errors,
}) {
  if (isEditing) {
    return (
      <div className={styles.emergencyCard}>
        <div className={styles.emergencyForm}>
          <div className={styles.formRow}>
            <label htmlFor={`contact-name-${index}`}>Name *</label>
            <input
              id={`contact-name-${index}`}
              type="text"
              value={editingContact?.name || ''}
              onChange={(e) => onContactChange(index, 'name', e.target.value)}
              className={`${styles.input} ${errors?.name ? styles.inputError : ''}`}
              autoFocus
            />
            {errors?.name && <span className={styles.errorText}>{errors.name}</span>}
          </div>

          <div className={styles.formRow}>
            <label htmlFor={`contact-relationship-${index}`}>Relationship *</label>
            <select
              id={`contact-relationship-${index}`}
              value={editingContact?.relationship || ''}
              onChange={(e) => onContactChange(index, 'relationship', e.target.value)}
              className={`${styles.input} ${styles.select}`}
            >
              <option value="">Select...</option>
              <option value="Spouse">Spouse</option>
              <option value="Partner">Partner</option>
              <option value="Parent">Parent</option>
              <option value="Sibling">Sibling</option>
              <option value="Child">Child</option>
              <option value="Friend">Friend</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div className={styles.formRow}>
            <label htmlFor={`contact-phone-${index}`}>Phone Number *</label>
            <input
              id={`contact-phone-${index}`}
              type="tel"
              value={editingContact?.phone || ''}
              onChange={(e) => onContactChange(index, 'phone', e.target.value)}
              className={`${styles.input} ${errors?.phone ? styles.inputError : ''}`}
            />
            {errors?.phone && <span className={styles.errorText}>{errors.phone}</span>}
          </div>

          <div className={styles.formRow}>
            <label htmlFor={`contact-email-${index}`}>Email</label>
            <input
              id={`contact-email-${index}`}
              type="email"
              value={editingContact?.email || ''}
              onChange={(e) => onContactChange(index, 'email', e.target.value)}
              className={`${styles.input} ${errors?.email ? styles.inputError : ''}`}
            />
            {errors?.email && <span className={styles.errorText}>{errors.email}</span>}
          </div>

          <div className={styles.formRow}>
            <label htmlFor={`contact-primary-${index}`}>
              <input
                id={`contact-primary-${index}`}
                type="checkbox"
                checked={editingContact?.isPrimary || false}
                onChange={(e) => onContactChange(index, 'isPrimary', e.target.checked)}
              />
              Primary Emergency Contact
            </label>
          </div>

          <div className={styles.contactActions}>
            <button
              type="button"
              onClick={() => onSaveContact(index)}
              className={`${styles.btn} ${styles.btnPrimary}`}
            >
              Save Contact
            </button>
            <button
              type="button"
              onClick={() => onCancelContact(index)}
              className={`${styles.btn} ${styles.btnSecondary}`}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.emergencyCard} ${contact.isPrimary ? styles.primaryContact : ''}`}>
      {contact.isPrimary && <span className={styles.primaryBadge}>Primary</span>}
      <h4 className={styles.contactName}>{contact.name}</h4>
      <p className={styles.contactRelationship}>{contact.relationship}</p>
      <div className={styles.contactDetails}>
        <span className={styles.contactPhone}>📞 {contact.phone}</span>
        {contact.email && <span className={styles.contactEmail}>✉️ {contact.email}</span>}
      </div>
      {canEdit && (
        <div className={styles.contactButtons}>
          <button
            type="button"
            onClick={() => onEdit(index)}
            className={styles.editContactBtn}
            aria-label={`Edit contact ${contact.name}`}
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => onDelete(index)}
            className={styles.deleteContactBtn}
            aria-label={`Delete contact ${contact.name}`}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

EmergencyContactCard.propTypes = {
  contact: PropTypes.shape({
    name: PropTypes.string,
    relationship: PropTypes.string,
    phone: PropTypes.string,
    email: PropTypes.string,
    isPrimary: PropTypes.bool,
  }),
  index: PropTypes.number.isRequired,
  canEdit: PropTypes.bool,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  isEditing: PropTypes.bool,
  editingContact: PropTypes.object,
  onSaveContact: PropTypes.func.isRequired,
  onCancelContact: PropTypes.func.isRequired,
  onContactChange: PropTypes.func.isRequired,
  errors: PropTypes.object,
};

// Main component
export function PersonalInformationPanel({
  employee,
  fieldPermissions,
  onFieldUpdate,
  onEmergencyContactsUpdate,
  isLoading,
}) {
  // State for inline editing
  const [editingFields, setEditingFields] = useState({});
  const [pendingValues, setPendingValues] = useState({});
  const [errors, setErrors] = useState({});
  const [editingContactIndex, setEditingContactIndex] = useState(null);
  const [editingContact, setEditingContact] = useState(null);
  const [contactErrors, setContactErrors] = useState({});
  const [isAddingContact, setIsAddingContact] = useState(false);

  // Reset editing state when employee changes
  useEffect(() => {
    setEditingFields({});
    setPendingValues({});
    setErrors({});
    setEditingContactIndex(null);
    setEditingContact(null);
    setIsAddingContact(false);
  }, [employee?.id]);

  // Permission helpers
  const getPermission = useCallback(
    (fieldName) => {
      return fieldPermissions?.[fieldName] || { canView: true, canEdit: false };
    },
    [fieldPermissions]
  );

  const canEditEmergencyContacts = useMemo(() => {
    return fieldPermissions?.emergencyContacts?.canEdit !== false;
  }, [fieldPermissions]);

  // Field editing handlers
  const handleStartEdit = useCallback(
    (fieldName) => {
      setEditingFields((prev) => ({ ...prev, [fieldName]: true }));
      setPendingValues((prev) => ({
        ...prev,
        [fieldName]: employee[fieldName] || '',
      }));
      setErrors((prev) => ({ ...prev, [fieldName]: null }));
    },
    [employee]
  );

  const handleCancelEdit = useCallback((fieldName) => {
    setEditingFields((prev) => ({ ...prev, [fieldName]: false }));
    setPendingValues((prev) => {
      const next = { ...prev };
      delete next[fieldName];
      return next;
    });
    setErrors((prev) => ({ ...prev, [fieldName]: null }));
  }, []);

  const handleChange = useCallback(
    (fieldName, value) => {
      setPendingValues((prev) => ({ ...prev, [fieldName]: value }));

      // Real-time validation
      const error = validateField(fieldName, value);
      setErrors((prev) => ({ ...prev, [fieldName]: error }));
    },
    []
  );

  const handleSaveEdit = useCallback(
    async (fieldName) => {
      const value = pendingValues[fieldName];
      const error = validateField(fieldName, value);

      if (error) {
        setErrors((prev) => ({ ...prev, [fieldName]: error }));
        return;
      }

      try {
        await onFieldUpdate?.(fieldName, value);
        setEditingFields((prev) => ({ ...prev, [fieldName]: false }));
        setPendingValues((prev) => {
          const next = { ...prev };
          delete next[fieldName];
          return next;
        });
      } catch (err) {
        setErrors((prev) => ({
          ...prev,
          [fieldName]: err.message || 'Failed to save changes',
        }));
      }
    },
    [pendingValues, onFieldUpdate]
  );

  // Emergency contact handlers
  const handleEditContact = useCallback(
    (index) => {
      const contacts = employee.emergencyContacts || [];
      setEditingContactIndex(index);
      setEditingContact({ ...contacts[index] });
      setContactErrors({});
    },
    [employee.emergencyContacts]
  );

  const handleDeleteContact = useCallback(
    async (index) => {
      if (!window.confirm('Are you sure you want to delete this emergency contact?')) {
        return;
      }

      const contacts = [...(employee.emergencyContacts || [])];
      contacts.splice(index, 1);
      await onEmergencyContactsUpdate?.(contacts);
    },
    [employee.emergencyContacts, onEmergencyContactsUpdate]
  );

  const handleContactChange = useCallback((index, field, value) => {
    setEditingContact((prev) => ({
      ...prev,
      [field]: value,
    }));

    // Clear error for this field
    setContactErrors((prev) => ({ ...prev, [field]: null }));
  }, []);

  const validateContact = useCallback((contact) => {
    const errors = {};

    if (!contact.name?.trim()) {
      errors.name = 'Name is required';
    }

    if (!contact.phone?.trim()) {
      errors.phone = 'Phone number is required';
    } else if (!/^\+?[0-9\s\-()]{7,20}$/.test(contact.phone)) {
      errors.phone = 'Please enter a valid phone number';
    }

    if (contact.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email)) {
      errors.email = 'Please enter a valid email address';
    }

    return errors;
  }, []);

  const handleSaveContact = useCallback(
    async (index) => {
      const errors = validateContact(editingContact);

      if (Object.keys(errors).length > 0) {
        setContactErrors(errors);
        return;
      }

      const contacts = [...(employee.emergencyContacts || [])];

      // If this contact is being set as primary, remove primary from others
      if (editingContact.isPrimary) {
        contacts.forEach((c) => {
          c.isPrimary = false;
        });
      }

      if (isAddingContact) {
        contacts.push(editingContact);
      } else {
        contacts[index] = editingContact;
      }

      await onEmergencyContactsUpdate?.(contacts);
      setEditingContactIndex(null);
      setEditingContact(null);
      setIsAddingContact(false);
      setContactErrors({});
    },
    [editingContact, employee.emergencyContacts, isAddingContact, onEmergencyContactsUpdate, validateContact]
  );

  const handleCancelContact = useCallback(() => {
    setEditingContactIndex(null);
    setEditingContact(null);
    setIsAddingContact(false);
    setContactErrors({});
  }, []);

  const handleAddContact = useCallback(() => {
    setIsAddingContact(true);
    setEditingContactIndex((employee.emergencyContacts || []).length);
    setEditingContact({
      name: '',
      relationship: '',
      phone: '',
      email: '',
      isPrimary: false,
    });
    setContactErrors({});
  }, [employee.emergencyContacts]);

  // Render field section
  const renderFieldSection = useCallback(
    (fields, title, description) => {
      const visibleFields = fields.filter((f) => getPermission(f.name).canView !== false);

      if (visibleFields.length === 0) return null;

      return (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{title}</h3>
          {description && <p className={styles.sectionDescription}>{description}</p>}
          <div className={styles.fieldsGrid}>
            {visibleFields.map((field) => (
              <EditableField
                key={field.name}
                field={field}
                value={employee[field.name]}
                permission={getPermission(field.name)}
                isEditing={editingFields[field.name]}
                pendingValue={pendingValues[field.name]}
                error={errors[field.name]}
                onStartEdit={handleStartEdit}
                onCancelEdit={handleCancelEdit}
                onSaveEdit={handleSaveEdit}
                onChange={handleChange}
              />
            ))}
          </div>
        </section>
      );
    },
    [
      employee,
      editingFields,
      pendingValues,
      errors,
      getPermission,
      handleStartEdit,
      handleCancelEdit,
      handleSaveEdit,
      handleChange,
    ]
  );

  if (isLoading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.spinner} aria-label="Loading personal information" />
        <p>Loading personal information...</p>
      </div>
    );
  }

  if (!employee) {
    return (
      <div className={styles.emptyState}>
        <p>No employee data available</p>
      </div>
    );
  }

  const emergencyContacts = employee.emergencyContacts || [];

  return (
    <article className={styles.panel} aria-label="Personal Information Panel">
      <header className={styles.panelHeader}>
        <h2 className={styles.panelTitle}>Personal Information</h2>
        <p className={styles.panelSubtitle}>
          View and manage your personal details, contact information, and emergency contacts.
        </p>
      </header>

      <div className={styles.permissionLegend}>
        <span className={styles.legendItem}>
          <span className={`${styles.legendIcon} ${styles.editable}`}>✏️</span> Editable
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.legendIcon} ${styles.readOnly}`}>🔒</span> Read-only
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.legendIcon} ${styles.sensitive}`}>⚠️</span> Sensitive
        </span>
      </div>

      {renderFieldSection(
        PERSONAL_FIELDS,
        'Basic Information',
        'Your name and personal details.'
      )}

      {renderFieldSection(
        CONTACT_FIELDS,
        'Contact Information',
        'Phone numbers and email addresses for work communication.'
      )}

      {renderFieldSection(
        ADDRESS_FIELDS,
        'Address',
        'Your current residential address.'
      )}

      {/* Emergency Contacts Section */}
      {fieldPermissions?.emergencyContacts?.canView !== false && (
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <div>
              <h3 className={styles.sectionTitle}>Emergency Contacts</h3>
              <p className={styles.sectionDescription}>
                People to contact in case of an emergency.
              </p>
            </div>
            {canEditEmergencyContacts && !isAddingContact && (
              <button
                type="button"
                onClick={handleAddContact}
                className={`${styles.btn} ${styles.btnPrimary}`}
                aria-label="Add emergency contact"
              >
                + Add Contact
              </button>
            )}
          </div>

          <div className={styles.emergencyContacts}>
            {emergencyContacts.length === 0 && !isAddingContact ? (
              <p className={styles.noContacts}>No emergency contacts on file.</p>
            ) : (
              emergencyContacts.map((contact, index) => (
                <EmergencyContactCard
                  key={index}
                  contact={contact}
                  index={index}
                  canEdit={canEditEmergencyContacts}
                  onEdit={handleEditContact}
                  onDelete={handleDeleteContact}
                  isEditing={editingContactIndex === index && !isAddingContact}
                  editingContact={editingContactIndex === index ? editingContact : null}
                  onSaveContact={handleSaveContact}
                  onCancelContact={handleCancelContact}
                  onContactChange={handleContactChange}
                  errors={editingContactIndex === index ? contactErrors : {}}
                />
              ))
            )}

            {isAddingContact && (
              <EmergencyContactCard
                contact={{}}
                index={emergencyContacts.length}
                canEdit={true}
                onEdit={() => {}}
                onDelete={() => {}}
                isEditing={true}
                editingContact={editingContact}
                onSaveContact={handleSaveContact}
                onCancelContact={handleCancelContact}
                onContactChange={handleContactChange}
                errors={contactErrors}
              />
            )}
          </div>
        </section>
      )}
    </article>
  );
}

PersonalInformationPanel.propTypes = {
  employee: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
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
    emergencyContacts: PropTypes.arrayOf(
      PropTypes.shape({
        name: PropTypes.string,
        relationship: PropTypes.string,
        phone: PropTypes.string,
        email: PropTypes.string,
        isPrimary: PropTypes.bool,
      })
    ),
  }),
  fieldPermissions: PropTypes.object,
  onFieldUpdate: PropTypes.func,
  onEmergencyContactsUpdate: PropTypes.func,
  isLoading: PropTypes.bool,
};

PersonalInformationPanel.defaultProps = {
  employee: null,
  fieldPermissions: {},
  onFieldUpdate: () => {},
  onEmergencyContactsUpdate: () => {},
  isLoading: false,
};

export default PersonalInformationPanel;
