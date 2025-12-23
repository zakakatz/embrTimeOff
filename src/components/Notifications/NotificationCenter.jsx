/**
 * NotificationCenter - In-app notification center panel
 * 
 * Features:
 * - Notification list with read/unread states
 * - Mark as read functionality
 * - Categorization and filtering
 * - Action buttons for quick responses
 */

import React, { useState, useCallback, useMemo } from 'react';
import styles from './Notifications.module.css';

/**
 * Notification categories
 */
export const NotificationCategory = {
  ALL: 'all',
  SYSTEM: 'system',
  MENTIONS: 'mentions',
  UPDATES: 'updates',
  APPROVALS: 'approvals',
};

/**
 * NotificationCenter component
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether panel is open
 * @param {Function} props.onClose - Handler to close panel
 * @param {Array} props.notifications - Array of notifications
 * @param {Function} props.onMarkAsRead - Handler for marking as read
 * @param {Function} props.onMarkAllAsRead - Handler for marking all as read
 * @param {Function} props.onAction - Handler for notification actions
 * @param {Function} props.onDismiss - Handler for dismissing notification
 * @param {Function} props.onClear - Handler for clearing all notifications
 */
export const NotificationCenter = ({
  isOpen = false,
  onClose,
  notifications = [],
  onMarkAsRead,
  onMarkAllAsRead,
  onAction,
  onDismiss,
  onClear,
}) => {
  const [activeCategory, setActiveCategory] = useState(NotificationCategory.ALL);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  
  // Filter notifications
  const filteredNotifications = useMemo(() => {
    let filtered = [...notifications];
    
    if (activeCategory !== NotificationCategory.ALL) {
      filtered = filtered.filter((n) => n.category === activeCategory);
    }
    
    if (showUnreadOnly) {
      filtered = filtered.filter((n) => !n.read);
    }
    
    // Sort by timestamp descending
    return filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [notifications, activeCategory, showUnreadOnly]);
  
  // Count unread
  const unreadCount = useMemo(() => {
    return notifications.filter((n) => !n.read).length;
  }, [notifications]);
  
  // Category counts
  const categoryCounts = useMemo(() => {
    const counts = { [NotificationCategory.ALL]: notifications.length };
    notifications.forEach((n) => {
      counts[n.category] = (counts[n.category] || 0) + 1;
    });
    return counts;
  }, [notifications]);
  
  const handleNotificationClick = useCallback((notification) => {
    if (!notification.read && onMarkAsRead) {
      onMarkAsRead(notification.id);
    }
  }, [onMarkAsRead]);
  
  if (!isOpen) return null;
  
  return (
    <div className={styles.notificationCenter} role="dialog" aria-label="Notifications">
      {/* Header */}
      <div className={styles.centerHeader}>
        <h2 className={styles.centerTitle}>
          Notifications
          {unreadCount > 0 && (
            <span className={styles.unreadBadge}>{unreadCount}</span>
          )}
        </h2>
        <div className={styles.headerActions}>
          {unreadCount > 0 && (
            <button
              type="button"
              className={styles.markAllRead}
              onClick={onMarkAllAsRead}
            >
              Mark all read
            </button>
          )}
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Close notifications"
          >
            <CloseIcon />
          </button>
        </div>
      </div>
      
      {/* Filters */}
      <div className={styles.centerFilters}>
        <div className={styles.categoryTabs}>
          {Object.values(NotificationCategory).map((category) => (
            <button
              key={category}
              type="button"
              className={`
                ${styles.categoryTab}
                ${activeCategory === category ? styles.active : ''}
              `}
              onClick={() => setActiveCategory(category)}
            >
              {category.charAt(0).toUpperCase() + category.slice(1)}
              {categoryCounts[category] > 0 && (
                <span className={styles.categoryCount}>
                  {categoryCounts[category]}
                </span>
              )}
            </button>
          ))}
        </div>
        
        <label className={styles.filterToggle}>
          <input
            type="checkbox"
            checked={showUnreadOnly}
            onChange={(e) => setShowUnreadOnly(e.target.checked)}
          />
          Unread only
        </label>
      </div>
      
      {/* Notification List */}
      <div className={styles.notificationList}>
        {filteredNotifications.length === 0 ? (
          <div className={styles.emptyState}>
            <BellIcon />
            <p>No notifications</p>
          </div>
        ) : (
          filteredNotifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onClick={() => handleNotificationClick(notification)}
              onAction={onAction}
              onDismiss={onDismiss}
            />
          ))
        )}
      </div>
      
      {/* Footer */}
      {notifications.length > 0 && (
        <div className={styles.centerFooter}>
          <button
            type="button"
            className={styles.clearAll}
            onClick={onClear}
          >
            Clear all notifications
          </button>
        </div>
      )}
    </div>
  );
};

/**
 * NotificationItem component
 */
const NotificationItem = ({
  notification,
  onClick,
  onAction,
  onDismiss,
}) => {
  const { id, type, title, message, timestamp, read, actions, avatar } = notification;
  
  // Format timestamp
  const formatTime = (ts) => {
    const date = new Date(ts);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
    return date.toLocaleDateString();
  };
  
  return (
    <div
      className={`
        ${styles.notificationItem}
        ${!read ? styles.unread : ''}
        ${styles[`type-${type}`]}
      `}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className={styles.itemLeft}>
        {avatar ? (
          <img src={avatar} alt="" className={styles.itemAvatar} />
        ) : (
          <div className={styles.itemIcon}>
            <NotificationTypeIcon type={type} />
          </div>
        )}
      </div>
      
      <div className={styles.itemContent}>
        <div className={styles.itemHeader}>
          <span className={styles.itemTitle}>{title}</span>
          <span className={styles.itemTime}>{formatTime(timestamp)}</span>
        </div>
        
        {message && <p className={styles.itemMessage}>{message}</p>}
        
        {actions && actions.length > 0 && (
          <div className={styles.itemActions}>
            {actions.map((action, index) => (
              <button
                key={index}
                type="button"
                className={`
                  ${styles.actionButton}
                  ${action.primary ? styles.primary : ''}
                `}
                onClick={(e) => {
                  e.stopPropagation();
                  onAction?.(id, action.type);
                }}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
      
      <button
        type="button"
        className={styles.dismissButton}
        onClick={(e) => {
          e.stopPropagation();
          onDismiss?.(id);
        }}
        aria-label="Dismiss"
      >
        <CloseIcon />
      </button>
      
      {!read && <span className={styles.unreadDot} />}
    </div>
  );
};

/**
 * NotificationBadge - Badge counter for header
 */
export const NotificationBadge = ({ count, onClick }) => {
  return (
    <button
      type="button"
      className={styles.notificationBadge}
      onClick={onClick}
      aria-label={`${count} notifications`}
    >
      <BellIcon />
      {count > 0 && (
        <span className={styles.badgeCount}>
          {count > 99 ? '99+' : count}
        </span>
      )}
    </button>
  );
};

// Icons
const CloseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const BellIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const NotificationTypeIcon = ({ type }) => {
  switch (type) {
    case 'success':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      );
    case 'error':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      );
    case 'warning':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      );
    default:
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
      );
  }
};

export default NotificationCenter;

