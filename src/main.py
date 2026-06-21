import random
import requests
import re
import time
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import logging
import schedule
from datetime import datetime
from bs4 import BeautifulSoup

from constants import CONFIG_PATH, COOKIE_KEY, BASE_URL, USER_AGENT, LOG_DIR


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError:
            sys.exit(1)

    required_keys = ["classes", "locations", "cookies"]
    for key in required_keys:
        if key not in cfg:
            sys.exit(1)

    cfg.setdefault("scheduletimes", ["auto"])
    cfg.setdefault("schedule_window_start", "20:00")
    cfg.setdefault("schedule_window_end", "23:30")
    cfg.setdefault("schedule_interval", 5)

    return cfg


def setup_logger(debug: bool) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("AutoCheckBJMF")
    logger.setLevel(logging.INFO)

    sign_handler = logging.FileHandler(
        os.path.join(LOG_DIR, "sign_log.txt"), encoding="utf-8", mode="a"
    )
    sign_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(sign_handler)

    if debug:
        debug_handler = logging.FileHandler(
            os.path.join(LOG_DIR, "AutoCheckBJMF.log"), encoding="utf-8"
        )
        debug_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(debug_handler)

    return logger


def modify_decimal_part(num: float | str) -> float:
    num = float(num)
    num_str = f"{num:.8f}"
    decimal_idx = num_str.find('.')

    decimal_part = num_str[decimal_idx + 4: decimal_idx + 9]
    decimal_value = int(decimal_part)

    random_offset = random.randint(-15000, 15000)
    new_decimal_value = abs(decimal_value + random_offset)
    new_decimal_str = f"{new_decimal_value:05d}"

    new_num_str = num_str[:decimal_idx + 4] + new_decimal_str + num_str[decimal_idx + 9:]
    return float(new_num_str)


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

    for uid, raw_cookie in enumerate(cookies):
        username_match = re.search(r'username=[^;]+', raw_cookie)
        username_tag = f" <{username_match.group(0).split('=')[1]}>" if username_match else ""

        time.sleep(random.uniform(1, 3))

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
            response = requests.get(url, headers=headers, timeout=15)
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

        if not all_matches:
            logger.info(f"Class[{class_id}] | No active check-in tasks")
            continue

        for match_id in all_matches:
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
                sign_resp = requests.post(sign_url, headers=headers, data=payload, timeout=15)
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
                    logger.warning(
                        f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | No result tag"
                    )
            else:
                logger.error(
                    f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | "
                    f"Request failed {sign_resp.status_code}"
                )
                error_cookies.append(raw_cookie)

    return error_cookies, null_count, success_count


def retry_with_backoff(
    class_id: str,
    error_cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger,
    delay_seconds: int,
    attempt_label: str
) -> list:
    logger.info(f"Class[{class_id}] | {len(error_cookies)} account(s) failed, {attempt_label} in {delay_seconds}s")
    time.sleep(delay_seconds)
    error_cookies, _, _ = qiandao(class_id, error_cookies, locations, debug, logger)
    return error_cookies


def run_all_classes(
    classes: list,
    cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger
):
    logger.info(f"Check-in start | Classes: {len(classes)}  Accounts: {len(cookies)}  Locations: {len(locations)}")

    for class_id in classes:
        error_cookies, null_count, success_count = qiandao(
            class_id, cookies, locations, debug, logger
        )

        if error_cookies:
            error_cookies = retry_with_backoff(
                class_id, error_cookies, locations, debug, logger, 30, "1st retry"
            )

        if error_cookies:
            error_cookies = retry_with_backoff(
                class_id, error_cookies, locations, debug, logger, 300, "2nd retry"
            )

        if error_cookies:
            logger.error(f"Class[{class_id}] | some accounts still failed after retries")
        elif null_count > 0:
            logger.warning(f"Class[{class_id}] | {null_count} invalid cookie(s)")
        else:
            logger.info(f"Class[{class_id}] | all check-ins successful")

    logger.info("Check-in complete")


def main():
    cfg = load_config()
    classes        = cfg["classes"]
    locations      = cfg["locations"]
    cookies        = cfg["cookies"]
    schedule_times = cfg["scheduletimes"]
    debug          = cfg.get("debug", False)

    logger = setup_logger(debug)
    logger.info("AutoCheckBJMF started")

    def job():
        run_all_classes(classes, cookies, locations, debug, logger)

    is_auto = (schedule_times and schedule_times[0] == "auto")

    if not is_auto and schedule_times:
        for t_str in schedule_times:
            schedule.every().day.at(t_str).do(job)
            logger.info(f"Registered task: daily at {t_str}")

        while True:
            schedule.run_pending()
            time.sleep(1)
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
        while True:
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute

            if start_minutes <= current_minutes < end_minutes:
                if last_scan is None or (now - last_scan).total_seconds() >= interval * 60:
                    last_scan = now
                    run_all_classes(classes, cookies, locations, debug, logger)

                sleep_time = min(60, interval * 60 - (datetime.now() - last_scan).total_seconds())
                if sleep_time > 0:
                    time.sleep(sleep_time)

            elif current_minutes < start_minutes:
                wait_minutes = start_minutes - current_minutes
                time.sleep(min(wait_minutes * 60, 1800))

            else:
                logger.info("Check-in window ended")
                break


if __name__ == "__main__":
    main()
