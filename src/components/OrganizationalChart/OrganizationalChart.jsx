/**
 * OrganizationalChart Component
 * 
 * Interactive organizational chart visualization with zoom, pan,
 * search, filtering, and export capabilities.
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import PropTypes from 'prop-types';
import { useOrganizationalChart } from '../../hooks/useOrganizationalChart';
import { calculateTreeLayout, calculateConnectorLines } from '../../utils/chartDataTransformer';
import { exportChart } from '../../utils/exportChart';
import OrganizationalChartNode from './OrganizationalChartNode';
import OrganizationalChartControls from './OrganizationalChartControls';
import styles from './OrganizationalChart.module.css';

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 2;
const NODE_WIDTH = 220;
const NODE_HEIGHT = 120;
const HORIZONTAL_SPACING = 40;
const VERTICAL_SPACING = 80;

export function OrganizationalChart({
  rootEmployeeId,
  maxDepth,
  onEmployeeSelect,
  onEmployeeNavigate,
  showControls,
  showMinimap,
  enableKeyboardNav,
  className,
}) {
  // Chart state from hook
  const {
    hierarchyData,
    flattenedNodes,
    selectedNode,
    loading,
    loadingNodes,
    error,
    zoom,
    pan,
    searchQuery,
    searchResults,
    departmentFilter,
    highlightedNodeId,
    loadChart,
    toggleNode,
    selectNode,
    clearSelection,
    navigateToEmployee,
    setZoom,
    zoomIn,
    zoomOut,
    setPan,
    resetView,
    searchInChart,
    filterByDepartment,
    refresh,
  } = useOrganizationalChart({
    rootEmployeeId,
    maxDepth,
    autoLoad: true,
  });

  // Local state
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [departments, setDepartments] = useState([]);
  const [quickViewNode, setQuickViewNode] = useState(null);

  // Refs
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const focusedNodeRef = useRef(null);

  // Fetch departments for filter
  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        const response = await fetch('/api/v1/departments');
        if (response.ok) {
          const data = await response.json();
          setDepartments(data);
        }
      } catch (err) {
        console.error('Failed to fetch departments:', err);
      }
    };
    fetchDepartments();
  }, []);

  // Calculate layout positions
  const { nodePositions, connectorLines, chartSize } = useMemo(() => {
    if (!hierarchyData) {
      return { nodePositions: new Map(), connectorLines: [], chartSize: { width: 0, height: 0 } };
    }

    const positions = calculateTreeLayout(hierarchyData, {
      nodeWidth: NODE_WIDTH,
      nodeHeight: NODE_HEIGHT,
      horizontalSpacing: HORIZONTAL_SPACING,
      verticalSpacing: VERTICAL_SPACING,
    });

    const lines = calculateConnectorLines(positions, hierarchyData);

    // Calculate chart bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    positions.forEach((pos) => {
      minX = Math.min(minX, pos.x - pos.width / 2);
      maxX = Math.max(maxX, pos.x + pos.width / 2);
      minY = Math.min(minY, pos.y);
      maxY = Math.max(maxY, pos.y + pos.height);
    });

    const padding = 50;
    return {
      nodePositions: positions,
      connectorLines: lines,
      chartSize: {
        width: maxX - minX + padding * 2,
        height: maxY - minY + padding * 2,
        offsetX: -minX + padding,
        offsetY: -minY + padding,
      },
    };
  }, [hierarchyData]);

  // Pan handlers
  const handlePanStart = useCallback((e) => {
    if (e.button !== 0) return; // Only left click
    
    setIsPanning(true);
    setPanStart({
      x: e.clientX - pan.x,
      y: e.clientY - pan.y,
    });
  }, [pan]);

  const handlePanMove = useCallback((e) => {
    if (!isPanning) return;
    
    setPan({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y,
    });
  }, [isPanning, panStart, setPan]);

  const handlePanEnd = useCallback(() => {
    setIsPanning(false);
  }, []);

  // Wheel zoom handler
  const handleWheel = useCallback((e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom(Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom + delta)));
    }
  }, [zoom, setZoom]);

  // Keyboard navigation
  useEffect(() => {
    if (!enableKeyboardNav) return;

    const handleKeyDown = (e) => {
      switch (e.key) {
        case '+':
        case '=':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            zoomIn();
          }
          break;
        case '-':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            zoomOut();
          }
          break;
        case '0':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            resetView();
          }
          break;
        case 'Escape':
          clearSelection();
          setQuickViewNode(null);
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [enableKeyboardNav, zoomIn, zoomOut, resetView, clearSelection]);

  // Node selection handler
  const handleNodeSelect = useCallback((node) => {
    selectNode(node);
    setQuickViewNode(node);
    onEmployeeSelect?.(node);
  }, [selectNode, onEmployeeSelect]);

  // Node navigation handler
  const handleNodeNavigate = useCallback((nodeId) => {
    navigateToEmployee(nodeId);
    onEmployeeNavigate?.(nodeId);
  }, [navigateToEmployee, onEmployeeNavigate]);

  // Export handler
  const handleExport = useCallback(async (format) => {
    try {
      await exportChart(format, {
        element: chartRef.current,
        nodes: flattenedNodes,
        hierarchy: hierarchyData,
      });
    } catch (err) {
      console.error('Export failed:', err);
    }
  }, [flattenedNodes, hierarchyData]);

  // Close quick view
  const handleCloseQuickView = useCallback(() => {
    setQuickViewNode(null);
    clearSelection();
  }, [clearSelection]);

  // Render connector lines as SVG paths
  const renderConnectors = useMemo(() => {
    return connectorLines.map((line) => {
      const pathData = line.points
        .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x + chartSize.offsetX} ${p.y + chartSize.offsetY}`)
        .join(' ');

      return (
        <path
          key={line.id}
          d={pathData}
          className={styles.connector}
          fill="none"
          strokeWidth="2"
        />
      );
    });
  }, [connectorLines, chartSize.offsetX, chartSize.offsetY]);

  // Render nodes
  const renderNodes = useMemo(() => {
    const nodes = [];

    const renderNode = (node) => {
      const pos = nodePositions.get(node.id);
      if (!pos) return null;

      const flatNode = flattenedNodes.find(n => n.id === node.id);
      const hasChildren = node.directReports && node.directReports.length > 0;
      const isExpanded = flatNode?.isExpanded ?? false;

      nodes.push(
        <div
          key={node.id}
          className={styles.nodeWrapper}
          style={{
            position: 'absolute',
            left: pos.x - pos.width / 2 + chartSize.offsetX,
            top: pos.y + chartSize.offsetY,
            width: pos.width,
            height: pos.height,
          }}
        >
          <OrganizationalChartNode
            node={node}
            isExpanded={isExpanded}
            isSelected={selectedNode?.id === node.id}
            isHighlighted={highlightedNodeId === node.id}
            isLoading={loadingNodes.has(node.id)}
            hasChildren={hasChildren}
            childCount={node.directReports?.length || 0}
            onToggle={() => toggleNode(node.id, hasChildren && !node.directReports?.length)}
            onSelect={handleNodeSelect}
            onNavigate={handleNodeNavigate}
            showQuickView={true}
          />
        </div>
      );

      // Render children if expanded
      if (isExpanded && node.directReports) {
        node.directReports.forEach(child => renderNode(child));
      }
    };

    if (hierarchyData) {
      renderNode(hierarchyData);
    }

    return nodes;
  }, [hierarchyData, nodePositions, flattenedNodes, selectedNode, highlightedNodeId, loadingNodes, chartSize.offsetX, chartSize.offsetY, toggleNode, handleNodeSelect, handleNodeNavigate]);

  if (error) {
    return (
      <div className={`${styles.chart} ${className || ''}`}>
        <div className={styles.errorState} role="alert">
          <span className={styles.errorIcon} aria-hidden="true">⚠️</span>
          <h3>Failed to Load Chart</h3>
          <p>{error}</p>
          <button
            type="button"
            className={styles.retryButton}
            onClick={() => loadChart(rootEmployeeId)}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.chart} ${className || ''}`}>
      {/* Controls */}
      {showControls && (
        <OrganizationalChartControls
          zoom={zoom}
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
          onResetView={resetView}
          searchQuery={searchQuery}
          searchResults={searchResults}
          onSearch={searchInChart}
          onSearchSelect={(result) => navigateToEmployee(result.id)}
          departments={departments}
          selectedDepartment={departmentFilter}
          onDepartmentChange={filterByDepartment}
          onExport={handleExport}
          onRefresh={refresh}
          isLoading={loading}
        />
      )}

      {/* Chart Container */}
      <div
        ref={containerRef}
        className={styles.chartContainer}
        onMouseDown={handlePanStart}
        onMouseMove={handlePanMove}
        onMouseUp={handlePanEnd}
        onMouseLeave={handlePanEnd}
        onWheel={handleWheel}
        style={{ cursor: isPanning ? 'grabbing' : 'grab' }}
        role="tree"
        aria-label="Organizational chart"
        tabIndex={0}
      >
        {loading && !hierarchyData ? (
          <div className={styles.loadingState} role="status">
            <div className={styles.loadingSpinner} />
            <span>Loading organizational chart...</span>
          </div>
        ) : (
          <div
            ref={chartRef}
            className={styles.chartContent}
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              width: chartSize.width,
              height: chartSize.height,
            }}
          >
            {/* SVG for connectors */}
            <svg
              className={styles.connectorsSvg}
              width={chartSize.width}
              height={chartSize.height}
              style={{ position: 'absolute', top: 0, left: 0 }}
            >
              {renderConnectors}
            </svg>

            {/* Nodes */}
            {renderNodes}
          </div>
        )}
      </div>

      {/* Quick View Panel */}
      {quickViewNode && (
        <aside className={styles.quickView} role="complementary" aria-label="Employee quick view">
          <div className={styles.quickViewHeader}>
            <h3>Employee Details</h3>
            <button
              type="button"
              className={styles.quickViewClose}
              onClick={handleCloseQuickView}
              aria-label="Close quick view"
            >
              ×
            </button>
          </div>
          <div className={styles.quickViewContent}>
            <div className={styles.quickViewAvatar}>
              {quickViewNode.profileImageUrl ? (
                <img src={quickViewNode.profileImageUrl} alt="" />
              ) : (
                <span>
                  {quickViewNode.firstName?.[0]}{quickViewNode.lastName?.[0]}
                </span>
              )}
            </div>
            <h4 className={styles.quickViewName}>
              {quickViewNode.preferredName || quickViewNode.firstName} {quickViewNode.lastName}
            </h4>
            {quickViewNode.jobTitle && (
              <p className={styles.quickViewTitle}>{quickViewNode.jobTitle}</p>
            )}
            {quickViewNode.department && (
              <p className={styles.quickViewDepartment}>{quickViewNode.department.name}</p>
            )}
            <div className={styles.quickViewContact}>
              {quickViewNode.email && (
                <a href={`mailto:${quickViewNode.email}`} className={styles.quickViewLink}>
                  ✉️ {quickViewNode.email}
                </a>
              )}
              {quickViewNode.phone && (
                <a href={`tel:${quickViewNode.phone}`} className={styles.quickViewLink}>
                  📞 {quickViewNode.phone}
                </a>
              )}
            </div>
            <div className={styles.quickViewActions}>
              <button
                type="button"
                className={styles.quickViewAction}
                onClick={() => handleNodeNavigate(quickViewNode.id)}
              >
                View in Chart
              </button>
              <button
                type="button"
                className={styles.quickViewAction}
                onClick={() => onEmployeeNavigate?.(quickViewNode.id)}
              >
                View Profile
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* Minimap */}
      {showMinimap && hierarchyData && (
        <div className={styles.minimap} aria-hidden="true">
          <div
            className={styles.minimapViewport}
            style={{
              transform: `translate(${-pan.x / 10}px, ${-pan.y / 10}px)`,
              width: `${100 / zoom}%`,
              height: `${100 / zoom}%`,
            }}
          />
        </div>
      )}
    </div>
  );
}

OrganizationalChart.propTypes = {
  rootEmployeeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  maxDepth: PropTypes.number,
  onEmployeeSelect: PropTypes.func,
  onEmployeeNavigate: PropTypes.func,
  showControls: PropTypes.bool,
  showMinimap: PropTypes.bool,
  enableKeyboardNav: PropTypes.bool,
  className: PropTypes.string,
};

OrganizationalChart.defaultProps = {
  rootEmployeeId: null,
  maxDepth: 3,
  onEmployeeSelect: null,
  onEmployeeNavigate: null,
  showControls: true,
  showMinimap: false,
  enableKeyboardNav: true,
  className: '',
};

export default OrganizationalChart;

