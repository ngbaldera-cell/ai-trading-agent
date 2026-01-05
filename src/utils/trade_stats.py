"""Utility for calculating trading performance statistics from diary entries."""

import json
import os
from typing import Optional


def calculate_performance(diary_path: str = "diary.jsonl") -> dict:
    """
    Calculate win rate and average PnL from closed trades in the diary.
    
    Returns:
        dict with total, wins, losses, win_rate, avg_win, avg_loss, last_5
    """
    if not os.path.exists(diary_path):
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "last_5": []
        }
    
    trades = []
    try:
        with open(diary_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Look for closed trades with outcome info
                    if entry.get("action") == "close" and "pnl_pct" in entry:
                        trades.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "last_5": []
        }
    
    if not trades:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "last_5": []
        }
    
    wins = [t for t in trades if t.get("pnl_pct", 0) > 0]
    losses = [t for t in trades if t.get("pnl_pct", 0) <= 0]
    
    avg_win = round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0
    
    last_5 = [
        {
            "asset": t.get("asset"),
            "outcome": t.get("outcome"),
            "pnl": t.get("pnl_pct"),
            "timestamp": t.get("timestamp")
        }
        for t in trades[-5:]
    ]
    
    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "last_5": last_5
    }


def get_trade_history(diary_path: str = "diary.jsonl", limit: int = 50) -> list:
    """
    Get recent trade history (entries and exits) for display.
    
    Returns:
        List of trade entries with relevant info for the dashboard
    """
    if not os.path.exists(diary_path):
        return []
    
    all_trades = []
    try:
        with open(diary_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    action = entry.get("action", "")
                    # Include buy, sell, close actions (skip holds)
                    if action in ("buy", "sell", "close"):
                        all_trades.append({
                            "timestamp": entry.get("timestamp"),
                            "asset": entry.get("asset"),
                            "action": action,
                            "entry_price": entry.get("entry_price"),
                            "exit_price": entry.get("exit_price"),
                            "pnl_pct": entry.get("pnl_pct"),
                            "outcome": entry.get("outcome"),
                            "allocation_usd": entry.get("allocation_usd"),
                            "is_long": entry.get("is_long"),
                            "rationale": entry.get("rationale", "")[:100]  # Truncate
                        })
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    
    # Return most recent first
    return list(reversed(all_trades[-limit:]))
