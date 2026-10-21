import type { FixForgeStreamState } from '../hooks/useFixForgeStream';
import type { MockScenario } from '../data/mockScenarios';

const pipelineOrder = [
  'planner',
  'retriever',
  'diagnoser',
  'fixer',
  'verifier',
  'confidence_engine',
  'reporter'
];

export class DemoPlaybackEngine {
  private scenario: MockScenario;
  private onStateUpdate: (state: FixForgeStreamState | ((prev: FixForgeStreamState) => FixForgeStreamState)) => void;
  private isPlaying = false;
  private timeouts: ReturnType<typeof setTimeout>[] = [];

  constructor(
    scenario: MockScenario,
    onStateUpdate: (state: FixForgeStreamState | ((prev: FixForgeStreamState) => FixForgeStreamState)) => void
  ) {
    this.scenario = scenario;
    this.onStateUpdate = onStateUpdate;
  }

  public play() {
    if (this.isPlaying) return;
    this.isPlaying = true;
    this.clear();

    // Reset to clean initial state
    this.onStateUpdate({
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
      isDemo: true,
    });

    let cumulativeDelay = 500;

    // Simulate each attempt
    this.scenario.attempts.forEach((attempt, attemptIdx) => {

      // If it's a retry, show retry loop event first
      if (attemptIdx > 0) {
        this.schedule(() => {
          this.onStateUpdate(prev => ({
            ...prev,
            retryIteration: attemptIdx,
            retryMessage: this.scenario.attempts[attemptIdx - 1].reason ?? 'Retry requested by verifier.',
            // Clear logs and nodes for new attempt
            logs: [],
            nodes: {},
            activeNode: null,
            finalDiff: null,  // clear stale diff on retry
          }));
        }, cumulativeDelay);
        cumulativeDelay += 1200;
      }

      pipelineOrder.forEach((agent) => {
        // ── NODE START ────────────────────────────────────────────────────
        this.schedule(() => {
          this.onStateUpdate(prev => ({
            ...prev,
            activeNode: agent,
            nodes: {
              ...prev.nodes,
              [agent]: { agent, status: 'running' }
            }
          }));
        }, cumulativeDelay);
        cumulativeDelay += 600;

        // ── PER-AGENT PROGRESS EVENTS ─────────────────────────────────────
        if (agent === 'fixer') {
          // Stream the diff line by line (typewriter effect)
          const diffLines = attempt.diff.split('\n');
          diffLines.forEach((_, lineIdx) => {
            this.schedule(() => {
              this.onStateUpdate(prev => ({
                ...prev,
                // Build up the diff incrementally for streaming feel
                chunks: attempt.diff.split('\n').slice(0, lineIdx + 1).join('\n'),
              }));
            }, cumulativeDelay + lineIdx * 60);
          });
          cumulativeDelay += diffLines.length * 60 + 300;

        } else if (agent === 'verifier') {
          // Stream each log line with a delay
          attempt.logs.forEach((log, logIdx) => {
            this.schedule(() => {
              this.onStateUpdate(prev => ({
                ...prev,
                logs: [...prev.logs, log]
              }));
            }, cumulativeDelay + logIdx * 350);
          });
          cumulativeDelay += attempt.logs.length * 350 + 300;

        } else if (agent === 'confidence_engine') {
          // Animate confidence score counting up
          const target = this.scenario.confidence;
          const steps = 12;
          for (let s = 1; s <= steps; s++) {
            const partial = parseFloat(((target / steps) * s).toFixed(2));
            this.schedule(() => {
              this.onStateUpdate(prev => ({ ...prev, confidenceScore: partial }));
            }, cumulativeDelay + s * 80);
          }
          cumulativeDelay += steps * 80 + 200;

        } else {
          // Other agents: just a processing pause
          cumulativeDelay += 700;
        }

        // ── NODE COMPLETE ─────────────────────────────────────────────────
        const isFailed = agent === 'verifier' && !attempt.passed;
        this.schedule(() => {
          this.onStateUpdate(prev => ({
            ...prev,
            activeNode: isFailed ? null : prev.activeNode,
            chunks: agent === 'fixer' ? '' : prev.chunks,  // clear streaming chunk
            nodes: {
              ...prev.nodes,
              [agent]: {
                agent,
                status: isFailed ? 'failed' : 'completed',
                latency: Math.floor(Math.random() * 900) + 200,
                output: agent === 'fixer'
                  ? { diff_lines: attempt.diff.split('\n').length }
                  : agent === 'verifier'
                  ? { passed: attempt.passed, tests_run: attempt.logs.length }
                  : agent === 'confidence_engine'
                  ? { score: this.scenario.confidence }
                  : { message: `${agent} completed.` }
              }
            }
          }));
        }, cumulativeDelay);
        cumulativeDelay += 200;

        // If failed, stop this attempt's pipeline
        if (isFailed) {
          cumulativeDelay += 800;
          return;
        }
      });
    });

    // ── PIPELINE COMPLETE ─────────────────────────────────────────────────────
    const lastAttempt = this.scenario.attempts[this.scenario.attempts.length - 1];

    this.schedule(() => {
      this.onStateUpdate(prev => ({
        ...prev,
        isComplete: true,
        activeNode: null,
        confidenceScore: this.scenario.confidence,
        finalDiff: lastAttempt.passed ? lastAttempt.diff : null,
        githubComment: lastAttempt.passed
          ? `FixForge AI verified this patch on \`${this.scenario.repo}\` with ${Math.round(this.scenario.confidence * 100)}% confidence.`
          : null,
        chunks: '',
      }));
      this.isPlaying = false;
    }, cumulativeDelay + 600);
  }

  public stop() {
    this.clear();
    this.isPlaying = false;
  }

  private schedule(fn: () => void, delayMs: number) {
    const t = setTimeout(fn, delayMs);
    this.timeouts.push(t);
  }

  private clear() {
    this.timeouts.forEach(clearTimeout);
    this.timeouts = [];
  }
}
