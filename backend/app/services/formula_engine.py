"""
Professional Spreadsheet Formula Engine

Features:
- AST-based formula parsing (no eval())
- Dependency graph for incremental recalculation
- 50+ Excel-compatible functions
- Circular reference detection
- Dynamic arrays support
- Named ranges
- Error propagation
"""

from __future__ import annotations

import math
import re
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Callable, Optional
from weakref import WeakValueDictionary

import numpy as np
import pandas as pd

logger = logging.getLogger("nexus.formulas")


class FormulaError(Exception):
    """Formula evaluation error with Excel-compatible error values."""
    ERROR_VALUES = {
        "#DIV/0!": "Division by zero",
        "#N/A": "Value not available",
        "#NAME?": "Unrecognized name",
        "#NULL!": "Null intersection",
        "#NUM!": "Numeric value error",
        "#REF!": "Invalid cell reference",
        "#VALUE!": "Wrong type of argument",
        "#CALC!": "Calculation error",
        "#SPILL!": "Spill range blocked",
    }

    def __init__(self, error_type: str, message: str = ""):
        self.error_type = error_type
        self.message = message or self.ERROR_VALUES.get(error_type, "Unknown error")
        super().__init__(f"{error_type}: {self.message}")

    def to_value(self) -> str:
        return self.error_type


class NodeType(Enum):
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    REFERENCE = "reference"
    RANGE = "range"
    FUNCTION = "function"
    OPERATOR = "operator"
    PARENTHESIS = "parenthesis"


@dataclass
class ASTNode:
    type: NodeType
    value: Any = None
    children: list['ASTNode'] = field(default_factory=list)
    token_start: int = 0
    token_end: int = 0

    def evaluate(self, context: 'FormulaContext') -> Any:
        """Evaluate this node in the given context."""
        if self.type == NodeType.NUMBER:
            return self.value
        elif self.type == NodeType.STRING:
            return self.value
        elif self.type == NodeType.BOOLEAN:
            return self.value
        elif self.type == NodeType.REFERENCE:
            return context.get_cell(self.value)
        elif self.type == NodeType.RANGE:
            return context.get_range(self.value)
        elif self.type == NodeType.FUNCTION:
            return self._evaluate_function(context)
        elif self.type == NodeType.OPERATOR:
            return self._evaluate_operator(context)
        elif self.type == NodeType.PARENTHESIS:
            if len(self.children) == 1:
                return self.children[0].evaluate(context)
            raise FormulaError("#VALUE!", "Invalid parenthesis")
        raise FormulaError("#VALUE!", f"Unknown node type: {self.type}")

    def _evaluate_function(self, context: 'FormulaContext') -> Any:
        func_name = self.value.upper()
        if func_name not in FormulaRegistry.FUNCTIONS:
            raise FormulaError("#NAME?" , f"Unknown function: {func_name}")
        
        func = FormulaRegistry.FUNCTIONS[func_name]
        args = [child.evaluate(context) for child in self.children]
        
        # Handle array arguments for dynamic arrays
        expanded_args = []
        max_len = 1
        for arg in args:
            if isinstance(arg, list) and not isinstance(arg, str):
                max_len = max(max_len, len(arg))
        
        # Broadcast scalar args to match array length
        for arg in args:
            if isinstance(arg, list) and len(arg) != max_len:
                # If sizes don't match and not broadcasting, error
                pass
            expanded_args.append(arg)
        
        try:
            return func.handler(*expanded_args, context=context)
        except FormulaError:
            raise
        except ZeroDivisionError:
            raise FormulaError("#DIV/0!")
        except (ValueError, TypeError) as e:
            raise FormulaError("#VALUE!", str(e))
        except Exception as e:
            logger.exception("Function %s failed", func_name)
            raise FormulaError("#CALC!", str(e))

    def _evaluate_operator(self, context: 'FormulaContext') -> Any:
        op = self.value
        if len(self.children) == 1:
            # Unary operator
            operand = self.children[0].evaluate(context)
            if op == '-':
                return -self._to_number(operand)
            elif op == '+':
                return self._to_number(operand)
            elif op == '%':
                return self._to_number(operand) / 100
        elif len(self.children) == 2:
            left = self.children[0].evaluate(context)
            right = self.children[1].evaluate(context)
            
            # Handle array operations
            if isinstance(left, list) and isinstance(right, list):
                return self._array_operation(left, right, op)
            elif isinstance(left, list):
                return [self._binary_op(l, right, op) for l in left]
            elif isinstance(right, list):
                return [self._binary_op(left, r, op) for r in right]
            
            return self._binary_op(left, right, op)
        
        raise FormulaError("#VALUE!", f"Invalid operator: {op}")

    def _to_number(self, value: Any) -> float:
        if isinstance(value, FormulaError):
            raise value
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                raise FormulaError("#VALUE!")
        raise FormulaError("#VALUE!")

    def _binary_op(self, left: Any, right: Any, op: str) -> Any:
        """Perform binary operation with Excel semantics."""
        # Handle errors
        if isinstance(left, FormulaError):
            return left
        if isinstance(right, FormulaError):
            return right
        
        # String concatenation
        if op == '&':
            return str(self._to_text(left)) + str(self._to_text(right))
        
        # Comparison operators (return boolean)
        if op in ('=', '<>', '<', '>', '<=', '>='):
            l = self._to_number(left) if self._is_numeric(left) else self._to_text(left)
            r = self._to_number(right) if self._is_numeric(right) else self._to_text(right)
            
            if op == '=':
                return l == r
            elif op == '<>':
                return l != r
            elif op == '<':
                return l < r
            elif op == '>':
                return l > r
            elif op == '<=':
                return l <= r
            elif op == '>=':
                return l >= r
        
        # Arithmetic operators
        l = self._to_number(left)
        r = self._to_number(right)
        
        if op == '+':
            return l + r
        elif op == '-':
            return l - r
        elif op == '*':
            return l * r
        elif op == '/':
            if r == 0:
                raise FormulaError("#DIV/0!")
            return l / r
        elif op == '^':
            return l ** r
        
        raise FormulaError("#VALUE!", f"Unknown operator: {op}")

    def _is_numeric(self, value: Any) -> bool:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if isinstance(value, str):
            try:
                float(value)
                return True
            except ValueError:
                return False
        return False

    def _to_text(self, value: Any) -> str:
        if isinstance(value, FormulaError):
            return value.to_value()
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if value is None:
            return ""
        return str(value)

    def _array_operation(self, left: list, right: list, op: str) -> list:
        """Element-wise array operation."""
        max_len = max(len(left), len(right))
        result = []
        for i in range(max_len):
            l = left[i % len(left)]
            r = right[i % len(right)]
            result.append(self._binary_op(l, r, op))
        return result


