const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

// Global state for analysis data
let analysisData = null;
let panel = null;
let statusBarItem = null;
let currentLens = null;
let traceOverlay = false;


function parseTopFiles() {
  // Prefer lens_merged.json for stability; fallback to tour markdown
  try {
    const lens = readJSON('maps/lens_merged.json') || readJSON('maps/lens.json');
    if (lens && lens.functions) {
      const arr = Object.entries(lens.functions).map(([q,m]) => ({file: m.file || '', score: m.error_proximity || 0}));
      const uniq = []; const seen = new Set();
      arr.sort((a,b)=>b.score-a.score);
      for (const it of arr) {
        if (it.file && !seen.has(it.file)) { uniq.push(it.file); seen.add(it.file); }
        if (uniq.length>=3) break;
      }
      if (uniq.length) return uniq;
    }
  } catch {}
  try {
    const md = fs.readFileSync('tours/PR.md', 'utf8');
    const files = [...md.matchAll(/`([^`]+\.py)`/g)].map(m=>m[1]).slice(0,3);
    if (files.length) return files;
  } catch {}
  try {
    const md = fs.readFileSync('tours/local.md', 'utf8');
    const files = [...md.matchAll(/`([^`]+\.py)`/g)].map(m=>m[1]).slice(0,3);
    if (files.length) return files;
  } catch {}
  return [];
}


function parseContractBlock(contractText, moduleFile, fn) {
  // find module block for file, then function block
  const norm = moduleFile.replace(/\\/g,'/');
  const modRe = new RegExp('module:\\s*'+norm.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  const modIdx = contractText.search(modRe);
  if (modIdx === -1) return {pre: [], post: []};
  const after = contractText.slice(modIdx);
  const fnRe = new RegExp('^\\s{2}'+fn+':\\s*$', 'm');
  const m = after.match(fnRe);
  if (!m) return {pre: [], post: []};
  const start = after.indexOf(m[0]) + m[0].length;
  const block = after.slice(start, after.indexOf('\nmodule:', start) !== -1 ? after.indexOf('\nmodule:', start) : after.length);
  const preMatch = block.match(/pre:\s*(\[[^\]]*\])?/);
  const postMatch = block.match(/post:\s*(\[[^\]]*\])?/);
  function parseList(s){ if(!s) return []; const arr = s.replace(/[\[\]]/g,'').split(',').map(x=>x.trim()).filter(Boolean); return arr; }
  return { pre: parseList(preMatch && preMatch[1]), post: parseList(postMatch && postMatch[1]) };
}


function fileExt(p){ const m = p.match(/\.[a-zA-Z0-9]+$/); return m ? m[0].toLowerCase() : ''; }
function readText(p){ try { return fs.readFileSync(p,'utf8'); } catch { return ''; } }

function inferArgsFromSource(moduleFile, fn) {
  const ext = fileExt(moduleFile);
  const src = readText(moduleFile);
  if (!src) return [];
  try {
    if (ext === '.py') {
      const re = new RegExp('^def\\s+'+fn+'\\s*\\(([^)]*)\\)\\s*:', 'm');
      const m = src.match(re);
      if (m) {
        return m[1].split(',').map(s=>s.trim()).filter(Boolean).filter(n=>!n.startsWith('*') && n!=='self');
      }
    } else if (ext === '.ts' || ext === '.tsx' || ext === '.js' || ext === '.jsx') {
      // function fn(a,b) { ... }  OR  const fn = (a,b) => { ... }  OR  export function fn(...)
      let m = src.match(new RegExp('function\\s+'+fn+'\\s*\\(([^)]*)\\)','m'));
      if (!m) m = src.match(new RegExp('const\\s+'+fn+'\\s*=\\s*\\(([^)]*)\\)\\s*=>','m'));
      if (!m) m = src.match(new RegExp('export\\s+function\\s+'+fn+'\\s*\\(([^)]*)\\)','m'));
      if (m) {
        return m[1].split(',').map(s=>s.trim()).filter(Boolean);
      }
    } else if (ext === '.go') {
      // func (r T) fn(a int, b string) ... OR func fn(a, b int)
      let m = src.match(new RegExp('^func\\s*(?:\\([^)]*\\)\\s*)?'+fn+'\\s*\\(([^)]*)\\)', 'm'));
      if (m) {
        const params = m[1];
        // Expand "a, b int" into "a int, b int"
        let expanded = [];
        params.split(',').forEach(part => {
          part = part.trim();
          if (!part) return;
          const mm = part.match(/^([\w\s,]+)\s+([\w\*\[\]]+)$/);
          if (mm) {
            const names = mm[1].split(',').map(s=>s.trim()).filter(Boolean);
            const typ = mm[2];
            names.forEach(n=>expanded.push(n+' '+typ));
          } else {
            expanded.push(part);
          }
        });
        return expanded.map(s=>s.split(/\s+/)[0]).filter(Boolean);
      }
    } else if (ext === '.rs') {
      // fn fn_name(a: i64, b: i64) { ... }
      const m = src.match(new RegExp('fn\\s+'+fn+'\\s*\\(([^)]*)\\)', 'm'));
      if (m) {
        return m[1].split(',').map(s=>s.trim()).filter(Boolean).map(s=>s.split(':')[0].trim());
      }
    }
  } catch {}
  return [];
}


// ---- Types & strategy mapping (Mypy/TS) ----
function scanInlineBounds(src, arg){
  const bounds = {};
  const rxMin = new RegExp('@min\s*\(\s*'+arg+'\s*\)\s*=\s*(-?\d+(?:\.\d+)?)','i');
  const rxMax = new RegExp('@max\s*\(\s*'+arg+'\s*\)\s*=\s*(-?\d+(?:\.\d+)?)','i');
  const m1 = src.match(rxMin); if (m1) bounds.min = Number(m1[1]);
  const m2 = src.match(rxMax); if (m2) bounds.max = Number(m2[1]);
  return bounds;
}
function parseBoundsFromPre(preLines, arg) {
  const out = {};
  const pats = [
    new RegExp(`(\\-?\\d+(?:\\.\\d+)?)\\s*<=\\s*${arg}\\s*<=\\s*(\\-?\\d+(?:\\.\\d+)?)`),
    new RegExp(`${arg}\\s*>=\\s*(\\-?\\d+(?:\\.\\d+)?)`),
    new RegExp(`${arg}\\s*<=\\s*(\\-?\\d+(?:\\.\\d+)?)`),
    new RegExp(`${arg}\\s*in\\s*\\[\\s*(\\-?\\d+(?:\\.\\d+)?)\\s*,\\s*(\\-?\\d+(?:\\.\\d+)?)\\s*\\]`),
  ];
  for (const line of preLines || []) {
    let m;
    if ((m = pats[0].exec(line))) { out.min = Number(m[1]); out.max = Number(m[2]); }
    else if ((m = pats[1].exec(line))) { out.min = Number(m[1]); }
    else if ((m = pats[2].exec(line))) { out.max = Number(m[1]); }
    else if ((m = pats[3].exec(line))) { out.min = Number(m[1]); out.max = Number(m[2]); }
  }
  return out;
}

function parsePythonTypeHints(moduleFile, fn) {
  const src = readText(moduleFile);
  const defRe = new RegExp('^def\\s+'+fn+'\\s*\\(([^)]*)\\)\\s*:', 'm');
  const m = src.match(defRe);
  const types = {};
  if (!m) return types;
  const params = m[1];
  const parts = params.split(',').map(s=>s.trim()).filter(Boolean);
  for (const p of parts) {
    // a: int = 0  |  b: typing.Literal["A","B"]  |  c: Optional[int]
    const mm = p.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^=,]+)(?:=.*)?$/);
    if (mm) {
      const name = mm[1];
      const t = mm[2].trim();
      types[name] = t;
    } else {
      const mm2 = p.match(/^([A-Za-z_][A-Za-z0-9_]*)/);
      if (mm2) types[mm2[1]] = '';
    }
  }
  return types;
}

