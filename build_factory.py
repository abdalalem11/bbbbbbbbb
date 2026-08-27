from pathlib import Path

files = {}

files["requirements.txt"] = r"""aiogram>=3.20,<4
python-dotenv>=1.0,<2
Telethon>=1.42,<2
"""

files[".env.example"] = r"""FACTORY_BOT_TOKEN=
ADMIN_ID=
NOTIFY_CHAT_ID=

SOURCE_NAME=الزعيم
SOURCE_REPO=https://github.com/abdalalem11/ZTele.git
SOURCE_BRANCH=master

DEVELOPER=@u_t_r
SOURCE_CHANNEL=@u_t_r

DATA_DIR=./data
ACCOUNTS_DIR=./data/accounts
"""

files["config.py"] = r'''import os
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
SOURCE_BRANCH = os.getenv("SOURCE_BRANCH", "master")

DEVELOPER = os.getenv("DEVELOPER", "@u_t_r")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "@u_t_r")

DATA_DIR = ROOT / os.getenv("DATA_DIR", "data")
ACCOUNTS_DIR = ROOT / os.getenv("ACCOUNTS_DIR", "data/accounts")

DATA_DIR.mkdir(parents=True, exist_ok=True)
ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
'''

files["factory/__init__.py"] = ""

files["factory/db.py"] = r'''import sqlite3
from datetime import datetime, timezone

from config import DATA_DIR

DB = DATA_DIR / "factory.db"


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                bot_token TEXT,
                api_id INTEGER NOT NULL,
                api_hash TEXT NOT NULL,
                method TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'stopped'
            )
            """
        )
        db.commit()


def add_account(values):
    with connect() as db:
        db.execute(
            """
            INSERT INTO accounts
            (
                id, name, phone, bot_token, api_id, api_hash,
                method, created_at, expires_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        db.commit()


def get_account(account_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM accounts WHERE id=?",
            (account_id,),
        ).fetchone()


def all_accounts():
    with connect() as db:
        return db.execute(
            "SELECT * FROM accounts ORDER BY created_at DESC"
        ).fetchall()


def set_status(account_id, status):
    with connect() as db:
        db.execute(
            "UPDATE accounts SET status=? WHERE id=?",
            (status, account_id),
        )
        db.commit()


def delete_account(account_id):
    with connect() as db:
        db.execute(
            "DELETE FROM accounts WHERE id=?",
            (account_id,),
        )
        db.commit()


def expired_accounts():
    now = datetime.now(timezone.utc).isoformat()

    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM accounts
            WHERE expires_at <= ?
              AND status != 'expired'
            """,
            (now,),
        ).fetchall()
'''

files["factory/keyboards.py"] = r'''from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from factory.db import all_accounts


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛠️ تنصيب حساب",
                    callback_data="install",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 تحديث الحسابات",
                    callback_data="update_accounts",
                ),
                InlineKeyboardButton(
                    text="🔄 تحديث المصنع",
                    callback_data="update_factory",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ حذف تنصيب",
                    callback_data="delete_accounts",
                ),
                InlineKeyboardButton(
                    text="♻️ إعادة تشغيل",
                    callback_data="restart_accounts",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👨‍💻 المطور @u_t_r",
                    url="https://t.me/u_t_r",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 قناة السورس @u_t_r",
                    url="https://t.me/u_t_r",
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ ماذا يعني سورس؟",
                    callback_data="about",
                )
            ],
        ]
    )


def method_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 تنصيب عبر Session",
                    callback_data="method:session",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 تنصيب عبر الرقم",
                    callback_data="method:phone",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ إلغاء",
                    callback_data="cancel",
                )
            ],
        ]
    )


def account_keyboard(action):
    rows = []

    for account in all_accounts():
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"👑 {account['name']} "
                        f"• {account['status']}"
                    ),
                    callback_data=f"{action}:{account['id']}",
                )
            ]
        )

    if not rows:
        rows.append(
            [
                InlineKeyboardButton(
                    text="لا توجد حسابات",
                    callback_data="noop",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ رجوع",
                callback_data="home",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
'''

files["factory/process.py"] = r'''import os
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
'''

files["factory/source.py"] = r'''import os
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
'''

