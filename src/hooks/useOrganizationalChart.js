/**
 * useOrganizationalChart Hook
 * 
 * Custom hook for managing organizational chart state,
 * hierarchy loading, relationship mapping, and navigation.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

const API_BASE_URL = '/api/v1';

/**
 * Hook for organizational chart state management.
 * 
 * @param {Object} options - Configuration options
 * @param {number} options.rootEmployeeId - Starting employee for the chart
 * @param {number} options.maxDepth - Maximum hierarchy depth (default: 3)
 * @param {boolean} options.autoLoad - Auto-load data on mount (default: true)
 * @returns {Object} Chart state and control functions
 */
export function useOrganizationalChart({
  rootEmployeeId = null,
  maxDepth = 3,
  autoLoad = true,
} = {}) {
  // Core state
  const [hierarchyData, setHierarchyData] = useState(null);
  const [visibleNodes, setVisibleNodes] = useState(new Set());
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [selectedNode, setSelectedNode] = useState(null);
  const [focusedNodeId, setFocusedNodeId] = useState(rootEmployeeId);
  
  // Loading states
  const [loading, setLoading] = useState(false);
  const [loadingNodes, setLoadingNodes] = useState(new Set());
  const [error, setError] = useState(null);
  
  // View state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [viewDepth, setViewDepth] = useState(maxDepth);
  
  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [departmentFilter, setDepartmentFilter] = useState(null);
  const [highlightedNodeId, setHighlightedNodeId] = useState(null);
  
  // Refs for caching
  const nodeCache = useRef(new Map());
  const loadingPromises = useRef(new Map());

  // =========================================================================
  // Data Loading
  // =========================================================================

  /**
   * Load hierarchy data for a specific employee.
   */
  const loadHierarchy = useCallback(async (employeeId, depth = maxDepth) => {
    if (!employeeId) return null;
    
    // Check cache first
    const cacheKey = `${employeeId}-${depth}`;
    if (nodeCache.current.has(cacheKey)) {
      return nodeCache.current.get(cacheKey);
    }
    
    // Check if already loading
    if (loadingPromises.current.has(cacheKey)) {
      return loadingPromises.current.get(cacheKey);
    }
    
    const loadPromise = (async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/employees/${employeeId}/hierarchy?depth=${depth}`
        );
        
        if (!response.ok) {
          throw new Error('Failed to load hierarchy');
        }
        
        const data = await response.json();
        nodeCache.current.set(cacheKey, data);
        return data;
      } finally {
        loadingPromises.current.delete(cacheKey);
      }
    })();
    
    loadingPromises.current.set(cacheKey, loadPromise);
    return loadPromise;
  }, [maxDepth]);

  /**
   * Load the initial chart data.
   */
  const loadChart = useCallback(async (startEmployeeId = rootEmployeeId) => {
    if (!startEmployeeId) {
      setError('No employee ID provided');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await loadHierarchy(startEmployeeId, viewDepth);
      setHierarchyData(data);
      setFocusedNodeId(startEmployeeId);
      
      // Initialize expanded nodes (expand first two levels)
      const initialExpanded = new Set();
      if (data) {
        initialExpanded.add(data.id);
        if (data.directReports) {
          data.directReports.forEach(report => initialExpanded.add(report.id));
        }
      }
      setExpandedNodes(initialExpanded);
      
    } catch (err) {
      setError(err.message || 'Failed to load organizational chart');
    } finally {
      setLoading(false);
    }
  }, [rootEmployeeId, viewDepth, loadHierarchy]);

  /**
   * Load children for a specific node (progressive loading).
   */
  const loadNodeChildren = useCallback(async (nodeId) => {
    if (loadingNodes.has(nodeId)) return;
    
    setLoadingNodes(prev => new Set([...prev, nodeId]));
    
    try {
      const data = await loadHierarchy(nodeId, 1);
      
      // Update hierarchy data with new children
      setHierarchyData(prev => {
        if (!prev) return prev;
        return updateNodeInHierarchy(prev, nodeId, data);
      });
      
      // Expand the node
      setExpandedNodes(prev => new Set([...prev, nodeId]));
      
    } catch (err) {
      console.error('Failed to load children:', err);
    } finally {
      setLoadingNodes(prev => {
        const next = new Set(prev);
        next.delete(nodeId);
        return next;
      });
    }
  }, [loadingNodes, loadHierarchy]);

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad && rootEmployeeId) {
      loadChart(rootEmployeeId);
    }
  }, [autoLoad, rootEmployeeId, loadChart]);

  // =========================================================================
  // Navigation
  // =========================================================================

  /**
   * Navigate to a specific employee in the chart.
   */
  const navigateToEmployee = useCallback(async (employeeId) => {
    setLoading(true);
    try {
      const data = await loadHierarchy(employeeId, viewDepth);
      setHierarchyData(data);
      setFocusedNodeId(employeeId);
      setSelectedNode(null);
      setHighlightedNodeId(employeeId);
      
      // Reset view
      setZoom(1);
      setPan({ x: 0, y: 0 });
      
      // Auto-clear highlight
      setTimeout(() => setHighlightedNodeId(null), 2000);
    } catch (err) {
      setError('Failed to navigate to employee');
    } finally {
      setLoading(false);
    }
  }, [viewDepth, loadHierarchy]);

  /**
   * Navigate up to manager.
   */
  const navigateToManager = useCallback(async () => {
    if (!hierarchyData?.manager) return;
    await navigateToEmployee(hierarchyData.manager.id);
  }, [hierarchyData, navigateToEmployee]);

  /**
   * Expand a node to show its direct reports.
   */
  const expandNode = useCallback((nodeId) => {
    setExpandedNodes(prev => new Set([...prev, nodeId]));
  }, []);

  /**
   * Collapse a node to hide its direct reports.
   */
  const collapseNode = useCallback((nodeId) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      next.delete(nodeId);
      return next;
    });
  }, []);

  /**
   * Toggle node expansion.
   */
  const toggleNode = useCallback((nodeId, hasUnloadedChildren = false) => {
    if (expandedNodes.has(nodeId)) {
      collapseNode(nodeId);
    } else if (hasUnloadedChildren) {
      loadNodeChildren(nodeId);
    } else {
      expandNode(nodeId);
    }
  }, [expandedNodes, collapseNode, expandNode, loadNodeChildren]);

  // =========================================================================
  // View Controls
  // =========================================================================

  /**
   * Set zoom level (0.25 - 2).
   */
  const setZoomLevel = useCallback((level) => {
    setZoom(Math.max(0.25, Math.min(2, level)));
  }, []);

  /**
   * Zoom in by step.
   */
  const zoomIn = useCallback(() => {
    setZoom(prev => Math.min(prev + 0.25, 2));
  }, []);

  /**
   * Zoom out by step.
   */
  const zoomOut = useCallback(() => {
    setZoom(prev => Math.max(prev - 0.25, 0.25));
  }, []);

  /**
   * Reset view to default.
   */
  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  /**
   * Center view on a specific node.
   */
  const centerOnNode = useCallback((nodeId) => {
    // Implementation depends on chart rendering
    // This would calculate the position of the node and set pan accordingly
    setHighlightedNodeId(nodeId);
    setTimeout(() => setHighlightedNodeId(null), 2000);
  }, []);

  // =========================================================================
  // Search and Filter
  // =========================================================================

  /**
   * Search within the chart.
   */
  const searchInChart = useCallback(async (query) => {
    setSearchQuery(query);
    
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/employees/search?q=${encodeURIComponent(query)}&limit=10`
      );
      
      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.data || data);
      }
    } catch (err) {
      console.error('Search failed:', err);
      setSearchResults([]);
    }
  }, []);

  /**
   * Filter by department.
   */
  const filterByDepartment = useCallback((departmentId) => {
    setDepartmentFilter(departmentId);
  }, []);

  /**
   * Clear all filters.
   */
  const clearFilters = useCallback(() => {
    setSearchQuery('');
    setSearchResults([]);
    setDepartmentFilter(null);
  }, []);

  // =========================================================================
  // Selection
  // =========================================================================

  /**
   * Select a node for quick view.
   */
  const selectNode = useCallback((node) => {
    setSelectedNode(node);
  }, []);

  /**
   * Clear node selection.
   */
  const clearSelection = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // =========================================================================
  // Computed Values
  // =========================================================================

  /**
   * Flatten hierarchy for rendering.
   */
  const flattenedNodes = useMemo(() => {
    if (!hierarchyData) return [];
    
    const nodes = [];
    const flatten = (node, level = 0, parentId = null) => {
      const isExpanded = expandedNodes.has(node.id);
      const isFiltered = departmentFilter && 
        node.department?.id !== departmentFilter;
      
      if (!isFiltered) {
        nodes.push({
          ...node,
          level,
          parentId,
          isExpanded,
          isSelected: selectedNode?.id === node.id,
          isHighlighted: highlightedNodeId === node.id,
          isLoading: loadingNodes.has(node.id),
        });
      }
      
      if (isExpanded && node.directReports) {
        node.directReports.forEach(child => {
          flatten(child, level + 1, node.id);
        });
      }
    };
    
    flatten(hierarchyData);
    return nodes;
  }, [hierarchyData, expandedNodes, departmentFilter, selectedNode, highlightedNodeId, loadingNodes]);

  /**
   * Get visible level range based on current view.
   */
  const levelRange = useMemo(() => {
    const levels = flattenedNodes.map(n => n.level);
    return {
      min: Math.min(...levels, 0),
      max: Math.max(...levels, viewDepth),
    };
  }, [flattenedNodes, viewDepth]);

  // =========================================================================
  // Return Value
  // =========================================================================

  return {
    // Data
    hierarchyData,
    flattenedNodes,
    selectedNode,
    focusedNodeId,
    
    // Loading states
    loading,
    loadingNodes,
    error,
    
    // View state
    zoom,
    pan,
    viewDepth,
    levelRange,
    
    // Search/Filter state
    searchQuery,
    searchResults,
    departmentFilter,
    highlightedNodeId,
    
    // Data loading
    loadChart,
    loadNodeChildren,
    refresh: () => loadChart(focusedNodeId),
    
    // Navigation
    navigateToEmployee,
    navigateToManager,
    expandNode,
    collapseNode,
    toggleNode,
    
    // View controls
    setZoom: setZoomLevel,
    zoomIn,
    zoomOut,
    setPan,
    resetView,
    centerOnNode,
    setViewDepth,
    
    // Search/Filter
    searchInChart,
    filterByDepartment,
    clearFilters,
    
    // Selection
    selectNode,
    clearSelection,
  };
}

// =========================================================================
// Helper Functions
// =========================================================================

/**
 * Update a node in the hierarchy tree.
 */
function updateNodeInHierarchy(root, nodeId, newData) {
  if (root.id === nodeId) {
    return { ...root, ...newData };
  }
  
  if (root.directReports) {
    return {
      ...root,
      directReports: root.directReports.map(child =>
        updateNodeInHierarchy(child, nodeId, newData)
      ),
    };
  }
  
  return root;
}

export default useOrganizationalChart;

