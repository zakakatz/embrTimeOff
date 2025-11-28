/**
 * Chart Data Transformer
 * 
 * Utilities for transforming organizational data into chart-friendly format.
 */

/**
 * Transform flat employee array to hierarchical tree structure.
 * 
 * @param {Array} employees - Array of employee objects
 * @param {number|null} rootId - ID of the root employee (or null for top-level)
 * @returns {Object|null} Hierarchical tree structure
 */
export function buildHierarchyTree(employees, rootId = null) {
  const employeeMap = new Map();
  
  // Create map of all employees
  employees.forEach(emp => {
    employeeMap.set(emp.id, {
      ...emp,
      directReports: [],
    });
  });
  
  // Build tree structure
  let root = null;
  
  employeeMap.forEach(emp => {
    if (emp.managerId) {
      const manager = employeeMap.get(emp.managerId);
      if (manager) {
        manager.directReports.push(emp);
      }
    }
    
    if (rootId) {
      if (emp.id === rootId) {
        root = emp;
      }
    } else if (!emp.managerId) {
      // No manager = top-level employee
      if (!root) root = emp;
    }
  });
  
  return root;
}

/**
 * Flatten a hierarchy tree to array.
 * 
 * @param {Object} root - Root node of the tree
 * @param {number} maxDepth - Maximum depth to flatten
 * @returns {Array} Flattened array of nodes with level info
 */
export function flattenHierarchy(root, maxDepth = Infinity) {
  const nodes = [];
  
  const traverse = (node, level = 0, parentId = null) => {
    if (!node || level > maxDepth) return;
    
    nodes.push({
      ...node,
      level,
      parentId,
      hasChildren: node.directReports?.length > 0,
      childCount: node.directReports?.length || 0,
    });
    
    if (node.directReports) {
      node.directReports.forEach(child => {
        traverse(child, level + 1, node.id);
      });
    }
  };
  
  traverse(root);
  return nodes;
}

/**
 * Calculate node positions for tree layout.
 * 
 * @param {Object} root - Root node of the tree
 * @param {Object} options - Layout options
 * @returns {Map} Map of node IDs to positions
 */
export function calculateTreeLayout(root, options = {}) {
  const {
    nodeWidth = 200,
    nodeHeight = 100,
    horizontalSpacing = 40,
    verticalSpacing = 80,
  } = options;
  
  const positions = new Map();
  
  // Calculate subtree widths
  const calculateWidth = (node) => {
    if (!node) return 0;
    
    if (!node.directReports || node.directReports.length === 0) {
      return nodeWidth;
    }
    
    const childrenWidth = node.directReports.reduce((sum, child) => {
      return sum + calculateWidth(child) + horizontalSpacing;
    }, -horizontalSpacing);
    
    return Math.max(nodeWidth, childrenWidth);
  };
  
  // Assign positions
  const assignPositions = (node, x, y) => {
    if (!node) return;
    
    positions.set(node.id, {
      x: x + nodeWidth / 2,
      y,
      width: nodeWidth,
      height: nodeHeight,
    });
    
    if (node.directReports && node.directReports.length > 0) {
      const totalWidth = calculateWidth(node);
      let currentX = x + (nodeWidth - totalWidth) / 2;
      
      node.directReports.forEach(child => {
        const childWidth = calculateWidth(child);
        assignPositions(child, currentX, y + nodeHeight + verticalSpacing);
        currentX += childWidth + horizontalSpacing;
      });
    }
  };
  
  assignPositions(root, 0, 0);
  return positions;
}

/**
 * Calculate connector lines between nodes.
 * 
 * @param {Map} positions - Map of node positions
 * @param {Object} root - Root node of the tree
 * @returns {Array} Array of line objects with start/end points
 */