@dataclass
class FormulaContext:
    """Evaluation context for formulas."""
    workbook: 'Workbook'
    sheet_name: str
    current_cell: tuple[int, int]  # (row, col) 0-indexed
    evaluating: set[str] = field(default_factory=set)  # For circular detection

    def get_cell(self, ref: str) -> Any:
        """Get cell value by A1 reference."""
        sheet, cell_ref = self._parse_ref(ref)
        row, col = self._a1_to_coords(cell_ref)
        return self.workbook.get_cell(sheet, row, col)

    def get_range(self, ref: str) -> list[list[Any]]:
        """Get range as 2D array."""
        sheet, range_ref = self._parse_ref(ref)
        start_ref, end_ref = range_ref.split(':')
        start_row, start_col = self._a1_to_coords(start_ref)
        end_row, end_col = self._a1_to_coords(end_ref)
        
        result = []
        for r in range(start_row, end_row + 1):
            row_data = []
            for c in range(start_col, end_col + 1):
                row_data.append(self.workbook.get_cell(sheet, r, c))
            result.append(row_data)
        return result

    def _parse_ref(self, ref: str) -> tuple[str, str]:
        """Parse sheet!A1 reference."""
        if '!' in ref:
            sheet_part, cell_part = ref.split('!', 1)
            sheet = sheet_part.strip("'")
        else:
            sheet = self.sheet_name
            cell_part = ref
        return sheet, cell_part

    def _a1_to_coords(self, a1: str) -> tuple[int, int]:
        """Convert A1 reference to 0-indexed (row, col)."""
        match = re.match(r'^([A-Z]+)(\d+)$', a1.upper())
        if not match:
            raise FormulaError("#REF!", f"Invalid reference: {a1}")
        col_str, row_str = match.groups()
        col = 0
        for ch in col_str:
            col = col * 26 + (ord(ch) - ord('A') + 1)
        col -= 1
        row = int(row_str) - 1
        if row < 0 or col < 0:
            raise FormulaError("#REF!", f"Invalid reference: {a1}")
        return row, col


class FunctionHandler:
    """Wrapper for formula functions."""
    def __init__(self, handler: Callable, min_args: int = 0, max_args: int = -1,
                 variadic: bool = False, categories: list[str] = None):
        self.handler = handler
        self.min_args = min_args
        self.max_args = max_args if max_args > 0 else float('inf')
        self.variadic = variadic
        self.categories = categories or []

    def validate_args(self, args: list[Any]) -> None:
        if len(args) < self.min_args:
            raise FormulaError("#VALUE!", f"Too few arguments (need {self.min_args}, got {len(args)})")
        if len(args) > self.max_args and not self.variadic:
            raise FormulaError("#VALUE!", f"Too many arguments (max {self.max_args}, got {len(args)})")


class FormulaRegistry:
    """Registry of all formula functions."""
    FUNCTIONS: dict[str, FunctionHandler] = {}

    @classmethod
    def register(cls, name: str, min_args: int = 0, max_args: int = -1,
                 variadic: bool = False, categories: list[str] = None):
        def decorator(func):
            cls.FUNCTIONS[name.upper()] = FunctionHandler(
                func, min_args, max_args, variadic, categories
            )
            return func
        return decorator


# =======================
# MATH & TRIGONOMETRY FUNCTIONS
# =======================

@FormulaRegistry.register("SUM", min_args=1, variadic=True, categories=["Math"])
def func_sum(*args, context=None) -> float:
    """Add all numbers in a range of cells."""
    total = 0.0
    for arg in args:
        if isinstance(arg, list):
            for item in arg:
                if isinstance(item, FormulaError):
                    continue
                total += FormulaContext._to_number_static(item)
        else:
            total += FormulaContext._to_number_static(arg)
    return total

FormulaContext._to_number_static = staticmethod(lambda v: FormulaEngine._to_number_static(v))

# Add static helper methods to FormulaContext
FormulaContext._to_number_static = staticmethod(lambda v: (
    float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else
    float(v) if isinstance(v, str) and v.replace('.', '', 1).replace('-', '', 1).isdigit() else
    1.0 if v is True else
    0.0 if v is False else
    0.0
))

@FormulaRegistry.register("AVERAGE", min_args=1, variadic=True, categories=["Statistical"])
def func_average(*args, context=None) -> float:
    """Calculate the average of numbers."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if not values:
        raise FormulaError("#DIV/0!")
    return sum(values) / len(values)

@FormulaRegistry.register("COUNT", min_args=1, variadic=True, categories=["Statistical"])
def func_count(*args, context=None) -> int:
    """Count numeric values."""
    count = 0
    for arg in args:
        if isinstance(arg, list):
            for item in arg:
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    count += 1
                elif isinstance(item, str):
                    try:
                        float(item)
                        count += 1
                    except ValueError:
                        pass
        else:
            if isinstance(arg, (int, float)) and not isinstance(arg, bool):
                count += 1
            elif isinstance(arg, str):
                try:
                    float(arg)
                    count += 1
                except ValueError:
                    pass
    return count

@FormulaRegistry.register("COUNTA", min_args=1, variadic=True, categories=["Statistical"])
def func_counta(*args, context=None) -> int:
    """Count non-empty values."""
    count = 0
    for arg in args:
        if isinstance(arg, list):
            for item in arg:
                if item is not None and item != "" and not isinstance(item, FormulaError):
                    count += 1
        else:
            if arg is not None and arg != "" and not isinstance(arg, FormulaError):
                count += 1
    return count

@FormulaRegistry.register("COUNTIF", min_args=2, max_args=2, categories=["Statistical"])
def func_countif(range_val, criteria, context=None) -> int:
    """Count cells that meet a criterion."""
    values = range_val if isinstance(range_val, list) else [range_val]
    count = 0
    for val in values:
        if FormulaEngine._match_criteria(val, criteria):
            count += 1
    return count

@FormulaRegistry.register("SUMIF", min_args=2, max_args=3, categories=["Math"])
def func_sumif(range_val, criteria, sum_range=None, context=None) -> float:
    """Sum cells that meet a criterion."""
    values = range_val if isinstance(range_val, list) else [range_val]
    sum_vals = sum_range if isinstance(sum_range, list) else ([sum_range] if sum_range is not None else values)
    
    total = 0.0
    for i, val in enumerate(values):
        if FormulaEngine._match_criteria(val, criteria):
            total += FormulaContext._to_number_static(sum_vals[i] if i < len(sum_vals) else 0)
    return total

@FormulaRegistry.register("AVERAGEIF", min_args=2, max_args=3, categories=["Statistical"])
def func_averageif(range_val, criteria, avg_range=None, context=None) -> float:
    """Average cells that meet a criterion."""
    values = range_val if isinstance(range_val, list) else [range_val]
    avg_vals = avg_range if isinstance(avg_range, list) else ([avg_range] if avg_range is not None else values)
    
    matched = []
    for i, val in enumerate(values):
        if FormulaEngine._match_criteria(val, criteria):
            matched.append(FormulaContext._to_number_static(avg_vals[i] if i < len(avg_range) else 0))
    
    if not matched:
        raise FormulaError("#DIV/0!")
    return sum(matched) / len(matched)

@FormulaRegistry.register("MAX", min_args=1, variadic=True, categories=["Statistical"])
def func_max(*args, context=None) -> float:
    """Return the maximum value."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if not values:
        return 0.0
    return max(values)

