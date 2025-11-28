/**
 * EmergencyContacts Component
 * 
 * Displays emergency contact information with role-based visibility.
 */

import React from 'react';
import PropTypes from 'prop-types';
import styles from '../EmployeeProfileView.module.css';

export function EmergencyContacts({ employee, fieldPermissions }) {
  const canView = (field) => fieldPermissions?.[field]?.canView !== false;
  const contacts = employee.emergencyContacts || [];

  if (!canView('emergencyContacts')) {
    return (
      <section aria-labelledby="emergency-contacts-heading">
        <h2 id="emergency-contacts-heading" className={styles.sectionTitle}>
          Emergency Contacts
        </h2>
        <p className={styles.restrictedMessage}>
          You do not have permission to view emergency contacts.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="emergency-contacts-heading">
      <h2 id="emergency-contacts-heading" className={styles.sectionTitle}>
        Emergency Contacts
      </h2>

      {contacts.length === 0 ? (
        <p className={styles.emptyMessage}>No emergency contacts on file.</p>
      ) : (
        <ul className={styles.contactList}>
          {contacts.map((contact, index) => (
            <li key={contact.id || index} className={styles.contactCard}>
              <div className={styles.contactHeader}>
                <h3 className={styles.contactName}>{contact.name}</h3>
                {contact.isPrimary && (
                  <span className={styles.primaryBadge}>Primary</span>
                )}
              </div>
              <dl className={styles.contactDetails}>
                <div className={styles.contactField}>
                  <dt>Relationship</dt>
                  <dd>{contact.relationship || '—'}</dd>
                </div>
                <div className={styles.contactField}>
                  <dt>Phone</dt>
                  <dd>
                    <a href={`tel:${contact.phoneNumber}`}>
                      {contact.phoneNumber || '—'}
                    </a>
                  </dd>
                </div>
                <div className={styles.contactField}>
                  <dt>Email</dt>
                  <dd>
                    {contact.email ? (
                      <a href={`mailto:${contact.email}`}>{contact.email}</a>
                    ) : (
                      '—'
                    )}
                  </dd>
                </div>
                {contact.address && (
                  <div className={styles.contactField}>
                    <dt>Address</dt>
                    <dd>{contact.address}</dd>
                  </div>
                )}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

EmergencyContacts.propTypes = {
  employee: PropTypes.shape({
    emergencyContacts: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        name: PropTypes.string.isRequired,
        relationship: PropTypes.string,
        phoneNumber: PropTypes.string,
        email: PropTypes.string,
        address: PropTypes.string,
        isPrimary: PropTypes.bool,
      })
    ),
  }).isRequired,
  fieldPermissions: PropTypes.object,
};

EmergencyContacts.defaultProps = {
  fieldPermissions: {},
};

export default EmergencyContacts;

