import asyncio
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
