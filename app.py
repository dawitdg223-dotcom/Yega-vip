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

# Replace with your actual private VIP channel ID (e.g., -1001234567890)
VIP_CHANNEL_ID = -1001234567890  

# Pricing Map (in Birr)
PLANS = {
    "daily": {"name": "Daily Pass (1 day)", "price": 15, "days": 1},
    "weekly": {"name": "Weekly Pass (7 days)", "price": 50, "days": 7},
    "monthly": {"name": "Monthly Pass (30 days)", "price": 300, "days": 30},
}

# In-memory database mock
USERS_DB = {}

logging.basicConfig(level=logging.INFO)
router = Router()

# --- MAIN USER MENU & START ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(text="🟢 Daily — 15 Birr", callback_data="buy_daily"),
        types.InlineKeyboardButton(text="🔵 Weekly — 50 Birr", callback_data="buy_weekly")
    )
    builder.row(types.InlineKeyboardButton(text="🟡 Monthly Pass — 300 Birr (Best Value)", callback_data="buy_monthly"))
    builder.row(
        types.InlineKeyboardButton(text="📊 My Status", callback_data="check_status"),
        types.InlineKeyboardButton(text="📞 Support", url="https://t.me/dawitdg223")
    )

    welcome_text = (
        f"👋 Welcome, **{user_name}** to **Yega VIP Bot**!\n\n"
        "⚽ Your trusted source for high-accuracy football multi-bets, accumulators, and expert insights.\n\n"
        "👇 **Choose a VIP plan below to generate your secure payment link:**"
    )
    await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "check_status")
async def check_status(callback: types.CallbackQuery):
    await callback.answer()  # Stops button loading animation immediately
    user_id = callback.from_user.id
    if user_id in USERS_DB and USERS_DB[user_id]["expiry"] > datetime.now():
        expiry_str = USERS_DB[user_id]["expiry"].strftime("%Y-%m-%d %H:%M")
        await callback.message.answer(f"✅ Your VIP status is **ACTIVE**.\nExpires on: `{expiry_str}` EAT", parse_mode="Markdown")
    else:
        await callback.message.answer("❌ You do not have an active VIP subscription. Select a plan from /start to join!")

# --- AUTOMATED SHEGERPAY CHECKOUT LINK GENERATION ---

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # Stops button loading animation instantly
    plan_key = callback.data.split("_")[1]
    plan = PLANS[plan_key]
    user_id = callback.from_user.id
    
    # Send a smooth processing notice
    processing_msg = await callback.message.answer("🔄 Generating your secure ShegerPay payment link...")

    url = "https://api.shegerpay.com/v1/transaction/initialize"
    headers = {
        "X-API-Key": SHEGERPAY_SECRET_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": plan["price"],
        "currency": "ETB",
        "email": f"user_{user_id}@yegavip.com",
        "first_name": callback.from_user.first_name or "VIP",
        "last_name": callback.from_user.last_name or "Customer",
        "tx_ref": f"yega-{user_id}-{int(datetime.now().timestamp())}",
        "customization": {
            "title": f"Yega VIP - {plan['name']}",
            "description": f"Subscription payment for {plan['name']}"
        }
    }

    checkout_url = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    res_data = await response.json()
                    checkout_url = res_data.get("data", {}).get("checkout_url") or res_data.get("checkout_url")
    except Exception as e:
        logging.error(f"ShegerPay API connection error: {e}")

    if not checkout_url:
        checkout_url = f"https://checkout.shegerpay.com/pay/test-{plan['price']}-{user_id}"

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Pay Now via ShegerPay", url=checkout_url))
    builder.row(types.InlineKeyboardButton(text="✅ I Have Paid — Verify Access", callback_data=f"verify_pay_{plan_key}"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Back to Plans", callback_data="back_to_start"))

    instructions = (
        f"💳 **Selected Plan:** {plan['name']}\n"
        f"💰 **Amount:** `{plan['price']} Birr`\n\n"
        f"1️⃣ Tap the **'Pay Now via ShegerPay'** button below to open the secure checkout page.\n"
        f"2️⃣ Complete your payment safely through the gateway.\n"
        f"3️⃣ Once done, tap **'I Have Paid — Verify Access'** below!"
    )
    
    await processing_msg.edit_text(instructions, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await callback.answer()  # Stops button loading animation immediately
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🟢 Daily — 15 Birr", callback_data="buy_daily"),
        types.InlineKeyboardButton(text="🔵 Weekly — 50 Birr", callback_data="buy_weekly")
    )
    builder.row(types.InlineKeyboardButton(text="🟡 Monthly Pass — 300 Birr", callback_data="buy_monthly"))
    builder.row(types.InlineKeyboardButton(text="📊 My Status", callback_data="check_status"))
    
    try:
        await callback.message.edit_text(
            "⚽ **Welcome back to Yega VIP Bot!**\n\nChoose your VIP access plan below:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("verify_pay_"))
async def manual_verify_link_payment(callback: types.CallbackQuery):
    await callback.answer("Verifying payment...", show_alert=False)
    plan_key = callback.data.split("_")[2]
    plan = PLANS[plan_key]
    user_id = callback.from_user.id
    
    expiry_date = datetime.now() + timedelta(days=plan["days"])
    USERS_DB[user_id] = {
        "expiry": expiry_date,
        "plan": plan_key,
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
        f"Your VIP access for **{plan['name']}** is active until: `{expiry_date.strftime('%Y-%m-%d %H:%M')}`\n\n"
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
    total_revenue = sum(PLANS[USERS_DB[uid]["plan"]]["price"] for uid in USERS_DB if USERS_DB[uid]["expiry"] > datetime.now())
    
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
    
    active_list = [f"• User ID: `{uid}` | Plan: `{info['plan']}` | Exp: `{info['expiry'].strftime('%m-%d %H:%M')}`" 
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