@FormulaRegistry.register("MIN", min_args=1, variadic=True, categories=["Statistical"])
def func_min(*args, context=None) -> float:
    """Return the minimum value."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if not values:
        return 0.0
    return min(values)

@FormulaRegistry.register("ROUND", min_args=2, max_args=2, categories=["Math"])
def func_round(number, digits, context=None) -> float:
    """Round a number to specified digits."""
    num = FormulaContext._to_number_static(number)
    dig = int(FormulaContext._to_number_static(digits))
    return round(num, dig)

@FormulaRegistry.register("ROUNDUP", min_args=2, max_args=2, categories=["Math"])
def func_roundup(number, digits, context=None) -> float:
    """Round up away from zero."""
    num = FormulaContext._to_number_static(number)
    dig = int(FormulaContext._to_number_static(digits))
    mult = 10 ** dig
    if num >= 0:
        return math.ceil(num * mult) / mult
    else:
        return math.floor(num * mult) / mult

@FormulaRegistry.register("ROUNDDOWN", min_args=2, max_args=2, categories=["Math"])
def func_rounddown(number, digits, context=None) -> float:
    """Round down toward zero."""
    num = FormulaContext._to_number_static(number)
    dig = int(FormulaContext._to_number_static(digits))
    mult = 10 ** dig
    if num >= 0:
        return math.floor(num * mult) / mult
    else:
        return math.ceil(num * mult) / mult

@FormulaRegistry.register("ABS", min_args=1, max_args=1, categories=["Math"])
def func_abs(number, context=None) -> float:
    """Return absolute value."""
    return abs(FormulaContext._to_number_static(number))

@FormulaRegistry.register("SQRT", min_args=1, max_args=1, categories=["Math"])
def func_sqrt(number, context=None) -> float:
    """Return square root."""
    num = FormulaContext._to_number_static(number)
    if num < 0:
        raise FormulaError("#NUM!")
    return math.sqrt(num)

@FormulaRegistry.register("POWER", min_args=2, max_args=2, categories=["Math"])
def func_power(number, power, context=None) -> float:
    """Raise number to power."""
    return FormulaContext._to_number_static(number) ** FormulaContext._to_number_static(power)

@FormulaRegistry.register("LOG", min_args=1, max_args=2, categories=["Math"])
def func_log(number, base=None, context=None) -> float:
    """Return logarithm."""
    num = FormulaContext._to_number_static(number)
    if num <= 0:
        raise FormulaError("#NUM!")
    if base is not None:
        b = FormulaContext._to_number_static(base)
        if b <= 0 or b == 1:
            raise FormulaError("#NUM!")
        return math.log(num, b)
    return math.log(num)

@FormulaRegistry.register("LN", min_args=1, max_args=1, categories=["Math"])
def func_ln(number, context=None) -> float:
    """Return natural logarithm."""
    num = FormulaContext._to_number_static(number)
    if num <= 0:
        raise FormulaError("#NUM!")
    return math.log(num)

@FormulaRegistry.register("LOG10", min_args=1, max_args=1, categories=["Math"])
def func_log10(number, context=None) -> float:
    """Return base-10 logarithm."""
    num = FormulaContext._to_number_static(number)
    if num <= 0:
        raise FormulaError("#NUM!")
    return math.log10(num)

@FormulaRegistry.register("EXP", min_args=1, max_args=1, categories=["Math"])
def func_exp(number, context=None) -> float:
    """Return e raised to power."""
    return math.exp(FormulaContext._to_number_static(number))

@FormulaRegistry.register("PI", min_args=0, max_args=0, categories=["Math"])
def func_pi(context=None) -> float:
    """Return pi."""
    return math.pi

# =======================
# STATISTICAL FUNCTIONS
# =======================

@FormulaRegistry.register("STDEV", min_args=1, variadic=True, categories=["Statistical"])
def func_stdev(*args, context=None) -> float:
    """Sample standard deviation."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if len(values) < 2:
        raise FormulaError("#DIV/0!")
    return float(np.std(values, ddof=1))

@FormulaRegistry.register("STDEV.P", min_args=1, variadic=True, categories=["Statistical"])
def func_stdev_p(*args, context=None) -> float:
    """Population standard deviation."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if not values:
        raise FormulaError("#DIV/0!")
    return float(np.std(values, ddof=0))

@FormulaRegistry.register("VAR", min_args=1, variadic=True, categories=["Statistical"])
def func_var(*args, context=None) -> float:
    """Sample variance."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if len(values) < 2:
        raise FormulaError("#DIV/0!")
    return float(np.var(values, ddof=1))

@FormulaRegistry.register("VAR.P", min_args=1, variadic=True, categories=["Statistical"])
def func_var_p(*args, context=None) -> float:
    """Population variance."""
    values = []
    for arg in args:
        if isinstance(arg, list):
            values.extend([FormulaContext._to_number_static(x) for x in arg])
        else:
            values.append(FormulaContext._to_number_static(arg))
    values = [v for v in values if v is not None and not math.isnan(v)]
    if not values:
        raise FormulaError("#DIV/0!")
    return float(np.var(values, ddof=0))

