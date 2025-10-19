const gridContainer = document.getElementById('sheet');
const statusElement = document.getElementById('status');
const addRowButton = document.getElementById('add-row');
const addColumnButton = document.getElementById('add-column');
const resetButton = document.getElementById('reset-grid');
const renameButton = document.getElementById('rename-sheet');
const saveSheetButton = document.getElementById('save-sheet');
const sheetSelect = document.getElementById('sheet-select');
const importButton = document.getElementById('import-data');
const importModal = document.getElementById('import-modal');
const importForm = document.getElementById('import-form');
const importFileInput = document.getElementById('import-file');
const importIncludeHeaderInput = document.getElementById('import-include-header');
const importCancelButton = document.getElementById('import-cancel');
const importCloseButton = document.getElementById('close-import-modal');
const importPreviewContainer = document.getElementById('import-preview');
const importPreviewTable = document.getElementById('import-preview-table');
const importPreviewMeta = document.getElementById('import-preview-meta');
const importSourceName = document.getElementById('import-source-name');
const importFeedback = document.getElementById('import-feedback');
const importConfirmButton = document.getElementById('confirm-import');
const importResetButton = document.getElementById('reset-import');
const exportCsvLink = document.getElementById('download-csv');
const exportXlsxLink = document.getElementById('download-xlsx');

const state = {
  sheetId: initialSheetId,
  rowCount: initialRowCount,
  colCount: initialColCount,
  cells: new Map(),
  sheets: Array.isArray(initialSheets) ? initialSheets : [],
  rowData: [],
};

let pendingImport = null;

if (importConfirmButton) {
  importConfirmButton.disabled = true;
}

function keyFor(row, col) {
  return `${row}:${col}`;
}

function isFormula(value) {
  return typeof value === 'string' && value.trim().startsWith('=');
}

function columnToIndex(label) {
  let result = 0;
  const upper = String(label || '').toUpperCase();
  for (let i = 0; i < upper.length; i += 1) {
    const charCode = upper.charCodeAt(i);
    if (charCode < 65 || charCode > 90) {
      return Number.NaN;
    }
    result *= 26;
    result += charCode - 64;
  }
  return result - 1;
}

function columnLabel(index) {
  let label = '';
  let num = index;
  while (num >= 0) {
    label = String.fromCharCode((num % 26) + 65) + label;
    num = Math.floor(num / 26) - 1;
  }
  return label;
}

function getCellEntry(row, col) {
  return state.cells.get(keyFor(row, col));
}

function getCellRaw(row, col) {
  const entry = getCellEntry(row, col);
  if (!entry) {
    return '';
  }
  return typeof entry.raw === 'string' ? entry.raw : '';
}

function setCellRaw(row, col, rawValue) {
  const key = keyFor(row, col);
  if (rawValue === null || rawValue === undefined || rawValue === '') {
    state.cells.delete(key);
    return;
  }
  const entry = state.cells.get(key) ?? {};
  entry.raw = String(rawValue);
  delete entry.value;
  state.cells.set(key, entry);
}

function evaluateExpression(expression) {
  const sanitized = expression.replace(/\s+/g, '');
  if (!/^[0-9+\-*/().]*$/.test(sanitized)) {
    throw new Error('Invalid characters in formula');
  }
  // eslint-disable-next-line no-new-func
  const fn = new Function('"use strict"; return (' + expression + ');');
  const result = fn();
  if (typeof result === 'number' && Number.isFinite(result)) {
    return String(result);
  }
  throw new Error('Invalid formula result');
}

