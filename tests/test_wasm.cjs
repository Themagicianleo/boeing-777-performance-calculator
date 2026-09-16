/* Execute the actual Python package in the pinned WebAssembly runtime. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {loadPyodide} = require(process.env.PYODIDE_NODE_MODULE || 'pyodide');
(async () => {
  const py = await loadPyodide();
  const root = path.resolve(__dirname, '..', 'dist', 'python');
  py.FS.mkdirTree('/lab/b777');
  for (const name of ['bridge.py','b777/__init__.py','b777/atmosphere.py','b777/engine.py','b777/model.py','b777/simulation.py','b777/validation.py']) {
    py.FS.writeFile('/lab/'+name,fs.readFileSync(path.join(root,name),'utf8'));
  }
  py.runPython("import sys\nsys.path.insert(0, '/lab')\nfrom bridge import dispatch");
  const call = payload => {py.globals.set('request_json', JSON.stringify(payload));return JSON.parse(py.runPython('dispatch(request_json)'));};
  const snapshot=call({action:'snapshot'});
  assert.equal(snapshot.ok,true);
  assert.ok(snapshot.result.fuel_total_kg_h>10000);
  const cruise=call({action:'cruise',cruise:{distance_nmi:1500}});
  assert.equal(cruise.ok,true); assert.equal(cruise.result.completed,true);
  const stopped=call({action:'cruise',cruise:{distance_nmi:2500}});
  assert.equal(stopped.result.completed,false);
  assert.equal(call({action:'snapshot',condition:{mach:.99}}).ok,false);
  assert.equal(call({action:'compare'}).result.comparisons.length,5);
  assert.equal(call({action:'sensitivity',cruise:{distance_nmi:100}}).result.sensitivity.length,3);
  assert.equal(call({action:'validate',dataset:{aircraft:'B77W',engine:'GE90-115B',source:'Empty',source_type:'measured',records:[]}}).ok,false);
  console.log(JSON.stringify({runtime:py.version,checks:7,status:'passed',fuel_kg_h:snapshot.result.fuel_total_kg_h,cruise_burn_kg:cruise.result.fuel_burn_kg}));
})().catch(error => {console.error(error);process.exitCode=1;});
