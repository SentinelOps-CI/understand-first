# Contributing

Thank you for contributing. This project aims for clarity, safety, and fast Time To Understanding.

## Environment
- Python 3.10+
- Create a virtualenv and install dependencies:
  - Windows: `py -m venv .venv && .venv\Scripts\python -m ensurepip --upgrade && .venv\Scripts\python -m pip install -r requirements.txt`
  - Linux/macOS: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Install CLI for development: `pip install -e cli`

## Development workflow
- Run `pytest -q` locally before sending a PR.
- Lint and format:
  - `ruff check`
  - `black .`
- Type checking (if available): `mypy` for Python sources.
- Keep edits focused and readable. Favor early returns, clear names, and guard clauses.

## Testing
- Unit tests live under `tests/`.
- Add tests when fixing bugs or adding features.
- For CLI features, prefer black‑box tests invoking `u` subcommands.

## Docs
- Update `README.md` and `docs/` when changing flags, outputs, or workflows.
- Keep language concise and free of emojis.
- Include minimal examples that can be copied and run.

## Commit and PR guidelines
- Use clear, imperative commit messages.
- Reference issues where relevant.
- Small, incremental PRs are preferred over large changes.

## CI
- PRs run CI on Windows and Linux to verify console script resolution and tests.
- Consider adding `u doctor`, `u config_validate`, and `u contracts report` steps to your workflow.
