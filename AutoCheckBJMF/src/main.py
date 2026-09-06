import random
import requests
import re
import os
import sys
import signal
import threading

if sys.stdout is not None and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import logging
from logging.handlers import RotatingFileHandler
import schedule
from datetime import datetime, timedelta
from contextlib import contextmanager
from bs4 import BeautifulSoup

from rich.console import Console

from constants import CONFIG_PATH, COOKIE_KEY, BASE_URL, USER_AGENT, LOG_DIR

try:
    import fcntl
except ImportError:  # Windows entry points: no cross-process lock, scans just don't overlap there
    fcntl = None

console = Console()

_stop_event = threading.Event()

# Task IDs the server already refused (e.g. photo-required sign-ins).
# Remembered so the scan loop stops re-submitting them every interval.
_rejected_task_ids: set[str] = set()


@contextmanager
def _scan_lock(logger: logging.Logger):
    """Cross-process exclusive scan lock.

    The pm2 main loop and a TG /checkin subprocess can both trigger a scan;
    the lock makes them wait for each other instead of signing with the same
    cookies concurrently. Yields False when the lock is held elsewhere.
    """
    if fcntl is None:
        yield True
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = open(os.path.join(LOG_DIR, "scan.lock"), "w")
    try:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            logger.info("Scan skipped: another scan is already running")
            yield False
            return
        yield True
    finally:
        fh.close()  # closing the fd releases the flock


def _signal_handler(signum, frame):
    _stop_event.set()


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"[AutoCheckBJMF] config.json not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[AutoCheckBJMF] config.json is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)

    for key in ("classes", "locations", "cookies"):
        if key not in cfg:
            print(f"[AutoCheckBJMF] config.json missing required key: '{key}'", file=sys.stderr)
            sys.exit(1)

    cfg.setdefault("scheduletimes", ["auto"])
    cfg.setdefault("schedule_window_start", "20:00")
    cfg.setdefault("schedule_window_end", "23:30")
    cfg.setdefault("schedule_interval", 5)

    return cfg


def setup_logger(debug: bool) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("AutoCheckBJMF")
    logger.setLevel(logging.DEBUG)

    sign_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "sign_log.txt"),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    sign_handler.setLevel(logging.INFO)
    sign_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(sign_handler)

    if debug:
        debug_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, "AutoCheckBJMF.log"),
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(debug_handler)

    return logger


def modify_decimal_part(num: float | str) -> float:
    """Return num shifted by a random offset of up to ±0.00015 (~±15 m)."""
    return (round(float(num) * 1e8) + random.randint(-15000, 15000)) / 1e8


def pick_location(locations: list) -> dict:
    return random.choice(locations)