function evaluateCell(row, col, visiting = new Set()) {
  const key = keyFor(row, col);
  const entry = state.cells.get(key);
  if (!entry) {
    return '';
  }
  const raw = typeof entry.raw === 'string' ? entry.raw.trim() : '';
  if (!isFormula(raw)) {
    entry.value = raw;
    return entry.value;
  }

  if (visiting.has(key)) {
    entry.value = '#CYCLE!';
    return entry.value;
  }

  visiting.add(key);

  const formulaBody = raw.slice(1);
  let sawCycle = false;
  let sawError = false;
  const replaced = formulaBody.replace(/([A-Za-z]+)(\d+)/g, (match, colLabel, rowNumber) => {
    const refCol = columnToIndex(colLabel);
    const refRow = Number.parseInt(rowNumber, 10) - 1;
    if (Number.isNaN(refCol) || Number.isNaN(refRow)) {
      sawError = true;
      return '0';
    }
    const refValue = evaluateCell(refRow, refCol, visiting);
    if (refValue === '#CYCLE!') {
      sawCycle = true;
      return '0';
    }
    if (refValue === '#ERROR') {
      sawError = true;
      return '0';
    }
    const numeric = Number.parseFloat(refValue);
    if (Number.isFinite(numeric)) {
      return String(numeric);
    }
    return '0';
  });

  if (sawCycle) {
    entry.value = '#CYCLE!';
    visiting.delete(key);
    return entry.value;
  }
  if (sawError) {
    entry.value = '#ERROR';
    visiting.delete(key);
    return entry.value;
  }

  try {
    entry.value = evaluateExpression(replaced);
  } catch (error) {
    entry.value = '#ERROR';
  }

  visiting.delete(key);
  return entry.value;
}

function recalculateAllCells() {
  const keys = Array.from(state.cells.keys());
  keys.forEach((key) => {
    const [rowStr, colStr] = key.split(':');
    const row = Number.parseInt(rowStr, 10);
    const col = Number.parseInt(colStr, 10);
    if (!Number.isNaN(row) && !Number.isNaN(col)) {
      evaluateCell(row, col, new Set());
    }
  });
}

function getDisplayValue(row, col) {
  const entry = getCellEntry(row, col);
  if (!entry) {
    return '';
  }
  if (isFormula(entry.raw)) {
    return typeof entry.value === 'string' ? entry.value : '';
  }
  return typeof entry.raw === 'string' ? entry.raw : '';
}

function setStatus(message, type = 'info') {
  if (!statusElement) {
    return;
  }
  statusElement.textContent = message;
  statusElement.classList.remove('success', 'error', 'info');
  statusElement.classList.add(type);
}

async function extractErrorMessage(response) {
  try {
    const data = await response.json();
    if (data && typeof data.message === 'string') {
      return data.message;
    }
    if (data && typeof data.error === 'string') {
      return data.error;
    }
  } catch (error) {
    // Ignore JSON parsing errors; fall back to text below.
  }
  try {
    const text = await response.text();
    if (text) {
      return text;
    }
  } catch (error) {
    // Ignore text parsing errors.
  }
  return 'Request failed';
}

function updateExportLinks() {
  const sheetId = Number.isInteger(state.sheetId) ? state.sheetId : null;
  if (exportCsvLink) {
    const csvUrl = new URL('/export.csv', window.location.origin);
    if (sheetId !== null) {
      csvUrl.searchParams.set('sheetId', String(sheetId));
    }
    exportCsvLink.href = csvUrl.toString();
  }
  if (exportXlsxLink) {
    const xlsxUrl = new URL('/export.xlsx', window.location.origin);
    if (sheetId !== null) {
      xlsxUrl.searchParams.set('sheetId', String(sheetId));
    }
    exportXlsxLink.href = xlsxUrl.toString();
  }
}

function setImportFeedback(message, type = 'info') {
  if (!importFeedback) {
    return;
  }
  importFeedback.textContent = message || '';
  importFeedback.className = 'import-feedback';
  if (type === 'error') {
    importFeedback.classList.add('error');
  } else if (type === 'success') {
    importFeedback.classList.add('success');
  }
}

function resetImportModal(clearForm = true) {
  if (clearForm && importForm) {
    importForm.reset();
    if (importFileInput) {
      importFileInput.value = '';
    }
    if (importIncludeHeaderInput) {
      importIncludeHeaderInput.checked = true;
    }
  }
  if (importPreviewContainer) {
    importPreviewContainer.classList.add('hidden');
  }
  if (importPreviewTable) {
    importPreviewTable.innerHTML = '';
  }
  if (importPreviewMeta) {
    importPreviewMeta.textContent = '';
  }
  if (importSourceName) {
    importSourceName.textContent = '';
  }
  setImportFeedback('');
  pendingImport = null;
  if (importConfirmButton) {
    importConfirmButton.disabled = true;
  }
}

