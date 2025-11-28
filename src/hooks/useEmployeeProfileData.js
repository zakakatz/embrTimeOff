/**
 * useEmployeeProfileData Hook
 * 
 * Custom hook for fetching and managing employee profile data.
 */

import { useState, useEffect, useCallback } from 'react';
import { profileService } from '../services/profileService';

export function useEmployeeProfileData(employeeId) {
  const [employee, setEmployee] = useState(null);
  const [recentChanges, setRecentChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchEmployee = useCallback(async () => {
    if (!employeeId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [employeeData, changesData] = await Promise.all([
        profileService.getEmployee(employeeId),
        profileService.getRecentChanges(employeeId),
      ]);

      setEmployee(employeeData);
      setRecentChanges(changesData);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    fetchEmployee();
  }, [fetchEmployee]);

  const refetch = useCallback(() => {
    return fetchEmployee();
  }, [fetchEmployee]);

  const updateLocalEmployee = useCallback((updates) => {
    setEmployee((prev) => ({
      ...prev,
      ...updates,
    }));
  }, []);

  return {
    employee,
    recentChanges,
    loading,
    error,
    refetch,
    updateLocalEmployee,
  };
}

export default useEmployeeProfileData;

