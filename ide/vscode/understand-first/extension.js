const vscode = require('vscode');
const fs = require('fs');


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

function activate(context) {
  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.showTour', function () { logTTU('tour_run'); openTourWalkthrough(); }));

  context.subscriptions.push(vscode.commands.registerCommand('understandFirst.explainErrorPropagation', function () {
    const {lens} = getMaps();
    const seeds = lens.lens ? lens.lens.seeds : [];
    vscode.window.showInformationMessage('Seeds: ' + seeds.join(', ') + ' — follow calls toward these seeds.');
  }));

  decorateEditor(vscode.window.activeTextEditor);
  vscode.window.onDidChangeActiveTextEditor(decorateEditor);
  vscode.workspace.onDidChangeTextDocument(() => decorateEditor(vscode.window.activeTextEditor));
}

function deactivate() {}
module.exports = { activate, deactivate };
