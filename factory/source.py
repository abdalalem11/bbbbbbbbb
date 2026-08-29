import os
import shutil
import subprocess
import sys
from pathlib import Path

from config import SOURCE_BRANCH, SOURCE_REPO
from factory.process import PROCESS_MANAGER


def run(command, cwd=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(error[-4000:])

    return result.stdout


def create_venv(account_id):
    account_dir = PROCESS_MANAGER.account_dir(account_id)
    venv = account_dir / ".venv"

    if not venv.exists():
        run(
            [
                sys.executable,
                "-m",
                "venv",
                str(venv),
            ]
        )


def install_requirements(account_id):
    source = PROCESS_MANAGER.source_dir(account_id)
    python = PROCESS_MANAGER.python(account_id)
    requirements = source / "requirements.txt"

    # تحديث pip داخل venv فقط
    run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
        ],
        cwd=source,
    )

    # requirements.txt الخاص بالمشروع
    if requirements.exists():
        run(
            [
                python,
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements),
            ],
            cwd=source,
        )

    # مكتبات إضافية يعتمد عليها السورس
    extra_packages = [
        "heroku3",
        "validators",
        "SQLAlchemy",
        "aiohttp",
        "beautifulsoup4",
        "Markdown",
        "requests",
        "python-dotenv",
        "IMDbPY",
        "html_telegraph_poster",
        "lxml_html_clean",
        "emoji",
        "sqlalchemy-json",
        "urlextract",
        "jikanpy",
        "youtube-search-python",
        "lyricsgenius",
    ]

    run(
        [
            python,
            "-m",
            "pip",
            "install",
            *extra_packages,
        ],
        cwd=source,
    )


def patch_runtime_installer(account_id):
    """
    يجعل install_pip داخل الحساب يستخدم Python الخاص بالـ venv
    بدلاً من pip العام للنظام.
    """

    source = PROCESS_MANAGER.source_dir(account_id)
    target = source / "zlzl" / "helpers" / "utils" / "extdl.py"

    if not target.exists():
        return

    target.write_text(
        '''import subprocess
import sys


def install_pip(pipfile):
    print(f"Installing {pipfile} using {sys.executable}")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                pipfile,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        print(result.stdout)

        return result.stdout

    except Exception as e:
        print(f"Failed to install {pipfile}: {e}")
        return ""
''',
        encoding="utf-8",
    )


def write_environment(account_id, account, session):
    source = PROCESS_MANAGER.source_dir(account_id)

    env = "\n".join(
        [
            f"APP_ID={account['api_id']}",
            f"API_HASH={account['api_hash']}",
            f"STRING_SESSION={session}",
            f"TG_BOT_TOKEN={account['bot_token'] or ''}",
            f"ALIVE_NAME={account['name']}",
            f"UPSTREAM_REPO={SOURCE_REPO}",
            f"UPSTREAM_REPO_BRANCH={SOURCE_BRANCH}",
            "ENV=False",
        ]
    ) + "\n"

    env_file = source / ".env"

    env_file.write_text(
        env,
        encoding="utf-8",
    )

    os.chmod(
        env_file,
        0o600,
    )


def verify_source(account_id):
    source = PROCESS_MANAGER.source_dir(account_id)
    python = PROCESS_MANAGER.python(account_id)

    code = """
import os
import sys

required = [
    "APP_ID",
    "API_HASH",
    "STRING_SESSION",
]

missing = [x for x in required if not os.environ.get(x)]

if missing:
    raise RuntimeError(
        "متغيرات البيئة الناقصة: " + ", ".join(missing)
    )

import telethon

print("ZLZL SOURCE CHECK OK")
print("PYTHON:", sys.executable)
print("TELETHON:", telethon.__version__)
print("APP_ID:", os.environ["APP_ID"])
print("API_HASH: SET")
print("STRING_SESSION: SET")
"""

    env = os.environ.copy()

    account_dir = PROCESS_MANAGER.account_dir(account_id)
    session_file = account_dir / "session.txt"

    if not session_file.exists():
        raise RuntimeError(
            f"ملف Session غير موجود: {session_file}"
        )

    session = session_file.read_text(
        encoding="utf-8"
    ).strip()

    if not session:
        raise RuntimeError(
            "STRING_SESSION فارغ للحساب"
        )

    # قراءة بيانات الحساب من المصنع
    account = __import__(
        "factory.db",
        fromlist=["get_account"]
    ).get_account(account_id)

    if not account:
        raise RuntimeError(
            f"الحساب {account_id} غير موجود في قاعدة البيانات"
        )

    env["APP_ID"] = str(account[4])
    env["API_HASH"] = str(account[5])
    env["STRING_SESSION"] = session
    env["TG_BOT_TOKEN"] = str(account[3] or "")

    result = subprocess.run(
        [
            python,
            "-c",
            code,
        ],
        cwd=source,
        env=env,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            "فشل فحص السورس:\n" + error[-4000:]
        )

    return result.stdout

def install_source(account_id, account, session):
    account_dir = PROCESS_MANAGER.account_dir(account_id)
    source = PROCESS_MANAGER.source_dir(account_id)

    account_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if source.exists():
        shutil.rmtree(source)

    run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            SOURCE_BRANCH,
            SOURCE_REPO,
            str(source),
        ]
    )

    create_venv(account_id)

    write_environment(
        account_id,
        account,
        session,
    )

    install_requirements(
        account_id,
    )

    patch_runtime_installer(
        account_id,
    )

    verify_source(
        account_id,
    )


async def update_account(account_id, account):
    account_dir = PROCESS_MANAGER.account_dir(account_id)
    source = PROCESS_MANAGER.source_dir(account_id)

    session_file = account_dir / "session.txt"

    if not session_file.exists():
        raise RuntimeError(
            "Session الخاصة بالحساب غير موجودة"
        )

    session = session_file.read_text(
        encoding="utf-8"
    ).strip()

    if not session:
        raise RuntimeError(
            "STRING_SESSION فارغ للحساب"
        )

    await PROCESS_MANAGER.stop(
        account_id
    )

    new_source = account_dir / "new_source"

    if new_source.exists():
        shutil.rmtree(new_source)

    run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            SOURCE_BRANCH,
            SOURCE_REPO,
            str(new_source),
        ]
    )

    if source.exists():
        shutil.rmtree(source)

    new_source.rename(source)

    write_environment(
        account_id,
        account,
        session,
    )

    install_requirements(
        account_id,
    )

    patch_runtime_installer(
        account_id,
    )

    verify_source(
        account_id,
    )

    await PROCESS_MANAGER.start(
        account_id
    )