function pyStrategyFor(typeStr, bounds, enumVals) {
  if (enumVals && enumVals.length) {
    const vals = enumVals.map(v => JSON.stringify(v)).join(', ');
    return `st.sampled_from([${vals}])`;
  }
  const clean = (typeStr||'').toLowerCase();
  if (clean.includes('int')) {
    if (Number.isFinite(bounds.min) || Number.isFinite(bounds.max)) {
      const kw = [];
      if (Number.isFinite(bounds.min)) kw.push(`min_value=${bounds.min}`);
      if (Number.isFinite(bounds.max)) kw.push(`max_value=${bounds.max}`);
      return `st.integers(${kw.join(', ')})`;
    }
    return `st.integers()`;
  }
  if (clean.includes('float') || clean.includes('decimal')) {
    if (Number.isFinite(bounds.min) || Number.isFinite(bounds.max)) {
      const kw = [];
      if (Number.isFinite(bounds.min)) kw.push(`min_value=${bounds.min}`);
      if (Number.isFinite(bounds.max)) kw.push(`max_value=${bounds.max}`);
      kw.push('allow_nan=False'); kw.push('allow_infinity=False');
      return `st.floats(${kw.join(', ')})`;
    }
    return `st.floats(allow_nan=False, allow_infinity=False)`;
  }
  if (clean.includes('bool')) return `st.booleans()`;
  if (clean.includes('str')) return `st.text()`;
  if (clean.includes('list[') || clean.includes('list[')) return `st.lists(st.integers(), max_size=10)`;
  if (clean.includes('dict[')) return `st.dictionaries(st.text(), st.integers(), max_size=5)`;
  return `st.just(None) | st.integers()`; // fallback
}

function parseEnumFromPython(typeStr) {
  // typing.Literal["A","B"] or Literal[1,2]
  const m = (typeStr||'').match(/Literal\\s*\\[\\s*([^\\]]+)\\]/);
  if (!m) return null;
  const parts = m[1].split(',').map(s=>s.trim()).map(s=>s.replace(/^(['"])(.*)\\1$/,'$2'));
  return parts;
}

function parseTSTypes(moduleFile, fn) {
  const src = readText(moduleFile);
  // function fn(a: T, b: U) OR const fn = (a: T, b: U) =>
  let m = src.match(new RegExp('function\\s+'+fn+'\\s*\\(([^)]*)\\)','m'));
  if (!m) m = src.match(new RegExp('const\\s+'+fn+'\\s*=\\s*\\(([^)]*)\\)\\s*=>','m'));
  const out = {};
  if (!m) return out;
  const params = m[1].split(',').map(s=>s.trim()).filter(Boolean);
  for (const p of params) {
    const mm = p.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^=,]+)(?:=.*)?$/);
    if (mm) out[mm[1]] = mm[2].trim();
    else { const mm2 = p.match(/^([A-Za-z_][A-Za-z0-9_]*)/); if (mm2) out[mm2[1]]='number'; }
  }
  return out;
}

function tsStrategyFor(typeStr, bounds, enumVals) {
  if (enumVals && enumVals.length) {
    const vals = enumVals.map(v => JSON.stringify(v)).join(', ');
    return `fc.constantFrom(${vals})`;
  }
  const t = (typeStr||'').trim();
  if (/^number(\[\])?$/.test(t) || t==='number') {
    if (Number.isFinite(bounds.min) || Number.isFinite(bounds.max)) {
      const kv = [];
      if (Number.isFinite(bounds.min)) kv.push(`min: ${bounds.min}`);
      if (Number.isFinite(bounds.max)) kv.push(`max: ${bounds.max}`);
      // Prefer integer if both bounds look integer
      if (Number.isInteger(bounds.min ?? 0) && Number.isInteger(bounds.max ?? 0)) {
        return `fc.integer({ ${kv.join(', ')} })`;
      }
      return `fc.float({ ${kv.join(', ')}, noNaN: true, noDefaultInfinity: true })`;
    }
    return `fc.float({ noNaN: true, noDefaultInfinity: true })`;
  }
  if (/^string(\[\])?$/.test(t) || t==='string') return `fc.string()`;
  if (/^boolean$/.test(t)) return `fc.boolean()`;
  if (/^string\[\]$/.test(t)) return `fc.array(fc.string(), { maxLength: 6 })`;
  if (/^number\[\]$/.test(t)) return `fc.array(fc.integer(), { maxLength: 6 })`;
  return `fc.anything()`;
}

function parseEnumFromTS(typeStr) {
  // "A" | "B" | 1 | 2
  const parts = (typeStr||'').split('|').map(s=>s.trim()).filter(x=>/^(['"].*['"]|[0-9]+)$/.test(x)).map(v=>v.replace(/^(['"])(.*)\\1$/,'$2'));
  if (!parts.length) return null;
  return parts.map(v => (/^[0-9]+$/.test(v) ? Number(v) : v));
}

function deriveStrategies(moduleFile, fn) {
  const cfg = readConfig();
  const ext = fileExt(moduleFile);
  const args = inferArgsFromSource(moduleFile, fn);
  const pre = [];
  const src = readText(moduleFile);
  for (const p of (cfg.contracts_paths||[])) {
    if (!fs.existsSync(p)) continue;
    const txt = fs.readFileSync(p,'utf8');
    const blk = parseContractBlock(txt, moduleFile, fn);
    (blk.pre||[]).forEach(x=>pre.push(x));
  }
  const byArg = {};
  if (ext === '.py') {
    const types = parsePythonTypeHints(moduleFile, fn);
    for (const a of args) {
      const enumVals = parseEnumFromPython(types[a]||'');
      let bounds = parseBoundsFromPre(pre, a);
      const ib = scanInlineBounds(src, a); if (Number.isFinite(ib.min)) bounds.min = ib.min; if (Number.isFinite(ib.max)) bounds.max = ib.max;
      byArg[a] = pyStrategyFor(types[a]||'', bounds, enumVals);
    }
  } else if (ext === '.ts' || ext === '.tsx' || ext === '.js' || ext === '.jsx') {
    const types = parseTSTypes(moduleFile, fn);
    for (const a of args) {
      const enumVals = parseEnumFromTS(types[a]||'');
      let bounds = parseBoundsFromPre(pre, a);
      const ib = scanInlineBounds(src, a); if (Number.isFinite(ib.min)) bounds.min = ib.min; if (Number.isFinite(ib.max)) bounds.max = ib.max;
      byArg[a] = tsStrategyFor(types[a]||'', bounds, enumVals);
    }
  } else {
    for (const a of args) byArg[a] = null;
  }
  return { args, byArg };
}

function guessImportPath(moduleFile){
  let p = moduleFile.replace(/\\/g,'/');
  const ws = (vscode.workspace && vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0]) ? vscode.workspace.workspaceFolders[0].uri.fsPath.replace(/\\/g,'/') : '';
  if (ws && p.startsWith(ws)) p = p.slice(ws.length+1);
  p = p.replace(/\.(ts|tsx|js|jsx)$/, '');
  return './' + p;
}
function templateForLanguageWithStrategies(moduleFile, fn, args, byArg) {
  const ext = fileExt(moduleFile);
  const argList = (args && args.length ? args : ['a','b']);
  if (ext === '.py') {
    const imports = `import importlib.util
import hypothesis.strategies as st
from hypothesis import given, assume`;
    const spec = `spec = importlib.util.spec_from_file_location("m0","${moduleFile.replace('\\','/')}")
m0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m0)  # type: ignore`;
    const strats = argList.map(a => byArg[a] || 'st.integers()').join(', ');
    return `# Auto-generated property test for ${fn} (types→strategies)
${imports}

${spec}

@given(${strats})
def test_property_${fn}(${argList.join(', ')}):
    # TODO: pre-conditions (from contracts/types)
    res = getattr(m0, "${fn}")(${argList.join(', ')})
    # TODO: post-conditions
    assert True
`;
  }
  if (ext === '.ts' || ext === '.tsx' || ext === '.js' || ext === '.jsx') {
    const strats = argList.map(a => byArg[a] || 'fc.anything()').join(', ');
    const importPath = guessImportPath(moduleFile);
    return `// Auto-generated property test for ${fn} (types→strategies)
// npm i -D fast-check
import fc from 'fast-check';

it('property ${fn}', () => {
  return fc.assert(
    fc.property(${strats}, (${argList.join(', ')}) => {
      import { ${fn} } from '${'${importPath}'}';

      // call ${fn}(${argList.join(', ')})
      return true;
    })
  );
});
`;
  }
  // Fallback keeps previous behavior
  return templateForLanguage(moduleFile, fn, argList);
}

