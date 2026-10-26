import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { API_BASE_URL } from '../config/env';

interface ChromaDBViewProps {
  onInjectHeuristic?: (heuristic: string) => void;
}

interface MemoryItem {
  id: string;
  repo: string;
  file: string;
  severity: string;
  similarity: number;
  description: string;
  diff: string;
}

interface MemoryStats {
  status: string;
  persist_dir: string;
  history_count: number;
  code_chunks_count: number;
  embedding_dimensions: number;
  collections: string[];
  distance_metric: string;
}

export default function ChromaDBView({ onInjectHeuristic }: ChromaDBViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [similarityThreshold, setSimilarityThreshold] = useState(60);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newFixRepo, setNewFixRepo] = useState('pallets/flask');
  const [newFixDesc, setNewFixDesc] = useState('');
  const [newFixPatch, setNewFixPatch] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [stats, setStats] = useState<MemoryStats>({
    status: 'connecting',
    persist_dir: './chroma_data',
    history_count: 0,
    code_chunks_count: 0,
    embedding_dimensions: 384,
    collections: ['historical_fix_kb', 'repo_code_chunks'],
    distance_metric: 'Cosine Similarity',
  });

  const [memoryEntries, setMemoryEntries] = useState<MemoryItem[]>([]);

  // Fetch real ChromaDB statistics
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/memory/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      // Fallback display if server restarting
    }
  }, []);

  // Fetch real fixes from ChromaDB
  const fetchFixes = useCallback(async (query: string) => {
    setIsLoading(true);
    try {
      const url = query.trim()
        ? `${API_BASE_URL}/api/memory/fixes?query=${encodeURIComponent(query.trim())}`
        : `${API_BASE_URL}/api/memory/fixes`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setMemoryEntries(data);
      }
    } catch {
      toast.error('Failed to query ChromaDB vector store');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchFixes('');
  }, [fetchStats, fetchFixes]);

  // Debounced search on query change
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchFixes(searchQuery);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery, fetchFixes]);

  const filteredEntries = memoryEntries.filter((item) => {
    return item.similarity * 100 >= similarityThreshold;
  });

  const handleAddFix = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFixDesc.trim() || !newFixPatch.trim()) {
      toast.error('Please enter both problem description and ground truth patch.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/memory/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo: newFixRepo,
          description: newFixDesc,
          diff: newFixPatch,
          file: 'src/flask/wrappers.py',
          severity: 'Medium',
        }),
      });
      if (!res.ok) throw new Error('API failed');
      toast.success('Vector embedding generated and stored in ChromaDB!');
      setIsAddModalOpen(false);
      setNewFixDesc('');
      setNewFixPatch('');
      fetchStats();
      fetchFixes('');
    } catch {
      toast.error('Failed to index new fix into ChromaDB');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border border-border-muted bg-surface-deep p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-text-muted font-label-caps text-label-caps mb-1">
            <span className="material-symbols-outlined text-[14px]">database</span>
            CHROMADB VECTOR MEMORY // REAL-TIME SEMANTIC STORE
          </div>
          <h2 className="font-headline-md text-primary font-bold">
            Historical Bug Fix Knowledge Base ({stats.history_count} Indexed)
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              fetchStats();
              fetchFixes(searchQuery);
              toast.info('Refreshed ChromaDB memory from server');
            }}
            className="border border-border-muted text-text-muted hover:text-primary font-label-caps text-xs px-3 py-2 transition-colors flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[14px]">refresh</span>
            Refresh
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="bg-primary text-background font-label-caps text-label-caps px-4 py-2 hover:bg-tertiary-fixed transition-colors flex items-center gap-2 font-bold"
          >
            <span className="material-symbols-outlined text-[16px]">add</span>
            Index New Fix
          </button>
        </div>
      </div>

      {/* Real-time Vector Store Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="border border-border-muted bg-surface-deep p-4">
          <div className="font-label-caps text-label-caps text-text-muted mb-1">PERSISTENCE STORAGE</div>
          <div className="text-primary font-mono text-sm font-bold truncate" title={stats.persist_dir}>
            {stats.persist_dir}
          </div>
          <div className="text-emerald-400 text-[10px] mt-1 font-mono">● {stats.status.toUpperCase()}</div>
        </div>

        <div className="border border-border-muted bg-surface-deep p-4">
          <div className="font-label-caps text-label-caps text-text-muted mb-1">INDEXED EMBEDDINGS</div>
          <div className="text-primary font-bold text-sm">
            historical_fix_kb <span className="text-emerald-400 text-xs font-mono">({stats.history_count})</span>
          </div>
          <div className="text-text-muted text-[10px] mt-1 font-mono">code_chunks ({stats.code_chunks_count})</div>
        </div>

        <div className="border border-border-muted bg-surface-deep p-4">
          <div className="font-label-caps text-label-caps text-text-muted mb-1">EMBEDDING SPACE</div>
          <div className="text-primary font-bold text-sm">
            {stats.embedding_dimensions}-dimensional
          </div>
          <div className="text-text-muted text-[10px] mt-1 font-mono">all-MiniLM-L6-v2</div>
        </div>

        <div className="border border-border-muted bg-surface-deep p-4">
          <div className="font-label-caps text-label-caps text-text-muted mb-1">DISTANCE METRIC</div>
          <div className="text-primary font-bold text-sm">
            {stats.distance_metric}
          </div>
          <div className="text-text-muted text-[10px] mt-1 font-mono">Live Cosine Distance</div>
        </div>
      </div>

      {/* Real-time Search & Similarity Filter */}
      <div className="border border-border-muted bg-surface-deep p-4 flex flex-col md:flex-row items-center gap-4">
        <div className="relative flex-1 w-full">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-[18px]">
            search
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Type query to semantically match against ChromaDB (e.g. 'cookie parse TypeError', 'KeyError in fixture')..."
            className="w-full bg-[#0c0c0c] border border-border-muted text-on-surface font-code-sm text-xs pl-9 pr-3 py-2.5 focus:border-primary focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-3 w-full md:w-auto font-code-sm text-xs text-text-muted">
          <span className="whitespace-nowrap">Similarity Threshold ≥ {similarityThreshold}%</span>
          <input
            type="range"
            min="10"
            max="95"
            step="5"
            value={similarityThreshold}
            onChange={(e) => setSimilarityThreshold(Number(e.target.value))}
            className="cursor-pointer accent-primary"
          />
        </div>
      </div>

      {/* List of Real Matched Memory Items */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="border border-border-muted bg-surface-deep p-8 text-center text-primary font-code-sm text-xs flex justify-center items-center gap-2">
            <span className="animate-spin material-symbols-outlined text-[16px]">progress_activity</span>
            Querying ChromaDB vector embeddings...
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="border border-border-muted bg-surface-deep p-8 text-center text-text-muted font-code-sm text-xs">
            {searchQuery
              ? `No historical fixes matched "${searchQuery}" with threshold ≥ ${similarityThreshold}%. Try lowering the slider.`
              : 'No historical fixes in memory. Use "Index New Fix" to add one.'}
          </div>
        ) : (
          filteredEntries.map((item, idx) => (
            <div key={`${item.id}-${idx}`} className="border border-border-muted bg-surface-deep p-5 space-y-3">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-border-muted/50 pb-3">
                <div className="flex items-center gap-3 font-code-sm text-xs">
                  <span className="text-primary font-bold text-sm">{item.id}</span>
                  <span className="text-text-muted font-mono">{item.repo}</span>
                  <span className="text-xs px-2 py-0.5 bg-surface-container border border-border-muted text-emerald-400">
                    {item.file}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-primary border border-primary px-2.5 py-0.5 text-xs font-mono font-bold">
                    {(item.similarity * 100).toFixed(0)}% Cosine Match
                  </span>
                  <span className="text-text-muted text-xs font-mono uppercase">{item.severity}</span>
                </div>
              </div>

              <p className="font-body-sm text-xs text-on-surface leading-relaxed">
                {item.description}
              </p>

              {item.diff ? (
                <div className="bg-[#0a0a0a] border border-border-muted p-3 font-code-sm text-xs overflow-x-auto whitespace-pre max-h-48">
                  {item.diff.split('\n').map((line, lIdx) => {
                    if (line.startsWith('+')) {
                      return <span key={lIdx} className="text-emerald-400 block font-bold">{line}</span>;
                    }
                    if (line.startsWith('-')) {
                      return <span key={lIdx} className="text-rose-400 block line-through">{line}</span>;
                    }
                    return <span key={lIdx} className="text-text-muted block">{line}</span>;
                  })}
                </div>
              ) : (
                <div className="bg-[#0a0a0a] border border-border-muted p-2 font-code-sm text-[11px] text-text-muted italic">
                  No patch diff recorded for this diagnostic record.
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => {
                    toast.success(`Injected historical heuristic into Fixer prompt!`);
                    if (onInjectHeuristic) onInjectHeuristic(item.description);
                  }}
                  className="px-3 py-1.5 border border-border-muted text-primary font-label-caps text-[11px] hover:border-primary transition-colors flex items-center gap-1.5"
                >
                  <span className="material-symbols-outlined text-[14px]">psychology</span>
                  Inject Heuristic to Prompt
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Index New Fix Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-deep border border-border-muted w-full max-w-lg p-6 space-y-4">
            <h3 className="font-headline-md text-primary font-bold flex items-center gap-2">
              <span className="material-symbols-outlined">add_circle</span>
              Index Ground Truth Fix into ChromaDB
            </h3>
            <form onSubmit={handleAddFix} className="space-y-4 font-code-sm text-xs">
              <div>
                <label className="block text-text-muted font-label-caps mb-1">TARGET REPOSITORY</label>
                <input
                  type="text"
                  value={newFixRepo}
                  onChange={(e) => setNewFixRepo(e.target.value)}
                  className="w-full bg-[#0c0c0c] border border-border-muted text-on-surface p-2 focus:border-primary focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-text-muted font-label-caps mb-1">ISSUE / BUG DESCRIPTION</label>
                <textarea
                  rows={3}
                  value={newFixDesc}
                  onChange={(e) => setNewFixDesc(e.target.value)}
                  placeholder="e.g. TypeError in parse_cookie due to non-ascii bytes..."
                  className="w-full bg-[#0c0c0c] border border-border-muted text-on-surface p-2 focus:border-primary focus:outline-none resize-none"
                />
              </div>
              <div>
                <label className="block text-text-muted font-label-caps mb-1">GROUND TRUTH PATCH DIFF</label>
                <textarea
                  rows={4}
                  value={newFixPatch}
                  onChange={(e) => setNewFixPatch(e.target.value)}
                  placeholder={`--- a/wrappers.py\n+++ b/wrappers.py\n@@ -10,1 +10,2 @@\n+    if not header: return {}`}
                  className="w-full bg-[#0c0c0c] border border-border-muted text-on-surface p-2 focus:border-primary focus:outline-none resize-none font-mono"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 text-text-muted hover:text-primary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-primary text-background font-bold hover:bg-tertiary-fixed transition-colors"
                >
                  Embed &amp; Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
