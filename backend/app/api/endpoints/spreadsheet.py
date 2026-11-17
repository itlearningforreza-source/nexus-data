"""
Spreadsheet API Endpoints

Provides endpoints for:
- Formula evaluation
- Workbook management
- Dependency graph
- Named ranges
- Recalculation
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.api.deps import get_current_user
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.core.errors import ValidationError
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.services.formula_engine import (
    FormulaEngine, Workbook, FormulaParser, FormulaError,
    FormulaContext, FormulaRegistry
)

logger = logging.getLogger("nexus")

router = APIRouter(prefix="/api/spreadsheet", tags=["spreadsheet"])


# In-memory workbook storage (in production, use Redis or database)
_workbooks: dict[str, Workbook] = {}


class FormulaRequest(BaseModel):
    formula: str
    sheet_name: str = "Sheet1"
    row: int
    col: int


class FormulaResponse(BaseModel):
    value: Any
    error: Optional[str] = None
    dependencies: list[str] = []
    dependents: list[str] = []


class WorkbookCreate(BaseModel):
    dataset_id: str
    sheet_name: str = "Sheet1"
    rows: int = 100
    cols: int = 26


class WorkbookResponse(BaseModel):
    workbook_id: str
    sheets: list[str]
    message: str


class SetCellRequest(BaseModel):
    workbook_id: str
    sheet_name: str
    row: int
    col: int
    value: Any
    formula: Optional[str] = None


class SetCellResponse(BaseModel):
    value: Any
    recalculated: dict[str, Any] = {}
    error: Optional[str] = None


class RecalcRequest(BaseModel):
    workbook_id: str
    changed_cells: list[tuple[str, int, int]]  # (sheet, row, col)


class DependencyGraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]


class NamedRangeRequest(BaseModel):
    workbook_id: str
    name: str
    sheet_name: str
    start_row: int
    start_col: int
    end_row: int
    end_col: int


class NamedRangeResponse(BaseModel):
    name: str
    reference: str


class AutoCompleteRequest(BaseModel):
    workbook_id: str
    sheet_name: str
    partial: str
    row: int
    col: int


class AutoCompleteResponse(BaseModel):
    suggestions: list[dict[str, Any]]


def _get_workbook(workbook_id: str) -> Workbook:
    if workbook_id not in _workbooks:
        raise HTTPException(status_code=404, detail="Workbook not found")
    return _workbooks[workbook_id]


def _get_engine(workbook_id: str) -> FormulaEngine:
    wb = _get_workbook(workbook_id)
    return FormulaEngine(wb)


@router.post("/workbook", response_model=WorkbookResponse)
def create_workbook(
    payload: WorkbookCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new spreadsheet workbook from a dataset."""
    import uuid
    
    ds = get_dataset_for_user(db, payload.dataset_id, user.id)
    df = load_dataset_df(ds)
    
    workbook_id = uuid.uuid4().hex
    wb = Workbook()
    
    # Create initial sheet with dataset data
    sheet = wb.sheets.get(payload.sheet_name)
    if not sheet:
        sheet = wb._create_sheet(payload.sheet_name)
    
    # Load data into sheet
    max_rows = min(payload.rows, len(df))
    max_cols = min(payload.cols, len(df.columns))
    
    # Set headers
    for c_idx, col_name in enumerate(df.columns[:max_cols]):
        sheet.set_cell(0, c_idx, col_name)
    
    # Set data
    for r_idx in range(max_rows):
        for c_idx in range(max_cols):
            val = df.iloc[r_idx, c_idx]
            sheet.set_cell(r_idx + 1, c_idx, val)
    
    _workbooks[workbook_id] = wb
    
    return WorkbookResponse(
        workbook_id=workbook_id,
        sheets=list(wb.sheets.keys()),
        message=f"Workbook created with {max_rows} rows and {max_cols} columns from dataset {ds.name}"
    )


@router.get("/workbook/{workbook_id}")
def get_workbook(workbook_id: str, user=Depends(get_current_user)):
    """Get workbook metadata."""
    wb = _get_workbook(workbook_id)
    
    sheets_info = {}
    for name, sheet in wb.sheets.items():
        # Get dimensions
        max_row = max((r for r, _ in sheet.cells.keys()), default=-1)
        max_col = max((c for _, c in sheet.cells.keys()), default=-1)
        sheets_info[name] = {
            "rows": max_row + 1,
            "cols": max_col + 1,
            "formulas": len([v for v in sheet.cells.values() if isinstance(v, str) and v.startswith('=')]),
        }
    
    return {
        "workbook_id": workbook_id,
        "sheets": sheets_info,
        "named_ranges": list(wb.formulas.keys()) if hasattr(wb, 'named_ranges') else [],
    }


