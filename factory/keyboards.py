from aiogram.types import (
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