@FormulaRegistry.register("PERCENTILE", min_args=2, max_args=2, categories=["Statistical"])
def func_percentile(range_val, k, context=None) -> float:
    """K-th percentile (exclusive)."""
    values = range_val if isinstance(range_val, list) else [range_val]
    nums = [FormulaContext._to_number_static(x) for x in values if x is not None and not math.isnan(FormulaContext._to_number_static(x))]
    if not nums:
        raise FormulaError("#NUM!")
    k_val = FormulaContext._to_number_static(k)
    if k_val < 0 or k_val > 1:
        raise FormulaError("#NUM!")
    return float(np.percentile(nums, k_val * 100))

@FormulaRegistry.register("QUARTILE", min_args=2, max_args=2, categories=["Statistical"])
def func_quartile(range_val, quart, context=None) -> float:
    """Return quartile."""
    values = range_val if isinstance(range_val, list) else [range_val]
    nums = [FormulaContext._to_number_static(x) for x in values if x is not None and not math.isnan(FormulaContext._to_number_static(x))]
    if not nums:
        raise FormulaError("#NUM!")
    q = int(FormulaContext._to_number_static(quart))
    if q < 0 or q > 4:
        raise FormulaError("#NUM!")
    percentiles = [0, 25, 50, 75, 100]
    return float(np.percentile(nums, percentiles[q]))

@FormulaRegistry.register("CORREL", min_args=2, max_args=2, categories=["Statistical"])
def func_correl(range1, range2, context=None) -> float:
    """Return correlation coefficient."""
    arr1 = range1 if isinstance(range1, list) else [range1]
    arr2 = range2 if isinstance(range2, list) else [range2]
    
    nums1 = [FormulaContext._to_number_static(x) for x in arr1]
    nums2 = [FormulaContext._to_number_static(x) for x in arr2]
    
    # Filter pairs where both are valid numbers
    pairs = [(a, b) for a, b in zip(nums1, nums2) 
             if a is not None and b is not None and not math.isnan(a) and not math.isnan(b)]
    
    if len(pairs) < 2:
        raise FormulaError("#NUM!")
    
    a_arr, b_arr = zip(*pairs)
    corr_matrix = np.corrcoef(a_arr, b_arr)
    return float(corr_matrix[0, 1])

@FormulaRegistry.register("SLOPE", min_args=2, max_args=2, categories=["Statistical"])
def func_slope(known_ys, known_xs, context=None) -> float:
    """Return slope of linear regression."""
    arr_y = known_ys if isinstance(known_ys, list) else [known_ys]
    arr_x = known_xs if isinstance(known_xs, list) else [known_xs]
    
    nums_y = [FormulaContext._to_number_static(x) for x in arr_y]
    nums_x = [FormulaContext._to_number_static(x) for x in arr_x]
    
    pairs = [(x, y) for x, y in zip(nums_x, nums_y) 
             if x is not None and y is not None and not math.isnan(x) and not math.isnan(y)]
    
    if len(pairs) < 2:
        raise FormulaError("#NUM!")
    
    x_arr, y_arr = zip(*pairs)
    slope, _ = np.polyfit(x_arr, y_arr, 1)
    return float(slope)

@FormulaRegistry.register("INTERCEPT", min_args=2, max_args=2, categories=["Statistical"])
def func_intercept(known_ys, known_xs, context=None) -> float:
    """Return y-intercept of linear regression."""
    arr_y = known_ys if isinstance(known_ys, list) else [known_ys]
    arr_x = known_xs if isinstance(known_xs, list) else [known_xs]
    
    nums_y = [FormulaContext._to_number_static(x) for x in arr_y]
    nums_x = [FormulaContext._to_number_static(x) for x in arr_x]
    
    pairs = [(x, y) for x, y in zip(nums_x, nums_y) 
             if x is not None and y is not None and not math.isnan(x) and not math.isnan(y)]
    
    if len(pairs) < 2:
        raise FormulaError("#NUM!")
    
    x_arr, y_arr = zip(*pairs)
    _, intercept = np.polyfit(x_arr, y_arr, 1)
    return float(intercept)

# =======================
# LOGICAL FUNCTIONS
# =======================

@FormulaRegistry.register("IF", min_args=3, max_args=3, categories=["Logical"])
def func_if(logical_test, value_if_true, value_if_false, context=None):
    """Return one value if true, another if false."""
    result = FormulaContext._to_logical(logical_test)
    return value_if_true if result else value_if_false

@FormulaRegistry.register("IFERROR", min_args=2, max_args=2, categories=["Logical"])
def func_iferror(value, value_if_error, context=None):
    """Return value_if_error if value is error."""
    if isinstance(value, FormulaError):
        return value_if_error
    return value

@FormulaRegistry.register("IFNA", min_args=2, max_args=2, categories=["Logical"])
def func_ifna(value, value_if_na, context=None):
    """Return value_if_na if value is #N/A."""
    if isinstance(value, FormulaError) and value.error_type == "#N/A":
        return value_if_na
    return value

@FormulaRegistry.register("AND", min_args=1, variadic=True, categories=["Logical"])
def func_and(*args, context=None) -> bool:
    """Return TRUE if all arguments are TRUE."""
    for arg in args:
        if isinstance(arg, list):
            for item in arg:
                if not FormulaContext._to_logical(item):
                    return False
        else:
            if not FormulaContext._to_logical(arg):
                return False
    return True

@FormulaRegistry.register("OR", min_args=1, variadic=True, categories=["Logical"])
def func_or(*args, context=None) -> bool:
    """Return TRUE if any argument is TRUE."""
    for arg in args:
        if isinstance(arg, list):
            for item in arg:
                if FormulaContext._to_logical(item):
                    return True
        else:
            if FormulaContext._to_logical(arg):
                return True
    return False

@FormulaRegistry.register("NOT", min_args=1, max_args=1, categories=["Logical"])
def func_not(logical, context=None) -> bool:
    """Reverse the logic of its argument."""
    return not FormulaContext._to_logical(logical)

FormulaContext._to_logical = staticmethod(lambda v: (
    True if v is True else
    False if v is False else
    True if isinstance(v, (int, float)) and v != 0 else
    True if isinstance(v, str) and v.upper() == "TRUE" else
    False
))

@FormulaRegistry.register("TRUE", min_args=0, max_args=0, categories=["Logical"])
def func_true(context=None) -> bool:
    return True

