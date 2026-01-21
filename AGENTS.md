# Repository Guidelines

## Project Structure & Module Organization
The core SDK package lives in `alibabacloud_ecs20140526/`, with `client.py` providing the primary API client and `models/` containing request/response model classes. Many files in `client.py` and `models/` include the header "This file is auto-generated, don't edit it. Thanks." and should only be changed via regeneration. Root-level scripts like `describe_price_async.py`, `lowest_price_by_zone_async.py`, `hourly_cost_bss.py`, and `query_bill_detail_probe.py` are runnable examples or probes. Packaging metadata is in `setup.py`, `setup.cfg`, and `MANIFEST.in`, with release history in `ChangeLog.md`.

## Build, Test, and Development Commands
- `python -m pip install -e .` installs the SDK in editable mode for local development (Python >= 3.7).
- `python setup.py sdist bdist_wheel` builds source and wheel distributions (requires `wheel`).
- `python describe_price_async.py` or `python hourly_cost_bss.py` runs sample scripts; set environment variables like `ALIBABA_CLOUD_REGION_ID` and `ALIBABA_CLOUD_ECS_ROLE_NAME` first.

## Coding Style & Naming Conventions
Use 4-space indentation and keep to standard Python style (PEP 8). Prefer `snake_case` for functions and variables, `PascalCase` for classes, and keep module names aligned with existing SDK patterns (many model files use a leading underscore in filenames). Avoid manual edits to auto-generated client/model files unless you are regenerating them.

## Testing Guidelines
No test framework or `tests/` directory is configured in this repository, and no coverage requirements are defined. If you add tests, document the chosen framework and how to run it in this file, and follow a `test_*.py` naming convention for discoverability.

## Commit & Pull Request Guidelines
Recent commit messages are short, imperative, and capitalized (examples: "Initial commit", "Add gitignore and billing/price scripts"). Keep commits scoped and descriptive. For pull requests, include a concise summary, note any API behavior changes, and call out when auto-generated files are touched.

## Security & Configuration Tips
Example scripts authenticate via environment variables and instance roles. Common variables include `ALIBABA_CLOUD_REGION_ID`, `ALIBABA_CLOUD_ENDPOINT`, `ALIBABA_CLOUD_BSS_ENDPOINT`, and `ALIBABA_CLOUD_DISABLE_IMDS_V1`. Avoid hardcoding credentials in scripts; prefer environment configuration.
