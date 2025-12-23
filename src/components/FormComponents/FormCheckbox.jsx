/**
 * FormCheckbox - Reusable checkbox component with React Hook Form integration
 * 
 * Supports single checkbox and checkbox groups
 */

import React, { forwardRef } from 'react';
import { FormField } from './FormField';
import styles from './FormComponents.module.css';

/**
 * FormCheckbox component (single checkbox)
 * @param {Object} props
 * @param {string} props.name - Field name
 * @param {string} props.label - Checkbox label
 * @param {string} props.description - Additional description text
 * @param {boolean} props.required - Whether field is required
 * @param {boolean} props.disabled - Whether field is disabled
 * @param {string} props.error - Error message
 * @param {string} props.className - Additional CSS class
 * @param {boolean} props.checked - Controlled checked state
 * @param {Function} props.onChange - Change handler
 * @param {Function} props.onBlur - Blur handler
 */
export const FormCheckbox = forwardRef(({
  name,
  label,
  description,
  required = false,
  disabled = false,
  error,
  className = '',
  checked,
  onChange,
  onBlur,
  ...rest
}, ref) => {
  return (
    <div className={`${styles.formField} ${error ? styles.hasError : ''} ${className}`}>
      <label className={styles.checkboxWrapper}>
        <input
          ref={ref}
          type="checkbox"
          id={name}
          name={name}
          disabled={disabled}
          checked={checked}
          onChange={onChange}
          onBlur={onBlur}
          className={styles.checkbox}
          aria-invalid={!!error}
          aria-describedby={error ? `${name}-error` : undefined}
          {...rest}
        />
        <div>
          <span className={styles.checkboxLabel}>
            {label}
            {required && <span className={styles.required}>*</span>}
          </span>
          {description && (
            <p className={styles.checkboxDescription}>{description}</p>
          )}
        </div>
      </label>
      
      {error && (
        <span className={styles.errorText} role="alert">
          {error}
        </span>
      )}
    </div>
  );
});

FormCheckbox.displayName = 'FormCheckbox';

/**
 * FormCheckboxGroup - Group of checkboxes
 * @param {Object} props
 * @param {string} props.name - Field name
 * @param {string} props.label - Group label
 * @param {Array} props.options - Array of options { value, label, description?, disabled? }
 * @param {boolean} props.required - Whether at least one selection is required
 * @param {string} props.error - Error message
 * @param {string} props.helperText - Helper text
 * @param {boolean} props.horizontal - Display checkboxes horizontally
 * @param {Array} props.value - Array of selected values
 * @param {Function} props.onChange - Change handler
 */
export const FormCheckboxGroup = forwardRef(({
  name,
  label,
  options = [],
  required = false,
  error,
  helperText,
  horizontal = false,
  value = [],
  onChange,
  className = '',
  ...rest
}, ref) => {
  const handleChange = (optionValue, checked) => {
    if (onChange) {
      if (checked) {
        onChange([...value, optionValue]);
      } else {
        onChange(value.filter((v) => v !== optionValue));
      }
    }
  };
  
  return (
    <FormField
      label={label}
      name={name}
      error={error}
      required={required}
      helperText={helperText}
    >
      <div 
        className={`${styles.checkboxGroup} ${horizontal ? styles.horizontal : ''} ${className}`}
        role="group"
        aria-labelledby={`${name}-label`}
      >
        {options.map((option, index) => (
          <label
            key={option.value}
            className={styles.checkboxWrapper}
          >
            <input
              ref={index === 0 ? ref : undefined}
              type="checkbox"
              name={`${name}[]`}
              value={option.value}
              disabled={option.disabled}
              checked={value.includes(option.value)}
              onChange={(e) => handleChange(option.value, e.target.checked)}
              className={styles.checkbox}
              {...rest}
            />
            <div>
              <span className={styles.checkboxLabel}>{option.label}</span>
              {option.description && (
                <p className={styles.checkboxDescription}>{option.description}</p>
              )}
            </div>
          </label>
        ))}
      </div>
    </FormField>
  );
});

FormCheckboxGroup.displayName = 'FormCheckboxGroup';

export default FormCheckbox;

