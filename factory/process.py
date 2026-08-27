import os
import signal
import subprocess
import sys
from pathlib import Path

from config import ACCOUNTS_DIR
from factory.db import set_status


class ProcessManager:
    def __init__(self):
        self.processes = {}

    def account_dir(self, account_id):
        return ACCOUNTS_DIR / account_id

    def source_dir(self, account_id):
        return self.account_dir(account_id) / "source"

    def python(self, account_id):
        python = self.account_dir(account_id) / ".venv" / "bin" / "python"

        if python.exists():
            return str(python)

        return sys.executable

    async def stop(self, account_id):
        process = self.processes.get(account_id)

        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        self.processes.pop(account_id, None)

        try:
            set_status(account_id, "stopped")
        except Exception:
            pass

    async def start(self, account_id):
        await self.stop(account_id)

        source = self.source_dir(account_id)

        if not source.exists():
            raise RuntimeError("مجلد السورس غير موجود")

        account_dir = self.account_dir(account_id)
        account_dir.mkdir(parents=True, exist_ok=True)

        stdout = open(account_dir / "stdout.log", "a", encoding="utf-8")
        stderr = open(account_dir / "stderr.log", "a", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            [self.python(account_id), "-m", "zlzl"],
            cwd=source,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )

        self.processes[account_id] = process
        set_status(account_id, "running")

    async def restart(self, account_id):
        await self.stop(account_id)
        await self.start(account_id)

    async def remove(self, account_id):
        await self.stop(account_id)

        import shutil

        shutil.rmtree(
            self.account_dir(account_id),
            ignore_errors=True,
        )


PROCESS_MANAGER = ProcessManager()
