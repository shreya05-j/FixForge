import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DiffViewer from '../DiffViewer';

const sampleDiff = `--- a/flask/wrappers.py
+++ b/flask/wrappers.py
@@ -10,3 +10,4 @@
 def parse_cookie(header):
-    return header.split(';')
+    if not header:
+        return {}
+    return header.split(';')
`;

describe('DiffViewer Component', () => {
  it('renders awaiting state when no diff and not streaming', () => {
    render(<DiffViewer diff="" isStreaming={false} />);
    expect(screen.getByText(/Awaiting patch generation/i)).toBeDefined();
  });

  it('renders streaming state when isStreaming is true', () => {
    render(<DiffViewer diff="" isStreaming={true} />);
    expect(screen.getByText(/Fixer agent synthesizing patch/i)).toBeDefined();
  });

  it('parses and renders unified diff file headers and lines', () => {
    render(<DiffViewer diff={sampleDiff} />);
    expect(screen.getByText('flask/wrappers.py')).toBeDefined();
    expect(screen.getByText(/1 file changed/i)).toBeDefined();
    expect(screen.getByText(/def parse_cookie/i)).toBeDefined();
  });

  it('switches between unified and split view modes', () => {
    const onViewModeChange = vi.fn();
    render(<DiffViewer diff={sampleDiff} viewMode="unified" onViewModeChange={onViewModeChange} />);
    const splitButton = screen.getByRole('button', { name: /split/i });
    expect(splitButton).toBeDefined();
    fireEvent.click(splitButton);
    expect(onViewModeChange).toHaveBeenCalledWith('split');
  });

  it('invokes onCopy and onDownload handlers', () => {
    const onCopy = vi.fn();
    const onDownload = vi.fn();
    render(<DiffViewer diff={sampleDiff} onCopy={onCopy} onDownload={onDownload} />);

    const copyBtn = screen.getByTitle('Copy diff');
    const downloadBtn = screen.getByTitle('Download .patch file');

    fireEvent.click(copyBtn);
    expect(onCopy).toHaveBeenCalledTimes(1);

    fireEvent.click(downloadBtn);
    expect(onDownload).toHaveBeenCalledTimes(1);
  });
});