function templateForLanguage(moduleFile, fn, args) {
  const ext = fileExt(moduleFile);
  const argListPy = (args.length ? args : ['a','b']).join(', ');
  const argListJS = (args.length ? args : ['a','b']).join(', ');
  const argListGo = (args.length ? args : ['a','b']).map(a=>a+' int').join(', ');
  const argListRs = (args.length ? args : ['a','b']).map(a=>a+': i64').join(', ');

  if (ext === '.py') {
    return `# Auto-generated property test for ${fn} (from contracts)
import importlib.util
import hypothesis.strategies as st
from hypothesis import given, assume

spec = importlib.util.spec_from_file_location("m0","${moduleFile.replace('\\','/')}")
m0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m0)  # type: ignore

# TODO: choose appropriate strategies for inputs
@given(${(args.length?args: ['a','b']).map(_=>'st.integers()').join(', ')})
def test_property_${fn}(${argListPy}):
    # Pre-conditions: fill from contract if needed
${(args.length?args:['a','b']).map(x=>'    # - '+x+' in domain').join('\\n')}
    res = getattr(m0, "${fn}")(${argListPy})
    # Post-conditions: fill from contract
    assert True  # replace with real checks
`;
  } else if (ext === '.ts' || ext === '.tsx' || ext === '.js' || ext === '.jsx') {
    return `// Auto-generated property test for ${fn} (from contracts)
// npm i -D fast-check
import fc from 'fast-check';
// TODO: import the function under test
// import { ${fn} } from '<path-to-module>';

it('property ${fn}', () => {
  return fc.assert(
    fc.property(${(args.length?args:['a','b']).map(_=>'fc.integer()').join(', ')}, (${argListJS}) => {
      // Pre-conditions
${(args.length?args:['a','b']).map(x=>'      // - '+x+' in domain').join('\\n')}
      // const res = ${fn}(${argListJS});
      // Post-conditions
      return true;
    })
  );
});
`;
  } else if (ext === '.go') {
    const pkg = (readText(moduleFile).match(/^package\s+(\w+)/m)||[])[1] || 'main';
    return `// Auto-generated property test for ${fn} (from contracts)
package ${pkg}

import (
  "testing"
  "testing/quick"
)

func TestProperty_${fn}(t *testing.T) {
  f := func(${argListGo}) bool {
    import { ${fn} } from '${'${importPath}'}';

      // call ${fn}(${(args.length?args:['a','b']).join(', ')})
    // _ = ${fn}(${(args.length?args:['a','b']).join(', ')})
    // Post-conditions
    return true
  }
  if err := quick.Check(f, nil); err != nil { t.Error(err) }
}
`;
  } else if (ext === '.rs') {
    return `// Auto-generated property test for ${fn} (from contracts)
// cargo add quickcheck --dev
#[cfg(test)]
mod tests {
    use super::*;
    use quickcheck::quickcheck;

    quickcheck! {
        fn prop_${fn}(${argListRs}) -> bool {
            import { ${fn} } from '${'${importPath}'}';

      // call ${fn}(${(args.length?args:['a','b']).join(', ')})
            // let _ = ${fn}(${(args.length?args:['a','b']).join(', ')});
            // Post-conditions
            true
        }
    }
}
`;
  }
  // Fallback to Python template
  return templateForLanguage(moduleFile.replace(/\.[^.]+$/,".py"), fn, args);
}

function generatePropertyTest(moduleFile, fn) {
  const { args, byArg } = deriveStrategies(moduleFile, fn);
  return templateForLanguageWithStrategies(moduleFile, fn, args, byArg);
}

function openTourWalkthrough() {
  const panel = vscode.window.createWebviewPanel('understandFirstTour', 'Understand-First: Tour Walkthrough', vscode.ViewColumn.One, { enableScripts: true });
  const files = parseTopFiles();
  const cmds = [
    { title: 'Trace Hot Path', cmd: 'workbench.action.terminal.sendSequence', args: { text: 'u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json\u000D' } },
    { title: 'Merge Trace', cmd: 'workbench.action.terminal.sendSequence', args: { text: 'u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json\u000D' } },
    { title: 'Generate Tour', cmd: 'workbench.action.terminal.sendSequence', args: { text: 'u tour maps/lens_merged.json -o tours/local.md\u000D' } }
  ];
  const html = `
  <script>
    const state = { opened: new Set(), ran: new Set() };
    function upd() {
      const o = state.opened.size, r = state.ran.size;
      const totalF = document.querySelectorAll('a[data-file]').length;
      const totalC = document.querySelectorAll('button[data-cmd]').length;
      document.getElementById('progress').textContent = `opened ${o}/${totalF} • ran ${r}/${totalC}`;
    }
  </script>

  <style>body{font:13px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial}.card{border:1px solid #ddd;border-radius:8px;padding:12px;margin:10px 0}</style>
  <h2>10‑Minute Tour</h2>
  <div class="card"><b>Open these files in order:</b><ol>${files.map(f=>`<li><a href="#" data-file="${f}">${f}</a></li>`).join('')}</ol></div>
  <div class="card"><div id="progress" style="float:right;color:#555">opened 0/0 • ran 0/0</div><b>Run these commands:</b>${cmds.map(c=>`<div><button data-cmd="${c.cmd}" data-args='${JSON.stringify(c.args)}'>${c.title}</button></div>`).join('')}</div>
  <div class="card"><button id="openTourMd">Open Tour Markdown</button> <button id="openGlossary">Open Glossary</button></div>
  <script>
    const vscode = acquireVsCodeApi();
    document.querySelectorAll('a[data-file]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();state.opened.add(a.dataset.file);upd();vscode.postMessage({t:'open',file:a.dataset.file});}));
    document.querySelectorAll('button[data-cmd]').forEach(b=>b.addEventListener('click',()=>{state.ran.add(b.dataset.cmd);upd();vscode.postMessage({t:'cmd',cmd:b.dataset.cmd,args:JSON.parse(b.dataset.args)});}));
    document.getElementById('openTourMd').onclick=()=>vscode.postMessage({t:'openTour'});
    document.getElementById('openGlossary').onclick=()=>vscode.postMessage({t:'openGlossary'});
  </script>`;
  panel.webview.html = html;
  panel.webview.onDidReceiveMessage(msg=>{
    if (msg.t==='open') {
      const p = msg.file;
      if (fs.existsSync(p)) vscode.workspace.openTextDocument(p).then(doc=>vscode.window.showTextDocument(doc));
      else vscode.window.showWarningMessage('File not found: '+p);
    } else if (msg.t==='cmd') {
      vscode.commands.executeCommand(msg.cmd, msg.args);
    } else if (msg.t==='openTour') {
      const tour = fs.existsSync('tours/PR.md') ? 'tours/PR.md' : (fs.existsSync('tours/local.md') ? 'tours/local.md' : null);
      if (tour) vscode.workspace.openTextDocument(tour).then(doc=>vscode.window.showTextDocument(doc));
      else vscode.window.showWarningMessage('No tour markdown found.');
    } else if (msg.t==='openGlossary') {
      const p = readConfig().glossary_path || 'docs/glossary.md';
      if (fs.existsSync(p)) vscode.workspace.openTextDocument(p).then(doc=>vscode.window.showTextDocument(doc));
      else vscode.window.showWarningMessage('Glossary not found: '+p);
    }
  });
}

function readJSON(path) { try { return JSON.parse(fs.readFileSync(path, 'utf8')); } catch { return null; } }

function logTTU(ev){ try { const fs = require('fs'); fs.mkdirSync('metrics',{recursive:true}); fs.appendFileSync('metrics/events.jsonl', JSON.stringify({ts: Math.floor(Date.now()/1000), event: ev})+'\n'); } catch(e){} }
function readTextSafe(p){ try { return fs.readFileSync(p, 'utf8'); } catch { return ''; } }
function countContractsFor(fnName) {
  // Look into default contract files
  const paths = ['contracts/contracts.yaml','contracts/contracts_from_openapi.yaml','contracts/contracts_from_proto.yaml'];
  let count = 0;
  for (const p of paths) {
    const txt = readTextSafe(p);
    if (!txt) continue;
    // Count occurrences of a function block header "  name:"
    const re = new RegExp('^\\s{2}'+fnName+'\:', 'mg');
    const matches = txt.match(re);
    if (matches) count += matches.length;
  }
  return count;
}

