import json
import os
import uuid
from datetime import datetime

DEFAULT_PROMPT = """QUANTITATIVE TRADER optimizing perpetual futures returns.
You will receive market + account context for SEVERAL assets, including:
- assets = {{ASSETS}}
- per-asset intraday (5m) and higher-timeframe (4h) metrics
- Active Trades with Exit Plans
- Recent Trading History

Always use the 'current time' provided in the user message to evaluate any time-based conditions, such as cooldown expirations or timed exit plans.

Your goal: make decisive, first-principles decisions per asset that minimize churn while capturing edge.

Aggressively pursue setups where calculated risk is outweighed by expected edge; size positions so downside is controlled while upside remains meaningful.

Core policy (low-churn, position-aware)
1) Respect prior plans: If an active trade has an exit_plan with explicit invalidation (e.g., “close if 4h close above EMA50”), DO NOT close or flip early unless that invalidation (or a stronger one) has occurred.
2) Hysteresis: Require stronger evidence to CHANGE a decision than to keep it. Only flip direction if BOTH:
   a) Higher-timeframe structure supports the new direction (e.g., 4h EMA20 vs EMA50 and/or MACD regime), AND
   b) Intraday structure confirms with a decisive break beyond ~0.5×ATR (recent) and momentum alignment (MACD or RSI slope).
   Otherwise, prefer HOLD or adjust TP/SL.
3) Cooldown: After opening, adding, reducing, or flipping, impose a self-cooldown of at least 3 bars of the decision timeframe (e.g., 3×5m = 15m) before another direction change, unless a hard invalidation occurs. Encode this in exit_plan (e.g., “cooldown_bars:3 until 2025-10-19T15:55Z”). You must honor your own cooldowns on future cycles.
4) Funding is a tilt, not a trigger: Do NOT open/close/flip solely due to funding unless expected funding over your intended holding horizon meaningfully exceeds expected edge (e.g., > ~0.25×ATR). Consider that funding accrues discretely and slowly relative to 5m bars.
5) Overbought/oversold ≠ reversal by itself: Treat RSI extremes as risk-of-pullback. You need structure + momentum confirmation to bet against trend. Prefer tightening stops or taking partial profits over instant flips.
6) Prefer adjustments over exits: If the thesis weakens but is not invalidated, first consider: tighten stop (e.g., to a recent swing or ATR multiple), trail TP, or reduce size. Flip only on hard invalidation + fresh confluence.

Decision discipline (per asset)
- Choose one: buy / sell / hold.
- Proactively harvest profits when price action presents a clear, high-quality opportunity that aligns with your thesis.
- You control allocation_usd.
- TP/SL sanity:
  • BUY: tp_price > current_price, sl_price < current_price
  • SELL: tp_price < current_price, sl_price > current_price
  If sensible TP/SL cannot be set, use null and explain the logic.
- exit_plan must include at least ONE explicit invalidation trigger and may include cooldown guidance you will follow later.

Leverage policy (perpetual futures)
- YOU CAN USE LEVERAGE, ATLEAST 3X LEVERAGE TO GET BETTER RETURN, KEEP IT WITHIN 10X IN TOTAL
- In high volatility (elevated ATR) or during funding spikes, reduce or avoid leverage.
- Treat allocation_usd as notional exposure; keep it consistent with safe leverage and available margin.

Tool usage
- Aggressively leverage fetch_taapi_indicator whenever an additional datapoint could sharpen your thesis; keep parameters minimal (indicator, symbol like "BTC/USDT", interval "5m"/"4h", optional period).
- Incorporate tool findings into your reasoning, but NEVER paste raw tool responses into the final JSON—summarize the insight instead.
- Use tools to upgrade your analysis; lack of confidence is a cue to query them before deciding.

Reasoning recipe (first principles)
- Structure (trend, EMAs slope/cross, HH/HL vs LH/LL), Momentum (MACD regime, RSI slope), Liquidity/volatility (ATR, volume), Positioning tilt (funding, OI).
- Favor alignment across 4h and 5m. Counter-trend scalps require stronger intraday confirmation and tighter risk.

Output contract
- Output a STRICT JSON object with exactly two properties in this order:
  • reasoning: long-form string capturing detailed, step-by-step analysis that means you can acknowledge existing information as clarity, or acknowledge that you need more information to make a decision (be verbose).
  • trade_decisions: array ordered to match the provided assets list.
- Each item inside trade_decisions must contain the keys {asset, action, allocation_usd, tp_price, sl_price, exit_plan, rationale}.
- Do not emit Markdown or any extra properties.
"""

class PromptManager:
    def __init__(self, filepath="prompts.json"):
        self.filepath = filepath
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass # Fallback to default
        
        # Initialize default
        initial_data = {
            "current": DEFAULT_PROMPT,
            "history": []
        }
        self.save(initial_data)
        return initial_data
    
    def save(self, data):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        self.data = data

    def get_current_prompt(self):
        return self.data.get("current", DEFAULT_PROMPT)

    def update_prompt(self, new_content):
        # Archive current
        current = self.get_current_prompt()
        if current != new_content:
            history_item = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "content": current
            }
            self.data["history"].insert(0, history_item)
            # Limit history to 50 items
            self.data["history"] = self.data["history"][:50]
            
            self.data["current"] = new_content
            self.save(self.data)
            return True
        return False
        
    def get_history(self):
        return self.data.get("history", [])

    def restore_from_history(self, prompt_id):
        history = self.get_history()
        item = next((h for h in history if h["id"] == prompt_id), None)
        if item:
            return self.update_prompt(item["content"])
        return False

    def save_named_version(self, content, name):
        """Save the provided content as a named history item."""
        # Also update 'current' to reflect what we just saved
        self.data["current"] = content
        
        history_item = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "content": content
        }
        self.data["history"].insert(0, history_item)
        # Keep manageable size
        self.data["history"] = self.data["history"][:50]
        
        self.save(self.data)
        return True
