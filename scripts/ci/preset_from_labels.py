import os, json, sys, subprocess


def main():
    label = os.environ.get("UF_LABEL", "").strip()
    repo_map = sys.argv[1] if len(sys.argv) > 1 else "maps/repo.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "maps/lens.json"
    if not label:
        print("No label; skipping preset")
        return 0
    cmd = f"u lens preset {label} --map {repo_map} -o {out}"
    print("> ", cmd)
    return subprocess.call(cmd, shell=True)


if __name__ == "__main__":
    sys.exit(main())
