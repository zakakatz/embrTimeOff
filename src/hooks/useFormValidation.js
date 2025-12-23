/**
 * useFormValidation - Custom hook for form validation
 * 
 * Features:
 * - Field-level validation
 * - Real-time validation
 * - Custom validation rules
 * - Async validation support
 */

import { useState, useCallback, useMemo, useRef } from 'react';

/**
 * Common validation patterns
 */
export const ValidationPatterns = {
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  phone: /^\+?[\d\s-()]{10,}$/,
  postalCode: /^[\d\w\s-]{3,10}$/,
  url: /^https?:\/\/.+/,
  ssn: /^\d{3}-\d{2}-\d{4}$/,
  date: /^\d{4}-\d{2}-\d{2}$/,
  alphanumeric: /^[a-zA-Z0-9]+$/,
  numeric: /^\d+$/,
  alpha: /^[a-zA-Z]+$/,
};

/**
 * Built-in validation rules
 */
export const ValidationRules = {
  required: (value, message = 'This field is required') => {
    if (value === undefined || value === null || value === '') return message;
    if (Array.isArray(value) && value.length === 0) return message;
    return null;
  },
  
  minLength: (min, message) => (value) => {
    if (!value) return null;
    if (value.length < min) {
      return message || `Must be at least ${min} characters`;
    }
    return null;
  },
  
  maxLength: (max, message) => (value) => {
    if (!value) return null;
    if (value.length > max) {
      return message || `Must be no more than ${max} characters`;
    }
    return null;
  },
  
  min: (min, message) => (value) => {
    if (value === undefined || value === null || value === '') return null;
    if (Number(value) < min) {
      return message || `Must be at least ${min}`;
    }
    return null;
  },
  
  max: (max, message) => (value) => {
    if (value === undefined || value === null || value === '') return null;
    if (Number(value) > max) {
      return message || `Must be no more than ${max}`;
    }
    return null;
  },
  
  pattern: (regex, message = 'Invalid format') => (value) => {
    if (!value) return null;
    if (!regex.test(value)) return message;
    return null;
  },
  
  email: (message = 'Invalid email address') => (value) => {
    if (!value) return null;
    if (!ValidationPatterns.email.test(value)) return message;
    return null;
  },
  
  phone: (message = 'Invalid phone number') => (value) => {
    if (!value) return null;
    if (!ValidationPatterns.phone.test(value)) return message;
    return null;
  },
  
  url: (message = 'Invalid URL') => (value) => {
    if (!value) return null;
    if (!ValidationPatterns.url.test(value)) return message;
    return null;
  },
  
  match: (fieldName, message) => (value, allValues) => {
    if (!value) return null;
    if (value !== allValues[fieldName]) {
      return message || `Must match ${fieldName}`;
    }
    return null;
  },
  
  custom: (validator) => validator,
};

/**
 * Compose multiple validators
 */
export const composeValidators = (...validators) => (value, allValues) => {
  for (const validator of validators) {
    const error = validator(value, allValues);
    if (error) return error;
  }
  return null;
};

/**
 * Custom hook for form validation
 * @param {Object} options Configuration options
 * @param {Object} options.schema Validation schema for fields
 * @param {Object} options.initialValues Initial form values
 * @param {string} options.mode Validation mode ('onChange', 'onBlur', 'onSubmit')
 * @param {boolean} options.validateOnMount Validate on mount
 * @returns {Object} Validation state and handlers
 */
