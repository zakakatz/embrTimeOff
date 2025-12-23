/**
 * MultiStepForm - Multi-step form wrapper with progress indicator and navigation
 * 
 * Features:
 * - Step progress indicator
 * - Navigation between steps
 * - Step validation before advancing
 * - Form state persistence
 * - Dirty state tracking
 */

import React, { useState, useCallback, useEffect } from 'react';
import { ProgressIndicator } from './ProgressIndicator';
import { StepNavigation } from './StepNavigation';
import styles from './MultiStepForm.module.css';

/**
 * MultiStepForm component
 * @param {Object} props
 * @param {Array} props.steps - Array of step configurations { id, title, description?, component, validate? }
 * @param {Object} props.initialData - Initial form data
 * @param {Function} props.onSubmit - Handler for form submission
 * @param {Function} props.onStepChange - Handler for step changes
 * @param {Function} props.onSaveDraft - Handler for saving draft
 * @param {boolean} props.showProgressIndicator - Show progress indicator
 * @param {boolean} props.showStepNumbers - Show step numbers
 * @param {boolean} props.allowSkipSteps - Allow skipping to any step
 * @param {string} props.submitButtonText - Text for submit button
 * @param {boolean} props.isSubmitting - External submitting state
 * @param {string} props.className - Additional CSS class
 */
export const MultiStepForm = ({
  steps = [],
  initialData = {},
  onSubmit,
  onStepChange,
  onSaveDraft,
  showProgressIndicator = true,
  showStepNumbers = true,
  allowSkipSteps = false,
  submitButtonText = 'Submit',
  isSubmitting = false,
  className = '',
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState(initialData);
  const [stepErrors, setStepErrors] = useState({});
  const [visitedSteps, setVisitedSteps] = useState(new Set([0]));
  const [isDirty, setIsDirty] = useState(false);
  
  const totalSteps = steps.length;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;
  const currentStepConfig = steps[currentStep];
  
  // Track dirty state
  useEffect(() => {
    const hasChanges = JSON.stringify(formData) !== JSON.stringify(initialData);
    setIsDirty(hasChanges);
  }, [formData, initialData]);
  
  // Warn about unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);
  
  // Update form data for current step
  const updateStepData = useCallback((stepData) => {
    setFormData((prev) => ({
      ...prev,
      ...stepData,
    }));
  }, []);
  
  // Validate current step
  const validateStep = useCallback(async () => {
    const stepConfig = steps[currentStep];
    
    if (stepConfig.validate) {
      try {
        const errors = await stepConfig.validate(formData);
        
        if (errors && Object.keys(errors).length > 0) {
          setStepErrors((prev) => ({
            ...prev,
            [currentStep]: errors,
          }));
          return false;
        }
      } catch (error) {
        console.error('Validation error:', error);
        return false;
      }
    }
    
    // Clear errors for this step
    setStepErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[currentStep];
      return newErrors;
    });
    
    return true;
  }, [currentStep, formData, steps]);
  
  // Go to next step
  const goToNextStep = useCallback(async () => {
    if (isLastStep) return;
    
    const isValid = await validateStep();
    
    if (!isValid) return;
    
    const nextStep = currentStep + 1;
    setCurrentStep(nextStep);
    setVisitedSteps((prev) => new Set([...prev, nextStep]));
    
    if (onStepChange) {
      onStepChange(nextStep, formData);
    }
  }, [currentStep, isLastStep, validateStep, formData, onStepChange]);
  
  // Go to previous step
  const goToPreviousStep = useCallback(() => {
    if (isFirstStep) return;
    
    const prevStep = currentStep - 1;
    setCurrentStep(prevStep);
    
    if (onStepChange) {
      onStepChange(prevStep, formData);
    }
  }, [currentStep, isFirstStep, formData, onStepChange]);
  
  // Go to specific step
  const goToStep = useCallback(async (stepIndex) => {
    if (stepIndex < 0 || stepIndex >= totalSteps) return;
    if (stepIndex === currentStep) return;
    
    // Validate current step if going forward
    if (stepIndex > currentStep && !allowSkipSteps) {
      const isValid = await validateStep();
      if (!isValid) return;
    }
    
    // Only allow going to visited steps unless skipping is allowed
    if (!allowSkipSteps && !visitedSteps.has(stepIndex) && stepIndex > currentStep + 1) {
      return;
    }
    
    setCurrentStep(stepIndex);
    setVisitedSteps((prev) => new Set([...prev, stepIndex]));
    
    if (onStepChange) {
      onStepChange(stepIndex, formData);
    }
  }, [currentStep, totalSteps, allowSkipSteps, visitedSteps, validateStep, formData, onStepChange]);
  
  // Handle form submission
  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault();
    
    // Validate final step
    const isValid = await validateStep();
    if (!isValid) return;
    
    if (onSubmit) {
      await onSubmit(formData);
      setIsDirty(false);
    }
  }, [validateStep, formData, onSubmit]);
  
  // Handle save draft
  const handleSaveDraft = useCallback(() => {
    if (onSaveDraft) {
      onSaveDraft(formData, currentStep);
    }
  }, [formData, currentStep, onSaveDraft]);
  
  // Reset form
  const resetForm = useCallback(() => {
    setFormData(initialData);
    setCurrentStep(0);
    setStepErrors({});
    setVisitedSteps(new Set([0]));
    setIsDirty(false);
  }, [initialData]);
  
  // Get step status for progress indicator
  const getStepStatus = useCallback((stepIndex) => {
    if (stepIndex === currentStep) return 'current';
    if (stepErrors[stepIndex]) return 'error';
    if (stepIndex < currentStep || visitedSteps.has(stepIndex)) return 'completed';
    return 'upcoming';
  }, [currentStep, stepErrors, visitedSteps]);
  
  // Render current step component
  const StepComponent = currentStepConfig?.component;
  
  return (
    <div className={`${styles.multiStepForm} ${className}`}>
      {showProgressIndicator && (
        <ProgressIndicator
          steps={steps.map((step, index) => ({
            id: step.id,
            title: step.title,
            description: step.description,
            status: getStepStatus(index),
          }))}
          currentStep={currentStep}
          onStepClick={allowSkipSteps || visitedSteps.has ? goToStep : undefined}
          showStepNumbers={showStepNumbers}
        />
      )}
      
      <div className={styles.formContent}>
        <div className={styles.stepHeader}>
          <h2 className={styles.stepTitle}>{currentStepConfig?.title}</h2>
          {currentStepConfig?.description && (
            <p className={styles.stepDescription}>{currentStepConfig.description}</p>
          )}
        </div>
        
        <form onSubmit={handleSubmit} className={styles.form}>
          {StepComponent && (
            <StepComponent
              data={formData}
              updateData={updateStepData}
              errors={stepErrors[currentStep] || {}}
              isFirstStep={isFirstStep}
              isLastStep={isLastStep}
            />
          )}
          
          <StepNavigation
            isFirstStep={isFirstStep}
            isLastStep={isLastStep}
            onPrevious={goToPreviousStep}
            onNext={goToNextStep}
            onSubmit={handleSubmit}
            onSaveDraft={onSaveDraft ? handleSaveDraft : undefined}
            isSubmitting={isSubmitting}
            submitButtonText={submitButtonText}
            isDirty={isDirty}
          />
        </form>
      </div>
      
      {isDirty && (
        <div className={styles.unsavedChanges}>
          You have unsaved changes
        </div>
      )}
    </div>
  );
};

export default MultiStepForm;