def qiandao(
    class_id: str,
    cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger
) -> tuple:
    url = f"{BASE_URL}/student/course/{class_id}/punchs"
    error_cookies = []
    null_count = 0
    success_count = 0
    had_task = False

    for uid, raw_cookie in enumerate(cookies):
        if _stop_event.is_set():
            break

        # One session per account so response Set-Cookie from a previous
        # account can never bleed into the next one's requests.
        session = requests.Session()

        username_match = re.search(r'username=[^;]+', raw_cookie)
        username_tag = f" <{username_match.group(0).split('=')[1]}>" if username_match else ""

        if _stop_event.wait(random.uniform(1, 3)):
            break

        cookie_match = re.search(rf'{COOKIE_KEY}=[^;]+', raw_cookie)
        if not cookie_match:
            null_count += 1
            continue

        extracted_cookie = cookie_match.group(0)

        headers = {
            'User-Agent':      USER_AGENT,
            'Accept':          ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                                'image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;'
                                'q=0.8,application/signed-exchange;v=b3;q=0.7'),
            'X-Requested-With': 'com.tencent.mm',
            'Referer':         f'{BASE_URL}/student/course/{class_id}',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh-SG;q=0.9,zh;q=0.8,en-SG;q=0.7,en-US;q=0.6,en;q=0.5',
            'Cookie':          extracted_cookie
        }

        try:
            response = session.get(url, headers=headers, timeout=15)
        except requests.RequestException:
            error_cookies.append(raw_cookie)
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('title')
        if not title_tag or "\u51fa\u9519" in title_tag.text:
            logger.error(f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | Login state invalid")
            error_cookies.append(raw_cookie)
            continue

        gps_btn = soup.find('a', id=re.compile(r'^gps_btn_\d+$'))
        all_matches = []
        if gps_btn:
            gps_id = re.compile(r'\d+').search(gps_btn.get('id')).group(0)
            all_matches.append(gps_id)
            had_task = True

        if not all_matches:
            logger.debug(f"Class[{class_id}] | No active check-in tasks")
            continue

        for match_id in all_matches:
            if match_id in _rejected_task_ids:
                logger.debug(
                    f"Class[{class_id}] | CheckInID[{match_id}] skipped: "
                    f"already rejected earlier (photo/other type)"
                )
                continue
            loc = pick_location(locations)
            new_lat = modify_decimal_part(loc["lat"])
            new_lng = modify_decimal_part(loc["lng"])
            acc = loc["acc"]

            sign_url = f"{BASE_URL}/student/punchs/course/{class_id}/{match_id}"
            payload = {
                'id':       match_id,
                'lat':      new_lat,
                'lng':      new_lng,
                'acc':      acc,
                'res':      '',
                'gps_addr': ''
            }

            try:
                sign_resp = session.post(sign_url, headers=headers, data=payload, timeout=15)
            except requests.RequestException:
                error_cookies.append(raw_cookie)
                continue

            logger.info(
                f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | "
                f"CheckInID[{match_id}] | Coord[{new_lat},{new_lng}]"
            )

            if sign_resp.status_code == 200:
                result_soup = BeautifulSoup(sign_resp.text, 'html.parser')
                div_tag = result_soup.find('div', id='title')
                if div_tag:
                    result_text = div_tag.text.strip()
                    logger.info(
                        f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | Result: {result_text}"
                    )
                    if result_text == "\u7b7e\u5230\u6210\u529f":
                        success_count += 1
                        break
                    else:
                        # e.g. photo-required sign-ins: the server refused this
                        # task type, don't re-submit it on the next scan
                        _rejected_task_ids.add(match_id)
                        logger.warning(
                            f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | "
                            f"Check-in not accepted: {result_text}"
                        )
                else:
                    logger.warning(
                        f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | No result tag"
                    )
            else:
                logger.error(
                    f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | "
                    f"Request failed {sign_resp.status_code}"
                )
                error_cookies.append(raw_cookie)

    return error_cookies, null_count, success_count, had_task


def retry_with_backoff(
    class_id: str,
    error_cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger,
    delay_seconds: int,
    attempt_label: str
) -> tuple:
    actual_delay = delay_seconds * random.uniform(0.5, 1.5)
    logger.info(f"Class[{class_id}] | {len(error_cookies)} account(s) failed, {attempt_label} in {actual_delay:.0f}s")
    if _stop_event.wait(actual_delay):
        logger.info(f"Class[{class_id}] | {attempt_label} cancelled, exiting")
        return error_cookies, 0, 0, False
    # Return the full result tuple: the retry's successes must be counted,
    # otherwise a recovered retry is misreported as "not accepted".
    return qiandao(class_id, error_cookies, locations, debug, logger)


def _scan_all_classes(
    classes: list,
    cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger
) -> tuple:
    had_success = False
    had_activity = False
    logger.debug(
        f"Check-in start | Classes: {len(classes)}  Accounts: {len(cookies)}  "
        f"Locations: {len(locations)}"
    )
    for class_id in classes:
        if _stop_event.is_set():
            break

        error_cookies, null_count, success_count, had_task = qiandao(
            class_id, cookies, locations, debug, logger
        )

        if success_count > 0:
            had_success = True
        if had_task or success_count > 0 or error_cookies or null_count > 0:
            had_activity = True

        if error_cookies:
            error_cookies, retry_null, retry_success, retry_task = retry_with_backoff(
                class_id, error_cookies, locations, debug, logger, 30, "1st retry"
            )
            null_count += retry_null
            success_count += retry_success
            had_task = had_task or retry_task
            if retry_success > 0:
                had_success = True
                had_activity = True

        if error_cookies:
            error_cookies, retry_null, retry_success, retry_task = retry_with_backoff(
                class_id, error_cookies, locations, debug, logger, 300, "2nd retry"
            )
            null_count += retry_null
            success_count += retry_success
            had_task = had_task or retry_task
            if retry_success > 0:
                had_success = True
                had_activity = True

        if error_cookies:
            logger.error(f"Class[{class_id}] | some accounts still failed after retries")
        elif null_count > 0:
            logger.warning(f"Class[{class_id}] | {null_count} invalid cookie(s)")
        elif had_task:
            if success_count > 0:
                logger.info(f"Class[{class_id}] | all check-ins successful")
            else:
                logger.warning(
                    f"Class[{class_id}] | check-in task found but not accepted "
                    f"(photo/other type?), manual check-in may be needed"
                )

    if had_activity:
        logger.info("Check-in complete")
    return had_success, had_activity


def run_all_classes(
    classes: list,
    cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger
) -> tuple:
    """Locked entry point shared by the main loop, TG /checkin and once.py.

    Returns (False, False) without scanning when another scan holds the lock.
    """
    with _scan_lock(logger) as locked:
        if not locked:
            return False, False
        return _scan_all_classes(classes, cookies, locations, debug, logger)


def seconds_until_next_start(now: datetime, start_minutes: int) -> float:
    """Seconds from now until tomorrow's window start (HH:MM -> minutes of day).

    Used after the check-in window ends: instead of exiting (which makes pm2
    restart-loop all night), the process sleeps until the next window.
    """
    next_start = datetime.combine(
        now.date() + timedelta(days=1), datetime.min.time()
    ) + timedelta(minutes=start_minutes)
    return max(0.0, (next_start - now).total_seconds())


def main():
    cfg = load_config()
    classes        = cfg["classes"]
    locations      = cfg["locations"]
    cookies        = cfg["cookies"]
    schedule_times = cfg["scheduletimes"]
    debug          = cfg.get("debug", False)

    logger = setup_logger(debug)
    logger.info("AutoCheckBJMF started")

    signal.signal(signal.SIGINT, _signal_handler)
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except (ValueError, OSError):
        pass

    def job():
        run_all_classes(classes, cookies, locations, debug, logger)

    is_auto = (schedule_times and schedule_times[0] == "auto")

    if not is_auto and schedule_times:
        for t_str in schedule_times:
            schedule.every().day.at(t_str).do(job)
            logger.info(f"Registered task: daily at {t_str}")

        while not _stop_event.is_set():
            schedule.run_pending()
            _stop_event.wait(1)
        logger.info("AutoCheckBJMF stopped")
    else:
        win_start = cfg.get("schedule_window_start", "20:00")
        win_end   = cfg.get("schedule_window_end", "23:30")
        interval  = cfg.get("schedule_interval", 5)

        sh, sm = map(int, win_start.split(":"))
        eh, em = map(int, win_end.split(":"))
        start_minutes = sh * 60 + sm
        end_minutes   = eh * 60 + em

        logger.info(f"Interval-scan mode active: {win_start}-{win_end} every {interval} min")

        last_scan = None
        dynamic_interval = interval
        last_idle_log = datetime.now()
        while not _stop_event.is_set():
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute

            if start_minutes <= current_minutes < end_minutes:
                if last_scan is None or (now - last_scan).total_seconds() >= dynamic_interval * 60:
                    last_scan = now
                    had_success, had_activity = run_all_classes(
                        classes, cookies, locations, debug, logger
                    )
                    if had_success:
                        dynamic_interval = min(interval * 2, 30)
                        logger.info(f"Check-in succeeded, next scan in {dynamic_interval} min")
                    else:
                        dynamic_interval = interval

                    if not had_activity:
                        if (now - last_idle_log).total_seconds() >= 1800:
                            logger.info(
                                "Idle heartbeat: window active, no check-in tasks seen"
                            )
                            last_idle_log = now
                    else:
                        last_idle_log = now

                sleep_time = min(60, dynamic_interval * 60 - (datetime.now() - last_scan).total_seconds())
                if sleep_time > 0:
                    _stop_event.wait(sleep_time)

            elif current_minutes < start_minutes:
                wait_minutes = start_minutes - current_minutes
                _stop_event.wait(min(wait_minutes * 60, 1800))

            else:
                # Sleep until tomorrow's window instead of exiting: exiting
                # makes pm2 restart the process immediately, which used to
                # loop all night (420k+ restarts on the server).
                logger.info("Check-in window ended, sleeping until next window start")
                last_scan = None
                dynamic_interval = interval
                while not _stop_event.is_set():
                    cur = datetime.now().hour * 60 + datetime.now().minute
                    if cur < end_minutes:
                        # Crossed past midnight: hand control back to the
                        # outer loop so the pre-window branch takes over.
                        break
                    wait_s = seconds_until_next_start(datetime.now(), start_minutes)
                    if _stop_event.wait(min(1800, wait_s)):
                        break

        logger.info("AutoCheckBJMF stopped")


if __name__ == "__main__":
    main()