export const useFormValidation = ({
  schema = {},
  initialValues = {},
  mode = 'onBlur',
  validateOnMount = false,
} = {}) => {
  // State
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isValidating, setIsValidating] = useState(false);
  const [isValid, setIsValid] = useState(true);
  
  // Refs
  const schemaRef = useRef(schema);
  schemaRef.current = schema;
  
  // Validate single field
  const validateField = useCallback(async (field, value, allValues = values) => {
    const fieldSchema = schemaRef.current[field];
    
    if (!fieldSchema) return null;
    
    const validators = Array.isArray(fieldSchema) ? fieldSchema : [fieldSchema];
    
    for (const validator of validators) {
      try {
        const error = await validator(value, allValues);
        if (error) return error;
      } catch (e) {
        return e.message || 'Validation error';
      }
    }
    
    return null;
  }, [values]);
  
  // Validate all fields
  const validateAll = useCallback(async (valuesToValidate = values) => {
    setIsValidating(true);
    const newErrors = {};
    
    for (const field of Object.keys(schemaRef.current)) {
      const error = await validateField(field, valuesToValidate[field], valuesToValidate);
      if (error) {
        newErrors[field] = error;
      }
    }
    
    setErrors(newErrors);
    setIsValidating(false);
    
    const valid = Object.keys(newErrors).length === 0;
    setIsValid(valid);
    
    return { isValid: valid, errors: newErrors };
  }, [values, validateField]);
  
  // Set field value
  const setValue = useCallback(async (field, value) => {
    const newValues = { ...values, [field]: value };
    setValues(newValues);
    
    // Validate on change if mode is onChange
    if (mode === 'onChange' || (touched[field] && mode === 'onBlur')) {
      const error = await validateField(field, value, newValues);
      setErrors((prev) => {
        if (error) {
          return { ...prev, [field]: error };
        }
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
    
    return newValues;
  }, [values, mode, touched, validateField]);
  
  // Set multiple values
  const setMultipleValues = useCallback((newValues) => {
    setValues((prev) => ({ ...prev, ...newValues }));
  }, []);
  
  // Handle blur
  const handleBlur = useCallback(async (field) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    
    if (mode === 'onBlur') {
      const error = await validateField(field, values[field]);
      setErrors((prev) => {
        if (error) {
          return { ...prev, [field]: error };
        }
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  }, [mode, values, validateField]);
  
  // Clear field error
  const clearError = useCallback((field) => {
    setErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[field];
      return newErrors;
    });
  }, []);
  
  // Clear all errors
  const clearAllErrors = useCallback(() => {
    setErrors({});
  }, []);
  
  // Set field error manually
  const setError = useCallback((field, error) => {
    setErrors((prev) => ({ ...prev, [field]: error }));
  }, []);
  
  // Reset form
  const reset = useCallback((newInitialValues = initialValues) => {
    setValues(newInitialValues);
    setErrors({});
    setTouched({});
    setIsValid(true);
  }, [initialValues]);
  
  // Check if field has error
  const hasError = useCallback((field) => {
    return touched[field] && !!errors[field];
  }, [touched, errors]);
  
  // Get field props (for spreading onto input)
  const getFieldProps = useCallback((field) => ({
    name: field,
    value: values[field] ?? '',
    onChange: (e) => {
      const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
      setValue(field, value);
    },
    onBlur: () => handleBlur(field),
    error: touched[field] ? errors[field] : undefined,
  }), [values, touched, errors, setValue, handleBlur]);
  
  // Computed state
  const isDirty = useMemo(() => {
    return JSON.stringify(values) !== JSON.stringify(initialValues);
  }, [values, initialValues]);
  
  const touchedFields = useMemo(() => {
    return Object.keys(touched).filter((k) => touched[k]);
  }, [touched]);
  
  const errorFields = useMemo(() => {
    return Object.keys(errors);
  }, [errors]);
  
  return {
    // State
    values,
    errors,
    touched,
    isValidating,
    isValid,
    isDirty,
    
    // Computed
    touchedFields,
    errorFields,
    
    // Actions
    setValue,
    setMultipleValues,
    setError,
    clearError,
    clearAllErrors,
    handleBlur,
    validateField,
    validateAll,
    reset,
    
    // Utilities
    hasError,
    getFieldProps,
  };
};

export default useFormValidation;

