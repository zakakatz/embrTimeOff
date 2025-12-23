/**
 * Export Progress Display Component
 * 
 * Shows export progress and completion status.
 */

import React from 'react';
import PropTypes from 'prop-types';
import styles from './ExportProgressDisplay.module.css';

export function ExportProgressDisplay({
  progress,
  result,
  isComplete,
}) {
  if (isComplete && result) {
    return (
      <div className={styles.container}>
        <div className={styles.successIcon}>✅</div>
        <h3 className={styles.title}>Export Complete!</h3>
        <p className={styles.subtitle}>
          Your file has been downloaded successfully.
        </p>

        <div className={styles.resultDetails}>
          <div className={styles.resultRow}>
            <span className={styles.resultLabel}>Filename:</span>
            <span className={styles.resultValue}>{result.filename}</span>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.resultLabel}>Total Records:</span>
            <span className={styles.resultValue}>{result.totalRecords}</span>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.resultLabel}>Fields Exported:</span>
            <span className={styles.resultValue}>{result.exportedFields?.length || 0}</span>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.resultLabel}>Generated At:</span>
            <span className={styles.resultValue}>
              {new Date(result.generatedAt).toLocaleString()}
            </span>
          </div>
        </div>

        <div className={styles.downloadInfo}>
          <span className={styles.downloadIcon}>📁</span>
          <span className={styles.downloadText}>
            Check your downloads folder for the exported file.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.progressIcon}>📊</div>
      <h3 className={styles.title}>Generating Export...</h3>
      <p className={styles.subtitle}>{progress.status}</p>

      <div className={styles.progressWrapper}>
        <div className={styles.progressBar}>
          <div
            className={styles.progressFill}
            style={{ width: `${progress.percentage}%` }}
          />
        </div>
        <span className={styles.progressText}>{progress.percentage}%</span>
      </div>

      <p className={styles.hint}>
        Please wait while we prepare your export.
        This may take a moment for large datasets.
      </p>
    </div>
  );
}

ExportProgressDisplay.propTypes = {
  progress: PropTypes.shape({
    percentage: PropTypes.number.isRequired,
    status: PropTypes.string,
  }).isRequired,
  result: PropTypes.shape({
    filename: PropTypes.string,
    totalRecords: PropTypes.number,
    exportedFields: PropTypes.arrayOf(PropTypes.string),
    generatedAt: PropTypes.string,
  }),
  isComplete: PropTypes.bool,
};

export default ExportProgressDisplay;

