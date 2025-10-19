const sheetElement = document.getElementById('sheet');
const statusElement = document.getElementById('status');
const addRowButton = document.getElementById('add-row');
const addColumnButton = document.getElementById('add-column');
const resetButton = document.getElementById('reset-grid');
const renameButton = document.getElementById('rename-sheet');
const saveSheetButton = document.getElementById('save-sheet');
const sheetSelect = document.getElementById('sheet-select');
const cellTemplate = document.getElementById('cell-template');

const CSRF_COOKIE_NAME = 'spreadsheet_csrftoken';

function getCookie(name) {
  const cookies = document.cookie.split(';');
  for (let i = 0; i < cookies.length; i += 1) {
    const cookie = cookies[i].trim();
    if (cookie.startsWith(`${name}=`)) {
      return cookie.slice(name.length + 1);
    }
  }
  return '';
}

function csrfHeaders() {
  const token = getCookie(CSRF_COOKIE_NAME);
  return token ? { 'X-CSRFToken': token } : {};
}

const state = {
  sheetId: initialSheetId,
  rowCount: initialRowCount,
  colCount: initialColCount,
  cells: new Map(),
  sheets: Array.isArray(initialSheets) ? initialSheets : [],
};

const keyFor = (row, col) => `${row}:${col}`;

const isFormula = (value) => typeof value === 'string' && value.trim().startsWith('=');

function columnToIndex(label) {
  let result = 0;
  const upper = label.toUpperCase();
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
  state.cells.set(key, entry);
}

