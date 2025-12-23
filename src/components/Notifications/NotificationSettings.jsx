/**
 * NotificationSettings - Settings panel for notification preferences
 * 
 * Allows users to configure:
 * - Notification sound
 * - Browser notifications
 * - Category preferences
 * - Quiet hours
 */

import React, { useState, useCallback } from 'react';
import styles from './Notifications.module.css';

/**
 * NotificationSettings component
 * @param {Object} props
 * @param {Object} props.settings - Current settings
 * @param {Function} props.onSave - Handler for saving settings
 * @param {Function} props.onClose - Handler for closing panel
 * @param {boolean} props.browserNotificationSupported - Browser notification support status
 * @param {string} props.browserNotificationPermission - Current permission status
 * @param {Function} props.onRequestPermission - Handler for requesting permission
 */
export const NotificationSettings = ({
  settings = {},
  onSave,
  onClose,
  browserNotificationSupported = true,
  browserNotificationPermission = 'default',
  onRequestPermission,
}) => {
  const [localSettings, setLocalSettings] = useState({
    soundEnabled: settings.soundEnabled ?? true,
    soundVolume: settings.soundVolume ?? 50,
    browserNotifications: settings.browserNotifications ?? false,
    categories: settings.categories ?? {
      system: true,
      mentions: true,
      updates: true,
      approvals: true,
    },
    quietHours: settings.quietHours ?? {
      enabled: false,
      start: '22:00',
      end: '08:00',
    },
    ...settings,
  });
  
  // Update setting
  const updateSetting = useCallback((key, value) => {
    setLocalSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  }, []);
  
  // Update nested setting
  const updateNestedSetting = useCallback((parent, key, value) => {
    setLocalSettings((prev) => ({
      ...prev,
      [parent]: {
        ...prev[parent],
        [key]: value,
      },
    }));
  }, []);
  
  // Handle save
  const handleSave = useCallback(() => {
    if (onSave) {
      onSave(localSettings);
    }
    if (onClose) {
      onClose();
    }
  }, [localSettings, onSave, onClose]);
  
  // Request browser notification permission
  const handleRequestPermission = useCallback(async () => {
    if (onRequestPermission) {
      const granted = await onRequestPermission();
      if (granted) {
        updateSetting('browserNotifications', true);
      }
    }
  }, [onRequestPermission, updateSetting]);
  
  return (
    <div className={styles.settingsPanel}>
      <div className={styles.settingsHeader}>
        <h3 className={styles.settingsTitle}>Notification Settings</h3>
        <button
          type="button"
          className={styles.closeButton}
          onClick={onClose}
          aria-label="Close settings"
        >
          <CloseIcon />
        </button>
      </div>
      
      <div className={styles.settingsContent}>
        {/* Sound Settings */}
        <section className={styles.settingsSection}>
          <h4 className={styles.sectionTitle}>
            <SoundIcon />
            Sound
          </h4>
          
          <div className={styles.settingRow}>
            <label className={styles.settingLabel}>
              <span>Notification sounds</span>
              <p className={styles.settingDescription}>
                Play a sound when you receive a notification
              </p>
            </label>
            <ToggleSwitch
              checked={localSettings.soundEnabled}
              onChange={(checked) => updateSetting('soundEnabled', checked)}
            />
          </div>
          
          {localSettings.soundEnabled && (
            <div className={styles.settingRow}>
              <label className={styles.settingLabel}>
                <span>Volume</span>
              </label>
              <div className={styles.volumeSlider}>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={localSettings.soundVolume}
                  onChange={(e) => updateSetting('soundVolume', Number(e.target.value))}
                  className={styles.slider}
                />
                <span className={styles.volumeValue}>{localSettings.soundVolume}%</span>
              </div>
            </div>
          )}
        </section>
        
        {/* Browser Notifications */}
        <section className={styles.settingsSection}>
          <h4 className={styles.sectionTitle}>
            <BellIcon />
            Browser Notifications
          </h4>
          
          <div className={styles.settingRow}>
            <label className={styles.settingLabel}>
              <span>Desktop notifications</span>
              <p className={styles.settingDescription}>
                Show notifications even when the browser is minimized
              </p>
            </label>
            
            {browserNotificationPermission === 'granted' ? (
              <ToggleSwitch
                checked={localSettings.browserNotifications}
                onChange={(checked) => updateSetting('browserNotifications', checked)}
              />
            ) : browserNotificationPermission === 'denied' ? (
              <span className={styles.permissionDenied}>
                Permission denied
              </span>
            ) : (
              <button
                type="button"
                className={styles.permissionButton}
                onClick={handleRequestPermission}
              >
                Enable
              </button>
            )}
          </div>
          
          {!browserNotificationSupported && (
            <p className={styles.warningText}>
              Your browser does not support desktop notifications
            </p>
          )}
        </section>
        
        {/* Category Preferences */}
        <section className={styles.settingsSection}>
          <h4 className={styles.sectionTitle}>
            <CategoryIcon />
            Categories
          </h4>
          <p className={styles.sectionDescription}>
            Choose which types of notifications you want to receive
          </p>
          
          {Object.entries(localSettings.categories).map(([category, enabled]) => (
            <div key={category} className={styles.settingRow}>
              <label className={styles.settingLabel}>
                <span>{category.charAt(0).toUpperCase() + category.slice(1)}</span>
              </label>
              <ToggleSwitch
                checked={enabled}
                onChange={(checked) => updateNestedSetting('categories', category, checked)}
              />
            </div>
          ))}
        </section>
        
        {/* Quiet Hours */}
        <section className={styles.settingsSection}>
          <h4 className={styles.sectionTitle}>
            <MoonIcon />
            Quiet Hours
          </h4>
          
          <div className={styles.settingRow}>
            <label className={styles.settingLabel}>
              <span>Enable quiet hours</span>
              <p className={styles.settingDescription}>
                Pause notifications during specified hours
              </p>
            </label>
            <ToggleSwitch
              checked={localSettings.quietHours.enabled}
              onChange={(checked) => updateNestedSetting('quietHours', 'enabled', checked)}
            />
          </div>
          
          {localSettings.quietHours.enabled && (
            <div className={styles.timeRange}>
              <div className={styles.timeInput}>
                <label>From</label>
                <input
                  type="time"
                  value={localSettings.quietHours.start}
                  onChange={(e) => updateNestedSetting('quietHours', 'start', e.target.value)}
                  className={styles.input}
                />
              </div>
              <div className={styles.timeInput}>
                <label>To</label>
                <input
                  type="time"
                  value={localSettings.quietHours.end}
                  onChange={(e) => updateNestedSetting('quietHours', 'end', e.target.value)}
                  className={styles.input}
                />
              </div>
            </div>
          )}
        </section>
      </div>
      
      <div className={styles.settingsFooter}>
        <button
          type="button"
          className={styles.cancelButton}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className={styles.saveButton}
          onClick={handleSave}
        >
          Save Changes
        </button>
      </div>
    </div>
  );
};

/**
 * ToggleSwitch component
 */
const ToggleSwitch = ({ checked, onChange, disabled = false }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    disabled={disabled}
    className={`${styles.toggle} ${checked ? styles.checked : ''}`}
    onClick={() => onChange(!checked)}
  >
    <span className={styles.toggleHandle} />
  </button>
);

// Icons
const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const SoundIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
  </svg>
);

const BellIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const CategoryIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </svg>
);

const MoonIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

export default NotificationSettings;

