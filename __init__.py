from aqt import mw
from aqt import gui_hooks
import time
import os
import copy
from datetime import date

from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QUrl

# Temporary session stats
stats = {
    "current_streak": 0,
    "session_correct": 0,
    "session_total": 0,
    "current_miss_streak": 0,
    "session_time_spent": 0,
    "last_time_check": time.time()
}

# The history stack for our custom undo logic
undo_stack = []
ding_player = QSoundEffect()

def get_config():
    default_config = {
        "best_streak": 0, 
        "worst_miss_streak": 0,
        "daily_date": str(date.today()),
        "daily_reviews": 0,
        "daily_correct": 0,
        "daily_best_streak": 0,
        "daily_worst_miss_streak": 0,
        "daily_time_spent": 0  
    }
    config = mw.addonManager.getConfig(__name__) or {}
    
    for key, value in default_config.items():
        if key not in config:
            config[key] = value
    return config

def save_config(config):
    mw.addonManager.writeConfig(__name__, config)

def check_daily_rollover(config):
    today_str = str(date.today())
    if config.get("daily_date") != today_str:
        # Day changed! Reset Daily Config
        config["daily_date"] = today_str
        config["daily_reviews"] = 0
        config["daily_correct"] = 0
        config["daily_best_streak"] = 0
        config["daily_worst_miss_streak"] = 0
        config["daily_time_spent"] = 0
        save_config(config)
        
        # Also strictly reset the session stats since it's a new day
        stats["current_streak"] = 0
        stats["session_correct"] = 0
        stats["session_total"] = 0
        stats["current_miss_streak"] = 0
        stats["session_time_spent"] = 0
        stats["last_time_check"] = time.time()
        global undo_stack
        undo_stack.clear()
        
    return config

def update_timers(config):
    now = time.time()
    elapsed = now - stats.get("last_time_check", now)
    
    # Cap idle time at 60 seconds per interaction to maintain accurate active time
    if elapsed > 60:
        elapsed = 60
        
    # Both timers now pulse in perfect unison
    stats["session_time_spent"] += elapsed
    config["daily_time_spent"] += elapsed
    
    stats["last_time_check"] = now
    return config

def on_state_change(state, old_state):
    # We no longer wipe stats here. This simply resets the timer baseline 
    # so you don't get a 60s bump immediately upon returning to a deck.
    if state == "review" and old_state != "review":
        stats["last_time_check"] = time.time()

def on_answer(reviewer, card, ease):
    global undo_stack
    config = get_config()
    config = check_daily_rollover(config) 
    config = update_timers(config)
    
    undo_stack.append({
        "stats": copy.deepcopy(stats),
        "config": copy.deepcopy(config)
    })
    
    if len(undo_stack) > 50:
        undo_stack.pop(0)
        
    stats["session_total"] += 1
    config["daily_reviews"] += 1

    if ease > 1: 
        stats["current_streak"] += 1
        stats["session_correct"] += 1
        stats["current_miss_streak"] = 0
        config["daily_correct"] += 1
        
        if stats["current_streak"] > config.get("best_streak", 0):
            config["best_streak"] = stats["current_streak"]
        if stats["current_streak"] > config.get("daily_best_streak", 0):
            config["daily_best_streak"] = stats["current_streak"]
            
        save_config(config)
        
        addon_path = os.path.dirname(__file__)
        if stats["current_streak"] >= 30:
            sound_file = "ding_30.wav"
        elif stats["current_streak"] >= 20:
            sound_file = "ding_20.wav"
        elif stats["current_streak"] >= 10:
            sound_file = "ding_10.wav"
        else:
            sound_file = "ding.wav"
            
        sound_path = os.path.join(addon_path, sound_file)
        if not os.path.exists(sound_path):
            sound_path = os.path.join(addon_path, "ding.wav")
            
        if os.path.exists(sound_path):
            ding_player.setSource(QUrl.fromLocalFile(sound_path))
            ding_player.play()

    else: 
        stats["current_streak"] = 0
        stats["current_miss_streak"] += 1
        
        if stats["current_miss_streak"] > config.get("worst_miss_streak", 0):
            config["worst_miss_streak"] = stats["current_miss_streak"]
        if stats["current_miss_streak"] > config.get("daily_worst_miss_streak", 0):
            config["daily_worst_miss_streak"] = stats["current_miss_streak"]
            
        save_config(config)

