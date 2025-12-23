/**
 * useImportExportPermissions Hook
 * 
 * Manages and checks user permissions for import/export operations.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

// Permission definitions
const PERMISSIONS = {
  IMPORT_EMPLOYEES: 'import_employees',
  EXPORT_EMPLOYEES: 'export_employees',
  EXPORT_SENSITIVE_FIELDS: 'export_sensitive_fields',
  VIEW_IMPORT_HISTORY: 'view_import_history',
  ROLLBACK_IMPORT: 'rollback_import',
};

// Role-based permissions mapping
const ROLE_PERMISSIONS = {
  admin: [
    PERMISSIONS.IMPORT_EMPLOYEES,
    PERMISSIONS.EXPORT_EMPLOYEES,
    PERMISSIONS.EXPORT_SENSITIVE_FIELDS,
    PERMISSIONS.VIEW_IMPORT_HISTORY,
    PERMISSIONS.ROLLBACK_IMPORT,
  ],
  hr_manager: [
    PERMISSIONS.IMPORT_EMPLOYEES,
    PERMISSIONS.EXPORT_EMPLOYEES,
    PERMISSIONS.EXPORT_SENSITIVE_FIELDS,
    PERMISSIONS.VIEW_IMPORT_HISTORY,
    PERMISSIONS.ROLLBACK_IMPORT,
  ],
  manager: [
    PERMISSIONS.EXPORT_EMPLOYEES,
    PERMISSIONS.VIEW_IMPORT_HISTORY,
  ],
  employee: [
    // Employees cannot import or export
  ],
};

// Sensitive fields that require special permission
const SENSITIVE_FIELDS = [
  'salary',
  'hourly_rate',
  'date_of_birth',
  'personal_email',
  'phone_number',
  'mobile_number',
  'address_line1',
  'address_line2',
];

/**
 * Hook for managing import/export permissions
 * 
 * @param {Object} options - Hook options
 * @param {string} options.userRole - Current user's role
 * @param {Function} options.onPermissionDenied - Callback when permission is denied
 * @returns {Object} Permission utilities and state
 */
export function useImportExportPermissions({
  userRole = 'employee',
  onPermissionDenied,
} = {}) {
  const [isLoading, setIsLoading] = useState(true);
  const [permissions, setPermissions] = useState([]);

  // Load permissions based on role
  useEffect(() => {
    setIsLoading(true);
    
    // Simulate async permission loading
    const loadPermissions = async () => {
      try {
        // In production, this might fetch from an API
        const rolePermissions = ROLE_PERMISSIONS[userRole] || [];
        setPermissions(rolePermissions);
      } catch (error) {
        console.error('Failed to load permissions:', error);
        setPermissions([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadPermissions();
  }, [userRole]);

  // Check if user has a specific permission
  const hasPermission = useCallback((permission) => {
    return permissions.includes(permission);
  }, [permissions]);

  // Check if user can import employees
  const canImport = useMemo(() => {
    return hasPermission(PERMISSIONS.IMPORT_EMPLOYEES);
  }, [hasPermission]);

  // Check if user can export employees
  const canExport = useMemo(() => {
    return hasPermission(PERMISSIONS.EXPORT_EMPLOYEES);
  }, [hasPermission]);

  // Check if user can export sensitive fields
  const canExportSensitiveFields = useMemo(() => {
    return hasPermission(PERMISSIONS.EXPORT_SENSITIVE_FIELDS);
  }, [hasPermission]);

  // Check if user can view import history
  const canViewImportHistory = useMemo(() => {
    return hasPermission(PERMISSIONS.VIEW_IMPORT_HISTORY);
  }, [hasPermission]);

  // Check if user can rollback imports
  const canRollbackImport = useMemo(() => {
    return hasPermission(PERMISSIONS.ROLLBACK_IMPORT);
  }, [hasPermission]);

  // Get exportable fields based on permissions
  const getExportableFields = useCallback((allFields) => {
    if (canExportSensitiveFields) {
      return allFields;
    }
    
    return allFields.filter((field) => {
      const fieldId = typeof field === 'string' ? field : field.id;
      return !SENSITIVE_FIELDS.includes(fieldId);
    });
  }, [canExportSensitiveFields]);

  // Check field export permission
  const canExportField = useCallback((fieldId) => {
    if (canExportSensitiveFields) {
      return true;
    }
    return !SENSITIVE_FIELDS.includes(fieldId);
  }, [canExportSensitiveFields]);

  // Require permission (throws or calls callback if denied)
  const requirePermission = useCallback((permission, action = 'perform this action') => {
    if (!hasPermission(permission)) {
      const error = new Error(`Permission denied: Cannot ${action}`);
      error.code = 'PERMISSION_DENIED';
      error.permission = permission;
      
      if (onPermissionDenied) {
        onPermissionDenied(error);
      }
      
      return false;
    }
    return true;
  }, [hasPermission, onPermissionDenied]);

  // Check import permission with callback
  const checkImportPermission = useCallback(() => {
    return requirePermission(PERMISSIONS.IMPORT_EMPLOYEES, 'import employees');
  }, [requirePermission]);

  // Check export permission with callback
  const checkExportPermission = useCallback(() => {
    return requirePermission(PERMISSIONS.EXPORT_EMPLOYEES, 'export employees');
  }, [requirePermission]);

  return {
    isLoading,
    permissions,
    hasPermission,
    
    // Computed permissions
    canImport,
    canExport,
    canExportSensitiveFields,
    canViewImportHistory,
    canRollbackImport,
    
    // Field-level permissions
    getExportableFields,
    canExportField,
    
    // Permission checks with callbacks
    checkImportPermission,
    checkExportPermission,
    requirePermission,
    
    // Constants
    PERMISSIONS,
    SENSITIVE_FIELDS,
  };
}

export default useImportExportPermissions;
export { PERMISSIONS, SENSITIVE_FIELDS };

