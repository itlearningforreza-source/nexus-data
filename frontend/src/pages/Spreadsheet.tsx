import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, Loader2, Database, ExternalLink } from 'lucide-react';
import { features } from '@/lib/features';
import { Button, Card, Select, Badge, toast } from '@/components/ui';
import Spreadsheet from '@/components/dataset/Spreadsheet';

export default function SpreadsheetPage() {
  const { id } = useParams<{ id: string }>();
  const [selectedDatasetId, setSelectedDatasetId] = useState(id || '');
  
  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  
  const selectedDataset = datasets?.find(d => d.id === selectedDatasetId);

  useEffect(() => {
    if (id && datasets?.length) {
      setSelectedDatasetId(id);
    } else if (datasets?.length && !selectedDatasetId) {
      setSelectedDatasetId(datasets[0].id);
    }
  }, [id, datasets, selectedDatasetId]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => window.history.back()}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold">Spreadsheet</h1>
            <p className="text-sm text-muted-foreground">Professional spreadsheet with formulas, dependencies & named ranges</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={selectedDatasetId}
            onChange={e => setSelectedDatasetId(e.target.value)}
            className="w-auto min-w-[200px] max-w-xs"
          >
            {datasets?.map(d => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          {selectedDataset && (
            <Badge variant="secondary" className="gap-1">
              <Database className="h-3 w-3" />
              {selectedDataset.row_count.toLocaleString()} rows · {selectedDataset.column_count} cols
            </Badge>
          )}
        </div>
      </div>

      {/* Spreadsheet */}
      <div className="flex-1 overflow-hidden">
        {selectedDatasetId ? (
          <Spreadsheet datasetId={selectedDatasetId} />
        ) : (
          <div className="flex h-full items-center justify-center">
            <Card className="p-8 text-center">
              <Database className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-medium mb-2">No dataset selected</h3>
              <p className="text-muted-foreground mb-4">Select or upload a dataset to start using the spreadsheet</p>
              <Button variant="outline" onClick={() => window.location.href = '/datasets'}>
                Go to Datasets
              </Button>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
