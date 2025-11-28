/**
 * Profile Service
 * 
 * API service for employee profile operations.
 */

const API_BASE_URL = '/api/v1';

class ProfileService {
  /**
   * Get employee profile by ID
   */
  async getEmployee(employeeId) {
    const response = await fetch(`${API_BASE_URL}/employees/${employeeId}`);
    
    if (!response.ok) {
      throw new Error('Failed to fetch employee');
    }
    
    return response.json();
  }

  /**
   * Update employee profile
   */
  async updateEmployee(employeeId, data, approvalData = null) {
    const payload = {
      ...data,
      ...(approvalData && { approval: approvalData }),
    };

    const response = await fetch(`${API_BASE_URL}/employees/${employeeId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'Failed to update employee');
    }

    return response.json();
  }

  /**
   * Check for conflicts before update
   */
  async checkConflicts(employeeId, changes) {
    const response = await fetch(
      `${API_BASE_URL}/employees/${employeeId}/check-conflicts`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ changes }),
      }
    );

    if (!response.ok) {
      return { hasConflicts: false };
    }

    return response.json();
  }

  /**
   * Get recent profile changes
   */
  async getRecentChanges(employeeId, limit = 10) {
    const response = await fetch(
      `${API_BASE_URL}/employees/${employeeId}/changes?limit=${limit}`
    );

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Search employees (for manager assignment)
   */
  async searchEmployees(query, limit = 10) {
    const response = await fetch(
      `${API_BASE_URL}/employees/search?q=${encodeURIComponent(query)}&limit=${limit}`
    );

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Get employee policies
   */
  async getEmployeePolicies(employeeId) {
    const response = await fetch(
      `${API_BASE_URL}/employees/${employeeId}/policies`
    );

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Get departments list
   */
  async getDepartments() {
    const response = await fetch(`${API_BASE_URL}/departments`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Get locations list
   */
  async getLocations() {
    const response = await fetch(`${API_BASE_URL}/locations`);

    if (!response.ok) {
      return [];
    }

    return response.json();
  }

  /**
   * Submit approval request for sensitive changes
   */
  async submitApprovalRequest(employeeId, changes, justification) {
    const response = await fetch(
      `${API_BASE_URL}/employees/${employeeId}/approval-requests`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          changes,
          justification,
        }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to submit approval request');
    }

    return response.json();
  }
}

export const profileService = new ProfileService();
export default profileService;

