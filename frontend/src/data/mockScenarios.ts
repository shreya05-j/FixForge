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
        reason: 'Failed to await async context closure — asyncio.create_task() does not propagate exceptions.',
        diff: `--- a/src/flask/ctx.py
+++ b/src/flask/ctx.py
@@ -412,8 +412,10 @@
         finally:
-            if self.request is not None:
-                self.request.close()
+            if self.request is not None:
+                asyncio.create_task(self.request.close())`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          'collecting ... collected 28 items',
          'FAILED tests/test_async.py::test_async_ctx_teardown',
          'AssertionError: Unhandled exception in background task',
          '1 failed, 27 passed in 1.18s',
        ]
      },
      {
        iteration: 1,
        passed: true,
        diff: `--- a/src/flask/ctx.py
+++ b/src/flask/ctx.py
@@ -412,8 +412,13 @@
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
          'PASSED tests/test_async.py::test_async_ctx_teardown',
          '28 passed in 1.42s',
          'Semgrep: 0 alerts.',
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
        diff: `--- a/requests/utils.py
+++ b/requests/utils.py
@@ -102,6 +102,10 @@
 def check_header_validity(header):
     name, value = header
-    if name.startswith(' '):
-        raise InvalidHeader("Invalid return character or leading space")
+    if re.search(r'\\r|\\n', str(value)):
+        raise InvalidHeader(
+            f"Invalid header value {value!r}: contains CR or LF characters"
+        )
+    if name.startswith(' '):
+        raise InvalidHeader("Invalid return character or leading space")`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          'collecting ... collected 14 items',
          'PASSED tests/test_utils.py::test_header_validity',
          '14 passed in 0.84s',
          'Semgrep static analysis: 0 alerts found.',
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
        reason: 'RecursionError during expression evaluation — infinite loop in eval().',
        diff: `--- a/sympy/functions/elementary/complexes.py
+++ b/sympy/functions/elementary/complexes.py
@@ -23,4 +23,6 @@
     def eval(cls, arg):
+        if arg == S.ComplexInfinity:
+            return S.NaN
         return -arg`,
        logs: [
          'FAILED sympy/tests/test_complexes.py::test_complex_infinity_sub',
          'RecursionError: maximum recursion depth exceeded',
        ]
      },
      {
        iteration: 1,
        passed: false,
        reason: 'Handles is_infinite but subtraction of ComplexInfinity - int still raises.',
        diff: `--- a/sympy/functions/elementary/complexes.py
+++ b/sympy/functions/elementary/complexes.py
@@ -23,4 +23,6 @@
     def eval(cls, arg):
+        if getattr(arg, 'is_infinite', False):
+            return arg
         return -arg`,
        logs: [
          'FAILED sympy/tests/test_complexes.py::test_complex_infinity_sub',
          "TypeError: unsupported operand type(s) for -: 'ComplexInfinity' and 'int'",
        ]
      },
      {
        iteration: 2,
        passed: true,
        diff: `--- a/sympy/functions/elementary/complexes.py
+++ b/sympy/functions/elementary/complexes.py
@@ -23,4 +23,9 @@
     def eval(cls, arg):
+        if arg is S.ComplexInfinity:
+            return S.NaN
+        if getattr(arg, 'is_infinite', False) and arg.is_real:
+            return -arg
+        if getattr(arg, 'is_infinite', False):
+            return S.NaN
         return -arg`,
        logs: [
          'Starting Pytest execution (Sandbox env)...',
          'collecting ... collected 45 items',
          'PASSED sympy/tests/test_complexes.py::test_complex_infinity_sub',
          '45 passed in 4.12s',
          'Semgrep: 0 alerts.',
        ]
      }
    ]
  }
};