@FormulaRegistry.register("FALSE", min_args=0, max_args=0, categories=["Logical"])
def func_false(context=None) -> bool:
    return False

# =======================
# LOOKUP & REFERENCE FUNCTIONS
# =======================

@FormulaRegistry.register("VLOOKUP", min_args=3, max_args=4, categories=["Lookup"])
def func_vlookup(lookup_value, table_array, col_index_num, range_lookup=True, context=None):
    """Vertical lookup."""
    table = table_array if isinstance(table_array, list) else [table_array]
    
    # Find matching row
    for i, row in enumerate(table):
        if isinstance(row, list) and len(row) > 0:
            if FormulaEngine._values_equal(row[0], lookup_value):
                col_idx = int(FormulaContext._to_number_static(col_index_num)) - 1
                if col_idx < 0 or col_idx >= len(row):
                    raise FormulaError("#REF!")
                return row[col_idx]
    
    # Approximate match if range_lookup is True
    if FormulaContext._to_logical(range_lookup):
        # Sort by first column and find closest match <= lookup_value
        pass
    
    raise FormulaError("#N/A")

@FormulaRegistry.register("HLOOKUP", min_args=3, max_args=4, categories=["Lookup"])
def func_hlookup(lookup_value, table_array, row_index_num, range_lookup=True, context=None):
    """Horizontal lookup."""
    table = table_array if isinstance(table_array, list) else [table_array]
    
    row_idx = int(FormulaContext._to_number_static(row_index_num)) - 1
    if row_idx < 0 or row_idx >= len(table[0] if table else 0):
        raise FormulaError("#REF!")
    
    # Search first row
    for col_idx, val in enumerate(table[0] if table else []):
        if FormulaEngine._values_equal(val, lookup_value):
            if row_idx < len(table):
                return table[row_idx][col_idx]
    
    raise FormulaError("#N/A")

@FormulaRegistry.register("INDEX", min_args=2, max_args=3, categories=["Lookup"])
def func_index(array, row_num, col_num=None, context=None):
    """Return value at row/col intersection."""
    arr = array if isinstance(array, list) else [[array]]
    
    r = int(FormulaContext._to_number_static(row_num)) - 1
    if col_num is not None:
        c = int(FormulaContext._to_number_static(col_num)) - 1
    else:
        c = 0
    
    if r < 0 or r >= len(arr) or c < 0 or c >= len(arr[0]):
        raise FormulaError("#REF!")
    
    return arr[r][c]

@FormulaRegistry.register("MATCH", min_args=2, max_args=3, categories=["Lookup"])
def func_match(lookup_value, lookup_array, match_type=1, context=None) -> int:
    """Return relative position of item."""
    arr = lookup_array if isinstance(lookup_array, list) else [lookup_array]
    
    match_type = int(FormulaContext._to_number_static(match_type))
    
    if match_type == 0:
        # Exact match
        for i, val in enumerate(arr):
            if FormulaEngine._values_equal(val, lookup_value):
                return i + 1
    elif match_type == 1:
        # Less than or equal (ascending order)
        pass
    elif match_type == -1:
        # Greater than or equal (descending order)
        pass
    
    raise FormulaError("#N/A")

# =======================
# TEXT FUNCTIONS
# =======================

@FormulaRegistry.register("TEXT", min_args=2, max_args=2, categories=["Text"])
def func_text(value, format_text, context=None) -> str:
    """Format number as text."""
    # Simplified - would need full Excel format code support
    num = FormulaContext._to_number_static(value)
    return f"{num:{format_text}}" if '{' in format_text else str(num)

@FormulaRegistry.register("CONCAT", min_args=1, variadic=True, categories=["Text"])
def func_concat(*args, context=None) -> str:
    """Concatenate text strings."""
    result = []
    for arg in args:
        if isinstance(arg, list):
            for item in arg:
                if not isinstance(item, FormulaError):
                    result.append(str(item))
        else:
            if not isinstance(arg, FormulaError):
                result.append(str(arg))
    return "".join(result)

@FormulaRegistry.register("LEFT", min_args=1, max_args=2, categories=["Text"])
def func_left(text, num_chars=None, context=None) -> str:
    """Return leftmost characters."""
    t = str(text)
    n = int(FormulaContext._to_number_static(num_chars)) if num_chars is not None else 1
    return t[:n]

@FormulaRegistry.register("RIGHT", min_args=1, max_args=2, categories=["Text"])
def func_right(text, num_chars=None, context=None) -> str:
    """Return rightmost characters."""
    t = str(text)
    n = int(FormulaContext._to_number_static(num_chars)) if num_chars is not None else 1
    return t[-n:]

@FormulaRegistry.register("MID", min_args=3, max_args=3, categories=["Text"])
def func_mid(text, start_num, num_chars, context=None) -> str:
    """Return middle characters."""
    t = str(text)
    start = int(FormulaContext._to_number_static(start_num)) - 1
    n = int(FormulaContext._to_number_static(num_chars))
    if start < 0 or start >= len(t):
        return ""
    return t[start:start+n]

@FormulaRegistry.register("LEN", min_args=1, max_args=1, categories=["Text"])
def func_len(text, context=None) -> int:
    """Return length of text."""
    return len(str(text))

@FormulaRegistry.register("TRIM", min_args=1, max_args=1, categories=["Text"])
def func_trim(text, context=None) -> str:
    """Remove extra spaces."""
    return " ".join(str(text).split())

@FormulaRegistry.register("UPPER", min_args=1, max_args=1, categories=["Text"])
def func_upper(text, context=None) -> str:
    return str(text).upper()

@FormulaRegistry.register("LOWER", min_args=1, max_args=1, categories=["Text"])
def func_lower(text, context=None) -> str:
    return str(text).lower()

@FormulaRegistry.register("PROPER", min_args=1, max_args=1, categories=["Text"])
def func_proper(text, context=None) -> str:
    return str(text).title()

# =======================
# DATE & TIME FUNCTIONS
# =======================

@FormulaRegistry.register("TODAY", min_args=0, max_args=0, categories=["Date"])
def func_today(context=None) -> datetime:
    return datetime.now().date()

@FormulaRegistry.register("NOW", min_args=0, max_args=0, categories=["Date"])
def func_now(context=None) -> datetime:
    return datetime.now()

