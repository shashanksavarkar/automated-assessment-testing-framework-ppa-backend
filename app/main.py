import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import config, registry, worker
from app.schemas import ConfigResponse, RunCreateRequest, RunCreateResponse, RunView


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.init_db()
    worker.start_worker()
    yield


app = FastAPI(title="PPA Assessment Runner API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_telemetry(output_dir):
    try:
        with open(f"{output_dir}/telemetry.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _fmt_time(epoch):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch)) if epoch else None


def _run_view(run: dict) -> RunView:
    return RunView(
        **{**run, "headless": bool(run["headless"])},
        queue_position=registry.queue_position(run["id"]) if run["status"] == "queued" else None,
        telemetry=_read_telemetry(run["output_dir"]),
        created_at_fmt=_fmt_time(run.get("created_at")),
        started_at_fmt=_fmt_time(run.get("started_at")),
        finished_at_fmt=_fmt_time(run.get("finished_at")),
    )


@app.get("/api/config", response_model=ConfigResponse)
def get_config():
    return ConfigResponse(
        accounts=list(config.TEST_ACCOUNTS.keys()),
        recommended_models=config.RECOMMENDED_MODELS,
        default_model=config.DEFAULT_MODEL,
        default_retries=config.DEFAULT_RETRIES,
    )


@app.post("/api/runs", response_model=RunCreateResponse)
def create_run(req: RunCreateRequest):
    assessment_url = req.assessment_url.strip()
    if not assessment_url.startswith(("http://", "https://")):
        raise HTTPException(400, "Please provide a valid assessment link (starting with http:// or https://).")

    if req.test_account_label not in config.TEST_ACCOUNTS:
        raise HTTPException(400, "Unknown test account selected.")

    model = (req.model or "").strip() or config.DEFAULT_MODEL

    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    output_dir = str(config.OUTPUT_DIR / "runs" / run_id)

    registry.create_run(
        run_id=run_id,
        assessment_url=assessment_url,
        headless=req.headless,
        test_account_label=req.test_account_label,
        model=model,
        max_retries=req.max_retries,
        output_dir=output_dir,
    )
    worker.enqueue({
        "run_id": run_id,
        "assessment_url": assessment_url,
        "headless": req.headless,
        "model": model,
        "max_retries": req.max_retries,
        "output_dir": output_dir,
        "account": config.TEST_ACCOUNTS[req.test_account_label],
    })

    return RunCreateResponse(id=run_id)


@app.get("/api/runs", response_model=list[RunView])
def list_runs():
    return [_run_view(r) for r in registry.list_runs()]


@app.get("/api/runs/{run_id}", response_model=RunView)
def get_run(run_id: str):
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    return _run_view(run)
