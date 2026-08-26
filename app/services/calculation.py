"""Safe server-side formula evaluation and dependency recalculation."""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from sqlmodel import Session, select

from ..models import SheetCell

CELL_RE = re.compile(r"(?<![A-Z0-9_])([A-Z]+[1-9][0-9]*)(?![A-Z0-9_])", re.I)
RANGE_RE = re.compile(r"([A-Z]+[1-9][0-9]*):([A-Z]+[1-9][0-9]*)", re.I)


class FormulaError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def address(row: int, col: int) -> str:
    label = ""
    value = col + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return f"{label}{row + 1}"


def parse_address(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", value.upper())
    if not match:
        raise FormulaError("#REF!")
    col = 0
    for char in match.group(1):
        col = col * 26 + ord(char) - 64
    return int(match.group(2)) - 1, col - 1


class FormulaEngine:
    def evaluate(self, formula: str, resolver: Callable[[str], Any]) -> Any:
        expression = formula.strip()
        if expression.startswith("="):
            expression = expression[1:]
        expression = RANGE_RE.sub(lambda m: f'RANGE("{m.group(1).upper()}","{m.group(2).upper()}")', expression)
        expression = CELL_RE.sub(lambda m: m.group(0) if _inside_quotes(expression, m.start()) else f'CELL("{m.group(1).upper()}")', expression)
        expression = expression.replace("^", "**").replace("<>", "!=")
        try:
            tree = ast.parse(expression, mode="eval")
            return _Evaluator(resolver).visit(tree.body)
        except FormulaError:
            raise
        except ZeroDivisionError as exc:
            raise FormulaError("#DIV/0!") from exc
        except (SyntaxError, TypeError, ValueError, OverflowError) as exc:
            raise FormulaError("#VALUE!") from exc


def _inside_quotes(text: str, offset: int) -> bool:
    return text[:offset].count('"') % 2 == 1 or text[:offset].count("'") % 2 == 1


class _Evaluator(ast.NodeVisitor):
    def __init__(self, resolver: Callable[[str], Any]) -> None:
        self.resolver = resolver

    def visit_Constant(self, node): return node.value
    def visit_List(self, node): return [self.visit(item) for item in node.elts]
    def visit_Tuple(self, node): return [self.visit(item) for item in node.elts]
    def visit_Name(self, node):
        if node.id.upper() == "TRUE": return True
        if node.id.upper() == "FALSE": return False
        raise FormulaError("#NAME?")
    def visit_UnaryOp(self, node):
        value = _number(self.visit(node.operand))
        if isinstance(node.op, ast.USub): return -value
        if isinstance(node.op, ast.UAdd): return value
        raise FormulaError("#VALUE!")
    def visit_BinOp(self, node):
        left, right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add):
            if isinstance(left, str) or isinstance(right, str): return str(left) + str(right)
            return _number(left) + _number(right)
        if isinstance(node.op, ast.Sub): return _number(left) - _number(right)
        if isinstance(node.op, ast.Mult): return _number(left) * _number(right)
        if isinstance(node.op, ast.Div): return _number(left) / _number(right)
        if isinstance(node.op, ast.Pow): return _number(left) ** _number(right)
        raise FormulaError("#VALUE!")
    def visit_Compare(self, node):
        left = self.visit(node.left)
        for operation, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            ok = ({ast.Eq: lambda: left == right, ast.NotEq: lambda: left != right, ast.Lt: lambda: left < right, ast.LtE: lambda: left <= right, ast.Gt: lambda: left > right, ast.GtE: lambda: left >= right}.get(type(operation)))
            if ok is None or not ok(): return False
            left = right
        return True
    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name): raise FormulaError("#NAME?")
        name = node.func.id.upper()
        if name == "CELL": return self.resolver(str(self.visit(node.args[0])))
        if name == "RANGE": return _range_values(str(self.visit(node.args[0])), str(self.visit(node.args[1])), self.resolver)
        args = [self.visit(item) for item in node.args]
        values = list(_flatten(args))
        if name == "SUM": return sum(_number(item) for item in values)
        if name == "AVERAGE": return sum(_number(item) for item in values) / len(values) if values else 0
        if name == "MIN": return min(_number(item) for item in values)
        if name == "MAX": return max(_number(item) for item in values)
        if name == "COUNT": return sum(1 for item in values if _is_number(item))
        if name == "ABS": return abs(_number(args[0]))
        if name == "ROUND": return round(_number(args[0]), int(_number(args[1])) if len(args) > 1 else 0)
        if name == "IF": return args[1] if bool(args[0]) else (args[2] if len(args) > 2 else False)
        if name == "AND": return all(bool(item) for item in values)
        if name == "OR": return any(bool(item) for item in values)
        if name == "NOT": return not bool(args[0])
        if name in {"CONCAT", "CONCATENATE"}: return "".join(str(item) for item in values)
        if name == "SQRT": return math.sqrt(_number(args[0]))
        raise FormulaError("#NAME?")
    def generic_visit(self, node): raise FormulaError("#VALUE!")


def _flatten(items: Iterable[Any]):
    for item in items:
        if isinstance(item, (list, tuple)):
            yield from _flatten(item)
        else:
            yield item


def _is_number(value: Any) -> bool:
    try: float(value); return not isinstance(value, bool)
    except (TypeError, ValueError): return False


def _number(value: Any) -> float:
    if value in (None, ""): return 0.0
    if isinstance(value, bool): return 1.0 if value else 0.0
    try: return float(value)
    except (TypeError, ValueError) as exc: raise FormulaError("#VALUE!") from exc


def _range_values(start: str, end: str, resolver: Callable[[str], Any]) -> list[Any]:
    start_row, start_col = parse_address(start); end_row, end_col = parse_address(end)
    return [resolver(address(row, col)) for row in range(min(start_row, end_row), max(start_row, end_row) + 1) for col in range(min(start_col, end_col), max(start_col, end_col) + 1)]


@dataclass
class CalculationResult:
    calculated: int
    errors: dict[str, str]


class CalculationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.engine = FormulaEngine()

    def recalculate_sheet(self, sheet_id: int) -> CalculationResult:
        cells = self.session.exec(select(SheetCell).where(SheetCell.sheet_id == sheet_id)).all()
        by_address = {address(item.row_index, item.col_index): item for item in cells}
        state: dict[str, int] = {}; errors: dict[str, str] = {}

        def resolve(key: str):
            cell = by_address.get(key.upper())
            if cell is None: return 0
            if not cell.formula: return _coerce_scalar(cell.value)
            if state.get(key) == 1: raise FormulaError("#CYCLE!")
            if state.get(key) == 2:
                if cell.error: raise FormulaError(cell.error)
                return _coerce_scalar(cell.calculated_value)
            state[key] = 1
            try:
                value = self.engine.evaluate(cell.formula, resolve)
                cell.calculated_value = _serialize(value); cell.error = None
            except FormulaError as exc:
                cell.calculated_value = None; cell.error = exc.code; errors[key] = exc.code
            state[key] = 2; self.session.add(cell)
            if cell.error: raise FormulaError(cell.error)
            return value

        for key, cell in by_address.items():
            if cell.formula:
                try: resolve(key)
                except FormulaError: pass
        self.session.commit()
        return CalculationResult(sum(1 for cell in cells if cell.formula), errors)


def _coerce_scalar(value: str | None) -> Any:
    if value is None: return 0
    if value.casefold() == "true": return True
    if value.casefold() == "false": return False
    try: return float(value)
    except ValueError: return value


def _serialize(value: Any) -> str:
    if isinstance(value, bool): return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer(): return str(int(value))
    return str(value)
