/**
 * DynamicFieldArray - Component for managing arrays of form fields
 * 
 * Allows adding/removing items dynamically with validation
 */

import React from 'react';
import styles from './FormComponents.module.css';

/**
 * DynamicFieldArray component
 * @param {Object} props
 * @param {string} props.name - Field array name
 * @param {string} props.label - Label for the field array
 * @param {Array} props.fields - Array of current field values
 * @param {Function} props.onAdd - Handler for adding new item
 * @param {Function} props.onRemove - Handler for removing item by index
 * @param {Function} props.renderField - Render function for each field (item, index) => JSX
 * @param {number} props.minItems - Minimum number of items
 * @param {number} props.maxItems - Maximum number of items
 * @param {string} props.addButtonText - Text for add button
 * @param {Object} props.defaultValue - Default value for new items
 * @param {boolean} props.disabled - Disable add/remove functionality
 * @param {string} props.error - Error message for the array
 */
export const DynamicFieldArray = ({
  name,
  label,
  fields = [],
  onAdd,
  onRemove,
  renderField,
  minItems = 0,
  maxItems = Infinity,
  addButtonText = 'Add Item',
  defaultValue = {},
  disabled = false,
  error,
  className = '',
}) => {
  const canAdd = !disabled && fields.length < maxItems;
  const canRemove = !disabled && fields.length > minItems;
  
  const handleAdd = () => {
    if (canAdd && onAdd) {
      onAdd(defaultValue);
    }
  };
  
  const handleRemove = (index) => {
    if (canRemove && onRemove) {
      onRemove(index);
    }
  };
  
  return (
    <div className={`${styles.formField} ${className}`}>
      {label && (
        <label className={styles.label}>
          {label}
        </label>
      )}
      
      <div className={styles.inputWrapper}>
        {fields.map((field, index) => (
          <div key={field.id || index} className={styles.dynamicFieldRow}>
            {renderField(field, index)}
            
            {canRemove && (
              <button
                type="button"
                onClick={() => handleRemove(index)}
                className={styles.removeFieldButton}
                aria-label={`Remove item ${index + 1}`}
                disabled={disabled}
              >
                <RemoveIcon />
              </button>
            )}
          </div>
        ))}
        
        {canAdd && (
          <button
            type="button"
            onClick={handleAdd}
            className={styles.addFieldButton}
            disabled={disabled}
          >
            <AddIcon />
            {addButtonText}
          </button>
        )}
        
        {error && (
          <span className={styles.errorText} role="alert">
            {error}
          </span>
        )}
      </div>
    </div>
  );
};

// Simple SVG icons
const RemoveIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const AddIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

export default DynamicFieldArray;

