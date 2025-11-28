/**
 * Employee Service
 * 
 * API service for employee directory and search operations.
 */

const API_BASE_URL = '/api/v1';

/**
 * Employee directory and search service.
 */
class EmployeeService {
  /**
   * Get paginated employee directory listing.
   * 
   * @param {Object} params - Query parameters
   * @param {number} params.page - Page number (1-indexed)
   * @param {number} params.pageSize - Number of items per page
   * @param {string} params.search - Search query
   * @param {string} params.department - Department filter
   * @param {string} params.location - Location filter
   * @param {string} params.status - Employment status filter
   * @param {string} params.sortBy - Field to sort by
   * @param {string} params.sortOrder - Sort direction ('asc' or 'desc')
   * @returns {Promise<Object>} Paginated employee data
   */
  async getDirectory({
    page = 1,
    pageSize = 20,
    search = '',
    department = '',
    location = '',
    status = 'active',
    sortBy = 'lastName',
    sortOrder = 'asc',
  } = {}) {
    const params = new URLSearchParams({
      page: page.toString(),
      pageSize: pageSize.toString(),
      sortBy,
      sortOrder,
    });

    if (search) params.append('search', search);
    if (department) params.append('department', department);
    if (location) params.append('location', location);
    if (status) params.append('status', status);

    const response = await fetch(`${API_BASE_URL}/employees/directory?${params}`);

    if (!response.ok) {
      throw new Error('Failed to fetch employee directory');
    }

    return response.json();
  }

  /**
   * Search employees with advanced options.
   * 
   * @param {Object} params - Search parameters
   * @param {string} params.query - Search query (supports fuzzy matching)
   * @param {Object} params.filters - Field-specific filters
   * @param {number} params.limit - Maximum results to return
   * @param {boolean} params.fuzzy - Enable fuzzy matching
   * @returns {Promise<Object>} Search results with relevance scores
   */
  async searchEmployees({
    query = '',
    filters = {},
    limit = 50,
    fuzzy = true,
  } = {}) {
    const response = await fetch(`${API_BASE_URL}/employees/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        filters,
        limit,
        fuzzy,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to search employees');
    }

    return response.json();
  }

  /**
   * Get search suggestions based on partial query.
   * 
   * @param {string} query - Partial search query
   * @param {number} limit - Maximum suggestions to return
   * @returns {Promise<Array>} Search suggestions
   */
  async getSearchSuggestions(query, limit = 5) {
    if (!query || query.length < 2) {
      return [];
    }

    const params = new URLSearchParams({
      q: query,
      limit: limit.toString(),
    });

    const response = await fetch(`${API_BASE_URL}/employees/suggestions?${params}`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Get available departments for filtering.
   * 
   * @returns {Promise<Array>} List of departments
   */
  async getDepartments() {
    const response = await fetch(`${API_BASE_URL}/departments`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Get available locations for filtering.
   * 
   * @returns {Promise<Array>} List of locations
   */
  async getLocations() {
    const response = await fetch(`${API_BASE_URL}/locations`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Export directory data in specified format.
   * 
   * @param {Object} params - Export parameters
   * @param {string} params.format - Export format ('csv', 'xlsx', 'pdf')
   * @param {Object} params.filters - Applied filters
   * @param {Array} params.fields - Fields to include in export
   * @returns {Promise<Blob>} Exported file as blob
   */
  async exportDirectory({
    format = 'csv',
    filters = {},
    fields = ['name', 'email', 'department', 'jobTitle', 'phone'],
  } = {}) {
    const response = await fetch(`${API_BASE_URL}/employees/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        format,
        filters,
        fields,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to export directory');
    }

    return response.blob();
  }

  /**
   * Save a search configuration for later use.
   * 
   * @param {Object} searchConfig - Search configuration to save
   * @param {string} searchConfig.name - Name for the saved search
   * @param {string} searchConfig.query - Search query
   * @param {Object} searchConfig.filters - Applied filters
   * @returns {Promise<Object>} Saved search with ID
   */
  async saveSearch({ name, query, filters }) {
    const response = await fetch(`${API_BASE_URL}/employees/saved-searches`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, query, filters }),
    });

    if (!response.ok) {
      throw new Error('Failed to save search');
    }

    return response.json();
  }

  /**
   * Get user's saved searches.
   * 
   * @returns {Promise<Array>} List of saved searches
   */
  async getSavedSearches() {
    const response = await fetch(`${API_BASE_URL}/employees/saved-searches`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Delete a saved search.
   * 
   * @param {string} searchId - ID of the saved search to delete
   * @returns {Promise<void>}
   */
  async deleteSavedSearch(searchId) {
    const response = await fetch(`${API_BASE_URL}/employees/saved-searches/${searchId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete saved search');
    }
  }

  /**
   * Get recent search history.
   * 
   * @param {number} limit - Maximum history items to return
   * @returns {Promise<Array>} Recent searches
   */
  async getRecentSearches(limit = 10) {
    const params = new URLSearchParams({ limit: limit.toString() });
    const response = await fetch(`${API_BASE_URL}/employees/recent-searches?${params}`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Clear recent search history.
   * 
   * @returns {Promise<void>}
   */
  async clearRecentSearches() {
    const response = await fetch(`${API_BASE_URL}/employees/recent-searches`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to clear search history');
    }
  }

  /**
   * Get organizational hierarchy for an employee.
   * 
   * @param {string} employeeId - Employee ID
   * @returns {Promise<Object>} Hierarchy data (manager, direct reports, team)
   */
  async getEmployeeHierarchy(employeeId) {
    const response = await fetch(`${API_BASE_URL}/employees/${employeeId}/hierarchy`);

    if (!response.ok) {
      throw new Error('Failed to fetch employee hierarchy');
    }

    return response.json();
  }
}

export const employeeService = new EmployeeService();
export default employeeService;

