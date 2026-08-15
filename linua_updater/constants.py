"""Module-level constants for Linua Updater.

Extracted verbatim from the former monolithic ``LinuaUpdater_v4.3.0.py``.
"""

APP_VERSION = "4.3.0"
GITHUB_REPO = "l1ntol/linua-updater"
DEFAULT_VERSION_CHECK_URL = "https://raw.githubusercontent.com/l1ntol/linua-updater/main/version.json"
DEFAULT_REGION_API = "https://ipapi.co/json/"
DEFAULT_PROXY_PORTS = [1080, 8080, 7890, 10808, 8888, 1087]
DEFAULT_MIRRORS = {
    "github.com": "https://gh-proxy.com/https://github.com",
    "raw.githubusercontent.com": "https://gh-proxy.com/https://raw.githubusercontent.com",
}

# Estimated archive sizes per DLC id (bytes). Used only as a fallback when a
# catalogue entry carries no ``size`` field.
SIZE_ESTIMATES = {
    "EP01": 1900000000, "EP02": 2100000000, "EP03": 2635798353,
    "EP04": 2800000000, "EP05": 2200000000, "EP06": 2807534837,
    "EP07": 2100000000, "EP08": 2300000000, "EP09": 1900000000,
    "EP10": 2400000000, "EP11": 2200000000, "EP12": 2100000000,
    "EP13": 2000000000, "EP14": 2300000000, "EP15": 1800000000,
    "EP16": 1900000000, "EP17": 2400000000, "EP18": 2100000000,
    "EP19": 1800000000, "EP20": 1900000000, "EP21": 2553349168,
    "GP01": 800000000, "GP02": 850000000, "GP03": 900000000,
    "GP04": 1000000000, "GP05": 750000000, "GP06": 1100000000,
    "GP07": 900000000, "GP08": 1000000000, "GP09": 1200000000,
    "GP10": 950000000, "GP11": 1000000000, "GP12": 950000000,
    "SP01": 150000000, "SP02": 100000000, "SP03": 120000000,
    "SP04": 110000000, "SP05": 130000000, "SP06": 140000000,
    "SP07": 160000000, "SP08": 100000000, "SP09": 150000000,
    "SP10": 180000000, "SP11": 120000000, "SP12": 110000000,
    "SP13": 130000000, "SP14": 100000000, "SP15": 140000000,
    "SP16": 110000000, "SP17": 120000000, "SP18": 150000000,
    "SP20": 80000000, "SP21": 70000000, "SP22": 60000000,
    "SP23": 75000000, "SP24": 65000000, "SP25": 70000000,
    "SP26": 80000000, "SP28": 75000000, "SP29": 70000000,
    "SP30": 80000000,
}