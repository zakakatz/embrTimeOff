/**
 * FormRadioGroup - Reusable radio button group component
 * 
 * Supports vertical and horizontal layouts with descriptions
 */

import React, { forwardRef } from 'react';
import { FormField } from './FormField';
import styles from './FormComponents.module.css';

/**
 * FormRadioGroup component
 * @param {Object} props
 * @param {string} props.name - Field name
 * @param {string} props.label - Group label
 * @param {Array} props.options - Array of options { value, label, description?, disabled? }
 * @param {boolean} props.required - Whether selection is required
 * @param {string} props.error - Error message
 * @param {string} props.helperText - Helper text
 * @param {boolean} props.horizontal - Display radios horizontally
 * @param {string} props.value - Selected value
 * @param {Function} props.onChange - Change handler
 * @param {Function} props.onBlur - Blur handler
 */
export const FormRadioGroup = forwardRef(({
  name,
  label,
  options = [],
  required = false,
  error,
  helperText,
  horizontal = false,
  value,
  onChange,
  onBlur,
  className = '',
  ...rest
}, ref) => {
  return (
    <FormField
      label={label}
      name={name}
      error={error}
      required={required}
      helperText={helperText}
    >
      <div 
        className={`${styles.radioGroup} ${horizontal ? styles.horizontal : ''} ${className}`}
        role="radiogroup"
        aria-labelledby={`${name}-label`}
      >
        {options.map((option, index) => (
          <label
            key={option.value}
            className={styles.radioWrapper}
          >
            <input
              ref={index === 0 ? ref : undefined}
              type="radio"
              name={name}
              value={option.value}
              disabled={option.disabled}
              checked={value === option.value}
              onChange={onChange}
              onBlur={onBlur}
              className={styles.radio}
              aria-invalid={!!error}
              {...rest}
            />
            <div>
              <span className={styles.radioLabel}>{option.label}</span>
              {option.description && (
                <p className={styles.radioDescription}>{option.description}</p>
              )}
            </div>
          </label>
        ))}
      </div>
    </FormField>
  );
});

FormRadioGroup.displayName = 'FormRadioGroup';

export default FormRadioGroup;