@router.post("/workbook/{workbook_id}/evaluate", response_model=FormulaResponse)
def evaluate_formula(
    workbook_id: str,
    payload: FormulaRequest,
    user=Depends(get_current_user)
):
    """Evaluate a formula at a specific cell."""
    engine = _get_engine(workbook_id)
    
    try:
        result = engine.evaluate(payload.formula, payload.sheet_name, payload.row, payload.col)
        
        # Get dependencies
        cell_key = f"{payload.sheet_name}!{engine._coords_to_a1(payload.row, payload.col)}"
        deps = engine.get_dependencies(cell_key)
        dependents = engine.get_dependents(cell_key)
        
        # Convert FormulaError to error string
        error = None
        if isinstance(result, FormulaError):
            error = result.to_value()
            result = None
        
        return FormulaResponse(
            value=result,
            error=error,
            dependencies=list(deps),
            dependents=list(dependents),
        )
    except FormulaError as e:
        return FormulaResponse(
            value=None,
            error=e.to_value(),
        )
    except Exception as e:
        logger.exception("Formula evaluation failed")
        return FormulaResponse(
            value=None,
            error=f"#VALUE!: {str(e)}",
        )


@router.post("/workbook/{workbook_id}/cell", response_model=SetCellResponse)
def set_cell(
    workbook_id: str,
    payload: SetCellRequest,
    user=Depends(get_current_user)
):
    """Set a cell value or formula and recalculate dependencies."""
    engine = _get_engine(workbook_id)
    wb = _get_workbook(workbook_id)
    
    try:
        sheet = wb.sheets.get(payload.sheet_name)
        if not sheet:
            sheet = wb._create_sheet(payload.sheet_name)
        
        if payload.formula and isinstance(payload.formula, str) and payload.formula.startswith('='):
            # It's a formula
            wb.engine.set_formula(payload.sheet_name, payload.row, payload.col, payload.formula)
            result = wb.engine.evaluate(payload.formula, payload.sheet_name, payload.row, payload.col)
            value = result
        else:
            # It's a value
            sheet.set_cell(payload.row, payload.col, payload.value)
            value = payload.value
            
            # If there was a formula, remove it
            if hasattr(engine, 'formulas'):
                pass  # Formula engine handles this
        
        # Recalculate dependents
        cell_key = f"{payload.sheet_name}!{engine._coords_to_a1(payload.row, payload.col)}
        dependents = engine.get_dependents(cell_key)
        
        recalculated = {}
        for dep in dependents:
            dep_sheet, dep_coord = dep.split('!', 1)
            dep_row, dep_col = engine._a1_to_coords(dep_coord)
            dep_formula = engine.workbook.get_formula(dep_sheet, dep_row, dep_col)
            if dep_formula:
                try:
                    new_val = engine.evaluate(dep_formula, dep_sheet, dep_row, dep_col)
                    engine.workbook.set_cell(dep_sheet, dep_row, dep_col, new_val)
                    recalculated[dep] = new_val
                except FormulaError as fe:
                    engine.workbook.set_cell(dep_sheet, dep_row, dep_col, fe.to_value())
                    recalculated[dep] = fe.to_value()
        
        return SetCellResponse(
            value=value,
            recalculated=recalculated,
        )
    except FormulaError as e:
        return SetCellResponse(
            value=None,
            error=e.to_value(),
        )
    except Exception as e:
        logger.exception("Set cell failed")
        return SetCellResponse(
            value=None,
            error=f"#VALUE!: {str(e)}",
        )


@router.post("/workbook/{workbook_id}/recalculate")
def recalculate(
    workbook_id: str,
    payload: RecalcRequest,
    user=Depends(get_current_user)
):
    """Recalculate all affected cells after bulk changes."""
    engine = _get_engine(workbook_id)
    
    # Convert to list of (sheet, row, col)
    changed = [(sheet, row, col) for sheet, row, col in payload.changed_cells]
    
    results = engine.recalculate(changed)
    
    return {
        "recalculated": results,
        "count": len(results),
    }


