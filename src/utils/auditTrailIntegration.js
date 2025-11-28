/**
 * Audit Trail Integration
 * 
 * Utilities for integrating with the audit trail system.
 */

const AUDIT_API_URL = '/api/v1/audit';

/**
 * Log an audit event
 */
export async function logAuditEvent(event) {
  try {
    const response = await fetch(AUDIT_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: event.action,
        employeeId: event.employeeId,
        changes: event.changes,
        metadata: {
          timestamp: new Date().toISOString(),
          approvalId: event.approvalId,
          userAgent: navigator.userAgent,
        },
      }),
    });

    if (!response.ok) {
      console.error('Failed to log audit event');
    }

    return response.ok;
  } catch (error) {
    console.error('Error logging audit event:', error);
    return false;
  }
}

/**
 * Get audit history for an employee
 */
export async function getAuditHistory(employeeId, options = {}) {
  const params = new URLSearchParams({
    limit: options.limit || 50,
    offset: options.offset || 0,
  });

  if (options.startDate) {
    params.append('startDate', options.startDate);
  }
  if (options.endDate) {
    params.append('endDate', options.endDate);
  }
  if (options.fieldName) {
    params.append('fieldName', options.fieldName);
  }

  try {
    const response = await fetch(
      `${AUDIT_API_URL}/employee/${employeeId}?${params}`
    );

    if (!response.ok) {
      return [];
    }

    return response.json();
  } catch (error) {
    console.error('Error fetching audit history:', error);
    return [];
  }
}

/**
 * Get activity summary for an employee
 */
export async function getActivitySummary(employeeId, days = 30) {
  try {
    const response = await fetch(
      `${AUDIT_API_URL}/employee/${employeeId}/summary?days=${days}`
    );

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch (error) {
    console.error('Error fetching activity summary:', error);
    return null;
  }
}

/**
 * Format audit entry for display
 */
export function formatAuditEntry(entry) {
  return {
    id: entry.id,
    action: formatAction(entry.action),
    fieldName: entry.changedField,
    previousValue: entry.previousValue,
    newValue: entry.newValue,
    changedBy: entry.changedByName || 'Unknown',
    timestamp: new Date(entry.changeTimestamp).toLocaleString(),
    isRecent: isRecent(entry.changeTimestamp),
  };
}

/**
 * Format action type for display
 */
function formatAction(action) {
  const actionLabels = {
    CREATE: 'Created',
    UPDATE: 'Updated',
    DELETE: 'Deleted',
    profile_updated: 'Profile Updated',
    profile_viewed: 'Profile Viewed',
  };
  return actionLabels[action] || action;
}

/**
 * Check if timestamp is recent (within last 24 hours)
 */
function isRecent(timestamp) {
  const now = new Date();
  const eventTime = new Date(timestamp);
  const hoursDiff = (now - eventTime) / (1000 * 60 * 60);
  return hoursDiff < 24;
}

export default {
  logAuditEvent,
  getAuditHistory,
  getActivitySummary,
  formatAuditEntry,
};

