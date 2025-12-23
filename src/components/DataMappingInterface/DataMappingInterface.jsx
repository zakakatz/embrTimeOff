/**
 * Data Mapping Interface for Employee Import Fields
 * 
 * Provides intuitive tools to map CSV columns to employee data fields
 * with automatic suggestions and validation.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import styles from './DataMappingInterface.module.css';

// Target employee fields with metadata
const TARGET_FIELDS = [
  { id: 'employee_id', label: 'Employee ID', type: 'string', required: true, category: 'identification' },
  { id: 'first_name', label: 'First Name', type: 'string', required: true, category: 'personal' },
  { id: 'last_name', label: 'Last Name', type: 'string', required: true, category: 'personal' },
  { id: 'preferred_name', label: 'Preferred Name', type: 'string', required: false, category: 'personal' },
  { id: 'email', label: 'Email', type: 'email', required: true, category: 'contact' },
  { id: 'phone', label: 'Phone Number', type: 'phone', required: false, category: 'contact' },
  { id: 'mobile', label: 'Mobile Phone', type: 'phone', required: false, category: 'contact' },
  { id: 'date_of_birth', label: 'Date of Birth', type: 'date', required: false, category: 'personal' },
  { id: 'hire_date', label: 'Hire Date', type: 'date', required: true, category: 'employment' },
  { id: 'job_title', label: 'Job Title', type: 'string', required: true, category: 'employment' },
  { id: 'department', label: 'Department', type: 'string', required: true, category: 'employment' },
  { id: 'location', label: 'Location', type: 'string', required: false, category: 'employment' },
  { id: 'manager_id', label: 'Manager ID', type: 'string', required: false, category: 'employment' },
  { id: 'employment_type', label: 'Employment Type', type: 'enum', required: false, category: 'employment' },
  { id: 'salary', label: 'Salary', type: 'number', required: false, category: 'compensation' },
  { id: 'address', label: 'Address', type: 'string', required: false, category: 'contact' },
  { id: 'city', label: 'City', type: 'string', required: false, category: 'contact' },
  { id: 'state', label: 'State/Province', type: 'string', required: false, category: 'contact' },
  { id: 'postal_code', label: 'Postal Code', type: 'string', required: false, category: 'contact' },
  { id: 'country', label: 'Country', type: 'string', required: false, category: 'contact' },
];

// Common column name patterns for auto-matching
const COLUMN_PATTERNS = {
  employee_id: ['employee_id', 'emp_id', 'id', 'employee number', 'emp no', 'badge'],
  first_name: ['first_name', 'firstname', 'first', 'given name', 'fname'],
  last_name: ['last_name', 'lastname', 'last', 'surname', 'family name', 'lname'],
  preferred_name: ['preferred_name', 'preferred', 'nickname', 'known as'],
  email: ['email', 'email_address', 'e-mail', 'work email', 'corporate email'],
  phone: ['phone', 'telephone', 'phone_number', 'work phone', 'office phone'],
  mobile: ['mobile', 'cell', 'mobile_phone', 'cellphone', 'cell phone'],
  date_of_birth: ['dob', 'date_of_birth', 'birth_date', 'birthdate', 'birthday'],
  hire_date: ['hire_date', 'start_date', 'joined', 'date_hired', 'employment date'],
  job_title: ['job_title', 'title', 'position', 'role', 'job'],
  department: ['department', 'dept', 'division', 'team', 'unit'],
  location: ['location', 'office', 'work_location', 'site', 'branch'],
  manager_id: ['manager_id', 'manager', 'supervisor', 'reports_to', 'supervisor_id'],
  employment_type: ['employment_type', 'emp_type', 'type', 'status', 'classification'],
  salary: ['salary', 'pay', 'compensation', 'wage', 'annual_salary'],
  address: ['address', 'street', 'street_address', 'address1'],
  city: ['city', 'town'],
  state: ['state', 'province', 'region'],
  postal_code: ['postal_code', 'zip', 'zipcode', 'postcode'],
  country: ['country', 'nation'],
};

/**
 * Calculate match confidence between column name and field patterns
 */