@FormulaRegistry.register("DATE", min_args=3, max_args=3, categories=["Date"])
def func_date(year, month, day, context=None) -> date:
    """Create date from year, month, day."""
    y = int(FormulaContext._to_number_static(year))
    m = int(FormulaContext._to_number_static(month))
    d = int(FormulaContext._to_number_static(day))
    try:
        return date(y, m, d)
    except ValueError:
        raise FormulaError("#VALUE!")

@FormulaRegistry.register("YEAR", min_args=1, max_args=1, categories=["Date"])
def func_year(serial_number, context=None) -> int:
    """Extract year from date."""
    dt = FormulaEngine._to_datetime(serial_number)
    return dt.year

@FormulaRegistry.register("MONTH", min_args=1, max_args=1, categories=["Date"])
def func_month(serial_number, context=None) -> int:
    """Extract month from date."""
    dt = FormulaEngine._to_datetime(serial_number)
    return dt.month

@FormulaRegistry.register("DAY", min_args=1, max_args=1, categories=["Date"])
def func_day(serial_number, context=None) -> int:
    """Extract day from date."""
    dt = FormulaEngine._to_datetime(serial_number)
    return dt.day

@FormulaRegistry.register("EOMONTH", min_args=2, max_args=2, categories=["Date"])
def func_eomonth(start_date, months, context=None) -> date:
    """Last day of month N months from start."""
    dt = FormulaEngine._to_datetime(start_date)
    months_int = int(FormulaContext._to_number_static(months))
    
    # Add months
    month = dt.month + months_int
    year = dt.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    
    # Get last day of target month
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    
    return next_month - timedelta(days=1)

@FormulaRegistry.register("WEEKDAY", min_args=1, max_args=2, categories=["Date"])
def func_weekday(serial_number, return_type=1, context=None) -> int:
    """Return day of week (1=Sunday...7=Saturday by default)."""
    dt = FormulaEngine._to_datetime(serial_number)
    return_type = int(FormulaContext._to_number_static(return_type))
    
    # Python: Monday=0...Sunday=6
    py_weekday = dt.weekday()
    
    # Excel systems:
    # 1: 1=Sun...7=Sat
    # 2: 1=Mon...7=Sun
    # 3: 0=Mon...6=Sun
    # 11-17: similar patterns
    
    if return_type == 1:
        return (py_weekday + 1) % 7 + 1
    elif return_type == 2:
        return py_weekday + 1
    elif return_type == 3:
        return py_weekday
    else:
        return (py_weekday + 1) % 7 + 1

FormulaEngine._to_datetime = staticmethod(lambda v: (
    v if isinstance(v, datetime) else
    v if isinstance(v, date) else
    datetime.fromordinal(int(v) + 693594) if isinstance(v, (int, float)) and v > 0 else
    datetime.strptime(str(v), "%Y-%m-%d") if isinstance(v, str) and '-' in v else
    datetime.now()
))

FormulaEngine._values_equal = staticmethod(lambda a, b: (
    str(a).strip().upper() == str(b).strip().upper()
))

FormulaEngine._match_criteria = staticmethod(lambda value, criteria: (
    FormulaEngine._values_equal(value, criteria) if isinstance(criteria, (str, int, float)) else
    True  # Simplified - would need full criteria parsing
))

FormulaEngine._to_number_static = FormulaContext._to_number_static


