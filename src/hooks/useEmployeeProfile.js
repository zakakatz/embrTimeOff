/**
 * useEmployeeProfile Hook
 * 
 * Comprehensive hook for managing employee profile data including loading,
 * caching, updating, validation, permission-based filtering, change tracking,
 * and conflict resolution.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

const API_BASE_URL = '/api/employees';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Hook for employee profile state management.
 * 
 * @param {Object} options - Configuration options
 * @param {number|string} options.employeeId - Employee ID (number or string ID)
 * @param {boolean} options.autoLoad - Auto-load profile on mount (default: true)
 * @param {string} options.userRole - Current user's role for permission filtering
 * @param {Function} options.onError - Error callback
 * @param {Function} options.onUpdate - Update success callback
 * @returns {Object} Profile state and control functions
 */
export function useEmployeeProfile({
  employeeId = null,
  autoLoad = true,
  userRole = 'employee',
  onError,
  onUpdate,
} = {}) {
  // Core state
  const [profile, setProfile] = useState(null);
  const [originalProfile, setOriginalProfile] = useState(null);
  const [auditTrail, setAuditTrail] = useState([]);
  
  // Loading states
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  
  // Edit state
  const [editMode, setEditMode] = useState(false);
  const [pendingChanges, setPendingChanges] = useState({});
  const [validationErrors, setValidationErrors] = useState({});
  const [conflictState, setConflictState] = useState(null);
  
  // Refs
  const cacheRef = useRef(new Map());
  const lastFetchRef = useRef(null);
  const versionRef = useRef(null);

  // =========================================================================
  // Permission-based Field Filtering
  // =========================================================================

  const ROLE_FIELD_PERMISSIONS = useMemo(() => ({
    admin: {
      viewable: ['*'], // All fields
      editable: ['*'],
    },
    hr_manager: {
      viewable: ['*'],
      editable: [
        'first_name', 'middle_name', 'last_name', 'preferred_name',
        'email', 'personal_email', 'phone_number', 'mobile_number',
        'address_line1', 'address_line2', 'city', 'state_province',
        'postal_code', 'country', 'date_of_birth', 'gender',
        'department_id', 'manager_id', 'location_id', 'work_schedule_id',
        'job_title', 'employment_type', 'employment_status',
        'hire_date', 'termination_date', 'salary', 'hourly_rate',
      ],
    },
    manager: {
      viewable: [
        'id', 'employee_id', 'email', 'first_name', 'middle_name', 'last_name',
        'preferred_name', 'phone_number', 'mobile_number', 'department_id',
        'manager_id', 'location_id', 'job_title', 'employment_type',
        'employment_status', 'hire_date', 'is_active', 'department', 'location',
      ],
      editable: ['work_schedule_id', 'job_title'],
    },
    employee: {
      viewable: [
        'id', 'employee_id', 'email', 'first_name', 'last_name',
        'preferred_name', 'phone_number', 'department_id', 'location_id',
        'job_title', 'employment_status', 'department', 'location',
      ],
      editable: [
        'preferred_name', 'personal_email', 'phone_number', 'mobile_number',
        'address_line1', 'address_line2', 'city', 'state_province',
        'postal_code', 'country',
      ],
    },
  }), []);

  const permissions = useMemo(() => {
    return ROLE_FIELD_PERMISSIONS[userRole] || ROLE_FIELD_PERMISSIONS.employee;
  }, [userRole, ROLE_FIELD_PERMISSIONS]);

  const canViewField = useCallback((fieldName) => {
    if (permissions.viewable.includes('*')) return true;
    return permissions.viewable.includes(fieldName);
  }, [permissions]);

  const canEditField = useCallback((fieldName) => {
    if (permissions.editable.includes('*')) return true;
    return permissions.editable.includes(fieldName);
  }, [permissions]);

  const filteredProfile = useMemo(() => {
    if (!profile) return null;
    if (permissions.viewable.includes('*')) return profile;
    
    const filtered = {};
    Object.keys(profile).forEach((key) => {
      if (canViewField(key)) {
        filtered[key] = profile[key];
      }
    });
    return filtered;
  }, [profile, permissions, canViewField]);

  // =========================================================================
  // Data Loading
  // =========================================================================

  const loadProfile = useCallback(async (id = employeeId) => {
    if (!id) {
      setError('No employee ID provided');
      return null;
    }

    // Check cache
    const cacheKey = String(id);
    const cached = cacheRef.current.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      setProfile(cached.data);
      setOriginalProfile(cached.data);
      versionRef.current = cached.data.updated_at;
      return cached.data;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/${id}`, {
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error?.message || `Failed to load profile: ${response.status}`);
      }

      const data = await response.json();
      const profileData = data.data || data;

      // Update cache
      cacheRef.current.set(cacheKey, {
        data: profileData,
        timestamp: Date.now(),
      });

      setProfile(profileData);
      setOriginalProfile(profileData);
      versionRef.current = profileData.updated_at;
      lastFetchRef.current = Date.now();

      return profileData;
    } catch (err) {
      const errorMessage = err.message || 'Failed to load profile';
      setError(errorMessage);
      onError?.(err);
      return null;
    } finally {
      setLoading(false);
    }
  }, [employeeId, userRole, onError]);

  const loadAuditTrail = useCallback(async (id = employeeId) => {
    if (!id) return [];

    try {
      const response = await fetch(`${API_BASE_URL}/${id}/audit-trail`, {
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
        },
      });

      if (response.ok) {
        const data = await response.json();
        const trailData = data.data || data;
        setAuditTrail(trailData);
        return trailData;
      }
    } catch (err) {
      console.error('Failed to load audit trail:', err);
    }
    return [];
  }, [employeeId, userRole]);

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad && employeeId) {
      loadProfile(employeeId);
    }
  }, [autoLoad, employeeId, loadProfile]);

  // =========================================================================
  // Change Tracking
  // =========================================================================

  const hasChanges = useMemo(() => {
    return Object.keys(pendingChanges).length > 0;
  }, [pendingChanges]);

  const changedFields = useMemo(() => {
    return Object.keys(pendingChanges);
  }, [pendingChanges]);

  const getFieldChange = useCallback((fieldName) => {
    if (!pendingChanges[fieldName]) return null;
    return {
      field: fieldName,
      oldValue: originalProfile?.[fieldName],
      newValue: pendingChanges[fieldName],
    };
  }, [pendingChanges, originalProfile]);

  const getAllChanges = useCallback(() => {
    return changedFields.map((field) => getFieldChange(field)).filter(Boolean);
  }, [changedFields, getFieldChange]);

  // =========================================================================
  // Field Updates
  // =========================================================================

  const updateField = useCallback((fieldName, value) => {
    if (!canEditField(fieldName)) {
      console.warn(`No permission to edit field: ${fieldName}`);
      return false;
    }

    setPendingChanges((prev) => {
      // If value matches original, remove from pending changes
      if (originalProfile && originalProfile[fieldName] === value) {
        const { [fieldName]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [fieldName]: value };
    });

    // Clear validation error for this field
    setValidationErrors((prev) => {
      const { [fieldName]: _, ...rest } = prev;
      return rest;
    });

    // Update local profile state for immediate UI feedback
    setProfile((prev) => ({
      ...prev,
      [fieldName]: value,
    }));

    return true;
  }, [canEditField, originalProfile]);

  const updateFields = useCallback((updates) => {
    Object.entries(updates).forEach(([field, value]) => {
      updateField(field, value);
    });
  }, [updateField]);

  const revertField = useCallback((fieldName) => {
    setPendingChanges((prev) => {
      const { [fieldName]: _, ...rest } = prev;
      return rest;
    });

    setProfile((prev) => ({
      ...prev,
      [fieldName]: originalProfile?.[fieldName],
    }));
  }, [originalProfile]);

  const revertAllChanges = useCallback(() => {
    setPendingChanges({});
    setValidationErrors({});
    setProfile(originalProfile);
  }, [originalProfile]);

  // =========================================================================
  // Validation
  // =========================================================================

  const validateField = useCallback((fieldName, value) => {
    const errors = [];

    // Required field validation
    const requiredFields = ['employee_id', 'email', 'first_name', 'last_name', 'hire_date'];
    if (requiredFields.includes(fieldName) && (!value || value === '')) {
      errors.push(`${fieldName.replace(/_/g, ' ')} is required`);
    }

    // Email validation
    if (fieldName === 'email' || fieldName === 'personal_email') {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (value && !emailRegex.test(value)) {
        errors.push('Invalid email format');
      }
    }

    // Phone validation
    if (fieldName === 'phone_number' || fieldName === 'mobile_number') {
      const phoneRegex = /^[\d\s\-\(\)\+]+$/;
      if (value && !phoneRegex.test(value)) {
        errors.push('Invalid phone number format');
      }
    }

    return errors;
  }, []);

  const validateAllChanges = useCallback(() => {
    const allErrors = {};
    let hasErrors = false;

    Object.entries(pendingChanges).forEach(([field, value]) => {
      const fieldErrors = validateField(field, value);
      if (fieldErrors.length > 0) {
        allErrors[field] = fieldErrors;
        hasErrors = true;
      }
    });

    setValidationErrors(allErrors);
    return !hasErrors;
  }, [pendingChanges, validateField]);

  // =========================================================================
  // Save Operations
  // =========================================================================

  const checkForConflicts = useCallback(async () => {
    if (!employeeId) return false;

    try {
      const response = await fetch(`${API_BASE_URL}/${employeeId}`, {
        headers: { 'X-User-Role': userRole },
      });

      if (response.ok) {
        const data = await response.json();
        const serverProfile = data.data || data;

        if (serverProfile.updated_at !== versionRef.current) {
          setConflictState({
            localChanges: pendingChanges,
            serverProfile,
            localProfile: originalProfile,
          });
          return true;
        }
      }
    } catch (err) {
      console.error('Conflict check failed:', err);
    }
    return false;
  }, [employeeId, userRole, pendingChanges, originalProfile]);

  const saveProfile = useCallback(async (options = {}) => {
    const { force = false, skipValidation = false } = options;

    if (!employeeId) {
      setError('No employee ID for save');
      return false;
    }

    if (!hasChanges) {
      return true; // Nothing to save
    }

    // Validate
    if (!skipValidation && !validateAllChanges()) {
      return false;
    }

    // Check for conflicts
    if (!force) {
      const hasConflict = await checkForConflicts();
      if (hasConflict) {
        return false;
      }
    }

    setSaving(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/${employeeId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
        },
        body: JSON.stringify(pendingChanges),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error?.message || 'Failed to save profile');
      }

      const data = await response.json();
      const savedProfile = data.data || data;

      // Update state
      setProfile(savedProfile);
      setOriginalProfile(savedProfile);
      setPendingChanges({});
      setConflictState(null);
      versionRef.current = savedProfile.updated_at;

      // Update cache
      cacheRef.current.set(String(employeeId), {
        data: savedProfile,
        timestamp: Date.now(),
      });

      onUpdate?.(savedProfile);
      return true;
    } catch (err) {
      const errorMessage = err.message || 'Failed to save profile';
      setError(errorMessage);
      onError?.(err);
      return false;
    } finally {
      setSaving(false);
    }
  }, [employeeId, hasChanges, pendingChanges, userRole, validateAllChanges, checkForConflicts, onUpdate, onError]);

  // =========================================================================
  // Conflict Resolution
  // =========================================================================

  const resolveConflict = useCallback((resolution) => {
    if (!conflictState) return;

    switch (resolution) {
      case 'keep_local':
        // Force save with local changes
        saveProfile({ force: true });
        break;
      case 'keep_server':
        // Accept server version
        setProfile(conflictState.serverProfile);
        setOriginalProfile(conflictState.serverProfile);
        setPendingChanges({});
        versionRef.current = conflictState.serverProfile.updated_at;
        break;
      case 'merge':
        // Merge changes (server as base, apply local changes that don't conflict)
        const merged = { ...conflictState.serverProfile };
        Object.entries(conflictState.localChanges).forEach(([field, value]) => {
          if (conflictState.serverProfile[field] === conflictState.localProfile?.[field]) {
            merged[field] = value;
          }
        });
        setProfile(merged);
        setOriginalProfile(conflictState.serverProfile);
        versionRef.current = conflictState.serverProfile.updated_at;
        break;
    }

    setConflictState(null);
  }, [conflictState, saveProfile]);

  // =========================================================================
  // Edit Mode Management
  // =========================================================================

  const enterEditMode = useCallback(() => {
    setEditMode(true);
  }, []);

  const exitEditMode = useCallback((save = false) => {
    if (save && hasChanges) {
      saveProfile();
    } else if (!save) {
      revertAllChanges();
    }
    setEditMode(false);
  }, [hasChanges, saveProfile, revertAllChanges]);

  // =========================================================================
  // Return Value
  // =========================================================================

  return {
    // Data
    profile: filteredProfile,
    originalProfile,
    auditTrail,

    // Loading states
    loading,
    saving,
    error,

    // Edit state
    editMode,
    pendingChanges,
    hasChanges,
    changedFields,
    validationErrors,
    conflictState,

    // Permissions
    canViewField,
    canEditField,
    permissions,

    // Data loading
    loadProfile,
    loadAuditTrail,
    refresh: () => loadProfile(employeeId),

    // Field updates
    updateField,
    updateFields,
    revertField,
    revertAllChanges,

    // Change tracking
    getFieldChange,
    getAllChanges,

    // Validation
    validateField,
    validateAllChanges,

    // Save operations
    saveProfile,
    checkForConflicts,

    // Conflict resolution
    resolveConflict,

    // Edit mode
    enterEditMode,
    exitEditMode,

    // Cache management
    clearCache: () => cacheRef.current.clear(),
  };
}

export default useEmployeeProfile;

