/**
 * FormInput - Reusable input component with React Hook Form integration
 * 
 * Supports text, email, password, number, date, and other input types
 */

import React, { forwardRef } from 'react';
import { FormField } from './FormField';
import styles from './FormComponents.module.css';

/**
 * FormInput component
 * @param {Object} props
 * @param {string} props.name - Field name
 * @param {string} props.label - Field label
 * @param {string} props.type - Input type (text, email, password, number, date, etc.)
 * @param {string} props.placeholder - Placeholder text
 * @param {boolean} props.required - Whether field is required
 * @param {boolean} props.disabled - Whether field is disabled
 * @param {string} props.error - Error message
 * @param {string} props.helperText - Helper text
 * @param {string} props.size - Input size (small, medium, large)
 * @param {string} props.prefix - Text or element to show before input
 * @param {string} props.suffix - Text or element to show after input
 * @param {number} props.maxLength - Maximum character length
 * @param {boolean} props.showCharCount - Show character counter
 * @param {string} props.className - Additional CSS class
 * @param {Function} props.onChange - Change handler
 * @param {Function} props.onBlur - Blur handler
 */
export const FormInput = forwardRef(({
  name,
  label,
  type = 'text',
  placeholder,
  required = false,
  disabled = false,
  error,
  helperText,
  size = 'medium',
  prefix,
  suffix,
  maxLength,
  showCharCount = false,
  className = '',
  value = '',
  onChange,
  onBlur,
  ...rest
}, ref) => {
  const sizeClass = {
    small: styles.inputSmall,
    medium: '',
    large: styles.inputLarge,
  }[size];
  
  const currentLength = value?.toString().length || 0;
  const isNearLimit = maxLength && currentLength >= maxLength * 0.9;
  const isAtLimit = maxLength && currentLength >= maxLength;
  
  const inputElement = (
    <input
      ref={ref}
      id={name}
      name={name}
      type={type}
      placeholder={placeholder}
      disabled={disabled}
      maxLength={maxLength}
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      className={`${styles.input} ${sizeClass} ${className}`}
      aria-invalid={!!error}
      aria-describedby={error ? `${name}-error` : helperText ? `${name}-helper` : undefined}
      {...rest}
    />
  );
  
  const hasAddons = prefix || suffix;
  
  return (
    <FormField
      label={label}
      name={name}
      error={error}
      required={required}
      helperText={!showCharCount ? helperText : undefined}
    >
      {hasAddons ? (
        <div className={styles.inputGroup}>
          {prefix && <span className={styles.inputPrefix}>{prefix}</span>}
          {inputElement}
          {suffix && <span className={styles.inputSuffix}>{suffix}</span>}
        </div>
      ) : (
        inputElement
      )}
      
      {showCharCount && maxLength && (
        <div className={styles.characterCounter + (
          isAtLimit ? ` ${styles.error}` : 
          isNearLimit ? ` ${styles.warning}` : ''
        )}>
          {currentLength} / {maxLength}
        </div>
      )}
      
      {showCharCount && helperText && (
        <span className={styles.helperText}>{helperText}</span>
      )}
    </FormField>
  );
});

FormInput.displayName = 'FormInput';

export default FormInput;

