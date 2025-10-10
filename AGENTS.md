# Repository Guidelines

## Project Structure & Module Organization
`src/infrastructure` owns Jetson system services, boot recovery, and thermal tuning; `src/video-pipeline` houses the C++ capture, NVENC, and sync layers; `src/platform` contains the FastAPI control plane and dashboard; `src/processing` delivers post-game stitching and lens correction. Shared specs and playbooks live in `docs/`, while install assets sit in `deploy/` and telemetry helpers in `monitoring/`. Tests are organized by objective across `tests/integration`, `tests/performance`, `tests/field-testing`, and `tests/strategy`.

## Build, Test, and Development Commands
Create an isolated environment with `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`. Run the control API locally using `uvicorn src.platform.simple_api:app --reload --host 0.0.0.0 --port 8000`. Compile video components via `cmake -S src/video-pipeline -B build/video && cmake --build build/video`, and provision field devices with `sudo deploy/install.sh` to register the systemd service and Prometheus endpoints.

## Coding Style & Naming Conventions
Apply PEP 8, 4-space indentation, and type hints for Python modules; format with `black` and gate with `flake8`, `mypy`, and `pylint` before sending a PR. C++ sources mirror the Google C++ Style Guide with 2-space indents, `CamelCase` types, and `snake_case` functions. Keep filenames descriptive (`recording_manager.py`, `recorder_main.cpp`) and group configuration into dedicated modules instead of scattering constants.

## Testing Guidelines
Use `pytest tests` for the fast path and add `--cov=src --cov-report=term-missing` to satisfy the >90% coverage bar from `CONTRIBUTING.md`. Integration workflows live in `tests/integration`; target individual flows with `pytest tests/integration/test_recording_workflow.py -k start`. Performance and endurance checks rely on the `benchmark` and `slow` markers—run them explicitly (`pytest tests/performance -m benchmark`) and document any hardware deviations. Capture logs or footage references in `tests/field-testing` when validating on Jetson hardware.

## Commit & Pull Request Guidelines
Branch from `develop`, keep commits scoped, and follow Conventional Commits (e.g., `feat(video-pipeline): reduce encode latency`) so automation can parse intent. Reference task IDs such as `VID-104` in the body and note telemetry or storage implications when they shift. Pull requests must complete `.github/pull_request_template.md`, link supporting docs, confirm integration touchpoints, and attach UI captures or Grafana snapshots when behavior changes. Update relevant READMEs or `docs/` pages before requesting review.

## Operations & Monitoring Tips
`deploy/install.sh` provisions `/mnt/recordings`, installs `footballvision-api.service`, and must run as a non-root user. Runtime logs stream to `/var/log/footballvision/api/`, while preview HLS output publishes under `/var/www/hls`. Keep secrets inside `src/platform/api-server/.env`, rotate them per environment, and exclude machine-specific overrides from commits.
