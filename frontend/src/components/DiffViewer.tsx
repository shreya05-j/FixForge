import React, { useMemo, useState, useEffect } from 'react';

// ─── Types ───────────────────────────────────────────────────────────────────
type LineType = 'added' | 'removed' | 'context' | 'file-header' | 'hunk-header' | 'empty';

interface DiffLine {
  type: LineType;
  content: string;
  oldLineNo: number | null;
  newLineNo: number | null;
}

interface ParsedHunk {
  header: string;
  lines: DiffLine[];
}

interface ParsedFile {
  oldPath: string;
  newPath: string;
  hunks: ParsedHunk[];
}

// ─── Parser ──────────────────────────────────────────────────────────────────
function parseDiff(raw: string): ParsedFile[] {
  const files: ParsedFile[] = [];
  const lines = raw.split('\n');

  let currentFile: ParsedFile | null = null;
  let currentHunk: ParsedHunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  for (const line of lines) {
    if (line.startsWith('--- ')) {
      if (currentFile) files.push(currentFile);
      currentFile = {
        oldPath: line.replace(/^--- (a\/)?/, '').trim(),
        newPath: '',
        hunks: [],
      };
      currentHunk = null;
      continue;
    }
    if (line.startsWith('+++ ') && currentFile) {
      currentFile.newPath = line.replace(/^\+\+\+ (b\/)?/, '').trim();
      continue;
    }
    if (line.startsWith('@@ ') && currentFile) {
      // Parse @@ -a,b +c,d @@ ...
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLine = parseInt(match[1], 10);
        newLine = parseInt(match[2], 10);
      }
      currentHunk = { header: line, lines: [] };
      currentFile.hunks.push(currentHunk);
      continue;
    }

    if (!currentFile || !currentHunk) {
      // Lines before any file header – create a synthetic file
      if (!currentFile) {
        currentFile = { oldPath: 'patch', newPath: 'patch', hunks: [] };
        currentHunk = { header: '', lines: [] };
        currentFile.hunks.push(currentHunk);
        oldLine = 1;
        newLine = 1;
      }
    }

    if (!currentHunk) continue;

    if (line.startsWith('+')) {
      currentHunk.lines.push({ type: 'added', content: line.slice(1), oldLineNo: null, newLineNo: newLine++ });
    } else if (line.startsWith('-')) {
      currentHunk.lines.push({ type: 'removed', content: line.slice(1), oldLineNo: oldLine++, newLineNo: null });
    } else {
      // context line (space prefix or blank)
      const content = line.startsWith(' ') ? line.slice(1) : line;
      currentHunk.lines.push({ type: 'context', content, oldLineNo: oldLine++, newLineNo: newLine++ });
    }
  }

  if (currentFile) files.push(currentFile);
  return files.filter(f => f.hunks.some(h => h.lines.length > 0));
}

// ─── Stat computation ────────────────────────────────────────────────────────
function getDiffStats(files: ParsedFile[]) {
  let added = 0, removed = 0, files_count = 0;
  for (const f of files) {
    files_count++;
    for (const h of f.hunks) {
      for (const l of h.lines) {
        if (l.type === 'added') added++;
        if (l.type === 'removed') removed++;
      }
    }
  }
  return { added, removed, files_count };
}

// ─── Line renderer ────────────────────────────────────────────────────────────
const LineNo: React.FC<{ n: number | null }> = ({ n }) => (
  <span className="select-none text-right pr-3 text-[11px] opacity-40 font-mono w-[36px] shrink-0 inline-block">
    {n ?? ''}
  </span>
);

const DiffLineRow: React.FC<{ line: DiffLine; animate?: boolean }> = ({ line, animate }) => {
  const { type, content, oldLineNo, newLineNo } = line;

  const rowStyles: Record<LineType, string> = {
    added:       'bg-[#0d2318] border-l-2 border-[#3fb950] text-[#3fb950]',
    removed:     'bg-[#1a0a0a] border-l-2 border-[#f85149] text-[#f85149]',
    context:     'text-[#8b949e] border-l-2 border-transparent',
    'file-header':'text-[#cdd9e5] bg-[#161b22] border-l-2 border-transparent font-bold',
    'hunk-header':'text-[#79c0ff] bg-[#111827] border-l-2 border-[#1f6feb]',
    empty:       'text-transparent border-l-2 border-transparent',
  };

  const prefix: Record<LineType, string> = {
    added: '+', removed: '-', context: ' ', 'file-header': ' ', 'hunk-header': ' ', empty: ' ',
  };

  return (
    <div
      className={`flex items-stretch min-h-[22px] group hover:brightness-110 transition-all ${rowStyles[type]} ${animate ? 'animate-in fade-in duration-200' : ''}`}
    >
      {/* Old line number */}
      <LineNo n={type === 'added' ? null : oldLineNo} />
      {/* New line number */}
      <LineNo n={type === 'removed' ? null : newLineNo} />
      {/* Prefix gutter */}
      <span className="select-none w-5 shrink-0 text-center text-[12px] opacity-60">
        {prefix[type]}
      </span>
      {/* Content */}
      <span className="font-mono text-[12.5px] leading-[22px] whitespace-pre flex-1 pr-4 overflow-hidden text-ellipsis">
        {content || '\u00a0'}
      </span>
    </div>
  );
};

