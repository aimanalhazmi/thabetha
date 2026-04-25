# thabetha

 Smart debt tracking with two‑party confirmation, reminders, Trust Score, QR profiles, and invoice OCR.


---

## Project Overview


---
## Environment setup

### Create & sync the environment from the project root
``` Bash
uv sync
```
This will:
- Create a virtual environment (managed by uv)
- Install all dependencies specified in pyproject.toml 
- Use uv.lock to ensure reproducible versions

### Environment variables & secrets
Create a .env file (not committed to git)

Example .env:

```text
OPENAI_API_KEY=sk-...
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your-username
DB_PASS=your-password
DB_NAME=your-database-name
```
Make sure .env is in .gitignore.

---



## Adding / removing dependencies with uv
Always manage dependencies via uv so that both pyproject.toml and uv.lock stay consistent.

1. Add a new dependency
``` Bash
# Add a runtime dependency
uv add package-name

# Add a dev-only dependency (e.g., testing, linting)
uv add --dev pytest
```
This will:
- Update [project.dependencies] (or [project.optional-dependencies] / dev section)
- Update uv.lock with the resolved versions

2. Remove a dependency
``` Bash
uv remove package-name
```

This will:
- Remove it from pyproject.toml
- Update uv.lock accordingly

After adding or removing dependencies, you can re-sync to ensure the environment matches:
``` Bash
uv sync
```

---



## Running the Application

``` Bash
# To fine-tune a model (e.g., DistilRoBERTa or MiniLM) using a specific configuration file:
uv run python src/models/fine_tuning.py --config fine-tuning-config.json

# Run the multi-perspective evaluation (Metrics, Human, LLM-Judge) on the test set:
python3 src/models/fine_tuning.py --config evaluation-config.json
```
---
## Working With JupyterLab
``` Bash
uv run jupyter lab
```
---
## Development & tooling (optional)
The project is configured with several tools in pyproject.toml:
- ruff for linting
- mypy for static type checking
- vulture for dead code detection
You can run them via uvx (after uv sync):
``` Bash
# Lint with ruff
uvx ruff check .

# Type check with mypy
uvx mypy src

# Find unused code with vulture
uvx vulture
```