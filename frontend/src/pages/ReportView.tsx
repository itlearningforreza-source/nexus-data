import { useEffect, useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Save, Monitor, Download, FileCode2 } from 'lucide-react';
import { features, blobDownload } from '@/lib/features';
import type { ReportSection, ChartData } from '@/lib/types';
import { formatNumber, cellToString } from '@/lib/format';
import { toast } from '@/components/ui/toast';
import { Button, EmptyState, Input, Modal, Spinner } from '@/components/ui';
import { ChartView } from '@/components/charts/chartEngine';

const nid = () => Math.random().toString(36).slice(2, 10);

function ChartSection({ section }: { section: ReportSection }) {
  const datasetId = section.dataset_id ?? '';
  const chartType = (section.chart_type as string) ?? 'column';
  const config = section.config ?? {};
  const existing = section.data as ChartData | undefined;
  const hasData = !!existing && !!(existing.values || existing.points || existing.series || existing.kpi || existing.gauge || existing.boxes || existing.rows);

  const build = useQuery({
    queryKey: ['report-section-chart', datasetId, chartType, config],
    queryFn: () => features.charts.build(datasetId, chartType, config),
    enabled: !hasData && !!datasetId,
  });

  const data = (hasData ? existing : build.data?.data ?? null) as ChartData | null;

  if (!data) {
    return (
      <div className="rounded-xl border border-border bg-muted p-6 text-center text-xs text-muted-foreground">
        {build.isLoading ? 'Loading chart…' : build.error ? 'Chart unavailable' : 'No chart data'}
      </div>
    );
  }

  let body: ReactNode;
  try {
    body = <ChartView data={data} chartType={chartType} height={280} />;
  } catch {
    body = <div className="text-center text-xs text-muted-foreground">Chart could not be rendered.</div>;
  }
  return <div className="rounded-2xl border border-border bg-card p-4">{body}</div>;
}

function SectionView({ section }: { section: ReportSection }) {
  const content = section.content ?? section.text ?? '';
  switch (section.type) {
    case 'heading':
      return <h2 className="text-lg font-semibold text-foreground">{content || section.title || 'Heading'}</h2>;
    case 'text':
    case 'paragraph':
    case 'markdown':
      return <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{content}</p>;
    case 'table': {
      const cols = section.columns ?? [];
      if (!cols.length) return null;
      const rows = Array.isArray(content) ? (content as unknown[]) : [];
      return (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c} className="border-b border-border bg-muted px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const cells = Array.isArray(r) ? r : Object.values(r as Record<string, unknown>);
                return (
                  <tr key={i} className="border-b border-border last:border-0">
                    {cells.map((c, j) => (
                      <td key={j} className="px-3 py-2 text-[13px]">{cellToString(c)}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }
    case 'kpi': {
      const num = Number(content);
      return (
        <div className="flex flex-col gap-1 rounded-2xl border border-border bg-card p-4">
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{section.title ?? section.column ?? 'KPI'}</div>
          <div className="text-2xl font-bold text-foreground">{Number.isNaN(num) ? content : formatNumber(num)}</div>
          {section.aggregation && <div className="text-[11px] text-muted-foreground">{section.aggregation}</div>}
        </div>
      );
    }
    case 'chart':
      return <ChartSection section={section} />;
    default:
      return null;
  }
}

export default function ReportView() {
  const { id = '' } = useParams();
  const qc = useQueryClient();

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', id],
    queryFn: () => features.reports.get(id),
    enabled: !!id,
  });

  const [name, setName] = useState('');
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [nameSaving, setNameSaving] = useState(false);

  useEffect(() => {
    if (report) {
      setName(report.name);
      setSections(report.sections ?? []);
    }
  }, [report?.id]);

  const commitName = async () => {
    if (!report || name.trim() === report.name) return;
    setNameSaving(true);
    try {
      await features.reports.update(report.id, { name: name.trim() });
      qc.invalidateQueries({ queryKey: ['report', report.id] });
      qc.invalidateQueries({ queryKey: ['reports'] });
    } catch {
      setName(report.name);
      toast('Failed to rename', undefined, 'error');
    } finally {
      setNameSaving(false);
    }
  };

  const handlePreview = async () => {
    if (!report) return;
    setPreviewLoading(true);
    try {
      setPreview(await features.reports.previewHtml(report.id));
    } catch {
      toast('Failed to generate preview', undefined, 'error');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleExport = async (format: 'pdf' | 'html') => {
    if (!report) return;
    try {
      const data = await features.reports.export(report.id, format);
      blobDownload(data.url, `${report.name}.${format}`);
      toast('Export started', undefined, 'success');
    } catch {
      toast('Export failed', undefined, 'error');
    }
  };

  const handleAddText = () => {
    setSections((prev) => [...prev, { id: nid(), type: 'text', content: 'Hello' }]);
  };

  const handleSave = async () => {
    if (!report) return;
    setSaving(true);
    try {
      await features.reports.update(report.id, { sections });
      toast('Report saved', undefined, 'success');
      qc.invalidateQueries({ queryKey: ['report', report.id] });
      qc.invalidateQueries({ queryKey: ['reports'] });
    } catch {
      toast('Failed to save report', undefined, 'error');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-full items-center justify-center p-6">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-6">
        <EmptyState title="Report not found" description="This report may have been deleted." />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-md">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={commitName}
            disabled={nameSaving}
            className="mb-1.5 h-9 border-transparent bg-transparent px-0 text-2xl font-bold tracking-tight shadow-none focus:border-primary/50 focus:bg-card focus:px-3"
            placeholder="Untitled report"
          />
          <p className="text-sm text-muted-foreground">{report.description || 'No description'}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" leftIcon={<Monitor className="h-3.5 w-3.5" />} onClick={handlePreview} loading={previewLoading}>
            Preview HTML
          </Button>
          <Button variant="outline" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={() => handleExport('pdf')}>
            Export PDF
          </Button>
          <Button variant="outline" leftIcon={<FileCode2 className="h-3.5 w-3.5" />} onClick={() => handleExport('html')}>
            Export HTML
          </Button>
        </div>
      </div>

      <div className="mb-6 flex items-center justify-between gap-3 border-b border-border pb-4">
        <div className="text-xs text-muted-foreground">{sections.length} sections</div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={handleAddText}>
            Add text section
          </Button>
          <Button size="sm" leftIcon={<Save className="h-3.5 w-3.5" />} onClick={handleSave} loading={saving}>
            Save
          </Button>
        </div>
      </div>

      {sections.length === 0 ? (
        <EmptyState
          icon={<FileCode2 className="h-8 w-8" />}
          title="No sections yet"
          description="Add a text section to start building your report."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {sections.map((s, i) => (
            <SectionView key={i} section={s} />
          ))}
        </div>
      )}

      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={report.name}
        description="HTML preview"
        size="xl"
      >
        {preview && (
          <iframe
            srcDoc={preview}
            title="Report preview"
            className="h-[70vh] w-full rounded-xl border border-border bg-white"
          />
        )}
      </Modal>
    </div>
  );
}