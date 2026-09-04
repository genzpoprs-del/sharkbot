from datetime import date

class RiskManager:
    def __init__(self, balance: float = 1500.0):
        self.starting_balance = balance
        self.balance = balance
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0
        self.consecutive_losses = 0
        self.trade_log = []
        self.today = date.today()
        self.daily_loss_limit = balance * 0.04   # $60
        self.max_drawdown = balance * 0.08       # $120
        self.profit_target = balance * 0.08      # $120
        self.risk_per_trade = balance * 0.01     # $15
        self.daily_loss_left = self.daily_loss_limit

    def reset_daily(self):
        if date.today() != self.today:
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.wins_today = 0
            self.losses_today = 0
            self.consecutive_losses = 0
            self.daily_loss_left = self.daily_loss_limit
            self.today = date.today()

    def log_trade(self, pair: str, direction: str, pnl: float, rr: float):
        self.reset_daily()
        self.balance += pnl
        self.daily_pnl += pnl
        self.total_pnl += pnl
        self.trades_today += 1
        self.daily_loss_left = self.daily_loss_limit - abs(min(self.daily_pnl, 0))
        
        if pnl > 0:
            self.wins_today += 1
            self.consecutive_losses = 0
        else:
            self.losses_today += 1
            self.consecutive_losses += 1
        
        self.trade_log.append({
            "pair": pair, "direction": direction,
            "pnl": pnl, "rr": rr,
            "balance_after": self.balance
        })

    def can_trade(self) -> tuple[bool, str]:
        self.reset_daily()
        if self.daily_loss_left <= 15:  # 75% of limit
            return False, "⛔ Daily loss limit reached (75% used). Stop trading."
        if self.consecutive_losses >= 2:
            return False, "⛔ 2 consecutive losses. Stop for the day."
        if abs(self.daily_pnl) >= self.daily_loss_limit:
            return False, "⛔ Max daily loss hit. Stop trading."
        if -self.total_pnl >= self.max_drawdown:
            return False, "⛔ Max drawdown breached. Account at risk."
        if self.total_pnl >= self.profit_target:
            return False, "🎉 Profit target hit! Consider stopping."
        return True, "✅ Trading allowed"

    def get_status(self) -> dict:
        self.reset_daily()
        progress = (self.total_pnl / self.profit_target) * 100 if self.profit_target > 0 else 0
        return {
            "balance": self.balance,
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "daily_loss_left": self.daily_loss_left,
            "progress": max(0, progress),
            "trades_today": self.trades_today,
            "wins_today": self.wins_today,
            "losses_today": self.losses_today,
            "consecutive_losses": self.consecutive_losses,
            "win_rate": (self.wins_today / self.trades_today * 100) if self.trades_today > 0 else 0
        }

    def get_report(self) -> str:
        s = self.get_status()
        can_trade, msg = self.can_trade()
        report = f"""
🦈 *ACCOUNT STATUS*
━━━━━━━━━━━━━━━
💰 Balance: `${s['balance']:,.2f}`
📅 Daily P&L: `${s['daily_pnl']:+,.2f}`
🛡️ Daily Loss Left: `${s['daily_loss_left']:,.2f}`
📊 Total P&L: `${s['total_pnl']:+,.2f}`
🎯 Target Progress: `{s['progress']:.1f}%`
━━━━━━━━━━━━━━━
📈 Trades Today: {s['trades_today']} (W:{s['wins_today']} / L:{s['losses_today']})
🎯 Win Rate: {s['win_rate']:.0f}%
⚠️ Consecutive Losses: {s['consecutive_losses']}
━━━━━━━━━━━━━━━
{msg}
"""
        return report
