/**
 * useEmployeeDirectory Hook
 * 
 * Comprehensive hook for managing employee directory functionality including
 * search, filtering, pagination, caching, search history, and export operations.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

const API_BASE_URL = '/api/employees';
const CACHE_TTL = 2 * 60 * 1000; // 2 minutes
const MAX_SEARCH_HISTORY = 10;
const MAX_SAVED_FILTERS = 5;

/**
 * Hook for employee directory state management.
 * 
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoLoad - Auto-load directory on mount (default: true)
 * @param {number} options.pageSize - Items per page (default: 20)
 * @param {string} options.initialSort - Initial sort field (default: 'last_name')
 * @param {string} options.initialSortOrder - Initial sort order (default: 'asc')
 * @param {string} options.userRole - Current user's role
 * @returns {Object} Directory state and control functions
 */
export function useEmployeeDirectory({
  autoLoad = true,
  pageSize = 20,
  initialSort = 'last_name',
  initialSortOrder = 'asc',
  userRole = 'admin',
} = {}) {
  // Core state
  const [employees, setEmployees] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(pageSize);
  
  // Sort state
  const [sortField, setSortField] = useState(initialSort);
  const [sortOrder, setSortOrder] = useState(initialSortOrder);
  
  // Filter state
  const [filters, setFilters] = useState({
    search: '',
    departmentId: null,
    locationId: null,
    employmentStatus: 'active',
    employmentType: null,
  });
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchSuggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  
  // History and saved filters
  const [searchHistory, setSearchHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('employeeSearchHistory') || '[]');
    } catch {
      return [];
    }
  });
  const [savedFilters, setSavedFilters] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('employeeSavedFilters') || '[]');
    } catch {
      return [];
    }
  });
  
  // Loading states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Refs
  const cacheRef = useRef(new Map());
  const searchTimeoutRef = useRef(null);
  const abortControllerRef = useRef(null);

  // =========================================================================
  // Computed Values
  // =========================================================================

  const totalPages = useMemo(() => {
    return Math.ceil(totalCount / itemsPerPage);
  }, [totalCount, itemsPerPage]);

  const hasNextPage = useMemo(() => {
    return currentPage < totalPages;
  }, [currentPage, totalPages]);

  const hasPreviousPage = useMemo(() => {
    return currentPage > 1;
  }, [currentPage]);

  const pagination = useMemo(() => ({
    page: currentPage,
    pageSize: itemsPerPage,
    totalItems: totalCount,
    totalPages,
    hasNext: hasNextPage,
    hasPrevious: hasPreviousPage,
  }), [currentPage, itemsPerPage, totalCount, totalPages, hasNextPage, hasPreviousPage]);

  // =========================================================================
  // Cache Management
  // =========================================================================

  const getCacheKey = useCallback((params) => {
    return JSON.stringify({
      page: params.page,
      pageSize: params.pageSize,
      sortField: params.sortField,
      sortOrder: params.sortOrder,
      filters: params.filters,
    });
  }, []);

  const getFromCache = useCallback((key) => {
    const cached = cacheRef.current.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data;
    }
    return null;
  }, []);

  const setCache = useCallback((key, data) => {
    cacheRef.current.set(key, {
      data,
      timestamp: Date.now(),
    });
  }, []);

  const clearCache = useCallback(() => {
    cacheRef.current.clear();
  }, []);

  // =========================================================================
  // Data Loading
  // =========================================================================

  const loadDirectory = useCallback(async (options = {}) => {
    const {
      page = currentPage,
      size = itemsPerPage,
      sort = sortField,
      order = sortOrder,
      filterParams = filters,
      useCache = true,
    } = options;

    // Check cache
    const cacheKey = getCacheKey({
      page,
      pageSize: size,
      sortField: sort,
      sortOrder: order,
      filters: filterParams,
    });

    if (useCache) {
      const cached = getFromCache(cacheKey);
      if (cached) {
        setEmployees(cached.employees);
        setTotalCount(cached.totalCount);
        return cached;
      }
    }

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const queryParams = new URLSearchParams({
        page: String(page),
        page_size: String(size),
        sort_by: sort,
        sort_order: order,
      });

      if (filterParams.search) {
        queryParams.append('search', filterParams.search);
      }
      if (filterParams.departmentId) {
        queryParams.append('department', String(filterParams.departmentId));
      }
      if (filterParams.locationId) {
        queryParams.append('location', String(filterParams.locationId));
      }
      if (filterParams.employmentStatus) {
        queryParams.append('status', filterParams.employmentStatus);
      }
      if (filterParams.employmentType) {
        queryParams.append('employment_type', filterParams.employmentType);
      }

      const response = await fetch(`${API_BASE_URL}?${queryParams.toString()}`, {
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
        },
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`Failed to load directory: ${response.status}`);
      }

      const result = await response.json();
      const employeesData = result.data || result.employees || result;
      const paginationData = result.pagination || {};

      const data = {
        employees: Array.isArray(employeesData) ? employeesData : [],
        totalCount: paginationData.total_items || employeesData.length || 0,
      };

      // Update cache
      setCache(cacheKey, data);

      setEmployees(data.employees);
      setTotalCount(data.totalCount);

      return data;
    } catch (err) {
      if (err.name === 'AbortError') {
        return null; // Request was cancelled
      }
      const errorMessage = err.message || 'Failed to load directory';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, [currentPage, itemsPerPage, sortField, sortOrder, filters, userRole, getCacheKey, getFromCache, setCache]);

  // Auto-load on mount and when dependencies change
  useEffect(() => {
    if (autoLoad) {
      loadDirectory();
    }
  }, [autoLoad]); // Only on mount for autoLoad

  // Reload when pagination/sort/filters change
  useEffect(() => {
    loadDirectory();
  }, [currentPage, itemsPerPage, sortField, sortOrder, filters]);

  // =========================================================================
  // Search Operations
  // =========================================================================

  const search = useCallback((query) => {
    setSearchQuery(query);
    setFilters((prev) => ({ ...prev, search: query }));
    setCurrentPage(1); // Reset to first page on search
  }, []);

  const loadSuggestions = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setSuggestions([]);
      return;
    }

    setIsSearching(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/suggestions?q=${encodeURIComponent(query)}&limit=5`,
        {
          headers: { 'X-User-Role': userRole },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setSuggestions(data || []);
      }
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    } finally {
      setIsSearching(false);
    }
  }, [userRole]);

  const debouncedSearch = useCallback((query) => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(() => {
      search(query);
      loadSuggestions(query);
    }, 300);
  }, [search, loadSuggestions]);

  const addToSearchHistory = useCallback((query) => {
    if (!query || query.trim() === '') return;

    setSearchHistory((prev) => {
      const filtered = prev.filter((item) => item !== query);
      const updated = [query, ...filtered].slice(0, MAX_SEARCH_HISTORY);
      localStorage.setItem('employeeSearchHistory', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const clearSearchHistory = useCallback(() => {
    setSearchHistory([]);
    localStorage.removeItem('employeeSearchHistory');
  }, []);

  // =========================================================================
  // Filter Operations
  // =========================================================================

  const updateFilter = useCallback((filterName, value) => {
    setFilters((prev) => ({
      ...prev,
      [filterName]: value,
    }));
    setCurrentPage(1); // Reset to first page on filter change
  }, []);

  const updateFilters = useCallback((newFilters) => {
    setFilters((prev) => ({
      ...prev,
      ...newFilters,
    }));
    setCurrentPage(1);
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({
      search: '',
      departmentId: null,
      locationId: null,
      employmentStatus: 'active',
      employmentType: null,
    });
    setSearchQuery('');
    setCurrentPage(1);
  }, []);

  const saveCurrentFilters = useCallback((name) => {
    const filterConfig = {
      id: Date.now(),
      name,
      filters: { ...filters },
      createdAt: new Date().toISOString(),
    };

    setSavedFilters((prev) => {
      const updated = [filterConfig, ...prev].slice(0, MAX_SAVED_FILTERS);
      localStorage.setItem('employeeSavedFilters', JSON.stringify(updated));
      return updated;
    });
  }, [filters]);

  const applySavedFilter = useCallback((filterId) => {
    const saved = savedFilters.find((f) => f.id === filterId);
    if (saved) {
      setFilters(saved.filters);
      setSearchQuery(saved.filters.search || '');
      setCurrentPage(1);
    }
  }, [savedFilters]);

  const deleteSavedFilter = useCallback((filterId) => {
    setSavedFilters((prev) => {
      const updated = prev.filter((f) => f.id !== filterId);
      localStorage.setItem('employeeSavedFilters', JSON.stringify(updated));
      return updated;
    });
  }, []);

  // =========================================================================
  // Sorting
  // =========================================================================

  const sort = useCallback((field, order = 'asc') => {
    setSortField(field);
    setSortOrder(order);
    setCurrentPage(1);
  }, []);

  const toggleSort = useCallback((field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
    setCurrentPage(1);
  }, [sortField]);

  // =========================================================================
  // Pagination
  // =========================================================================

  const goToPage = useCallback((page) => {
    const targetPage = Math.max(1, Math.min(page, totalPages));
    setCurrentPage(targetPage);
  }, [totalPages]);

  const nextPage = useCallback(() => {
    if (hasNextPage) {
      setCurrentPage((prev) => prev + 1);
    }
  }, [hasNextPage]);

  const previousPage = useCallback(() => {
    if (hasPreviousPage) {
      setCurrentPage((prev) => prev - 1);
    }
  }, [hasPreviousPage]);

  const changePageSize = useCallback((size) => {
    setItemsPerPage(size);
    setCurrentPage(1);
  }, []);

  // =========================================================================
  // Export Operations
  // =========================================================================

  const exportToCSV = useCallback(async (options = {}) => {
    const {
      fields = null,
      includeAllPages = true,
      useCurrentFilters = true,
    } = options;

    try {
      const queryParams = new URLSearchParams();
      
      if (fields) {
        queryParams.append('fields', fields.join(','));
      }
      
      if (useCurrentFilters) {
        if (filters.search) queryParams.append('search', filters.search);
        if (filters.departmentId) queryParams.append('department_ids', String(filters.departmentId));
        if (filters.locationId) queryParams.append('location_ids', String(filters.locationId));
        if (filters.employmentStatus) queryParams.append('employment_status', filters.employmentStatus);
      }

      const response = await fetch(`${API_BASE_URL}/export?${queryParams.toString()}`, {
        headers: {
          'X-User-Role': userRole,
        },
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Get filename from headers
      const disposition = response.headers.get('Content-Disposition');
      const filenameMatch = disposition?.match(/filename=(.+)/);
      const filename = filenameMatch ? filenameMatch[1] : 'employees_export.csv';

      // Download file
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      return true;
    } catch (err) {
      setError('Export failed: ' + err.message);
      return false;
    }
  }, [filters, userRole]);

  // =========================================================================
  // Return Value
  // =========================================================================

  return {
    // Data
    employees,
    totalCount,

    // Pagination
    pagination,
    currentPage,
    totalPages,
    hasNextPage,
    hasPreviousPage,

    // Sort
    sortField,
    sortOrder,

    // Filters
    filters,
    searchQuery,
    searchSuggestions,
    searchHistory,
    savedFilters,

    // Loading states
    loading,
    isSearching,
    error,

    // Data loading
    loadDirectory,
    refresh: () => loadDirectory({ useCache: false }),

    // Search
    search,
    debouncedSearch,
    loadSuggestions,
    addToSearchHistory,
    clearSearchHistory,

    // Filters
    updateFilter,
    updateFilters,
    clearFilters,
    saveCurrentFilters,
    applySavedFilter,
    deleteSavedFilter,

    // Sorting
    sort,
    toggleSort,

    // Pagination
    goToPage,
    nextPage,
    previousPage,
    changePageSize,

    // Export
    exportToCSV,

    // Cache
    clearCache,
  };
}

export default useEmployeeDirectory;

