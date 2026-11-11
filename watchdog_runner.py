"""
SHIV Database 24/7 Persistent Watchdog & Supervisor Runner
Ensures the server remains running continuously, auto-restarts on unexpected crashes,
and captures stdout/stderr in rotating logs.
"""

import os
import sys
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "shiv_database.log"

# Setup Rotating Logger (max 10MB per file, up to 5 backups)
logger = logging.getLogger("shiv_watchdog")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(str(LOG_FILE), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Also log to stdout
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = os.environ.get("PORT", "8000")

def run_server():
    cmd = [
        sys.executable,
        "-m", "uvicorn",
        "app.main:app",
        "--host", HOST,
        "--port", str(PORT),
        "--timeout-keep-alive", "65",
        "--log-level", "info"
    ]

    logger.info("=" * 65)
    logger.info(f"Starting SHIV Database 24/7 Supervisor on http://{HOST}:{PORT}")
    logger.info(f"Working Directory: {BASE_DIR}")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("=" * 65)

    crash_count = 0
    max_fast_crashes = 10

    while True:
        start_time = time.time()
        try:
            logger.info("Launching Uvicorn backend process...")
            with open(str(LOG_FILE), "a", encoding="utf-8") as log_out:
                process = subprocess.Popen(
                    cmd,
                    cwd=str(BASE_DIR),
                    stdout=log_out,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy()
                )
                process.wait()
                exit_code = process.returncode

            uptime = time.time() - start_time
            logger.warning(f"Server process stopped with exit code: {exit_code} (Uptime: {uptime:.1f}s)")

            # Check if this was a fast crash loop
            if uptime < 5:
                crash_count += 1
                backoff = min(crash_count * 2, 30)
                logger.warning(f"Fast crash detected ({crash_count}/{max_fast_crashes}). Backing off for {backoff}s before restart...")
                time.sleep(backoff)
            else:
                # Reset counter if server was running stably
                crash_count = 0
                time.sleep(2)

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down supervisor gracefully.")
            if 'process' in locals() and process.poll() is None:
                process.terminate()
            break
        except Exception as e:
            logger.error(f"Unexpected watchdog exception: {e}", exc_info=True)
            time.sleep(3)

if __name__ == "__main__":
    run_server()
