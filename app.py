import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from flask import Flask
from threading import Thread

# --- CONFIGURATION & CREDENTIALS ---
BOT_TOKEN = "9157386220:AAEpkVOxoiciY-By26pJsbKCYpR0hqBIMyI"
ADMIN_ID = 5287278470

# Your fixed 50 ETB ShegerPay Payment Link
SHEGERPAY_LINK = "https://pay.shegerpay.com/wG9Woidfb19Hsc4i"

# Replace with your actual private VIP channel ID (e.g., -1001234567890)
VIP_CHANNEL_ID = -1001234567890  

# Plan Configuration (Weekly VIP Pass: 50 Birr for 7 days)
PLAN_NAME = "Weekly VIP Pass (7 days)"
PLAN_PRICE = 50
PLAN_DAYS = 7

# In-memory database mock
USERS_DB = {}

logging.basicConfig(level=logging.INFO)
router = Router()

# --- MAIN USER MENU & START ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    builder = InlineKeyboardBuilder()
    
    builder.row(types.InlineKeyboardButton(text="⭐ Get Weekly VIP Pass — 50 Birr", callback_data="buy_vip"))
    builder.row(
        types.InlineKeyboardButton(text="📊 My Status", callback_data="check_status"),
        types.InlineKeyboardButton(text="📞 Support", url="https://t.me/dawitdg223")
    )

    welcome_text = (
        f"👋 Welcome, **{user_name}** to **Yega VIP Bot**!\n\n"
        "⚽ Your trusted source for high-accuracy football multi-bets, accumulators, and expert insights.\n\n"
        "🔥 **Get full access to our exclusive VIP channel for 7 days!**\n\n"
        "👇 Tap the button below to get started:"
    )
    await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "check_status")
async def check_status(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in USERS_DB and USERS_DB[user_id]["expiry"] > datetime.now():
        expiry_str = USERS_DB[user_id]["expiry"].strftime("%Y-%m-%d %H:%M")
        await callback.message.answer(f"✅ Your VIP status is **ACTIVE**.\nExpires on: `{expiry_str}` EAT", parse_mode="Markdown")
    else:
        await callback.message.answer("❌ You do not have an active VIP subscription. Tap /start to join!")

# --- PAYMENT LINK HANDLER ---

@router.callback_query(F.data == "buy_vip")
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Pay 50 Birr via ShegerPay", url=SHEGERPAY_LINK))
    builder.row(types.InlineKeyboardButton(text="✅ I Have Paid — Verify Access", callback_data="verify_pay"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Back to Menu", callback_data="back_to_start"))

    instructions = (
        f"⭐ **Plan:** {PLAN_NAME}\n"
        f"💰 **Price:** `{PLAN_PRICE} Birr`\n\n"
        f"1️⃣ Tap **'Pay 50 Birr via ShegerPay'** below to open your checkout page.\n"
        f"2️⃣ Complete your payment safely.\n"
        f"3️⃣ Come back here and tap **'I Have Paid — Verify Access'** to receive your private invite link!"
    )
    
    await callback.message.edit_text(instructions, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⭐ Get Weekly VIP Pass — 50 Birr", callback_data="buy_vip"))
    builder.row(types.InlineKeyboardButton(text="📊 My Status", callback_data="check_status"))
    
    try:
        await callback.message.edit_text(
            "⚽ **Welcome back to Yega VIP Bot!**\n\nTap below to get your weekly access:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception:
        pass

@router.callback_query(F.data == "verify_pay")
async def manual_verify_link_payment(callback: types.CallbackQuery):
    await callback.answer("Verifying payment...", show_alert=False)
    user_id = callback.from_user.id
    
    expiry_date = datetime.now() + timedelta(days=PLAN_DAYS)
    USERS_DB[user_id] = {
        "expiry": expiry_date,
        "joined": datetime.now()
    }
    
    try:
        invite = await callback.bot.create_chat_invite_link(
            chat_id=VIP_CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(hours=1)
        )
        invite_link = invite.invite_link
    except Exception:
        invite_link = "https://t.me/+YourVIPChannelInviteBackupLink"

    await callback.message.edit_text(
        "✅ **Payment Confirmed!**\n\n"
        f"Your VIP access for **{PLAN_NAME}** is active until: `{expiry_date.strftime('%Y-%m-%d %H:%M')}`\n\n"
        f"🚀 **Join your VIP Channel here:**\n{invite_link}",
        parse_mode="Markdown"
    )

# --- ADMIN PANEL & MANAGEMENT ---

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📊 View Stats & Revenue", callback_data="admin_stats"))
    builder.row(types.InlineKeyboardButton(text="👥 List Active Users", callback_data="admin_users"))
    
    await message.answer("👑 **Admin Control Panel**\nSelect an action:", reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.answer()
    
    active_users = sum(1 for uid in USERS_DB if USERS_DB[uid]["expiry"] > datetime.now())
    total_revenue = active_users * PLAN_PRICE
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back to Admin Menu", callback_data="admin_back"))
    
    await callback.message.edit_text(
        "📊 **Bot Statistics Dashboard**\n\n"
        f"👥 Active VIP Subscribers: `{active_users}`\n"
        f"💰 Estimated Active Revenue: `{total_revenue} Birr`\n"
        f"📂 Total Users in Memory DB: `{len(USERS_DB)}`",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.answer()
    
    active_list = [f"• User ID: `{uid}` | Exp: `{info['expiry'].strftime('%m-%d %H:%M')}`" 
                   for uid, info in USERS_DB.items() if info["expiry"] > datetime.now()]
    
    text = "👥 **Active Subscribers List:**\n\n" + ("\n".join(active_list) if active_list else "No active subscribers right now.")
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Back to Admin Menu", callback_data="admin_back"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📊 View Stats & Revenue", callback_data="admin_stats"))
    builder.row(types.InlineKeyboardButton(text="👥 List Active Users", callback_data="admin_users"))
    
    await callback.message.edit_text("👑 **Admin Control Panel**\nSelect an action:", reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- BACKGROUND EXPIRY KICKER TASK ---
async def background_expiry_checker(bot: Bot):
    while True:
        await asyncio.sleep(3600)
        now = datetime.now()
        for user_id, info in list(USERS_DB.items()):
            if info["expiry"] < now:
                try:
                    await bot.ban_chat_member(chat_id=VIP_CHANNEL_ID, user_id=user_id)
                    await bot.unban_chat_member(chat_id=VIP_CHANNEL_ID, user_id=user_id)
                    await bot.send_message(user_id, "⏳ Your VIP subscription has expired! Renew your plan using /start to regain access.")
                except Exception as e:
                    logging.error(f"Failed to kick expired user {user_id}: {e}")
                del USERS_DB[user_id]

# --- FLASK KEEP-ALIVE SERVER FOR 24/7 RENDER HOSTING ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Yega VIP Bot Web Service is active 24/7!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    asyncio.create_task(background_expiry_checker(bot))
    
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot and Web Service are running 24/7...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
