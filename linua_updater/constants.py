"""Module-level constants for Linua Updater.

Extracted verbatim from the former monolithic ``LinuaUpdater_v4.3.0.py``.
"""

APP_VERSION = "5.0.0"
GITHUB_URL = "https://github.com"
GITHUB_USER_CONTENT_URL = "https://raw.githubusercontent.com"
CLOUDFLARE_WARP_URL = "https://1.1.1.1/"
DEFAULT_VERSION_CHECK_URL = f"{GITHUB_USER_CONTENT_URL}/BLaDZer/linua-updater/main/version.json"
DEFAULT_DATABASE_URL = f"{GITHUB_USER_CONTENT_URL}/BLaDZer/linua-updater/main/database.json"
DEFAULT_REGION_API_URL = "https://ipapi.co/json/"
DEFAULT_PROXY_PORTS = [1080, 2080, 8080, 7890, 10808, 8888, 1087]
DEFAULT_MIRRORS = {
    "github.com": "https://gh-proxy.com/" + GITHUB_URL,
    "raw.githubusercontent.com": "https://gh-proxy.com/" + GITHUB_USER_CONTENT_URL,
}

# Byte-size conversion factors
KB = 1024
MB = KB * 1024
GB = MB * 1024

# HTTP timeouts (seconds)
HTTP_TIMEOUT_SEC = 10
DEFAULT_DOWNLOAD_TIMEOUT_SEC = 30

# HTTP status codes
HTTP_OK = 200
HTTP_CLIENT_ERROR = 400

# Result protocol strings returned by installers/downloaders
RESULT_OK = "OK"
RESULT_CANCELLED = "Cancelled"

# Cache/metadata wrapper key holding the write time of a JSON cache file
CACHE_TIMESTAMP_KEY = "timestamp"

# UI / log theme colors (shared between the log colorizer and widget stylesheets)
COLOR_ERROR = "#ff6b6b"
COLOR_WARNING = "#ffd93d"
COLOR_SUCCESS = "#6bcf7f"
COLOR_INFO = "#4dabf7"
COLOR_DOWNLOADING = "#a78bfa"
COLOR_TEXT_DEFAULT = "#e9ecef"
COLOR_ACCENT = "#0078d7"
COLOR_DANGER = "#c92a2a"

# The Sims 4 executable path relative to the game folder
SIMS_4_GAME_EXE_REL = ("Game", "Bin", "TS4_x64.exe")

# Time and percentage helpers
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600
MILLISECONDS_IN_SECOND = 1000
PERCENT_MAX = 100

# Checksum algorithm names used in catalog entries
CHECKSUM_SHA256 = "sha256"
CHECKSUM_SHA1 = "sha1"
CHECKSUM_MD5 = "md5"

# JSON file pretty-print indentation (state/cache/config files)
JSON_INDENT = 2

# Installer sanity check: minimum plausible size of a downloaded archive
MIN_VALID_DOWNLOAD_SIZE = KB

# DATABASE keys
DATABASE_KEY_VERSION = "version"
DATABASE_KEY_DLC = "dlc"
DATABASE_KEY_UPDATED_AT = "updated_at"

DATABASE_DLC_KEY_NAME = "name"
DATABASE_DLC_KEY_URL = "url"
DATABASE_DLC_KEY_PARTS = "parts"
DATABASE_DLC_KEY_MAGNET = "magnet"
DATABASE_DLC_KEY_MIRRORS = "mirrors"
DATABASE_DLC_KEY_CHECKSUM = "checksum"
DATABASE_DLC_KEY_PRIORITY = "priority"
DATABASE_DLC_KEY_TYPE = "type"
DATABASE_DLC_KEY_SIZE = "size"

DOWNLOAD_SOURCE_DEFAULT_PRIORITY_FOR_MAGNET = 100
DOWNLOAD_SOURCE_DEFAULT_PRIORITY_FOR_PARTS = 50
DOWNLOAD_SOURCE_DEFAULT_PRIORITY_FOR_URL = 30

