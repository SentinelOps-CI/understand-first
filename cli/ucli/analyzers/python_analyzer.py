from __future__ import annotations
import ast, os, pathlib, hashlib, sqlite3, time
from typing import Dict, Any, List, Optional, Tuple
from multiprocessing import Pool, cpu_count


def _is_code_file(path: pathlib.Path) -> bool:
    return path.suffix == ".py" and not any(part.startswith(".") for part in path.parts)


def _file_signature(path: pathlib.Path) -> Tuple[int, int, str]:
    st = path.stat()
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return int(st.st_mtime), int(st.st_size), h


def _parse_file(file_path: pathlib.Path) -> Dict[str, Any]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    calls_by_func: Dict[str, List[str]] = {}
    current_func: Optional[str] = None

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            nonlocal current_func
            current_func = node.name
            calls_by_func[current_func] = []
            self.generic_visit(node)
            current_func = None

        def visit_Call(self, node: ast.Call):
            if current_func is not None:
                callee = None
                if isinstance(node.func, ast.Name):
                    callee = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    callee = node.func.attr
                if callee:
                    calls_by_func[current_func].append(callee)
            self.generic_visit(node)

    Visitor().visit(tree)
    out = {}
    for func, calls in calls_by_func.items():
        out[func] = {
            "file": str(file_path.as_posix()),
            "calls": calls,
        }
    return out


def _open_cache(cache_path: pathlib.Path):
    conn = sqlite3.connect(str(cache_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime INTEGER, size INTEGER, sha TEXT, data TEXT)"
    )
    return conn


def build_python_map(
    root: pathlib.Path,
    use_cache: bool = False,
    processes: Optional[int] = None,
    cache_path: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    functions: Dict[str, Any] = {}
    files: List[pathlib.Path] = []
    for p, _, files_in_dir in os.walk(root):
        for name in files_in_dir:
            path = pathlib.Path(p) / name
            if _is_code_file(path):
                files.append(path)

    def qn(file_path: pathlib.Path, func_name: str) -> str:
        rel = file_path.with_suffix("").as_posix()
        return f"{rel}:{func_name}"

    cache_conn = None
    cache = {}
    if use_cache:
        cp = cache_path or (root / "maps" / "cache.sqlite")
        cp.parent.mkdir(parents=True, exist_ok=True)
        cache_conn = _open_cache(cp)
        for path, mtime, size, sha, data in cache_conn.execute(
            "SELECT path, mtime, size, sha, data FROM files"
        ):
            cache[path] = (mtime, size, sha, data)

    work: List[pathlib.Path] = []
    for file_path in files:
        if cache_conn is not None:
            mtime, size, sha = _file_signature(file_path)
            row = cache.get(str(file_path.as_posix()))
            if row and row[0] == mtime and row[1] == size and row[2] == sha:
                # reuse cached
                data = (
                    json.loads(row[3]) if "json" in globals() else __import__("json").loads(row[3])
                )
                for func, meta in data.items():
                    functions[qn(file_path, func)] = meta
                continue
        work.append(file_path)

    start = time.time()
    results = []
    if work:
        procs = max(1, processes or min(4, cpu_count()))
        if procs > 1:
            with Pool(processes=procs) as pool:
                results = pool.map(_parse_file, work)
        else:
            results = [_parse_file(fp) for fp in work]
        # write results and update cache
        for file_path, data in zip(work, results):
            for func, meta in data.items():
                functions[qn(file_path, func)] = meta
            if cache_conn is not None:
                mtime, size, sha = _file_signature(file_path)
                import json as _json

                cache_conn.execute(
                    "REPLACE INTO files(path, mtime, size, sha, data) VALUES (?,?,?,?,?)",
                    (str(file_path.as_posix()), mtime, size, sha, _json.dumps(data)),
                )
        if cache_conn is not None:
            cache_conn.commit()

    return {"language": "python", "functions": functions}
