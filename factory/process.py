import os
import signal
import subprocess
from pathlib import Path

from config import ACCOUNTS_DIR
from factory.db import set_status, get_account


class ProcessManager:
    def __init__(self):
        self.processes = {}

    def account_dir(self, account_id):
        return ACCOUNTS_DIR / account_id

    def source_dir(self, account_id):
        return self.account_dir(account_id) / "source"

    def python(self, account_id):
        return str(
            self.account_dir(account_id)
            / ".venv"
            / "bin"
            / "python"
        )

    async def stop(self, account_id):
        process = self.processes.get(account_id)

        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except Exception:
                    pass

        self.processes.pop(account_id, None)

        try:
            set_status(account_id, "stopped")
        except Exception:
            pass

    async def start(self, account_id):
        # منع تشغيل نفس الحساب مرتين
        current = self.processes.get(account_id)

        if current is not None:
            if current.poll() is None:
                return

            self.processes.pop(account_id, None)

        account_dir = self.account_dir(account_id)
        source = self.source_dir(account_id)
        python = self.python(account_id)

        if not source.exists():
            raise RuntimeError(
                f"مجلد السورس غير موجود: {source}"
            )

        if not Path(python).exists():
            raise RuntimeError(
                f"Python الخاص بالحساب غير موجود: {python}"
            )

        account_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        account = get_account(account_id)

        if not account:
            raise RuntimeError(
                f"الحساب {account_id} غير موجود في قاعدة البيانات"
            )

        # ترتيب الأعمدة:
        # id, name, phone, bot_token, api_id, api_hash, ...

        api_id = account[4]
        api_hash = account[5]
        bot_token = account[3] or ""

        session_file = account_dir / "session.txt"

        if not session_file.exists():
            raise RuntimeError(
                f"ملف Session غير موجود: {session_file}"
            )

        string_session = session_file.read_text(
            encoding="utf-8"
        ).strip()

        if not api_id:
            raise RuntimeError(
                "APP_ID غير موجود للحساب"
            )

        if not api_hash:
            raise RuntimeError(
                "API_HASH غير موجود للحساب"
            )

        if not string_session:
            raise RuntimeError(
                "STRING_SESSION فارغ للحساب"
            )

        # منع تشغيل نسخة أخرى من نفس الحساب
        try:
            result = subprocess.run(
                ["pgrep", "-af", "python.*-m zlzl"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            for line in result.stdout.splitlines():
                if str(source) in line:
                    return

        except Exception:
            pass

        stdout_path = account_dir / "stdout.log"
        stderr_path = account_dir / "stderr.log"

        stdout = open(
            stdout_path,
            "a",
            encoding="utf-8",
        )

        stderr = open(
            stderr_path,
            "a",
            encoding="utf-8",
        )

        # بيئة مستقلة للحساب
        env = os.environ.copy()

        env["PYTHONUNBUFFERED"] = "1"

        env["APP_ID"] = str(api_id)
        env["API_HASH"] = str(api_hash)
        env["STRING_SESSION"] = string_session
        env["TG_BOT_TOKEN"] = str(bot_token)
        env["ZELZAL_A"] = "@u_t_rbbb"

        # إجبار Python على استخدام مكتبات هذا الحساب
        env["VIRTUAL_ENV"] = str(
            account_dir / ".venv"
        )

        env["PATH"] = (
            str(account_dir / ".venv" / "bin")
            + os.pathsep
            + env.get("PATH", "")
        )

        # جعل استيراد zlzl من نفس السورس
        env["PYTHONPATH"] = str(source)

        process = subprocess.Popen(
            [
                python,
                "-m",
                "zlzl",
            ],
            cwd=source,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )

        self.processes[account_id] = process

        set_status(
            account_id,
            "running",
        )

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
