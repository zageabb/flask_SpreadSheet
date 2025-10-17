const sheetElement = document.getElementById('sheet');
const statusElement = document.getElementById('status');
const addRowButton = document.getElementById('add-row');
const addColumnButton = document.getElementById('add-column');
const resetButton = document.getElementById('reset-grid');
const renameButton = document.getElementById('rename-sheet');
const saveSheetButton = document.getElementById('save-sheet');
const sheetSelect = document.getElementById('sheet-select');
const cellTemplate = document.getElementById('cell-template');

const state = {
  sheetId: initialSheetId,
  rowCount: initialRowCount,
  colCount: initialColCount,
  cells: new Map(),
  sheets: Array.isArray(initialSheets) ? initialSheets : [],
};

const keyFor = (row, col) => `${row}:${col}`;

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
      const key = keyFor(row, col);
      const value = state.cells.get(key) ?? '';
      if (value) {
        cellNode.textContent = value;
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
    const response = await fetch(url);
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
        if (value !== null && value !== '') {
          state.cells.set(keyFor(rowIndex, colIndex), value);
        }
      });
    });
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
      headers: {
        'Content-Type': 'application/json',
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
      const key = keyFor(item.row, item.col);
      if (item.value === '') {
        state.cells.delete(key);
      } else {
        state.cells.set(key, item.value);
      }
    });
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

sheetElement.addEventListener('focusout', (event) => {
  const target = event.target;
  if (!target.matches('td.cell')) {
    return;
  }
  const row = Number.parseInt(target.dataset.row, 10);
  const col = Number.parseInt(target.dataset.col, 10);
  const value = target.textContent.trim();
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
    state.sheets = result.sheets;
    populateSheetSelect();
    setStatus('Sheet renamed', 'success');
  } catch (error) {
    console.error(error);
    setStatus('Unable to rename sheet', 'error');
  }
});

function collectSheetSnapshot() {
  const updates = [];
  const cells = sheetElement.querySelectorAll('td.cell');
  cells.forEach((cell) => {
    const row = Number.parseInt(cell.dataset.row, 10);
    const col = Number.parseInt(cell.dataset.col, 10);
    const value = cell.textContent.trim();
    updates.push({ row, col, value });
  });
  return updates;
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
