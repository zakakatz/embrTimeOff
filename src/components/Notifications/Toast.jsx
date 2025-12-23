/**
 * Toast - Individual toast notification component
 * 
 * Displays a single toast notification with auto-dismiss and action support
 */

import React, { useEffect, useState, useCallback } from 'react';
import styles from './Notifications.module.css';

/**
 * Toast notification types
 */
export const ToastType = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
};

/**
 * Toast component
 * @param {Object} props
 * @param {string} props.id - Unique toast ID
 * @param {string} props.type - Toast type (success, error, warning, info)
 * @param {string} props.title - Toast title
 * @param {string} props.message - Toast message
 * @param {number} props.duration - Auto-dismiss duration in ms (0 for no auto-dismiss)
 * @param {Function} props.onDismiss - Handler for dismissing toast
 * @param {Object} props.action - Action button config { label, onClick }
 * @param {boolean} props.showProgress - Show progress bar
 */
export const Toast = ({
  id,
  type = ToastType.INFO,
  title,
  message,
  duration = 5000,
  onDismiss,
  action,
  showProgress = true,
}) => {
  const [isExiting, setIsExiting] = useState(false);
  const [progress, setProgress] = useState(100);
  const [isPaused, setIsPaused] = useState(false);
  
  // Handle dismiss with animation
  const handleDismiss = useCallback(() => {
    setIsExiting(true);
    setTimeout(() => {
      if (onDismiss) onDismiss(id);
    }, 300); // Match exit animation duration
  }, [id, onDismiss]);
  
  // Auto-dismiss timer
  useEffect(() => {
    if (duration <= 0 || isPaused) return;
    
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(remaining);
      
      if (remaining <= 0) {
        clearInterval(interval);
        handleDismiss();
      }
    }, 50);
    
    return () => clearInterval(interval);
  }, [duration, isPaused, handleDismiss]);
  
  // Pause on hover
  const handleMouseEnter = () => setIsPaused(true);
  const handleMouseLeave = () => setIsPaused(false);
  
  // Get icon based on type
  const getIcon = () => {
    switch (type) {
      case ToastType.SUCCESS:
        return <SuccessIcon />;
      case ToastType.ERROR:
        return <ErrorIcon />;
      case ToastType.WARNING:
        return <WarningIcon />;
      case ToastType.INFO:
      default:
        return <InfoIcon />;
    }
  };
  
  return (
    <div
      className={`
        ${styles.toast}
        ${styles[`toast-${type}`]}
        ${isExiting ? styles.toastExiting : ''}
      `}
      role="alert"
      aria-live="polite"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className={styles.toastIcon}>{getIcon()}</div>
      
      <div className={styles.toastContent}>
        {title && <div className={styles.toastTitle}>{title}</div>}
        {message && <div className={styles.toastMessage}>{message}</div>}
        
        {action && (
          <button
            type="button"
            className={styles.toastAction}
            onClick={() => {
              action.onClick?.();
              handleDismiss();
            }}
          >
            {action.label}
          </button>
        )}
      </div>
      
      <button
        type="button"
        className={styles.toastClose}
        onClick={handleDismiss}
        aria-label="Dismiss notification"
      >
        <CloseIcon />
      </button>
      
      {showProgress && duration > 0 && (
        <div className={styles.toastProgress}>
          <div
            className={styles.toastProgressBar}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
};

/**
 * ToastContainer - Container for multiple toasts
 * @param {Object} props
 * @param {Array} props.toasts - Array of toast objects
 * @param {Function} props.onDismiss - Handler for dismissing toasts
 * @param {string} props.position - Position (top-right, top-left, bottom-right, bottom-left, top-center, bottom-center)
 */
export const ToastContainer = ({
  toasts = [],
  onDismiss,
  position = 'top-right',
}) => {
  if (toasts.length === 0) return null;
  
  return (
    <div
      className={`${styles.toastContainer} ${styles[`position-${position}`]}`}
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <Toast key={toast.id} {...toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

// Icons
const SuccessIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const ErrorIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);

const WarningIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const InfoIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </svg>
);

const CloseIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export default Toast;