function calculateMatchConfidence(columnName, fieldId) {
  const patterns = COLUMN_PATTERNS[fieldId] || [];
  const normalized = columnName.toLowerCase().replace(/[_\-\s]+/g, '');
  
  for (const pattern of patterns) {
    const normalizedPattern = pattern.toLowerCase().replace(/[_\-\s]+/g, '');
    
    // Exact match
    if (normalized === normalizedPattern) {
      return 1.0;
    }
    
    // Contains match
    if (normalized.includes(normalizedPattern) || normalizedPattern.includes(normalized)) {
      return 0.8;
    }
  }
  
  // Partial word match
  const words = columnName.toLowerCase().split(/[_\-\s]+/);
  for (const pattern of patterns) {
    const patternWords = pattern.toLowerCase().split(/[_\-\s]+/);
    const matchingWords = words.filter(w => patternWords.includes(w));
    if (matchingWords.length > 0) {
      return 0.5 * (matchingWords.length / Math.max(words.length, patternWords.length));
    }
  }
  
  return 0;
}

/**
 * Detect data type from sample values
 */
function detectDataType(values) {
  const nonEmpty = values.filter(v => v && v.trim());
  if (nonEmpty.length === 0) return 'unknown';
  
  // Check for email
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (nonEmpty.every(v => emailPattern.test(v))) return 'email';
  
  // Check for date
  const datePatterns = [
    /^\d{4}-\d{2}-\d{2}$/,
    /^\d{2}\/\d{2}\/\d{4}$/,
    /^\d{2}-\d{2}-\d{4}$/,
  ];
  if (nonEmpty.every(v => datePatterns.some(p => p.test(v)))) return 'date';
  
  // Check for number
  if (nonEmpty.every(v => !isNaN(parseFloat(v.replace(/[$,]/g, ''))))) return 'number';
  
  // Check for phone
  const phonePattern = /^[\d\s\-\+\(\)]{7,}$/;
  if (nonEmpty.every(v => phonePattern.test(v))) return 'phone';
  
  return 'string';
}

/**
 * Check type compatibility
 */
function checkTypeCompatibility(sourceType, targetType) {
  if (sourceType === targetType) return { compatible: true, warning: null };
  if (sourceType === 'unknown') return { compatible: true, warning: 'Data type could not be detected' };
  if (targetType === 'string') return { compatible: true, warning: null }; // Anything can be a string
  
  const compatibilityMatrix = {
    number: ['string'],
    email: ['string'],
    phone: ['string'],
    date: ['string'],
  };
  
  if (compatibilityMatrix[targetType]?.includes(sourceType)) {
    return { compatible: true, warning: `Converting ${sourceType} to ${targetType}` };
  }
  
  return { compatible: false, warning: `Incompatible types: ${sourceType} → ${targetType}` };
}

/**
 * Mapping Row Component
 */
function MappingRow({ 
  sourceColumn, 
  mapping, 
  targetFields, 
  sampleData,
  onMappingChange,
  onStatusChange,
  onDragStart,
  onDragOver,
  onDrop,
  isDragging,
  isDropTarget,
}) {
  const targetField = targetFields.find(f => f.id === mapping?.targetField);
  const sourceType = detectDataType(sampleData);
  const compatibility = targetField 
    ? checkTypeCompatibility(sourceType, targetField.type)
    : { compatible: true, warning: null };
  
  return (
    <div 
      className={`${styles.mappingRow} ${isDragging ? styles.dragging : ''} ${isDropTarget ? styles.dropTarget : ''}`}
      draggable
      onDragStart={(e) => onDragStart(e, sourceColumn)}
      onDragOver={onDragOver}
      onDrop={(e) => onDrop(e, sourceColumn)}
    >
      {/* Source Column */}
      <div className={styles.sourceColumn}>
        <div className={styles.columnHeader}>
          <span className={styles.dragHandle}>⋮⋮</span>
          <span className={styles.columnName}>{sourceColumn}</span>
        </div>
        <span className={styles.dataType}>{sourceType}</span>
      </div>
      
      {/* Arrow */}
      <div className={styles.mappingArrow}>→</div>
      
      {/* Target Field Select */}
      <div className={styles.targetColumn}>
        <select
          value={mapping?.targetField || ''}
          onChange={(e) => onMappingChange(sourceColumn, e.target.value)}
          className={`${styles.targetSelect} ${mapping?.targetField ? styles.mapped : ''}`}
        >
          <option value="">-- Select Field --</option>
          {targetFields.map(field => (
            <option key={field.id} value={field.id}>
              {field.label} {field.required ? '*' : ''}
            </option>
          ))}
        </select>
        
        {targetField && (
          <span className={styles.targetType}>{targetField.type}</span>
        )}
      </div>
      
      {/* Status */}
      <div className={styles.statusColumn}>
        <select
          value={mapping?.status || 'auto'}
          onChange={(e) => onStatusChange(sourceColumn, e.target.value)}
          className={styles.statusSelect}
        >
          <option value="auto">Auto</option>
          <option value="required">Required</option>
          <option value="optional">Optional</option>
          <option value="ignored">Ignored</option>
        </select>
      </div>
      
      {/* Confidence/Warnings */}
      <div className={styles.infoColumn}>
        {mapping?.confidence != null && mapping.confidence > 0 && (
          <span className={styles.confidenceBadge}>
            {Math.round(mapping.confidence * 100)}% match
          </span>
        )}
        {!compatibility.compatible && (
          <span className={styles.warningBadge}>⚠️ {compatibility.warning}</span>
        )}
        {compatibility.compatible && compatibility.warning && (
          <span className={styles.infoBadge}>ℹ️ {compatibility.warning}</span>
        )}
      </div>
    </div>
  );
}