def handle_undo():
    global undo_stack
    if undo_stack:
        last_state = undo_stack.pop()
        stats.update(last_state["stats"])
        save_config(last_state["config"])
        stats["last_time_check"] = time.time() # Ensures the undo gap doesn't break the timer

mw.form.actionUndo.triggered.connect(handle_undo)

def on_webview_msg(handled, message, context):
    if message == "gamified_clear_session":
        stats["current_streak"] = 0
        stats["session_correct"] = 0
        stats["session_total"] = 0
        stats["current_miss_streak"] = 0
        stats["session_time_spent"] = 0
        stats["last_time_check"] = time.time()
        global undo_stack
        undo_stack.clear()
        
        mw.reviewer.refresh_if_needed()
        return (True, None)
    return handled

gui_hooks.webview_did_receive_js_message.append(on_webview_msg)

def append_stats_to_html(text, card, kind):
    config = get_config()
    config = check_daily_rollover(config)
    config = update_timers(config)
    save_config(config) # Ensures idle time saves even if you close Anki without answering
    
    s_elapsed = int(stats.get("session_time_spent", 0))
    s_mins, s_secs = divmod(s_elapsed, 60)
    timer_str = f"{s_mins:02d}:{s_secs:02d}"
    
    daily_elapsed = int(config.get("daily_time_spent", 0))
    d_hours, remainder = divmod(daily_elapsed, 3600)
    d_mins, d_secs = divmod(remainder, 60)
    if d_hours > 0:
        daily_time_str = f"{d_hours}h {d_mins}m"
    else:
        daily_time_str = f"{d_mins}m {d_secs}s"
    
    session_pct = 0
    if stats["session_total"] > 0:
        session_pct = int((stats["session_correct"] / stats["session_total"]) * 100)
        
    daily_pct = 0
    if config["daily_reviews"] > 0:
        daily_pct = int((config["daily_correct"] / config["daily_reviews"]) * 100)
        
    if stats["current_miss_streak"] > 0:
        streak_display = f"<b style='font-size: 16px; color: #ff4444;'>💔 Misses: {stats['current_miss_streak']}</b>"
    else:
        streak_display = f"<b style='font-size: 16px; color: var(--fg);'>🔥 Streak: {stats['current_streak']}</b>"
        
    stats_html = f"""
    <div style="position: relative; text-align: center; margin-bottom: 15px; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: transparent;">
        
        <button onclick="pycmd('gamified_clear_session');" style="position: absolute; top: 8px; right: 8px; cursor: pointer; background: transparent; border: 1px solid var(--border); border-radius: 4px; color: var(--fg); padding: 3px 8px; font-size: 11px; opacity: 0.7; transition: opacity 0.2s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.7'">🔄 Clear</button>
        
        <div style="margin-bottom: 6px; padding-top: 5px;">
            <b style="font-size: 16px; color: var(--fg);">⏱️ {timer_str}</b> &nbsp;|&nbsp; 
            {streak_display} &nbsp;|&nbsp; 
            <b style="font-size: 16px; color: var(--fg);">🎯 Session Score: {session_pct}%</b>
        </div>
        <div style="font-size: 13.5px; color: var(--fg); opacity: 0.9; margin-bottom: 5px;">
            📅 <b>Today:</b> {daily_time_str} &nbsp;|&nbsp; {config['daily_reviews']} Reviews &nbsp;|&nbsp; {daily_pct}% Correct &nbsp;|&nbsp; Best: {config['daily_best_streak']} &nbsp;|&nbsp; Worst: {config.get('daily_worst_miss_streak', 0)}
        </div>
        <div style="font-size: 11px; margin-top: 5px; opacity: 0.6; color: var(--fg);">
            🏆 All-Time Best: {config.get('best_streak', 0)} | 💀 Worst Misses: {config.get('worst_miss_streak', 0)}
        </div>
    </div>
    <hr style="border: none; border-top: 1px solid var(--border);">
    """
    return stats_html + text

gui_hooks.state_did_change.append(on_state_change)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.card_will_show.append(append_stats_to_html)