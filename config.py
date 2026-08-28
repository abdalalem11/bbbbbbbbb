import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

FACTORY_BOT_TOKEN = os.getenv("FACTORY_BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
NOTIFY_CHAT_ID = int(os.getenv("NOTIFY_CHAT_ID", "0") or 0)

SOURCE_NAME = os.getenv("SOURCE_NAME", "الزعيم")
SOURCE_REPO = os.getenv(
    "SOURCE_REPO",
    "https://github.com/abdalalem11/ZTele.git",
)
SOURCE_BRANCH = os.getenv("SOURCE_BRANCH", "factory-source")

DEVELOPER = os.getenv("DEVELOPER", "@u_t_r")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "@u_t_r")

DATA_DIR = ROOT / os.getenv("DATA_DIR", "data")
ACCOUNTS_DIR = ROOT / os.getenv("ACCOUNTS_DIR", "data/accounts")

DATA_DIR.mkdir(parents=True, exist_ok=True)
ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
