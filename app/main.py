import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app import auth, config, registry, worker
from app.schemas import (
    ConfigResponse, LoginRequest, MeResponse, RunCreateRequest, RunCreateResponse, RunView,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.init_db()
    worker.start_worker()
    yield


app = FastAPI(title="PPA Assessment Runner API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,  # needed for the session cookie on any non-proxied deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/login", response_model=MeResponse)
def login(req: LoginRequest, response: Response):
    token = auth.login(req.email, req.password)
    if token is None:
        raise HTTPException(401, "Incorrect email or password.")
    response.set_cookie(
        auth.COOKIE_NAME, token, max_age=auth.SESSION_TTL_SECONDS,
        httponly=True, samesite="lax",
    )
    return MeResponse(email=req.email)


@app.post("/api/auth/logout")
def logout(response: Response, session_token: str | None = Cookie(default=None)):
    auth.logout(session_token)
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/api/auth/me", response_model=MeResponse)
def me(trainer: str = Depends(auth.require_auth)):
    return MeResponse(email=trainer)


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
def get_config(trainer: str = Depends(auth.require_auth)):
    return ConfigResponse(
        accounts=list(config.TEST_ACCOUNTS.keys()),
        recommended_models=config.RECOMMENDED_MODELS,
        default_model=config.DEFAULT_MODEL,
        default_retries=config.DEFAULT_RETRIES,
    )


@app.post("/api/runs", response_model=RunCreateResponse)
def create_run(req: RunCreateRequest, trainer: str = Depends(auth.require_auth)):
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
        created_by=trainer,
        note=(req.note or "").strip() or None,
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
def list_runs(trainer: str = Depends(auth.require_auth)):
    return [_run_view(r) for r in registry.list_runs()]


@app.get("/api/runs/{run_id}", response_model=RunView)
def get_run(run_id: str, trainer: str = Depends(auth.require_auth)):
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    return _run_view(run)


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str, trainer: str = Depends(auth.require_auth)):
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    if run["status"] not in ("queued", "running"):
        raise HTTPException(400, f"Run is already {run['status']}; nothing to cancel.")
    if not worker.cancel_run(run_id):
        raise HTTPException(409, "Could not cancel the run (it may have just finished).")
    return {"ok": True}