function openImportModal() {
  if (!importModal) {
    return;
  }
  resetImportModal();
  importModal.classList.remove('hidden');
  if (importFileInput) {
    importFileInput.focus();
  }
}

function closeImportModal() {
  if (!importModal) {
    return;
  }
  resetImportModal();
  importModal.classList.add('hidden');
}

function renderImportPreview(preview) {
  if (!importPreviewContainer || !importPreviewTable) {
    return;
  }

  importPreviewTable.innerHTML = '';

  const headerRow = Array.isArray(preview?.headerRow) ? preview.headerRow : [];
  const columns = Array.isArray(preview?.columns) ? preview.columns : [];
  const rows = Array.isArray(preview?.previewRows) ? preview.previewRows : [];

  let headerValues = headerRow.length ? headerRow : columns;
  const fallbackColumnCount = headerValues.length
    || (Array.isArray(rows[0]) ? rows[0].length : Number.parseInt(preview?.totalColumns, 10))
    || 0;
  if (!headerValues.length && fallbackColumnCount > 0) {
    headerValues = Array.from({ length: fallbackColumnCount }, (_, index) => columnLabel(index));
  }

  if (headerValues.length) {
    const thead = document.createElement('thead');
    const headerTr = document.createElement('tr');
    headerValues.forEach((value) => {
      const th = document.createElement('th');
      th.textContent = value ?? '';
      headerTr.appendChild(th);
    });
    thead.appendChild(headerTr);
    importPreviewTable.appendChild(thead);
  }

  const tbody = document.createElement('tbody');
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    const cells = Array.isArray(row) ? row : [];
    const cellCount = headerValues.length || cells.length;
    for (let index = 0; index < cellCount; index += 1) {
      const td = document.createElement('td');
      td.textContent = cells[index] ?? '';
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  });
  importPreviewTable.appendChild(tbody);

  if (importPreviewMeta) {
    let totalRows = Number.parseInt(preview?.totalRows, 10);
    if (Number.isNaN(totalRows)) {
      totalRows = rows.length;
    }
    let totalColumns = Number.parseInt(preview?.totalColumns, 10);
    if (Number.isNaN(totalColumns)) {
      totalColumns = headerValues.length || (rows[0] ? rows[0].length : 0);
    }
    const displayedRows = rows.length;
    const truncated = Boolean(preview?.truncated) && displayedRows < totalRows;
    if (totalRows === 0 && headerRow.length) {
      importPreviewMeta.textContent = `Preview contains only a header row (${headerRow.length} columns).`;
    } else if (truncated) {
      importPreviewMeta.textContent = `Showing first ${displayedRows} of ${totalRows} rows (${totalColumns} columns).`;
    } else {
      importPreviewMeta.textContent = `Detected ${totalRows} row${totalRows === 1 ? '' : 's'} and ${totalColumns} column${totalColumns === 1 ? '' : 's'}.`;
    }
  }

  if (importSourceName) {
    const name = typeof preview?.sourceName === 'string' ? preview.sourceName : '';
    importSourceName.textContent = name ? `File: ${name}` : '';
  }

  importPreviewContainer.classList.remove('hidden');
  if (importConfirmButton) {
    importConfirmButton.disabled = false;
  }
}

function populateSheetSelect() {
  if (!sheetSelect) {
    return;
  }
  const sheets = Array.isArray(state.sheets) ? state.sheets : [];
  sheetSelect.innerHTML = '';
  sheets.forEach((sheet) => {
    if (!sheet || typeof sheet.id !== 'number') {
      return;
    }
    const option = document.createElement('option');
    option.value = String(sheet.id);
    option.textContent = sheet.name;
    if (sheet.id === state.sheetId) {
      option.selected = true;
    }
    sheetSelect.appendChild(option);
  });
}

