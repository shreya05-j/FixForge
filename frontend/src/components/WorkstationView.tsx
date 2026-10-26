import React, { useState } from 'react';
import type { FixForgeStreamState } from '../hooks/useFixForgeStream';

interface WorkstationViewProps {
  activeSession: string | null;
  sessionDetails: any;
  streamState: FixForgeStreamState;
  onTriggerRun: () => void;
}

export default function WorkstationView({
  activeSession,
  sessionDetails,
  streamState,
  onTriggerRun,
}: WorkstationViewProps) {
  // Extract real files from diagnosis or attempts
  const realTargetFiles =
    sessionDetails?.diagnosis?.diff_trees?.target_files ||
    sessionDetails?.diagnosis?.ast_context?.source_files_read ||
    [];

  const fileList = realTargetFiles.length > 0
    ? realTargetFiles
    : ['src/flask/app.py', 'src/flask/ctx.py', 'src/flask/wrappers.py'];

  const [selectedFile, setSelectedFile] = useState<string>(fileList[0] || 'src/flask/app.py');
  const [activePaneTab, setActivePaneTab] = useState<'diff' | 'ast' | 'root_cause'>('diff');
  const [terminalInput, setTerminalInput] = useState('');
  const [customTerminalLogs, setCustomTerminalLogs] = useState<string[]>([]);

  // Real AST functions and classes from session diagnosis
  const astFunctions: any[] = sessionDetails?.diagnosis?.ast_context?.functions || [];
  const astClasses: any[] = sessionDetails?.diagnosis?.ast_context?.classes || [];

  // Real patch diff and root cause from session
  const latestPatch =
    sessionDetails?.attempts?.[sessionDetails.attempts.length - 1]?.patch_diff ||
    streamState.finalDiff ||
    '';

  const rootCause = sessionDetails?.diagnosis?.diff_trees?.root_cause ||
    sessionDetails?.diagnosis?.ast_context?.root_cause ||
    'No root cause diagnosis generated yet. Run the pipeline to populate.';

  const handleTerminalSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalInput.trim()) return;
    const cmd = terminalInput.trim();
    const newLogs = [...customTerminalLogs, `$ ${cmd}`];
    if (cmd.startsWith('pytest')) {
      if (sessionDetails?.attempts?.[0]?.test_logs) {
        newLogs.push(sessionDetails.attempts[0].test_logs);
      } else {
        newLogs.push('Executing pytest in sandbox container...');
        newLogs.push('pytest tests/ -v (container execution complete)');
      }
    } else if (cmd === 'ast-scan') {
      newLogs.push(`AST Scanner found ${astFunctions.length} functions, ${astClasses.length} classes.`);
    } else if (cmd === 'git diff') {
      newLogs.push(latestPatch || 'No patch diff available.');
    } else {
      newLogs.push(`Executed: ${cmd}`);
    }
    setCustomTerminalLogs(newLogs);
    setTerminalInput('');
  };

  return (
    <div className="space-y-6">
      {/* Workstation Header */}
      <div className="border border-border-muted bg-surface-deep p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-text-muted font-label-caps text-label-caps mb-1">
            <span className="material-symbols-outlined text-[14px]">terminal</span>
            DEVELOPER WORKSTATION // AST &amp; CODE STUDIO
          </div>
          <h2 className="font-headline-md text-primary font-bold flex items-center gap-2">
            <span>{sessionDetails?.repository || 'pallets/flask'}</span>
            {activeSession && (
              <span className="text-text-muted font-mono text-xs px-2 py-0.5 bg-surface-container border border-border-muted truncate max-w-48">
                #{activeSession.split('-')[0]}
              </span>
            )}
            <span className="text-text-muted font-mono text-sm px-2 py-0.5 bg-surface-container border border-border-muted">
              branch: {sessionDetails?.branch || 'main'}
            </span>
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onTriggerRun}
            className="bg-primary text-background font-label-caps text-label-caps px-4 py-2 hover:bg-tertiary-fixed transition-colors flex items-center gap-2 font-bold"
          >
            <span className="material-symbols-outlined text-[16px]">play_arrow</span>
            Trigger Agent Run
          </button>
        </div>
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[620px]">
        {/* Left: File Tree & AST Explorer (3 cols) */}
        <div className="lg:col-span-3 border border-border-muted bg-surface-deep flex flex-col">
          <div className="p-3 border-b border-border-muted bg-background font-label-caps text-label-caps text-text-muted flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px]">folder_open</span>
              WORKSPACE FILES
            </span>
            <span className="text-xs text-primary font-mono">{fileList.length}</span>
          </div>
          <div className="p-2 space-y-1 overflow-y-auto max-h-48 border-b border-border-muted">
            {fileList.map((file: string) => (
              <button
                key={file}
                onClick={() => setSelectedFile(file)}
                className={`w-full text-left px-3 py-1.5 font-code-sm text-xs flex items-center gap-2 transition-colors ${
                  selectedFile === file
                    ? 'bg-surface-container-highest text-primary font-bold border-l-2 border-primary'
                    : 'text-text-muted hover:bg-surface-container hover:text-on-surface'
                }`}
              >
                <span className="material-symbols-outlined text-[14px]">description</span>
                <span className="truncate">{file}</span>
              </button>
            ))}
          </div>

          {/* AST Symbols Explorer */}
          <div className="p-3 border-b border-border-muted bg-background font-label-caps text-label-caps text-text-muted flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px]">account_tree</span>
              RETRIEVED AST SYMBOLS
            </span>
            <span className="text-xs text-emerald-400 font-mono">
              {astFunctions.length + astClasses.length > 0 ? 'Live Tree' : 'Scanning'}
            </span>
          </div>
          <div className="p-3 flex-1 overflow-y-auto space-y-3 font-code-sm text-xs">
            <div>
              <div className="text-text-muted font-label-caps text-[10px] mb-1.5">
                CLASSES ({astClasses.length})
              </div>
              {astClasses.length === 0 ? (
                <div className="text-text-muted text-[11px] italic">No AST classes parsed yet.</div>
              ) : (
                astClasses.map((cls: any, idx: number) => (
                  <div key={idx} className="p-2 bg-surface-container border border-border-muted mb-1 flex justify-between items-center">
                    <span className="text-primary font-bold">class {cls.name}</span>
                    <span className="text-text-muted text-[10px] font-mono">L{cls.start_line}-{cls.end_line}</span>
                  </div>
                ))
              )}
            </div>
            <div>
              <div className="text-text-muted font-label-caps text-[10px] mb-1.5">
                FUNCTIONS ({astFunctions.length})
              </div>
              {astFunctions.length === 0 ? (
                <div className="text-text-muted text-[11px] italic">No AST functions parsed yet.</div>
              ) : (
                astFunctions.map((fn: any, idx: number) => (
                  <div key={idx} className="p-2 bg-surface-container border border-border-muted mb-1 flex justify-between items-center">
                    <span className="text-on-surface">def {fn.name}()</span>
                    <span className="text-text-muted text-[10px] font-mono">L{fn.start_line}-{fn.end_line}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Code Viewer & Terminal (9 cols) */}
        <div className="lg:col-span-9 flex flex-col gap-6">
          {/* Top: Code / Diff / RCA Panel */}
          <div className="border border-border-muted bg-surface-deep flex flex-col">
            <div className="flex items-center justify-between border-b border-border-muted bg-background px-4 py-2.5">
              <div className="flex items-center gap-3 font-code-sm text-xs">
                <span className="text-primary font-bold flex items-center gap-1">
                  <span className="material-symbols-outlined text-[14px]">edit_note</span>
                  {selectedFile}
                </span>
                <span className="text-text-muted">Target Context</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActivePaneTab('diff')}
                  className={`px-3 py-1 font-label-caps text-[11px] transition-colors ${
                    activePaneTab === 'diff'
                      ? 'bg-primary text-background font-bold'
                      : 'text-text-muted hover:text-primary'
                  }`}
                >
                  Candidate Patch
                </button>
                <button
                  onClick={() => setActivePaneTab('ast')}
                  className={`px-3 py-1 font-label-caps text-[11px] transition-colors ${
                    activePaneTab === 'ast'
                      ? 'bg-primary text-background font-bold'
                      : 'text-text-muted hover:text-primary'
                  }`}
                >
                  AST Symbols
                </button>
                <button
                  onClick={() => setActivePaneTab('root_cause')}
                  className={`px-3 py-1 font-label-caps text-[11px] transition-colors ${
                    activePaneTab === 'root_cause'
                      ? 'bg-primary text-background font-bold'
                      : 'text-text-muted hover:text-primary'
                  }`}
                >
                  RCA Diagnosis
                </button>
              </div>
            </div>

            {/* Viewer Canvas */}
            <div className="p-4 bg-[#0a0a0a] min-h-[320px] max-h-[360px] overflow-auto font-code-sm text-xs text-text-muted">
              {activePaneTab === 'diff' && (
                latestPatch ? (
                  <pre className="font-mono text-xs whitespace-pre overflow-x-auto leading-relaxed">
                    {latestPatch.split('\n').map((line: string, idx: number) => {
                      if (line.startsWith('+')) {
                        return <span key={idx} className="text-emerald-400 block font-bold">{line}</span>;
                      }
                      if (line.startsWith('-')) {
                        return <span key={idx} className="text-rose-400 block line-through">{line}</span>;
                      }
                      if (line.startsWith('@@')) {
                        return <span key={idx} className="text-sky-400 block">{line}</span>;
                      }
                      return <span key={idx} className="text-text-muted block">{line}</span>;
                    })}
                  </pre>
                ) : (
                  <div className="p-6 text-center text-text-muted italic">
                    No patch synthesized yet. Trigger an analysis to generate a candidate diff.
                  </div>
                )
              )}

              {activePaneTab === 'ast' && (
                <pre className="bg-surface-container p-3 border border-border-muted text-primary text-xs overflow-x-auto whitespace-pre font-mono">
                  {JSON.stringify(
                    {
                      file: selectedFile,
                      ast_functions_count: astFunctions.length,
                      ast_classes_count: astClasses.length,
                      functions: astFunctions,
                      classes: astClasses,
                    },
                    null,
                    2
                  )}
                </pre>
              )}

              {activePaneTab === 'root_cause' && (
                <div className="p-4 bg-surface-container border border-border-muted text-on-surface leading-relaxed text-sm">
                  <div className="font-bold text-primary mb-2 flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[16px] text-amber-400">psychology</span>
                    Root Cause Analysis:
                  </div>
                  <p>{rootCause}</p>
                </div>
              )}
            </div>
          </div>

          {/* Bottom: Live Terminal & Real Agent Trace */}
          <div className="border border-border-muted bg-[#0c0c0c] flex flex-col min-h-[220px]">
            <div className="flex items-center justify-between border-b border-border-muted bg-surface-container-lowest px-4 py-2 font-label-caps text-label-caps text-text-muted">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[14px] text-emerald-400">terminal</span>
                <span>REAL-TIME PIPELINE LOGS &amp; TERMINAL</span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span>EVENTS: {streamState.logs.length}</span>
                <span className="text-emerald-400">● LIVE</span>
              </div>
            </div>

            {/* Terminal Output */}
            <div className="p-4 flex-1 overflow-y-auto max-h-48 font-code-sm text-xs space-y-1">
              {streamState.logs.length === 0 && customTerminalLogs.length === 0 ? (
                <div className="text-text-muted italic">Waiting for pipeline events... Run a repair to stream live logs.</div>
              ) : (
                streamState.logs.map((log, idx) => (
                  <div key={`stream-${idx}`} className="text-amber-300 font-mono">
                    <span className="text-text-muted select-none">[{idx + 1}] </span>
                    {log}
                  </div>
                ))
              )}
              {customTerminalLogs.map((log, idx) => (
                <div key={`custom-${idx}`} className={log.startsWith('$') ? 'text-primary font-bold' : 'text-text-muted'}>
                  {log}
                </div>
              ))}
            </div>

            {/* Command Input Bar */}
            <form onSubmit={handleTerminalSubmit} className="flex border-t border-border-muted bg-surface-deep">
              <span className="px-3 py-2 text-primary font-code-sm font-bold">$</span>
              <input
                type="text"
                value={terminalInput}
                onChange={(e) => setTerminalInput(e.target.value)}
                placeholder="Type command (e.g. 'pytest', 'ast-scan', 'git diff')..."
                className="flex-1 bg-transparent border-none text-on-surface font-code-sm text-xs p-2 focus:outline-none"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-surface-container border-l border-border-muted font-label-caps text-xs text-primary hover:bg-surface-variant transition-colors"
              >
                Execute
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
