import { useState, useEffect, useCallback, useRef } from 'react';
import { mockScenarios } from '../data/mockScenarios';
import { DemoPlaybackEngine } from '../utils/demoPlayback';
import { API_BASE_URL } from '../config/env';

export interface AgentNode {
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'unverified';
  latency?: number;
  output?: unknown;
}

export interface FixForgeStreamState {
  nodes: Record<string, AgentNode>;
  activeNode: string | null;
  logs: string[];
  chunks: string;
  retryIteration: number;
  retryMessage: string | null;
  isComplete: boolean;
  isStreaming: boolean;  // true while fixer is streaming diff tokens
  confidenceScore: number | null;
  finalDiff: string | null;
  githubComment: string | null;
  error: string | null;
  verdict?: 'passed' | 'failed' | 'unverified' | null;
  isDemo?: boolean;
}

const initialState: FixForgeStreamState = {
  nodes: {},
  activeNode: null,
  logs: [],
  chunks: '',
  retryIteration: 0,
  retryMessage: null,
  isComplete: false,
  isStreaming: false,
  confidenceScore: null,
  finalDiff: null,
  githubComment: null,
  error: null,
};

const MAX_RECONNECT_ATTEMPTS = 5;

export function useFixForgeStream(sessionId: string) {
  const [state, setState] = useState<FixForgeStreamState>(initialState);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  
  const engineRef = useRef<DemoPlaybackEngine | null>(null);

  const connect = useCallback(() => {
    if (!sessionId) return;
    
    // Check if it's a demo scenario
    if (mockScenarios[sessionId]) {
       const scenario = mockScenarios[sessionId];
       engineRef.current?.stop();
       
       const engine = new DemoPlaybackEngine(scenario, (update) => {
         setState(update);
       });
       engineRef.current = engine;
       setState(prev => ({...prev, isDemo: true, error: null}));
       engine.play();
       return;
    }

    // Real SSE Connection
    setState(prev => ({...prev, isDemo: false}));
    
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const baseUrl = API_BASE_URL;
    const es = new EventSource(`${baseUrl}/api/sessions/${sessionId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('node_start', (e: Event) => {
      const msgEvent = e as MessageEvent;
      const data = JSON.parse(msgEvent.data);
      setState(prev => ({
        ...prev,
        activeNode: data.agent,
        nodes: {
          ...prev.nodes,
          [data.agent]: { agent: data.agent, status: 'running' }
        }
      }));
    });

    es.addEventListener('node_progress', (e: Event) => {
      const msgEvent = e as MessageEvent;
      const data = JSON.parse(msgEvent.data);
      if (data.chunk) {
        setState(prev => ({ ...prev, chunks: prev.chunks + data.chunk, isStreaming: true }));
      }
      if (data.log_line) {
        setState(prev => ({ ...prev, logs: [...prev.logs, data.log_line] }));
      }
    });

    es.addEventListener('node_complete', (e: Event) => {
      const msgEvent = e as MessageEvent;
      const data = JSON.parse(msgEvent.data);
      setState(prev => ({
        ...prev,
        nodes: {
          ...prev.nodes,
          [data.agent]: {
            ...prev.nodes[data.agent],
            status: data.status as 'completed' | 'failed' | 'unverified',
            latency: data.latency,
            output: data.output
          }
        },
        chunks: '',
        isStreaming: false,
      }));
    });

    es.addEventListener('retry_loop', (e: Event) => {
      const msgEvent = e as MessageEvent;
      const data = JSON.parse(msgEvent.data);
      setState(prev => ({
        ...prev,
        retryIteration: data.iteration,
        retryMessage: data.message
      }));
    });

    es.addEventListener('pipeline_complete', (e: Event) => {
      const msgEvent = e as MessageEvent;
      const data = JSON.parse(msgEvent.data);
      setState(prev => ({
        ...prev,
        isComplete: true,
        finalDiff: data.diff,
        confidenceScore: data.confidenceScore ?? data.confidence_score,
        githubComment: data.githubComment ?? data.github_comment,
        verdict: data.verdict ?? (data.status === 'unverified' ? 'unverified' : (data.diff ? 'passed' : 'failed'))
      }));
      es.close();
    });

    es.addEventListener('error', (e: Event) => {
      const msgEvent = e as MessageEvent;
      const data = msgEvent.data ? JSON.parse(msgEvent.data) : { detail: 'Unknown streaming error' };
      setState(prev => ({ ...prev, error: data.detail }));
    });

    es.onerror = (error) => {
      console.warn("SSE Connection closed or complete:", error);
      es.close();

      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 5000);
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(connect, backoffMs);
      } else {
        // Stream completed or server closed connection for finished session
        setState(prev => ({ ...prev, isComplete: true, isStreaming: false, error: null }));
      }
    };

    es.onopen = () => {
      reconnectAttemptsRef.current = 0; 
    };
  }, [sessionId]);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (engineRef.current) {
        engineRef.current.stop();
      }
    };
  }, [connect]);

  // Method to manually re-trigger demo if needed
  const replayDemo = useCallback(() => {
    if (state.isDemo && engineRef.current) {
      engineRef.current.play();
    }
  }, [state.isDemo]);

  return { ...state, replayDemo };
}
