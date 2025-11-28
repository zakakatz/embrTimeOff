/**
 * ProfileActions Component
 * 
 * Contextual actions for employee profile management.
 */

import React, { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeProfileView.module.css';

export function ProfileActions({ employeeId, onEditClick, hasEditPermission }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setMenuOpen(false);
    }
  };

  return (
    <div className={styles.profileActions} ref={menuRef}>
      {hasEditPermission && (
        <button
          className={styles.primaryAction}
          onClick={() => onEditClick(employeeId)}
          aria-label="Edit employee profile"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M12.146.854a.5.5 0 0 1 .708 0l2.292 2.292a.5.5 0 0 1 0 .708l-9.5 9.5a.5.5 0 0 1-.168.11l-4 1.5a.5.5 0 0 1-.65-.65l1.5-4a.5.5 0 0 1 .11-.168l9.5-9.5zM11.207 2L14 4.793 12.793 6 10 3.207 11.207 2zM9.5 3.707L2 11.207V12h.793L10.5 4.293 9.5 3.707z"/>
          </svg>
          Edit Profile
        </button>
      )}

      <div className={styles.moreActionsContainer}>
        <button
          className={styles.moreActionsButton}
          onClick={() => setMenuOpen(!menuOpen)}
          onKeyDown={handleKeyDown}
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          aria-label="More actions"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M10 6a2 2 0 110-4 2 2 0 010 4zm0 6a2 2 0 110-4 2 2 0 010 4zm0 6a2 2 0 110-4 2 2 0 010 4z"/>
          </svg>
        </button>

        {menuOpen && (
          <ul
            className={styles.actionsMenu}
            role="menu"
            aria-label="Profile actions"
          >
            <li role="menuitem">
              <button onClick={() => { setMenuOpen(false); }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M8 1a7 7 0 100 14A7 7 0 008 1zM7 4h2v5H7V4zm0 6h2v2H7v-2z"/>
                </svg>
                View Policies
              </button>
            </li>
            <li role="menuitem">
              <button onClick={() => { setMenuOpen(false); }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M8 1a2 2 0 012 2v1h3a1 1 0 011 1v9a1 1 0 01-1 1H3a1 1 0 01-1-1V5a1 1 0 011-1h3V3a2 2 0 012-2zm0 1a1 1 0 00-1 1v1h2V3a1 1 0 00-1-1z"/>
                </svg>
                Org Chart
              </button>
            </li>
            <li role="menuitem">
              <button onClick={() => { setMenuOpen(false); }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M14 1H2a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V2a1 1 0 00-1-1zM2 0a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2V2a2 2 0 00-2-2H2z"/>
                  <path d="M4 4h8v1H4V4zm0 3h8v1H4V7zm0 3h5v1H4v-1z"/>
                </svg>
                View Activity Log
              </button>
            </li>
            <li className={styles.menuDivider} role="separator" />
            <li role="menuitem">
              <button onClick={() => { setMenuOpen(false); }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm3.5 9.5l-4-2.5V4h1v3.5l3.5 2.2-.5.8z"/>
                </svg>
                Schedule Meeting
              </button>
            </li>
            <li role="menuitem">
              <button onClick={() => { setMenuOpen(false); }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M0 4a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H2a2 2 0 01-2-2V4zm2-1a1 1 0 00-1 1v.217l7 4.2 7-4.2V4a1 1 0 00-1-1H2zm13 2.383l-6.586 3.95a1 1 0 01-1.028 0L1 5.383V12a1 1 0 001 1h12a1 1 0 001-1V5.383z"/>
                </svg>
                Send Message
              </button>
            </li>
          </ul>
        )}
      </div>
    </div>
  );
}

ProfileActions.propTypes = {
  employeeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  onEditClick: PropTypes.func,
  hasEditPermission: PropTypes.bool,
};

ProfileActions.defaultProps = {
  onEditClick: () => {},
  hasEditPermission: false,
};

export default ProfileActions;

