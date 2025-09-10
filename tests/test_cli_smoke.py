import os, subprocess, sys, time, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

def run(cmd, cwd=None, check=True):
    print('>', cmd)
    return subprocess.run(cmd, cwd=cwd or ROOT, shell=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def test_scan_and_lens():
    run('u scan examples/python_toy -o maps/repo.json')
    run('u lens from-seeds --map maps/repo.json -o maps/lens.json')

def test_trace_and_tour():
    # start HTTP server
    p = subprocess.Popen([sys.executable, 'examples/servers/http_server.py'], cwd=ROOT)
    try:
        time.sleep(1.5)
        run('u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json', check=False)
        run('u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json', check=False)
        run('u tour maps/lens_merged.json -o tours/test.md', check=False)
    finally:
        p.terminate()