/**
 * Preview Panel Component
 */
function PreviewPanel({ mappings, sourceData, sourceColumns }) {
  const previewRows = sourceData.slice(0, 3);
  
  const activeMappings = Object.entries(mappings)
    .filter(([_, m]) => m.targetField && m.status !== 'ignored')
    .sort((a, b) => sourceColumns.indexOf(a[0]) - sourceColumns.indexOf(b[0]));
  
  if (activeMappings.length === 0) {
    return (
      <div className={styles.previewPanel}>
        <h3 className={styles.previewTitle}>Data Preview</h3>
        <p className={styles.previewEmpty}>Map fields to see preview</p>
      </div>
    );
  }
  
  return (
    <div className={styles.previewPanel}>
      <h3 className={styles.previewTitle}>Data Preview (First 3 rows)</h3>
      <div className={styles.previewTable}>
        <table>
          <thead>
            <tr>
              <th className={styles.rowNum}>#</th>
              {activeMappings.map(([sourceCol, mapping]) => (
                <th key={sourceCol}>
                  <div className={styles.previewHeader}>
                    <span className={styles.sourceLabel}>{sourceCol}</span>
                    <span className={styles.targetLabel}>→ {mapping.targetField}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {previewRows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                <td className={styles.rowNum}>{rowIdx + 1}</td>
                {activeMappings.map(([sourceCol]) => {
                  const colIdx = sourceColumns.indexOf(sourceCol);
                  return (
                    <td key={sourceCol}>
                      {row[colIdx] || <span className={styles.emptyValue}>—</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Saved Configurations Panel
 */
function SavedConfigs({ configs, onLoad, onDelete }) {
  if (configs.length === 0) {
    return null;
  }
  
  return (
    <div className={styles.savedConfigs}>
      <h4 className={styles.configsTitle}>Saved Configurations</h4>
      <ul className={styles.configsList}>
        {configs.map(config => (
          <li key={config.id} className={styles.configItem}>
            <span className={styles.configName}>{config.name}</span>
            <span className={styles.configDate}>
              {new Date(config.savedAt).toLocaleDateString()}
            </span>
            <div className={styles.configActions}>
              <button onClick={() => onLoad(config)} className={styles.loadButton}>
                Load
              </button>
              <button onClick={() => onDelete(config.id)} className={styles.deleteButton}>
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Main Data Mapping Interface Component
 */
export default function DataMappingInterface({
  sourceColumns = [],
  sourceData = [],
  onMappingComplete,
  initialMappings = {},
}) {
  // State
  const [mappings, setMappings] = useState({});
  const [savedConfigs, setSavedConfigs] = useState([]);
  const [configName, setConfigName] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [draggedColumn, setDraggedColumn] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [filterCategory, setFilterCategory] = useState('all');
  
  // Auto-suggest mappings on mount
  useEffect(() => {
    if (sourceColumns.length > 0 && Object.keys(mappings).length === 0) {
      const autoMappings = {};
      
      sourceColumns.forEach(column => {
        let bestMatch = null;
        let bestConfidence = 0;
        
        TARGET_FIELDS.forEach(field => {
          const confidence = calculateMatchConfidence(column, field.id);
          if (confidence > bestConfidence && confidence >= 0.5) {
            bestMatch = field.id;
            bestConfidence = confidence;
          }
        });
        
        autoMappings[column] = {
          targetField: bestMatch,
          confidence: bestConfidence,
          status: 'auto',
        };
      });
      
      setMappings(autoMappings);
    }
  }, [sourceColumns]);
  
  // Load saved configs from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('import_mapping_configs');
    if (saved) {
      setSavedConfigs(JSON.parse(saved));
    }
  }, []);
  
  // Filter target fields by category
  const filteredTargetFields = useMemo(() => {
    if (filterCategory === 'all') return TARGET_FIELDS;
    return TARGET_FIELDS.filter(f => f.category === filterCategory);
  }, [filterCategory]);
  
  // Get sample data for a column
  const getSampleData = useCallback((columnName) => {
    const colIdx = sourceColumns.indexOf(columnName);
    if (colIdx === -1) return [];
    return sourceData.slice(0, 5).map(row => row[colIdx]);
  }, [sourceColumns, sourceData]);
  
  // Handle mapping change
  const handleMappingChange = useCallback((sourceColumn, targetField) => {
    setMappings(prev => ({
      ...prev,
      [sourceColumn]: {
        ...prev[sourceColumn],
        targetField: targetField || null,
        confidence: targetField ? 1.0 : 0,
      },
    }));
  }, []);
  
  // Handle status change
  const handleStatusChange = useCallback((sourceColumn, status) => {
    setMappings(prev => ({
      ...prev,
      [sourceColumn]: {
        ...prev[sourceColumn],
        status,
      },
    }));
  }, []);
  
  // Drag and drop handlers
  const handleDragStart = useCallback((e, column) => {
    setDraggedColumn(column);
    e.dataTransfer.effectAllowed = 'move';
  }, []);
  
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);
  
  const handleDrop = useCallback((e, targetColumn) => {
    e.preventDefault();
    if (draggedColumn && draggedColumn !== targetColumn) {
      // Swap mappings
      setMappings(prev => {
        const draggedMapping = prev[draggedColumn];
        const targetMapping = prev[targetColumn];
        return {
          ...prev,
          [draggedColumn]: { ...draggedMapping, targetField: targetMapping?.targetField },
          [targetColumn]: { ...targetMapping, targetField: draggedMapping?.targetField },
        };
      });
    }
    setDraggedColumn(null);
    setDropTarget(null);
  }, [draggedColumn]);
  
  // Save configuration
  const handleSaveConfig = useCallback(() => {
    if (!configName.trim()) return;
    
    const config = {
      id: Date.now().toString(),
      name: configName.trim(),
      mappings,
      savedAt: new Date().toISOString(),
    };
    
    const updated = [...savedConfigs, config];
    setSavedConfigs(updated);
    localStorage.setItem('import_mapping_configs', JSON.stringify(updated));
    setConfigName('');
    setShowSaveDialog(false);
  }, [configName, mappings, savedConfigs]);
  
  // Load configuration
  const handleLoadConfig = useCallback((config) => {
    // Only load mappings for columns that exist in current source
    const loadedMappings = {};
    sourceColumns.forEach(col => {
      if (config.mappings[col]) {
        loadedMappings[col] = config.mappings[col];
      }
    });
    setMappings(loadedMappings);
  }, [sourceColumns]);
  
  // Delete configuration
  const handleDeleteConfig = useCallback((configId) => {
    const updated = savedConfigs.filter(c => c.id !== configId);
    setSavedConfigs(updated);
    localStorage.setItem('import_mapping_configs', JSON.stringify(updated));
  }, [savedConfigs]);
  
  // Clear all mappings
  const handleClearMappings = useCallback(() => {
    setMappings(
      sourceColumns.reduce((acc, col) => ({
        ...acc,
        [col]: { targetField: null, status: 'auto', confidence: 0 },
      }), {})
    );
  }, [sourceColumns]);
  
  // Validate mappings
  const validationResult = useMemo(() => {
    const requiredFields = TARGET_FIELDS.filter(f => f.required);
    const mappedFields = new Set(
      Object.values(mappings)
        .filter(m => m.targetField && m.status !== 'ignored')
        .map(m => m.targetField)
    );
    
    const missingRequired = requiredFields.filter(f => !mappedFields.has(f.id));
    const duplicateMappings = Object.entries(mappings)
      .filter(([_, m]) => m.targetField)
      .reduce((acc, [col, m]) => {
        acc[m.targetField] = acc[m.targetField] || [];
        acc[m.targetField].push(col);
        return acc;
      }, {});
    
    const duplicates = Object.entries(duplicateMappings)
      .filter(([_, cols]) => cols.length > 1);
    
    return {
      isValid: missingRequired.length === 0 && duplicates.length === 0,
      missingRequired,
      duplicates,
      mappedCount: mappedFields.size,
      totalRequired: requiredFields.length,
    };
  }, [mappings]);
  
  // Handle complete
  const handleComplete = useCallback(() => {
    if (validationResult.isValid && onMappingComplete) {
      onMappingComplete(mappings);
    }
  }, [mappings, validationResult, onMappingComplete]);
  
  // Category counts
  const categoryCounts = useMemo(() => {
    const counts = { all: TARGET_FIELDS.length };
    TARGET_FIELDS.forEach(f => {
      counts[f.category] = (counts[f.category] || 0) + 1;
    });
    return counts;
  }, []);
  
  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <h2 className={styles.title}>Map Import Fields</h2>
          <p className={styles.subtitle}>
            Match CSV columns to employee data fields. Drag rows to reorder.
          </p>
        </div>
        
        <div className={styles.headerActions}>
          <button 
            className={styles.clearButton}
            onClick={handleClearMappings}
          >
            Clear All
          </button>
          <button 
            className={styles.saveConfigButton}
            onClick={() => setShowSaveDialog(true)}
          >
            💾 Save Config
          </button>
        </div>
      </header>
      
      {/* Save Dialog */}
      {showSaveDialog && (
        <div className={styles.saveDialog}>
          <input
            type="text"
            placeholder="Configuration name..."
            value={configName}
            onChange={(e) => setConfigName(e.target.value)}
            className={styles.configInput}
            autoFocus
          />
          <button onClick={handleSaveConfig} className={styles.confirmButton}>
            Save
          </button>
          <button onClick={() => setShowSaveDialog(false)} className={styles.cancelButton}>
            Cancel
          </button>
        </div>
      )}
      
      {/* Saved Configs */}
      <SavedConfigs
        configs={savedConfigs}
        onLoad={handleLoadConfig}
        onDelete={handleDeleteConfig}
      />
      
      {/* Category Filter */}
      <div className={styles.categoryFilter}>
        <span className={styles.filterLabel}>Filter fields:</span>
        {['all', 'identification', 'personal', 'contact', 'employment', 'compensation'].map(cat => (
          <button
            key={cat}
            className={`${styles.categoryButton} ${filterCategory === cat ? styles.active : ''}`}
            onClick={() => setFilterCategory(cat)}
          >
            {cat.charAt(0).toUpperCase() + cat.slice(1)} ({categoryCounts[cat] || 0})
          </button>
        ))}
      </div>
      
      {/* Mapping Table Header */}
      <div className={styles.tableHeader}>
        <div className={styles.sourceColumn}>Source Column</div>
        <div className={styles.mappingArrow}></div>
        <div className={styles.targetColumn}>Target Field</div>
        <div className={styles.statusColumn}>Status</div>
        <div className={styles.infoColumn}>Info</div>
      </div>
      
      {/* Mapping Rows */}
      <div className={styles.mappingList}>
        {sourceColumns.map(column => (
          <MappingRow
            key={column}
            sourceColumn={column}
            mapping={mappings[column]}
            targetFields={filteredTargetFields}
            sampleData={getSampleData(column)}
            onMappingChange={handleMappingChange}
            onStatusChange={handleStatusChange}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            isDragging={draggedColumn === column}
            isDropTarget={dropTarget === column}
          />
        ))}
      </div>
      
      {/* Preview Panel */}
      <PreviewPanel
        mappings={mappings}
        sourceData={sourceData}
        sourceColumns={sourceColumns}
      />
      
      {/* Validation Summary */}
      <div className={styles.validationSummary}>
        <div className={styles.validationStats}>
          <span className={styles.statItem}>
            <strong>{validationResult.mappedCount}</strong> fields mapped
          </span>
          <span className={styles.statItem}>
            <strong>{validationResult.totalRequired}</strong> required
          </span>
        </div>
        
        {validationResult.missingRequired.length > 0 && (
          <div className={styles.validationWarning}>
            ⚠️ Missing required: {validationResult.missingRequired.map(f => f.label).join(', ')}
          </div>
        )}
        
        {validationResult.duplicates.length > 0 && (
          <div className={styles.validationError}>
            ❌ Duplicate mappings: {validationResult.duplicates.map(([field]) => field).join(', ')}
          </div>
        )}
      </div>
      
      {/* Actions */}
      <div className={styles.actions}>
        <button
          className={styles.completeButton}
          onClick={handleComplete}
          disabled={!validationResult.isValid}
        >
          {validationResult.isValid ? '✓ Continue to Validation' : 'Fix Mapping Issues'}
        </button>
      </div>
    </div>
  );
}

