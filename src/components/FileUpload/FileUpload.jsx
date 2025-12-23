/**
 * File Upload Component for Employee Data Import
 * 
 * Provides drag-and-drop and traditional file selection for CSV imports
 * with validation, progress tracking, and preview capabilities.
 */

import React, { useState, useCallback, useRef } from 'react';
import styles from './FileUpload.module.css';

// Constants
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const SUPPORTED_TYPES = ['text/csv', 'application/vnd.ms-excel'];
const SUPPORTED_EXTENSIONS = ['.csv'];
const PREVIEW_ROWS = 10;

// Encoding options
const ENCODINGS = [
  { value: 'UTF-8', label: 'UTF-8' },
  { value: 'ASCII', label: 'ASCII' },
  { value: 'ISO-8859-1', label: 'ISO-8859-1 (Latin-1)' },
  { value: 'Windows-1252', label: 'Windows-1252' },
];

/**
 * Detect file encoding (simplified detection)
 */
function detectEncoding(content) {
  // Check for BOM markers
  if (content.charCodeAt(0) === 0xFEFF) {
    return 'UTF-8';
  }
  
  // Check for non-ASCII characters
  let hasExtended = false;
  for (let i = 0; i < Math.min(content.length, 1000); i++) {
    const code = content.charCodeAt(i);
    if (code > 127) {
      hasExtended = true;
      break;
    }
  }
  
  return hasExtended ? 'UTF-8' : 'ASCII';
}

/**
 * Parse CSV content into rows and columns
 */
function parseCSV(content, delimiter = ',') {
  const lines = content.split(/\r?\n/).filter(line => line.trim());
  const rows = [];
  
  for (const line of lines) {
    const row = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === delimiter && !inQuotes) {
        row.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    row.push(current.trim());
    rows.push(row);
  }
  
  return rows;
}

/**
 * Analyze data quality
 */
