/**
 * File Upload Step Component
 * 
 * Handles CSV file upload with drag-and-drop support and template download.
 */

import React, { useState, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import styles from './Steps.module.css';

const ACCEPTED_FILE_TYPES = ['.csv', 'text/csv', 'application/vnd.ms-excel'];
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

const CSV_TEMPLATE = `employee_id,email,first_name,last_name,hire_date,job_title,department_id,employment_status
EMP001,john.doe@example.com,John,Doe,2024-01-15,Software Engineer,1,active
EMP002,jane.smith@example.com,Jane,Smith,2024-02-01,Product Manager,2,active`;

export function FileUploadStep({
  wizardState,
  setIsLoading,
  setError,
  onFileUpload,
  apiBaseUrl,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const fileInputRef = useRef(null);

  // Parse CSV content for preview
  const parseCSVPreview = useCallback((content) => {
    const lines = content.split('\n').filter((line) => line.trim());
    if (lines.length === 0) return null;

    const headers = lines[0].split(',').map((h) => h.trim());
    const rows = lines.slice(1, 6).map((line) => {
      const values = line.split(',');
      return headers.reduce((obj, header, index) => {
        obj[header] = values[index]?.trim() || '';
        return obj;
      }, {});
    });

    // Auto-suggest field mappings
    const suggestedMappings = {};
    const knownFields = [
      'employee_id', 'email', 'first_name', 'last_name', 'hire_date',
      'job_title', 'department_id', 'employment_status', 'salary',
    ];
    
    headers.forEach((header) => {
      const normalized = header.toLowerCase().replace(/[^a-z0-9]/g, '_');
      if (knownFields.includes(normalized)) {
        suggestedMappings[header] = normalized;
      }
    });

    return {
      headers,
      rows,
      totalRows: lines.length - 1,
      suggestedMappings,
    };
  }, []);

  // Handle file selection
  const handleFileSelect = useCallback(async (file) => {
    if (!file) return;

    // Validate file type
    const isValidType = ACCEPTED_FILE_TYPES.some(
      (type) => file.type === type || file.name.endsWith(type)
    );
    if (!isValidType) {
      setError('Please select a valid CSV file');
      return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      setError('File size exceeds 100MB limit');
      return;
    }

    setSelectedFile(file);
    setIsLoading(true);
    setError(null);

    try {
      // Read file content
      const content = await file.text();
      const preview = parseCSVPreview(content);
      
      if (!preview || preview.headers.length === 0) {
        throw new Error('Unable to parse CSV file. Please check the format.');
      }

      setPreviewData(preview);
    } catch (err) {
      setError(err.message || 'Failed to read file');
      setSelectedFile(null);
    } finally {
      setIsLoading(false);
    }
  }, [parseCSVPreview, setIsLoading, setError]);

  // Handle drag events
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer?.files;
    if (files?.length > 0) {
      handleFileSelect(files[0]);
    }
  }, [handleFileSelect]);

  // Handle file input change
  const handleInputChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  // Download template
  const handleDownloadTemplate = useCallback(() => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'employee_import_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  // Proceed to next step
  const handleContinue = useCallback(() => {
    if (selectedFile && previewData) {
      onFileUpload(selectedFile, previewData);
    }
  }, [selectedFile, previewData, onFileUpload]);

  // Remove selected file
  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
    setPreviewData(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  return (
    <div className={styles.stepContainer}>
      {/* Instructions */}
      <div className={styles.instructions}>
        <h3 className={styles.instructionsTitle}>Upload Employee Data</h3>
        <p className={styles.instructionsText}>
          Upload a CSV file containing employee information. The file should include
          headers in the first row. We'll help you map the columns to employee fields.
        </p>
        <button
          className={styles.templateButton}
          onClick={handleDownloadTemplate}
        >
          <span>📥</span>
          Download CSV Template
        </button>
      </div>

      {/* File Upload Zone */}
      {!selectedFile ? (
        <div
          className={`${styles.dropZone} ${isDragging ? styles.dropZoneDragging : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload file"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              fileInputRef.current?.click();
            }
          }}
        >
          <div className={styles.dropZoneIcon}>📁</div>
          <p className={styles.dropZoneText}>
            Drag and drop your CSV file here, or click to browse
          </p>
          <p className={styles.dropZoneHint}>
            Maximum file size: 100MB
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleInputChange}
            className={styles.fileInput}
            aria-hidden="true"
          />
        </div>
      ) : (
        <div className={styles.fileSelected}>
          <div className={styles.fileInfo}>
            <div className={styles.fileIcon}>📄</div>
            <div className={styles.fileDetails}>
              <span className={styles.fileName}>{selectedFile.name}</span>
              <span className={styles.fileSize}>
                {(selectedFile.size / 1024).toFixed(1)} KB
              </span>
            </div>
            <button
              className={styles.removeFileButton}
              onClick={handleRemoveFile}
              aria-label="Remove file"
            >
              ×
            </button>
          </div>

          {/* Preview Table */}
          {previewData && (
            <div className={styles.preview}>
              <div className={styles.previewHeader}>
                <span className={styles.previewTitle}>Preview</span>
                <span className={styles.previewCount}>
                  {previewData.totalRows} rows detected
                </span>
              </div>
              <div className={styles.previewTableWrapper}>
                <table className={styles.previewTable}>
                  <thead>
                    <tr>
                      {previewData.headers.map((header, index) => (
                        <th key={index}>{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.rows.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {previewData.headers.map((header, colIndex) => (
                          <td key={colIndex}>{row[header] || '-'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {previewData.totalRows > 5 && (
                <p className={styles.previewMore}>
                  ... and {previewData.totalRows - 5} more rows
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className={styles.actions}>
        <div className={styles.actionsRight}>
          <button
            className={styles.primaryButton}
            onClick={handleContinue}
            disabled={!selectedFile || !previewData}
          >
            Continue to Field Mapping
            <span className={styles.buttonIcon}>→</span>
          </button>
        </div>
      </div>
    </div>
  );
}

FileUploadStep.propTypes = {
  wizardState: PropTypes.object.isRequired,
  setIsLoading: PropTypes.func.isRequired,
  setError: PropTypes.func.isRequired,
  onFileUpload: PropTypes.func.isRequired,
  apiBaseUrl: PropTypes.string,
};

export default FileUploadStep;

