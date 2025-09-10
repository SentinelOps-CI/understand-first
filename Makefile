.PHONY: bootstrap dev ci-local tour vsix wheel smoke

bootstrap:
	python3 -m pip install --upgrade pip
	pip install -r requirements.txt
	cd cli && pip install -e .

dev:
	uvicorn examples.servers.http_server:app --host 127.0.0.1 --port 8000 &
	python examples/servers/grpc_server.py &
	@echo "Servers started. Generate stubs if needed: python -m grpc_tools.protoc -I examples/apis --python_out=examples/apis/gen --grpc_python_out=examples/apis/gen examples/apis/orders.proto"

ci-local:
	pytest -q

tour:
	u scan . -o maps/repo.json || true
	u lens from-seeds --map maps/repo.json -o maps/lens.json || true
	u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
	u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json
	u tour maps/lens_merged.json -o tours/local.md

vsix:
	cd ide/vscode/understand-first && npx --yes @vscode/vsce package --no-yarn

wheel:
	cd cli && python -m build

smoke:
	pytest -q
