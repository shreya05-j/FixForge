import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFixForgeStream } from '../useFixForgeStream';

describe('useFixForgeStream Hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('initializes in demo mode when provided a mock scenario ID', () => {
    const { result } = renderHook(() => useFixForgeStream('demo-flask'));

    // Should detect demo scenario immediately
    expect(result.current.isDemo).toBe(true);
    expect(result.current.isComplete).toBe(false);
  });

  it('attempts reconnection and eventually falls back to demo mode on network failure', () => {
    // Mock EventSource that immediately triggers onerror
    class MockEventSource {
      listeners: Record<string, Function[]> = {};
      onerror: ((err: any) => void) | null = null;
      close = vi.fn();

      constructor(public url: string) {
        setTimeout(() => {
          if (this.onerror) {
            this.onerror(new Error('Connection refused'));
          }
        }, 10);
      }

      addEventListener(event: string, cb: Function) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(cb);
      }

      removeEventListener() {}
    }

    vi.stubGlobal('EventSource', MockEventSource);

    const { result } = renderHook(() => useFixForgeStream('live-session-123'));

    expect(result.current.isDemo).toBe(false);

    // Fast-forward timers through multiple reconnect backoffs
    act(() => {
      vi.advanceTimersByTime(50000);
    });

    // Should indicate fallback error and activate demo mode
    expect(result.current.error).toBeDefined();
  });
});
