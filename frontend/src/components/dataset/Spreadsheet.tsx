// Spreadsheet Component
//
// Professional spreadsheet UI with:
// - Formula bar with autocomplete
// - Editable grid with formula support
// - Multiple sheets
// - Dependency graph visualization
// - Named ranges management
// - Keyboard navigation

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronLeft,
  Plus,
  Search,
  Download,
  Zap,
  Trash2,
  EyeOff,
  Settings,
  Maximize2,
  ExternalLink,
} from 'lucide-react';
import { features } from '@/lib/features';
import { toast } from '@/components/ui';
import {
  Button,
  Input,
  Divider,
} from '@/components/ui';

// Column width constants
const DEFAULT_COL_WIDTH = 100;
const ROW_HEIGHT = 28;
const HEADER_HEIGHT = 28;
const FORMULA_BAR_HEIGHT = 36;
const SHEET_TAB_HEIGHT = 32;

// Types
interface Cell {
  value: unknown;
  formula?: string;
  error?: string;
  displayValue: string;
}

interface Sheet {
  name: string;
  cells: Map<string, Cell>; // key: "row,col"
  rowCount: number;
  colCount: number;
  columnWidths: number[];
}

interface Workbook {
  id: string;
  sheets: Map<string, Sheet>;
  activeSheet: string;
  namedRanges: Map<string, string>;
}

interface DependencyNode {
  id: string;
  label: string;
  formula: string;
  type: string;
}

interface DependencyEdge {
  from: string;
  to: string;
}

function colToA1(col: number): string {
  let result = '';
  col++;
  while (col > 0) {
    col--;
    result = String.fromCharCode(65 + (col % 26)) + result;
    col = Math.floor(col / 26);
  }
  return result;
}

function a1ToCol(a1: string): number {
  let col = 0;
  for (const ch of a1.toUpperCase()) {
    col = col * 26 + (ch.charCodeAt(0) - 64);
  }
  return col - 1;
}

function parseCoord(coord: string): { row: number; col: number } {
  const match = coord.match(/^([A-Z]+)(\d+)$/i);
  if (!match) return { row: 0, col: 0 };
  return { row: parseInt(match[2], 10) - 1, col: a1ToCol(match[1]) };
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : value.toFixed(4).replace(/\.?0+$/, '');
  }
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
  return String(value);
}