function rebuildRowData() {
  state.rowData = Array.from({ length: state.rowCount }, (_, rowIndex) => {
    const row = { __rowIndex: rowIndex };
    for (let colIndex = 0; colIndex < state.colCount; colIndex += 1) {
      row[`c${colIndex}`] = getCellRaw(rowIndex, colIndex);
    }
    return row;
  });
}

function updateRowDataCell(rowIndex, colIndex, rawValue) {
  if (rowIndex < 0 || rowIndex >= state.rowCount) {
    return;
  }
  while (state.rowData.length <= rowIndex) {
    state.rowData.push({ __rowIndex: state.rowData.length });
  }
  const row = state.rowData[rowIndex] ?? { __rowIndex: rowIndex };
  row.__rowIndex = rowIndex;
  row[`c${colIndex}`] = typeof rawValue === 'string' ? rawValue : '';
  state.rowData[rowIndex] = row;
}

function pruneInvalidCells() {
  const invalidKeys = [];
  state.cells.forEach((_, key) => {
    const [rowStr, colStr] = key.split(':');
    const row = Number.parseInt(rowStr, 10);
    const col = Number.parseInt(colStr, 10);
    if (row >= state.rowCount || col >= state.colCount) {
      invalidKeys.push(key);
    }
  });
  invalidKeys.forEach((key) => state.cells.delete(key));
}

let gridApi = null;

function refreshGridCells() {
  if (!gridApi) {
    return;
  }
  gridApi.refreshCells({ force: true });
}

function handleValueSetter(params) {
  const rowIndex = params.data?.__rowIndex ?? params.node?.rowIndex;
  const colId = params.column.getColId();
  const colIndex = Number.parseInt(colId, 10);
  if (!Number.isInteger(rowIndex) || Number.isNaN(colIndex)) {
    return false;
  }
  const newValue = typeof params.newValue === 'string' ? params.newValue.trim() : '';
  const previousRaw = getCellRaw(rowIndex, colIndex);
  if (previousRaw === newValue) {
    params.data[params.colDef.field] = previousRaw;
    return false;
  }
  if (newValue === '') {
    state.cells.delete(keyFor(rowIndex, colIndex));
  } else {
    setCellRaw(rowIndex, colIndex, newValue);
  }
  updateRowDataCell(rowIndex, colIndex, newValue);
  params.data[params.colDef.field] = newValue;
  return true;
}

function createColumnDefs() {
  const defs = [
    {
      headerName: '#',
      colId: 'rowNumber',
      valueGetter: (params) => (params.node ? params.node.rowIndex + 1 : ''),
      width: 70,
      pinned: 'left',
      editable: false,
      sortable: false,
      filter: false,
      resizable: false,
      suppressMenu: true,
      lockPosition: true,
      cellClass: 'row-number-cell',
    },
  ];

  for (let colIndex = 0; colIndex < state.colCount; colIndex += 1) {
    defs.push({
      headerName: columnLabel(colIndex),
      field: `c${colIndex}`,
      colId: String(colIndex),
      editable: true,
      minWidth: 96,
      valueSetter: handleValueSetter,
      valueFormatter(params) {
        const rowIndex = params.data?.__rowIndex ?? params.node?.rowIndex;
        if (!Number.isInteger(rowIndex)) {
          return '';
        }
        return getDisplayValue(rowIndex, colIndex);
      },
      cellClass(params) {
        const rowIndex = params.data?.__rowIndex ?? params.node?.rowIndex;
        if (!Number.isInteger(rowIndex)) {
          return '';
        }
        return isFormula(getCellRaw(rowIndex, colIndex)) ? 'formula-cell' : '';
      },
    });
  }

  return defs;
}

function updateGridStructure() {
  if (!gridApi) {
    return;
  }
  gridApi.setColumnDefs(createColumnDefs());
  gridApi.setRowData(state.rowData);
  if (typeof gridApi.sizeColumnsToFit === 'function') {
    gridApi.sizeColumnsToFit();
  }
  refreshGridCells();
}

