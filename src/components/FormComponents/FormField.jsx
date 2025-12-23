/**
 * FormField - Base wrapper component for form fields
 * 
 * Provides consistent layout and error display for all form inputs
 */

import React from 'react';
import styles from './FormComponents.module.css';

/**
 * FormField wrapper component
 * @param {Object} props
 * @param {string} props.label - Field label
 * @param {string} props.name - Field name
 * @param {string} props.error - Error message
 * @param {boolean} props.required - Whether field is required
 * @param {string} props.helperText - Helper text displayed below input
 * @param {string} props.className - Additional CSS class
 * @param {React.ReactNode} props.children - Form input element
 * @param {boolean} props.horizontal - Display label and input horizontally
 */
export const FormField = ({
  label,
  name,
  error,
  required = false,
  helperText,
  className = '',
  children,
  horizontal = false,
}) => {
  const hasError = Boolean(error);
  
  return (
    <div 
      className={`
        ${styles.formField}
        ${horizontal ? styles.horizontal : ''}
        ${hasError ? styles.hasError : ''}
        ${className}
      `}
    >
      {label && (
        <label htmlFor={name} className={styles.label}>
          {label}
          {required && <span className={styles.required}>*</span>}
        </label>
      )}
      
      <div className={styles.inputWrapper}>
        {children}
        
        {helperText && !hasError && (
          <span className={styles.helperText}>{helperText}</span>
        )}
        
        {hasError && (
          <span className={styles.errorText} role="alert">
            {error}
          </span>
        )}
      </div>
    </div>
  );
};

export default FormField;

