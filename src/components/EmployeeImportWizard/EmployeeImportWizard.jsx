/**
 * Employee Import Wizard Component
 * 
 * Provides a step-by-step workflow for importing employee data from CSV files.
 * Includes file upload, field mapping, validation preview, and import execution.
 */

import React, { useState, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import styles from './EmployeeImportWizard.module.css';
import { FileUploadStep } from './steps/FileUploadStep';
import { FieldMappingStep } from './steps/FieldMappingStep';
import { ValidationPreviewStep } from './steps/ValidationPreviewStep';
import { ImportExecutionStep } from './steps/ImportExecutionStep';

const WIZARD_STEPS = [
  { id: 'upload', label: 'Upload File', icon: '📁' },
  { id: 'mapping', label: 'Map Fields', icon: '🔗' },
  { id: 'preview', label: 'Preview', icon: '👁️' },
  { id: 'import', label: 'Import', icon: '✅' },
];

const INITIAL_STATE = {
  file: null,
  fileContent: null,
  parsedData: null,
  fieldMappings: {},
  validationResults: null,
  importJob: null,
  allowPartialImport: true,
};

export function EmployeeImportWizard({
  isOpen,
  onClose,
  onImportComplete,
  apiBaseUrl = '/api/employees',
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [wizardState, setWizardState] = useState(INITIAL_STATE);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Reset wizard state
  const resetWizard = useCallback(() => {
    setCurrentStep(0);
    setWizardState(INITIAL_STATE);
    setError(null);
    setIsLoading(false);
  }, []);

  // Handle close with reset
  const handleClose = useCallback(() => {
    resetWizard();
    onClose?.();
  }, [resetWizard, onClose]);

  // Navigate to next step
  const goToNextStep = useCallback(() => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep((prev) => prev + 1);
      setError(null);
    }
  }, [currentStep]);

  // Navigate to previous step
  const goToPreviousStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
      setError(null);
    }
  }, [currentStep]);

  // Handle file upload completion
  const handleFileUpload = useCallback(async (file, parsedData) => {
    setWizardState((prev) => ({
      ...prev,
      file,
      parsedData,
      fieldMappings: parsedData?.suggestedMappings || {},
    }));
    goToNextStep();
  }, [goToNextStep]);

  // Handle field mapping changes
  const handleMappingChange = useCallback((mappings) => {
    setWizardState((prev) => ({
      ...prev,
      fieldMappings: mappings,
    }));
  }, []);

  // Handle validation completion
  const handleValidationComplete = useCallback((validationResults) => {
    setWizardState((prev) => ({
      ...prev,
      validationResults,
    }));
  }, []);

  // Handle partial import toggle
  const handlePartialImportToggle = useCallback((allow) => {
    setWizardState((prev) => ({
      ...prev,
      allowPartialImport: allow,
    }));
  }, []);

  // Handle import completion
  const handleImportComplete = useCallback((result) => {
    onImportComplete?.(result);
  }, [onImportComplete]);

  // Get current step component
  const renderStepContent = useMemo(() => {
    const stepProps = {
      wizardState,
      setWizardState,
      setIsLoading,
      setError,
      apiBaseUrl,
    };

    switch (WIZARD_STEPS[currentStep]?.id) {
      case 'upload':
        return (
          <FileUploadStep
            {...stepProps}
            onFileUpload={handleFileUpload}
          />
        );
      case 'mapping':
        return (
          <FieldMappingStep
            {...stepProps}
            onMappingChange={handleMappingChange}
            onNext={goToNextStep}
            onBack={goToPreviousStep}
          />
        );
      case 'preview':
        return (
          <ValidationPreviewStep
            {...stepProps}
            onValidationComplete={handleValidationComplete}
            onPartialImportToggle={handlePartialImportToggle}
            onNext={goToNextStep}
            onBack={goToPreviousStep}
          />
        );
      case 'import':
        return (
          <ImportExecutionStep
            {...stepProps}
            onImportComplete={handleImportComplete}
            onClose={handleClose}
            onBack={goToPreviousStep}
          />
        );
      default:
        return null;
    }
  }, [
    currentStep,
    wizardState,
    apiBaseUrl,
    handleFileUpload,
    handleMappingChange,
    handleValidationComplete,
    handlePartialImportToggle,
    handleImportComplete,
    handleClose,
    goToNextStep,
    goToPreviousStep,
  ]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div
        className={styles.wizard}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-wizard-title"
      >
        {/* Header */}
        <header className={styles.header}>
          <h2 id="import-wizard-title" className={styles.title}>
            <span className={styles.titleIcon}>📤</span>
            Import Employees
          </h2>
          <button
            className={styles.closeButton}
            onClick={handleClose}
            aria-label="Close import wizard"
          >
            ×
          </button>
        </header>

        {/* Progress Steps */}
        <nav className={styles.progress} aria-label="Import progress">
          {WIZARD_STEPS.map((step, index) => (
            <div
              key={step.id}
              className={`${styles.step} ${
                index < currentStep
                  ? styles.stepCompleted
                  : index === currentStep
                  ? styles.stepActive
                  : styles.stepPending
              }`}
            >
              <div className={styles.stepIndicator}>
                {index < currentStep ? (
                  <span className={styles.stepCheck}>✓</span>
                ) : (
                  <span className={styles.stepNumber}>{index + 1}</span>
                )}
              </div>
              <span className={styles.stepLabel}>{step.label}</span>
              {index < WIZARD_STEPS.length - 1 && (
                <div className={styles.stepConnector} />
              )}
            </div>
          ))}
        </nav>

        {/* Error Display */}
        {error && (
          <div className={styles.error} role="alert">
            <span className={styles.errorIcon}>⚠️</span>
            <span className={styles.errorMessage}>{error}</span>
            <button
              className={styles.errorDismiss}
              onClick={() => setError(null)}
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        {/* Step Content */}
        <div className={styles.content}>
          {isLoading && (
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner} />
              <span>Processing...</span>
            </div>
          )}
          {renderStepContent}
        </div>
      </div>
    </div>
  );
}

EmployeeImportWizard.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func,
  apiBaseUrl: PropTypes.string,
};

export default EmployeeImportWizard;

