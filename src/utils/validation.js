/**
 * Validation Utilities
 * 
 * Common form validation functions.
 */

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Phone validation regex (flexible international format)
const PHONE_REGEX = /^\+?[0-9\s\-()]{7,20}$/;

/**
 * Validate a single field
 */
export function validateField(fieldName, value) {
  switch (fieldName) {
    case 'firstName':
    case 'lastName':
      if (!value || value.trim().length === 0) {
        return 'This field is required';
      }
      if (value.length > 100) {
        return 'Must be 100 characters or less';
      }
      return null;

    case 'email':
      if (!value || value.trim().length === 0) {
        return 'Email is required';
      }
      if (!EMAIL_REGEX.test(value)) {
        return 'Please enter a valid email address';
      }
      return null;

    case 'personalEmail':
      if (value && !EMAIL_REGEX.test(value)) {
        return 'Please enter a valid email address';
      }
      return null;

    case 'phoneNumber':
    case 'mobileNumber':
      if (value && !PHONE_REGEX.test(value)) {
        return 'Please enter a valid phone number';
      }
      return null;

    case 'hireDate':
      if (!value) {
        return 'Hire date is required';
      }
      const hireDate = new Date(value);
      const today = new Date();
      if (hireDate > today) {
        return 'Hire date cannot be in the future';
      }
      return null;

    case 'dateOfBirth':
      if (value) {
        const dob = new Date(value);
        const now = new Date();
        const age = Math.floor((now - dob) / (365.25 * 24 * 60 * 60 * 1000));
        if (age < 16) {
          return 'Employee must be at least 16 years old';
        }
        if (age > 100) {
          return 'Please enter a valid date of birth';
        }
      }
      return null;

    case 'postalCode':
      if (value && value.length > 20) {
        return 'Postal code must be 20 characters or less';
      }
      return null;

    default:
      return null;
  }
}

/**
 * Validate entire form
 */
export function validateForm(formData) {
  const errors = {};
  const requiredFields = ['firstName', 'lastName', 'email', 'hireDate'];

  requiredFields.forEach((field) => {
    const error = validateField(field, formData[field]);
    if (error) {
      errors[field] = error;
    }
  });

  // Validate all other fields that have values
  Object.keys(formData).forEach((field) => {
    if (!requiredFields.includes(field)) {
      const error = validateField(field, formData[field]);
      if (error) {
        errors[field] = error;
      }
    }
  });

  return errors;
}

/**
 * Format date for display
 */
export function formatDate(dateString) {
  if (!dateString) return null;
  
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}

/**
 * Format currency
 */
export function formatCurrency(amount, currency = 'USD') {
  if (amount === null || amount === undefined) return null;
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount);
}

/**
 * Check if value has changed
 */
export function hasChanged(original, current) {
  return JSON.stringify(original) !== JSON.stringify(current);
}

export default {
  validateField,
  validateForm,
  formatDate,
  formatCurrency,
  hasChanged,
};