# Estimated archive sizes per DLC id (bytes). Used only as a fallback when a
# catalogue entry carries no ``size`` field.
SIZE_ESTIMATES = {
    "EP01": 1900000000,
    "EP02": 2100000000,
    "EP03": 2635798353,
    "EP04": 2800000000,
    "EP05": 2200000000,
    "EP06": 2807534837,
    "EP07": 2100000000,
    "EP08": 2300000000,
    "EP09": 1900000000,
    "EP10": 2400000000,
    "EP11": 2200000000,
    "EP12": 2100000000,
    "EP13": 2000000000,
    "EP14": 2300000000,
    "EP15": 1800000000,
    "EP16": 1900000000,
    "EP17": 2400000000,
    "EP18": 2100000000,
    "EP19": 1800000000,
    "EP20": 1900000000,
    "EP21": 2553349168,
    "GP01": 800000000,
    "GP02": 850000000,
    "GP03": 900000000,
    "GP04": 1000000000,
    "GP05": 750000000,
    "GP06": 1100000000,
    "GP07": 900000000,
    "GP08": 1000000000,
    "GP09": 1200000000,
    "GP10": 950000000,
    "GP11": 1000000000,
    "GP12": 950000000,
    "SP01": 150000000,
    "SP02": 100000000,
    "SP03": 120000000,
    "SP04": 110000000,
    "SP05": 130000000,
    "SP06": 140000000,
    "SP07": 160000000,
    "SP08": 100000000,
    "SP09": 150000000,
    "SP10": 180000000,
    "SP11": 120000000,
    "SP12": 110000000,
    "SP13": 130000000,
    "SP14": 100000000,
    "SP15": 140000000,
    "SP16": 110000000,
    "SP17": 120000000,
    "SP18": 150000000,
    "SP20": 80000000,
    "SP21": 70000000,
    "SP22": 60000000,
    "SP23": 75000000,
    "SP24": 65000000,
    "SP25": 70000000,
    "SP26": 80000000,
    "SP28": 75000000,
    "SP29": 70000000,
    "SP30": 80000000,
}