function getMaps() { logTTU('map_open');
  const repo = readJSON('maps/repo.json') || {functions:{}};
  const lens = readJSON('maps/lens_merged.json') || readJSON('maps/lens.json') || {functions:{}, lens:{seeds:[]}};
  return {repo, lens};
}

function decorateEditor(editor) {
  if (!editor) return;
  if (typeof overlayEnabled !== 'undefined' && !overlayEnabled) { 
    const decType = vscode.window.createTextEditorDecorationType({});
    editor.setDecorations(decType, []);
    return;
  }
  const {repo, lens} = getMaps();
  const text = editor.document.getText();
  // crude multi-language function regex
  const lang = editor.document.languageId;
  let regex = /^def\s+([A-Za-z_][A-Za-z0-9_]*)\(/mg; // python
  if (lang==='javascript' || lang==='typescript') regex = /(function\s+|const\s+)([A-Za-z_][A-Za-z0-9_]*)\s*(\(|=\s*\()/mg;
  if (lang==='go') regex = /^func\s*(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(/mg;
  if (lang==='rust') regex = /^fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/mg;
  if (lang==='java') regex = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{/mg;
  if (lang==='csharp') regex = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{/mg;
  const decType = vscode.window.createTextEditorDecorationType({ after: { margin: '0 0 0 1rem' }});
  const decs = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    const fn = match[1];
    const line = editor.document.positionAt(match.index).line;
    let callers = 0, runtime = false;
    for (const [q, meta] of Object.entries(lens.functions || {})) {
      if ((meta.calls || []).includes(fn)) callers++;
      if (q.endsWith(':'+fn) && meta.runtime_hit) runtime = true;
    }
    const contracts = countContractsFor(fn);
    const abbr = ` [calls:${callers}]${runtime?' [hot]':''}${contracts?` [contracts:${contracts}]`:''}`;
    const range = new vscode.Range(new vscode.Position(line, 0), new vscode.Position(line, 0));
    decs.push({ range, renderOptions: { after: { contentText: abbr }}});
  }
  editor.setDecorations(decType, decs);
}

// CodeLens Provider Class
class UnderstandFirstCodeLensProvider {
  provideCodeLenses(document, token) {
    const codeLenses = [];
    
    if (!analysisData || !analysisData.functions) {
      return codeLenses;
    }

    const text = document.getText();
    const functionRegex = /def\s+(\w+)\s*\(/g;
    let match;

    while ((match = functionRegex.exec(text)) !== null) {
      const functionName = match[1];
      const line = document.lineAt(document.positionAt(match.index).line);
      const range = new vscode.Range(
        document.positionAt(match.index),
        document.positionAt(match.index + match[0].length)
      );

      // Find function data
      const funcData = analysisData.functions[functionName];
      if (funcData) {
        const callers = funcData.callers ? funcData.callers.length : 0;
        const callees = funcData.calls ? funcData.calls.length : 0;
        const complexity = funcData.complexity || 0;
        const sideEffects = funcData.side_effects || [];

        // Create CodeLens for function info
        const infoLens = new vscode.CodeLens(range, {
          title: `📊 ${callers} callers, ${callees} callees, complexity: ${complexity}`,
          command: 'understandFirst.showFunctionDetails',
          arguments: [functionName, funcData]
        });
        codeLenses.push(infoLens);

        // Create CodeLens for actions
        const actionsLens = new vscode.CodeLens(range, {
          title: '🗺️ Open in Map | ➕ Add to Lens',
          command: 'understandFirst.showFunctionActions',
          arguments: [functionName, funcData]
        });
        codeLenses.push(actionsLens);

        // Create CodeLens for side effects
        if (sideEffects.length > 0) {
          const sideEffectsLens = new vscode.CodeLens(range, {
            title: `⚠️ Side effects: ${sideEffects.join(', ')}`,
            command: 'understandFirst.showSideEffects',
            arguments: [functionName, sideEffects]
          });
          codeLenses.push(sideEffectsLens);
        }
      }
    }

    return codeLenses;
  }
}

// Hover Provider Class
class UnderstandFirstHoverProvider {
  provideHover(document, position, token) {
    if (!analysisData || !analysisData.functions) {
      return null;
    }

    const range = document.getWordRangeAtPosition(position);
    if (!range) {
      return null;
    }

    const word = document.getText(range);
    const funcData = analysisData.functions[word];

    if (!funcData) {
      return null;
    }

    const callers = funcData.callers ? funcData.callers.length : 0;
    const callees = funcData.calls ? funcData.calls.length : 0;
    const complexity = funcData.complexity || 0;
    const sideEffects = funcData.side_effects || [];
    const isHotPath = funcData.is_hot_path || false;
    const lastTouched = funcData.last_touched_pr || 'Unknown';

    const hoverContent = new vscode.MarkdownString();
    hoverContent.appendMarkdown(`## ${word}\n\n`);
    hoverContent.appendMarkdown(`**File:** ${funcData.file || 'Unknown'}\n`);
    hoverContent.appendMarkdown(`**Line:** ${funcData.line || 'Unknown'}\n\n`);
    
    hoverContent.appendMarkdown(`**Callers:** ${callers}\n`);
    hoverContent.appendMarkdown(`**Callees:** ${callees}\n`);
    hoverContent.appendMarkdown(`**Complexity:** ${complexity}\n\n`);
    
    if (sideEffects.length > 0) {
      hoverContent.appendMarkdown(`**Side Effects:** ${sideEffects.join(', ')}\n\n`);
    }
    
    if (isHotPath) {
      hoverContent.appendMarkdown(`🔥 **Hot Path**\n\n`);
    }
    
    hoverContent.appendMarkdown(`**Last Touched:** ${lastTouched}\n\n`);
    
    hoverContent.appendMarkdown(`[Open in Map](command:understandFirst.openInMap?${encodeURIComponent(JSON.stringify({functionName: word, filePath: funcData.file}))}) | [Add to Lens](command:understandFirst.addToLens?${encodeURIComponent(JSON.stringify({functionName: word, filePath: funcData.file}))})`);

    return new vscode.Hover(hoverContent);
  }
}

// Panel Management
function createPanel() {
  if (panel) {
    panel.reveal();
    return;
  }

  panel = vscode.window.createWebviewPanel(
    'understandFirstPanel',
    'Understand-First Analysis',
    vscode.ViewColumn.Two,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: []
    }
  );

  panel.webview.html = getWebviewContent();

  panel.onDidDispose(() => {
    panel = null;
  });

  // Handle messages from webview
  panel.webview.onDidReceiveMessage(
    message => {
      switch (message.command) {
        case 'scanRepo':
          scanRepository();
          break;
        case 'generateTour':
          generateTourFromSelection();
          break;
        case 'openPRSnippet':
          openPRSnippet();
          break;
        case 'toggleOverlay':
          toggleTraceOverlay();
          break;
        case 'updateLens':
          updateLens(message.lens);
          break;
      }
    },
    undefined,
    context.subscriptions
  );
}

function getWebviewContent() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Understand-First Analysis</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
            margin: 0;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 6px;
            padding: 15px;
            text-align: center;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        .metric-label {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .section {
            margin-bottom: 20px;
        }
        .section h3 {
            margin: 0 0 10px 0;
            color: var(--vscode-foreground);
        }
        .function-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .function-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            margin: 4px 0;
            background: var(--vscode-list-hoverBackground);
            border-radius: 4px;
            cursor: pointer;
        }
        .function-item:hover {
            background: var(--vscode-list-activeSelectionBackground);
        }
        .function-name {
            font-family: var(--vscode-editor-font-family);
            font-weight: 500;
        }
        .function-metrics {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
        }
        .button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin: 4px;
        }
        .button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--vscode-charts-green);
        }
        .status-text {
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>🧠 Understand-First Analysis</h2>
        <div>
            <button class="button" onclick="scanRepo()">Scan Repo</button>
            <button class="button" onclick="generateTour()">Generate Tour</button>
            <button class="button" onclick="openPRSnippet()">PR Snippet</button>
        </div>
    </div>

    <div class="status">
        <div class="status-indicator" id="statusIndicator"></div>
        <div class="status-text" id="statusText">Loading analysis...</div>
    </div>

    <div class="metrics" id="metrics">
        <!-- Metrics will be populated by JavaScript -->
    </div>

    <div class="section">
        <h3>Hot Paths</h3>
        <div class="function-list" id="hotPaths">
            <!-- Hot paths will be populated by JavaScript -->
        </div>
    </div>

    <div class="section">
        <h3>High Complexity Functions</h3>
        <div class="function-list" id="highComplexity">
            <!-- High complexity functions will be populated by JavaScript -->
        </div>
    </div>

    <div class="section">
        <h3>Side Effects</h3>
        <div class="function-list" id="sideEffects">
            <!-- Side effects will be populated by JavaScript -->
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        
        function scanRepo() {
            vscode.postMessage({ command: 'scanRepo' });
        }
        
        function generateTour() {
            vscode.postMessage({ command: 'generateTour' });
        }
        
        function openPRSnippet() {
            vscode.postMessage({ command: 'openPRSnippet' });
        }
        
        function toggleOverlay() {
            vscode.postMessage({ command: 'toggleOverlay' });
        }
        
        function updateMetrics(data) {
            const metricsContainer = document.getElementById('metrics');
            metricsContainer.innerHTML = \`
                <div class="metric-card">
                    <div class="metric-value">\${data.totalFunctions || 0}</div>
                    <div class="metric-label">Functions</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">\${data.avgComplexity || 0}</div>
                    <div class="metric-label">Avg Complexity</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">\${data.sideEffectCount || 0}</div>
                    <div class="metric-label">Side Effects</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">\${data.hotPathCount || 0}</div>
                    <div class="metric-label">Hot Paths</div>
                </div>
            \`;
        }
        
        function updateFunctionList(containerId, functions, titleKey = 'name') {
            const container = document.getElementById(containerId);
            container.innerHTML = functions.map(func => \`
                <div class="function-item" onclick="openFunction('\${func.name}')">
                    <div class="function-name">\${func[titleKey]}</div>
                    <div class="function-metrics">
                        Complexity: \${func.complexity || 0} | 
                        Callers: \${func.callers?.length || 0} | 
                        Callees: \${func.calls?.length || 0}
                    </div>
                </div>
            \`).join('');
        }
        
        function openFunction(functionName) {
            vscode.postMessage({ 
                command: 'openFunction', 
                functionName: functionName 
            });
        }
        
        // Initialize with current analysis data
        window.addEventListener('load', () => {
            // This would be populated with actual analysis data
            updateMetrics({
                totalFunctions: 0,
                avgComplexity: 0,
                sideEffectCount: 0,
                hotPathCount: 0
            });
        });
    </script>
</body>
</html>`;
}

// Helper functions
function loadAnalysisData() {
  try {
    const analysisPath = path.join(vscode.workspace.workspaceFolders[0].uri.fsPath, 'maps', 'analysis.json');
    if (fs.existsSync(analysisPath)) {
      const data = fs.readFileSync(analysisPath, 'utf8');
      analysisData = JSON.parse(data);
      updateStatusBar();
    }
  } catch (error) {
    console.error('Failed to load analysis data:', error);
  }
}

function updateStatusBar() {
  if (statusBarItem && analysisData) {
    const functionCount = analysisData.functions ? Object.keys(analysisData.functions).length : 0;
    statusBarItem.text = `$(search) ${functionCount} functions`;
  }
}

function openFunctionInMap(functionName, filePath) {
  // Implementation for opening function in map
  vscode.window.showInformationMessage(`Opening ${functionName} in map...`);
}

function addFunctionToLens(functionName, filePath) {
  // Implementation for adding function to lens
  vscode.window.showInformationMessage(`Adding ${functionName} to lens...`);
}

function scanRepository() {
  vscode.window.withProgress({
    location: vscode.ProgressLocation.Notification,
    title: "Scanning repository...",
    cancellable: false
  }, async (progress) => {
    return new Promise((resolve, reject) => {
      exec('u scan', { cwd: vscode.workspace.workspaceFolders[0].uri.fsPath }, (error, stdout, stderr) => {
        if (error) {
          vscode.window.showErrorMessage(`Scan failed: ${error.message}`);
          reject(error);
        } else {
          loadAnalysisData();
          vscode.window.showInformationMessage('Repository scan completed!');
          resolve();
        }
      });
    });
  });
}

function generateTourFromSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('No active editor');
    return;
  }

  const selection = editor.selection;
  const selectedText = editor.document.getText(selection);
  
  if (!selectedText.trim()) {
    vscode.window.showWarningMessage('No text selected');
    return;
  }

  vscode.window.showInformationMessage('Generating tour from selection...');
}

function openPRSnippet() {
  vscode.window.showInformationMessage('Opening PR snippet...');
}

function toggleTraceOverlay() {
  traceOverlay = !traceOverlay;
  vscode.window.showInformationMessage(`Trace overlay ${traceOverlay ? 'enabled' : 'disabled'}`);
}

function updateLens(lens) {
  currentLens = lens;
  vscode.window.showInformationMessage('Lens updated');
}

function activate(context) {
  // Initialize status bar
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.text = "$(search) Understand-First";
  statusBarItem.command = 'understandFirst.openPanel';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Load analysis data
  loadAnalysisData();

  // Register CodeLens provider
  const codeLensProvider = new UnderstandFirstCodeLensProvider();
  context.subscriptions.push(vscode.languages.registerCodeLensProvider(
    { scheme: 'file', language: 'python' },
    codeLensProvider
  ));

  // Register hover provider
  const hoverProvider = new UnderstandFirstHoverProvider();
  context.subscriptions.push(vscode.languages.registerHoverProvider(
    { scheme: 'file', language: 'python' },
    hoverProvider
  ));

  // Register commands
  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showTour', function () { 
    logTTU('tour_run'); 
    openTourWalkthrough(); 
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.explainErrorPropagation', function () {
    const {lens} = getMaps();
    const seeds = lens.lens ? lens.lens.seeds : [];
    vscode.window.showInformationMessage('Seeds: ' + seeds.join(', ') + ' — follow calls toward these seeds.');
  }));

  // Enhanced commands for new features
  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.openInMap', function (args) {
    logTTU('map_open_from_codelens');
    openFunctionInMap(args.functionName, args.filePath);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.addToLens', function (args) {
    logTTU('lens_add_from_codelens');
    addFunctionToLens(args.functionName, args.filePath);
  }));

  // Panel commands
  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.openPanel', function () {
    createPanel();
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showFunctionDetails', function (functionName, funcData) {
    vscode.window.showInformationMessage(`Function: ${functionName}, Complexity: ${funcData.complexity || 0}`);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showFunctionActions', function (functionName, funcData) {
    const actions = ['Open in Map', 'Add to Lens', 'Show Details'];
    vscode.window.showQuickPick(actions).then(selected => {
      if (selected === 'Open in Map') {
        openFunctionInMap(functionName, funcData.file);
      } else if (selected === 'Add to Lens') {
        addFunctionToLens(functionName, funcData.file);
      } else if (selected === 'Show Details') {
        vscode.window.showInformationMessage(`Function: ${functionName}, Complexity: ${funcData.complexity || 0}`);
      }
    });
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showSideEffects', function (functionName, sideEffects) {
    vscode.window.showInformationMessage(`Side effects in ${functionName}: ${sideEffects.join(', ')}`);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.scanRepo', function () {
    logTTU('repo_scan');
    scanRepository();
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.generateTour', function (args) {
    logTTU('tour_generate_from_selection');
    generateTourFromSelection(args);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.openPRSnippet', function () {
    logTTU('pr_snippet_generate');
    generatePRSnippet();
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.openPanel', function () {
    logTTU('panel_open');
    openUnderstandingPanel();
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.refreshPanel', function () {
    logTTU('panel_refresh');
    refreshUnderstandingPanel();
  }));

  // Enhanced command handlers
  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showFunctionDetails', function (args) {
    logTTU('function_details_show');
    showFunctionDetails(args.functionName, args.filePath);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showCallers', function (args) {
    logTTU('callers_show');
    showCallers(args.functionName, args.filePath);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showCallees', function (args) {
    logTTU('callees_show');
    showCallees(args.functionName, args.filePath);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showHotPath', function (args) {
    logTTU('hot_path_show');
    showHotPathAnalysis(args.functionName, args.filePath);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.analyzeFunction', function (args) {
    logTTU('function_analyze');
    analyzeFunction(args.functionName, args.filePath);
  }));

  // Register CodeLens provider
  context.subscriptions.push(vscode.languages.registerCodeLensProvider(
    { scheme: 'file', language: 'python' },
    new UnderstandFirstCodeLensProvider()
  ));

  // Register hover provider
  context.subscriptions.push(vscode.languages.registerHoverProvider(
    { scheme: 'file', language: 'python' },
    new UnderstandFirstHoverProvider()
  ));

  // Register status bar item
  const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.text = "$(eye) UF";
  statusBarItem.tooltip = "Understand-First: Click to toggle overlay";
  statusBarItem.command = 'understandFirst.toggleOverlay';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Register overlay toggle command
  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.toggleOverlay', function () {
    overlayEnabled = !overlayEnabled;
    statusBarItem.text = overlayEnabled ? "$(eye) UF" : "$(eye-closed) UF";
    decorateEditor(vscode.window.activeTextEditor);
    logTTU('overlay_toggled');
  }));

  // Initialize overlay state
  overlayEnabled = true;

  // Enhanced editor decoration with live sync
  decorateEditor(vscode.window.activeTextEditor);
  vscode.window.onDidChangeActiveTextEditor(decorateEditor);
  vscode.workspace.onDidChangeTextDocument(() => decorateEditor(vscode.window.activeTextEditor));
  
  // Live map sync - refresh decorations when maps change
  const watcher = vscode.workspace.createFileSystemWatcher('maps/**/*.json');
  watcher.onDidChange(() => {
    decorateEditor(vscode.window.activeTextEditor);
    updateStatusBar(statusBarItem);
  });
  context.subscriptions.push(watcher);

  // Update status bar with current lens info
  updateStatusBar(statusBarItem);
}