// ─── Split View ───────────────────────────────────────────────────────────────
const SplitView: React.FC<{ files: ParsedFile[] }> = ({ files }) => {
  return (
    <div className="overflow-auto flex-1">
      {files.map((file, fi) => (
        <div key={fi}>
          <FileHeader file={file} />
          {file.hunks.map((hunk, hi) => {
            // Build side-by-side pairs
            const left: DiffLine[] = [];
            const right: DiffLine[] = [];
            let ri = 0, li = 0;
            const lines = hunk.lines;
            while (ri < lines.length || li < lines.length) {
              const l = lines[li];
              if (!l) break;
              if (l.type === 'removed') {
                left.push(l); li++;
                // Look for corresponding added
                const nextAdded = lines[li];
                if (nextAdded?.type === 'added') {
                  right.push(nextAdded); li++;
                } else {
                  right.push({ type: 'empty', content: '', oldLineNo: null, newLineNo: null });
                }
              } else if (l.type === 'added') {
                right.push(l); li++;
                left.push({ type: 'empty', content: '', oldLineNo: null, newLineNo: null });
              } else {
                left.push(l);
                right.push({ ...l });
                li++;
              }
            }

            return (
              <div key={hi}>
                <HunkHeader header={hunk.header} />
                <div className="grid grid-cols-2 divide-x divide-[#30363d]">
                  <div>{left.map((l, i) => <DiffLineRow key={i} line={l} />)}</div>
                  <div>{right.map((l, i) => <DiffLineRow key={i} line={l} />)}</div>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

const FileHeader: React.FC<{ file: ParsedFile }> = ({ file }) => (
  <div className="flex items-center gap-2 bg-[#161b22] border-y border-[#30363d] px-3 py-2 font-mono text-[12px] text-[#cdd9e5] sticky top-0 z-10">
    <span className="material-symbols-outlined text-[14px] text-[#79c0ff]">description</span>
    <span className="text-[#f0883e]">{file.oldPath}</span>
    {file.oldPath !== file.newPath && (
      <>
        <span className="text-[#8b949e]">→</span>
        <span className="text-[#3fb950]">{file.newPath}</span>
      </>
    )}
  </div>
);

const HunkHeader: React.FC<{ header: string }> = ({ header }) => (
  header ? (
    <div className="flex items-center bg-[#111827] px-3 py-1 font-mono text-[11px] text-[#79c0ff] border-y border-[#1f6feb]/30">
      <span className="material-symbols-outlined text-[12px] mr-2 opacity-60">code</span>
      {header}
    </div>
  ) : null
);

// ─── Stats Bar ────────────────────────────────────────────────────────────────
const StatsBar: React.FC<{ added: number; removed: number; files_count: number }> = ({ added, removed, files_count }) => {
  const total = added + removed;
  const addedPct = total > 0 ? Math.round((added / total) * 100) : 50;
  return (
    <div className="flex items-center gap-4 px-3 py-2 bg-[#0d1117] border-b border-[#30363d] font-mono text-[11px] shrink-0">
      <span className="text-[#8b949e]">
        <span className="material-symbols-outlined text-[12px] align-middle mr-1">insert_drive_file</span>
        {files_count} file{files_count !== 1 ? 's' : ''} changed
      </span>
      <span className="text-[#3fb950] font-bold">+{added}</span>
      <span className="text-[#f85149] font-bold">-{removed}</span>
      <div className="flex flex-1 max-w-[80px] h-[6px] rounded overflow-hidden bg-[#f85149]">
        <div className="bg-[#3fb950] h-full transition-all duration-500" style={{ width: `${addedPct}%` }} />
      </div>
    </div>
  );
};

// ─── Streaming Cursor ─────────────────────────────────────────────────────────
const StreamingCursor: React.FC = () => (
  <span className="inline-block w-2 h-4 bg-[#3fb950] animate-pulse ml-1 align-middle" />
);

// ─── Main Component ───────────────────────────────────────────────────────────
interface DiffViewerProps {
  diff: string | null;
  isStreaming?: boolean;
  viewMode?: 'unified' | 'split';
  onCopy?: () => void;
  onDownload?: () => void;
  onViewModeChange?: (mode: 'unified' | 'split') => void;
}

const DiffViewer: React.FC<DiffViewerProps> = ({
  diff,
  isStreaming = false,
  viewMode = 'unified',
  onCopy,
  onDownload,
  onViewModeChange,
}) => {
  const [revealedLines, setRevealedLines] = useState(0);

  const parsedFiles = useMemo(() => {
    if (!diff) return [];
    return parseDiff(diff);
  }, [diff]);

  const stats = useMemo(() => getDiffStats(parsedFiles), [parsedFiles]);
  const totalLines = useMemo(() => parsedFiles.reduce((a, f) => a + f.hunks.reduce((b, h) => b + h.lines.length, 0), 0), [parsedFiles]);

  // Animate line reveal when diff first appears
  useEffect(() => {
    if (totalLines === 0) { setRevealedLines(0); return; }
    setRevealedLines(0);
    let i = 0;
    const interval = setInterval(() => {
      i += 3;
      setRevealedLines(i);
      if (i >= totalLines) clearInterval(interval);
    }, 30);
    return () => clearInterval(interval);
  }, [diff, totalLines]);

  // ── Toolbar ──────────────────────────────────────────────────────────────
  const toolbar = (
    <div className="bg-[#0d1117] border-b border-[#30363d] px-3 py-2 flex justify-between items-center shrink-0">
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined text-[14px] text-[#8b949e]">difference</span>
        <span className="font-mono text-[12px] text-[#cdd9e5]">
          fixforge_solution.patch
          {isStreaming && <StreamingCursor />}
        </span>
        {/* View mode toggle */}
        <div className="flex bg-[#161b22] border border-[#30363d] rounded overflow-hidden">
          {(['unified', 'split'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => onViewModeChange?.(mode)}
              className={`px-3 py-0.5 text-[11px] font-mono capitalize transition-colors ${
                viewMode === mode
                  ? 'bg-[#1f6feb] text-white'
                  : 'text-[#8b949e] hover:text-[#cdd9e5]'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={onDownload}
          title="Download .patch file"
          className="flex items-center gap-1 px-2 py-1 text-[11px] font-mono text-[#8b949e] hover:text-[#cdd9e5] border border-[#30363d] hover:border-[#8b949e] rounded transition-colors"
        >
          <span className="material-symbols-outlined text-[13px]">download</span>
          .patch
        </button>
        <button
          onClick={onCopy}
          title="Copy diff"
          className="flex items-center gap-1 px-2 py-1 text-[11px] font-mono text-[#8b949e] hover:text-[#cdd9e5] border border-[#30363d] hover:border-[#8b949e] rounded transition-colors"
        >
          <span className="material-symbols-outlined text-[13px]">content_copy</span>
          Copy
        </button>
      </div>
    </div>
  );

  // ── Empty / Loading state ─────────────────────────────────────────────────
  if (!diff && !isStreaming) {
    return (
      <div className="flex-1 flex flex-col bg-[#0d1117] h-full">
        {toolbar}
        <div className="flex-1 flex items-center justify-center flex-col gap-3 text-[#8b949e]">
          <span className="material-symbols-outlined text-[48px] opacity-30 animate-spin" style={{ animationDuration: '3s' }}>sync</span>
          <span className="font-mono text-[12px]">Awaiting patch generation…</span>
        </div>
      </div>
    );
  }

  if (!diff && isStreaming) {
    return (
      <div className="flex-1 flex flex-col bg-[#0d1117] h-full">
        {toolbar}
        <div className="flex-1 flex items-center justify-center flex-col gap-3 text-[#3fb950]">
          <span className="material-symbols-outlined text-[36px] animate-pulse">terminal</span>
          <span className="font-mono text-[12px]">Fixer agent synthesizing patch<StreamingCursor /></span>
        </div>
      </div>
    );
  }

  // ── Unified view ──────────────────────────────────────────────────────────
  const UnifiedView = () => (
    <div className="overflow-auto flex-1">
      {parsedFiles.map((file, fi) => {
        let globalLineIdx = 0;
        return (
          <div key={fi}>
            <FileHeader file={file} />
            {file.hunks.map((hunk, hi) => (
              <div key={hi}>
                <HunkHeader header={hunk.header} />
                {hunk.lines.map((line, li) => {
                  const idx = globalLineIdx++;
                  const visible = idx < revealedLines;
                  return (
                    <DiffLineRow key={li} line={line} animate={visible && totalLines > 0} />
                  );
                })}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="flex-1 flex flex-col bg-[#0d1117] h-full overflow-hidden">
      {toolbar}
      {parsedFiles.length > 0 && (
        <StatsBar added={stats.added} removed={stats.removed} files_count={stats.files_count} />
      )}
      {viewMode === 'unified' ? <UnifiedView /> : <SplitView files={parsedFiles} />}
    </div>
  );
};

export default DiffViewer;