function handleCellValueChanged(params) {
  const rowIndex = params.data?.__rowIndex ?? params.node?.rowIndex;
  const colId = params.column.getColId();
  const colIndex = Number.parseInt(colId, 10);
  if (!Number.isInteger(rowIndex) || Number.isNaN(colIndex)) {
    return;
  }
  recalculateAllCells();
  refreshGridCells();
  const raw = getCellRaw(rowIndex, colIndex);
  saveChanges({
    updates: [
      {
        row: rowIndex,
        col: colIndex,
        value: raw,
      },
    ],
  });
}

async function loadGrid(sheetId = state.sheetId) {
  try {
    setStatus('Loading…', 'info');
    const url = new URL('/data', window.location.origin);
    if (typeof sheetId === 'number' && !Number.isNaN(sheetId)) {
      url.searchParams.set('sheetId', sheetId);
    }
    url.searchParams.set('page', '1');
    url.searchParams.set('pageSize', '0');
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to load grid');
    }
    const data = await response.json();
    state.sheetId = data.sheetId;
    state.rowCount = data.rowCount;
    state.colCount = data.colCount;
    if (Array.isArray(data.sheets)) {
      state.sheets = data.sheets;
    }
    state.cells.clear();
    if (Array.isArray(data.rows)) {
      data.rows.forEach((row) => {
        const rowIndex = Number.parseInt(row.rowIndex ?? row.rowindex ?? row.row_index, 10);
        if (!Number.isInteger(rowIndex) || rowIndex < 0) {
          return;
        }
        const values = Array.isArray(row.values) ? row.values : [];
        values.forEach((value, colIndex) => {
          if (value !== null && value !== undefined && value !== '') {
            setCellRaw(rowIndex, colIndex, String(value));
          }
        });
      });
    }
    recalculateAllCells();
    rebuildRowData();
    updateGridStructure();
    populateSheetSelect();
    updateExportLinks();
    setStatus('Ready', 'info');
  } catch (error) {
    console.error(error);
    setStatus('Unable to load spreadsheet', 'error');
  }
}

