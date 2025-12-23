/**
 * ProgressIndicator - Step progress display component
 * 
 * Shows current progress through multi-step form with visual indicators
 */

import React from 'react';
import styles from './MultiStepForm.module.css';

/**
 * ProgressIndicator component
 * @param {Object} props
 * @param {Array} props.steps - Array of step info { id, title, description?, status }
 * @param {number} props.currentStep - Current step index
 * @param {Function} props.onStepClick - Handler for clicking on a step
 * @param {boolean} props.showStepNumbers - Show step numbers
 * @param {string} props.variant - Visual variant (horizontal, vertical)
 */
export const ProgressIndicator = ({
  steps = [],
  currentStep = 0,
  onStepClick,
  showStepNumbers = true,
  variant = 'horizontal',
}) => {
  const handleStepClick = (index) => {
    if (onStepClick) {
      onStepClick(index);
    }
  };
  
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckIcon />;
      case 'error':
        return <ErrorIcon />;
      case 'current':
        return <CurrentIcon />;
      default:
        return null;
    }
  };
  
  return (
    <nav 
      className={`${styles.progressIndicator} ${styles[variant]}`}
      aria-label="Form progress"
    >
      <ol className={styles.stepList}>
        {steps.map((step, index) => {
          const isClickable = onStepClick && (step.status === 'completed' || step.status === 'current');
          
          return (
            <li
              key={step.id || index}
              className={`
                ${styles.stepItem}
                ${styles[`status-${step.status}`]}
                ${isClickable ? styles.clickable : ''}
              `}
            >
              <button
                type="button"
                className={styles.stepButton}
                onClick={() => handleStepClick(index)}
                disabled={!isClickable}
                aria-current={step.status === 'current' ? 'step' : undefined}
              >
                <span className={styles.stepIndicator}>
                  {step.status === 'completed' || step.status === 'error' ? (
                    getStatusIcon(step.status)
                  ) : (
                    showStepNumbers && <span className={styles.stepNumber}>{index + 1}</span>
                  )}
                </span>
                
                <span className={styles.stepContent}>
                  <span className={styles.stepLabel}>{step.title}</span>
                  {step.description && variant === 'vertical' && (
                    <span className={styles.stepDesc}>{step.description}</span>
                  )}
                </span>
              </button>
              
              {index < steps.length - 1 && (
                <div className={styles.stepConnector} aria-hidden="true">
                  <div 
                    className={`
                      ${styles.connectorLine}
                      ${step.status === 'completed' ? styles.connectorComplete : ''}
                    `}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ol>
      
      {/* Mobile progress bar */}
      <div className={styles.mobileProgress}>
        <div className={styles.mobileProgressText}>
          Step {currentStep + 1} of {steps.length}: {steps[currentStep]?.title}
        </div>
        <div className={styles.mobileProgressBar}>
          <div 
            className={styles.mobileProgressFill}
            style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
          />
        </div>
      </div>
    </nav>
  );
};

// Icons
const CheckIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const ErrorIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const CurrentIcon = () => (
  <span className={styles.currentDot} aria-hidden="true" />
);

export default ProgressIndicator;