@router.get("/workbook/{workbook_id}/dependencies", response_model=DependencyGraphResponse)
def get_dependency_graph(
    workbook_id: str,
    user=Depends(get_current_user)
):
    """Get the full dependency graph for visualization."""
    engine = _get_engine(workbook_id)
    
    nodes = []
    edges = []
    
    # Collect all cells with formulas
    for (sheet, row, col), formula in engine.workbook.formulas.items():
        cell_key = f"{sheet}!{engine._coords_to_a1(row, col)}"
        nodes.append({
            "id": cell_key,
            "label": cell_key,
            "formula": formula,
            "type": "formula",
        })
        
        deps = engine.get_dependencies(cell_key)
        for dep in deps:
            edges.append({"from": dep, "to": cell_key})
    
    return DependencyGraphResponse(nodes=nodes, edges=edges)


@router.post("/workbook/{workbook_id}/named-range", response_model=NamedRangeResponse)
def create_named_range(
    workbook_id: str,
    payload: NamedRangeRequest,
    user=Depends(get_current_user)
):
    """Create a named range."""
    wb = _get_workbook(workbook_id)
    
    # Initialize named ranges if needed
    if not hasattr(wb, 'named_ranges'):
        wb.named_ranges = {}
    
    engine = FormulaEngine(wb)
    start_a1 = engine._coords_to_a1(payload.start_row, payload.start_col)
    end_a1 = engine._coords_to_a1(payload.end_row, payload.end_col)
    ref = f"{payload.sheet_name}!{start_a1}:{end_a1}"
    
    wb.named_ranges[payload.name] = ref
    
    return NamedRangeResponse(name=payload.name, reference=ref)


@router.get("/workbook/{workbook_id}/named-ranges")
def list_named_ranges(workbook_id: str, user=Depends(get_current_user)):
    """List all named ranges."""
    wb = _get_workbook(workbook_id)
    
    if not hasattr(wb, 'named_ranges'):
        return {"named_ranges": {}}
    
    return {"named_ranges": wb.named_ranges}


@router.post("/workbook/{workbook_id}/autocomplete", response_model=AutoCompleteResponse)
def autocomplete(
    workbook_id: str,
    payload: AutoCompleteRequest,
    user=Depends(get_current_user)
):
    """Get formula autocomplete suggestions."""
    # Function suggestions
    function_names = list(FormulaRegistry.FUNCTIONS.keys())
    
    # Filter by partial match
    partial_upper = payload.partial.upper()
    suggestions = []
    
    for fn in function_names:
        if fn.startswith(partial_upper):
            func_handler = FormulaRegistry.FUNCTIONS[fn]
            suggestions.append({
                "label": fn,
                "type": "function",
                "detail": f"{fn}(...) - {', '.join(func_handler.categories) if func_handler.categories else 'Function'}",
                "documentation": f"{fn} function",
            })
    
    # Add named ranges if available
    wb = _get_workbook(workbook_id)
    if hasattr(wb, 'named_ranges'):
        for name in wb.named_ranges:
            if name.upper().startswith(partial_upper):
                suggestions.append({
                    "label": name,
                    "type": "named_range",
                    "detail": f"Named range: {wb.named_ranges[name]}",
                })
    
    # Add column references
    sheet = wb.sheets.get(payload.sheet_name)
    if sheet:
        max_col = max((c for _, c in sheet.cells.keys()), default=-1)
        for c in range(max_col + 1):
            col_ref = engine._coords_to_a1(0, c)
            if col_ref.upper().startswith(partial_upper):
                suggestions.append({
                    "label": col_ref,
                    "type": "reference",
                    "detail": f"Column {col_ref}",
                })
    
    return AutoCompleteResponse(suggestions=suggestions[:20])


@router.get("/functions")
def list_functions(user=Depends(get_current_user)):
    """List all available spreadsheet functions with metadata."""
    functions = []
    for name, handler in FormulaRegistry.FUNCTIONS.items():
        functions.append({
            "name": name,
            "min_args": handler.min_args,
            "max_args": handler.max_args if handler.max_args != float('inf') else -1,
            "variadic": handler.variadic,
            "categories": handler.categories,
        })
    
    # Group by category
    categories = {}
    for fn in functions:
        for cat in fn["categories"]:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(fn)
    
    return {"functions": functions, "categories": categories}
