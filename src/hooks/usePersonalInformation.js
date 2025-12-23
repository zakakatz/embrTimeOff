/**
 * usePersonalInformation Hook
 * 
 * Custom hook for managing personal information data with field-level permissions,
 * validation, and update operations.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';

// Field definitions with validation and permission requirements
const FIELD_DEFINITIONS = {
  // Name fields
  firstName: {
    label: 'First Name',
    required: true,
    sensitive: false,
    category: 'personal',
    defaultPermission: { canView: true, canEdit: true },
  },
  middleName: {
    label: 'Middle Name',
    required: false,
    sensitive: false,
    category: 'personal',
    defaultPermission: { canView: true, canEdit: true },
  },
  lastName: {
    label: 'Last Name',
    required: true,
    sensitive: false,
    category: 'personal',
    defaultPermission: { canView: true, canEdit: true },
  },
  preferredName: {
    label: 'Preferred Name',
    required: false,
    sensitive: false,
    category: 'personal',
    defaultPermission: { canView: true, canEdit: true },
  },
  
  // Personal details
  dateOfBirth: {
    label: 'Date of Birth',
    required: false,
    sensitive: true,
    category: 'personal',
    defaultPermission: { canView: true, canEdit: true, isSensitive: true },
  },
  gender: {
    label: 'Gender',
    required: false,
    sensitive: false,
    category: 'personal',
    defaultPermission: { canView: true, canEdit: true },
  },
  
  // Contact information
  email: {
    label: 'Work Email',
    required: true,
    sensitive: false,
    category: 'contact',
    defaultPermission: { canView: true, canEdit: true },
  },
  personalEmail: {
    label: 'Personal Email',
    required: false,
    sensitive: true,
    category: 'contact',
    defaultPermission: { canView: true, canEdit: true, isSensitive: true },
  },
  phoneNumber: {
    label: 'Work Phone',
    required: false,
    sensitive: false,
    category: 'contact',
    defaultPermission: { canView: true, canEdit: true },
  },
  mobileNumber: {
    label: 'Mobile Number',
    required: false,
    sensitive: false,
    category: 'contact',
    defaultPermission: { canView: true, canEdit: true },
  },
  
  // Address
  addressLine1: {
    label: 'Street Address',
    required: false,
    sensitive: false,
    category: 'address',
    defaultPermission: { canView: true, canEdit: true },
  },
  addressLine2: {
    label: 'Address Line 2',
    required: false,
    sensitive: false,
    category: 'address',
    defaultPermission: { canView: true, canEdit: true },
  },
  city: {
    label: 'City',
    required: false,
    sensitive: false,
    category: 'address',
    defaultPermission: { canView: true, canEdit: true },
  },
  stateProvince: {
    label: 'State/Province',
    required: false,
    sensitive: false,
    category: 'address',
    defaultPermission: { canView: true, canEdit: true },
  },
  postalCode: {
    label: 'Postal Code',
    required: false,
    sensitive: false,
    category: 'address',
    defaultPermission: { canView: true, canEdit: true },
  },
  country: {
    label: 'Country',
    required: false,
    sensitive: false,
    category: 'address',
    defaultPermission: { canView: true, canEdit: true },
  },
  
  // Emergency contacts
  emergencyContacts: {
    label: 'Emergency Contacts',
    required: false,
    sensitive: false,
    category: 'emergency',
    defaultPermission: { canView: true, canEdit: true },
  },
};

// Validation functions
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_REGEX = /^\+?[0-9\s\-()]{7,20}$/;

function validateField(fieldName, value, isRequired) {
  // Check required
  if (isRequired && (!value || String(value).trim().length === 0)) {
    return `${FIELD_DEFINITIONS[fieldName]?.label || fieldName} is required`;
  }

  // Skip further validation if empty and not required
  if (!value || String(value).trim().length === 0) {
    return null;
  }

  // Field-specific validation
  switch (fieldName) {
    case 'firstName':
    case 'lastName':
      if (value.length > 100) {
        return 'Must be 100 characters or less';
      }
      if (!/^[a-zA-Z\s\-']+$/.test(value)) {
        return 'Only letters, spaces, hyphens, and apostrophes allowed';
      }
      return null;

    case 'email':
    case 'personalEmail':
      if (!EMAIL_REGEX.test(value)) {
        return 'Please enter a valid email address';
      }
      return null;

    case 'phoneNumber':
    case 'mobileNumber':
      if (!PHONE_REGEX.test(value)) {
        return 'Please enter a valid phone number';
      }
      return null;

    case 'dateOfBirth':
      const dob = new Date(value);
      const now = new Date();
      const age = Math.floor((now - dob) / (365.25 * 24 * 60 * 60 * 1000));
      if (age < 16) {
        return 'Employee must be at least 16 years old';
      }
      if (age > 100) {
        return 'Please enter a valid date of birth';
      }
      return null;

    case 'postalCode':
      if (value.length > 20) {
        return 'Postal code must be 20 characters or less';
      }
      return null;

    default:
      return null;
  }
}

/**
 * Custom hook for personal information management
 */
