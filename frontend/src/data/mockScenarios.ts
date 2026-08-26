export interface MockScenario {
  id: string;
  title: string;
  repo: string;
  bug: string;
  taxonomy: string;
  severity: string;
  confidence: number;
  historicalMatch: {
    id: string;
    similarity: number;
    description: string;
    diff: string;
  };
  attempts: {
    iteration: number;
    diff: string;
    logs: string[];
    passed: boolean;
    reason?: string;
  }[];
}

export const mockScenarios: Record<string, MockScenario> = {
  'demo-flask': {
    id: 'demo-flask',
    title: 'pallets/flask #1084',
    repo: 'pallets/flask',
    bug: 'AssertionError: Request context was not preserved across async generator teardown',
    taxonomy: 'Runtime / Concurrency Issue',
    severity: 'Critical',
    confidence: 0.94,
    historicalMatch: {
      id: 'Fix #402',
      similarity: 0.91,
      description: 'Async context teardown handler',
      diff: '- ctx.close()\n+ await ctx.close()'
    },
    attempts: [
      {
        iteration: 0,
        passed: false,
        reason: 'Failed to await asynchronous context closure in finally block.',
        diff: `@@ -412,8 +412,10 @@
         finally:
-            if self.request is not None:
-                self.request.close()
+            if self.request is not None:
+                asyncio.create_task(self.request.close())`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          'collecting ... collected 28 items',
          'test_async_ctx_teardown FAILED',
          'AssertionError: Unhandled exception in background task'
        ]
      },
      {
        iteration: 1,
        passed: true,
        diff: `@@ -412,8 +412,10 @@
         finally:
-            if self.request is not None:
-                self.request.close()
+            if self.request is not None:
+                if inspect.iscoroutinefunction(self.request.close):
+                    asyncio.run(self.request.close())
+                else:
+                    self.request.close()`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          'collecting ... collected 28 items',
          'test_async_ctx_teardown PASSED',
          '28 passed in 1.42s'
        ]
      }
    ]
  },
  'demo-requests': {
    id: 'demo-requests',
    title: 'requests/requests #4349',
    repo: 'requests/requests',
    bug: 'InvalidHeader: Value for header name contains invalid characters on redirect',
    taxonomy: 'Logic / Security Error',
    severity: 'High',
    confidence: 0.98,
    historicalMatch: {
      id: 'Fix #211',
      similarity: 0.89,
      description: 'Header validation stripping CRLF',
      diff: '- if "\\n" in value:\n+ if "\\n" in value or "\\r" in value:'
    },
    attempts: [
      {
        iteration: 0,
        passed: true,
        diff: `@@ -102,4 +102,6 @@
     def check_header_validity(header):
-        if header.startswith(' '):
-            raise InvalidHeader("Invalid return character")
+        if re.search(r'\\r|\\n', header):
+            raise InvalidHeader("Value for header contains invalid characters")
+        if header.startswith(' '):
+            raise InvalidHeader("Invalid return character")`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          'collecting ... collected 14 items',
          '14 passed in 0.84s',
          'Semgrep static analysis: 0 alerts found.'
        ]
      }
    ]
  },
  'demo-sympy': {
    id: 'demo-sympy',
    title: 'sympy/sympy #18059',
    repo: 'sympy/sympy',
    bug: "TypeError: unsupported operand type(s) for -: 'ComplexInfinity' and 'int'",
    taxonomy: 'Syntax / Type Evaluation',
    severity: 'Medium',
    confidence: 0.86,
    historicalMatch: {
      id: 'Fix #1120',
      similarity: 0.82,
      description: 'Type checking for ComplexInfinity expressions',
      diff: '+ if expr.is_infinite:\n+     return S.NaN'
    },
    attempts: [
      {
        iteration: 0,
        passed: false,
        reason: 'RecursionError during expression evaluation',
        diff: `@@ -23,3 +23,4 @@
     def eval(cls, arg):
+        if arg == S.ComplexInfinity:
+            return S.NaN
         return -arg`,
        logs: [
          'test_complex_infinity_sub FAILED',
          'RecursionError: maximum recursion depth exceeded while calling a Python object'
        ]
      },
      {
        iteration: 1,
        passed: false,
        reason: 'Failed to handle subtraction specifically.',
        diff: `@@ -23,3 +23,4 @@
     def eval(cls, arg):
+        if getattr(arg, 'is_infinite', False):
+            return arg
         return -arg`,
        logs: [
          'test_complex_infinity_sub FAILED',
          'TypeError: unsupported operand type(s) for -'
        ]
      },
      {
        iteration: 2,
        passed: true,
        diff: `@@ -23,3 +23,5 @@
     def eval(cls, arg):
+        if arg is S.ComplexInfinity:
+            return S.NaN
+        if arg.is_infinite:
+            return arg
         return -arg`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          '45 passed in 4.12s'
        ]
      }
    ]
  }
};
