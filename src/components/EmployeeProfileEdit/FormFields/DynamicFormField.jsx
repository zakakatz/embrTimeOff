/**
 * DynamicFormField Component
 * 
 * Renders form fields dynamically based on field metadata.
 */

import React from 'react';
import PropTypes from 'prop-types';
import { generateAriaDescribedBy } from '../../../utils/accessibilityHelpers';
import styles from '../EmployeeProfileEdit.module.css';

export function DynamicFormField({
  name,
  label,
  type,
  value,
  onChange,
  onBlur,
  error,
  hint,
  required,
  disabled,
  options,
  fullWidth,
  placeholder,
  maxLength,
  min,
  max,
  pattern,
  autoComplete,
}) {
  const inputId = `field-${name}`;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const ariaDescribedBy = generateAriaDescribedBy(error ? errorId : null, hint ? hintId : null);

  const handleChange = (event) => {
    onChange(name, event.target.value);
  };

  const handleBlur = () => {
    onBlur?.(name);
  };

  const renderInput = () => {
    const commonProps = {
      id: inputId,
      name,
      value: value ?? '',
      onChange: handleChange,
      onBlur: handleBlur,
      disabled,
      required,
      'aria-invalid': !!error,
      'aria-describedby': ariaDescribedBy || undefined,
      className: `${styles.fieldInput} ${error ? styles.hasError : ''}`,
    };

    switch (type) {
      case 'select':
        return (
          <select {...commonProps}>
            {options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );

      case 'textarea':
        return (
          <textarea
            {...commonProps}
            placeholder={placeholder}
            maxLength={maxLength}
            rows={4}
          />
        );

      case 'date':
        return (
          <input
            {...commonProps}
            type="date"
            min={min}
            max={max}
          />
        );

      case 'number':
        return (
          <input
            {...commonProps}
            type="number"
            placeholder={placeholder}
            min={min}
            max={max}
            step="any"
          />
        );

      case 'email':
        return (
          <input
            {...commonProps}
            type="email"
            placeholder={placeholder || 'email@example.com'}
            autoComplete={autoComplete || 'email'}
          />
        );

      case 'tel':
        return (
          <input
            {...commonProps}
            type="tel"
            placeholder={placeholder || '+1 (555) 000-0000'}
            autoComplete={autoComplete || 'tel'}
          />
        );

      default:
        return (
          <input
            {...commonProps}
            type={type}
            placeholder={placeholder}
            maxLength={maxLength}
            pattern={pattern}
            autoComplete={autoComplete}
          />
        );
    }
  };

  return (
    <div className={`${styles.fieldGroup} ${fullWidth ? styles.fullWidth : ''}`}>
      <label htmlFor={inputId} className={styles.fieldLabel}>
        {label}
        {required && <span className={styles.required} aria-hidden="true">*</span>}
      </label>
      
      {renderInput()}
      
      {error && (
        <p id={errorId} className={styles.fieldError} role="alert">
          {error}
        </p>
      )}
      
      {hint && !error && (
        <p id={hintId} className={styles.fieldHint}>
          {hint}
        </p>
      )}
    </div>
  );
}

DynamicFormField.propTypes = {
  name: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  type: PropTypes.oneOf([
    'text',
    'email',
    'tel',
    'number',
    'date',
    'select',
    'textarea',
    'password',
  ]),
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  onBlur: PropTypes.func,
  error: PropTypes.string,
  hint: PropTypes.string,
  required: PropTypes.bool,
  disabled: PropTypes.bool,
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
    })
  ),
  fullWidth: PropTypes.bool,
  placeholder: PropTypes.string,
  maxLength: PropTypes.number,
  min: PropTypes.string,
  max: PropTypes.string,
  pattern: PropTypes.string,
  autoComplete: PropTypes.string,
};

DynamicFormField.defaultProps = {
  type: 'text',
  value: '',
  onBlur: () => {},
  error: null,
  hint: null,
  required: false,
  disabled: false,
  options: [],
  fullWidth: false,
  placeholder: '',
  maxLength: undefined,
  min: undefined,
  max: undefined,
  pattern: undefined,
  autoComplete: undefined,
};

export default DynamicFormField;

