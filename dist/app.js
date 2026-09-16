const $ = selector => document.querySelector(selector);
const fields = $('#conditions');
const cruiseForm = $('#cruise-form');
let worker, ready = false, busy = false, serial = 0, revision = 0, pending = null, latest = null;
let selectedTab = 'calculate';
const format = (n, digits = 0) => Number(n).toLocaleString(undefined, {maximumFractionDigits: digits, minimumFractionDigits: digits});
const node = (tag, text, className) => {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
};
function setStatus(text) { $('#status').textContent = text; }
function buttons() {
  $('#calculate').disabled = !ready || busy;
  document.querySelectorAll('[data-run]').forEach(button => button.disabled = !ready || busy);
  $('#validate').disabled = !ready || busy || !$('#reference-file').files.length;
  $('#export-json').disabled = !latest || busy;
}
function invalidate() {
  revision++;
  latest = null;
  $('#export-csv').disabled = true;
  $('#error').hidden = true;
  if (ready) setStatus('Inputs changed. Run an experiment to update the displayed results.');
  buttons();
}
function launchWorker() {
  worker?.terminate();
  ready = false; busy = false; pending = null; latest = null;
  $('#retry').hidden = true;
  $('#runtime-state').textContent = 'Loading Python…';
  setStatus('Downloading the Python runtime. First load may take a moment.');
  buttons();
  worker = new Worker(new URL('./worker.js', import.meta.url));
  const timer = setTimeout(() => {
    if (!ready) {
      $('#runtime-state').textContent = 'Python is taking longer to load';
      $('#retry').hidden = false;
      setStatus('The first load needs an internet connection. You can retry if it stalls.');
    }
  }, 45000);
  worker.onerror = () => {
    clearTimeout(timer); ready = false; busy = false;
    $('#runtime-state').textContent = 'Python unavailable';
    $('#retry').hidden = false;
    showError('Python could not start. Check your connection, then retry.'); buttons();
  };
  worker.onmessage = ({data}) => {
    if (data.type === 'ready') {
      clearTimeout(timer); ready = true;
      $('#runtime-state').textContent = 'Python ready';
      buttons(); run('snapshot', false); return;
    }
    if (data.type === 'init-error') {
      clearTimeout(timer); ready = false; busy = false;
      $('#runtime-state').textContent = 'Python unavailable';
      $('#retry').hidden = false; showError(data.error); buttons(); return;
    }
    if (data.type !== 'result' || !pending || data.id !== pending.id) return;
    busy = false;
    const experiment = pending; pending = null;
    if (experiment.revision !== revision) {
      setStatus('Inputs changed during calculation. Rerun to see current results.'); buttons(); return;
    }
    if (!data.result.ok) { showError(data.result.error); latest = null; buttons(); return; }
    latest = {action: experiment.action, payload: data.result};
    if (experiment.action === 'snapshot') renderSnapshot(data.result.result);
    if (experiment.action === 'cruise') renderCruise(data.result.result);
    if (experiment.action === 'compare' || experiment.action === 'sensitivity') renderComparison(data.result.result);
    if (experiment.action === 'validate') renderValidation(data.result.result);
    renderWarnings(data.result.result.warnings || [data.result.model.notice]);
    setStatus('Calculation complete. Results reflect the current inputs.');
    buttons();
    if (experiment.scroll && matchMedia('(max-width: 760px)').matches) {
      $('.output-panel').scrollIntoView({behavior: 'smooth', block: 'start'});
    }
  };
}
function showError(message) { $('#error').textContent = message; $('#error').hidden = false; setStatus('Calculation not completed. Check the inputs.'); }
function values(form) {
  const result = {};
  for (const [name, raw] of new FormData(form)) result[name] = raw.trim() === '' ? null : Number(raw);
  return result;
}
function getPayload(action) {
  const input = values(fields);
  return {
    action,
    condition: Object.fromEntries(['mass_kg','altitude_ft','mach','isa_delta_c','headwind_kt','crosswind_kt'].map(k => [k,input[k]])),
    settings: {fuel_scale: input.fuel_scale, drag_scale: input.drag_scale, tsfc_kg_kn_h: input.tsfc},
    thrust_kn: input.thrust_kn,
    cruise: values(cruiseForm),
  };
}
async function run(action, scroll = true) {
  if (!ready || busy) return;
  if (!fields.reportValidity()) return;
  if (['cruise', 'sensitivity'].includes(action) && !cruiseForm.reportValidity()) return;
  const requestRevision = revision;
  const payload = getPayload(action);
  if (!['snapshot','validate'].includes(action) && payload.thrust_kn !== null) {
    showError('Clear manual thrust in Engine & model settings for this experiment.'); return;
  }
  if (action === 'validate') {
    const file = $('#reference-file').files[0];
    if (!file) return;
    if (file.size > 2_000_000) { showError('Use a reference JSON file smaller than 2 MB.'); return; }
    try { payload.dataset = JSON.parse(await file.text()); }
    catch { showError('The selected file is not valid JSON.'); return; }
    if (!Array.isArray(payload.dataset?.records) || payload.dataset.records.length > 5000) {
      showError('Reference data must contain a records array with at most 5,000 observations.'); return;
    }
  }
  if (requestRevision !== revision) { setStatus('Inputs changed while reading the file. Run again.'); return; }
  if (busy) return;
  busy = true; latest = null; $('#export-csv').disabled = true;
  $('#error').hidden = true;
  pending = {id: ++serial, revision, action, scroll};
  setStatus('Calculating in Python…'); buttons();
  worker.postMessage({id: serial, payload});
}
function changeTab(name) {
  selectedTab = name;
  document.querySelectorAll('[data-tab]').forEach(button => {
    const active = button.dataset.tab === name;
    button.classList.toggle('active',active);
    if (active) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.view').forEach(view => view.hidden = view.id !== name + '-view');
}
function renderWarnings(warnings) {
  $('#warnings').replaceChildren(...warnings.map(text => node('li',text)));
}
function renderSnapshot(result) {
  changeTab('calculate');
  $('#fuel').textContent = format(result.fuel_total_kg_h);
  $('#per-mile').textContent = format(result.fuel_kg_nmi,2);
  $('#thrust').textContent = format(result.drag_kn,1);
  $('#groundspeed').textContent = format(result.groundspeed_kt,1);
  $('#engine-name').textContent = result.engine_model.includes('constant') ? '· constant TSFC override' : '· GE90-115B model';
  $('#screening').textContent = result.screening_passed ? 'Research screen passed' : 'Outside research screen';
  $('#screening').classList.toggle('warning',!result.screening_passed);
  const rows = [
    ['True airspeed',format(result.tas_kt,1)+' kt'],['Lift-to-drag ratio',format(result.lift_to_drag,2)],
    ['Outside temperature',format(result.temperature_c,1)+' °C'],['Static pressure',format(result.pressure_hpa,1)+' hPa'],
    ['Per-engine fuel',format(result.fuel_per_engine_kg_h)+' kg/h'],['Applied total thrust',format(result.total_thrust_kn,1)+' kN'],
    ['ISA reference thrust margin',format(result.isa_reference_margin_kn,1)+' kN'],['Lift coefficient',format(result.lift_coefficient,3)],
  ];
  $('#flight-state').replaceChildren(...rows.map(([label,value]) => {
    const row = node('div'); row.append(node('dt',label),node('dd',value)); return row;
  }));
}
function metric(label, value, unit) {
  const card=node('article'); card.append(node('p',label),node('strong',value),node('span',unit)); return card;
}
function renderCruise(result) {
  changeTab('cruise'); $('#cruise-output').hidden = false;
  const last = result.points.at(-1);
  $('#cruise-metrics').replaceChildren(metric('Fuel burned',format(result.fuel_burn_kg),'kg'),metric('Elapsed time',format(last.elapsed_h,2),'hours'),metric('Remaining fuel',format(last.remaining_fuel_kg),'kg'));
  $('#cruise-stop').textContent = result.stop_reason + ' · ' + format(last.distance_nmi,1) + ' / ' + format(result.request.distance_nmi) + ' nmi';
  $('#cruise-stop').classList.toggle('warning',!result.completed);
  chart(result); $('#export-csv').disabled=false;
}
function svgNode(tag, attributes, text) {
  const element=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for (const [key,value] of Object.entries(attributes)) element.setAttribute(key,value);
  if (text !== undefined) element.textContent=text;
  return element;
}
function chart(result) {
  const svg=$('#cruise-chart'); svg.replaceChildren();
  const points=result.points, maxX=Math.max(1,result.request.distance_nmi), maxY=points[0].remaining_fuel_kg/1000*1.08;
  const x = n => 64+n/maxX*610, y=n=>260-n/maxY*220;
  svg.append(svgNode('title',{},'Remaining fuel versus ground distance'),svgNode('desc',{},result.stop_reason));
  for (let tick=0;tick<=4;tick++) {
    const v=maxY*tick/4, yy=y(v);
    svg.append(svgNode('line',{x1:64,x2:674,y1:yy,y2:yy,stroke:'#e1e7ef'}));
    svg.append(svgNode('text',{x:53,y:yy+4,'text-anchor':'end',fill:'#52677f','font-size':14},format(v,0)));
    const xx=maxX*tick/4;
    svg.append(svgNode('text',{x:x(xx),y:284,'text-anchor':'middle',fill:'#52677f','font-size':14},format(xx,0)));
  }
  svg.append(svgNode('text',{x:64,y:20,fill:'#52677f','font-size':14},'Remaining fuel · tonnes'));
  svg.append(svgNode('text',{x:674,y:306,'text-anchor':'end',fill:'#52677f','font-size':14},'Distance · nmi'));
  const path=points.map((p,i)=>(i?'L':'M')+x(p.distance_nmi).toFixed(2)+','+y(p.remaining_fuel_kg/1000).toFixed(2)).join(' ');
  svg.append(svgNode('path',{d:path,fill:'none',stroke:'#215cf0','stroke-width':3}));
  const floor=y(result.request.protected_fuel_kg/1000);
  svg.append(svgNode('line',{x1:64,x2:674,y1:floor,y2:floor,stroke:'#b87727','stroke-width':1.5,'stroke-dasharray':'5 5'}));
}
function renderComparison(result) {
  changeTab('compare'); const rows=result.comparisons || result.sensitivity;
  $('#comparisons').replaceChildren(...rows.map(row=>{
    const card=node('article',undefined,'comparison-row');
    card.append(node('h3',row.scenario || `Fuel model ×${format(row.relative_fuel_factor,2)}`));
    if(row.error){card.append(node('p',row.error));return card;}
    const numbers=node('div',undefined,'comparison-numbers');
    const pairs=row.scenario?[[row.fuel_kg_h,'kg / h',0],[row.fuel_kg_nmi,'kg / nmi',2],[row.groundspeed_kt,'groundspeed · kt',1]]:[[row.fuel_burn_kg,'kg burned',0],[row.distance_nmi,'nmi covered',1]];
    pairs.forEach(([value,unit,digits])=>{const group=node('div');group.append(node('strong',format(value,digits)),node('span',unit));numbers.append(group);});
    card.append(numbers,node('p',row.scenario?(row.screening_passed?'Research screen passed':'Outside research screen'):(row.completed?'Requested distance completed':'Protected fuel floor reached early')));
    return card;
  }));
}
function renderValidation(result) {
  changeTab('evidence'); const output=$('#validation-result'); output.replaceChildren();
  output.append(node('p','Source: '+result.source),node('p','Declared data type: '+result.source_type),node('p','Fitted multiplier: '+format(result.relative_fitted_scale,4)+' × current model. Not automatically applied.'));
  for(const [split,scores] of Object.entries(result.metrics)){
    const card=node('article',undefined,'comparison-row');card.append(node('h3',split.toUpperCase()+' · '+scores.flight_count+' flight(s)'));
    for(const key of ['baseline','fitted']){const score=scores[key];card.append(node('p',`${key}: MAE ${format(score.mae_kg_h,1)} kg/h · RMSE ${format(score.rmse_kg_h,1)} kg/h · MAPE ${format(score.mape_percent,2)}%`));}
    output.append(card);
  }
  output.append(node('p',result.qualification));
}
function download(name, content, type) {
  const url=URL.createObjectURL(new Blob([content],{type}));const link=node('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);
}
fields.addEventListener('submit',event=>{event.preventDefault();run('snapshot');});
cruiseForm.addEventListener('submit',event=>{event.preventDefault();run('cruise');});
document.querySelectorAll('[data-run]').forEach(button=>{if(button.dataset.run !== 'cruise') button.addEventListener('click',()=>run(button.dataset.run));});
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>changeTab(button.dataset.tab)));
fields.addEventListener('input',invalidate);cruiseForm.addEventListener('input',invalidate);
$('#reference-file').addEventListener('change',invalidate);
$('#reset').addEventListener('click',()=>{fields.reset();cruiseForm.reset();invalidate();if(ready&&!busy)run('snapshot',false);});
$('#retry').addEventListener('click',launchWorker);
$('#validate').addEventListener('click',()=>run('validate'));
$('#export-json').addEventListener('click',()=>{if(latest)download('b777-'+latest.action+'.json',JSON.stringify(latest.payload,null,2),'application/json');});
$('#export-csv').addEventListener('click',()=>{
  if(latest?.action!=='cruise')return;
  const points=latest.payload.result.points, keys=Object.keys(points[0]);
  download('b777-cruise.csv',keys.join(',')+'\n'+points.map(p=>keys.map(k=>p[k]).join(',')).join('\n'),'text/csv');
});
launchWorker();
