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
        raise RuntimeError(error[-2500:])

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

    if not requirements.exists():
        return

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
        ]
    ) + "\n"

    env_file = source / ".env"
    env_file.write_text(env, encoding="utf-8")
    os.chmod(env_file, 0o600)


def install_source(account_id, account, session):
    account_dir = PROCESS_MANAGER.account_dir(account_id)
    source = PROCESS_MANAGER.source_dir(account_id)

    account_dir.mkdir(parents=True, exist_ok=True)

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
    write_environment(account_id, account, session)
    install_requirements(account_id)


async def update_account(account_id, account):
    account_dir = PROCESS_MANAGER.account_dir(account_id)
    source = PROCESS_MANAGER.source_dir(account_id)

    session_file = account_dir / "session.txt"

    if not session_file.exists():
        raise RuntimeError("Session الخاصة بالحساب غير موجودة")

    session = session_file.read_text(
        encoding="utf-8"
    ).strip()

    await PROCESS_MANAGER.stop(account_id)

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

    old_env = source / ".env"

    if old_env.exists():
        environment = old_env.read_text(
            encoding="utf-8"
        )
    else:
        environment = ""

    if source.exists():
        shutil.rmtree(source)

    new_source.rename(source)

    if environment:
        (source / ".env").write_text(
            environment,
            encoding="utf-8",
        )

    os.chmod(source / ".env", 0o600)

    install_requirements(account_id)