function analyzeDataQuality(rows) {
  if (rows.length === 0) return { emptyRows: 0, completeness: 0 };
  
  const headers = rows[0];
  const dataRows = rows.slice(1);
  
  let emptyRows = 0;
  let emptyCells = 0;
  let totalCells = 0;
  
  for (const row of dataRows) {
    const isEmpty = row.every(cell => !cell || cell.trim() === '');
    if (isEmpty) {
      emptyRows++;
    }
    
    for (let i = 0; i < headers.length; i++) {
      totalCells++;
      if (!row[i] || row[i].trim() === '') {
        emptyCells++;
      }
    }
  }
  
  const completeness = totalCells > 0 
    ? Math.round(((totalCells - emptyCells) / totalCells) * 100) 
    : 0;
  
  return { emptyRows, completeness };
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * FileUpload Component
 */
export default function FileUpload({ onFileProcessed, onError }) {
  // State
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null);
  const [selectedEncoding, setSelectedEncoding] = useState('UTF-8');
  const [detectedEncoding, setDetectedEncoding] = useState(null);
  const [fileSummary, setFileSummary] = useState(null);
  
  const fileInputRef = useRef(null);
  const dropZoneRef = useRef(null);
  
  /**
   * Validate file before processing
   */
  const validateFile = useCallback((file) => {
    // Check file type
    const extension = '.' + file.name.split('.').pop().toLowerCase();
    const isValidType = SUPPORTED_TYPES.includes(file.type) || 
                        SUPPORTED_EXTENSIONS.includes(extension);
    
    if (!isValidType) {
      return {
        valid: false,
        error: `Unsupported file type. Please upload a CSV file. Received: ${file.type || extension}`
      };
    }
    
    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: `File size exceeds maximum limit of ${formatFileSize(MAX_FILE_SIZE)}. Your file: ${formatFileSize(file.size)}`
      };
    }
    
    // Check if file is empty
    if (file.size === 0) {
      return {
        valid: false,
        error: 'The selected file is empty. Please choose a file with data.'
      };
    }
    
    return { valid: true };
  }, []);
  
  /**
   * Process the uploaded file
   */
  const processFile = useCallback(async (file) => {
    setIsProcessing(true);
    setError(null);
    setUploadProgress(0);
    
    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 100);
      
      // Read file content
      const content = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = () => reject(new Error('Failed to read file'));
        
        reader.readAsText(file, selectedEncoding);
      });
      
      clearInterval(progressInterval);
      setUploadProgress(95);
      
      // Detect encoding
      const detected = detectEncoding(content);
      setDetectedEncoding(detected);
      
      // Parse CSV
      const rows = parseCSV(content);
      
      if (rows.length === 0) {
        throw new Error('File appears to be empty or corrupted');
      }
      
      // Extract headers and preview data
      const headers = rows[0];
      const previewRows = rows.slice(1, PREVIEW_ROWS + 1);
      
      // Analyze data quality
      const quality = analyzeDataQuality(rows);
      
      // Build summary
      const summary = {
        fileName: file.name,
        fileSize: formatFileSize(file.size),
        totalRows: rows.length - 1, // Exclude header
        totalColumns: headers.length,
        encoding: detected,
        emptyRows: quality.emptyRows,
        completeness: quality.completeness,
        uploadedAt: new Date().toISOString(),
      };
      
      setFileSummary(summary);
      setPreview({
        headers,
        rows: previewRows,
      });
      
      setUploadProgress(100);
      
      // Notify parent
      if (onFileProcessed) {
        onFileProcessed({
          file,
          content,
          headers,
          totalRows: rows.length - 1,
          summary,
        });
      }
      
    } catch (err) {
      const errorMessage = err.message || 'Failed to process file';
      setError(errorMessage);
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setIsProcessing(false);
    }
  }, [selectedEncoding, onFileProcessed, onError]);
  
  /**
   * Handle file selection
   */
  const handleFileSelect = useCallback((selectedFile) => {
    const validation = validateFile(selectedFile);
    
    if (!validation.valid) {
      setError(validation.error);
      if (onError) {
        onError(validation.error);
      }
      return;
    }
    
    setFile(selectedFile);
    setError(null);
    processFile(selectedFile);
  }, [validateFile, processFile, onError]);
  
  /**
   * Handle drag events
   */
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);
  
  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.target === dropZoneRef.current) {
      setIsDragging(false);
    }
  }, []);
  
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);
  
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      handleFileSelect(droppedFiles[0]);
    }
  }, [handleFileSelect]);
  
  /**
   * Handle click to select file
   */
  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);
  
  /**
   * Handle file input change
   */
  const handleInputChange = useCallback((e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      handleFileSelect(selectedFile);
    }
  }, [handleFileSelect]);
  
  /**
   * Handle encoding change and reprocess
   */
  const handleEncodingChange = useCallback((e) => {
    const newEncoding = e.target.value;
    setSelectedEncoding(newEncoding);
    
    if (file) {
      processFile(file);
    }
  }, [file, processFile]);
  
  /**
   * Clear current file
   */
  const handleClear = useCallback(() => {
    setFile(null);
    setPreview(null);
    setFileSummary(null);
    setError(null);
    setUploadProgress(0);
    setDetectedEncoding(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);
  
  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <h2 className={styles.title}>Upload Employee Data</h2>
        <p className={styles.subtitle}>
          Upload a CSV file to import employee records. Maximum file size: 50MB.
        </p>
      </div>
      
      {/* Drop Zone */}
      {!file && (
        <div
          ref={dropZoneRef}
          className={`${styles.dropZone} ${isDragging ? styles.dragging : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={handleClick}
          role="button"
          tabIndex={0}
          onKeyPress={(e) => e.key === 'Enter' && handleClick()}
          aria-label="Click or drag file to upload"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleInputChange}
            className={styles.fileInput}
            aria-hidden="true"
          />
          
          <div className={styles.dropZoneContent}>
            <div className={styles.uploadIcon}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
            </div>
            <p className={styles.dropText}>
              {isDragging ? 'Drop file here' : 'Drag and drop your CSV file here'}
            </p>
            <p className={styles.orText}>or</p>
            <button type="button" className={styles.browseButton}>
              Browse Files
            </button>
            <p className={styles.supportText}>
              Supported format: CSV (up to 50MB)
            </p>
          </div>
        </div>
      )}
      
      {/* Error Display */}
      {error && (
        <div className={styles.error} role="alert">
          <span className={styles.errorIcon}>⚠️</span>
          <span className={styles.errorText}>{error}</span>
          <button 
            type="button" 
            className={styles.errorDismiss}
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}
      
      {/* Progress Indicator */}
      {isProcessing && (
        <div className={styles.progressContainer}>
          <div className={styles.progressHeader}>
            <span>Processing file...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill}
              style={{ width: `${uploadProgress}%` }}
              role="progressbar"
              aria-valuenow={uploadProgress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <p className={styles.progressEstimate}>
            {uploadProgress < 50 ? 'Reading file...' : 
             uploadProgress < 90 ? 'Parsing data...' : 
             'Finalizing...'}
          </p>
        </div>
      )}
      
      {/* File Summary */}
      {fileSummary && !isProcessing && (
        <div className={styles.summary}>
          <div className={styles.summaryHeader}>
            <div className={styles.fileInfo}>
              <span className={styles.fileIcon}>📄</span>
              <div>
                <h3 className={styles.fileName}>{fileSummary.fileName}</h3>
                <span className={styles.fileSize}>{fileSummary.fileSize}</span>
              </div>
            </div>
            <button 
              type="button"
              className={styles.clearButton}
              onClick={handleClear}
              aria-label="Remove file"
            >
              Remove
            </button>
          </div>
          
          <div className={styles.summaryStats}>
            <div className={styles.stat}>
              <span className={styles.statLabel}>Total Rows</span>
              <span className={styles.statValue}>{fileSummary.totalRows.toLocaleString()}</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>Columns</span>
              <span className={styles.statValue}>{fileSummary.totalColumns}</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>Data Completeness</span>
              <span className={styles.statValue}>{fileSummary.completeness}%</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>Empty Rows</span>
              <span className={styles.statValue}>{fileSummary.emptyRows}</span>
            </div>
          </div>
          
          {/* Encoding Selection */}
          <div className={styles.encodingSection}>
            <label className={styles.encodingLabel}>
              File Encoding:
              <select 
                value={selectedEncoding}
                onChange={handleEncodingChange}
                className={styles.encodingSelect}
              >
                {ENCODINGS.map(enc => (
                  <option key={enc.value} value={enc.value}>
                    {enc.label} {enc.value === detectedEncoding ? '(detected)' : ''}
                  </option>
                ))}
              </select>
            </label>
            {detectedEncoding && detectedEncoding !== selectedEncoding && (
              <span className={styles.encodingWarning}>
                ⚠️ Detected encoding differs from selected
              </span>
            )}
          </div>
        </div>
      )}
      
      {/* Data Preview */}
      {preview && !isProcessing && (
        <div className={styles.preview}>
          <h3 className={styles.previewTitle}>
            Data Preview (First {Math.min(preview.rows.length, PREVIEW_ROWS)} rows)
          </h3>
          <div className={styles.tableContainer}>
            <table className={styles.previewTable}>
              <thead>
                <tr>
                  <th className={styles.rowNumber}>#</th>
                  {preview.headers.map((header, idx) => (
                    <th key={idx} className={styles.headerCell}>
                      {header || `Column ${idx + 1}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, rowIdx) => (
                  <tr key={rowIdx}>
                    <td className={styles.rowNumber}>{rowIdx + 1}</td>
                    {preview.headers.map((_, colIdx) => (
                      <td key={colIdx} className={styles.dataCell}>
                        {row[colIdx] || <span className={styles.emptyCell}>—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {fileSummary.totalRows > PREVIEW_ROWS && (
            <p className={styles.previewNote}>
              Showing {PREVIEW_ROWS} of {fileSummary.totalRows.toLocaleString()} rows
            </p>
          )}
        </div>
      )}
    </div>
  );
}

