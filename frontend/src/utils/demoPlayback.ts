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

    // Initial state
    this.onStateUpdate({
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
      error: null
    });

    let cumulativeDelay = 0;
    
    // Simulate each attempt
    this.scenario.attempts.forEach((attempt, attemptIdx) => {
      
      // If it's a retry, add the retry loop event
      if (attemptIdx > 0) {
        this.schedule(() => {
          this.onStateUpdate(prev => ({
            ...prev,
            retryIteration: attemptIdx,
            retryMessage: this.scenario.attempts[attemptIdx - 1].reason || 'Retry requested.',
            logs: [],
            nodes: {},
            activeNode: null,
          }));
        }, cumulativeDelay);
        cumulativeDelay += 1000;
      }

      pipelineOrder.forEach((agent, _idx) => {
        // Start node
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
        
        cumulativeDelay += 500; // Agent processing time

        // Simulate streaming tokens or logs
        if (agent === 'verifier') {
          attempt.logs.forEach((log, _logIdx) => {
            this.schedule(() => {
              this.onStateUpdate(prev => ({
                ...prev,
                logs: [...prev.logs, log]
              }));
            }, cumulativeDelay);
            cumulativeDelay += 400;
          });
        } else if (agent === 'fixer') {
           this.schedule(() => {
              this.onStateUpdate(prev => ({
                ...prev,
                finalDiff: attempt.diff
              }));
           }, cumulativeDelay);
           cumulativeDelay += 500;
        } else {
          cumulativeDelay += 600;
        }

        // Complete node
        const isFailed = agent === 'verifier' && !attempt.passed;
        
        this.schedule(() => {
          this.onStateUpdate(prev => ({
            ...prev,
            nodes: {
              ...prev.nodes,
              [agent]: { 
                agent, 
                status: isFailed ? 'failed' : 'completed',
                latency: Math.floor(Math.random() * 1000) + 200,
                output: { message: `Completed ${agent} successfully.` }
              }
            }
          }));
        }, cumulativeDelay);

        if (isFailed) {
           // Break out of this pipeline run early because it failed
           cumulativeDelay += 1000;
           return; 
        }
      });
    });

    // Final Completion Step
    const lastAttempt = this.scenario.attempts[this.scenario.attempts.length - 1];
    
    this.schedule(() => {
      this.onStateUpdate(prev => ({
        ...prev,
        isComplete: true,
        activeNode: null,
        confidenceScore: this.scenario.confidence,
        finalDiff: lastAttempt.diff
      }));
      this.isPlaying = false;
    }, cumulativeDelay + 1000);
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