function evaluateExpression(expression) {
  const sanitized = expression.replace(/\s+/g, '');
  if (!/^[0-9+\-*/().]*$/.test(sanitized)) {
    throw new Error('Invalid characters in formula');
  }
  // eslint-disable-next-line no-new-func
  const fn = new Function(`"use strict"; return (${expression});`);
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
  statusElement.textContent = message;
  statusElement.classList.remove('success', 'error', 'info');
  statusElement.classList.add(type);
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

function focusCell(row, col) {
  const cell = sheetElement.querySelector(`td.cell[data-row="${row}"][data-col="${col}"]`);
  if (cell) {
    cell.focus();
  }
}

function populateSheetSelect() {
  if (!Array.isArray(state.sheets)) {
    state.sheets = [];
  }
  sheetSelect.innerHTML = '';
  state.sheets.forEach((sheet) => {
    const option = document.createElement('option');
    option.value = sheet.id;
    option.textContent = sheet.name;
    if (sheet.id === state.sheetId) {
      option.selected = true;
    }
    sheetSelect.appendChild(option);
  });
}

function renderTable() {
  sheetElement.innerHTML = '';

  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  const corner = document.createElement('th');
  corner.classList.add('corner');
  headRow.appendChild(corner);

  for (let col = 0; col < state.colCount; col += 1) {
    const th = document.createElement('th');
    th.textContent = columnLabel(col);
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  sheetElement.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (let row = 0; row < state.rowCount; row += 1) {
    const tr = document.createElement('tr');
    const rowHeader = document.createElement('th');
    rowHeader.textContent = row + 1;
    tr.appendChild(rowHeader);

    for (let col = 0; col < state.colCount; col += 1) {
      const cellNode = cellTemplate.content.firstElementChild.cloneNode(true);
      cellNode.dataset.row = row;
      cellNode.dataset.col = col;
      const entry = getCellEntry(row, col);
      const displayValue = getDisplayValue(row, col);
      if (displayValue) {
        cellNode.textContent = displayValue;
      }
      if (entry && isFormula(entry.raw)) {
        cellNode.dataset.formula = entry.raw;
        cellNode.classList.add('formula-cell');
      }
      tr.appendChild(cellNode);
    }

    tbody.appendChild(tr);
  }

  sheetElement.appendChild(tbody);
}

async function loadGrid(sheetId = state.sheetId) {
  try {
    setStatus('Loading…', 'info');
    const url = new URL('/api/grid', window.location.origin);
    if (typeof sheetId === 'number') {
      url.searchParams.set('sheetId', sheetId);
    }
    const response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) {
      throw new Error('Failed to load grid');
    }
    const data = await response.json();
    state.sheetId = data.sheetId;
    state.rowCount = data.rowCount;
    state.colCount = data.colCount;
    state.sheets = data.sheets ?? state.sheets;
    state.cells.clear();
    data.cells.forEach((rowValues, rowIndex) => {
      rowValues.forEach((value, colIndex) => {
        if (value !== null && value !== undefined && value !== '') {
          setCellRaw(rowIndex, colIndex, String(value));
        }
      });
    });
    recalculateAllCells();
    renderTable();
    populateSheetSelect();
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
    const response = await fetch('/api/grid', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error('Save failed');
    }
    const result = await response.json();
    state.sheetId = result.sheetId;
    state.rowCount = result.rowCount;
    state.colCount = result.colCount;
    const invalidKeys = [];
    state.cells.forEach((_, key) => {
      const [row, col] = key.split(':').map((part) => Number.parseInt(part, 10));
      if (row >= state.rowCount || col >= state.colCount) {
        invalidKeys.push(key);
      }
    });
    invalidKeys.forEach((key) => state.cells.delete(key));
    updates.forEach((item) => {
      const raw = typeof item.value === 'string' ? item.value : '';
      if (raw === '') {
        state.cells.delete(keyFor(item.row, item.col));
      } else {
        setCellRaw(item.row, item.col, raw);
      }
    });
    recalculateAllCells();
    renderTable();
    setStatus('All changes saved', 'success');
  } catch (error) {
    console.error(error);
    setStatus('Failed to save changes', 'error');
  }
}

sheetElement.addEventListener('input', (event) => {
  if (!event.target.matches('td.cell')) {
    return;
  }
  event.target.classList.add('modified');
});

sheetElement.addEventListener('focusin', (event) => {
  const target = event.target;
  if (!target.matches('td.cell')) {
    return;
  }
  const row = Number.parseInt(target.dataset.row, 10);
  const col = Number.parseInt(target.dataset.col, 10);
  const entry = getCellEntry(row, col);
  if (entry && isFormula(entry.raw)) {
    target.textContent = entry.raw;
  }
});

sheetElement.addEventListener('focusout', (event) => {
  const target = event.target;
  if (!target.matches('td.cell')) {
    return;
  }
  const row = Number.parseInt(target.dataset.row, 10);
  const col = Number.parseInt(target.dataset.col, 10);
  const value = target.textContent.trim();
  const previousRaw = getCellRaw(row, col);
  if (previousRaw === value) {
    target.textContent = getDisplayValue(row, col);
    if (previousRaw !== '' && isFormula(previousRaw)) {
      target.dataset.formula = previousRaw;
      target.classList.add('formula-cell');
    } else {
      target.removeAttribute('data-formula');
      target.classList.remove('formula-cell');
    }
    target.classList.remove('modified');
    return;
  }
  if (value === '') {
    state.cells.delete(keyFor(row, col));
  } else {
    setCellRaw(row, col, value);
  }
  recalculateAllCells();
  const displayValue = getDisplayValue(row, col);
  if (displayValue !== value) {
    target.textContent = displayValue;
  }
  if (value !== '' && isFormula(value)) {
    target.dataset.formula = value;
    target.classList.add('formula-cell');
  } else {
    target.removeAttribute('data-formula');
    target.classList.remove('formula-cell');
  }
  target.classList.remove('modified');
  saveChanges({
    updates: [
      {
        row,
        col,
        value,
      },
    ],
  });
});

sheetElement.addEventListener('keydown', (event) => {
  const target = event.target;
  if (!target.matches('td.cell')) {
    return;
  }
  if (event.key === 'Enter') {
    event.preventDefault();
    const row = Number.parseInt(target.dataset.row, 10);
    const col = Number.parseInt(target.dataset.col, 10);
    const nextRow = event.shiftKey ? Math.max(0, row - 1) : Math.min(state.rowCount - 1, row + 1);
    focusCell(nextRow, col);
  }
});

addRowButton.addEventListener('click', () => {
  saveChanges({ rowCount: state.rowCount + 1 });
});

addColumnButton.addEventListener('click', () => {
  saveChanges({ colCount: state.colCount + 1 });
});

resetButton.addEventListener('click', () => {
  if (!window.confirm('This will clear all values in the current sheet. Continue?')) {
    return;
  }
  const updates = [];
  state.cells.forEach((_, key) => {
    const [row, col] = key.split(':').map((part) => Number.parseInt(part, 10));
    updates.push({ row, col, value: '' });
  });
  state.cells.clear();
  saveChanges({ updates, rowCount: state.rowCount, colCount: state.colCount });
});

sheetSelect.addEventListener('change', (event) => {
  const selectedId = Number.parseInt(event.target.value, 10);
  if (Number.isNaN(selectedId) || selectedId === state.sheetId) {
    return;
  }
  loadGrid(selectedId);
});

renameButton.addEventListener('click', async () => {
  const current = state.sheets.find((sheet) => sheet.id === state.sheetId);
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
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
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
    state.sheets = result.sheets;
    populateSheetSelect();
    setStatus('Sheet renamed', 'success');
  } catch (error) {
    console.error(error);
    setStatus('Unable to rename sheet', 'error');
  }
});

function collectSheetSnapshot() {
  const snapshot = [];
  for (let row = 0; row < state.rowCount; row += 1) {
    for (let col = 0; col < state.colCount; col += 1) {
      snapshot.push({ row, col, value: getCellRaw(row, col) });
    }
  }
  return snapshot;
}

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
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
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
    state.sheets = result.sheets;
    await loadGrid(result.sheetId);
    setStatus('Sheet copy saved', 'success');
  } catch (error) {
    console.error(error);
    setStatus('Unable to save sheet copy', 'error');
  }
});

window.addEventListener('load', () => {
  populateSheetSelect();
  loadGrid();
});
