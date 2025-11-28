/**
 * ApprovalWorkflowModal Component
 * 
 * Modal for handling approval workflows for sensitive field modifications.
 */

import React, { useState, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { trapFocus, moveFocusTo } from '../../utils/accessibilityHelpers';
import styles from './ApprovalWorkflowModal.module.css';

export function ApprovalWorkflowModal({
  isOpen,
  onClose,
  onSubmit,
  changes,
  employeeId,
}) {
  const [justification, setJustification] = useState('');
  const [urgency, setUrgency] = useState('normal');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const modalRef = useRef(null);
  const previousActiveElement = useRef(null);

  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = document.activeElement;
      moveFocusTo(modalRef.current);
      
      const cleanup = trapFocus(modalRef.current);
      
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
      
      return () => {
        cleanup();
        document.body.style.overflow = '';
        previousActiveElement.current?.focus();
      };
    }
  }, [isOpen]);

  useEffect(() => {
    function handleEscape(event) {
      if (event.key === 'Escape' && isOpen) {
        onClose();
      }
    }

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!justification.trim()) {
      setError('Please provide a justification for these changes');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await onSubmit({
        justification: justification.trim(),
        urgency,
        requestedAt: new Date().toISOString(),
      });
    } catch (err) {
      setError(err.message || 'Failed to submit approval request');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const changedFields = Object.keys(changes || {});

  return (
    <div
      className={styles.overlay}
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="presentation"
    >
      <div
        ref={modalRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
      >
        <header className={styles.header}>
          <h2 id="modal-title" className={styles.title}>
            Approval Required
          </h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Close modal"
          >
            ×
          </button>
        </header>

        <div className={styles.content}>
          <p className={styles.description}>
            The following changes require manager approval before they can be applied.
          </p>

          <div className={styles.changesSection}>
            <h3 className={styles.changesTitle}>Changes Requiring Approval</h3>
            <ul className={styles.changesList}>
              {changedFields.map((field) => (
                <li key={field} className={styles.changeItem}>
                  <span className={styles.fieldName}>
                    {formatFieldName(field)}
                  </span>
                  <div className={styles.changeValues}>
                    <span className={styles.oldValue}>
                      {formatValue(changes[field].previous)}
                    </span>
                    <span className={styles.arrow}>→</span>
                    <span className={styles.newValue}>
                      {formatValue(changes[field].current)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <form onSubmit={handleSubmit} className={styles.form}>
            {error && (
              <div className={styles.error} role="alert">
                {error}
              </div>
            )}

            <div className={styles.formGroup}>
              <label htmlFor="justification" className={styles.label}>
                Justification <span className={styles.required}>*</span>
              </label>
              <textarea
                id="justification"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                className={styles.textarea}
                placeholder="Please explain why these changes are needed..."
                rows={4}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="urgency" className={styles.label}>
                Urgency Level
              </label>
              <select
                id="urgency"
                value={urgency}
                onChange={(e) => setUrgency(e.target.value)}
                className={styles.select}
              >
                <option value="low">Low - No rush</option>
                <option value="normal">Normal - Within a few days</option>
                <option value="high">High - ASAP</option>
                <option value="urgent">Urgent - Immediate action needed</option>
              </select>
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={styles.submitButton}
                disabled={submitting}
              >
                {submitting ? 'Submitting...' : 'Submit for Approval'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function formatFieldName(field) {
  return field
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

function formatValue(value) {
  if (value === null || value === undefined) return '(empty)';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

ApprovalWorkflowModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  changes: PropTypes.object,
  employeeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

ApprovalWorkflowModal.defaultProps = {
  changes: {},
  employeeId: null,
};

export default ApprovalWorkflowModal;

