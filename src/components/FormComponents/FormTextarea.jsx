/**
 * FormTextarea - Reusable textarea component with React Hook Form integration
 * 
 * Supports auto-resize, character counting, and various configurations
 */

import React, { forwardRef, useEffect, useRef, useCallback } from 'react';
import { FormField } from './FormField';
import styles from './FormComponents.module.css';

/**
 * FormTextarea component
 * @param {Object} props
 * @param {string} props.name - Field name
 * @param {string} props.label - Field label
 * @param {string} props.placeholder - Placeholder text
 * @param {boolean} props.required - Whether field is required
 * @param {boolean} props.disabled - Whether field is disabled
 * @param {string} props.error - Error message
 * @param {string} props.helperText - Helper text
 * @param {number} props.rows - Number of visible rows
 * @param {number} props.maxLength - Maximum character length
 * @param {boolean} props.showCharCount - Show character counter
 * @param {boolean} props.autoResize - Auto-resize based on content
 * @param {boolean} props.noResize - Disable manual resize
 * @param {string} props.className - Additional CSS class
 * @param {Function} props.onChange - Change handler
 * @param {Function} props.onBlur - Blur handler
 */
export const FormTextarea = forwardRef(({
  name,
  label,
  placeholder,
  required = false,
  disabled = false,
  error,
  helperText,
  rows = 4,
  maxLength,
  showCharCount = false,
  autoResize = false,
  noResize = false,
  className = '',
  value = '',
  onChange,
  onBlur,
  ...rest
}, ref) => {
  const internalRef = useRef(null);
  const textareaRef = ref || internalRef;
  
  const currentLength = value?.toString().length || 0;
  const isNearLimit = maxLength && currentLength >= maxLength * 0.9;
  const isAtLimit = maxLength && currentLength >= maxLength;
  
  // Auto-resize functionality
  const adjustHeight = useCallback(() => {
    if (autoResize && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [autoResize, textareaRef]);
  
  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);
  
  const handleChange = (e) => {
    if (onChange) {
      onChange(e);
    }
    adjustHeight();
  };
  
  return (
    <FormField
      label={label}
      name={name}
      error={error}
      required={required}
      helperText={!showCharCount ? helperText : undefined}
    >
      <textarea
        ref={textareaRef}
        id={name}
        name={name}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        maxLength={maxLength}
        value={value}
        onChange={handleChange}
        onBlur={onBlur}
        className={`
          ${styles.textarea}
          ${noResize ? styles.textareaNoResize : ''}
          ${className}
        `}
        aria-invalid={!!error}
        aria-describedby={error ? `${name}-error` : helperText ? `${name}-helper` : undefined}
        {...rest}
      />
      
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

FormTextarea.displayName = 'FormTextarea';

export default FormTextarea;

