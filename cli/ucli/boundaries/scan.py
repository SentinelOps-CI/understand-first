import os, re
from typing import Dict, Any

def scan_boundaries(path: str) -> Dict[str, Any]:
    endpoints = []
    protos = []
    tables = []
    for root, dirs, files in os.walk(path):
        for f in files:
            full = os.path.join(root, f)
            try:
                head = open(full, 'r', encoding='utf-8', errors='ignore').read(2000)
            except Exception:
                continue
            if f.endswith(('.yml', '.yaml')) and 'openapi' in head.lower():
                data = open(full, 'r', encoding='utf-8', errors='ignore').read()
                for m in re.finditer(r"\n\s{0,6}(/[^\s:]+):", data):
                    endpoints.append(m.group(1))
            elif f.endswith('.proto'):
                txt = open(full, 'r', encoding='utf-8', errors='ignore').read()
                for m in re.finditer(r"rpc\s+(\w+)\s*\(", txt):
                    protos.append(m.group(1))
            elif f.endswith('.sql'):
                txt = open(full, 'r', encoding='utf-8', errors='ignore').read()
                for m in re.finditer(r"CREATE\s+TABLE\s+(\w+)", txt, re.I):
                    tables.append(m.group(1))
    return {'openapi_paths': sorted(set(endpoints)), 'proto_rpcs': sorted(set(protos)), 'sql_tables': sorted(set(tables))}
