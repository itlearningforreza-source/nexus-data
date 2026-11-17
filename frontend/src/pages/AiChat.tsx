import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Send, Sparkles, Plus, Loader2 } from 'lucide-react';
import { features } from '@/lib/features';
import type { AIMessage } from '@/lib/types';
import { Button, Card, Select, Textarea, EmptyState, toast } from '@/components/ui';
import { ChartView } from '@/components/charts/chartEngine';

export default function AiChat() {
  const qc = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [datasetId, setDatasetId] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  const { data: conversations } = useQuery({ queryKey: ['ai', 'convs'], queryFn: () => features.ai.conversations() });

  const selectedDataset = datasets?.find((d) => d.id === datasetId) ?? datasets?.[0];

  useEffect(() => {
    if (datasets?.length && !datasetId) {
      setDatasetId(datasets[0].id);
    }
  }, [datasets, datasetId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  function selectDataset(id: string) {
    setDatasetId(id);
    setConversationId(null);
    setMessages([]);
  }

  async function loadConversation(id: string) {
    try {
      const conv = await features.ai.getConversation(id);
      setConversationId(conv.id);
      setMessages(conv.messages ?? []);
    } catch {
      toast('Failed to load conversation', undefined, 'error');
    }
  }

  async function newConversation() {
    try {
      const conv = await features.ai.createConversation();
      setConversationId(conv.id);
      setMessages([]);
      qc.invalidateQueries({ queryKey: ['ai', 'convs'] });
    } catch {
      toast('Failed to create conversation', undefined, 'error');
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || !datasetId || loading) return;

    const userMsg: AIMessage = {
      id: `tmp-${Date.now()}`,
      role: 'user',
      content: text,
      artifacts: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await features.ai.ask(datasetId, text, conversationId ?? '');
      setMessages((prev) => [...prev.filter((m) => m.id !== userMsg.id), res.message]);
      if (res.conversation) {
        setConversationId(res.conversation.id);
      }
      qc.invalidateQueries({ queryKey: ['ai', 'convs'] });
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
      toast('Request failed', 'Please try again.', 'error');
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="flex h-full flex-col lg:flex-row">
      <aside className="flex w-full flex-shrink-0 flex-col border-r border-border bg-card lg:w-60">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">AI Analyst</span>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <Button variant="ghost" size="sm" className="mb-2 w-full justify-start gap-2" onClick={newConversation}>
            <Plus className="h-3.5 w-3.5" />
            New Chat
          </Button>
          <div className="flex flex-col gap-0.5">
            {conversations?.map((c) => (
              <button
                key={c.id}
                onClick={() => loadConversation(c.id)}
                className={`w-full truncate rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                  conversationId === c.id
                    ? 'bg-muted font-medium text-foreground'
                    : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                }`}
              >
                {c.title || 'Untitled'}
              </button>
            ))}
          </div>
          {conversations && conversations.length === 0 && (
            <p className="px-3 py-8 text-center text-[11px] text-muted-foreground">No conversations yet</p>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-2.5">
          <Select
            value={datasetId}
            onChange={(e) => selectDataset(e.target.value)}
            className="w-auto min-w-[180px] max-w-xs"
          >
            {datasets?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          {selectedDataset && (
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {selectedDataset.row_count.toLocaleString()} rows · {selectedDataset.column_count} cols
            </span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {messages.length === 0 && !loading ? (
            <EmptyState
              icon={<Sparkles className="h-8 w-8" />}
              title="Ask anything about your data"
              description="Select a dataset and start a conversation. The AI Analyst can generate insights, statistics, and charts."
            />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-3">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                      msg.role === 'user'
                        ? 'bg-primary text-white'
                        : 'border border-border bg-card text-foreground'
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    {msg.role === 'assistant' && msg.artifacts?.length > 0 && (
                      <div className="mt-3 flex flex-col gap-3">
                        {msg.artifacts.map((a, i) =>
                          a.type === 'chart' ? (
                            <Card key={i} className="overflow-hidden">
                              <div className="border-b border-border px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                                {a.chart_type}
                              </div>
                              <div className="p-2">
                                {a.data ? (
                                  <ChartView data={a.data} chartType={a.chart_type} height={240} />
                                ) : (
                                  <p className="py-6 text-center text-xs text-muted-foreground">
                                    {a.error || 'No data available for this chart.'}
                                  </p>
                                )}
                              </div>
                            </Card>
                          ) : null,
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-2.5 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyzing…
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="border-t border-border px-4 py-3">
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your data…"
              rows={1}
              className="min-h-[40px] resize-none"
            />
            <Button
              size="icon"
              variant="primary"
              onClick={send}
              disabled={!input.trim() || loading || !datasetId}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
