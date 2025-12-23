/**
 * StepNavigation - Navigation buttons for multi-step form
 * 
 * Provides previous/next/submit buttons with loading states
 */

import React from 'react';
import styles from './MultiStepForm.module.css';

/**
 * StepNavigation component
 * @param {Object} props
 * @param {boolean} props.isFirstStep - Whether on first step
 * @param {boolean} props.isLastStep - Whether on last step
 * @param {Function} props.onPrevious - Handler for previous button
 * @param {Function} props.onNext - Handler for next button
 * @param {Function} props.onSubmit - Handler for submit button
 * @param {Function} props.onSaveDraft - Handler for save draft button
 * @param {boolean} props.isSubmitting - Whether form is submitting
 * @param {boolean} props.isValidating - Whether step is validating
 * @param {string} props.submitButtonText - Text for submit button
 * @param {string} props.nextButtonText - Text for next button
 * @param {string} props.previousButtonText - Text for previous button
 * @param {boolean} props.isDirty - Whether form has unsaved changes
 */
export const StepNavigation = ({
  isFirstStep = false,
  isLastStep = false,
  onPrevious,
  onNext,
  onSubmit,
  onSaveDraft,
  isSubmitting = false,
  isValidating = false,
  submitButtonText = 'Submit',
  nextButtonText = 'Continue',
  previousButtonText = 'Back',
  isDirty = false,
}) => {
  const isLoading = isSubmitting || isValidating;
  
  return (
    <div className={styles.stepNavigation}>
      <div className={styles.navigationLeft}>
        {!isFirstStep && (
          <button
            type="button"
            onClick={onPrevious}
            disabled={isLoading}
            className={`${styles.navButton} ${styles.navButtonSecondary}`}
          >
            <ChevronLeftIcon />
            {previousButtonText}
          </button>
        )}
      </div>
      
      <div className={styles.navigationRight}>
        {onSaveDraft && isDirty && (
          <button
            type="button"
            onClick={onSaveDraft}
            disabled={isLoading}
            className={`${styles.navButton} ${styles.navButtonTertiary}`}
          >
            <SaveIcon />
            Save Draft
          </button>
        )}
        
        {isLastStep ? (
          <button
            type="submit"
            onClick={onSubmit}
            disabled={isLoading}
            className={`${styles.navButton} ${styles.navButtonPrimary}`}
          >
            {isSubmitting ? (
              <>
                <LoadingSpinner />
                Submitting...
              </>
            ) : (
              <>
                {submitButtonText}
                <CheckIcon />
              </>
            )}
          </button>
        ) : (
          <button
            type="button"
            onClick={onNext}
            disabled={isLoading}
            className={`${styles.navButton} ${styles.navButtonPrimary}`}
          >
            {isValidating ? (
              <>
                <LoadingSpinner />
                Validating...
              </>
            ) : (
              <>
                {nextButtonText}
                <ChevronRightIcon />
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};

// Icons
const ChevronLeftIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const CheckIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const SaveIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </svg>
);

const LoadingSpinner = () => (
  <svg
    className={styles.loadingSpinner}
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

export default StepNavigation;