export function calculateConnectorLines(positions, root) {
  const lines = [];
  
  const traverse = (node) => {
    if (!node || !node.directReports) return;
    
    const parentPos = positions.get(node.id);
    if (!parentPos) return;
    
    node.directReports.forEach(child => {
      const childPos = positions.get(child.id);
      if (!childPos) return;
      
      // Create an elbow connector
      const midY = parentPos.y + parentPos.height + 
        (childPos.y - parentPos.y - parentPos.height) / 2;
      
      lines.push({
        id: `${node.id}-${child.id}`,
        parentId: node.id,
        childId: child.id,
        points: [
          { x: parentPos.x, y: parentPos.y + parentPos.height },
          { x: parentPos.x, y: midY },
          { x: childPos.x, y: midY },
          { x: childPos.x, y: childPos.y },
        ],
      });
      
      traverse(child);
    });
  };
  
  traverse(root);
  return lines;
}

/**
 * Get ancestors of a node.
 * 
 * @param {Array} flatNodes - Flattened array of nodes
 * @param {number} nodeId - ID of the target node
 * @returns {Array} Array of ancestor nodes from root to parent
 */
export function getAncestors(flatNodes, nodeId) {
  const nodeMap = new Map(flatNodes.map(n => [n.id, n]));
  const ancestors = [];
  
  let current = nodeMap.get(nodeId);
  while (current && current.parentId) {
    const parent = nodeMap.get(current.parentId);
    if (parent) {
      ancestors.unshift(parent);
      current = parent;
    } else {
      break;
    }
  }
  
  return ancestors;
}

/**
 * Get descendants of a node.
 * 
 * @param {Object} node - Node to get descendants of
 * @param {number} maxDepth - Maximum depth to traverse
 * @returns {Array} Array of descendant nodes
 */
export function getDescendants(node, maxDepth = Infinity) {
  const descendants = [];
  
  const traverse = (n, depth = 0) => {
    if (!n || depth > maxDepth) return;
    
    if (n.directReports) {
      n.directReports.forEach(child => {
        descendants.push(child);
        traverse(child, depth + 1);
      });
    }
  };
  
  traverse(node);
  return descendants;
}

/**
 * Find a node by ID in the tree.
 * 
 * @param {Object} root - Root node of the tree
 * @param {number} nodeId - ID of the node to find
 * @returns {Object|null} The found node or null
 */
export function findNodeById(root, nodeId) {
  if (!root) return null;
  if (root.id === nodeId) return root;
  
  if (root.directReports) {
    for (const child of root.directReports) {
      const found = findNodeById(child, nodeId);
      if (found) return found;
    }
  }
  
  return null;
}

/**
 * Get the path from root to a specific node.
 * 
 * @param {Object} root - Root node of the tree
 * @param {number} nodeId - ID of the target node
 * @returns {Array} Array of nodes from root to target
 */
export function getPathToNode(root, nodeId) {
  const path = [];
  
  const findPath = (node, target) => {
    if (!node) return false;
    
    path.push(node);
    
    if (node.id === target) return true;
    
    if (node.directReports) {
      for (const child of node.directReports) {
        if (findPath(child, target)) return true;
      }
    }
    
    path.pop();
    return false;
  };
  
  findPath(root, nodeId);
  return path;
}

/**
 * Count total nodes in a tree.
 * 
 * @param {Object} root - Root node of the tree
 * @returns {number} Total node count
 */
export function countNodes(root) {
  if (!root) return 0;
  
  let count = 1;
  if (root.directReports) {
    root.directReports.forEach(child => {
      count += countNodes(child);
    });
  }
  
  return count;
}

/**
 * Calculate tree depth.
 * 
 * @param {Object} root - Root node of the tree
 * @returns {number} Maximum depth of the tree
 */
export function calculateTreeDepth(root) {
  if (!root) return 0;
  
  if (!root.directReports || root.directReports.length === 0) {
    return 1;
  }
  
  return 1 + Math.max(...root.directReports.map(calculateTreeDepth));
}

export default {
  buildHierarchyTree,
  flattenHierarchy,
  calculateTreeLayout,
  calculateConnectorLines,
  getAncestors,
  getDescendants,
  findNodeById,
  getPathToNode,
  countNodes,
  calculateTreeDepth,
};

