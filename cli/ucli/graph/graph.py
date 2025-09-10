def write_dot(system_map: dict, out_path: str):
    fns = system_map.get('functions', {})
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('digraph G {\n')
        for qname, meta in fns.items():
            safe = qname.replace('"', '\"')
            f.write(f'  "{safe}";\n')
        for qname, meta in fns.items():
            caller = qname.replace('"', '\"')
            for callee in meta.get('calls', []):
                f.write(f'  "{caller}" -> "{callee}";\n')
        f.write('}\n')
