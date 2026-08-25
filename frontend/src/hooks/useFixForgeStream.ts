import { useState, useEffect, useCallback, useRef } from 'react';

export interface AgentNode {
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  latency?: number;
  output?: any;
}

export interface FixForgeStreamState {
  nodes: Record<string, AgentNode>;
  activeNode: string | null;
  logs: string[];
  chunks: string;
  retryIteration: number;
  retryMessage: string | null;
  isComplete: boolean;
  confidenceScore: number | null;
  finalDiff: string | null;
  githubComment: string | null;
  error: string | null;
}

const initialState: FixForgeStreamState = {
  nodes: {},
  activeNode: null,
  logs: [],
  chunks: '',
  retryIteration: 0,
  retryMessage: null,
  isComplete: false,
  confidenceScore: null,
  finalDiff: null,
  githubComment: null,
  error: null,
};

export function useFixForgeStream(sessionId: string) {
  const [state, setState] = useState<FixForgeStreamState>(initialState);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;

  const connect = useCallback(() => {
    if (!sessionId) return;
    
    // Clear any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Default to localhost:8000 for FastAPI backend during dev
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const es = new EventSource(`${baseUrl}/api/sessions/${sessionId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('node_start', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        activeNode: data.agent,
        nodes: {
          ...prev.nodes,
          [data.agent]: {
            agent: data.agent,
            status: 'running'
          }
        }
      }));
    });

    es.addEventListener('node_progress', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      if (data.chunk) {
        setState(prev => ({ ...prev, chunks: prev.chunks + data.chunk }));
      }
      if (data.log_line) {
        setState(prev => ({ ...prev, logs: [...prev.logs, data.log_line] }));
      }
    });

    es.addEventListener('node_complete', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        nodes: {
          ...prev.nodes,
          [data.agent]: {
            ...prev.nodes[data.agent],
            status: data.status as 'completed' | 'failed',
            latency: data.latency,
            output: data.output
          }
        },
        chunks: '' // Reset token chunks for next agent
      }));
    });

    es.addEventListener('retry_loop', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        retryIteration: data.iteration,
        retryMessage: data.message
      }));
    });

    es.addEventListener('pipeline_complete', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        isComplete: true,
        finalDiff: data.diff,
        confidenceScore: data.confidenceScore || data.confidence_score,
        githubComment: data.githubComment || data.github_comment
      }));
      es.close(); // Cleanly close connection when complete
    });
    
    es.addEventListener('error', (e: MessageEvent) => {
      const data = e.data ? JSON.parse(e.data) : { detail: 'Unknown streaming error' };
      setState(prev => ({ ...prev, error: data.detail }));
    });

    es.onerror = (error) => {
      console.error("SSE Connection Error:", error);
      es.close();
      
      // Implement Exponential Backoff Reconnection
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(connect, backoffMs);
      } else {
        setState(prev => ({ ...prev, error: 'Connection lost. Max reconnect attempts reached.' }));
      }
    };

    es.onopen = () => {
      reconnectAttemptsRef.current = 0; // Reset counter on successful connection
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
    };
  }, [connect]);

  return state;
}
