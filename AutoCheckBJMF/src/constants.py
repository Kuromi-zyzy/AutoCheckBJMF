"""
Shared constants for AutoCheckBJMF.
"""

import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

COOKIE_KEY = "remember_student_59ba36addc2b2f9401580f014c7f58ea4e30989d"
LOGIN_URL = "https://bj.k8n.cn/login/qr/weixin/student/2"
LISTEN_TARGET = "https://bj.k8n.cn"
MAP_URL = "https://lbs.qq.com/getPoint/"
BASE_URL = "http://k8n.cn"

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 9; AKT-AK47 Build/USER-AK47; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 "
    "Mobile Safari/537.36 XWEB/1160065 MMWEBSDK/20231202 MMWEBID/1136 "
    "MicroMessenger/8.0.47.2560(0x28002F35) WeChat/arm64 Weixin "
    "NetType/4G Language/zh_CN ABI/arm64"
)
