/**
 * useFormPersistence - Custom hook for persisting form data
 * 
 * Features:
 * - Auto-save to localStorage
 * - Debounced saving
 * - Clear saved data on submit
 * - Restore on mount
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook for form data persistence
 * @param {Object} options Configuration options
 * @param {string} options.key Storage key for the form
 * @param {Object} options.initialData Initial form data
 * @param {number} options.debounceMs Debounce delay for auto-save (ms)
 * @param {boolean} options.autoSave Enable auto-save
 * @param {Function} options.serialize Custom serialization function
 * @param {Function} options.deserialize Custom deserialization function
 * @param {string} options.storage Storage type ('local' or 'session')
 * @returns {Object} Persistence state and handlers
 */
export const useFormPersistence = ({
  key,
  initialData = {},
  debounceMs = 1000,
  autoSave = true,
  serialize = JSON.stringify,
  deserialize = JSON.parse,
  storage = 'local',
} = {}) => {
  // Get storage object
  const getStorage = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return storage === 'session' ? window.sessionStorage : window.localStorage;
  }, [storage]);
  
  // State
  const [data, setData] = useState(() => {
    // Try to restore data on initial render
    const storageObj = getStorage();
    if (!storageObj || !key) return initialData;
    
    try {
      const stored = storageObj.getItem(key);
      if (stored) {
        const parsed = deserialize(stored);
        return { ...initialData, ...parsed.data };
      }
    } catch (error) {
      console.warn('Failed to restore form data:', error);
    }
    
    return initialData;
  });
  
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [hasRestoredData, setHasRestoredData] = useState(false);
  
  // Refs for debouncing
  const saveTimeoutRef = useRef(null);
  const dataRef = useRef(data);
  
  // Keep data ref updated
  useEffect(() => {
    dataRef.current = data;
  }, [data]);
  
  // Check if there's saved data
  const hasSavedData = useCallback(() => {
    const storageObj = getStorage();
    if (!storageObj || !key) return false;
    
    try {
      return storageObj.getItem(key) !== null;
    } catch {
      return false;
    }
  }, [getStorage, key]);
  
  // Get saved metadata
  const getSavedMetadata = useCallback(() => {
    const storageObj = getStorage();
    if (!storageObj || !key) return null;
    
    try {
      const stored = storageObj.getItem(key);
      if (stored) {
        const parsed = deserialize(stored);
        return {
          savedAt: parsed.savedAt ? new Date(parsed.savedAt) : null,
          currentStep: parsed.currentStep,
        };
      }
    } catch {
      return null;
    }
    
    return null;
  }, [getStorage, key, deserialize]);
  
  // Save data to storage
  const save = useCallback((dataToSave = dataRef.current, metadata = {}) => {
    const storageObj = getStorage();
    if (!storageObj || !key) return false;
    
    setIsSaving(true);
    
    try {
      const payload = {
        data: dataToSave,
        savedAt: new Date().toISOString(),
        ...metadata,
      };
      
      storageObj.setItem(key, serialize(payload));
      setLastSavedAt(new Date());
      setIsSaving(false);
      return true;
    } catch (error) {
      console.error('Failed to save form data:', error);
      setIsSaving(false);
      return false;
    }
  }, [getStorage, key, serialize]);
  
  // Save with debounce
  const saveDebounced = useCallback((dataToSave = dataRef.current, metadata = {}) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    saveTimeoutRef.current = setTimeout(() => {
      save(dataToSave, metadata);
    }, debounceMs);
  }, [save, debounceMs]);
  
  // Clear saved data
  const clear = useCallback(() => {
    const storageObj = getStorage();
    if (!storageObj || !key) return;
    
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    try {
      storageObj.removeItem(key);
      setLastSavedAt(null);
    } catch (error) {
      console.error('Failed to clear form data:', error);
    }
  }, [getStorage, key]);
  
  // Restore data from storage
  const restore = useCallback(() => {
    const storageObj = getStorage();
    if (!storageObj || !key) return null;
    
    try {
      const stored = storageObj.getItem(key);
      if (stored) {
        const parsed = deserialize(stored);
        setData({ ...initialData, ...parsed.data });
        setHasRestoredData(true);
        return parsed;
      }
    } catch (error) {
      console.error('Failed to restore form data:', error);
    }
    
    return null;
  }, [getStorage, key, deserialize, initialData]);
  
  // Update data handler
  const updateData = useCallback((newData) => {
    const updated = typeof newData === 'function'
      ? newData(dataRef.current)
      : { ...dataRef.current, ...newData };
    
    setData(updated);
    
    if (autoSave) {
      saveDebounced(updated);
    }
    
    return updated;
  }, [autoSave, saveDebounced]);
  
  // Set field value
  const setFieldValue = useCallback((field, value) => {
    return updateData({ [field]: value });
  }, [updateData]);
  
  // Reset to initial data
  const reset = useCallback((clearStorage = true) => {
    setData(initialData);
    setHasRestoredData(false);
    
    if (clearStorage) {
      clear();
    }
  }, [initialData, clear]);
  
  // Auto-save effect
  useEffect(() => {
    return () => {
      // Save on unmount if there's pending data
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        save(dataRef.current);
      }
    };
  }, [save]);
  
  // Check for restored data on mount
  useEffect(() => {
    if (hasSavedData()) {
      setHasRestoredData(true);
    }
  }, [hasSavedData]);
  
  return {
    // State
    data,
    lastSavedAt,
    isSaving,
    hasRestoredData,
    
    // Actions
    updateData,
    setFieldValue,
    save,
    saveDebounced,
    clear,
    restore,
    reset,
    
    // Utilities
    hasSavedData,
    getSavedMetadata,
  };
};

/**
 * Hook for tracking unsaved changes with warning
 * @param {boolean} isDirty Whether form has unsaved changes
 * @param {string} message Warning message
 */
export const useUnsavedChangesWarning = (isDirty, message = 'You have unsaved changes. Are you sure you want to leave?') => {
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = message;
        return message;
      }
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isDirty, message]);
};

export default useFormPersistence;