export function usePersonalInformation(employeeId, options = {}) {
  const {
    apiClient = null,
    initialData = null,
    onUpdateSuccess = () => {},
    onUpdateError = () => {},
  } = options;

  // State
  const [employee, setEmployee] = useState(initialData);
  const [fieldPermissions, setFieldPermissions] = useState({});
  const [isLoading, setIsLoading] = useState(!initialData);
  const [error, setError] = useState(null);
  const [pendingUpdates, setPendingUpdates] = useState({});
  const [updateErrors, setUpdateErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  // Fetch employee data and permissions
  const fetchData = useCallback(async () => {
    if (!employeeId) return;

    setIsLoading(true);
    setError(null);

    try {
      // In production, replace with actual API calls
      const [employeeResponse, permissionsResponse] = await Promise.all([
        apiClient?.getEmployee?.(employeeId) || mockFetchEmployee(employeeId),
        apiClient?.getFieldPermissions?.(employeeId) || mockFetchPermissions(employeeId),
      ]);

      setEmployee(employeeResponse);
      setFieldPermissions(permissionsResponse);
    } catch (err) {
      setError(err.message || 'Failed to load personal information');
    } finally {
      setIsLoading(false);
    }
  }, [employeeId, apiClient]);

  // Load data on mount or when employeeId changes
  useEffect(() => {
    if (!initialData) {
      fetchData();
    }
  }, [fetchData, initialData]);

  // Get permission for a specific field
  const getFieldPermission = useCallback(
    (fieldName) => {
      const permission = fieldPermissions[fieldName];
      const definition = FIELD_DEFINITIONS[fieldName];
      
      if (permission) {
        return {
          ...definition?.defaultPermission,
          ...permission,
        };
      }
      
      return definition?.defaultPermission || { canView: true, canEdit: false };
    },
    [fieldPermissions]
  );

  // Computed merged permissions
  const mergedPermissions = useMemo(() => {
    const result = {};
    Object.keys(FIELD_DEFINITIONS).forEach((fieldName) => {
      result[fieldName] = getFieldPermission(fieldName);
    });
    return result;
  }, [getFieldPermission]);

  // Validate a single field
  const validateSingleField = useCallback((fieldName, value) => {
    const definition = FIELD_DEFINITIONS[fieldName];
    return validateField(fieldName, value, definition?.required);
  }, []);

  // Update a single field
  const updateField = useCallback(
    async (fieldName, value) => {
      // Check permission
      const permission = getFieldPermission(fieldName);
      if (!permission.canEdit) {
        throw new Error(`You do not have permission to edit ${FIELD_DEFINITIONS[fieldName]?.label || fieldName}`);
      }

      // Validate
      const validationError = validateSingleField(fieldName, value);
      if (validationError) {
        setUpdateErrors((prev) => ({ ...prev, [fieldName]: validationError }));
        throw new Error(validationError);
      }

      setIsSaving(true);
      setPendingUpdates((prev) => ({ ...prev, [fieldName]: value }));

      try {
        // In production, replace with actual API call
        await (apiClient?.updateEmployeeField?.(employeeId, fieldName, value) ||
          mockUpdateField(employeeId, fieldName, value));

        // Update local state
        setEmployee((prev) => ({
          ...prev,
          [fieldName]: value,
        }));

        // Clear pending and errors
        setPendingUpdates((prev) => {
          const next = { ...prev };
          delete next[fieldName];
          return next;
        });
        setUpdateErrors((prev) => {
          const next = { ...prev };
          delete next[fieldName];
          return next;
        });

        onUpdateSuccess(fieldName, value);
      } catch (err) {
        const errorMessage = err.message || 'Failed to save changes';
        setUpdateErrors((prev) => ({ ...prev, [fieldName]: errorMessage }));
        onUpdateError(fieldName, errorMessage);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [employeeId, apiClient, getFieldPermission, validateSingleField, onUpdateSuccess, onUpdateError]
  );

  // Update emergency contacts
  const updateEmergencyContacts = useCallback(
    async (contacts) => {
      const permission = getFieldPermission('emergencyContacts');
      if (!permission.canEdit) {
        throw new Error('You do not have permission to edit emergency contacts');
      }

      setIsSaving(true);

      try {
        await (apiClient?.updateEmergencyContacts?.(employeeId, contacts) ||
          mockUpdateEmergencyContacts(employeeId, contacts));

        setEmployee((prev) => ({
          ...prev,
          emergencyContacts: contacts,
        }));

        onUpdateSuccess('emergencyContacts', contacts);
      } catch (err) {
        const errorMessage = err.message || 'Failed to save emergency contacts';
        onUpdateError('emergencyContacts', errorMessage);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [employeeId, apiClient, getFieldPermission, onUpdateSuccess, onUpdateError]
  );

  // Check if any field has unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    return Object.keys(pendingUpdates).length > 0;
  }, [pendingUpdates]);

  // Get fields that require approval
  const fieldsRequiringApproval = useMemo(() => {
    return Object.entries(mergedPermissions)
      .filter(([, perm]) => perm.requiresApproval)
      .map(([fieldName]) => fieldName);
  }, [mergedPermissions]);

  // Refresh data
  const refresh = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return {
    // Data
    employee,
    fieldPermissions: mergedPermissions,
    
    // State
    isLoading,
    isSaving,
    error,
    updateErrors,
    hasUnsavedChanges,
    pendingUpdates,
    fieldsRequiringApproval,
    
    // Actions
    updateField,
    updateEmergencyContacts,
    validateField: validateSingleField,
    getFieldPermission,
    refresh,
  };
}

// Mock functions for development/testing
async function mockFetchEmployee(employeeId) {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 300));

  return {
    id: employeeId,
    firstName: 'John',
    middleName: 'William',
    lastName: 'Doe',
    preferredName: 'Johnny',
    dateOfBirth: '1990-05-15',
    gender: 'Male',
    email: 'john.doe@company.com',
    personalEmail: 'john.doe@gmail.com',
    phoneNumber: '+1 (555) 123-4567',
    mobileNumber: '+1 (555) 987-6543',
    addressLine1: '123 Main Street',
    addressLine2: 'Apt 4B',
    city: 'San Francisco',
    stateProvince: 'California',
    postalCode: '94102',
    country: 'United States',
    emergencyContacts: [
      {
        name: 'Jane Doe',
        relationship: 'Spouse',
        phone: '+1 (555) 111-2222',
        email: 'jane.doe@email.com',
        isPrimary: true,
      },
      {
        name: 'Robert Doe',
        relationship: 'Parent',
        phone: '+1 (555) 333-4444',
        email: '',
        isPrimary: false,
      },
    ],
  };
}

async function mockFetchPermissions(employeeId) {
  await new Promise((resolve) => setTimeout(resolve, 100));

  // Return permissions based on employee viewing their own profile
  return {
    firstName: { canView: true, canEdit: true },
    middleName: { canView: true, canEdit: true },
    lastName: { canView: true, canEdit: true },
    preferredName: { canView: true, canEdit: true },
    dateOfBirth: { canView: true, canEdit: true, isSensitive: true },
    gender: { canView: true, canEdit: true },
    email: { canView: true, canEdit: false }, // Work email typically not editable
    personalEmail: { canView: true, canEdit: true, isSensitive: true },
    phoneNumber: { canView: true, canEdit: true },
    mobileNumber: { canView: true, canEdit: true },
    addressLine1: { canView: true, canEdit: true },
    addressLine2: { canView: true, canEdit: true },
    city: { canView: true, canEdit: true },
    stateProvince: { canView: true, canEdit: true },
    postalCode: { canView: true, canEdit: true },
    country: { canView: true, canEdit: true },
    emergencyContacts: { canView: true, canEdit: true },
  };
}

async function mockUpdateField(employeeId, fieldName, value) {
  await new Promise((resolve) => setTimeout(resolve, 200));
  
  // Simulate occasional failure for testing
  if (Math.random() < 0.05) {
    throw new Error('Network error. Please try again.');
  }
  
  return { success: true, fieldName, value };
}

async function mockUpdateEmergencyContacts(employeeId, contacts) {
  await new Promise((resolve) => setTimeout(resolve, 300));
  return { success: true, contacts };
}

export default usePersonalInformation;