export default function Spreadsheet({
  datasetId,
  onClose,
}: {
  datasetId: string;
  onClose?: () => void;
}) {
  const [workbookId, setWorkbookId] = useState<string | null>(null);
  const [workbook, setWorkbook] = useState<Workbook | null>(null);
  const [loading, setLoading] = useState(false);
  const [formula, setFormula] = useState('');
  const [activeCell, setActiveCell] = useState<{ row: number; col: number }>({ row: 0, col: 0 });
  const [showDependencies, setShowDependencies] = useState(false);
  const [showNamedRanges, setShowNamedRanges] = useState(false);
  const [showFunctions, setShowFunctions] = useState(false);
  const [dependencies, setDependencies] = useState<{ nodes: DependencyNode[]; edges: DependencyEdge[] }>({ nodes: [], edges: [] });
  const [functions, setFunctions] = useState<{ name: string; min_args: number; max_args: number; variadic: boolean; categories: string[] }[]>([]);
  const [namedRanges, setNamedRanges] = useState<Record<string, string>>({});
  
  // Refs
  const gridRef = useRef<HTMLDivElement>(null);
  const formulaBarRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<HTMLDivElement>(null);
  const [autocompleteVisible, setAutocompleteVisible] = useState(false);
  const [autocompleteSuggestions, setAutocompleteSuggestions] = useState<{ label: string; type: string; detail: string; documentation?: string }[]>([]);
  const [autocompleteIndex, setAutocompleteIndex] = useState(0);
  
  // Viewport for virtualization
  const [scrollTop, setScrollTop] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);
  
  // Initialize workbook from dataset
  const initWorkbook = useCallback(async () => {
    setLoading(true);
    try {
      const result = await features.spreadsheet.createWorkbook(datasetId);
      setWorkbookId(result.workbook_id);
      
      // Load workbook details
      const wb = await features.spreadsheet.getWorkbook(result.workbook_id);
      
      const sheets = new Map<string, Sheet>();
      for (const [name, info] of Object.entries(wb.sheets)) {
        sheets.set(name, {
          name,
          cells: new Map(),
          rowCount: info.rows,
          colCount: info.cols,
          columnWidths: Array(info.cols).fill(DEFAULT_COL_WIDTH),
        });
      }
      
      setWorkbook({
        id: result.workbook_id,
        sheets,
        activeSheet: wb.sheets[Object.keys(wb.sheets)[0]] ? Object.keys(wb.sheets)[0] : 'Sheet1',
        namedRanges: new Map(Object.entries(wb.named_ranges || {})),
      });
      
      // Load functions
      const funcs = await features.spreadsheet.listFunctions();
      setFunctions(funcs.functions);
      
      // Load named ranges
      if (wb.named_ranges && wb.named_ranges.length > 0) {
        const nr = await features.spreadsheet.listNamedRanges(result.workbook_id);
        setNamedRanges(nr.named_ranges);
      }
      
      toast('Workbook created', result.message, 'success');
    } catch (error) {
      toast('Failed to create workbook', 'Please try again.', 'error');
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    initWorkbook();
  }, [initWorkbook]);

  // Load dependencies when workbook changes
  useEffect(() => {
    if (workbookId && showDependencies) {
      features.spreadsheet.getDependencies(workbookId).then(setDependencies).catch(() => {});
    }
  }, [workbookId, showDependencies]);

  // Get active sheet
  const activeSheet = useMemo(() => {
    return workbook?.sheets.get(workbook?.activeSheet || '');
  }, [workbook]);

  // Get visible columns based on scroll
  const visibleCols = useMemo(() => {
    if (!activeSheet) return [];
    let totalWidth = 0;
    const startCol = activeSheet.columnWidths.findIndex((_, i) => {
      totalWidth += activeSheet.columnWidths[i];
      return totalWidth > scrollLeft;
    });
    const visible = [];
    totalWidth = 0;
    for (let i = Math.max(0, startCol - 1); i < activeSheet.colCount; i++) {
      totalWidth += activeSheet.columnWidths[i];
      if (totalWidth > scrollLeft + (gridRef.current?.clientWidth || 800)) break;
      visible.push(i);
    }
    return visible;
  }, [activeSheet, scrollLeft]);

  // Get visible rows based on scroll
  const visibleRows = useMemo(() => {
    if (!activeSheet) return [];
    const rowHeight = ROW_HEIGHT;
    const startRow = Math.floor(scrollTop / rowHeight);
    const visibleCount = Math.ceil((gridRef.current?.clientHeight || 400) / rowHeight) + 1;
    return Array.from({ length: visibleCount }, (_, i) => startRow + i).filter(r => r < activeSheet.rowCount);
  }, [activeSheet, scrollTop]);

  // Handle formula bar input
  const handleFormulaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setFormula(value);
    
    // Trigger autocomplete for formulas
    if (value.startsWith('=') && workbookId) {
      const partial = value.slice(1);
      features.spreadsheet.autocomplete(workbookId, activeSheet?.name || 'Sheet1', partial, activeCell.row, activeCell.col)
        .then(({ suggestions }) => {
          setAutocompleteSuggestions(suggestions);
          setAutocompleteVisible(suggestions.length > 0);
          setAutocompleteIndex(0);
        })
        .catch(() => setAutocompleteVisible(false));
    } else {
      setAutocompleteVisible(false);
    }
  };

  // Handle formula bar keydown
  const handleFormulaKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      applyFormula();
    } else if (e.key === 'Escape') {
      setFormula('');
      formulaBarRef.current?.blur();
    } else if (autocompleteVisible && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault();
      setAutocompleteIndex(prev => 
        e.key === 'ArrowDown' 
          ? Math.min(prev + 1, autocompleteSuggestions.length - 1)
          : Math.max(prev - 1, 0)
      );
    } else if (autocompleteVisible && e.key === 'Tab') {
      e.preventDefault();
      insertAutocomplete(autocompleteSuggestions[autocompleteIndex]);
    }
  };

  const insertAutocomplete = (suggestion: typeof autocompleteSuggestions[0]) => {
    if (!suggestion) return;
    const beforeCursor = formula.slice(0, formula.lastIndexOf(formula.match(/[A-Z]+$/i)?.[0] || ''));
    const afterCursor = formula.slice(formula.lastIndexOf(formula.match(/[A-Z]+$/i)?.[0] || '') + (formula.match(/[A-Z]+$/i)?.[0]?.length || 0));
    setFormula(beforeCursor + suggestion.label + afterCursor);
    setAutocompleteVisible(false);
    formulaBarRef.current?.focus();
  };

  const applyFormula = async () => {
    if (!workbookId || !activeSheet) return;
    
    try {
      const result = await features.spreadsheet.setCell(
        workbookId,
        activeSheet.name,
        activeCell.row,
        activeCell.col,
        formula,
        formula.startsWith('=') ? formula : undefined
      );
      
      if (result.error) {
        toast('Formula error', result.error, 'error');
      } else {
        // Update local cell
        setWorkbook(prev => {
          if (!prev) return prev;
          const newSheets = new Map(prev.sheets);
          const sheet = new Map(activeSheet!.cells);
          sheet.set(`${activeCell.row},${activeCell.col}`, {
            value: result.value,
            formula: formula.startsWith('=') ? formula : undefined,
            displayValue: formatCellValue(result.value),
          });
          newSheets.set(activeSheet!.name, { ...activeSheet!, cells: sheet });
          return { ...prev!, sheets: newSheets };
        });
        
        // Update recalculated cells
        if (result.recalculated && Object.keys(result.recalculated).length > 0) {
          setWorkbook(prev => {
            if (!prev) return prev;
            const newSheets = new Map(prev.sheets);
            for (const [coord, value] of Object.entries(result.recalculated)) {
              const [sheetName, cellCoord] = coord.split('!');
              const { row, col } = parseCoord(cellCoord);
              const sheet = newSheets.get(sheetName);
              if (sheet) {
                const newCells = new Map(sheet.cells);
                newCells.set(`${row},${col}`, {
                  value,
                  displayValue: formatCellValue(value),
                });
                newSheets.set(sheetName, { ...sheet, cells: newCells });
              }
            }
            return { ...prev!, sheets: newSheets };
          });
        }
        
        toast('Formula applied', 'Cell updated', 'success');
      }
    } catch (error) {
      toast('Failed to apply formula', 'Please try again.', 'error');
    }
  };

  // Handle cell click
  const handleCellClick = (row: number, col: number) => {
    setActiveCell({ row, col });
    
    // Show formula if cell has one
    const cell = activeSheet?.cells.get(`${row},${col}`);
    if (cell?.formula) {
      setFormula(cell.formula);
    } else {
      setFormula(cell?.displayValue || '');
    }
    formulaBarRef.current?.focus();
  };



  // Handle scroll
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
    setScrollLeft(e.currentTarget.scrollLeft);
  };

  // Add new sheet
  const addSheet = () => {
    if (!workbook) return;
    const sheetNum = workbook.sheets.size + 1;
    const newName = `Sheet${sheetNum}`;
    
    setWorkbook(prev => {
      if (!prev) return prev;
      const newSheets = new Map(prev.sheets);
      newSheets.set(newName, {
        name: newName,
        cells: new Map(),
        rowCount: 100,
        colCount: 26,
        columnWidths: Array(26).fill(DEFAULT_COL_WIDTH),
      });
      return { ...prev!, sheets: newSheets, activeSheet: newName };
    });
  };

  // Switch sheet
  const switchSheet = (name: string) => {
    setWorkbook(prev => prev ? { ...prev, activeSheet: name } : prev);
  };

  // Create named range
  const createNamedRange = async (name: string) => {
    if (!workbookId || !activeSheet) return;
    
    // For simplicity, use current selection
    try {
      await features.spreadsheet.createNamedRange(
        workbookId,
        name,
        activeSheet.name,
        activeCell.row,
        activeCell.col,
        activeCell.row,
        activeCell.col
      );
      toast('Named range created', `${name} defined`, 'success');
      const nr = await features.spreadsheet.listNamedRanges(workbookId);
      setNamedRanges(nr.named_ranges);
      setShowNamedRanges(false);
    } catch (error) {
      toast('Failed to create named range', 'Please try again.', 'error');
    }
  };

  // Export to CSV
  const exportCsv = () => {
    if (!activeSheet) return;
    
    let csv = '';
    // Headers
    csv += activeSheet.columnWidths.map((_, i) => colToA1(i)).join(',') + '\n';
    
    // Data rows
    for (let r = 0; r < activeSheet.rowCount; r++) {
      const row = [];
      for (let c = 0; c < activeSheet.colCount; c++) {
        const cell = activeSheet.cells.get(`${r},${c}`);
        row.push(cell?.displayValue || '');
      }
      csv += row.map(v => { const needsQuotes = /[,"\n]/.test(v); return needsQuotes ? `"${v.replace(/"/g, '""')}"` : v; }).join(',') + '\n';
    }
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeSheet.name}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Exported', 'CSV downloaded', 'success');
  };

  // Current cell reference (A1 notation)
  const currentCellRef = useMemo(() => {
    return `${colToA1(activeCell.col)}${activeCell.row + 1}`;
  }, [activeCell]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm text-muted-foreground">Loading spreadsheet...</span>
        </div>
      </div>
    );
  }

  if (!workbook || !activeSheet) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground">No workbook loaded</p>
          <Button onClick={initWorkbook} className="mt-4">Create Workbook</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2 bg-card">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={onClose}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Divider className="h-6 mx-1" />
          <Button variant="outline" size="xs" leftIcon={<Plus className="h-3 w-3" />} onClick={addSheet}>
            Sheet
          </Button>
          <Button variant="outline" size="xs" leftIcon={<Download className="h-3 w-3" />} onClick={exportCsv}>
            Export CSV
          </Button>
        </div>
        
        <div className="flex-1" />
        
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => setShowDependencies(!showDependencies)} title="Dependency Graph">
            <Zap className="h-4 w-4" />
          </Button>
          <Button variant={showDependencies ? 'secondary' : 'ghost'} size="icon" onClick={() => setShowDependencies(!showDependencies)} title="Dependency Graph">
            <ExternalLink className="h-4 w-4" />
          </Button>
          <Button variant={showNamedRanges ? 'secondary' : 'ghost'} size="icon" onClick={() => setShowNamedRanges(!showNamedRanges)} title="Named Ranges">
            <Settings className="h-4 w-4" />
          </Button>
          <Button variant={showFunctions ? 'secondary' : 'ghost'} size="icon" onClick={() => setShowFunctions(!showFunctions)} title="Functions">
            <Search className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setShowFunctions(!showFunctions)} title="Functions">
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Formula Bar */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 bg-card" style={{ height: FORMULA_BAR_HEIGHT }}>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono w-24">
          {currentCellRef}
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => { setFormula('='); formulaBarRef.current?.focus(); setAutocompleteVisible(true); }}>=
          <Zap className="h-3.5 w-3.5" />
        </Button>
        <Input
          ref={formulaBarRef}
          value={formula}
          onChange={handleFormulaChange}
          onKeyDown={handleFormulaKeyDown}
          placeholder="Enter formula or value..."
          className="flex-1 h-7 text-sm font-mono bg-transparent"
          autoComplete="off"
          spellCheck={false}
        />
        <Button variant="ghost" size="icon" onClick={applyFormula} disabled={!formula.trim()}>
          <Zap className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Autocomplete Dropdown */}
      {autocompleteVisible && autocompleteSuggestions.length > 0 && (
        <div
          ref={autocompleteRef}
          className="fixed z-50 mt-1 max-h-48 overflow-auto rounded-md border border-border bg-popover p-1 shadow-lg w-64"
          style={{ 
            left: formulaBarRef.current?.getBoundingClientRect().left,
            top: formulaBarRef.current?.getBoundingClientRect().bottom + window.scrollY + 2
          }}
        >
          {autocompleteSuggestions.map((s, i) => (
            <div
              key={s.label}
              className={`px-2 py-1.5 text-xs cursor-pointer transition-colors ${i === autocompleteIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-accent'}`}
              onClick={() => insertAutocomplete(s)}
            >
              <span className="font-medium text-primary">{s.label}</span>
              <span className="ml-2 text-muted-foreground">{s.detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* Sheet Tabs */}
      <div className="flex items-center gap-1 border-b border-border px-2 py-1 bg-card" style={{ height: SHEET_TAB_HEIGHT }}>        <div className="flex-1 flex items-center gap-1 overflow-x-auto pb-1">
          {Array.from(workbook.sheets.keys()).map((name, i) => (
            <button
              key={name}
              onClick={() => switchSheet(name)}
              className={
                `flex items-center gap-1.5 px-2 py-1 rounded-t-lg text-xs font-medium transition-colors whitespace-nowrap ` +
                (workbook.activeSheet === name
                  ? 'bg-background text-foreground border-b-2 border-primary'
                  : 'text-muted-foreground hover:bg-muted/50')
              }
            >
              {name}
              <Button
                variant="ghost"
                size="icon"
                className="h-4 w-4 p-0 opacity-0 hover:opacity-100"
                onClick={(e) => { e.stopPropagation(); }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </button>
          ))}
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={addSheet}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Main Grid */}
      <div
        ref={gridRef}
        className="flex-1 overflow-auto relative"
        onScroll={handleScroll}
        style={{ 
          height: `calc(100% - ${FORMULA_BAR_HEIGHT + SHEET_TAB_HEIGHT + 60}px)`
        }}
      >
        {/* Column Headers (Sticky) */}
        <div className="sticky top-0 z-10 flex" style={{ height: HEADER_HEIGHT }}>          <div className="sticky left-0 z-20 flex items-center justify-center border-r border-border bg-muted/95" style={{ width: 40, height: HEADER_HEIGHT }}>#</div>
          <div className="flex overflow-x-auto" style={{ marginLeft: 40 }}>            {visibleCols.map(col => (
              <div
                key={col}
                className="sticky top-0 z-10 flex items-center justify-center border-r border-border bg-muted/95 font-mono text-[10px] text-muted-foreground"
                style={{ 
                  width: activeSheet.columnWidths[col],
                  height: HEADER_HEIGHT,
                  left: activeSheet.columnWidths.slice(0, col).reduce((a, b) => a + b, 0)
                }}
              >
                {colToA1(col)}
              </div>
            ))}
          </div>
        </div>

        {/* Row Headers (Sticky) */}
        <div className="absolute left-0 top-0 z-10" style={{ top: HEADER_HEIGHT }}>          {visibleRows.map(row => (
            <div
              key={row}
              className="sticky left-0 z-20 flex items-center justify-center border-b border-border bg-muted/95 font-mono text-[10px] text-muted-foreground"
              style={{ width: 40, height: ROW_HEIGHT, top: row * ROW_HEIGHT }}
            >
              {row + 1}
            </div>
          ))}
        </div>

        {/* Grid Cells */}
        <div
          className="absolute"
          style={{ 
            top: HEADER_HEIGHT,
            left: 40,
            width: activeSheet.columnWidths.reduce((a, b) => a + b, 0),
            height: activeSheet.rowCount * ROW_HEIGHT
          }}
        >
          {visibleRows.map(row => (
            <div
              key={row}
              className="flex"
              style={{ top: row * ROW_HEIGHT, height: ROW_HEIGHT, position: 'absolute', width: '100%' }}
            >
              {visibleCols.map(col => {
                const cellKey = `${row},${col}`;
                const cell = activeSheet.cells.get(cellKey);
                const isActive = activeCell.row === row && activeCell.col === col;
                const hasFormula = !!cell?.formula;
                const hasError = !!cell?.error;
                
                return (
                  <div
                    key={col}
                    className={`relative border-r border-border/60 border-b border-border/60 transition-colors ${isActive ? 'ring-2 ring-primary ring-offset-1 ring-offset-background' : ''}`}
                    style={{ width: activeSheet.columnWidths[col], height: ROW_HEIGHT }}
                    onClick={() => handleCellClick(row, col)}
                    onDoubleClick={() => { formulaBarRef.current?.focus(); }}
                  >
                    {hasError && (
                      <div className="absolute inset-0 bg-red-500/10" />
                    )}
                    {hasFormula && !isActive && (
                      <div className="absolute top-0 right-0 mt-0.5 mr-0.5 h-3 w-3" title="Has formula">
                        <Zap className="h-3 w-3 text-primary/60" />
                      </div>
                    )}
                    <div
                      className={`flex items-center px-2 h-full overflow-hidden text-xs ${hasError ? 'text-red-500' : ''}`}
                      style={{ width: activeSheet.columnWidths[col] - 4 }}
                    >
                      {cell?.displayValue ?? ''}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Side Panels */}
      {(showDependencies || showNamedRanges || showFunctions) && (
        <div className="fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-black/50" onClick={() => { setShowDependencies(false); setShowNamedRanges(false); setShowFunctions(false); }} />
          <div className="ml-auto w-96 h-full bg-card border-l border-border overflow-y-auto p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">
                {showDependencies && 'Dependency Graph'}
                {showNamedRanges && 'Named Ranges'}
                {showFunctions && 'Functions'}
              </h3>
              <Button variant="ghost" size="icon" onClick={() => { setShowDependencies(false); setShowNamedRanges(false); setShowFunctions(false); }}>
                <EyeOff className="h-4 w-4" />
              </Button>
            </div>

            {showDependencies && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">{dependencies.nodes.length} formula cells, {dependencies.edges.length} dependencies</p>
                <div className="h-[300px] overflow-auto">
                  <div className="space-y-1">
                    {dependencies.nodes.map(node => (
                      <div key={node.id} className="p-2 rounded border border-border bg-muted/30 text-xs font-mono">
                        <div className="font-medium">{node.label}</div>
                        <div className="text-muted-foreground">{node.formula}</div>
                        <div className="flex gap-2 mt-1">
                          {dependencies.edges.filter(e => e.from === node.id).map(e => (
                            <span key={e.to} className="text-primary hover:underline cursor-pointer" onClick={() => { setActiveCell(parseCoord(e.to.split('!')[1])); setShowDependencies(false); }}>
                              → {e.to}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
            )}

            {showNamedRanges && (
              <div className="space-y-2">
                <div className="flex gap-2 mb-2">
                  <Input placeholder="Range name" className="flex-1" onKeyDown={e => e.key === 'Enter' && createNamedRange(e.currentTarget.value)} />
                  <Button size="sm" onClick={() => { /* createNamedRange */ }}>Create</Button>
                </div>
                <div className="space-y-1">
                  {Object.entries(namedRanges).map(([name, ref]) => (
                    <div key={name} className="flex items-center justify-between p-2 rounded border border-border bg-muted/30 text-xs">
                      <span className="font-medium">{name}</span>
                      <span className="text-muted-foreground font-mono">{ref}</span>
                      <Button variant="ghost" size="icon" className="h-5 w-5"><Trash2 className="h-3 w-3" /></Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {showFunctions && (
              <div className="space-y-2">
                <Input placeholder="Search functions..." className="mb-2" />
                <div className="h-[300px] overflow-auto">
                  <div className="space-y-1">
                    {functions.map(fn => (
                      <div key={fn.name} className="p-2 rounded border border-border bg-muted/30 text-xs" onClick={() => { insertAutocomplete({ label: fn.name, type: 'function', detail: fn.categories.join(', ') }); setShowFunctions(false); }}>
                        <div className="font-medium text-primary">{fn.name}</div>
                        <div className="text-muted-foreground">{fn.categories.join(', ')}</div>
                        <div className="text-[10px] text-muted-foreground">Args: {fn.min_args} - {fn.max_args === -1 ? '∞' : fn.max_args} {fn.variadic ? ' (variadic)' : ''}</div>
                      </div>
                    ))}
                  </div>
                </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
