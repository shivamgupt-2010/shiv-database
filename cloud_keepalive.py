"""
SHIV Cloud Keep-Alive Daemon
Pings https://shiv-database.onrender.com/health every 8 minutes to prevent Render free-tier sleep.
"""

import time
import urllib.request
import urllib.error
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("keep_alive")

URLS = [
    "https://shiv-database.onrender.com/health",
    "https://shiv-aiserver.onrender.com/health"
]

INTERVAL_SECONDS = 8 * 60 # 8 minutes (Render sleeps after 15 mins of inactivity)

def ping(url: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SHIV-KeepAlive/2.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            logger.info(f"Ping {url} -> Status {resp.status}")
    except urllib.error.HTTPError as e:
        logger.warning(f"Ping {url} -> HTTP {e.code}")
    except Exception as e:
        logger.warning(f"Ping {url} -> Failed: {e}")

def run():
    logger.info("Starting SHIV 24/7 Cloud Keep-Alive Daemon...")
    while True:
        for u in URLS:
            ping(u)
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    run()
