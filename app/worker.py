import os
import queue
import subprocess
import threading
import time

from app import config, registry

# Each job launches a real Chrome + Selenium run, so jobs are processed strictly one at a
# time by a single background worker thread -- running the assessment engine in-process
# instead would mean fighting its module-level state (a ReportGenerator singleton, settings
# read once at import, log FileHandlers) across concurrent runs. Spawning it as an isolated
# subprocess sidesteps all of that.
JOB_QUEUE = queue.Queue()
_worker_started = False
_start_lock = threading.Lock()


def start_worker():
    global _worker_started
    with _start_lock:
        if _worker_started:
            return
        threading.Thread(target=_worker_loop, daemon=True).start()
        _worker_started = True


def enqueue(job):
    JOB_QUEUE.put(job)


def _worker_loop():
    while True:
        job = JOB_QUEUE.get()
        try:
            _run_job(job)
        except Exception as e:
            registry.update_run(job["run_id"], status="failed", error=f"Worker exception: {e}", finished_at=time.time())
        finally:
            JOB_QUEUE.task_done()


def _run_job(job):
    run_id = job["run_id"]
    output_dir = job["output_dir"]
    os.makedirs(output_dir, exist_ok=True)

    account = job["account"]
    env = os.environ.copy()
    env["ASSESSMENT_URL"] = job["assessment_url"]
    env["HEADLESS"] = "true" if job["headless"] else "false"
    env["OUTPUT_DIR"] = output_dir
    env["NVIDIA_MODEL"] = job["model"]
    env["CODING_MAX_RETRIES"] = str(job["max_retries"])
    env["TEST_USER_EMAIL"] = account["email"]
    env["TEST_USER_NAME"] = account["name"]
    env["TEST_USER_MOBILE"] = account["mobile"]
    env["TEST_USER_ROLL"] = account["roll_number"]

    registry.update_run(run_id, status="running", started_at=time.time())

    subprocess_log_path = os.path.join(output_dir, "subprocess.log")
    with open(subprocess_log_path, "w", encoding="utf-8") as logf:
        # stdin=DEVNULL is deliberate: main.py's final input() call (a "press Enter to exit"
        # prompt meant for interactive CLI use) reads EOF immediately from a null stdin and is
        # already caught via `except EOFError: pass`, so the subprocess exits cleanly on its
        # own instead of hanging forever waiting for a keypress that will never come from a
        # web-triggered run.
        #
        # config.ASSESSMENT_PYTHON (NOT sys.executable) is deliberate too: this process runs
        # in the backend's own venv, which has fastapi/uvicorn but not selenium/openai. Using
        # sys.executable here would make every run fail immediately with ModuleNotFoundError.
        proc = subprocess.Popen(
            [str(config.ASSESSMENT_PYTHON), "main.py"],
            cwd=str(config.ASSESSMENT_DIR),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
        try:
            returncode = proc.wait(timeout=config.RUN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            # Killing just the `python main.py` process leaves its child chromedriver/Chrome
            # processes orphaned on Windows -- taskkill /T kills the whole tree instead.
            _kill_process_tree(proc.pid)
            registry.update_run(
                run_id, status="failed", finished_at=time.time(),
                error=f"Run exceeded the {config.RUN_TIMEOUT_SECONDS // 60}-minute timeout and was killed.",
            )
            return

    if returncode == 0:
        registry.update_run(run_id, status="completed", finished_at=time.time())
    else:
        registry.update_run(
            run_id, status="failed", finished_at=time.time(),
            error=f"main.py exited with code {returncode} -- see subprocess.log in this run's output folder.",
        )


def _kill_process_tree(pid):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass
