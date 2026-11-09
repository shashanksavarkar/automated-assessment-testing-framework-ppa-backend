# PPA Assessment Runner — Backend

FastAPI service that exposes the trainer-facing API for the PPA automated assessment tool. It authenticates trainers, starts assessment runs, tracks their status, and returns results. The actual test execution is handled by the **TestCase1** assessment engine (Selenium + LLM-generated code), which this service runs as a subprocess.

## Tech stack

- Python 3.12, FastAPI, Uvicorn
- bcrypt for trainer password hashing
- Subprocess orchestration of the Selenium assessment engine (TestCase1, git submodule)
- Docker image for single-container deployment (serves the built frontend too)

## API overview

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login` | Trainer login |
| POST | `/api/auth/logout` | End session |
| GET | `/api/auth/me` | Current trainer |
| GET | `/api/config` | Available test accounts and recommended models |
| POST | `/api/runs` | Start an assessment run |
| GET | `/api/runs` | List run history |
| GET | `/api/runs/{run_id}` | Run details and results |
| POST | `/api/runs/{run_id}/cancel` | Cancel a queued or running run |

Interactive docs are available at `/docs` once the server is running.

## Setup

```bash
git clone --recurse-submodules <this-repo-url>
cd automated-assessment-testing-framework-ppa-backend

python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The server runs on http://127.0.0.1:8000. Run it alongside the frontend dev server (see the frontend README); Vite proxies `/api` to this port.

### Configuration

Settings are read from `TestCase1/.env`:

- `TRAINER_ACCOUNTS_JSON` — list of trainer accounts with bcrypt-hashed passwords. If unset, a single demo account is used (`admin` / `Pass@123`). **Set real accounts before any non-local use.** Use `python scripts/hash_password.py "your password"` to generate a hash.
- `NVIDIA_MODEL`, `CODING_MAX_RETRIES` — LLM model and retry settings for the assessment engine.
- `TEST_USER_EMAIL`, `TEST_USER_NAME` — default candidate identity for test runs.

Set `ASSESSMENT_DIR` to point at a different location of the assessment engine if needed.

## Docker

```bash
docker build -t ppa-backend .
docker run -p 8000:8000 ppa-backend
```

The container installs headless Chrome and both requirement sets, and expects the TestCase1 submodule at the repo root.

## Project layout

```
app/
  main.py       FastAPI routes and static frontend serving
  auth.py       Trainer login and session handling
  config.py     Paths, env loading, trainer accounts, model list
  registry.py   Run tracking
  worker.py     Launches TestCase1 runs as subprocesses
  schemas.py    Request/response models
scripts/
  hash_password.py   Generate bcrypt hashes for trainer accounts
TestCase1/           Assessment engine (git submodule)
```
