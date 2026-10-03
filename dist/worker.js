/* Python runs away from the UI thread. No user-supplied code is evaluated. */
const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
let runtime;
let localRuntime = false;
async function initialize() {
  if (['127.0.0.1', 'localhost'].includes(self.location.hostname)) {
    try {
      const response = await fetch('/api/runtime', {signal: AbortSignal.timeout(3000)});
      if (response.ok && (await response.json()).runtime === 'cpython-local') {
        localRuntime = true;
        self.postMessage({ type: 'ready', runtime: 'local' });
        return;
      }
    } catch { /* A static local server still uses the browser Python runtime. */ }
  }
  importScripts(PYODIDE_URL + 'pyodide.js');
  runtime = await loadPyodide({ indexURL: PYODIDE_URL });
  runtime.FS.mkdirTree('/lab/b777');
  const files = ['bridge.py', 'b777/__init__.py', 'b777/atmosphere.py', 'b777/engine.py', 'b777/model.py', 'b777/simulation.py', 'b777/validation.py'];
  const contents = await Promise.all(files.map(async path => {
    const response = await fetch(new URL('./python/' + path, self.location.href));
    if (!response.ok) throw new Error('Unable to load Python source: ' + path);
    return [path, await response.text()];
  }));
  for (const [path, source] of contents) runtime.FS.writeFile('/lab/' + path, source);
  runtime.runPython("import sys\nsys.path.insert(0, '/lab')\nfrom bridge import dispatch");
  self.postMessage({ type: 'ready', runtime: 'browser' });
}
const ready = initialize().catch(error => {
  self.postMessage({ type: 'init-error', error: 'Python could not load. Check your internet connection and retry.' });
  throw error;
});
self.onmessage = async ({data}) => {
  try {
    await ready;
    if (localRuntime) {
      const response = await fetch('/api/calculate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data.payload),
      });
      if (!response.ok) throw new Error('Local calculation request failed.');
      self.postMessage({ type: 'result', id: data.id, result: await response.json() });
      return;
    }
    runtime.globals.set('request_json', JSON.stringify(data.payload));
    const result = JSON.parse(runtime.runPython('dispatch(request_json)'));
    runtime.globals.delete('request_json');
    self.postMessage({ type: 'result', id: data.id, result });
  } catch (error) {
    self.postMessage({ type: 'result', id: data.id, result: { ok: false, error: 'Calculation failed. Reload the Python engine and try again.' } });
  }
};