class UnderstandFirstCodeLensProvider {
  provideCodeLenses(document, token) {
    const {repo, lens} = getMaps();
    const codeLenses = [];
    const text = document.getText();
    
    // Enhanced function detection for multiple languages
    const lang = document.languageId;
    let functionRegex;
    
    if (lang === 'python') {
      functionRegex = /^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm;
    } else if (lang === 'javascript' || lang === 'typescript') {
      functionRegex = /(?:function\s+|const\s+|let\s+|var\s+)([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|=\s*\()/gm;
    } else if (lang === 'go') {
      functionRegex = /^func\s*(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm;
    } else if (lang === 'rust') {
      functionRegex = /^fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm;
    } else if (lang === 'java') {
      functionRegex = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{/gm;
    } else if (lang === 'csharp') {
      functionRegex = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{/gm;
    } else {
      // Fallback to Python regex
      functionRegex = /^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm;
    }
    
    let match;
    
    while ((match = functionRegex.exec(text)) !== null) {
      const functionName = match[1];
      const line = document.lineAt(document.positionAt(match.index).line);
      const range = new vscode.Range(line.range.start, line.range.end);
      
      // Get function metadata
      const funcKey = `${document.fileName}:${functionName}`;
      const funcMeta = lens.functions[funcKey] || repo.functions[funcKey];
      
      if (funcMeta) {
        const callersCount = (funcMeta.callers || []).length;
        const calleesCount = (funcMeta.calls || []).length;
        const complexity = funcMeta.complexity || 0;
        const sideEffects = funcMeta.side_effects || [];
        const runtimeHit = funcMeta.runtime_hit;
        const contracts = countContractsFor(functionName);
        
        // Enhanced main CodeLens with better formatting
        let summary = `📊 ${callersCount}→${calleesCount} calls`;
        if (complexity > 0) summary += ` | ${complexity} complexity`;
        if (sideEffects.length > 0) summary += ` | ${sideEffects.length} side effects`;
        if (contracts > 0) summary += ` | ${contracts} contracts`;
        if (runtimeHit) summary += ` | 🔥 hot path`;
        
        codeLenses.push(new vscode.CodeLens(range, {
          title: summary,
          command: 'understandFirst.showFunctionDetails',
          arguments: [{ functionName, filePath: document.fileName }]
        }));
        
        // Enhanced secondary CodeLenses for actions
        codeLenses.push(new vscode.CodeLens(range, {
          title: "🗺️ Open in Map",
          command: 'understandFirst.openInMap',
          arguments: [{ functionName, filePath: document.fileName }]
        }));
        
        codeLenses.push(new vscode.CodeLens(range, {
          title: "🎯 Add to Lens",
          command: 'understandFirst.addToLens',
          arguments: [{ functionName, filePath: document.fileName }]
        }));
        
        codeLenses.push(new vscode.CodeLens(range, {
          title: "📖 Generate Tour",
          command: 'understandFirst.generateTour',
          arguments: [{ functionName, filePath: document.fileName }]
        }));
        
        if (callersCount > 0) {
          codeLenses.push(new vscode.CodeLens(range, {
            title: `👥 Show Callers (${callersCount})`,
            command: 'understandFirst.showCallers',
            arguments: [{ functionName, filePath: document.fileName }]
          }));
        }
        
        if (calleesCount > 0) {
          codeLenses.push(new vscode.CodeLens(range, {
            title: `🔗 Show Callees (${calleesCount})`,
            command: 'understandFirst.showCallees',
            arguments: [{ functionName, filePath: document.fileName }]
          }));
        }
        
        if (funcMeta.runtime_hit) {
          codeLenses.push(new vscode.CodeLens(range, {
            title: "🔥 Hot Path Analysis",
            command: 'understandFirst.showHotPath',
            arguments: [{ functionName, filePath: document.fileName }]
          }));
        }
      } else {
        // Show basic CodeLens for functions not in maps
        codeLenses.push(new vscode.CodeLens(range, {
          title: "🔍 Analyze Function",
          command: 'understandFirst.analyzeFunction',
          arguments: [{ functionName, filePath: document.fileName }]
        }));
      }
    }
    
    return codeLenses;
  }
}

class UnderstandFirstHoverProvider {
  provideHover(document, position, token) {
    const {repo, lens} = getMaps();
    const wordRange = document.getWordRangeAtPosition(position);
    if (!wordRange) return null;
    
    const word = document.getText(wordRange);
    const line = document.lineAt(position).text;
    const lang = document.languageId;
    
    // Enhanced function detection for multiple languages
    let funcDefRegex, funcCallRegex;
    
    if (lang === 'python') {
      funcDefRegex = new RegExp(`^def\\s+${word}\\s*\\(`);
      funcCallRegex = new RegExp(`\\b${word}\\s*\\(`);
    } else if (lang === 'javascript' || lang === 'typescript') {
      funcDefRegex = new RegExp(`(?:function\\s+|const\\s+|let\\s+|var\\s+)${word}\\s*(?:\\(|=\\s*\\()`);
      funcCallRegex = new RegExp(`\\b${word}\\s*\\(`);
    } else if (lang === 'go') {
      funcDefRegex = new RegExp(`^func\\s*(?:\\([^)]*\\)\\s*)?${word}\\s*\\(`);
      funcCallRegex = new RegExp(`\\b${word}\\s*\\(`);
    } else if (lang === 'rust') {
      funcDefRegex = new RegExp(`^fn\\s+${word}\\s*\\(`);
      funcCallRegex = new RegExp(`\\b${word}\\s*\\(`);
    } else if (lang === 'java' || lang === 'csharp') {
      funcDefRegex = new RegExp(`\\b${word}\\s*\\([^)]*\\)\\s*\\{`);
      funcCallRegex = new RegExp(`\\b${word}\\s*\\(`);
    } else {
      // Fallback to Python
      funcDefRegex = new RegExp(`^def\\s+${word}\\s*\\(`);
      funcCallRegex = new RegExp(`\\b${word}\\s*\\(`);
    }
    
    if (funcDefRegex.test(line) || funcCallRegex.test(line)) {
      const funcKey = `${document.fileName}:${word}`;
      const funcMeta = lens.functions[funcKey] || repo.functions[funcKey];
      
      if (funcMeta) {
        const callersCount = (funcMeta.callers || []).length;
        const calleesCount = (funcMeta.calls || []).length;
        const complexity = funcMeta.complexity || 0;
        const sideEffects = funcMeta.side_effects || [];
        const runtimeHit = funcMeta.runtime_hit;
        const contracts = countContractsFor(word);
        const lines = funcMeta.lines || 0;
        
        let hoverContent = `**${word}()**\n\n`;
        
        // Enhanced call analysis
        hoverContent += `📊 **Call Analysis**\n`;
        hoverContent += `• **Callers**: ${callersCount}\n`;
        hoverContent += `• **Callees**: ${calleesCount}\n`;
        hoverContent += `• **Complexity**: ${complexity}\n`;
        hoverContent += `• **Lines**: ${lines}\n\n`;
        
        // Side effects section
        if (sideEffects.length > 0) {
          hoverContent += `⚠️ **Side Effects**\n`;
          sideEffects.forEach(effect => {
            hoverContent += `• ${effect}\n`;
          });
          hoverContent += '\n';
        }
        
        // Runtime analysis
        if (runtimeHit) {
          hoverContent += `🔥 **Runtime Hot Path**\n`;
          hoverContent += `This function was called during runtime tracing.\n\n`;
        }
        
        // Contracts section
        if (contracts > 0) {
          hoverContent += `📋 **Contracts**\n`;
          hoverContent += `• ${contracts} contract(s) defined\n\n`;
        }
        
        // File information
        hoverContent += `📁 **File**: ${document.fileName}\n`;
        hoverContent += `📝 **Line**: ${position.line + 1}\n\n`;
        
        // Action hints
        hoverContent += `*Use CodeLens actions to explore this function in the map, add it to your understanding lens, or generate a tour.*`;
        
        return new vscode.Hover(new vscode.MarkdownString(hoverContent));
      } else {
        // Show basic hover for functions not in maps
        let hoverContent = `**${word}()**\n\n`;
        hoverContent += `🔍 **Not analyzed yet**\n`;
        hoverContent += `This function hasn't been analyzed by Understand-First.\n\n`;
        hoverContent += `*Use CodeLens actions to analyze this function.*`;
        
        return new vscode.Hover(new vscode.MarkdownString(hoverContent));
      }
    }
    
    return null;
  }
}

function openFunctionInMap(functionName, filePath) {
  // This would integrate with the web demo or open a map view
  vscode.window.showInformationMessage(`Opening ${functionName} in map view...`);
  logTTU('map_open_from_codelens');
}

function addFunctionToLens(functionName, filePath) {
  // Add function to current lens
  const {lens} = getMaps();
  if (!lens.lens) {
    lens.lens = { seeds: [] };
  }
  
  const funcKey = `${filePath}:${functionName}`;
  if (!lens.lens.seeds.includes(funcKey)) {
    lens.lens.seeds.push(funcKey);
    vscode.window.showInformationMessage(`Added ${functionName} to understanding lens`);
    logTTU('lens_add_from_codelens');
  } else {
    vscode.window.showInformationMessage(`${functionName} is already in the lens`);
  }
}

function scanRepository() {
  const terminal = vscode.window.createTerminal('Understand-First Scan');
  terminal.sendText('u scan . -o maps/repo.json --verbose');
  terminal.show();
  logTTU('repo_scan');
}

function generateTourFromSelection(args) {
  const terminal = vscode.window.createTerminal('Understand-First Tour');
  terminal.sendText(`u lens from-seeds --map maps/repo.json --seed ${args.functionName} -o maps/lens.json`);
  terminal.sendText('u tour maps/lens.json -o tours/generated.md');
  terminal.show();
  logTTU('tour_generate_from_selection');
}

function generatePRSnippet() {
  const {lens} = getMaps();
  if (!lens.functions || Object.keys(lens.functions).length === 0) {
    vscode.window.showWarningMessage('No lens data available. Run "u scan" and "u lens" first.');
    return;
  }
  
  const snippet = generatePRCommentSnippet(lens);
  vscode.env.clipboard.writeText(snippet);
  vscode.window.showInformationMessage('PR snippet copied to clipboard!');
  logTTU('pr_snippet_generate');
}

function generatePRCommentSnippet(lens) {
  const functions = Object.keys(lens.functions);
  const addedCount = functions.length;
  
  let snippet = `## 📊 Understanding Analysis\n\n`;
  snippet += `**Functions analyzed**: ${addedCount}\n\n`;
  
  if (addedCount > 0) {
    snippet += `### 🔍 Key Functions\n`;
    functions.slice(0, 5).forEach(func => {
      const meta = lens.functions[func];
      const complexity = meta.complexity || 0;
      const sideEffects = meta.side_effects || [];
      snippet += `• \`${func}\` (complexity: ${complexity}${sideEffects.length ? `, side effects: ${sideEffects.length}` : ''})\n`;
    });
    snippet += '\n';
  }
  
  snippet += `### ✅ Reviewer Checklist\n`;
  snippet += `- [ ] I have read the understanding tour\n`;
  snippet += `- [ ] I understand the side effects and complexity\n`;
  snippet += `- [ ] I have verified the changes align with the analysis\n\n`;
  
  snippet += `*Generated by Understand-First*`;
  
  return snippet;
}

function updateStatusBar(statusBarItem) {
  const {lens} = getMaps();
  if (lens && lens.lens && lens.lens.seeds) {
    const seedsCount = lens.lens.seeds.length;
    statusBarItem.text = `$(eye) UF:${seedsCount}`;
    statusBarItem.tooltip = `Understand-First: ${seedsCount} functions in lens`;
  } else {
    statusBarItem.text = "$(eye) UF";
    statusBarItem.tooltip = "Understand-First: Click to toggle overlay";
  }
}

// Enhanced function implementations
function showFunctionDetails(functionName, filePath) {
  const {repo, lens} = getMaps();
  const funcKey = `${filePath}:${functionName}`;
  const funcMeta = lens.functions[funcKey] || repo.functions[funcKey];
  
  if (!funcMeta) {
    vscode.window.showWarningMessage(`Function ${functionName} not found in analysis data.`);
    return;
  }
  
  const callersCount = (funcMeta.callers || []).length;
  const calleesCount = (funcMeta.calls || []).length;
  const complexity = funcMeta.complexity || 0;
  const sideEffects = funcMeta.side_effects || [];
  const runtimeHit = funcMeta.runtime_hit;
  const contracts = countContractsFor(functionName);
  const lines = funcMeta.lines || 0;
  
  let details = `**${functionName}()** - Function Details\n\n`;
  details += `📊 **Analysis Summary**\n`;
  details += `• Callers: ${callersCount}\n`;
  details += `• Callees: ${calleesCount}\n`;
  details += `• Complexity: ${complexity}\n`;
  details += `• Lines: ${lines}\n`;
  details += `• Contracts: ${contracts}\n`;
  details += `• Hot Path: ${runtimeHit ? 'Yes' : 'No'}\n\n`;
  
  if (sideEffects.length > 0) {
    details += `⚠️ **Side Effects**\n`;
    sideEffects.forEach(effect => {
      details += `• ${effect}\n`;
    });
    details += '\n';
  }
  
  if (funcMeta.callers && funcMeta.callers.length > 0) {
    details += `👥 **Callers**\n`;
    funcMeta.callers.slice(0, 5).forEach(caller => {
      details += `• ${caller}\n`;
    });
    if (funcMeta.callers.length > 5) {
      details += `• ... and ${funcMeta.callers.length - 5} more\n`;
    }
    details += '\n';
  }
  
  if (funcMeta.calls && funcMeta.calls.length > 0) {
    details += `🔗 **Callees**\n`;
    funcMeta.calls.slice(0, 5).forEach(callee => {
      details += `• ${callee}\n`;
    });
    if (funcMeta.calls.length > 5) {
      details += `• ... and ${funcMeta.calls.length - 5} more\n`;
    }
    details += '\n';
  }
  
  details += `📁 **File**: ${filePath}\n`;
  details += `📝 **Line**: ${funcMeta.line || 'Unknown'}\n\n`;
  
  details += `*Use the panel to explore this function further or generate a tour.*`;
  
  vscode.window.showInformationMessage(details);
}

function showCallers(functionName, filePath) {
  const {repo, lens} = getMaps();
  const funcKey = `${filePath}:${functionName}`;
  const funcMeta = lens.functions[funcKey] || repo.functions[funcKey];
  
  if (!funcMeta || !funcMeta.callers || funcMeta.callers.length === 0) {
    vscode.window.showInformationMessage(`No callers found for ${functionName}.`);
    return;
  }
  
  const callers = funcMeta.callers;
  let message = `**${functionName}()** - Callers (${callers.length})\n\n`;
  
  callers.forEach((caller, index) => {
    message += `${index + 1}. ${caller}\n`;
  });
  
  vscode.window.showInformationMessage(message);
}

function showCallees(functionName, filePath) {
  const {repo, lens} = getMaps();
  const funcKey = `${filePath}:${functionName}`;
  const funcMeta = lens.functions[funcKey] || repo.functions[funcKey];
  
  if (!funcMeta || !funcMeta.calls || funcMeta.calls.length === 0) {
    vscode.window.showInformationMessage(`No callees found for ${functionName}.`);
    return;
  }
  
  const callees = funcMeta.calls;
  let message = `**${functionName}()** - Callees (${callees.length})\n\n`;
  
  callees.forEach((callee, index) => {
    message += `${index + 1}. ${callee}\n`;
  });
  
  vscode.window.showInformationMessage(message);
}

function showHotPathAnalysis(functionName, filePath) {
  const {repo, lens} = getMaps();
  const funcKey = `${filePath}:${functionName}`;
  const funcMeta = lens.functions[funcKey] || repo.functions[funcKey];
  
  if (!funcMeta || !funcMeta.runtime_hit) {
    vscode.window.showInformationMessage(`${functionName} is not part of a hot path.`);
    return;
  }
  
  let message = `**${functionName}()** - Hot Path Analysis\n\n`;
  message += `🔥 **Runtime Hot Path**\n`;
  message += `This function was called during runtime tracing.\n\n`;
  
  if (funcMeta.trace_data) {
    message += `📊 **Trace Data**\n`;
    message += `• Call count: ${funcMeta.trace_data.call_count || 'Unknown'}\n`;
    message += `• Execution time: ${funcMeta.trace_data.execution_time || 'Unknown'}\n`;
    message += `• Memory usage: ${funcMeta.trace_data.memory_usage || 'Unknown'}\n\n`;
  }
  
  message += `*This function is part of a critical execution path and should be optimized for performance.*`;
  
  vscode.window.showInformationMessage(message);
}

function analyzeFunction(functionName, filePath) {
  const terminal = vscode.window.createTerminal('Understand-First Analysis');
  terminal.sendText(`u scan "${filePath}" -o maps/temp_analysis.json --verbose`);
  terminal.sendText(`u lens from-seeds --map maps/temp_analysis.json --seed "${functionName}" -o maps/temp_lens.json`);
  terminal.show();
  vscode.window.showInformationMessage(`Analyzing ${functionName}... Check the terminal for progress.`);
  logTTU('function_analyze');
}

// Panel management
let understandingPanel = null;

function openUnderstandingPanel() {
  if (understandingPanel) {
    understandingPanel.reveal();
    return;
  }

  understandingPanel = vscode.window.createWebviewPanel(
    'understandFirstPanel',
    'Understanding Analysis',
    vscode.ViewColumn.Two,
    {
      enableScripts: true,
      retainContextWhenHidden: true
    }
  );

  understandingPanel.webview.html = getPanelContent();

  understandingPanel.onDidDispose(() => {
    understandingPanel = null;
  });

  // Handle messages from the webview
  understandingPanel.webview.onDidReceiveMessage(
    message => {
      switch (message.command) {
        case 'refresh':
          refreshUnderstandingPanel();
          break;
        case 'openFunction':
          openFunctionInMap(message.functionName, message.filePath);
          break;
        case 'addToLens':
          addFunctionToLens(message.functionName, message.filePath);
          break;
        case 'generateTour':
          generateTourFromSelection({ functionName: message.functionName, filePath: message.filePath });
          break;
      }
    },
    undefined,
    context.subscriptions
  );
}

function refreshUnderstandingPanel() {
  if (understandingPanel) {
    understandingPanel.webview.html = getPanelContent();
  }
}

function getPanelContent() {
  const {repo, lens} = getMaps();
  const functions = Object.keys(lens.functions || {});
  const repoFunctions = Object.keys(repo.functions || {});
  
  let content = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Understanding Analysis</title>
        <style>
            body { font-family: var(--vscode-font-family); padding: 20px; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: var(--vscode-editor-background); border: 1px solid var(--vscode-panel-border); padding: 15px; border-radius: 5px; }
            .stat-title { font-weight: bold; margin-bottom: 5px; }
            .stat-value { font-size: 24px; color: var(--vscode-textLink-foreground); }
            .function-list { margin-top: 20px; }
            .function-item { 
                background: var(--vscode-editor-background); 
                border: 1px solid var(--vscode-panel-border); 
                margin-bottom: 10px; 
                padding: 15px; 
                border-radius: 5px;
                cursor: pointer;
            }
            .function-item:hover { background: var(--vscode-list-hoverBackground); }
            .function-name { font-weight: bold; margin-bottom: 5px; }
            .function-meta { color: var(--vscode-descriptionForeground); font-size: 14px; }
            .actions { margin-top: 10px; }
            .action-btn { 
                background: var(--vscode-button-background); 
                color: var(--vscode-button-foreground); 
                border: none; 
                padding: 5px 10px; 
                margin-right: 10px; 
                border-radius: 3px; 
                cursor: pointer;
            }
            .action-btn:hover { background: var(--vscode-button-hoverBackground); }
            .refresh-btn { 
                background: var(--vscode-button-secondaryBackground); 
                color: var(--vscode-button-secondaryForeground); 
                border: none; 
                padding: 8px 16px; 
                border-radius: 3px; 
                cursor: pointer;
            }
            .refresh-btn:hover { background: var(--vscode-button-secondaryHoverBackground); }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🧠 Understanding Analysis</h1>
            <button class="refresh-btn" onclick="refreshPanel()">Refresh</button>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-title">Functions in Lens</div>
                <div class="stat-value">${functions.length}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">Total Functions</div>
                <div class="stat-value">${repoFunctions.length}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">Seeds</div>
                <div class="stat-value">${lens.lens ? lens.lens.seeds.length : 0}</div>
            </div>
        </div>
        
        <div class="function-list">
            <h2>Functions in Understanding Lens</h2>
            ${functions.map(funcName => {
              const funcMeta = lens.functions[funcName];
              const complexity = funcMeta.complexity || 0;
              const sideEffects = funcMeta.side_effects || [];
              const callersCount = (funcMeta.callers || []).length;
              const calleesCount = (funcMeta.calls || []).length;
              const filePath = funcMeta.file || '';
              const fileName = filePath.split('/').pop() || filePath;
              
              return `
                <div class="function-item" onclick="openFunction('${funcName}', '${filePath}')">
                    <div class="function-name">${funcName}()</div>
                    <div class="function-meta">
                        📊 Calls: ${callersCount}→${calleesCount} | 
                        Complexity: ${complexity} | 
                        File: ${fileName}
                        ${sideEffects.length ? ` | Side effects: ${sideEffects.length}` : ''}
                    </div>
                    <div class="actions">
                        <button class="action-btn" onclick="event.stopPropagation(); openInMap('${funcName}', '${filePath}')">🗺️ Map</button>
                        <button class="action-btn" onclick="event.stopPropagation(); addToLens('${funcName}', '${filePath}')">🎯 Lens</button>
                        <button class="action-btn" onclick="event.stopPropagation(); generateTour('${funcName}', '${filePath}')">📖 Tour</button>
                    </div>
                </div>
              `;
            }).join('')}
        </div>
        
        <script>
            const vscode = acquireVsCodeApi();
            
            function refreshPanel() {
                vscode.postMessage({ command: 'refresh' });
            }
            
            function openFunction(functionName, filePath) {
                vscode.postMessage({ command: 'openFunction', functionName, filePath });
            }
            
            function openInMap(functionName, filePath) {
                vscode.postMessage({ command: 'openFunction', functionName, filePath });
            }
            
            function addToLens(functionName, filePath) {
                vscode.postMessage({ command: 'addToLens', functionName, filePath });
            }
            
            function generateTour(functionName, filePath) {
                vscode.postMessage({ command: 'generateTour', functionName, filePath });
            }
        </script>
    </body>
    </html>
  `;
  
  return content;
}

function deactivate() {}
module.exports = { activate, deactivate };
