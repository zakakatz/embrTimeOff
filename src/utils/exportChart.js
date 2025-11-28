/**
 * Export Chart Utilities
 * 
 * Functions for exporting organizational chart to various formats.
 */

/**
 * Export chart to PNG image.
 * 
 * @param {HTMLElement} chartElement - The chart container element
 * @param {Object} options - Export options
 * @returns {Promise<Blob>} PNG image as blob
 */
export async function exportToPng(chartElement, options = {}) {
  const {
    scale = 2,
    backgroundColor = '#ffffff',
    filename = 'organizational-chart.png',
  } = options;

  // Create canvas
  const canvas = document.createElement('canvas');
  const rect = chartElement.getBoundingClientRect();
  
  canvas.width = rect.width * scale;
  canvas.height = rect.height * scale;
  
  const ctx = canvas.getContext('2d');
  ctx.scale(scale, scale);
  ctx.fillStyle = backgroundColor;
  ctx.fillRect(0, 0, rect.width, rect.height);

  // Use html2canvas if available, otherwise basic implementation
  if (typeof html2canvas !== 'undefined') {
    const capturedCanvas = await html2canvas(chartElement, {
      scale,
      backgroundColor,
      logging: false,
    });
    return new Promise(resolve => {
      capturedCanvas.toBlob(resolve, 'image/png');
    });
  }

  // Fallback: Create SVG representation
  const svg = chartElementToSvg(chartElement);
  const svgData = new XMLSerializer().serializeToString(svg);
  const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
  
  return svgBlob;
}

/**
 * Export chart to SVG.
 * 
 * @param {HTMLElement} chartElement - The chart container element
 * @param {Object} options - Export options
 * @returns {Blob} SVG as blob
 */
export function exportToSvg(chartElement, options = {}) {
  const { filename = 'organizational-chart.svg' } = options;
  
  // Find SVG element or create one
  let svg = chartElement.querySelector('svg');
  
  if (!svg) {
    svg = chartElementToSvg(chartElement);
  } else {
    svg = svg.cloneNode(true);
  }
  
  // Add XML declaration and styling
  const svgData = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
${new XMLSerializer().serializeToString(svg)}`;
  
  return new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
}

/**
 * Export chart data to CSV.
 * 
 * @param {Array} flattenedNodes - Array of flattened chart nodes
 * @param {Object} options - Export options
 * @returns {Blob} CSV as blob
 */
export function exportToCsv(flattenedNodes, options = {}) {
  const {
    filename = 'organizational-chart.csv',
    fields = ['name', 'jobTitle', 'department', 'email', 'manager', 'level'],
  } = options;
  
  // Build header
  const headers = {
    name: 'Name',
    jobTitle: 'Job Title',
    department: 'Department',
    email: 'Email',
    manager: 'Reports To',
    level: 'Level',
    employeeId: 'Employee ID',
    location: 'Location',
  };
  
  const selectedHeaders = fields.map(f => headers[f] || f);
  
  // Build rows
  const rows = flattenedNodes.map(node => {
    return fields.map(field => {
      switch (field) {
        case 'name':
          return `${node.firstName || ''} ${node.lastName || ''}`.trim();
        case 'department':
          return node.department?.name || '';
        case 'manager':
          if (node.manager) {
            return `${node.manager.firstName || ''} ${node.manager.lastName || ''}`.trim();
          }
          return '';
        case 'location':
          return node.location?.name || '';
        default:
          return node[field] || '';
      }
    });
  });
  
  // Create CSV content
  const csvContent = [
    selectedHeaders.join(','),
    ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')),
  ].join('\n');
  
  return new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
}

/**
 * Export chart data to JSON.
 * 
 * @param {Object} hierarchyData - The hierarchy tree data
 * @param {Object} options - Export options
 * @returns {Blob} JSON as blob
 */
export function exportToJson(hierarchyData, options = {}) {
  const { filename = 'organizational-chart.json', pretty = true } = options;
  
  const jsonContent = pretty
    ? JSON.stringify(hierarchyData, null, 2)
    : JSON.stringify(hierarchyData);
  
  return new Blob([jsonContent], { type: 'application/json;charset=utf-8' });
}

/**
 * Download a blob as a file.
 * 
 * @param {Blob} blob - The blob to download
 * @param {string} filename - The filename for download
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Export and download chart.
 * 
 * @param {string} format - Export format ('png', 'svg', 'csv', 'json')
 * @param {Object} data - Chart data (element for image, nodes/hierarchy for data)
 * @param {Object} options - Export options
 */
export async function exportChart(format, data, options = {}) {
  let blob;
  let filename;
  
  switch (format.toLowerCase()) {
    case 'png':
      blob = await exportToPng(data.element, options);
      filename = options.filename || 'organizational-chart.png';
      break;
    case 'svg':
      blob = exportToSvg(data.element, options);
      filename = options.filename || 'organizational-chart.svg';
      break;
    case 'csv':
      blob = exportToCsv(data.nodes, options);
      filename = options.filename || 'organizational-chart.csv';
      break;
    case 'json':
      blob = exportToJson(data.hierarchy, options);
      filename = options.filename || 'organizational-chart.json';
      break;
    default:
      throw new Error(`Unsupported export format: ${format}`);
  }
  
  downloadBlob(blob, filename);
}

/**
 * Helper: Convert chart element to SVG representation.
 * 
 * @param {HTMLElement} element - The chart element
 * @returns {SVGElement} SVG representation
 */
function chartElementToSvg(element) {
  const rect = element.getBoundingClientRect();
  
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', rect.width);
  svg.setAttribute('height', rect.height);
  svg.setAttribute('viewBox', `0 0 ${rect.width} ${rect.height}`);
  svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  
  // Add background
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('width', '100%');
  bg.setAttribute('height', '100%');
  bg.setAttribute('fill', '#ffffff');
  svg.appendChild(bg);
  
  // Add text placeholder
  const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text.setAttribute('x', '50%');
  text.setAttribute('y', '50%');
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('fill', '#666');
  text.textContent = 'Organizational Chart Export';
  svg.appendChild(text);
  
  return svg;
}

export default {
  exportToPng,
  exportToSvg,
  exportToCsv,
  exportToJson,
  exportChart,
  downloadBlob,
};