async function saveChanges({ updates = [], rowCount = null, colCount = null }) {
  if (!updates.length && rowCount === null && colCount === null) {
    return;
  }
  try {
    setStatus('Saving…', 'info');
    const payload = { sheetId: state.sheetId };
    if (updates.length) {
      payload.updates = updates;
    }
    if (typeof rowCount === 'number') {
      payload.rowCount = rowCount;
    }
    if (typeof colCount === 'number') {
      payload.colCount = colCount;
    }
    const method = rowCount !== null || colCount !== null ? 'POST' : 'PATCH';
    const response = await fetch('/data', {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error('Save failed');
    }
    const result = await response.json();
    const previousRowCount = state.rowCount;
    const previousColCount = state.colCount;
    state.sheetId = result.sheetId;
    if (typeof result.rowCount === 'number') {
      state.rowCount = result.rowCount;
    }
    if (typeof result.colCount === 'number') {
      state.colCount = result.colCount;
    }
    const dimensionChanged = previousRowCount !== state.rowCount || previousColCount !== state.colCount;
    pruneInvalidCells();
    if (dimensionChanged) {
      rebuildRowData();
      updateGridStructure();
    } else if (updates.length) {
      updates.forEach((item) => {
        if (typeof item.row !== 'number' || typeof item.col !== 'number') {
          return;
        }
        const raw = typeof item.value === 'string' ? item.value.trim() : '';
        updateRowDataCell(item.row, item.col, raw);
      });
      refreshGridCells();
    }
    setStatus('All changes saved', 'success');
  } catch (error) {
    console.error(error);
    setStatus('Failed to save changes', 'error');
  }
}

function collectSheetSnapshot() {
  const snapshot = [];
  for (let row = 0; row < state.rowCount; row += 1) {
    for (let col = 0; col < state.colCount; col += 1) {
      snapshot.push({ row, col, value: getCellRaw(row, col) });
    }
  }
  return snapshot;
}

if (addRowButton) {
  addRowButton.addEventListener('click', () => {
    saveChanges({ rowCount: state.rowCount + 1 });
  });
}

if (addColumnButton) {
  addColumnButton.addEventListener('click', () => {
    saveChanges({ colCount: state.colCount + 1 });
  });
}

if (resetButton) {
  resetButton.addEventListener('click', () => {
    if (!window.confirm('This will clear all values in the current sheet. Continue?')) {
      return;
    }
    const updates = [];
    state.cells.forEach((_, key) => {
      const [rowStr, colStr] = key.split(':');
      const row = Number.parseInt(rowStr, 10);
      const col = Number.parseInt(colStr, 10);
      updates.push({ row, col, value: '' });
    });
    state.cells.clear();
    recalculateAllCells();
    rebuildRowData();
    updateGridStructure();
    saveChanges({ updates, rowCount: state.rowCount, colCount: state.colCount });
  });
}

if (importButton) {
  importButton.addEventListener('click', () => {
    if (!Number.isInteger(state.sheetId)) {
      setStatus('Select a sheet before importing.', 'error');
      return;
    }
    openImportModal();
  });
}

if (importCancelButton) {
  importCancelButton.addEventListener('click', () => {
    closeImportModal();
  });
}

if (importCloseButton) {
  importCloseButton.addEventListener('click', () => {
    closeImportModal();
  });
}

if (importResetButton) {
  importResetButton.addEventListener('click', () => {
    resetImportModal();
  });
}

if (importModal) {
  importModal.addEventListener('click', (event) => {
    if (event.target === importModal) {
      closeImportModal();
    }
  });
}

if (importForm) {
  importForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!Number.isInteger(state.sheetId)) {
      setImportFeedback('Select a sheet before importing.', 'error');
      return;
    }
    if (!importFileInput || importFileInput.files.length === 0) {
      setImportFeedback('Select a CSV or XLSX file to upload.', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', importFileInput.files[0]);
    formData.append('sheetId', String(state.sheetId));
    const includeHeader = importIncludeHeaderInput ? importIncludeHeaderInput.checked : true;
    formData.append('includeHeader', includeHeader ? 'true' : 'false');

    try {
      setStatus('Processing import…', 'info');
      setImportFeedback('Uploading file…');
      if (importConfirmButton) {
        importConfirmButton.disabled = true;
      }
      const response = await fetch('/import', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const message = await extractErrorMessage(response);
        setImportFeedback(message, 'error');
        setStatus('Unable to prepare import', 'error');
        return;
      }
      const result = await response.json();
      if (!result || typeof result.previewId !== 'string') {
        setImportFeedback('Unexpected response from the server.', 'error');
        setStatus('Unable to prepare import', 'error');
        return;
      }
      const previewSheetId = Number.parseInt(result.sheetId, 10);
      pendingImport = {
        previewId: result.previewId,
        sheetId: Number.isNaN(previewSheetId) ? state.sheetId : previewSheetId,
      };
      renderImportPreview(result);
      setImportFeedback('Preview ready. Review the data before confirming.', 'success');
      setStatus('Import preview ready', 'info');
    } catch (error) {
      console.error(error);
      setImportFeedback('Unable to upload file.', 'error');
      setStatus('Unable to upload file', 'error');
    }
  });
}

if (importConfirmButton) {
  importConfirmButton.addEventListener('click', async () => {
    if (!pendingImport || typeof pendingImport.previewId !== 'string') {
      setImportFeedback('Upload a file before confirming the import.', 'error');
      return;
    }
    if (pendingImport.sheetId !== state.sheetId) {
      setImportFeedback('The preview was created for a different sheet. Upload the file again.', 'error');
      return;
    }
    try {
      importConfirmButton.disabled = true;
      setImportFeedback('Importing data…');
      setStatus('Importing data…', 'info');
      const response = await fetch('/import/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sheetId: state.sheetId,
          previewId: pendingImport.previewId,
        }),
      });
      if (!response.ok) {
        const message = await extractErrorMessage(response);
        setImportFeedback(message, 'error');
        setStatus('Import failed', 'error');
        importConfirmButton.disabled = false;
        return;
      }
      await response.json();
      setImportFeedback('Import complete.', 'success');
      setStatus('Import complete', 'success');
      closeImportModal();
      await loadGrid(state.sheetId);
    } catch (error) {
      console.error(error);
      setImportFeedback('Import failed.', 'error');
      setStatus('Import failed', 'error');
      importConfirmButton.disabled = false;
    }
  });
}

