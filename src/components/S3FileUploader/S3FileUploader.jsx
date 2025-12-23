/**
 * S3FileUploader Component
 * 
 * A comprehensive file upload system with drag-and-drop functionality,
 * S3 presigned URL integration, progress tracking, and multi-file support.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import styles from './S3FileUploader.module.css';

// File status states
const FileStatus = {
  PENDING: 'pending',
  UPLOADING: 'uploading',
  COMPLETED: 'completed',
  FAILED: 'failed',
};

// Default configuration
const DEFAULT_CONFIG = {
  maxFileSize: 10 * 1024 * 1024, // 10MB
  allowedTypes: ['image/*', 'application/pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv'],
  maxFiles: 10,
  presignedUrlEndpoint: '/api/v1/uploads/presigned-url',
};

/**
 * Generate unique file ID
 */
function generateFileId() {
  return `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
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
 * Get file type icon
 */
function getFileIcon(mimeType, fileName) {
  if (mimeType?.startsWith('image/')) return '🖼️';
  if (mimeType === 'application/pdf') return '📄';
  if (fileName?.match(/\.(doc|docx)$/i)) return '📝';
  if (fileName?.match(/\.(xls|xlsx|csv)$/i)) return '📊';
  if (fileName?.match(/\.(zip|rar|7z)$/i)) return '📦';
  return '📎';
}

/**
 * Check if file type is allowed
 */
function isFileTypeAllowed(file, allowedTypes) {
  if (!allowedTypes || allowedTypes.length === 0) return true;

  const fileName = file.name.toLowerCase();
  const mimeType = file.type;

  return allowedTypes.some((type) => {
    if (type.includes('*')) {
      // Handle wildcards like 'image/*'
      const prefix = type.replace('*', '');
      return mimeType.startsWith(prefix);
    }
    if (type.startsWith('.')) {
      // Handle extensions like '.pdf'
      return fileName.endsWith(type.toLowerCase());
    }
    // Handle exact MIME types
    return mimeType === type;
  });
}

/**
 * FilePreview Component
 */
function FilePreview({ file, previewUrl }) {
  const isImage = file.type?.startsWith('image/');

  if (isImage && previewUrl) {
    return (
      <div className={styles.previewImage}>
        <img src={previewUrl} alt={file.name} />
      </div>
    );
  }

  return (
    <div className={styles.previewIcon}>
      <span className={styles.fileIcon}>{getFileIcon(file.type, file.name)}</span>
    </div>
  );
}

FilePreview.propTypes = {
  file: PropTypes.object.isRequired,
  previewUrl: PropTypes.string,
};

/**
 * ProgressBar Component
 */
function ProgressBar({ progress, status }) {
  const getProgressClass = () => {
    if (status === FileStatus.COMPLETED) return styles.progressSuccess;
    if (status === FileStatus.FAILED) return styles.progressError;
    return styles.progressActive;
  };

  return (
    <div className={styles.progressWrapper}>
      <div className={styles.progressTrack}>
        <div
          className={`${styles.progressBar} ${getProgressClass()}`}
          style={{ width: `${progress}%` }}
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin="0"
          aria-valuemax="100"
        />
      </div>
      <span className={styles.progressText}>{Math.round(progress)}%</span>
    </div>
  );
}

ProgressBar.propTypes = {
  progress: PropTypes.number.isRequired,
  status: PropTypes.string.isRequired,
};

/**
 * FileItem Component
 */
function FileItem({ fileData, onRemove, onRetry }) {
  const { id, file, status, progress, error, uploadedUrl, previewUrl } = fileData;

  const statusText = {
    [FileStatus.PENDING]: 'Waiting...',
    [FileStatus.UPLOADING]: 'Uploading...',
    [FileStatus.COMPLETED]: 'Completed',
    [FileStatus.FAILED]: error || 'Failed',
  };

  const statusClass = {
    [FileStatus.PENDING]: styles.statusPending,
    [FileStatus.UPLOADING]: styles.statusUploading,
    [FileStatus.COMPLETED]: styles.statusCompleted,
    [FileStatus.FAILED]: styles.statusFailed,
  };

  return (
    <div className={`${styles.fileItem} ${statusClass[status]}`}>
      <FilePreview file={file} previewUrl={previewUrl} />

      <div className={styles.fileInfo}>
        <div className={styles.fileName} title={file.name}>
          {file.name}
        </div>
        <div className={styles.fileMeta}>
          <span className={styles.fileSize}>{formatFileSize(file.size)}</span>
          <span className={styles.fileStatus}>{statusText[status]}</span>
        </div>

        {(status === FileStatus.UPLOADING || status === FileStatus.PENDING) && (
          <ProgressBar progress={progress} status={status} />
        )}

        {status === FileStatus.FAILED && error && (
          <div className={styles.errorMessage}>{error}</div>
        )}
      </div>

      <div className={styles.fileActions}>
        {status === FileStatus.FAILED && (
          <button
            type="button"
            className={styles.retryBtn}
            onClick={() => onRetry(id)}
            aria-label={`Retry uploading ${file.name}`}
          >
            ↻
          </button>
        )}
        <button
          type="button"
          className={styles.removeBtn}
          onClick={() => onRemove(id)}
          aria-label={`Remove ${file.name}`}
        >
          ✕
        </button>
      </div>
    </div>
  );
}

FileItem.propTypes = {
  fileData: PropTypes.shape({
    id: PropTypes.string.isRequired,
    file: PropTypes.object.isRequired,
    status: PropTypes.string.isRequired,
    progress: PropTypes.number.isRequired,
    error: PropTypes.string,
    uploadedUrl: PropTypes.string,
    previewUrl: PropTypes.string,
  }).isRequired,
  onRemove: PropTypes.func.isRequired,
  onRetry: PropTypes.func.isRequired,
};

/**
 * Main S3FileUploader Component
 */
export function S3FileUploader({
  onUploadComplete,
  onUploadError,
  onFilesChange,
  config = {},
  disabled = false,
  className = '',
}) {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };
  const { maxFileSize, allowedTypes, maxFiles, presignedUrlEndpoint } = mergedConfig;

  const [files, setFiles] = useState([]);
  const [dragState, setDragState] = useState('idle'); // idle, hover, active, rejected
  const fileInputRef = useRef(null);
  const dropZoneRef = useRef(null);

  // Notify parent of file changes
  useEffect(() => {
    onFilesChange?.(files);
  }, [files, onFilesChange]);

  /**
   * Create file preview URL
   */
  const createPreview = useCallback((file) => {
    if (file.type?.startsWith('image/')) {
      return URL.createObjectURL(file);
    }
    return null;
  }, []);

  /**
   * Validate a file
   */
  const validateFile = useCallback(
    (file) => {
      if (file.size > maxFileSize) {
        return `File exceeds ${formatFileSize(maxFileSize)} limit`;
      }

      if (!isFileTypeAllowed(file, allowedTypes)) {
        return 'File type not allowed';
      }

      return null;
    },
    [maxFileSize, allowedTypes]
  );

  /**
   * Get presigned URL from server
   */
  const getPresignedUrl = useCallback(
    async (file) => {
      const response = await fetch(presignedUrlEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fileName: file.name,
          fileType: file.type,
          fileSize: file.size,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get upload URL');
      }

      return response.json();
    },
    [presignedUrlEndpoint]
  );

  /**
   * Upload file to S3 using presigned URL
   */
  const uploadToS3 = useCallback(async (file, presignedData, onProgress) => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = (event.loaded / event.total) * 100;
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve({
            url: presignedData.fileUrl || presignedData.url,
            key: presignedData.key,
          });
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload cancelled'));
      });

      xhr.open('PUT', presignedData.uploadUrl);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);
    });
  }, []);

  /**
   * Upload a single file
   */
  const uploadFile = useCallback(
    async (fileId) => {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, status: FileStatus.UPLOADING, progress: 0 } : f
        )
      );

      const fileData = files.find((f) => f.id === fileId);
      if (!fileData) return;

      try {
        // Get presigned URL
        const presignedData = await getPresignedUrl(fileData.file);

        // Upload to S3
        const result = await uploadToS3(fileData.file, presignedData, (progress) => {
          setFiles((prev) =>
            prev.map((f) => (f.id === fileId ? { ...f, progress } : f))
          );
        });

        // Update file status
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: FileStatus.COMPLETED,
                  progress: 100,
                  uploadedUrl: result.url,
                  uploadedKey: result.key,
                }
              : f
          )
        );

        onUploadComplete?.({
          id: fileId,
          fileName: fileData.file.name,
          url: result.url,
          key: result.key,
        });
      } catch (error) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? { ...f, status: FileStatus.FAILED, error: error.message }
              : f
          )
        );

        onUploadError?.({
          id: fileId,
          fileName: fileData.file.name,
          error: error.message,
        });
      }
    },
    [files, getPresignedUrl, uploadToS3, onUploadComplete, onUploadError]
  );

  /**
   * Add files to the upload queue
   */
  const addFiles = useCallback(
    (newFiles) => {
      const filesToAdd = [];

      for (const file of newFiles) {
        // Check max files limit
        if (files.length + filesToAdd.length >= maxFiles) {
          break;
        }

        const validationError = validateFile(file);
        const previewUrl = createPreview(file);

        filesToAdd.push({
          id: generateFileId(),
          file,
          status: validationError ? FileStatus.FAILED : FileStatus.PENDING,
          progress: 0,
          error: validationError,
          previewUrl,
          uploadedUrl: null,
          uploadedKey: null,
        });
      }

      if (filesToAdd.length > 0) {
        setFiles((prev) => [...prev, ...filesToAdd]);

        // Auto-start upload for valid files
        filesToAdd
          .filter((f) => f.status === FileStatus.PENDING)
          .forEach((f) => {
            setTimeout(() => uploadFile(f.id), 100);
          });
      }
    },
    [files.length, maxFiles, validateFile, createPreview, uploadFile]
  );

  /**
   * Handle file input change
   */
  const handleFileInput = useCallback(
    (event) => {
      const selectedFiles = Array.from(event.target.files || []);
      addFiles(selectedFiles);
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [addFiles]
  );

  /**
   * Handle drag events
   */
  const handleDragEnter = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    setDragState('hover');
  }, []);

  const handleDragOver = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();

      // Check if files are valid
      const items = event.dataTransfer?.items;
      if (items) {
        const hasValidFiles = Array.from(items).some(
          (item) => item.kind === 'file'
        );
        setDragState(hasValidFiles ? 'active' : 'rejected');
      }
    },
    []
  );

  const handleDragLeave = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();

    // Only reset if leaving the drop zone entirely
    if (!dropZoneRef.current?.contains(event.relatedTarget)) {
      setDragState('idle');
    }
  }, []);

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      setDragState('idle');

      if (disabled) return;

      const droppedFiles = Array.from(event.dataTransfer?.files || []);
      addFiles(droppedFiles);
    },
    [disabled, addFiles]
  );

  /**
   * Remove a file
   */
  const handleRemove = useCallback((fileId) => {
    setFiles((prev) => {
      const fileToRemove = prev.find((f) => f.id === fileId);
      if (fileToRemove?.previewUrl) {
        URL.revokeObjectURL(fileToRemove.previewUrl);
      }
      return prev.filter((f) => f.id !== fileId);
    });
  }, []);

  /**
   * Retry a failed upload
   */
  const handleRetry = useCallback(
    (fileId) => {
      const fileData = files.find((f) => f.id === fileId);
      if (!fileData) return;

      // Re-validate
      const validationError = validateFile(fileData.file);
      if (validationError) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId ? { ...f, error: validationError } : f
          )
        );
        return;
      }

      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? { ...f, status: FileStatus.PENDING, progress: 0, error: null }
            : f
        )
      );

      setTimeout(() => uploadFile(fileId), 100);
    },
    [files, validateFile, uploadFile]
  );

  /**
   * Trigger file input click
   */
  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  // Cleanup preview URLs on unmount
  useEffect(() => {
    return () => {
      files.forEach((f) => {
        if (f.previewUrl) {
          URL.revokeObjectURL(f.previewUrl);
        }
      });
    };
  }, []);

  // Calculate stats
  const stats = {
    total: files.length,
    pending: files.filter((f) => f.status === FileStatus.PENDING).length,
    uploading: files.filter((f) => f.status === FileStatus.UPLOADING).length,
    completed: files.filter((f) => f.status === FileStatus.COMPLETED).length,
    failed: files.filter((f) => f.status === FileStatus.FAILED).length,
  };

  const dragStateClass = {
    idle: '',
    hover: styles.dragHover,
    active: styles.dragActive,
    rejected: styles.dragRejected,
  };

  return (
    <div className={`${styles.uploader} ${className}`}>
      {/* Drop Zone */}
      <div
        ref={dropZoneRef}
        className={`${styles.dropZone} ${dragStateClass[dragState]} ${disabled ? styles.disabled : ''}`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={disabled ? undefined : openFilePicker}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => e.key === 'Enter' && openFilePicker()}
        aria-label="Drop files here or click to select"
      >
        <div className={styles.dropZoneContent}>
          <div className={styles.uploadIcon}>
            {dragState === 'rejected' ? '🚫' : '📁'}
          </div>
          <p className={styles.dropZoneText}>
            {dragState === 'active'
              ? 'Drop files here'
              : dragState === 'rejected'
              ? 'Invalid file type'
              : 'Drag & drop files here, or click to select'}
          </p>
          <p className={styles.dropZoneHint}>
            Max {formatFileSize(maxFileSize)} per file • Up to {maxFiles} files
          </p>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          className={styles.fileInput}
          onChange={handleFileInput}
          multiple
          accept={allowedTypes.join(',')}
          disabled={disabled}
          aria-hidden="true"
        />
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className={styles.fileList}>
          <div className={styles.fileListHeader}>
            <h3 className={styles.fileListTitle}>
              Files ({stats.completed}/{stats.total})
            </h3>
            {stats.uploading > 0 && (
              <span className={styles.uploadingIndicator}>
                Uploading {stats.uploading}...
              </span>
            )}
          </div>

          <div className={styles.fileListContent}>
            {files.map((fileData) => (
              <FileItem
                key={fileData.id}
                fileData={fileData}
                onRemove={handleRemove}
                onRetry={handleRetry}
              />
            ))}
          </div>

          {stats.failed > 0 && (
            <div className={styles.fileListFooter}>
              <span className={styles.failedCount}>
                {stats.failed} file(s) failed to upload
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

S3FileUploader.propTypes = {
  onUploadComplete: PropTypes.func,
  onUploadError: PropTypes.func,
  onFilesChange: PropTypes.func,
  config: PropTypes.shape({
    maxFileSize: PropTypes.number,
    allowedTypes: PropTypes.arrayOf(PropTypes.string),
    maxFiles: PropTypes.number,
    presignedUrlEndpoint: PropTypes.string,
  }),
  disabled: PropTypes.bool,
  className: PropTypes.string,
};

export default S3FileUploader;

