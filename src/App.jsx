/**
 * Main Application Component
 * 
 * Root component that integrates employee directory and search functionality.
 */

import React, { useState, useCallback } from 'react';
import { EmployeeDirectory } from './components/EmployeeDirectory';
import { EmployeeSearch } from './components/EmployeeSearch';
import { EmployeeProfileView } from './components/EmployeeProfileView/EmployeeProfileView';
import './App.css';

const NAV_ITEMS = [
  { id: 'directory', label: 'Directory', icon: '👥' },
  { id: 'search', label: 'Search', icon: '🔍' },
];

export function App() {
  const [activeView, setActiveView] = useState('directory');
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [showProfile, setShowProfile] = useState(false);

  const handleEmployeeSelect = useCallback((employee) => {
    setSelectedEmployee(employee);
    setShowProfile(true);
  }, []);

  const handleCloseProfile = useCallback(() => {
    setShowProfile(false);
    setSelectedEmployee(null);
  }, []);

  const handleEditProfile = useCallback(() => {
    // Navigate to edit view - to be implemented
    console.log('Edit profile:', selectedEmployee?.id);
  }, [selectedEmployee]);

  return (
    <div className="app">
      {/* Navigation Header */}
      <header className="app-header">
        <div className="app-header-content">
          <div className="app-logo">
            <span className="app-logo-icon">🏢</span>
            <h1 className="app-title">Employee Management</h1>
          </div>

          <nav className="app-nav" role="navigation" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                className={`app-nav-item ${activeView === item.id ? 'app-nav-item--active' : ''}`}
                onClick={() => setActiveView(item.id)}
                aria-current={activeView === item.id ? 'page' : undefined}
              >
                <span className="app-nav-icon" aria-hidden="true">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          <div className="app-actions">
            <button className="app-user-menu" aria-label="User menu">
              <span className="app-user-avatar">JD</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {activeView === 'directory' && (
          <EmployeeDirectory
            onEmployeeSelect={handleEmployeeSelect}
            showExport={true}
            enableVirtualScroll={true}
          />
        )}

        {activeView === 'search' && (
          <EmployeeSearch
            onEmployeeSelect={handleEmployeeSelect}
            showSuggestions={true}
            showRecentSearches={true}
            showSavedSearches={true}
            showAdvancedSearch={true}
            autoFocus={true}
          />
        )}
      </main>

      {/* Employee Profile Modal/Slide-out */}
      {showProfile && selectedEmployee && (
        <div className="app-profile-overlay" onClick={handleCloseProfile}>
          <aside
            className="app-profile-panel"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Employee Profile"
            aria-modal="true"
          >
            <div className="app-profile-header">
              <h2>Employee Profile</h2>
              <button
                className="app-profile-close"
                onClick={handleCloseProfile}
                aria-label="Close profile"
              >
                ×
              </button>
            </div>
            <div className="app-profile-content">
              <EmployeeProfileView
                employeeId={selectedEmployee.id}
                onEditClick={handleEditProfile}
              />
            </div>
          </aside>
        </div>
      )}

      {/* Footer */}
      <footer className="app-footer">
        <p>Employee Management System © {new Date().getFullYear()}</p>
      </footer>
    </div>
  );
}

export default App;

