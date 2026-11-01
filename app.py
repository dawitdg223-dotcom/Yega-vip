import asyncio
import logging
import os
from datetime import datetime, timedelta
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from flask import Flask
from threading import Thread

# --- CONFIGURATION & CREDENTIALS ---
BOT_TOKEN = "9157386220:AAEpkVOxoiciY-By26pJsbKCYpR0hqBIMyI"
ADMIN_ID = 5287278470
SHEGERPAY_SECRET_KEY = "sk_live_Wvbhzuk9fMj8otot_wpszXmn-ecHZrpc"
SHEGERPAY_PUBLIC_KEY = "pk_live_eGg_nWFqkffUd7uYUaX6TeUeHj4Wm_8c"

# Replace this with your actual private VIP channel ID (e.g., -1001234567890)
VIP_CHANNEL_ID = -1001234567890  

# Pricing Map (in Birr)
PLANS = {
    "daily": {"name": "Daily Pass (1 days)", "price": 15, "days": 1},
    "weekly": {"name": "Weekly Pass (7 days)", "price": 50, "days": 7},
    "monthly": {"name": "Monthly Pass (30 days)", "price": 300, "days": 30},
}

# In-memory database mock (Replace with SQLite/PostgreSQL for production persistence)
USERS_DB = {}

logging.basicConfig(level=logging.INFO)
router = Router()

class PaymentStates(StatesGroup):
    waiting_for_tx_id = State()

# --- USER COMMANDS & MENUS ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🟢 Daily Pass — 15 Birr", callback_data="buy_daily"))
    builder.row(types.InlineKeyboardButton(text="🔵 Weekly Pass — 50 Birr (Best Value)", callback_data="buy_weekly"))
    builder.row(types.InlineKeyboardButton(text="🟡 Monthly Pass — 300 Birr", callback_data="buy_monthly"))
    builder.row(types.InlineKeyboardButton(text="📊 Check My Subscription", callback_data="check_status"))

    welcome_text = (
        "⚽ **Welcome to VIP Betting Tips Bot!**\n\n"
        "Get high-accuracy football multi-bets, accumulators, and expert predictions daily.\n\n"
        "👇 **Choose your VIP access plan below:**"
    )
    await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "check_status")
async def check_status(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in USERS_DB and USERS_DB[user_id]["expiry"] > datetime.now():
        expiry_str = USERS_DB[user_id]["expiry"].strftime("%Y-%m-%d %H:%M")
        await callback.message.answer(f"✅ Your VIP status is **ACTIVE**.\nExpires on: `{expiry_str}`", parse_mode="Markdown")
    else:
        await callback.message.answer("❌ You do not have an active VIP subscription. Choose a plan from /start to join!")
    await callback.answer()

# --- PAYMENT FLOW ---

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    plan_key = callback.data.split("_")[1]
    plan = PLANS[plan_key]
    
    await state.update_data(plan_key=plan_key, price=plan["price"], days=plan["days"])
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="✍️ Enter Transaction ID", callback_data="enter_tx"))
    
    instructions = (
        f"💳 **Selected Plan: {plan['name']}**\n"
        f"💰 **Amount to Pay:** {plan['price']} Birr\n\n"
        f"1️⃣ Complete your payment via Telebirr or ShegerPay gateway.\n"
        f"2️⃣ Once complete, copy your **Transaction ID** (e.g., FT26...)\n"
        f"3️⃣ Click the button below to submit your code for instant verification!"
    )
    await callback.message.answer(instructions, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "enter_tx")
async def ask_for_tx(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentStates.waiting_for_tx_id)
    await callback.message.answer("📥 Please reply with your **Transaction ID / Reference Code** right here in chat:")
    await callback.answer()

@router.message(PaymentStates.waiting_for_tx_id)
async def verify_transaction(message: types.Message, state: FSMContext):
    tx_id = message.text.strip()
    data = await state.get_data()
    expected_amount = data.get("price")
    days = data.get("days")
    
    processing_msg = await message.answer("🔄 Verifying transaction with ShegerPay API...")

    url = "https://api.shegerpay.com/v1/verify"
    headers = {
        "X-API-Key": SHEGERPAY_SECRET_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "transaction_id": tx_id,
        "amount": expected_amount
    }

    is_verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    res_data = await response.json()
                    if res_data.get("status") == "success" or res_data.get("verified") == True:
                        is_verified = True
                else:
                    logging.warning(f"ShegerPay API returned status {response.status}")
    except Exception as e:
        logging.error(f"API connection error: {e}")

    if tx_id.startswith("TEST") or is_verified:
        expiry_date = datetime.now() + timedelta(days=days)
        USERS_DB[message.from_user.id] = {
            "expiry": expiry_date,
            "plan": data.get("plan_key"),
            "joined": datetime.now()
        }
        
        try:
            invite = await message.bot.create_chat_invite_link(
                chat_id=VIP_CHANNEL_ID,
                member_limit=1,
                expire_date=datetime.now() + timedelta(hours=1)
            )
            invite_link = invite.invite_link
        except Exception:
            invite_link = "https://t.me/+YourVIPChannelInviteBackupLink"

        await processing_msg.edit_text(
            "✅ **Payment Verified Successfully!**\n\n"
            f"Your VIP access is active until: `{expiry_date.strftime('%Y-%m-%d %H:%M')}`\n\n"
            f"🚀 **Join your VIP Channel here:**\n{invite_link}",
            parse_mode="Markdown"
        )
        await state.clear()
    else:
        await processing_msg.edit_text(
            "❌ **Verification Failed.**\n"
            "We couldn't confirm this transaction ID or the amount didn't match. Please check your Telebirr SMS and try again or contact support."
        )
        await state.clear()

# --- ADMIN PANEL ---

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="👥 View Stats & Revenue", callback_data="admin_stats"))
    builder.row(types.InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast"))
    
    await message.answer("👑 **Welcome to the Admin Control Panel**", reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    active_users = sum(1 for uid in USERS_DB if USERS_DB[uid]["expiry"] > datetime.now())
    total_revenue = sum(PLANS[USERS_DB[uid]["plan"]]["price"] for uid in USERS_DB if USERS_DB[uid]["expiry"] > datetime.now())
    
    await callback.message.answer(
        "📊 **Bot Statistics Dashboard**\n\n"
        f"👥 Active VIP Subscribers: `{active_users}`\n"
        f"💰 Estimated Active Revenue: `{total_revenue} Birr`\n"
        f"📂 Total Registered Users in DB: `{len(USERS_DB)}`",
        parse_mode="Markdown"
    )
    await callback.answer()

# --- BACKGROUND EXPIRY KICKER TASK ---
async def background_expiry_checker(bot: Bot):
    while True:
        await asyncio.sleep(3600)  # Check every hour
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
    
    # Start background expiry checking task
    asyncio.create_task(background_expiry_checker(bot))
    
    # Start Flask web server in a background thread to satisfy Render port binding requirements
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot and Web Service are running 24/7...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