files["factory/telegram_auth.py"] = r'''from telethon import TelegramClient
from telethon.sessions import StringSession


async def request_code(api_id, api_hash, phone):
    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
    )

    await client.connect()

    result = await client.send_code_request(phone)

    session_seed = client.session.save()

    await client.disconnect()

    return session_seed, result.phone_code_hash


async def finish_code(
    api_id,
    api_hash,
    phone,
    code,
    session_seed,
    phone_code_hash,
):
    client = TelegramClient(
        StringSession(session_seed),
        api_id,
        api_hash,
    )

    await client.connect()

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash,
        )
    except Exception:
        raise

    session = client.session.save()

    await client.disconnect()

    return session


async def finish_password(
    api_id,
    api_hash,
    session_seed,
    password,
):
    client = TelegramClient(
        StringSession(session_seed),
        api_id,
        api_hash,
    )

    await client.connect()

    await client.sign_in(password=password)

    session = client.session.save()

    await client.disconnect()

    return session
'''

files["factory/bot.py"] = r'''import asyncio
import os
import secrets
import subprocess
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import (
    ACCOUNTS_DIR,
    ADMIN_ID,
    DEVELOPER,
    FACTORY_BOT_TOKEN,
    NOTIFY_CHAT_ID,
    SOURCE_CHANNEL,
    SOURCE_NAME,
)

from factory.db import (
    add_account,
    all_accounts,
    delete_account,
    expired_accounts,
    get_account,
    init_db,
    set_status,
)

from factory.keyboards import (
    account_keyboard,
    main_keyboard,
    method_keyboard,
)

from factory.process import PROCESS_MANAGER
from factory.source import install_source, update_account
from factory.telegram_auth import (
    finish_code,
    finish_password,
    request_code,
)

dp = Dispatcher()


class InstallState(StatesGroup):
    method = State()
    name = State()
    bot_token = State()
    api_id = State()
    api_hash = State()
    phone = State()
    code = State()
    password = State()
    session = State()
    days = State()


def is_admin(user_id):
    return user_id == ADMIN_ID


async def notify(bot, text):
    if not NOTIFY_CHAT_ID:
        return

    try:
        await bot.send_message(
            NOTIFY_CHAT_ID,
            text,
        )
    except Exception:
        pass


async def reject_if_not_admin(callback):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ غير مصرح لك",
            show_alert=True,
        )
        return True

    return False


@dp.message(CommandStart())
async def start(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer(
            "⛔ هذا المصنع خاص بالمدير."
        )

    await message.answer(
        f"👑 <b>مصنع {SOURCE_NAME}</b>\n\n"
        "إدارة احترافية لتنصيب وتشغيل وتحديث الحسابات.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin(callback):
        return

    await state.clear()

    await callback.message.edit_text(
        f"👑 <b>مصنع {SOURCE_NAME}</b>\n\n"
        "اختر العملية:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin(callback):
        return

    await state.clear()

    await callback.message.edit_text(
        "❌ تم إلغاء العملية.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer("لا توجد حسابات حالياً.")


@dp.callback_query(F.data == "install")
async def install(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin(callback):
        return

    await state.clear()
    await state.set_state(InstallState.method)

    await callback.message.edit_text(
        "🛠️ <b>تنصيب حساب جديد</b>\n\n"
        "اختر طريقة تسجيل الدخول:",
        reply_markup=method_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("method:"))
async def method(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin(callback):
        return

    selected = callback.data.split(":", 1)[1]

    await state.update_data(method=selected)
    await state.set_state(InstallState.name)

    await callback.message.edit_text(
        "📝 أرسل <b>اسم التنصيب</b>.",
        parse_mode="HTML",
    )


@dp.message(InstallState.name)
async def install_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()

    if not name or len(name) > 80:
        return await message.answer(
            "❌ الاسم غير صالح."
        )

    await state.update_data(name=name)
    await state.set_state(InstallState.bot_token)

    await message.delete()

    await message.answer(
        "🤖 أرسل <b>توكن البوت</b>.",
        parse_mode="HTML",
    )


@dp.message(InstallState.bot_token)
async def install_token(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    token = message.text.strip()

    await message.delete()

    if ":" not in token:
        return await message.answer(
            "❌ يبدو أن التوكن غير صحيح."
        )

    await state.update_data(bot_token=token)
    await state.set_state(InstallState.api_id)

    await message.answer(
        "🔑 أرسل <b>API_ID</b>.",
        parse_mode="HTML",
    )


@dp.message(InstallState.api_id)
async def install_api_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    value = message.text.strip()

    await message.delete()

    if not value.isdigit():
        return await message.answer(
            "❌ API_ID يجب أن يكون رقماً."
        )

    await state.update_data(api_id=int(value))
    await state.set_state(InstallState.api_hash)

    await message.answer(
        "🔐 أرسل <b>API_HASH</b>.",
        parse_mode="HTML",
    )


@dp.message(InstallState.api_hash)
async def install_api_hash(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    value = message.text.strip()

    await message.delete()

    if len(value) < 20:
        return await message.answer(
            "❌ API_HASH يبدو غير صحيح."
        )

    await state.update_data(api_hash=value)

    data = await state.get_data()

    if data["method"] == "session":
        await state.set_state(InstallState.session)

        await message.answer(
            "🔐 أرسل <b>String Session</b> للحساب.",
            parse_mode="HTML",
        )
    else:
        await state.set_state(InstallState.phone)

        await message.answer(
            "📱 أرسل رقم الحساب بصيغة دولية.\n\n"
            "مثال:\n"
            "<code>+9665XXXXXXXX</code>",
            parse_mode="HTML",
        )


@dp.message(InstallState.session)
async def install_session(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    session = message.text.strip()

    await message.delete()

    if len(session) < 50:
        return await message.answer(
            "❌ Session تبدو غير صحيحة."
        )

    await state.update_data(session=session)
    await state.set_state(InstallState.days)

    await message.answer(
        "⏳ أرسل مدة الاشتراك.\n\n"
        "المسموح من <b>1</b> إلى <b>300</b> يوم.",
        parse_mode="HTML",
    )


@dp.message(InstallState.phone)
async def install_phone(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    phone = message.text.strip()

    await message.delete()

    if not phone.startswith("+"):
        return await message.answer(
            "❌ أرسل الرقم مع + ومفتاح الدولة."
        )

    data = await state.get_data()

    try:
        session_seed, phone_code_hash = await request_code(
            data["api_id"],
            data["api_hash"],
            phone,
        )
    except Exception as exc:
        return await message.answer(
            "❌ فشل إرسال كود Telegram.\n\n"
            f"<code>{str(exc)[-1200:]}</code>",
            parse_mode="HTML",
        )

    await state.update_data(
        phone=phone,
        session_seed=session_seed,
        phone_code_hash=phone_code_hash,
    )

    await state.set_state(InstallState.code)

    await message.answer(
        "📨 تم إرسال كود Telegram.\n\n"
        "أرسل الكود هنا.\n\n"
        "⚠️ لا تشارك الكود مع أي شخص آخر.",
    )


@dp.message(InstallState.code)
async def install_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    code = message.text.strip()

    await message.delete()

    data = await state.get_data()

    try:
        session = await finish_code(
            data["api_id"],
            data["api_hash"],
            data["phone"],
            code,
            data["session_seed"],
            data["phone_code_hash"],
        )
    except Exception as exc:
        if exc.__class__.__name__ == "SessionPasswordNeededError":
            await state.update_data(code=code)
            await state.set_state(InstallState.password)

            return await message.answer(
                "🔐 الحساب محمي بالتحقق بخطوتين.\n\n"
                "أرسل كلمة مرور التحقق بخطوتين.",
            )

        return await message.answer(
            "❌ فشل تسجيل الدخول.\n\n"
            f"<code>{str(exc)[-1200:]}</code>",
            parse_mode="HTML",
        )

    await state.update_data(session=session)
    await state.set_state(InstallState.days)

    await message.answer(
        "⏳ أرسل مدة الاشتراك من 1 إلى 300 يوم."
    )


@dp.message(InstallState.password)
async def install_password(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    password = message.text.strip()

    await message.delete()

    data = await state.get_data()

    try:
        session = await finish_password(
            data["api_id"],
            data["api_hash"],
            data["session_seed"],
            password,
        )
    except Exception as exc:
        return await message.answer(
            "❌ فشل التحقق بخطوتين.\n\n"
            f"<code>{str(exc)[-1200:]}</code>",
            parse_mode="HTML",
        )

    await state.update_data(session=session)
    await state.set_state(InstallState.days)

    await message.answer(
        "⏳ أرسل مدة الاشتراك من 1 إلى 300 يوم."
    )


@dp.message(InstallState.days)
async def install_days(
    message: Message,
    state: FSMContext,
    bot: Bot,
):
    if not is_admin(message.from_user.id):
        return

    value = message.text.strip()

    await message.delete()

    if not value.isdigit():
        return await message.answer(
            "❌ أرسل رقم الأيام فقط."
        )

    days = int(value)

    if days < 1 or days > 300:
        return await message.answer(
            "❌ المدة يجب أن تكون بين 1 و300 يوم."
        )

    data = await state.get_data()

    account_id = secrets.token_hex(4)

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)

    add_account(
        (
            account_id,
            data["name"],
            data.get("phone", ""),
            data["bot_token"],
            data["api_id"],
            data["api_hash"],
            data["method"],
            now.isoformat(),
            expires.isoformat(),
            "stopped",
        )
    )

    account_dir = ACCOUNTS_DIR / account_id
    account_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    session_file = account_dir / "session.txt"
    session_file.write_text(
        data["session"],
        encoding="utf-8",
    )

    os.chmod(session_file, 0o600)

    account = get_account(account_id)

    try:
        install_source(
            account_id,
            account,
            data["session"],
        )

        await PROCESS_MANAGER.start(account_id)

        status = "running"

    except Exception as exc:
        status = "stopped"

        await message.answer(
            "⚠️ تم إنشاء بيانات التنصيب، "
            "لكن تشغيل السورس فشل.\n\n"
            f"<code>{str(exc)[-1800:]}</code>",
            parse_mode="HTML",
        )

    await state.clear()

    text = (
        "✅ <b>تم إنشاء التنصيب</b>\n\n"
        f"👑 الاسم: <b>{data['name']}</b>\n"
        f"📦 السورس: <b>{SOURCE_NAME}</b>\n"
        f"⚙️ الحالة: <b>{status}</b>\n"
        f"⏳ الاشتراك: <b>{days} يوم</b>\n"
        f"📅 الانتهاء: <b>{expires.strftime('%Y-%m-%d %H:%M UTC')}</b>\n\n"
        f"👨‍💻 الحقوق: {DEVELOPER}"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    await notify(
        bot,
        "🟢 <b>تم تنصيب حساب جديد</b>\n\n"
        f"👑 الاسم: {data['name']}\n"
        f"📦 السورس: {SOURCE_NAME}\n"
        f"⏳ المدة: {days} يوم\n"
        f"📅 الانتهاء: {expires.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"👨‍💻 المطور: {DEVELOPER}",
    )


@dp.callback_query(F.data == "update_accounts")
async def update_accounts(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    await callback.message.edit_text(
        "🔄 <b>اختر الحساب الذي تريد تحديثه:</b>",
        reply_markup=account_keyboard("update"),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("update:"))
async def update_one(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    account_id = callback.data.split(":", 1)[1]
    account = get_account(account_id)

    if not account:
        return await callback.answer(
            "الحساب غير موجود.",
            show_alert=True,
        )

    await callback.message.edit_text(
        "⏳ جاري تحديث الحساب...\n\n"
        "1️⃣ إيقاف الحساب\n"
        "2️⃣ تنزيل آخر نسخة\n"
        "3️⃣ تثبيت المتطلبات\n"
        "4️⃣ تشغيل الحساب",
    )

    try:
        await update_account(
            account_id,
            account,
        )

        await PROCESS_MANAGER.start(
            account_id
        )

        await callback.message.edit_text(
            f"✅ تم تحديث <b>{account['name']}</b> وتشغيله.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )

    except Exception as exc:
        await callback.message.edit_text(
            "❌ فشل تحديث الحساب.\n\n"
            f"<code>{str(exc)[-1800:]}</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )


@dp.callback_query(F.data == "restart_accounts")
async def restart_accounts(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    await callback.message.edit_text(
        "♻️ اختر الحساب:",
        reply_markup=account_keyboard("restart"),
    )


@dp.callback_query(F.data.startswith("restart:"))
async def restart_one(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    account_id = callback.data.split(":", 1)[1]

    if not get_account(account_id):
        return await callback.answer(
            "الحساب غير موجود.",
            show_alert=True,
        )

    try:
        await PROCESS_MANAGER.restart(account_id)

        await callback.message.edit_text(
            "✅ تمت إعادة تشغيل الحساب.",
            reply_markup=main_keyboard(),
        )

    except Exception as exc:
        await callback.message.edit_text(
            f"❌ فشل إعادة التشغيل:\n<code>{str(exc)}</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )


@dp.callback_query(F.data == "delete_accounts")
async def delete_accounts(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    await callback.message.edit_text(
        "🗑️ اختر الحساب الذي تريد حذفه:",
        reply_markup=account_keyboard("delete"),
    )


@dp.callback_query(F.data.startswith("delete:"))
async def delete_one(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    account_id = callback.data.split(":", 1)[1]
    account = get_account(account_id)

    if not account:
        return await callback.answer(
            "الحساب غير موجود.",
            show_alert=True,
        )

    await PROCESS_MANAGER.remove(account_id)
    delete_account(account_id)

    await callback.message.edit_text(
        f"🗑️ تم حذف تنصيب <b>{account['name']}</b> بالكامل.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    if await reject_if_not_admin(callback):
        return

    await callback.message.edit_text(
        f"ℹ️ <b>ماذا يعني السورس؟</b>\n\n"
        f"السورس هو الكود البرمجي الذي يشغّل حساب Telegram "
        f"ويحتوي على الأوامر والإضافات والإعدادات.\n\n"
        f"👑 اسم السورس: <b>{SOURCE_NAME}</b>\n"
        f"👨‍💻 المبرمج: <b>{DEVELOPER}</b>\n"
        f"📢 قناة السورس: <b>{SOURCE_CHANNEL}</b>\n\n"
        "⚠️ المصنع وظيفته إدارة نسخ السورس وتنصيبها "
        "وتحديثها وتشغيلها.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "update_factory")
async def update_factory(
    callback: CallbackQuery,
    bot: Bot,
):
    if await reject_if_not_admin(callback):
        return

    await callback.message.edit_text(
        "🔄 <b>جاري تحديث المصنع...</b>\n\n"
        "📥 جلب آخر نسخة من GitHub.",
        parse_mode="HTML",
    )

    result = subprocess.run(
        [
            "git",
            "pull",
            "--ff-only",
        ],
        cwd=str(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        ),
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        return await callback.message.edit_text(
            "❌ فشل تحديث المصنع.\n\n"
            f"<code>{result.stderr[-1500:]}</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )

    accounts = all_accounts()
    failed = []

    for account in accounts:
        try:
            await update_account(
                account["id"],
                account,
            )
            await PROCESS_MANAGER.start(
                account["id"]
            )
        except Exception as exc:
            failed.append(
                f"{account['name']}: {str(exc)[:300]}"
            )

    text = (
        "✅ <b>اكتمل تحديث المصنع</b>\n\n"
        f"📦 الحسابات: {len(accounts)}\n"
        f"❌ فشل: {len(failed)}\n\n"
    )

    if failed:
        text += "\n".join(
            f"• {item}"
            for item in failed[:10]
        )

    text += (
        "\n\n⚠️ سيتم إعادة تشغيل خدمة المصنع "
        "لتطبيق كود المصنع الجديد."
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    # Give Telegram time to deliver the result before restarting.
    await asyncio.sleep(3)

    subprocess.Popen(
        [
            "systemctl",
            "restart",
            "zaeem-factory.service",
        ]
    )


async def subscription_loop(bot: Bot):
    while True:
        try:
            accounts = expired_accounts()

            for account in accounts:
                try:
                    await PROCESS_MANAGER.stop(
                        account["id"]
                    )
                except Exception:
                    pass

                set_status(
                    account["id"],
                    "expired",
                )

                await notify(
                    bot,
                    "⛔ <b>انتهى الاشتراك</b>\n\n"
                    f"👑 الحساب: {account['name']}\n"
                    f"📦 السورس: {SOURCE_NAME}\n"
                    f"📅 تاريخ الانتهاء: "
                    f"{account['expires_at']}\n\n"
                    f"👨‍💻 {DEVELOPER}",
                )

        except Exception:
            pass

        await asyncio.sleep(30)


async def main():
    if not FACTORY_BOT_TOKEN:
        raise RuntimeError(
            "FACTORY_BOT_TOKEN غير موجود في .env"
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "ADMIN_ID غير موجود في .env"
        )

    init_db()

    bot = Bot(
        FACTORY_BOT_TOKEN
    )

    asyncio.create_task(
        subscription_loop(bot)
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
'''

files["main.py"] = r'''import asyncio

from factory.bot import main


if __name__ == "__main__":
    asyncio.run(main())
'''

files["README.md"] = r'''# مصنع الزعيم

مصنع لإدارة نسخ ZTele.

الوظائف:

- تنصيب عبر String Session.
- تنصيب عبر رقم Telegram.
- مدة اشتراك من 1 إلى 300 يوم.
- إشعار عند التنصيب.
- إيقاف الحساب عند انتهاء الاشتراك.
- إشعار انتهاء الاشتراك.
- تحديث حساب منفرد.
- تحديث جميع الحسابات.
- تحديث المصنع.
- حذف تنصيب.
- إعادة تشغيل حساب.
- إدارة الحسابات من Inline Keyboard.
- مدير واحد فقط.
'''

root = Path(".").resolve()

for name, content in files.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

print("======================================")
print(" Factory files created successfully")
print("======================================")

for name in sorted(files):
    print(name)