# Fallback database payload used when the remote database file cannot be
# downloaded (or is broken) and no usable copy is cached yet. Mirrors the
# remote ``database.json`` shape: a top-level dict whose ``dlc`` key maps DLC
# ids to their metadata. `DLCDatabase` currently only consumes the ``dlc``
# key, but the whole payload is preserved so future keys (e.g. ``version``,
# ``updatedAt``) can be added without restructuring.
DEFAULT_DATABASE_FALLBACK = {
    "dlc": {
        "EP01": {
            "name": "Get to Work",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP01.zip",
        },
        "EP02": {
            "name": "Get Together",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP02.zip",
        },
        "EP03": {
            "name": "City Living",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP03.zip",
        },
        "EP04": {
            "name": "Cats and Dogs",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP04.zip",
        },
        "EP05": {
            "name": "Seasons",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP05.zip",
        },
        "EP06": {
            "name": "Get Famous",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.zip",
            "mirrors": [
                {
                    "type": "parts",
                    "parts": [
                        {
                            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.001",
                            "checksum": {
                                "sha256": "6ca5aae51994b388c0c1754b35a796b0aa2a70134d7d19cff3ad2d7c5e39f76b",
                                "sha1": "cdd5c4ebe754780e7bdf9bbadac040744d933b91",
                                "md5": "a6a32c44748cb864f95395060f02373b",
                            },
                        },
                        {"url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.002"},
                        {"url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.003"},
                        {"url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.004"},
                        {"url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.005"},
                        {"url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.006"},
                        {"url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP06.7z.007"},
                    ],
                }
            ],
            "checksum": {
                "sha256": "6ca5aae51994b388c0c1754b35a796b0aa2a70134d7d19cff3ad2d7c5e39f76b",
                "sha1": "cdd5c4ebe754780e7bdf9bbadac040744d933b91",
                "md5": "a6a32c44748cb864f95395060f02373b",
            },
        },
        "EP07": {
            "name": "Island Living",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP07.zip",
        },
        "EP08": {
            "name": "Discover University",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP08.zip",
        },
        "EP09": {
            "name": "Eco Lifestyle",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP09.zip",
        },
        "EP10": {
            "name": "Snowy Escape",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP10.zip",
        },
        "EP11": {
            "name": "Cottage Living",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP11.zip",
        },
        "EP12": {
            "name": "High School Years",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP12.zip",
        },
        "EP13": {
            "name": "Growing Together",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP13.zip",
        },
        "EP14": {
            "name": "Horse Ranch",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP14.zip",
        },
        "EP15": {
            "name": "For Rent",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP15.zip",
        },
        "EP16": {
            "name": "The Sims 4 Strangerville",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP16.zip",
        },
        "EP17": {
            "name": "Realm of Magic",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP17.zip",
        },
        "EP18": {
            "name": "My Wedding Stories",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP18.zip",
        },
        "EP19": {
            "name": "Werewolves",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP19.zip",
        },
        "EP20": {
            "name": "Adventure in the Jungle",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP20.zip",
        },
        "EP21": {
            "name": "Royalty & Legacy",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP21.zip",
        },
        "FP01": {
            "name": "Holiday Celebration Pack",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/FP01.zip",
        },
        "GP01": {
            "name": "Outdoor Retreat",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP01.zip",
        },
        "GP02": {
            "name": "Spa Day",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP02.zip",
        },
        "GP03": {
            "name": "Dine Out",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP03.zip",
        },
        "GP04": {
            "name": "Vampires",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP04.zip",
        },
        "GP05": {
            "name": "Parenthood",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP05.zip",
        },
        "GP06": {
            "name": "Jungle Adventure",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP06.zip",
        },
        "GP07": {
            "name": "StrangerVille",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP07.zip",
        },
        "GP08": {
            "name": "Star Wars: Journey to Batuu",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP08.zip",
        },
        "GP09": {
            "name": "Dream Home Decorator",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP09.zip",
        },
        "GP10": {
            "name": "My Wedding Stories",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP10.zip",
        },
        "GP11": {
            "name": "Werewolves",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP11.zip",
        },
        "GP12": {
            "name": "Oasis Springs Pack",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/GP12.zip",
        },
        "SP01": {
            "name": "Luxury Party Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP01.zip",
        },
        "SP02": {
            "name": "Perfect Patio Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP02.zip",
        },
        "SP03": {
            "name": "Cool Kitchen Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP03.zip",
        },
        "SP04": {
            "name": "Spooky Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP04.zip",
        },
        "SP05": {
            "name": "Movie Hangout Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP05.zip",
        },
        "SP06": {
            "name": "Romantic Garden Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP06.zip",
        },
        "SP07": {
            "name": "Kids Room Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP07.zip",
        },
        "SP08": {
            "name": "Backyard Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP08.zip",
        },
        "SP09": {
            "name": "Vintage Glamour Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP09.zip",
        },
        "SP10": {
            "name": "Bowling Night Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP10.zip",
        },
        "SP11": {
            "name": "Fitness Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP11.zip",
        },
        "SP12": {
            "name": "Toddler Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP12.zip",
        },
        "SP13": {
            "name": "Laundry Day Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP13.zip",
        },
        "SP14": {
            "name": "My First Pet Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP14.zip",
        },
        "SP15": {
            "name": "Moschino Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP15.zip",
        },
        "SP16": {
            "name": "Tiny Living Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP16.zip",
        },
        "SP17": {
            "name": "Nifty Knitting Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP17.zip",
        },
        "SP18": {
            "name": "Paranormal Stuff",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP18.zip",
        },
        "SP20": {
            "name": "Throwback Fit Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP20.zip",
        },
        "SP21": {
            "name": "Country Kitchen Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP21.zip",
        },
        "SP22": {
            "name": "Bust the Dust Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP22.zip",
        },
        "SP23": {
            "name": "Courtyard Oasis Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP23.zip",
        },
        "SP24": {
            "name": "Fashion Street Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP24.zip",
        },
        "SP25": {
            "name": "Industrial Loft Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP25.zip",
        },
        "SP26": {
            "name": "Incheon Arrivals Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP26.zip",
        },
        "SP28": {
            "name": "Modern Menswear Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP28.zip",
        },
        "SP29": {
            "name": "Blooming Rooms Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP29.zip",
        },
        "SP30": {
            "name": "Carnaval Streetwear Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP30.zip",
        },
        "SP31": {
            "name": "Decor to the Max Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP31.zip",
        },
        "SP32": {
            "name": "Moonlight Chic Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP32.zip",
        },
        "SP33": {
            "name": "Little Campers Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP33.zip",
        },
        "SP34": {
            "name": "First Fits Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP34.zip",
        },
        "SP35": {
            "name": "Desert Luxe Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP35.zip",
        },
        "SP36": {
            "name": "Pastel Pop Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP36.zip",
        },
        "SP37": {
            "name": "Everyday Clutter Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP37.zip",
        },
        "SP38": {
            "name": "Simtimates Collection Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP38.zip",
        },
        "SP39": {
            "name": "Bathroom Clutter Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP39.zip",
        },
        "SP40": {
            "name": "Greenhouse Haven Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP40.zip",
        },
        "SP41": {
            "name": "Basement Treasures Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP41.zip",
        },
        "SP42": {
            "name": "Grunge Revival Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP42.zip",
        },
        "SP43": {
            "name": "Book Nook Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP43.zip",
        },
        "SP44": {
            "name": "Poolside Splash Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP44.zip",
        },
        "SP45": {
            "name": "Modern Luxe Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP45.zip",
        },
        "SP46": {
            "name": "Culinary Delights Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP46.zip",
        },
        "SP47": {
            "name": "Little Castle Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP47.zip",
        },
        "SP48": {
            "name": "Goth Galore Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP48.zip",
        },
        "SP49": {
            "name": "Sunflower & Daisies Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP49.zip",
        },
        "SP50": {
            "name": "Fashion Nostalgia Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP50.zip",
        },
        "SP51": {
            "name": "Party Essentials Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP51.zip",
        },
        "SP52": {
            "name": "Villa on the Riviera Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP52.zip",
        },
        "SP53": {
            "name": "Cozy Cafe Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP53.zip",
        },
        "SP54": {
            "name": "Artist Studio Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP54.zip",
        },
        "SP55": {
            "name": "Kids Fairytale Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP55.zip",
        },
        "SP56": {
            "name": "Pyjama Party Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP56.zip",
        },
        "SP57": {
            "name": "Bella's Kitchen Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP57.zip",
        },
        "SP58": {
            "name": "Gamer's Delight Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP58.zip",
        },
        "SP59": {
            "name": "Belle's Beauty Boutique Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP59.zip",
        },
        "SP60": {
            "name": "Downtown Loft Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP60.zip",
        },
        "SP61": {
            "name": "Luxurious Living Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP61.zip",
        },
        "SP62": {
            "name": "Professionalism Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP62.zip",
        },
        "SP63": {
            "name": "Trendy Bathroom Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP63.zip",
        },
        "SP64": {
            "name": "Romantic Mood Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP64.zip",
        },
        "SP65": {
            "name": "DIY Repair Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP65.zip",
        },
        "SP66": {
            "name": "Golden Years Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP66.zip",
        },
        "SP67": {
            "name": "Kitchen Utensil Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP67.zip",
        },
        "SP68": {
            "name": "SP68",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP68.zip",
        },
        "SP69": {
            "name": "Autumn Looks Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP69.zip",
        },
        "SP70": {
            "name": "SP70",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP70.zip",
        },
        "SP71": {
            "name": "Country Living Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP71.zip",
        },
        "SP72": {
            "name": "Ideal Makeup Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP72.zip",
        },
        "SP73": {
            "name": "Modern Interior Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP73.zip",
        },
        "SP74": {
            "name": "From the Garden Kit",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP74.zip",
        },
        "SP76": {
            "name": "SP76",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP76.zip",
        },
        "SP77": {
            "name": "SP77",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP77.zip",
        },
        "SP81": {
            "name": "SP81",
            "url": "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/SP81.zip",
        },
    }
}
