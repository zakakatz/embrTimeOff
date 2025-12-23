/**
 * FormSelect - Reusable select/dropdown component with React Hook Form integration
 * 
 * Supports single and multiple selection
 */

import React, { forwardRef } from 'react';
import { FormField } from './FormField';
import styles from './FormComponents.module.css';

/**
 * FormSelect component
 * @param {Object} props
 * @param {string} props.name - Field name
 * @param {string} props.label - Field label
 * @param {Array} props.options - Array of options { value, label, disabled? }
 * @param {string} props.placeholder - Placeholder text (for empty option)
 * @param {boolean} props.required - Whether field is required
 * @param {boolean} props.disabled - Whether field is disabled
 * @param {boolean} props.multiple - Enable multiple selection
 * @param {string} props.error - Error message
 * @param {string} props.helperText - Helper text
 * @param {string} props.size - Input size (small, medium, large)
 * @param {string} props.className - Additional CSS class
 * @param {Function} props.onChange - Change handler
 * @param {Function} props.onBlur - Blur handler
 */
export const FormSelect = forwardRef(({
  name,
  label,
  options = [],
  placeholder = 'Select an option...',
  required = false,
  disabled = false,
  multiple = false,
  error,
  helperText,
  size = 'medium',
  className = '',
  value,
  onChange,
  onBlur,
  ...rest
}, ref) => {
  const sizeClass = {
    small: styles.inputSmall,
    medium: '',
    large: styles.inputLarge,
  }[size];
  
  return (
    <FormField
      label={label}
      name={name}
      error={error}
      required={required}
      helperText={helperText}
    >
      <select
        ref={ref}
        id={name}
        name={name}
        disabled={disabled}
        multiple={multiple}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        className={`
          ${styles.select}
          ${sizeClass}
          ${multiple ? styles.selectMultiple : ''}
          ${className}
        `}
        aria-invalid={!!error}
        aria-describedby={error ? `${name}-error` : helperText ? `${name}-helper` : undefined}
        {...rest}
      >
        {!multiple && placeholder && (
          <option value="" disabled={required}>
            {placeholder}
          </option>
        )}
        
        {options.map((option) => {
          // Handle grouped options
          if (option.options) {
            return (
              <optgroup key={option.label} label={option.label}>
                {option.options.map((groupOption) => (
                  <option
                    key={groupOption.value}
                    value={groupOption.value}
                    disabled={groupOption.disabled}
                  >
                    {groupOption.label}
                  </option>
                ))}
              </optgroup>
            );
          }
          
          // Handle regular options
          return (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </option>
          );
        })}
      </select>
    </FormField>
  );
});

FormSelect.displayName = 'FormSelect';

export default FormSelect;

