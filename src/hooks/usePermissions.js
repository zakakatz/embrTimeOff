/**
 * usePermissions Hook
 * 
 * Custom hook for checking user permissions for fields and actions.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

// Mock permission data - would come from auth context in real app
const mockUserPermissions = {
  role: 'hr_admin',
  permissions: [
    'view_personal',
    'view_job',
    'view_compensation',
    'view_emergency',
    'view_organization',
    'edit_profile',
  ],
  editableFields: [
    'firstName',
    'middleName',
    'lastName',
    'preferredName',
    'dateOfBirth',
    'gender',
    'email',
    'personalEmail',
    'phoneNumber',
    'mobileNumber',
    'addressLine1',
    'addressLine2',
    'city',
    'stateProvince',
    'postalCode',
    'country',
    'jobTitle',
    'employmentType',
    'hireDate',
    'departmentId',
    'managerId',
  ],
  fieldPermissions: {
    personal: {
      firstName: { canView: true, canEdit: true },
      middleName: { canView: true, canEdit: true },
      lastName: { canView: true, canEdit: true },
      preferredName: { canView: true, canEdit: true },
      dateOfBirth: { canView: true, canEdit: true, isSensitive: true },
      gender: { canView: true, canEdit: true },
      email: { canView: true, canEdit: true },
      personalEmail: { canView: true, canEdit: true, isSensitive: true },
      phoneNumber: { canView: true, canEdit: true },
      mobileNumber: { canView: true, canEdit: true },
      addressLine1: { canView: true, canEdit: true },
      addressLine2: { canView: true, canEdit: true },
      city: { canView: true, canEdit: true },
      stateProvince: { canView: true, canEdit: true },
      postalCode: { canView: true, canEdit: true },
      country: { canView: true, canEdit: true },
    },
    job: {
      employeeId: { canView: true, canEdit: false },
      jobTitle: { canView: true, canEdit: true },
      employmentType: { canView: true, canEdit: true },
      employmentStatus: { canView: true, canEdit: true },
      hireDate: { canView: true, canEdit: true },
      terminationDate: { canView: true, canEdit: false },
      location: { canView: true, canEdit: true },
      workSchedule: { canView: true, canEdit: true },
    },
    compensation: {
      salary: { canView: true, canEdit: false, isSensitive: true, canReveal: true },
      hourlyRate: { canView: true, canEdit: false, isSensitive: true, canReveal: true },
      benefits: { canView: true, canEdit: false },
    },
    emergency: {
      emergencyContacts: { canView: true, canEdit: true },
    },
    organization: {
      department: { canView: true, canEdit: true },
      manager: { canView: true, canEdit: true },
      directReports: { canView: true, canEdit: false },
      teamMembers: { canView: true, canEdit: false },
    },
  },
};

export function usePermissions() {
  const [userPermissions, setUserPermissions] = useState(mockUserPermissions);

  // Check if user has a specific permission
  const hasPermission = useCallback(
    (permission) => {
      return userPermissions.permissions.includes(permission);
    },
    [userPermissions.permissions]
  );

  // Get field permissions for a section
  const getFieldPermissions = useCallback(
    (section) => {
      return userPermissions.fieldPermissions[section] || {};
    },
    [userPermissions.fieldPermissions]
  );

  // Check if a field can be edited
  const canEditField = useCallback(
    (fieldName) => {
      return userPermissions.editableFields.includes(fieldName);
    },
    [userPermissions.editableFields]
  );

  // Get list of editable fields
  const getEditableFields = useCallback(() => {
    return userPermissions.editableFields;
  }, [userPermissions.editableFields]);

  // Check if user is admin
  const isAdmin = useMemo(() => {
    return ['admin', 'hr_admin'].includes(userPermissions.role);
  }, [userPermissions.role]);

  // Check if field requires approval to edit
  const requiresApproval = useCallback((fieldName) => {
    const sensitiveFields = ['salary', 'hourlyRate', 'managerId', 'departmentId'];
    return sensitiveFields.includes(fieldName);
  }, []);

  return {
    hasPermission,
    getFieldPermissions,
    canEditField,
    getEditableFields,
    isAdmin,
    requiresApproval,
    userRole: userPermissions.role,
  };
}

export default usePermissions;

