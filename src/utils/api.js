/**
 * API Utilities for Employee Import/Export
 * 
 * Centralized API calls for import and export operations.
 * These stubs will be connected to the backend API implementation.
 */

const DEFAULT_API_BASE = '/api/employees';

/**
 * Create headers for API requests
 */
function createHeaders(additionalHeaders = {}) {
  return {
    'Content-Type': 'application/json',
    'X-User-Role': 'admin', // For development - would come from auth in production
    ...additionalHeaders,
  };
}

/**
 * Handle API response errors
 */
async function handleResponse(response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || `API Error: ${response.status}`);
  }
  return response.json();
}

// =============================================================================
// Import API Functions
// =============================================================================

/**
 * Create a new import job by uploading a CSV file
 */
export async function createImportJob(file, options = {}, apiBase = DEFAULT_API_BASE) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('allow_partial_import', options.allowPartialImport ?? true);
  formData.append('delimiter', options.delimiter || ',');

  const response = await fetch(`${apiBase}/import`, {
    method: 'POST',
    headers: {
      'X-User-Role': 'admin',
    },
    body: formData,
  });

  return handleResponse(response);
}

/**
 * Validate import data for an existing import job
 */
export async function validateImportJob(importId, file, apiBase = DEFAULT_API_BASE) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${apiBase}/import/${importId}/validate`, {
    method: 'POST',
    headers: {
      'X-User-Role': 'admin',
    },
    body: formData,
  });

  return handleResponse(response);
}

/**
 * Process an import job
 */
export async function processImportJob(importId, file, apiBase = DEFAULT_API_BASE) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${apiBase}/import/${importId}/process`, {
    method: 'POST',
    headers: {
      'X-User-Role': 'admin',
    },
    body: formData,
  });

  return handleResponse(response);
}

/**
 * Get import job status
 */
export async function getImportStatus(importId, apiBase = DEFAULT_API_BASE) {
  const response = await fetch(`${apiBase}/import/${importId}/status`, {
    method: 'GET',
    headers: createHeaders(),
  });

  return handleResponse(response);
}

/**
 * Download import template
 */
export function downloadImportTemplate() {
  const template = [
    'employee_id,email,first_name,last_name,hire_date,job_title,department_id,employment_status',
    'EMP001,john.doe@example.com,John,Doe,2024-01-15,Software Engineer,1,active',
    'EMP002,jane.smith@example.com,Jane,Smith,2024-02-01,Product Manager,2,active',
  ].join('\n');

  const blob = new Blob([template], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'employee_import_template.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// =============================================================================
// Export API Functions
// =============================================================================

/**
 * Get available export fields based on user permissions
 */
export async function getExportFields(apiBase = DEFAULT_API_BASE) {
  const response = await fetch(`${apiBase}/export/fields`, {
    method: 'GET',
    headers: createHeaders(),
  });

  return handleResponse(response);
}

/**
 * Export employees to CSV
 */
export async function exportEmployees(options = {}, apiBase = DEFAULT_API_BASE) {
  const params = new URLSearchParams();
  
  if (options.fields?.length) {
    params.append('fields', options.fields.join(','));
  }
  if (options.excludeFields?.length) {
    params.append('exclude_fields', options.excludeFields.join(','));
  }
  if (options.includeAll) {
    params.append('include_all', 'true');
  }
  if (options.departmentIds?.length) {
    params.append('department_ids', options.departmentIds.join(','));
  }
  if (options.locationIds?.length) {
    params.append('location_ids', options.locationIds.join(','));
  }
  if (options.employmentStatus?.length) {
    params.append('employment_status', options.employmentStatus.join(','));
  }
  if (options.isActive !== undefined) {
    params.append('is_active', options.isActive.toString());
  }
  if (options.includeHeaders !== undefined) {
    params.append('include_headers', options.includeHeaders.toString());
  }
  if (options.delimiter) {
    params.append('delimiter', options.delimiter);
  }
  if (options.filenamePrefix) {
    params.append('filename_prefix', options.filenamePrefix);
  }

  const response = await fetch(`${apiBase}/export?${params.toString()}`, {
    method: 'GET',
    headers: {
      'X-User-Role': 'admin',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || `Export failed: ${response.status}`);
  }

  // Get filename from Content-Disposition header
  const disposition = response.headers.get('Content-Disposition');
  const filenameMatch = disposition?.match(/filename=(.+)/);
  const filename = filenameMatch ? filenameMatch[1] : 'employees_export.csv';

  // Get metadata from headers
  const totalRecords = parseInt(response.headers.get('X-Total-Records') || '0', 10);
  const exportedFields = (response.headers.get('X-Exported-Fields') || '').split(',');

  // Get blob content
  const blob = await response.blob();

  return {
    blob,
    filename,
    totalRecords,
    exportedFields,
  };
}

/**
 * Export employees using POST method (for complex filters)
 */
export async function exportEmployeesPost(options = {}, apiBase = DEFAULT_API_BASE) {
  const requestBody = {
    field_selection: {
      include_all: options.includeAll || false,
      fields: options.fields || [],
      exclude_fields: options.excludeFields || [],
    },
    filters: {
      department_ids: options.departmentIds || [],
      location_ids: options.locationIds || [],
      employment_status: options.employmentStatus || [],
      is_active: options.isActive,
    },
    include_headers: options.includeHeaders ?? true,
    delimiter: options.delimiter || ',',
    filename_prefix: options.filenamePrefix || 'employees_export',
  };

  const response = await fetch(`${apiBase}/export`, {
    method: 'POST',
    headers: createHeaders(),
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || `Export failed: ${response.status}`);
  }

  const disposition = response.headers.get('Content-Disposition');
  const filenameMatch = disposition?.match(/filename=(.+)/);
  const filename = filenameMatch ? filenameMatch[1] : 'employees_export.csv';

  const totalRecords = parseInt(response.headers.get('X-Total-Records') || '0', 10);
  const exportedFields = (response.headers.get('X-Exported-Fields') || '').split(',');

  const blob = await response.blob();

  return {
    blob,
    filename,
    totalRecords,
    exportedFields,
  };
}

/**
 * Trigger file download from blob
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// =============================================================================
// Reference Data API Functions
// =============================================================================

/**
 * Get departments list
 */
export async function getDepartments(apiBase = '/api') {
  const response = await fetch(`${apiBase}/departments`, {
    method: 'GET',
    headers: createHeaders(),
  });

  return handleResponse(response);
}

/**
 * Get locations list
 */
export async function getLocations(apiBase = '/api') {
  const response = await fetch(`${apiBase}/locations`, {
    method: 'GET',
    headers: createHeaders(),
  });

  return handleResponse(response);
}