class FormulaParser:
    """Parse formula strings into AST."""
    
    OPERATORS = {
        '^': (5, 'right'),
        '*': (4, 'left'), '/': (4, 'left'),
        '+': (3, 'left'), '-': (3, 'left'),
        '&': (2, 'left'),
        '=': (1, 'left'), '<>': (1, 'left'), '<': (1, 'left),
        '>': (1, 'left), '<=': (1, 'left), '>=': (1, 'left),
    }

    def __init__(self):
        self.tokens = []
        self.pos = 0
        self.formula = ""

    def parse(self, formula: str) -> ASTNode:
        """Parse formula string into AST."""
        self.formula = formula.strip()
        if self.formula.startswith('='):
            self.formula = self.formula[1:]
        self.tokens = self._tokenize(self.formula)
        self.pos = 0
        node = self._parse_expression(0)
        if self.pos < len(self.tokens):
            raise FormulaError("#VALUE!", "Unexpected tokens after expression")
        return node

    def _tokenize(self, formula: str) -> list[dict[str, Any]]:
        """Tokenize formula string."""
        tokens = []
        i = 0
        while i < len(formula):
            ch = formula[i]
            
            if ch.isspace():
                i += 1
                continue
            
            # Numbers
            if ch.isdigit() or ch == '.':
                start = i
                has_dot = False
                while i < len(formula) and (formula[i].isdigit() or formula[i] == '.'):
                    if formula[i] == '.':
                        if has_dot:
                            break
                        has_dot = True
                    i += 1
                num_str = formula[start:i]
                try:
                    value = float(num_str) if '.' in num_str else int(num_str)
                except ValueError:
                    value = num_str
                tokens.append({'type': 'number', 'value': value, 'start': start, 'end': i})
                continue
            
            # Strings
            if ch == '"':
                start = i
                i += 1
                while i < len(formula) and formula[i] != '"':
                    if formula[i] == '"' and i + 1 < len(formula) and formula[i+1] == '"':
                        i += 2
                        continue
                    i += 1
                if i >= len(formula):
                    raise FormulaError("#VALUE!", "Unterminated string")
                value = formula[start+1:i].replace('""', '"')
                tokens.append({'type': 'string', 'value': value, 'start': start, 'end': i+1})
                i += 1
                continue
            
            # Range reference (A1:B2)
            if ch.isalpha():
                start = i
                while i < len(formula) and formula[i].isalnum():
                    i += 1
                # Check for range operator
                if i < len(formula) and formula[i] == ':':
                    i += 1
                    range_start = i
                    while i < len(formula) and formula[i].isalnum():
                        i += 1
                    tokens.append({'type': 'range', 'value': formula[start:i], 'start': start, 'end': i})
                else:
                    # Could be function name or cell reference
                    word = formula[start:i]
                    # Check if followed by '('
                    if i < len(formula) and formula[i] == '(':
                        tokens.append({'type': 'function', 'value': word, 'start': start, 'end': i})
                    else:
                        tokens.append({'type': 'reference', 'value': word, 'start': start, 'end': i})
                continue
            
            # Operators
            matched = False
            for op_len in range(2, 0, -1):
                if i + op_len <= len(formula):
                    op = formula[i:i+op_len]
                    if op in self.OPERATORS:
                        tokens.append({'type': 'operator', 'value': op, 'start': i, 'end': i+op_len})
                        i += op_len
                        matched = True
                        break
            if matched:
                continue
            
            # Parentheses and commas
            if ch == '(':
                tokens.append({'type': 'lparen', 'value': ch, 'start': i, 'end': i+1})
                i += 1
                continue
            if ch == ')':
                tokens.append({'type': 'rparen', 'value': ch, 'start': i, 'end': i+1})
                i += 1
                continue
            if ch == ',':
                tokens.append({'type': 'comma', 'value': ch, 'start': i, 'end': i+1})
                i += 1
                continue
            
            # Logical constants
            if formula[i:i+4].upper() == 'TRUE':
                tokens.append({'type': 'boolean', 'value': True, 'start': i, 'end': i+4})
                i += 4
                continue
            if formula[i:i+5].upper() == 'FALSE':
                tokens.append({'type': 'boolean', 'value': False, 'start': i, 'end': i+5})
                i += 5
                continue
            
            raise FormulaError("#VALUE!", f"Unexpected character: {ch}")
        
        tokens.append({'type': 'EOF', 'value': None, 'start': len(formula), 'end': len(formula)})
        return tokens

    def _current(self) -> dict[str, Any]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else {'type': 'EOF'}

    def _advance(self) -> dict[str, Any]:
        tok = self._current()
        self.pos += 1
        return tok

    def _parse_expression(self, min_precedence: int = 0) -> ASTNode:
        left = self._parse_primary()
        
        while True:
            tok = self._current()
            if tok['type'] != 'operator':
                break
            
            op = tok['value']
            precedence, associativity = self.OPERATORS[op]
            
            if precedence < min_precedence:
                break
            
            self._advance()  # consume operator
            
            # Right-associative operators bind tighter on the right
            next_min_precedence = precedence + 1 if associativity == 'left' else precedence
            right = self._parse_expression(next_min_precedence)
            
            left = ASTNode(
                type=NodeType.OPERATOR,
                value=op,
                children=[left, right],
                token_start=tok['start'],
                token_end=tok['end'],
            )
        
        return left

    def _parse_primary(self) -> ASTNode:
        tok = self._current()
        
        if tok['type'] == 'number':
            self._advance()
            return ASTNode(NodeType.NUMBER, value=tok['value'],
                          token_start=tok['start'], token_end=tok['end'])
        
        if tok['type'] == 'string':
            self._advance()
            return ASTNode(NodeType.STRING, value=tok['value'],
                          token_start=tok['start'], token_end=tok['end'])
        
        if tok['type'] == 'boolean':
            self._advance()
            return ASTNode(NodeType.BOOLEAN, value=tok['value'],
                          token_start=tok['start'], token_end=tok['end'])
        
        if tok['type'] == 'reference':
            self._advance()
            return ASTNode(NodeType.REFERENCE, value=tok['value'],
                          token_start=tok['start'], token_end=tok['end'])
        
        if tok['type'] == 'range':
            self._advance()
            return ASTNode(NodeType.RANGE, value=tok['value'],
                          token_start=tok['start'], token_end=tok['end'])
        
        if tok['type'] == 'function':
            return self._parse_function()
        
        if tok['type'] == 'lparen':
            self._advance()
            node = self._parse_expression()
            if self._current()['type'] != 'rparen':
                raise FormulaError("#VALUE!", "Missing closing parenthesis")
            self._advance()  # consume ')'
            return node
        
        if tok['type'] == 'operator' and tok['value'] in ('+', '-'):
            # Unary plus/minus
            op = tok['value']
            self._advance()
            operand = self._parse_primary()
            return ASTNode(NodeType.OPERATOR, value=op,
                          children=[operand],
                          token_start=tok['start'], token_end=tok['end'])
        
        raise FormulaError("#VALUE!", f"Unexpected token: {tok['type']}")

    def _parse_function(self) -> ASTNode:
        tok = self._advance()  # consume function name
        func_name = tok['value']
        
        if self._current()['type'] != 'lparen':
            raise FormulaError("#VALUE!", f"Expected '(' after function name {func_name}")
        self._advance()  # consume '('
        
        args = []
        if self._current()['type'] != 'rparen':
            while True:
                arg_node = self._parse_expression()
                args.append(arg_node)
                
                if self._current()['type'] == 'comma':
                    self._advance()  # consume ','
                    continue
                break
        
        if self._current()['type'] != 'rparen':
            raise FormulaError("#VALUE!", "Missing closing parenthesis for function")
        self._advance()  # consume ')'
        
        node = ASTNode(
            type=NodeType.FUNCTION,
            value=func_name,
            children=args,
            token_start=tok['start'],
            token_end=self.tokens[self.pos-1]['end'],
        )
        return node


class FormulaEngine:
    """Main formula evaluation engine."""
    
    def __init__(self, workbook: 'Workbook'):
        self.workbook = workbook
        self.parser = FormulaParser()
        self._cache: dict[str, ASTNode] = {}
        self._dependency_graph: dict[str, set[str]] = defaultdict(set)  # cell -> dependents
        self._reverse_deps: dict[str, set[str]] = defaultdict(set)  # cell -> dependencies

    def evaluate(self, formula: str, sheet_name: str, row: int, col: int) -> Any:
        """Evaluate formula at given cell location."""
        # Check cache
        cache_key = formula
        if cache_key in self._cache:
            ast = self._cache[cache_key]
        else:
            ast = self.parser.parse(formula)
            self._cache[cache_key] = ast
        
        # Create context
        context = FormulaContext(
            workbook=self.workbook,
            sheet_name=sheet_name,
            current_cell=(row, col),
        )
        
        # Check for circular references
        cell_key = f"{sheet_name}!{self._coords_to_a1(row, col)}"
        if cell_key in context.evaluating:
            raise FormulaError("#REF!", "Circular reference detected")
        
        context.evaluating.add(cell_key)
        
        try:
            result = ast.evaluate(context)
        finally:
            context.evaluating.discard(cell_key)
        
        # Update dependency graph
        self._update_dependencies(cell_key, ast)
        
        return result

    def _update_dependencies(self, cell_key: str, ast: ASTNode) -> None:
        """Extract and update cell dependencies from AST."""
        # Clear old dependencies
        for old_dep in self._reverse_deps[cell_key]:
            self._dependency_graph[old_dep].discard(cell_key)
        self._reverse_deps[cell_key].clear()
        
        # Extract new dependencies
        deps = self._extract_references(ast)
        for dep in deps:
            self._reverse_deps[cell_key].add(dep)
            self._dependency_graph[dep].add(cell_key)

    def _extract_references(self, node: ASTNode) -> set[str]:
        """Extract all cell references from AST."""
        refs = set()
        if node.type == NodeType.REFERENCE:
            refs.add(node.value)
        elif node.type == NodeType.RANGE:
            # Expand range to individual cells
            sheet, range_ref = self._parse_ref(node.value)
            # This would need full range expansion
            refs.add(node.value)
        
        for child in node.children:
            refs.update(self._extract_references(child))
        
        return refs

    def _parse_ref(self, ref: str) -> tuple[str, str]:
        if '!' in ref:
            sheet_part, cell_part = ref.split('!', 1)
            return sheet_part.strip("'"), cell_part
        return "Sheet1", ref

    def _coords_to_a1(self, row: int, col: int) -> str:
        """Convert 0-indexed coords to A1 reference."""
        col_str = ""
        col += 1
        while col > 0:
            col -= 1
            col_str = chr(ord('A') + col % 26) + col_str
            col //= 26
        return f"{col_str}{row + 1}"

    def get_dependents(self, cell_key: str) -> set[str]:
        """Get all cells that depend on this cell."""
        return self._dependency_graph.get(cell_key, set())

    def get_dependencies(self, cell_key: str) -> set[str]:
        """Get all cells this cell depends on."""
        return self._reverse_deps.get(cell_key, set())

    def recalculate(self, changed_cells: list[tuple[str, int, int]]) -> dict[tuple[str, int, int], Any]:
        """Recalculate all affected cells after changes."""
        # Build set of all cells that need recalculation
        to_recalc = set()
        visited = set()
        
        for sheet, row, col in changed_cells:
            cell_key = f"{sheet}!{self._coords_to_a1(row, col)}"
            to_recalc.update(self._get_all_dependents(cell_key))
        
        # Topological sort for evaluation order
        eval_order = self._topological_sort(to_recalc)
        
        results = {}
        for cell_key in eval_order:
            sheet, coord = cell_key.split('!', 1)
            row, col = self._a1_to_coords(coord)
            formula = self.workbook.get_formula(sheet, row, col)
            if formula:
                try:
                    value = self.evaluate(formula, sheet, row, col)
                    self.workbook.set_cell(sheet, row, col, value)
                    results[(sheet, row, col)] = value
                except FormulaError as e:
                    self.workbook.set_cell(sheet, row, col, e.to_value())
                    results[(sheet, row, col)] = e.to_value()
        
        return results

    def _get_all_dependents(self, cell_key: str) -> set[str]:
        """Get all transitive dependents."""
        result = set()
        queue = deque([cell_key])
        
        while queue:
            current = queue.popleft()
            if current in result:
                continue
            result.add(current)
            for dep in self._dependency_graph.get(current, []):
                if dep not in visited:
                    queue.append(dep)
        
        return result

    def _topological_sort(self, nodes: set[str]) -> list[str]:
        """Sort nodes in evaluation order (dependencies first)."""
        # Build subgraph
        in_degree = {node: 0 for node in nodes}
        adj = {node: [] for node in nodes}
        
        for node in nodes:
            for dep in self._dependency_graph.get(node, []):
                if dep in nodes:
                    adj[node].append(dep)
                    in_degree[dep] += 1
        
        # Kahn's algorithm
        queue = deque([n for n in nodes if in_degree[n] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Add any remaining (shouldn't happen if no cycles)
        remaining = [n for n in nodes if n not in result]
        result.extend(remaining)
        
        # Reverse so dependencies are evaluated first
        return list(reversed(result))

    def _a1_to_coords(self, a1: str) -> tuple[int, int]:
        match = re.match(r'^([A-Z]+)(\d+)$', a1.upper())
        col_str, row_str = match.groups()
        col = 0
        for ch in col_str:
            col = col * 26 + (ord(ch) - ord('A') + 1)
        col -= 1
        row = int(row_str) - 1
        return row, col

    def clear_cache(self) -> None:
        self._cache.clear()
        self._dependency_graph.clear()
        self._reverse_deps.clear()


class Workbook:
    """Spreadsheet workbook with formula support."""
    
    def __init__(self):
        self.sheets: dict[str, Sheet] = {}
        self.formulas: dict[str, dict[tuple[int, int], str]] = defaultdict(dict)
        self.engine = FormulaEngine(self)
        self._create_sheet("Sheet1")

    def _create_sheet(self, name: str) -> 'Sheet':
        sheet = Sheet(name)
        self.sheets[name] = sheet
        return sheet

    def get_sheet(self, name: str) -> Optional['Sheet']:
        return self.sheets.get(name)

    def get_cell(self, sheet_name: str, row: int, col: int) -> Any:
        sheet = self.sheets.get(sheet_name)
        if sheet:
            return sheet.get_cell(row, col)
        return None

    def set_cell(self, sheet_name: str, row: int, col: int, value: Any) -> None:
        sheet = self.sheets.get(sheet_name)
        if sheet:
            sheet.set_cell(row, col, value)

    def get_formula(self, sheet_name: str, row: int, col: int) -> Optional[str]:
        return self.formulas[sheet_name].get((row, col))

    def set_formula(self, sheet_name: str, row: int, col: int, formula: str) -> None:
        self.formulas[sheet_name][(row, col)] = formula
        # Recalculate this cell and dependents
        self.engine.evaluate(formula, sheet_name, row, col)

    def get_sheet_names(self) -> list[str]:
        return list(self.sheets.keys())


class Sheet:
    """Spreadsheet sheet with cells."""
    
    def __init__(self, name: str):
        self.name = name
        self.cells: dict[tuple[int, int], Any] = {}

    def get_cell(self, row: int, col: int) -> Any:
        return self.cells.get((row, col))

    def set_cell(self, row: int, col: int, value: Any) -> None:
        self.cells[(row, col)] = value

    def get_range(self, start_row: int, start_col: int, end_row: int, end_col: int) -> list[list[Any]]:
        result = []
        for r in range(start_row, end_row + 1):
            row_data = []
            for c in range(start_col, end_col + 1):
                row_data.append(self.cells.get((r, c)))
            result.append(row_data)
        return result
