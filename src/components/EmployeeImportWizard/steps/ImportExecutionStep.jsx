/**
 * Import Execution Step Component
 * 
 * Handles the actual import process with progress tracking and result display.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import styles from './Steps.module.css';

const IMPORT_STATES = {
  IDLE: 'idle',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
};

export function ImportExecutionStep({
  wizardState,
  setIsLoading,
  setError,
  apiBaseUrl,
  onImportComplete,
  onClose,
  onBack,
}) {
  const { validationResults, allowPartialImport, file, fieldMappings } = wizardState;
  const [importState, setImportState] = useState(IMPORT_STATES.IDLE);
  const [progress, setProgress] = useState({
    current: 0,
    total: validationResults?.validRows || 0,
    percentage: 0,
  });
  const [importResult, setImportResult] = useState(null);
  const progressIntervalRef = useRef(null);

  // Start the import process
  const startImport = useCallback(async () => {
    setImportState(IMPORT_STATES.PROCESSING);
    setIsLoading(true);
    setProgress({ current: 0, total: validationResults?.validRows || 0, percentage: 0 });

    try {
      // Simulate progress updates (in production, this would poll the API)
      const totalRows = validationResults?.validRows || 0;
      let currentProgress = 0;

      progressIntervalRef.current = setInterval(() => {
        currentProgress += Math.floor(Math.random() * 5) + 1;
        if (currentProgress >= totalRows) {
          currentProgress = totalRows;
          clearInterval(progressIntervalRef.current);
        }
        
        setProgress({
          current: currentProgress,
          total: totalRows,
          percentage: Math.round((currentProgress / totalRows) * 100),
        });
      }, 200);

      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, totalRows * 50 + 1000));

      clearInterval(progressIntervalRef.current);
      
      // Simulate result
      const result = {
        status: 'completed',
        importedCount: totalRows,
        skippedCount: validationResults?.errorRows || 0,
        duration: ((totalRows * 50 + 1000) / 1000).toFixed(1),
        importId: `IMP-${Date.now()}`,
      };

      setImportResult(result);
      setImportState(IMPORT_STATES.COMPLETED);
      setProgress({ current: totalRows, total: totalRows, percentage: 100 });
      onImportComplete?.(result);
    } catch (err) {
      clearInterval(progressIntervalRef.current);
      setImportState(IMPORT_STATES.FAILED);
      setError(err.message || 'Import failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [validationResults, setIsLoading, setError, onImportComplete]);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);

  // Render based on import state
  const renderContent = () => {
    switch (importState) {
      case IMPORT_STATES.IDLE:
        return (
          <>
            <div className={styles.confirmationBox}>
              <div className={styles.confirmationIcon}>📋</div>
              <h3 className={styles.confirmationTitle}>Ready to Import</h3>
              <p className={styles.confirmationText}>
                You are about to import <strong>{validationResults?.validRows || 0} employees</strong> 
                {validationResults?.errorRows > 0 && allowPartialImport && (
                  <> ({validationResults.errorRows} rows will be skipped due to errors)</>
                )}
              </p>
              
              <div className={styles.confirmationDetails}>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>File:</span>
                  <span className={styles.detailValue}>{file?.name || 'Unknown'}</span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Mapped Fields:</span>
                  <span className={styles.detailValue}>
                    {Object.keys(fieldMappings).length} columns
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Partial Import:</span>
                  <span className={styles.detailValue}>
                    {allowPartialImport ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>
            </div>

            <div className={styles.actions}>
              <button
                className={styles.secondaryButton}
                onClick={onBack}
              >
                <span className={styles.buttonIcon}>←</span>
                Back to Preview
              </button>
              <button
                className={styles.primaryButton}
                onClick={startImport}
              >
                <span className={styles.buttonIcon}>🚀</span>
                Start Import
              </button>
            </div>
          </>
        );

      case IMPORT_STATES.PROCESSING:
        return (
          <div className={styles.progressContainer}>
            <div className={styles.progressIcon}>⏳</div>
            <h3 className={styles.progressTitle}>Importing Employees...</h3>
            <p className={styles.progressSubtitle}>
              Please wait while we import your data
            </p>

            <div className={styles.progressBarWrapper}>
              <div className={styles.progressBar}>
                <div 
                  className={styles.progressFill}
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
              <span className={styles.progressText}>
                {progress.current} of {progress.total} ({progress.percentage}%)
              </span>
            </div>

            <p className={styles.progressHint}>
              Do not close this window during import
            </p>
          </div>
        );

      case IMPORT_STATES.COMPLETED:
        return (
          <>
            <div className={styles.resultBox}>
              <div className={styles.resultIconSuccess}>✅</div>
              <h3 className={styles.resultTitle}>Import Complete!</h3>
              
              <div className={styles.resultStats}>
                <div className={styles.resultStat}>
                  <span className={styles.resultStatValue}>{importResult?.importedCount || 0}</span>
                  <span className={styles.resultStatLabel}>Employees Imported</span>
                </div>
                {(importResult?.skippedCount || 0) > 0 && (
                  <div className={styles.resultStat}>
                    <span className={styles.resultStatValue}>{importResult.skippedCount}</span>
                    <span className={styles.resultStatLabel}>Rows Skipped</span>
                  </div>
                )}
                <div className={styles.resultStat}>
                  <span className={styles.resultStatValue}>{importResult?.duration}s</span>
                  <span className={styles.resultStatLabel}>Duration</span>
                </div>
              </div>

              <div className={styles.resultReference}>
                <span className={styles.resultReferenceLabel}>Import Reference:</span>
                <code className={styles.resultReferenceValue}>{importResult?.importId}</code>
              </div>
            </div>

            <div className={styles.actions}>
              <button
                className={styles.primaryButton}
                onClick={onClose}
              >
                <span className={styles.buttonIcon}>✓</span>
                Done
              </button>
            </div>
          </>
        );

      case IMPORT_STATES.FAILED:
        return (
          <>
            <div className={styles.resultBox}>
              <div className={styles.resultIconError}>❌</div>
              <h3 className={styles.resultTitle}>Import Failed</h3>
              <p className={styles.resultText}>
                An error occurred during the import process. 
                Your data has not been modified.
              </p>
            </div>

            <div className={styles.actions}>
              <button
                className={styles.secondaryButton}
                onClick={onBack}
              >
                <span className={styles.buttonIcon}>←</span>
                Back
              </button>
              <button
                className={styles.primaryButton}
                onClick={startImport}
              >
                <span className={styles.buttonIcon}>🔄</span>
                Retry Import
              </button>
            </div>
          </>
        );

      default:
        return null;
    }
  };

  return (
    <div className={styles.stepContainer}>
      {renderContent()}
    </div>
  );
}

ImportExecutionStep.propTypes = {
  wizardState: PropTypes.object.isRequired,
  setIsLoading: PropTypes.func.isRequired,
  setError: PropTypes.func.isRequired,
  apiBaseUrl: PropTypes.string,
  onImportComplete: PropTypes.func,
  onClose: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default ImportExecutionStep;