window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && importModal && !importModal.classList.contains('hidden')) {
    closeImportModal();
  }
});

if (sheetSelect) {
  sheetSelect.addEventListener('change', (event) => {
    const selectedId = Number.parseInt(event.target.value, 10);
    if (Number.isNaN(selectedId) || selectedId === state.sheetId) {
      return;
    }
    loadGrid(selectedId);
  });
}

if (renameButton) {
  renameButton.addEventListener('click', async () => {
    const current = Array.isArray(state.sheets)
      ? state.sheets.find((sheet) => sheet.id === state.sheetId)
      : null;
    const proposed = window.prompt('Rename sheet', current ? current.name : '');
    if (proposed === null) {
      return;
    }
    const name = proposed.trim();
    if (!name) {
      setStatus('Sheet name cannot be empty', 'error');
      return;
    }
    try {
      setStatus('Renaming…', 'info');
      const response = await fetch(`/api/sheets/${state.sheetId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name }),
      });
      if (response.status === 409) {
        setStatus('A sheet with that name already exists', 'error');
        return;
      }
      if (!response.ok) {
        throw new Error('Rename failed');
      }
      const result = await response.json();
      state.sheets = Array.isArray(result.sheets) ? result.sheets : state.sheets;
      populateSheetSelect();
      setStatus('Sheet renamed', 'success');
    } catch (error) {
      console.error(error);
      setStatus('Unable to rename sheet', 'error');
    }
  });
}

if (saveSheetButton) {
  saveSheetButton.addEventListener('click', async () => {
    const proposed = window.prompt('Save current sheet as…');
    if (proposed === null) {
      return;
    }
    const name = proposed.trim();
    if (!name) {
      setStatus('Sheet name cannot be empty', 'error');
      return;
    }
    const snapshot = collectSheetSnapshot();
    try {
      setStatus('Saving copy…', 'info');
      const response = await fetch('/api/sheets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          rowCount: state.rowCount,
          colCount: state.colCount,
          cells: snapshot,
        }),
      });
      if (response.status === 409) {
        setStatus('A sheet with that name already exists', 'error');
        return;
      }
      if (!response.ok) {
        throw new Error('Save failed');
      }
      const result = await response.json();
      state.sheets = Array.isArray(result.sheets) ? result.sheets : state.sheets;
      await loadGrid(result.sheetId);
      setStatus('Sheet copy saved', 'success');
    } catch (error) {
      console.error(error);
      setStatus('Unable to save sheet copy', 'error');
    }
  });
}

rebuildRowData();

const gridOptions = {
  rowData: state.rowData,
  columnDefs: createColumnDefs(),
  defaultColDef: {
    editable: true,
    resizable: true,
    sortable: false,
    filter: false,
  },
  maintainColumnOrder: true,
  enterMovesDownAfterEdit: true,
  stopEditingWhenCellsLoseFocus: true,
  onCellValueChanged: handleCellValueChanged,
  getRowId: (params) => (params.data ? `row-${params.data.__rowIndex}` : `row-${params.node?.rowIndex ?? 0}`),
  onGridReady(params) {
    gridApi = params.api;
    if (typeof params.api.sizeColumnsToFit === 'function') {
      params.api.sizeColumnsToFit();
    }
  },
};

function initializeGrid() {
  if (!gridContainer) {
    return;
  }
  if (!window.agGrid) {
    console.error('AG Grid library failed to load');
    return;
  }
  gridApi = agGrid.createGrid(gridContainer, gridOptions);
}

window.addEventListener('load', () => {
  initializeGrid();
  populateSheetSelect();
  updateExportLinks();
  loadGrid();
});
