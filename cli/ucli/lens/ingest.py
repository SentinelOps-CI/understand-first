import re, json

def seeds_from_github_log(path: str):
    txt = open(path, 'r', encoding='utf-8', errors='ignore').read()
    # pytest short tb lines: "file.py:123: in func"
    files = re.findall(r"([A-Za-z0-9_./-]+\.py):\d+", txt)
    funcs = re.findall(r"in\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", txt, flags=re.M)
    return sorted(list(set(files + funcs)))

def seeds_from_jira(path: str):
    txt = open(path, 'r', encoding='utf-8', errors='ignore').read()
    # naive: capture code blocks and file.py:line occurrences
    files = re.findall(r"([A-Za-z0-9_./-]+\.py):\d+", txt)
    funcs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\(", txt)
    return sorted(list(set(files + funcs)))
