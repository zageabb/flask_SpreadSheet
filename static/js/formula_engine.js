(function (global) {
  const ValueKind = Object.freeze({
    NUMBER: 'number',
    STRING: 'string',
    BOOLEAN: 'boolean',
    ERROR: 'error',
    BLANK: 'blank',
    RANGE: 'range',
  });

  function makeNumber(value) {
    if (!Number.isFinite(value)) {
      return { kind: ValueKind.ERROR, code: '#NUM!' };
    }
    return { kind: ValueKind.NUMBER, value };
  }

  function makeString(value) {
    return { kind: ValueKind.STRING, value: String(value) };
  }

  function makeBoolean(value) {
    return { kind: ValueKind.BOOLEAN, value: Boolean(value) };
  }

  function makeBlank() {
    return { kind: ValueKind.BLANK };
  }

  function makeError(code) {
    return { kind: ValueKind.ERROR, code };
  }

  function makeRange(values) {
    return { kind: ValueKind.RANGE, values };
  }

  function isErrorValue(value) {
    return value && value.kind === ValueKind.ERROR;
  }

  function toDisplayString(value) {
    if (!value) {
      return '';
    }
    if (value.kind === ValueKind.ERROR) {
      return value.code || '#ERROR';
    }
    if (value.kind === ValueKind.BLANK) {
      return '';
    }
    if (value.kind === ValueKind.NUMBER) {
      if (!Number.isFinite(value.value)) {
        return '#NUM!';
      }
      return String(value.value);
    }
    if (value.kind === ValueKind.BOOLEAN) {
      return value.value ? 'TRUE' : 'FALSE';
    }
    if (value.kind === ValueKind.STRING) {
      return value.value;
    }
    if (value.kind === ValueKind.RANGE) {
      return '#VALUE!';
    }
    return '#ERROR';
  }

  function convertDisplayToValue(display) {
    if (typeof display !== 'string') {
      if (display === null || display === undefined) {
        return makeBlank();
      }
      return makeString(display);
    }
    const trimmed = display.trim();
    if (trimmed === '') {
      return makeBlank();
    }
    const upper = trimmed.toUpperCase();
    if (upper === '#CYCLE!') {
      return makeError('#CYCLE!');
    }
    if (upper === '#ERROR') {
      return makeError('#ERROR');
    }
    if (upper === '#DIV/0!') {
      return makeError('#DIV/0!');
    }
    if (upper === '#VALUE!') {
      return makeError('#VALUE!');
    }
    if (upper === '#NUM!') {
      return makeError('#NUM!');
    }
    if (upper === '#NAME?') {
      return makeError('#NAME?');
    }
    if (upper === 'TRUE') {
      return makeBoolean(true);
    }
    if (upper === 'FALSE') {
      return makeBoolean(false);
    }
    if (/^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(trimmed)) {
      const numeric = Number(trimmed);
      if (Number.isFinite(numeric)) {
        return makeNumber(numeric);
      }
      return makeError('#NUM!');
    }
    return makeString(display);
  }

  function convertRawToValue(raw) {
    if (raw === null || raw === undefined) {
      return makeBlank();
    }
    const stringValue = String(raw);
    const trimmed = stringValue.trim();
    if (trimmed === '') {
      return makeBlank();
    }
    const upper = trimmed.toUpperCase();
    if (upper === 'TRUE') {
      return makeBoolean(true);
    }
    if (upper === 'FALSE') {
      return makeBoolean(false);
    }
    if (/^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(trimmed)) {
      const numeric = Number(trimmed);
      if (Number.isFinite(numeric)) {
        return makeNumber(numeric);
      }
      return makeError('#NUM!');
    }
    return makeString(stringValue);
  }

  function coerceToString(value) {
    if (isErrorValue(value)) {
      return value;
    }
    if (value.kind === ValueKind.BLANK) {
      return makeString('');
    }
    if (value.kind === ValueKind.STRING) {
      return value;
    }
    if (value.kind === ValueKind.NUMBER) {
      return makeString(String(value.value));
    }
    if (value.kind === ValueKind.BOOLEAN) {
      return makeString(value.value ? 'TRUE' : 'FALSE');
    }
    if (value.kind === ValueKind.RANGE) {
      return makeError('#VALUE!');
    }
    return makeError('#VALUE!');
  }

  function coerceToBoolean(value) {
    if (isErrorValue(value)) {
      return value;
    }
    if (value.kind === ValueKind.BOOLEAN) {
      return value;
    }
    if (value.kind === ValueKind.NUMBER) {
      return makeBoolean(value.value !== 0);
    }
    if (value.kind === ValueKind.STRING) {
      const normalized = value.value.trim().toUpperCase();
      if (normalized === 'TRUE') {
        return makeBoolean(true);
      }
      if (normalized === 'FALSE' || normalized === '') {
        return makeBoolean(false);
      }
      return makeError('#VALUE!');
    }
    if (value.kind === ValueKind.BLANK) {
      return makeBoolean(false);
    }
    if (value.kind === ValueKind.RANGE) {
      return makeError('#VALUE!');
    }
    return makeError('#VALUE!');
  }

  function tryCoerceNumber(value, { blankAsZero = false } = {}) {
    if (isErrorValue(value)) {
      return { error: value };
    }
    if (value.kind === ValueKind.NUMBER) {
      return { success: true, value: value.value };
    }
    if (value.kind === ValueKind.BOOLEAN) {
      return { success: true, value: value.value ? 1 : 0 };
    }
    if (value.kind === ValueKind.STRING) {
      const trimmed = value.value.trim();
      if (trimmed === '') {
        return blankAsZero ? { success: true, value: 0 } : { success: false };
      }
      const numeric = Number(trimmed);
      if (Number.isFinite(numeric)) {
        return { success: true, value: numeric };
      }
      return { success: false };
    }
    if (value.kind === ValueKind.BLANK) {
      return blankAsZero ? { success: true, value: 0 } : { success: false };
    }
    if (value.kind === ValueKind.RANGE) {
      return { error: makeError('#VALUE!') };
    }
    return { success: false };
  }

  function numericBinaryOperation(left, right, operator) {
    const leftCoerced = tryCoerceNumber(left, { blankAsZero: true });
    if (leftCoerced.error) {
      return leftCoerced.error;
    }
    const rightCoerced = tryCoerceNumber(right, { blankAsZero: true });
    if (rightCoerced.error) {
      return rightCoerced.error;
    }
    if (!leftCoerced.success || !rightCoerced.success) {
      return makeError('#VALUE!');
    }
    const a = leftCoerced.value;
    const b = rightCoerced.value;
    switch (operator) {
      case '+':
        return makeNumber(a + b);
      case '-':
        return makeNumber(a - b);
      case '*':
        return makeNumber(a * b);
      case '/':
        if (b === 0) {
          return makeError('#DIV/0!');
        }
        return makeNumber(a / b);
      case '^':
        return makeNumber(a ** b);
      default:
        return makeError('#VALUE!');
    }
  }

  function concatValues(left, right) {
    const leftString = coerceToString(left);
    if (isErrorValue(leftString)) {
      return leftString;
    }
    const rightString = coerceToString(right);
    if (isErrorValue(rightString)) {
      return rightString;
    }
    return makeString(leftString.value + rightString.value);
  }

  function compareValues(left, right, operator) {
    if (isErrorValue(left)) {
      return left;
    }
    if (isErrorValue(right)) {
      return right;
    }
    const leftNumber = tryCoerceNumber(left, { blankAsZero: true });
    const rightNumber = tryCoerceNumber(right, { blankAsZero: true });
    if (leftNumber.error) {
      return leftNumber.error;
    }
    if (rightNumber.error) {
      return rightNumber.error;
    }
    if (leftNumber.success && rightNumber.success) {
      switch (operator) {
        case '=':
          return makeBoolean(leftNumber.value === rightNumber.value);
        case '<>':
          return makeBoolean(leftNumber.value !== rightNumber.value);
        case '>':
          return makeBoolean(leftNumber.value > rightNumber.value);
        case '>=':
          return makeBoolean(leftNumber.value >= rightNumber.value);
        case '<':
          return makeBoolean(leftNumber.value < rightNumber.value);
        case '<=':
          return makeBoolean(leftNumber.value <= rightNumber.value);
        default:
          return makeError('#VALUE!');
      }
    }

    const leftString = coerceToString(left);
    if (isErrorValue(leftString)) {
      return leftString;
    }
    const rightString = coerceToString(right);
    if (isErrorValue(rightString)) {
      return rightString;
    }
    const leftVal = leftString.value;
    const rightVal = rightString.value;
    switch (operator) {
      case '=':
        return makeBoolean(leftVal === rightVal);
      case '<>':
        return makeBoolean(leftVal !== rightVal);
      case '>':
        return makeBoolean(leftVal > rightVal);
      case '>=':
        return makeBoolean(leftVal >= rightVal);
      case '<':
        return makeBoolean(leftVal < rightVal);
      case '<=':
        return makeBoolean(leftVal <= rightVal);
      default:
        return makeError('#VALUE!');
    }
  }

  function flattenArgumentValues(args) {
    const results = [];
    for (const arg of args) {
      if (isErrorValue(arg)) {
        return arg;
      }
      if (arg.kind === ValueKind.RANGE) {
        for (const item of arg.values) {
          if (isErrorValue(item)) {
            return item;
          }
          results.push(item);
        }
      } else {
        results.push(arg);
      }
    }
    return results;
  }

  function aggregateNumeric(args, reducer, {
    initial = 0,
    blankAsZero = true,
    requireValues = false,
  } = {}) {
    const values = flattenArgumentValues(args);
    if (isErrorValue(values)) {
      return values;
    }
    let result = initial;
    let count = 0;
    let seen = false;
    for (const value of values) {
      const coerced = tryCoerceNumber(value, { blankAsZero });
      if (coerced && coerced.error) {
        return coerced.error;
      }
      if (!coerced.success) {
        continue;
      }
      seen = true;
      count += 1;
      result = reducer(result, coerced.value);
    }
    if (requireValues && !seen) {
      return makeError('#DIV/0!');
    }
    return { value: result, count };
  }

  function countValues(args, predicate) {
    const values = flattenArgumentValues(args);
    if (isErrorValue(values)) {
      return values;
    }
    let count = 0;
    for (const value of values) {
      if (predicate(value)) {
        count += 1;
      }
    }
    return makeNumber(count);
  }

  const functionHandlers = {
    SUM: (args) => {
      const aggregate = aggregateNumeric(args, (acc, val) => acc + val, {
        blankAsZero: true,
      });
      if (isErrorValue(aggregate)) {
        return aggregate;
      }
      return makeNumber(aggregate.value);
    },
    AVERAGE: (args) => {
      const aggregate = aggregateNumeric(args, (acc, val) => acc + val, {
        blankAsZero: false,
        requireValues: true,
      });
      if (isErrorValue(aggregate)) {
        return aggregate;
      }
      return makeNumber(aggregate.value / aggregate.count);
    },
    MIN: (args) => {
      const aggregate = aggregateNumeric(
        args,
        (acc, val) => (acc === null ? val : Math.min(acc, val)),
        {
          blankAsZero: false,
          requireValues: true,
          initial: null,
        },
      );
      if (isErrorValue(aggregate)) {
        return aggregate;
      }
      return makeNumber(aggregate.value);
    },
    MAX: (args) => {
      const aggregate = aggregateNumeric(
        args,
        (acc, val) => (acc === null ? val : Math.max(acc, val)),
        {
          blankAsZero: false,
          requireValues: true,
          initial: null,
        },
      );
      if (isErrorValue(aggregate)) {
        return aggregate;
      }
      return makeNumber(aggregate.value);
    },
    COUNT: (args) =>
      countValues(args, (value) => {
        const numeric = tryCoerceNumber(value, { blankAsZero: false });
        if (numeric && numeric.error) {
          return false;
        }
        return Boolean(numeric && numeric.success);
      }),
    COUNTA: (args) =>
      countValues(args, (value) => {
        if (isErrorValue(value)) {
          return true;
        }
        if (value.kind === ValueKind.BLANK) {
          return false;
        }
        if (value.kind === ValueKind.STRING) {
          return value.value.trim() !== '';
        }
        return true;
      }),
    ABS: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const coerced = tryCoerceNumber(args[0], { blankAsZero: false });
      if (coerced && coerced.error) {
        return coerced.error;
      }
      if (!coerced.success) {
        return makeError('#VALUE!');
      }
      return makeNumber(Math.abs(coerced.value));
    },
    ROUND: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      const digits = tryCoerceNumber(args[1], { blankAsZero: true });
      if (digits && digits.error) {
        return digits.error;
      }
      if (!digits.success) {
        return makeError('#VALUE!');
      }
      const factor = 10 ** digits.value;
      return makeNumber(Math.round(value.value * factor) / factor);
    },
    ROUNDDOWN: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      const digits = tryCoerceNumber(args[1], { blankAsZero: true });
      if (digits && digits.error) {
        return digits.error;
      }
      if (!digits.success) {
        return makeError('#VALUE!');
      }
      const factor = 10 ** digits.value;
      const scaled = value.value * factor;
      const rounded = scaled >= 0 ? Math.floor(scaled) : Math.ceil(scaled);
      return makeNumber(rounded / factor);
    },
    ROUNDUP: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      const digits = tryCoerceNumber(args[1], { blankAsZero: true });
      if (digits && digits.error) {
        return digits.error;
      }
      if (!digits.success) {
        return makeError('#VALUE!');
      }
      const factor = 10 ** digits.value;
      const scaled = value.value * factor;
      const rounded = scaled >= 0 ? Math.ceil(scaled) : Math.floor(scaled);
      return makeNumber(rounded / factor);
    },
    CEILING: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      let significance = 1;
      if (args.length > 1) {
        const sig = tryCoerceNumber(args[1], { blankAsZero: false });
        if (sig && sig.error) {
          return sig.error;
        }
        if (!sig.success) {
          return makeError('#VALUE!');
        }
        significance = sig.value;
      }
      if (significance === 0) {
        return makeError('#DIV/0!');
      }
      const result = Math.ceil(value.value / significance) * significance;
      return makeNumber(result);
    },
    FLOOR: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      let significance = 1;
      if (args.length > 1) {
        const sig = tryCoerceNumber(args[1], { blankAsZero: false });
        if (sig && sig.error) {
          return sig.error;
        }
        if (!sig.success) {
          return makeError('#VALUE!');
        }
        significance = sig.value;
      }
      if (significance === 0) {
        return makeError('#DIV/0!');
      }
      const result = Math.floor(value.value / significance) * significance;
      return makeNumber(result);
    },
    INT: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      return makeNumber(Math.floor(value.value));
    },
    MOD: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const dividend = tryCoerceNumber(args[0], { blankAsZero: false });
      if (dividend && dividend.error) {
        return dividend.error;
      }
      if (!dividend.success) {
        return makeError('#VALUE!');
      }
      const divisor = tryCoerceNumber(args[1], { blankAsZero: false });
      if (divisor && divisor.error) {
        return divisor.error;
      }
      if (!divisor.success) {
        return makeError('#VALUE!');
      }
      if (divisor.value === 0) {
        return makeError('#DIV/0!');
      }
      const result = ((dividend.value % divisor.value) + divisor.value) % divisor.value;
      return makeNumber(result);
    },
    POWER: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const base = tryCoerceNumber(args[0], { blankAsZero: false });
      if (base && base.error) {
        return base.error;
      }
      if (!base.success) {
        return makeError('#VALUE!');
      }
      const exponent = tryCoerceNumber(args[1], { blankAsZero: false });
      if (exponent && exponent.error) {
        return exponent.error;
      }
      if (!exponent.success) {
        return makeError('#VALUE!');
      }
      return makeNumber(base.value ** exponent.value);
    },
    SQRT: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const value = tryCoerceNumber(args[0], { blankAsZero: false });
      if (value && value.error) {
        return value.error;
      }
      if (!value.success) {
        return makeError('#VALUE!');
      }
      if (value.value < 0) {
        return makeError('#NUM!');
      }
      return makeNumber(Math.sqrt(value.value));
    },
    IF: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const condition = coerceToBoolean(args[0]);
      if (isErrorValue(condition)) {
        return condition;
      }
      if (condition.value) {
        return args[1] ?? makeBlank();
      }
      return args[2] ?? makeBlank();
    },
    AND: (args) => {
      const values = flattenArgumentValues(args);
      if (isErrorValue(values)) {
        return values;
      }
      for (const value of values) {
        const coerced = coerceToBoolean(value);
        if (isErrorValue(coerced)) {
          return coerced;
        }
        if (!coerced.value) {
          return makeBoolean(false);
        }
      }
      return makeBoolean(true);
    },
    OR: (args) => {
      const values = flattenArgumentValues(args);
      if (isErrorValue(values)) {
        return values;
      }
      for (const value of values) {
        const coerced = coerceToBoolean(value);
        if (isErrorValue(coerced)) {
          return coerced;
        }
        if (coerced.value) {
          return makeBoolean(true);
        }
      }
      return makeBoolean(false);
    },
    NOT: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const value = coerceToBoolean(args[0]);
      if (isErrorValue(value)) {
        return value;
      }
      return makeBoolean(!value.value);
    },
    CONCAT: (args) => {
      const values = flattenArgumentValues(args);
      if (isErrorValue(values)) {
        return values;
      }
      const parts = [];
      for (const value of values) {
        const coerced = coerceToString(value);
        if (isErrorValue(coerced)) {
          return coerced;
        }
        parts.push(coerced.value);
      }
      return makeString(parts.join(''));
    },
    CONCATENATE: null,
    LEFT: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      let count = 1;
      if (args.length > 1) {
        const numChars = tryCoerceNumber(args[1], { blankAsZero: true });
        if (numChars && numChars.error) {
          return numChars.error;
        }
        if (!numChars.success || numChars.value < 0) {
          return makeError('#VALUE!');
        }
        count = Math.floor(numChars.value);
      }
      return makeString(text.value.slice(0, count));
    },
    RIGHT: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      let count = 1;
      if (args.length > 1) {
        const numChars = tryCoerceNumber(args[1], { blankAsZero: true });
        if (numChars && numChars.error) {
          return numChars.error;
        }
        if (!numChars.success || numChars.value < 0) {
          return makeError('#VALUE!');
        }
        count = Math.floor(numChars.value);
      }
      return makeString(text.value.slice(Math.max(0, text.value.length - count)));
    },
    MID: (args) => {
      if (args.length < 2) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      const start = tryCoerceNumber(args[1], { blankAsZero: true });
      if (start && start.error) {
        return start.error;
      }
      if (!start.success || start.value < 1) {
        return makeError('#VALUE!');
      }
      let length = text.value.length - (start.value - 1);
      if (args.length > 2) {
        const lenArg = tryCoerceNumber(args[2], { blankAsZero: true });
        if (lenArg && lenArg.error) {
          return lenArg.error;
        }
        if (!lenArg.success || lenArg.value < 0) {
          return makeError('#VALUE!');
        }
        length = Math.floor(lenArg.value);
      }
      const startIndex = Math.max(0, Math.floor(start.value) - 1);
      return makeString(text.value.substr(startIndex, length));
    },
    LEN: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      return makeNumber(text.value.length);
    },
    LOWER: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      return makeString(text.value.toLowerCase());
    },
    UPPER: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      return makeString(text.value.toUpperCase());
    },
    TRIM: (args) => {
      if (args.length === 0) {
        return makeError('#VALUE!');
      }
      const text = coerceToString(args[0]);
      if (isErrorValue(text)) {
        return text;
      }
      return makeString(text.value.trim().replace(/\s+/g, ' '));
    },
  };

  functionHandlers.CONCATENATE = functionHandlers.CONCAT;

  function callFunction(name, args) {
    const upper = name.toUpperCase();
    const handler = functionHandlers[upper];
    if (!handler) {
      return makeError('#NAME?');
    }
    return handler(args);
  }

  const TOKEN_TYPE = Object.freeze({
    NUMBER: 'NUMBER',
    STRING: 'STRING',
    IDENTIFIER: 'IDENTIFIER',
    CELL: 'CELL',
    OP: 'OP',
    LPAREN: 'LPAREN',
    RPAREN: 'RPAREN',
    COMMA: 'COMMA',
    COLON: 'COLON',
    EOF: 'EOF',
  });

  function tokenize(input) {
    const tokens = [];
    let index = 0;
    const length = input.length;

    const isLetter = (ch) => /[A-Za-z_]/.test(ch);
    const isAlphaNumeric = (ch) => /[A-Za-z0-9_]/.test(ch);

    while (index < length) {
      const char = input[index];
      if (/\s/.test(char)) {
        index += 1;
        continue;
      }
      if (char === ',') {
        tokens.push({ type: TOKEN_TYPE.COMMA, value: ',' });
        index += 1;
        continue;
      }
      if (char === ':') {
        tokens.push({ type: TOKEN_TYPE.COLON, value: ':' });
        index += 1;
        continue;
      }
      if (char === '(') {
        tokens.push({ type: TOKEN_TYPE.LPAREN, value: '(' });
        index += 1;
        continue;
      }
      if (char === ')') {
        tokens.push({ type: TOKEN_TYPE.RPAREN, value: ')' });
        index += 1;
        continue;
      }
      if (char === '>' || char === '<' || char === '=') {
        if (input.slice(index, index + 2) === '>=') {
          tokens.push({ type: TOKEN_TYPE.OP, value: '>=' });
          index += 2;
          continue;
        }
        if (input.slice(index, index + 2) === '<=') {
          tokens.push({ type: TOKEN_TYPE.OP, value: '<=' });
          index += 2;
          continue;
        }
        if (input.slice(index, index + 2) === '<>') {
          tokens.push({ type: TOKEN_TYPE.OP, value: '<>' });
          index += 2;
          continue;
        }
        tokens.push({ type: TOKEN_TYPE.OP, value: char });
        index += 1;
        continue;
      }
      if ('+-*/^&'.includes(char)) {
        tokens.push({ type: TOKEN_TYPE.OP, value: char });
        index += 1;
        continue;
      }
      if (char === '"') {
        let end = index + 1;
        let value = '';
        while (end < length) {
          const current = input[end];
          if (current === '"') {
            if (input[end + 1] === '"') {
              value += '"';
              end += 2;
              continue;
            }
            break;
          }
          value += current;
          end += 1;
        }
        if (end >= length || input[end] !== '"') {
          throw new Error('Unterminated string literal');
        }
        tokens.push({ type: TOKEN_TYPE.STRING, value });
        index = end + 1;
        continue;
      }
      if (/[0-9.]/.test(char)) {
        const match = input.slice(index).match(/^(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?/);
        if (!match) {
          throw new Error('Invalid number');
        }
        tokens.push({ type: TOKEN_TYPE.NUMBER, value: match[0] });
        index += match[0].length;
        continue;
      }
      if (isLetter(char)) {
        let end = index + 1;
        while (end < length && isAlphaNumeric(input[end])) {
          end += 1;
        }
        const text = input.slice(index, end);
        const cellMatch = text.match(/^([A-Za-z]{1,3})(\d{1,7})$/);
        const nextChar = input[end];
        if (cellMatch && nextChar !== '(') {
          tokens.push({
            type: TOKEN_TYPE.CELL,
            value: text,
            column: cellMatch[1],
            row: cellMatch[2],
          });
        } else {
          tokens.push({ type: TOKEN_TYPE.IDENTIFIER, value: text });
        }
        index = end;
        continue;
      }
      throw new Error(`Unexpected character: ${char}`);
    }

    tokens.push({ type: TOKEN_TYPE.EOF, value: null });
    return tokens;
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

  class FormulaParser {
    constructor(input, context) {
      this.tokens = tokenize(input);
      this.index = 0;
      this.context = context;
    }

    current() {
      return this.tokens[this.index];
    }

    consume() {
      const token = this.tokens[this.index];
      this.index += 1;
      return token;
    }

    expect(type) {
      const token = this.current();
      if (token.type !== type) {
        throw new Error(`Expected token ${type} but found ${token.type}`);
      }
      this.index += 1;
      return token;
    }

    parse() {
      const value = this.parseComparison();
      const token = this.current();
      if (token.type !== TOKEN_TYPE.EOF) {
        throw new Error('Unexpected characters at end of formula');
      }
      return value;
    }

    parseComparison() {
      let left = this.parseConcatenation();
      while (true) {
        const token = this.current();
        if (token.type !== TOKEN_TYPE.OP || !['=', '<>', '>', '<', '>=', '<='].includes(token.value)) {
          break;
        }
        this.consume();
        const right = this.parseConcatenation();
        left = compareValues(left, right, token.value);
      }
      return left;
    }

    parseConcatenation() {
      let left = this.parseAddition();
      while (true) {
        const token = this.current();
        if (token.type !== TOKEN_TYPE.OP || token.value !== '&') {
          break;
        }
        this.consume();
        const right = this.parseAddition();
        left = concatValues(left, right);
      }
      return left;
    }

    parseAddition() {
      let left = this.parseMultiplication();
      while (true) {
        const token = this.current();
        if (token.type !== TOKEN_TYPE.OP || (token.value !== '+' && token.value !== '-')) {
          break;
        }
        this.consume();
        const right = this.parseMultiplication();
        left = numericBinaryOperation(left, right, token.value);
      }
      return left;
    }

    parseMultiplication() {
      let left = this.parsePower();
      while (true) {
        const token = this.current();
        if (token.type !== TOKEN_TYPE.OP || (token.value !== '*' && token.value !== '/')) {
          break;
        }
        this.consume();
        const right = this.parsePower();
        left = numericBinaryOperation(left, right, token.value);
      }
      return left;
    }

    parsePower() {
      let left = this.parseUnary();
      while (true) {
        const token = this.current();
        if (token.type !== TOKEN_TYPE.OP || token.value !== '^') {
          break;
        }
        this.consume();
        const right = this.parseUnary();
        left = numericBinaryOperation(left, right, token.value);
      }
      return left;
    }

    parseUnary() {
      const token = this.current();
      if (token.type === TOKEN_TYPE.OP && (token.value === '+' || token.value === '-')) {
        this.consume();
        const operand = this.parseUnary();
        if (token.value === '+') {
          return numericBinaryOperation(makeNumber(0), operand, '+');
        }
        return numericBinaryOperation(makeNumber(0), operand, '-');
      }
      return this.parsePrimary();
    }

    parsePrimary() {
      const token = this.current();
      if (token.type === TOKEN_TYPE.NUMBER) {
        this.consume();
        return makeNumber(Number(token.value));
      }
      if (token.type === TOKEN_TYPE.STRING) {
        this.consume();
        return makeString(token.value);
      }
      if (token.type === TOKEN_TYPE.CELL) {
        this.consume();
        const startRef = this.resolveCellReference(token);
        let value = this.context.getCellValue(startRef.row, startRef.col);
        let rangeStart = startRef;
        while (this.current().type === TOKEN_TYPE.COLON) {
          this.consume();
          const endToken = this.current();
          if (endToken.type !== TOKEN_TYPE.CELL) {
            throw new Error('Range must end with a cell reference');
          }
          this.consume();
          const endRef = this.resolveCellReference(endToken);
          value = this.context.getRange(rangeStart, endRef);
          rangeStart = endRef;
        }
        return value;
      }
      if (token.type === TOKEN_TYPE.IDENTIFIER) {
        this.consume();
        const identifier = token.value;
        if (this.current().type === TOKEN_TYPE.LPAREN) {
          this.consume();
          const args = [];
          if (this.current().type !== TOKEN_TYPE.RPAREN) {
            while (true) {
              args.push(this.parseComparison());
              if (this.current().type === TOKEN_TYPE.COMMA) {
                this.consume();
                continue;
              }
              break;
            }
          }
          this.expect(TOKEN_TYPE.RPAREN);
          return callFunction(identifier, args);
        }
        const upper = identifier.toUpperCase();
        if (upper === 'TRUE') {
          return makeBoolean(true);
        }
        if (upper === 'FALSE') {
          return makeBoolean(false);
        }
        return makeError('#NAME?');
      }
      if (token.type === TOKEN_TYPE.LPAREN) {
        this.consume();
        const value = this.parseComparison();
        this.expect(TOKEN_TYPE.RPAREN);
        return value;
      }
      throw new Error('Unexpected token in formula');
    }

    resolveCellReference(token) {
      const colIndex = columnToIndex(token.column);
      const rowIndex = Number.parseInt(token.row, 10) - 1;
      if (Number.isNaN(colIndex) || Number.isNaN(rowIndex)) {
        throw new Error('Invalid cell reference');
      }
      return { row: rowIndex, col: colIndex };
    }
  }

  function evaluateFormula(formulaBody, context) {
    const parser = new FormulaParser(formulaBody, context);
    return parser.parse();
  }

  global.FormulaEngine = Object.freeze({
    ValueKind,
    makeNumber,
    makeString,
    makeBoolean,
    makeBlank,
    makeError,
    makeRange,
    toDisplayString,
    convertDisplayToValue,
    convertRawToValue,
    evaluateFormula,
  });
})(window);
