import React, { useState, useEffect, useRef } from 'react';
import { useFixForgeStream } from './hooks/useFixForgeStream';
import { Toaster, toast } from 'sonner';
import { mockScenarios } from './data/mockScenarios';
import DiffViewer from './components/DiffViewer';
import WorkstationView from './components/WorkstationView';
import TelemetryView from './components/TelemetryView';
import ChromaDBView from './components/ChromaDBView';
import { API_BASE_URL } from './config/env';
import './index.css';

const pipelineOrder = [
  'planner',
  'retriever',
  'diagnoser',
  'fixer',
  'verifier',
  'confidence_engine',
  'reporter'
];

type SidebarTab = 'executions' | 'workstation' | 'telemetry' | 'chromadb';

export default function App() {
  const [sessionId, setSessionId] = useState<string>('');
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'diff' | 'diagnosis' | 'logs' | 'history'>('diff');
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('executions');
  const [sessionDetails, setSessionDetails] = useState<any>(null);

  // Interactive States
  const [isNewRunModalOpen, setIsNewRunModalOpen] = useState(false);
  const [newRunUrl, setNewRunUrl] = useState('');
  
  const [activeAgentNode, setActiveAgentNode] = useState<string | null>(null);
  const [diffViewMode, setDiffViewMode] = useState<'unified' | 'split'>('unified');
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [activeAttemptTab, setActiveAttemptTab] = useState(0);
  
  const [isRetryModalOpen, setIsRetryModalOpen] = useState(false);
  const [retryGuidance, setRetryGuidance] = useState('');
  
  const [isHistoricalFixDrawerOpen, setIsHistoricalFixDrawerOpen] = useState(false);

  interface HealthInfo {
    overall_mode: 'LIVE' | 'PARTIAL' | 'FALLBACK';
    llm_mode: 'live' | 'fallback';
    docker_mode: 'live' | 'unavailable';
    sandbox_image: 'present' | 'missing';
    github_mode: 'dry_run' | 'live';
    details?: {
      llm?: { model?: string };
    };
  }
  const [health, setHealth] = useState<HealthInfo | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/health`)
      .then(r => r.json())
      .then(data => setHealth(data))
      .catch(() => setHealth({
        overall_mode: 'FALLBACK',
        llm_mode: 'fallback',
        docker_mode: 'unavailable',
        sandbox_image: 'missing',
        github_mode: 'dry_run'
      }));
  }, []);

  const [liveSessions, setLiveSessions] = useState<any[]>([]);

  const fetchLiveSessions = () => {
    fetch(`${API_BASE_URL}/api/sessions`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (Array.isArray(data)) setLiveSessions(data);
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchLiveSessions();
  }, []);

  useEffect(() => {
    if (!activeSession) {
      setSessionDetails(null);
      return;
    }
    if (mockScenarios[activeSession]) {
      setSessionDetails(null);
      return;
    }
    fetch(`${API_BASE_URL}/api/sessions/${activeSession}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setSessionDetails(data);
      })
      .catch(() => {});
  }, [activeSession]);

  const streamState = useFixForgeStream(activeSession || '');
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Derive scenario data for the UI
  const currentScenario = streamState.isDemo && activeSession ? mockScenarios[activeSession] : null;

  // Auto-scroll logic
  useEffect(() => {
    if (activeTab === 'logs' && isAutoScrollEnabled) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [streamState.logs, activeTab, isAutoScrollEnabled]);

  // Error toast observer
  useEffect(() => {
    if (streamState.error) {
      toast.error(`Stream Error: ${streamState.error}`);
    }
  }, [streamState.error]);

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    if (sessionId.trim()) {
      setActiveSession(sessionId.trim());
      toast.success(`Connected to session ${sessionId}`);
    }
  };

  const handleNewRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRunUrl) return;
    try {
      toast.info("Triggering new analysis...");
      const res = await fetch(`${API_BASE_URL}/api/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newRunUrl })
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        const errorDetail =
          errorData?.detail ||
          (Array.isArray(errorData?.detail) ? errorData.detail[0]?.msg : null) ||
          'Failed to start analysis.';
        toast.error(`Analysis Request Error: ${errorDetail}`);
        return;
      }
      const data = await res.json();
      setSessionId(data.session_id);
      setActiveSession(data.session_id);
      setIsNewRunModalOpen(false);
      setNewRunUrl('');
      fetchLiveSessions();
      toast.success("Live analysis started!");
    } catch (err: any) {
      toast.error(
        err?.message === 'Failed to fetch'
          ? "Cannot reach backend. Please ensure the backend is running on port 8000."
          : (err?.message || "Error starting analysis")
      );
    }
  };

  const handleApprove = async () => {
    if (!activeSession) return toast.error("No active session.");
    if (streamState.isDemo) {
      return toast.success("DEMO MODE: PR Successfully Approved & Pushed to GitHub!", { id: 'approve' });
    }
    try {
      toast.loading("Approving PR...", { id: 'approve' });
      const res = await fetch(`${API_BASE_URL}/api/sessions/${activeSession}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve_pr' })
      });
      if (!res.ok) throw new Error('API failed');
      toast.success("PR Successfully Approved & Pushed to GitHub!", { id: 'approve' });
    } catch (err) {
      toast.error("Failed to approve PR (backend disconnected).", { id: 'approve' });
    }
  };

  const handleRequestRetry = async () => {
    if (!activeSession) return;
    if (streamState.isDemo) {
      setIsRetryModalOpen(false);
      return toast.success("DEMO MODE: Retry requested successfully!", { id: 'retry' });
    }
    try {
      toast.loading("Requesting retry loop...", { id: 'retry' });
      const res = await fetch(`${API_BASE_URL}/api/sessions/${activeSession}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'request_retry', guidance: retryGuidance })
      });
      if (!res.ok) throw new Error('API failed');
      setIsRetryModalOpen(false);
      setRetryGuidance('');
      toast.success("Retry requested successfully!", { id: 'retry' });
    } catch (err) {
      toast.error("Failed to request retry.", { id: 'retry' });
      setIsRetryModalOpen(false);
    }
  };

  const handleDismiss = () => {
    setActiveSession(null);
    setSessionId('');
    toast.info("Session dismissed and archived.");
  };

  const copyDiff = () => {
    if (streamState.finalDiff) {
      navigator.clipboard.writeText(streamState.finalDiff);
      toast.success("Diff copied to clipboard!");
    } else {
      toast.error("No diff available to copy.");
    }
  };

  const downloadPatch = () => {
    if (streamState.finalDiff) {
      const blob = new Blob([streamState.finalDiff], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'fixforge_solution.patch';
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Patch downloaded!");
    }
  };

  const copyLogs = () => {
    if (streamState.logs.length) {
      navigator.clipboard.writeText(streamState.logs.join('\n'));
      toast.success("Logs copied to clipboard!");
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-on-surface font-body-md text-body-md">
      <Toaster position="bottom-right" theme="dark" />

      {/* TopNavBar */}
      <header className="bg-background dark:bg-background docked full-width top-0 border-b border-border-muted flex justify-between items-center w-full px-margin-desktop h-16 shrink-0 z-50">
        <div className="flex items-center gap-4">
          <div className="font-headline-md text-headline-md font-bold text-primary dark:text-primary tracking-tight">
            FixForge AI
          </div>
          {/* System Mode Badge */}
          {streamState.isDemo ? (
            <span
              id="mode-badge"
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/50 tracking-widest uppercase"
              title="This session is running in offline simulated demo mode"
            >
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
              SIMULATED
            </span>
          ) : health ? (
            <span
              id="mode-badge"
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-black tracking-widest uppercase border ${
                health.overall_mode === 'LIVE'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
                  : health.overall_mode === 'PARTIAL'
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/50'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/50'
              }`}
              title={`LLM: ${health.llm_mode} | Docker: ${health.docker_mode} | Sandbox Image: ${health.sandbox_image}`}
            >
              <span className={`w-2 h-2 rounded-full ${
                health.overall_mode === 'LIVE' ? 'bg-emerald-400' : health.overall_mode === 'PARTIAL' ? 'bg-amber-400' : 'bg-rose-400'
              }`}></span>
              {health.overall_mode}
            </span>
          ) : (
            <span id="mode-badge" className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-black tracking-widest uppercase border bg-surface-container text-text-muted border-border-muted">
              CHECKING...
            </span>
          )}
          
          <select 
            className="hidden lg:block bg-surface-deep border border-border-muted text-on-surface font-body-sm text-body-sm px-3 py-1.5 focus:border-primary focus:outline-none transition-colors rounded-none"
            value={activeSession || ''}
            onChange={(e) => {
              if (e.target.value) {
                setActiveSession(e.target.value);
                setSessionId(e.target.value);
                toast.info(`Loaded scenario: ${e.target.value}`);
              }
            }}
          >
            <option value="">Select Session / Demo...</option>
            {liveSessions.length > 0 && (
              <optgroup label="Live Backend Sessions">
                {liveSessions.map((s) => {
                  const repoLabel = s.repository?.replace('https://github.com/', '') || s.repository || 'Session';
                  return (
                    <option key={s.id} value={s.id}>
                      {repoLabel} (#{s.id.slice(0, 8)}) — {s.status.toUpperCase()}
                    </option>
                  );
                })}
              </optgroup>
            )}
            <optgroup label="Demo Scenarios (Offline)">
              {Object.values(mockScenarios).map(sc => (
                <option key={sc.id} value={sc.id}>{sc.title}</option>
              ))}
            </optgroup>
          </select>

          <form onSubmit={handleConnect} className="relative w-64 hidden xl:block">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-[18px]">search</span>
            <input 
              className="w-full bg-surface-deep border border-border-muted text-on-surface font-body-sm text-body-sm pl-9 pr-3 py-1.5 focus:border-primary focus:outline-none focus:ring-0 transition-colors rounded-none placeholder:text-text-muted" 
              placeholder="Enter Session UUID..." 
              type="text" 
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
            />
          </form>
        </div>

        <nav className="hidden md:flex items-center gap-6">
          <button 
            onClick={() => setSidebarTab('executions')}
            className={`${sidebarTab === 'executions' ? 'text-primary font-bold border-b-2 border-primary' : 'text-text-muted hover:text-primary'} h-16 flex items-center pt-0.5 cursor-pointer font-body-md transition-colors`}
          >
            Dashboard
          </button>
          <button 
            onClick={() => setSidebarTab('workstation')}
            className={`${sidebarTab === 'workstation' ? 'text-primary font-bold border-b-2 border-primary' : 'text-text-muted hover:text-primary'} h-16 flex items-center pt-0.5 cursor-pointer font-body-md transition-colors`}
          >
            Workstation
          </button>
          <button 
            onClick={() => setSidebarTab('telemetry')}
            className={`${sidebarTab === 'telemetry' ? 'text-primary font-bold border-b-2 border-primary' : 'text-text-muted hover:text-primary'} h-16 flex items-center pt-0.5 cursor-pointer font-body-md transition-colors`}
          >
            Telemetry
          </button>
          <button 
            onClick={() => setSidebarTab('chromadb')}
            className={`${sidebarTab === 'chromadb' ? 'text-primary font-bold border-b-2 border-primary' : 'text-text-muted hover:text-primary'} h-16 flex items-center pt-0.5 cursor-pointer font-body-md transition-colors`}
          >
            ChromaDB
          </button>
        </nav>

        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsNewRunModalOpen(true)}
            className="hidden md:flex items-center gap-2 border border-primary text-primary font-label-caps text-label-caps px-4 py-2 hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">play_arrow</span>
            Run FixForge
          </button>
          <div className="flex items-center gap-3 text-text-muted border-l border-border-muted pl-4">
            <button className="hover:text-primary transition-colors relative">
              <span className="material-symbols-outlined">notifications</span>
              {streamState.activeNode && (
                <span className="absolute top-0 right-0 w-2 h-2 bg-primary rounded-full animate-pulse" />
              )}
            </button>
            <button className="hover:text-primary transition-colors"><span className="material-symbols-outlined">settings</span></button>
            <div className="w-8 h-8 rounded-none bg-surface-container border border-border-muted overflow-hidden ml-2 cursor-pointer flex items-center justify-center text-text-muted hover:text-primary transition-colors" title="Operator Profile">
              <span className="material-symbols-outlined text-[18px]">account_circle</span>
            </div>
          </div>
        </div>
      </header>

      {/* Offline Demo Banner */}
      {streamState.isDemo && (
        <div className="bg-amber-500/10 border-b border-amber-500/40 text-amber-300 px-4 py-1.5 text-center font-code-sm text-xs flex justify-center items-center gap-3">
          <span className="px-1.5 py-0.5 rounded bg-amber-500 text-black font-black text-[10px] tracking-wider">
            SIMULATED
          </span>
          <span>Running in Offline Simulated Demo Mode (no live LLM/Docker calls).</span>
          <button onClick={streamState.replayDemo} className="ml-2 underline font-bold hover:text-white flex items-center gap-1 text-amber-200">
            <span className="material-symbols-outlined text-[14px]">play_circle</span> Replay Simulation
          </button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden relative">
        {/* SideNavBar */}
        <aside className="bg-surface-container-lowest dark:bg-surface-container-lowest docked fixed left-0 h-full w-60 border-r border-border-muted flex flex-col z-40 hidden xl:flex shrink-0">
          <div className="p-6 border-b border-border-muted">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-surface-deep border border-border-muted flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-primary">dns</span>
              </div>
              <div>
                <div className="font-label-caps text-label-caps text-text-muted mb-1">SESSION ID</div>
                <div className="font-headline-md text-headline-md text-primary leading-tight truncate w-32" title={activeSession || 'None'}>
                  {activeSession ? activeSession.split('-')[0] + '...' : 'None'}
                </div>
              </div>
            </div>
            
            {streamState.isDemo ? (
              <button 
                onClick={streamState.replayDemo}
                className="w-full bg-primary text-background font-label-caps text-label-caps py-2 flex justify-center items-center gap-2 hover:bg-tertiary-fixed transition-colors"
              >
                <span className="material-symbols-outlined text-[14px]">play_arrow</span>
                Play Live Run
              </button>
            ) : (
              <button 
                onClick={() => setIsNewRunModalOpen(true)}
                className="w-full border border-border-muted text-primary font-label-caps text-label-caps py-2 flex justify-center items-center gap-2 hover:border-primary transition-colors"
              >
                <span className="material-symbols-outlined text-[14px]">play_arrow</span>
                New Run
              </button>
            )}
          </div>
          <nav className="flex-1 py-4 flex flex-col">
            <button 
              onClick={() => setSidebarTab('workstation')}
              className={`flex items-center gap-4 px-4 py-3 transition-all duration-150 ease-in-out font-body-sm text-body-sm w-full text-left ${
                sidebarTab === 'workstation'
                  ? 'bg-surface-container-highest text-primary font-bold border-l-2 border-primary'
                  : 'text-text-muted hover:bg-surface-container hover:text-primary'
              }`}
            >
              <span className="material-symbols-outlined">terminal</span> Workstation
            </button>
            <button 
              onClick={() => setSidebarTab('executions')}
              className={`flex items-center gap-4 px-4 py-3 transition-all duration-150 ease-in-out font-body-sm text-body-sm w-full text-left ${
                sidebarTab === 'executions'
                  ? 'bg-surface-container-highest text-primary font-bold border-l-2 border-primary'
                  : 'text-text-muted hover:bg-surface-container hover:text-primary'
              }`}
            >
              <span className="material-symbols-outlined" style={{fontVariationSettings: sidebarTab === 'executions' ? "'FILL' 1" : undefined}}>account_tree</span> Executions
            </button>
            <button 
              onClick={() => setSidebarTab('telemetry')}
              className={`flex items-center gap-4 px-4 py-3 transition-all duration-150 ease-in-out font-body-sm text-body-sm w-full text-left ${
                sidebarTab === 'telemetry'
                  ? 'bg-surface-container-highest text-primary font-bold border-l-2 border-primary'
                  : 'text-text-muted hover:bg-surface-container hover:text-primary'
              }`}
            >
              <span className="material-symbols-outlined">analytics</span> Telemetry
            </button>
            <button 
              onClick={() => setSidebarTab('chromadb')}
              className={`flex items-center gap-4 px-4 py-3 transition-all duration-150 ease-in-out font-body-sm text-body-sm w-full text-left ${
                sidebarTab === 'chromadb'
                  ? 'bg-surface-container-highest text-primary font-bold border-l-2 border-primary'
                  : 'text-text-muted hover:bg-surface-container hover:text-primary'
              }`}
            >
              <span className="material-symbols-outlined">database</span> ChromaDB Memory
            </button>
          </nav>
        </aside>

        {/* Main Canvas */}
        <main className="flex-1 xl:ml-60 h-full overflow-y-auto bg-background p-margin-mobile md:p-margin-desktop relative">
          <div className="max-w-7xl mx-auto space-y-8 pb-20">
            {sidebarTab === 'workstation' && (
              <WorkstationView
                activeSession={activeSession}
                sessionDetails={sessionDetails}
                streamState={streamState}
                onTriggerRun={() => setIsNewRunModalOpen(true)}
              />
            )}

            {sidebarTab === 'telemetry' && (
              <TelemetryView
                sessionDetails={sessionDetails}
                streamState={streamState}
                health={health}
              />
            )}

            {sidebarTab === 'chromadb' && (
              <ChromaDBView
                onInjectHeuristic={(heuristic) => {
                  setRetryGuidance(`Consider historical fix pattern: ${heuristic}`);
                }}
              />
            )}

            {sidebarTab === 'executions' && (
              <>
            {/* Header Section */}
            <div>
              <div className="flex items-center gap-2 text-text-muted font-label-caps text-label-caps mb-2">
                <span className="material-symbols-outlined text-[14px]">smart_toy</span>
                AUTONOMOUS PROGRAM REPAIR // FIXFORGE AI
              </div>
              <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight flex items-center gap-3">
                {currentScenario ? currentScenario.title : activeSession ? `Execution Trace` : 'Awaiting Session'} 
                {!currentScenario && activeSession && (
                  <span className="text-text-muted font-normal text-[24px]">
                    #{activeSession.split('-')[0]}
                  </span>
                )}
                
                {streamState.activeNode && !streamState.isComplete && (
                  <span className="relative flex h-3 w-3 ml-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                  </span>
                )}
              </h1>
              {activeSession && (
                <div className="flex items-center gap-3 mt-2 font-code-sm text-code-sm text-text-muted">
                  <span className="flex items-center gap-1 border border-border-muted px-2 py-0.5">
                    <span className="material-symbols-outlined text-[14px]">commit</span> {streamState.isComplete ? 'Execution Completed' : 'In Progress'}
                  </span>
                  <span>•</span>
                  <span>{streamState.isDemo ? 'Triggered via Simulated Playback' : 'Triggered via Webhook'}</span>
                  {health && (
                    <>
                      <span>•</span>
                      <span className="text-xs uppercase font-mono text-text-muted">
                        LLM: <b className={health.llm_mode === 'live' ? 'text-emerald-400' : 'text-amber-400'}>{health.llm_mode}</b> | DOCKER: <b className={health.docker_mode === 'live' ? 'text-emerald-400' : 'text-rose-400'}>{health.docker_mode}</b>
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>

            {!activeSession && (
              <div className="border border-border-muted bg-surface-deep p-12 flex flex-col items-center justify-center text-center">
                <span className="material-symbols-outlined text-[48px] text-text-muted mb-4">search</span>
                <h3 className="font-headline-md text-primary mb-2">No Active Run</h3>
                <p className="text-text-muted max-w-md">Enter a Session UUID, trigger a new run, or select a Demo Scenario to view the execution trace.</p>
                <button onClick={() => setIsNewRunModalOpen(true)} className="mt-6 bg-primary text-background px-6 py-2 font-bold hover:bg-tertiary-fixed transition-colors">Start New Analysis</button>
              </div>
            )}

            {activeSession && (
              <>
                {/* Verdict Banner */}
                {streamState.isComplete && (
                  <div className="border border-border-muted bg-surface-deep flex flex-col md:flex-row md:items-center justify-between p-6 relative overflow-hidden group animate-in fade-in slide-in-from-top-4 duration-500">
                    <div className="absolute inset-0 bg-gradient-to-r from-background to-transparent opacity-50 pointer-events-none"></div>
                    <div className="relative z-10 flex items-start md:items-center gap-4">
                      {streamState.verdict === 'unverified' ? (
                        <>
                          <div className="w-12 h-12 flex items-center justify-center border border-amber-500/50 bg-amber-500/10 text-amber-400">
                            <span className="material-symbols-outlined text-[28px]" style={{fontVariationSettings: "'FILL' 1"}}>
                              warning
                            </span>
                          </div>
                          <div>
                            <div className="font-headline-md text-headline-md font-bold text-amber-400">
                              STATUS: UNVERIFIED • {health?.docker_mode === 'live' ? 'SANDBOX VERIFICATION INCOMPLETE' : 'DOCKER SANDBOX UNAVAILABLE'}
                            </div>
                            <div className="font-body-sm text-body-sm text-text-muted mt-1">
                              {health?.docker_mode === 'live'
                                ? 'Sandbox execution could not verify the fix candidate. Fix candidate generated but unverified.'
                                : 'Verification was skipped because the Docker daemon is unreachable. Fix candidate generated but unverified.'}
                            </div>
                          </div>
                        </>
                      ) : streamState.verdict === 'passed' || (streamState.finalDiff && streamState.verdict !== 'failed') ? (
                        <>
                          <div className="w-12 h-12 flex items-center justify-center border border-primary bg-primary/10">
                            <span className="material-symbols-outlined text-[28px] text-primary" style={{fontVariationSettings: "'FILL' 1"}}>
                              check_circle
                            </span>
                          </div>
                          <div>
                            <div className="font-headline-md text-headline-md font-bold text-primary">
                              FIX VERIFIED • READY FOR APPROVAL
                            </div>
                            <div className="font-body-sm text-body-sm text-text-muted mt-1">
                              All sandbox constraints satisfied. Patch ready to be merged.
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="w-12 h-12 flex items-center justify-center border border-error bg-error/10">
                            <span className="material-symbols-outlined text-[28px] text-error" style={{fontVariationSettings: "'FILL' 1"}}>
                              error
                            </span>
                          </div>
                          <div>
                            <div className="font-headline-md text-headline-md font-bold text-error">
                              FIX FAILED • VERIFICATION UNSUCCESSFUL
                            </div>
                            <div className="font-body-sm text-body-sm text-text-muted mt-1">
                              The agent was unable to find a valid patch within the retry limits.
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                    <div className="relative z-10 flex items-center gap-6 mt-6 md:mt-0 font-code-sm text-code-sm border-t md:border-t-0 md:border-l border-border-muted pt-4 md:pt-0 md:pl-6">
                      <div>
                        <div className="text-text-muted mb-1">ATTEMPTS</div>
                        <div className="text-primary text-[16px]">0{streamState.retryIteration + 1}</div>
                      </div>
                      {streamState.confidenceScore !== null && (
                        <div>
                          <div className="text-text-muted mb-1">CONFIDENCE</div>
                          <div className="text-primary text-[16px]">{(streamState.confidenceScore * 100).toFixed(0)}%</div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Agent Flow Timeline */}
                <div className="border border-border-muted p-4 bg-surface-deep">
                  <div className="font-label-caps text-label-caps text-text-muted mb-4">EXECUTION PIPELINE</div>
                  <div className="flex flex-col md:flex-row justify-between relative">
                    <div className="hidden md:block absolute top-1/2 left-4 right-4 h-px bg-border-muted -translate-y-1/2 z-0"></div>
                    <div className="flex items-center gap-8 w-full justify-between z-10 relative overflow-x-auto pb-2 md:pb-0 hide-scrollbar">
                      {pipelineOrder.map((agentName, idx) => {
                        const node = streamState.nodes[agentName];
                        const isCompleted = node?.status === 'completed';
                        const isRunning = streamState.activeNode === agentName;
                        const isFailed = node?.status === 'failed';
                        const isUnverified = node?.status === 'unverified';
                        
                        let bgClass = 'bg-surface-container border border-border-muted text-text-muted hover:border-primary cursor-pointer transition-colors';
                        if (isCompleted) bgClass = 'bg-primary text-background shadow-[0_0_10px_rgba(255,255,255,0.2)] cursor-pointer';
                        if (isRunning) bgClass = 'bg-primary border border-primary text-background animate-pulse cursor-pointer';
                        if (isFailed) bgClass = 'bg-error text-background cursor-pointer';
                        if (isUnverified) bgClass = 'bg-amber-500 text-background cursor-pointer';

                        return (
                          <div key={agentName} className="flex flex-col items-center gap-2 min-w-[60px]" onClick={() => setActiveAgentNode(agentName)}>
                            <div className={`w-4 h-4 flex items-center justify-center ${bgClass}`} title={`Inspect ${agentName} telemetry`}>
                              {isCompleted ? <span className="material-symbols-outlined text-[12px] font-bold">check</span> :
                              isFailed ? <span className="material-symbols-outlined text-[12px] font-bold">close</span> :
                              isUnverified ? <span className="material-symbols-outlined text-[12px] font-bold">warning</span> : null}
                            </div>
                            <div className={`font-label-caps text-label-caps text-center whitespace-nowrap ${isCompleted || isRunning ? 'text-primary' : isUnverified ? 'text-amber-400' : 'text-text-muted'}`}>
                              0{idx + 1} {agentName.replace('_', ' ').toUpperCase()}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Main Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
                  {/* Left Panel (60%) */}
                  <div className="lg:col-span-6 flex flex-col gap-0 border border-border-muted bg-surface-deep">
                    {/* Tabs */}
                    <div className="flex items-center border-b border-border-muted bg-background overflow-x-auto hide-scrollbar">
                      <button 
                        onClick={() => setActiveTab('diff')}
                        className={`px-6 py-3 font-code-sm text-code-sm flex items-center gap-2 whitespace-nowrap ${activeTab === 'diff' ? 'text-primary border-b-2 border-primary bg-surface-deep' : 'text-text-muted hover:text-primary transition-colors border-b-2 border-transparent'}`}
                      >
                        <span className="material-symbols-outlined text-[16px]">difference</span> Patch Diff
                      </button>
                      <button 
                        onClick={() => setActiveTab('diagnosis')}
                        className={`px-6 py-3 font-code-sm text-code-sm flex items-center gap-2 whitespace-nowrap border-l border-border-muted ${activeTab === 'diagnosis' ? 'text-primary border-b-2 border-primary bg-surface-deep' : 'text-text-muted hover:text-primary transition-colors border-b-2 border-transparent'}`}
                      >
                        <span className="material-symbols-outlined text-[16px]">bug_report</span> RCA Diagnosis
                      </button>
                      <button 
                        onClick={() => setActiveTab('logs')}
                        className={`px-6 py-3 font-code-sm text-code-sm flex items-center gap-2 whitespace-nowrap border-l border-border-muted ${activeTab === 'logs' ? 'text-primary border-b-2 border-primary bg-surface-deep' : 'text-text-muted hover:text-primary transition-colors border-b-2 border-transparent'}`}
                      >
                        <span className="material-symbols-outlined text-[16px]">terminal</span> Sandbox Logs
                      </button>
                      <button 
                        onClick={() => setActiveTab('history')}
                        className={`px-6 py-3 font-code-sm text-code-sm flex items-center gap-2 whitespace-nowrap border-l border-border-muted ${activeTab === 'history' ? 'text-primary border-b-2 border-primary bg-surface-deep' : 'text-text-muted hover:text-primary transition-colors border-b-2 border-transparent'}`}
                      >
                        <span className="material-symbols-outlined text-[16px]">history</span> Iteration History
                      </button>
                    </div>
                    
                    {/* Tab Content */}
                    <div className="flex flex-col h-[550px]">
                      {activeTab === 'diff' && (
                        <DiffViewer
                          diff={streamState.finalDiff ?? (streamState.chunks ? streamState.chunks : null)}
                          isStreaming={streamState.isStreaming || (!!streamState.activeNode && streamState.activeNode === 'fixer' && !streamState.finalDiff)}
                          viewMode={diffViewMode}
                          onCopy={copyDiff}
                          onDownload={downloadPatch}
                          onViewModeChange={setDiffViewMode}
                        />
                      )}

                      {activeTab === 'diagnosis' && (
                        <div className="flex-1 bg-surface-deep p-6 overflow-y-auto flex flex-col gap-4">
                          <div className="border border-border-muted bg-background p-4">
                            <h3 className="font-bold text-primary mb-2 flex items-center gap-2">
                              <span className="material-symbols-outlined text-error">warning</span> Failure Mechanism & Root Cause
                            </h3>
                            <p className="text-text-muted font-code-sm leading-relaxed whitespace-pre-wrap">
                              {sessionDetails?.diagnosis?.diff_trees?.root_cause ||
                               sessionDetails?.diagnosis?.ast_context?.error ||
                               sessionDetails?.diagnosis?.failure_classification ||
                               (currentScenario ? currentScenario.bug : 'Awaiting diagnosis...')}
                            </p>
                          </div>
                          {sessionDetails?.diagnosis?.diff_trees?.plan && (
                            <div className="border border-border-muted bg-background p-4">
                              <h3 className="font-bold text-primary mb-2 flex items-center gap-2">
                                <span className="material-symbols-outlined text-sky-400">psychology</span> Investigation & Action Plan
                              </h3>
                              <p className="text-text-muted font-code-sm leading-relaxed whitespace-pre-wrap">
                                {sessionDetails.diagnosis.diff_trees.plan}
                              </p>
                            </div>
                          )}
                          <div className="border border-border-muted bg-background p-4">
                            <h3 className="font-bold text-primary mb-2 flex items-center gap-2">
                              <span className="material-symbols-outlined text-primary">account_tree</span> Scoped Source Files & Blast Radius
                            </h3>
                            {sessionDetails?.diagnosis?.ast_context?.source_files_read?.length ? (
                              <ul className="text-text-muted font-code-sm ml-4 list-disc space-y-1">
                                {sessionDetails.diagnosis.ast_context.source_files_read.map((file: string, idx: number) => (
                                  <li key={idx} className="text-primary font-mono text-xs">{file}</li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-text-muted font-code-sm text-xs italic">
                                {sessionDetails?.diagnosis?.ast_context?.error ||
                                 (currentScenario ? '__init__.py (Caller), core.py (Dependency)' : 'No target source files localized.')}
                              </p>
                            )}
                          </div>
                        </div>
                      )}

                      {activeTab === 'logs' && (
                        <div className="flex-1 flex flex-col bg-[#050508]">
                           <div className="bg-surface-container-lowest border-b border-border-muted px-4 py-2 flex justify-between items-center text-text-muted shrink-0">
                            <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-[14px]">terminal</span> Pytest Sandbox
                            </div>
                            <div className="flex gap-3 items-center">
                              <label className="flex items-center gap-1 text-xs cursor-pointer hover:text-primary">
                                <input type="checkbox" checked={isAutoScrollEnabled} onChange={(e) => setIsAutoScrollEnabled(e.target.checked)} className="accent-primary" />
                                Auto-scroll
                              </label>
                              <button onClick={() => toast("Re-running sandbox suite...", {id: 'rerun'})} title="Re-run Sandbox" className="hover:text-primary"><span className="material-symbols-outlined text-[14px]">replay</span></button>
                              <button onClick={copyLogs} title="Copy Logs" className="hover:text-primary"><span className="material-symbols-outlined text-[14px]">content_copy</span></button>
                            </div>
                          </div>
                          <div className="p-4 overflow-y-auto font-code-sm text-code-sm text-[#a0aec0] flex-1">
                            {streamState.logs.length === 0 ? (
                               <div className="opacity-50 italic">Waiting for sandbox execution logs...</div>
                            ) : (
                              streamState.logs.map((log, i) => (
                                <div key={i} className="break-all whitespace-pre-wrap mb-1">
                                  <span className="text-text-muted">[{new Date().toLocaleTimeString()}]</span> {log}
                                </div>
                              ))
                            )}
                            {streamState.chunks && <span className="text-primary">{streamState.chunks}</span>}
                            <div ref={logsEndRef} />
                          </div>
                        </div>
                      )}

                      {activeTab === 'history' && (
                        <div className="flex-1 flex flex-col bg-surface-deep">
                          <div className="flex border-b border-border-muted">
                            {[...Array(streamState.retryIteration + 1)].map((_, i) => (
                              <button 
                                key={i}
                                onClick={() => setActiveAttemptTab(i)}
                                className={`px-4 py-2 font-code-sm text-code-sm border-r border-border-muted ${activeAttemptTab === i ? 'bg-primary text-background font-bold' : 'text-text-muted hover:text-primary transition-colors'}`}
                              >
                                Attempt #{i + 1}
                              </button>
                            ))}
                          </div>
                          <div className="p-6 text-text-muted font-code-sm">
                            {activeAttemptTab === streamState.retryIteration ? (
                              <p>Current iteration. {streamState.retryMessage}</p>
                            ) : (
                              <p>Attempt #{activeAttemptTab + 1} failed constraints. Sent back for human/agent review.</p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Panel (40%) */}
                  <div className="lg:col-span-4 flex flex-col gap-6">
                    {/* Confidence Card */}
                    <div className="bento-grid group">
                      <div className="bento-item p-6 flex flex-col items-center justify-center cursor-help">
                        <div className="font-label-caps text-label-caps text-text-muted mb-2 tracking-widest">OVERALL CONFIDENCE</div>
                        <div className="font-headline-lg text-[64px] leading-none text-primary font-bold tracking-tighter">
                          {streamState.confidenceScore !== null ? (streamState.confidenceScore * 100).toFixed(0) : '--'}
                          <span className="text-[32px] text-text-muted">%</span>
                        </div>
                        <div className="hidden group-hover:block absolute bg-surface-container border border-border-muted p-2 text-xs text-text-muted mt-24 shadow-lg z-50">
                          Weighted average of Test Pass Rate (40%), Static Analysis (30%), and Context Match (30%).
                        </div>
                      </div>
                      <div className="bento-item p-6 space-y-5">
                        <div className="relative group/bar cursor-help">
                          <div className="flex justify-between font-label-caps text-label-caps text-text-muted mb-2">
                            <span>TEST PASS (SANDBOX)</span>
                            <span className="text-primary">{streamState.finalDiff ? '100%' : '0%'}</span>
                          </div>
                          <div className="flex gap-1">
                            {[...Array(10)].map((_, i) => (
                              <div key={i} className={`h-2 flex-1 ${streamState.finalDiff ? 'bg-primary' : 'border border-border-muted'}`}></div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Action Center */}
                    <div className="border border-border-muted bg-surface p-6 flex flex-col gap-4">
                      <button 
                        onClick={handleApprove}
                        disabled={!streamState.isComplete || !streamState.finalDiff}
                        className={`w-full font-headline-md text-body-md font-bold py-4 flex items-center justify-center gap-2 transition-colors
                          ${(!streamState.isComplete || !streamState.finalDiff) 
                            ? 'bg-surface-container text-text-muted cursor-not-allowed border border-border-muted' 
                            : 'bg-primary text-background hover:bg-tertiary-fixed'}`}
                      >
                        <span className="material-symbols-outlined">merge_type</span>
                        Approve & Create Pull Request
                      </button>
                      <button 
                        onClick={() => setIsRetryModalOpen(true)}
                        disabled={!activeSession}
                        className={`w-full border border-border-muted font-body-md font-bold py-4 flex items-center justify-center gap-2 transition-colors
                          ${!activeSession ? 'text-text-muted opacity-50 cursor-not-allowed' : 'text-primary hover:bg-surface-container'}`}
                      >
                        <span className="material-symbols-outlined">refresh</span>
                        Request HITL Retry
                      </button>
                      <button 
                        onClick={handleDismiss}
                        disabled={!activeSession}
                        className="w-full text-error font-body-md py-2 hover:bg-error/10 transition-colors disabled:opacity-50"
                      >
                        Dismiss / Reject
                      </button>
                      
                      {streamState.retryIteration > 0 && (
                        <div className="mt-4 pt-4 border-t border-border-muted flex flex-col font-code-sm text-code-sm text-warning-gray">
                           <span className="text-error">Retry Triggered: {streamState.retryIteration}/3</span>
                           <span>{streamState.retryMessage}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}
            </>
            )}
          </div>
        </main>
      </div>

      {/* MODALS & DRAWERS */}

      {/* 1. New Run Modal */}
      {isNewRunModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-deep border border-border-muted w-full max-w-lg p-6">
            <h2 className="font-headline-md text-primary mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined">rocket_launch</span> Trigger New Analysis
            </h2>
            <form onSubmit={handleNewRun}>
              <div className="mb-4">
                <label className="block font-label-caps text-text-muted mb-2">TARGET GITHUB REPOSITORY OR ISSUE</label>
                <input 
                  type="text" 
                  autoFocus
                  required
                  value={newRunUrl}
                  onChange={(e) => setNewRunUrl(e.target.value)}
                  placeholder="https://github.com/pallets/flask or pallets/flask#5012"
                  className="w-full bg-surface-container border border-border-muted text-on-surface p-3 font-code-sm focus:border-primary focus:outline-none mb-2"
                />
                <div className="flex flex-wrap items-center gap-2 text-xs mt-2">
                  <span className="text-text-muted font-label-caps text-[10px]">PRESETS:</span>
                  <button 
                    type="button" 
                    onClick={() => setNewRunUrl("https://github.com/jkoppel/QuixBugs#breadth_first_search")}
                    className="border border-border-muted px-2 py-1 text-text-muted hover:text-primary hover:border-primary font-code-sm transition-colors"
                  >
                    QuixBugs (BFS)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setNewRunUrl("https://github.com/jkoppel/QuixBugs#bitcount")}
                    className="border border-border-muted px-2 py-1 text-text-muted hover:text-primary hover:border-primary font-code-sm transition-colors"
                  >
                    QuixBugs (bitcount)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setNewRunUrl("https://github.com/pallets/flask/pull/5012")}
                    className="border border-border-muted px-2 py-1 text-text-muted hover:text-primary hover:border-primary font-code-sm transition-colors"
                  >
                    pallets/flask#5012
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setNewRunUrl("https://github.com/pallets/flask")}
                    className="border border-border-muted px-2 py-1 text-text-muted hover:text-primary hover:border-primary font-code-sm transition-colors"
                  >
                    pallets/flask
                  </button>
                </div>

              </div>
              <div className="flex justify-end gap-4 mt-6">
                <button type="button" onClick={() => setIsNewRunModalOpen(false)} className="px-4 py-2 text-text-muted hover:text-primary">Cancel</button>
                <button type="submit" className="bg-primary text-background px-6 py-2 font-bold hover:bg-tertiary-fixed">Execute Run</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 2. HITL Retry Modal */}
      {isRetryModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-deep border border-border-muted w-full max-w-lg p-6">
            <h2 className="font-headline-md text-primary mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined">psychology</span> Human-in-the-Loop Guidance
            </h2>
            <div className="mb-4">
              <label className="block font-label-caps text-text-muted mb-2">GUIDANCE FOR AGENT</label>
              <textarea 
                rows={4}
                autoFocus
                value={retryGuidance}
                onChange={(e) => setRetryGuidance(e.target.value)}
                placeholder="e.g., Do not modify the public signature of pop(). Use asyncio.run() instead."
                className="w-full bg-surface-container border border-border-muted text-on-surface p-3 font-code-sm focus:border-primary focus:outline-none resize-none"
              />
            </div>
            <div className="flex justify-end gap-4 mt-6">
              <button onClick={() => setIsRetryModalOpen(false)} className="px-4 py-2 text-text-muted hover:text-primary">Cancel</button>
              <button onClick={handleRequestRetry} className="bg-primary text-background px-6 py-2 font-bold hover:bg-tertiary-fixed">Submit & Restart Loop</button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Agent Inspection Drawer */}
      {activeAgentNode && (
        <div className="fixed inset-y-0 right-0 w-96 bg-surface-deep border-l border-border-muted z-50 shadow-2xl flex flex-col animate-in slide-in-from-right">
          <div className="p-4 border-b border-border-muted flex justify-between items-center bg-background">
            <h2 className="font-headline-md text-primary capitalize flex items-center gap-2">
              <span className="material-symbols-outlined">memory</span> {activeAgentNode.replace('_', ' ')}
            </h2>
            <button onClick={() => setActiveAgentNode(null)} className="text-text-muted hover:text-primary"><span className="material-symbols-outlined">close</span></button>
          </div>
          <div className="p-4 overflow-y-auto flex-1 font-code-sm text-xs">
            <div className="mb-4">
              <div className="text-text-muted mb-1 font-label-caps">STATUS</div>
              <div className="text-primary">{streamState.nodes[activeAgentNode]?.status?.toUpperCase() || 'PENDING'}</div>
            </div>
            <div className="mb-4">
              <div className="text-text-muted mb-1 font-label-caps">EXECUTION LATENCY</div>
              <div className="text-primary">{streamState.nodes[activeAgentNode]?.latency ? `${streamState.nodes[activeAgentNode]?.latency}ms` : '--'}</div>
            </div>
            <div className="mb-4">
              <div className="text-text-muted mb-1 font-label-caps">PAYLOAD (JSON)</div>
              <pre className="bg-[#0c0c0c] p-2 border border-border-muted overflow-x-auto text-text-muted">
                {JSON.stringify(streamState.nodes[activeAgentNode]?.output || { state: 'waiting' }, null, 2)}
              </pre>
            </div>
            <div className="mb-4">
              <div className="text-text-muted mb-1 font-label-caps">SYSTEM PROMPT HINT</div>
              <p className="text-text-muted italic border-l-2 border-border-muted pl-2">System instruction configuration for {activeAgentNode} loaded from memory.</p>
            </div>
          </div>
        </div>
      )}

      {/* 4. Historical Fix Memory Drawer */}
      {isHistoricalFixDrawerOpen && (
        <div className="fixed inset-y-0 right-0 w-full md:w-1/2 lg:w-1/3 bg-surface-deep border-l border-border-muted z-50 shadow-2xl flex flex-col animate-in slide-in-from-right">
          <div className="p-4 border-b border-border-muted flex justify-between items-center bg-background">
            <h2 className="font-headline-md text-primary flex items-center gap-2">
              <span className="material-symbols-outlined">database</span> ChromaDB Recall
            </h2>
            <button onClick={() => setIsHistoricalFixDrawerOpen(false)} className="text-text-muted hover:text-primary"><span className="material-symbols-outlined">close</span></button>
          </div>
          <div className="p-6 overflow-y-auto flex-1 font-code-sm">
            {currentScenario ? (
              <div className="border border-border-muted bg-surface-container p-4 mb-4">
                <div className="flex justify-between items-start mb-2">
                  <div className="font-bold text-primary">Matched {currentScenario.historicalMatch.id}</div>
                  <div className="text-primary border border-primary px-2 text-xs">{(currentScenario.historicalMatch.similarity * 100).toFixed(0)}% Cosine Sim</div>
                </div>
                <p className="text-text-muted mb-4 text-xs">{currentScenario.historicalMatch.description}</p>
                <div className="bg-[#0c0c0c] border border-border-muted p-2 text-xs overflow-x-auto whitespace-pre">
                  {currentScenario.historicalMatch.diff.split('\n').map((line, i) => {
                     if (line.startsWith('+')) return <span key={i} className="text-primary block">{line}</span>;
                     if (line.startsWith('-')) return <span key={i} className="text-error line-through block">{line}</span>;
                     return <span key={i} className="block">{line}</span>;
                  })}
                </div>
                <button className="mt-4 text-primary underline text-xs w-full text-left" onClick={() => toast("Applying historical heuristic to context...")}>Inject Heuristic to Current Prompt</button>
              </div>
            ) : (
              <div className="text-text-muted">No historical matches loaded.</div>
            )}
          </div>
        </div>
      )}

    </div>
  );
}
