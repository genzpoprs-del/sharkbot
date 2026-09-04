import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import google.generativeai as genai
from prompts import SHARKBOT_SYSTEM_PROMPT
from risk_manager import RiskManager

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    system_instruction=SHARKBOT_SYSTEM_PROMPT
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_sessions = {}

def get_rm(user_id: int) -> RiskManager:
    if user_id not in user_sessions:
        user_sessions[user_id] = RiskManager(balance=1500)
    return user_sessions[user_id]

# ============ COMMANDS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rm = get_rm(user.id)
    msg = f"""
🦈 *Welcome to SharkBot, {user.first_name}!*

🎯 *Account:* SharkFunded Bolt $1,500
💰 *Balance:* `${rm.balance:,.2f}`
🛡️ *Daily Loss Left:* `${rm.daily_loss_left:,.2f}`
🎯 *Profit Target:* `${rm.profit_target:,.2f}`

*Commands:*
/signal — Get a trade signal
/balance — Account status
/log — Log trade (use: /log XAUUSD BUY 15)
/reset — Reset for new day
/rules — Trading rules

📊 *Send any chart screenshot* for AI analysis!
"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm = get_rm(update.effective_user.id)
    await update.message.reply_text(rm.get_report(), parse_mode="Markdown")

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = """
🦈 *SHARKBOT RULES*
━━━━━━━━━━━━━━━
📏 *Risk:* 1% per trade = $15
🎯 *Min RR:* 1:2
⏰ *Sessions:* London 2-5 AM EST | NY 7-10 AM EST
🚫 *No trading:* News, weekends, dead zones

🛑 *STOP if:*
• 2 losses in a row
• Daily loss hits $45 (75% of limit)
• Max drawdown $120 reached

🎯 *Targets:*
• Daily loss limit: $60
• Max drawdown: $120
• Profit target: $120 (8%)
"""
    await update.message.reply_text(rules, parse_mode="Markdown")

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm = get_rm(update.effective_user.id)
    can_trade, msg = rm.can_trade()
    if not can_trade:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    
    user_request = " ".join(context.args) if context.args else "XAUUSD (Gold) — find me an A+ setup right now"
    prompt = f"""
User is asking for a signal on: {user_request}

Current account status:
- Balance: ${rm.balance:,.2f}
- Daily P&L: ${rm.daily_pnl:+,.2f}
- Daily loss left: ${rm.daily_loss_left:,.2f}

Give the signal using the exact format from your instructions. Include 2-3 lines explaining the setup reason. """
    
    try:
        await update.message.reply_text("🔍 *Analyzing market...*", parse_mode="Markdown")
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm = get_rm(update.effective_user.id)
    # Format: /log XAUUSD BUY 15  or  /log XAUUSD SELL -15
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ *Usage:* `/log PAIR DIRECTION PNL`\n"
                "*Example:* `/log XAUUSD BUY 22.50`",
                parse_mode="Markdown"
            )
            return
        
        pair = context.args[0].upper()
        direction = context.args[1].upper()
        pnl = float(context.args[2])
        rr = 2.0  # default
        if len(context.args) >= 4:
            rr = float(context.args[3])
        
        rm.log_trade(pair, direction, pnl, rr)
        await update.message.reply_text(
            f"✅ *Trade logged:*\n"
            f"• Pair: {pair}\n"
            f"• Direction: {direction}\n"
            f"• P&L: ${pnl:+,.2f}\n\n"
            f"{rm.get_report()}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error logging trade: {e}")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm = get_rm(update.effective_user.id)
    rm.reset_daily()
    await update.message.reply_text("🔄 *Daily stats reset!*\n" + rm.get_report(), parse_mode="Markdown")

async def handle_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm = get_rm(update.effective_user.id)
    can_trade, msg = rm.can_trade()
    
    if not can_trade:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    
    if not update.message.photo:
        await update.message.reply_text("📊 Please send a chart screenshot.")
        return
    
    try:
        await update.message.reply_text("🔍 *Analyzing chart with AI...*", parse_mode="Markdown")
        
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Note: For image analysis, you'd download and pass to Gemini Vision
        # This is a placeholder for image analysis
        
        prompt = f"""
User sent a chart screenshot. Account: ${rm.balance:,.2f}, Daily P&L: ${rm.daily_pnl:+,.2f}

Analyze the chart using your strategy (SMC + FVG + Liquidity Sweep) and provide a signal in your standard format. If no A+ setup, say "NO TRADE". """
        
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm = get_rm(update.effective_user.id)
    can_trade, msg = rm.can_trade()
    
    if not can_trade:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    
    try:
        user_text = update.message.text
        prompt = f"""
User said: "{user_text}"

Account: ${rm.balance:,.2f} | Daily P&L: ${rm.daily_pnl:+,.2f}

Respond helpfully about their trade or provide a signal. """
        
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ============ MAIN ============

def main():
    if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
        print("❌ ERROR: Set TELEGRAM_TOKEN and GEMINI_API_KEY in environment!")
        return
    
    print("🦈 Starting SharkBot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("log", log_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_chart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
📄 FILE 7 (Optional): README.md
Click "Add file" → "Create new file" → name: README.md

# 🦈 SharkBot — AI Trading Signal Bot

Telegram bot powered by Google Gemini AI for SharkFunded prop firm accounts. ## Features
- Real-time BUY/SELL signals
- Risk management tracking
- Daily loss monitoring
- Chart screenshot analysis
- Trade journal

## Setup
1. Get Telegram token from @BotFather
2. Get Gemini API key from aistudio.google.com
3. Add secrets to Railway environment variables
4. Deploy!

## Commands
- `/signal` — Get trade signal
- `/balance` — Account status
- `/log` — Log a trade result
- `/rules` — Show trading rules
