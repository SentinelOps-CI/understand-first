import os, zipfile, json, pathlib, time

def make_pack(dist_dir='dist'):
    os.makedirs(dist_dir, exist_ok=True)
    pack_path = os.path.join(dist_dir, 'understanding-pack.zip')
    with zipfile.ZipFile(pack_path, 'w', zipfile.ZIP_DEFLATED) as z:
        def addp(p):
            if os.path.exists(p): z.write(p, p)
        addp('tours/PR.md'); addp('tours/local.md')
        addp('maps/delta.svg'); addp('docs/understanding-dashboard.md'); addp('docs/glossary.md')
        for root, _, files in os.walk('maps'):
            for f in files:
                if f.endswith('.json'): z.write(os.path.join(root, f), os.path.join(root, f))
    meta = {'created': int(time.time()), 'paths': ['tours/PR.md','tours/local.md','maps/delta.svg','docs/understanding-dashboard.md','docs/glossary.md']}
    with open(os.path.join(dist_dir, 'pack.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    print(f"Pack created at {pack_path}")
    return pack_path
