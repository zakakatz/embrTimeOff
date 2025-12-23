/**
 * useMultiStepForm - Custom hook for managing multi-step form state
 * 
 * Features:
 * - Step navigation with validation
 * - Form data management across steps
 * - Step completion tracking
 * - Draft saving support
 */

import { useState, useCallback, useMemo, useEffect } from 'react';

/**
 * Custom hook for multi-step form management
 * @param {Object} options Configuration options
 * @param {Array} options.steps Array of step configurations
 * @param {Object} options.initialData Initial form data
 * @param {Function} options.onStepChange Callback when step changes
 * @param {Function} options.onComplete Callback when form is completed
 * @param {boolean} options.allowBackNavigation Allow going back to previous steps
 * @param {boolean} options.validateBeforeNext Validate before advancing
 * @returns {Object} Form state and handlers
 */
export const useMultiStepForm = ({
  steps = [],
  initialData = {},
  onStepChange,
  onComplete,
  allowBackNavigation = true,
  validateBeforeNext = true,
} = {}) => {
  // State
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [formData, setFormData] = useState(initialData);
  const [stepValidation, setStepValidation] = useState({});
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  
  // Derived state
  const totalSteps = steps.length;
  const currentStep = steps[currentStepIndex];
  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === totalSteps - 1;
  const progress = totalSteps > 0 ? ((currentStepIndex + 1) / totalSteps) * 100 : 0;
  
  // Check if step can be accessed
  const canAccessStep = useCallback((stepIndex) => {
    if (stepIndex < 0 || stepIndex >= totalSteps) return false;
    if (stepIndex <= currentStepIndex) return true;
    if (!validateBeforeNext) return true;
    
    // Can only access step if all previous steps are completed
    for (let i = 0; i < stepIndex; i++) {
      if (!completedSteps.has(i)) return false;
    }
    return true;
  }, [currentStepIndex, totalSteps, validateBeforeNext, completedSteps]);
  
  // Update form data
  const updateFormData = useCallback((newData) => {
    setFormData((prev) => ({
      ...prev,
      ...(typeof newData === 'function' ? newData(prev) : newData),
    }));
  }, []);
  
  // Set field value
  const setFieldValue = useCallback((field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    
    // Clear field error when value changes
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  }, [errors]);
  
  // Get field value
  const getFieldValue = useCallback((field) => {
    return formData[field];
  }, [formData]);
  
  // Validate current step
  const validateCurrentStep = useCallback(async () => {
    const step = steps[currentStepIndex];
    
    if (!step?.validate) {
      return { isValid: true, errors: {} };
    }
    
    try {
      const validationResult = await step.validate(formData);
      
      if (validationResult === true) {
        setErrors({});
        return { isValid: true, errors: {} };
      }
      
      if (typeof validationResult === 'object') {
        setErrors(validationResult);
        return { isValid: false, errors: validationResult };
      }
      
      return { isValid: true, errors: {} };
    } catch (error) {
      const errorMessage = error.message || 'Validation failed';
      setErrors({ _form: errorMessage });
      return { isValid: false, errors: { _form: errorMessage } };
    }
  }, [currentStepIndex, formData, steps]);
  
  // Go to next step
  const goToNext = useCallback(async () => {
    if (isLastStep) return false;
    
    if (validateBeforeNext) {
      const { isValid } = await validateCurrentStep();
      if (!isValid) return false;
    }
    
    // Mark current step as completed
    setCompletedSteps((prev) => new Set([...prev, currentStepIndex]));
    
    const nextIndex = currentStepIndex + 1;
    setCurrentStepIndex(nextIndex);
    
    if (onStepChange) {
      onStepChange(nextIndex, steps[nextIndex], formData);
    }
    
    return true;
  }, [
    isLastStep,
    validateBeforeNext,
    validateCurrentStep,
    currentStepIndex,
    steps,
    formData,
    onStepChange,
  ]);
  
  // Go to previous step
  const goToPrevious = useCallback(() => {
    if (isFirstStep || !allowBackNavigation) return false;
    
    const prevIndex = currentStepIndex - 1;
    setCurrentStepIndex(prevIndex);
    
    if (onStepChange) {
      onStepChange(prevIndex, steps[prevIndex], formData);
    }
    
    return true;
  }, [isFirstStep, allowBackNavigation, currentStepIndex, steps, formData, onStepChange]);
  
  // Go to specific step
  const goToStep = useCallback(async (stepIndex) => {
    if (!canAccessStep(stepIndex)) return false;
    
    // If going forward, validate current step first
    if (stepIndex > currentStepIndex && validateBeforeNext) {
      const { isValid } = await validateCurrentStep();
      if (!isValid) return false;
      
      // Mark current step as completed
      setCompletedSteps((prev) => new Set([...prev, currentStepIndex]));
    }
    
    setCurrentStepIndex(stepIndex);
    
    if (onStepChange) {
      onStepChange(stepIndex, steps[stepIndex], formData);
    }
    
    return true;
  }, [
    canAccessStep,
    currentStepIndex,
    validateBeforeNext,
    validateCurrentStep,
    steps,
    formData,
    onStepChange,
  ]);
  
  // Submit form
  const submit = useCallback(async () => {
    if (validateBeforeNext) {
      const { isValid } = await validateCurrentStep();
      if (!isValid) return false;
    }
    
    setIsSubmitting(true);
    
    try {
      if (onComplete) {
        await onComplete(formData);
      }
      
      // Mark all steps as completed
      setCompletedSteps(new Set(steps.map((_, i) => i)));
      
      return true;
    } catch (error) {
      setErrors({ _form: error.message || 'Submission failed' });
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }, [validateBeforeNext, validateCurrentStep, formData, onComplete, steps]);
  
  // Reset form
  const reset = useCallback(() => {
    setCurrentStepIndex(0);
    setFormData(initialData);
    setStepValidation({});
    setCompletedSteps(new Set());
    setErrors({});
    setIsSubmitting(false);
  }, [initialData]);
  
  // Check if form is dirty
  const isDirty = useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(initialData);
  }, [formData, initialData]);
  
  // Get steps with status
  const stepsWithStatus = useMemo(() => {
    return steps.map((step, index) => ({
      ...step,
      index,
      isCompleted: completedSteps.has(index),
      isCurrent: index === currentStepIndex,
      isAccessible: canAccessStep(index),
      hasErrors: stepValidation[index]?.hasErrors || false,
    }));
  }, [steps, completedSteps, currentStepIndex, canAccessStep, stepValidation]);
  
  return {
    // State
    currentStepIndex,
    currentStep,
    formData,
    errors,
    isSubmitting,
    isDirty,
    
    // Derived state
    totalSteps,
    isFirstStep,
    isLastStep,
    progress,
    completedSteps: Array.from(completedSteps),
    stepsWithStatus,
    
    // Actions
    updateFormData,
    setFieldValue,
    getFieldValue,
    goToNext,
    goToPrevious,
    goToStep,
    submit,
    reset,
    validateCurrentStep,
    canAccessStep,
    
    // Setters (for advanced use cases)
    setErrors,
    setCurrentStepIndex,
  };
};

export default useMultiStepForm;

