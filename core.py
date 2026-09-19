"""Review progress, independent of Anki and Qt. No scheduling changes."""

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date
import math
import time


DEFAULTS = {
    "daily_goal": 100,
    "sound_mode": "all",
    "sound_volume": 0.35,
    "show_details": False,
    "animations": True,
}
COUNTERS = (
    "best_streak", "worst_miss_streak", "daily_reviews", "daily_correct",
    "daily_best_streak", "daily_worst_miss_streak",
)
DAILY_COUNTERS = tuple(key for key in COUNTERS if key.startswith("daily_"))


def number(value, default=0, maximum=None):
    try:
        result = float(value)
        if not math.isfinite(result) or isinstance(value, bool):
            return default
        result = max(0, result)
        return min(result, maximum) if maximum is not None else result
    except (TypeError, ValueError, OverflowError):
        return default


def settings(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULTS)
    out["daily_goal"] = int(number(raw.get("daily_goal", 100), 100, 100000))
    out["sound_volume"] = number(raw.get("sound_volume", .35), .35, 1)
    if raw.get("sound_mode") in ("all", "milestones", "off"):
        out["sound_mode"] = raw["sound_mode"]
    for key in ("show_details", "animations"):
        if isinstance(raw.get(key), bool):
            out[key] = raw[key]
    return out


def progress(raw, today):
    raw = raw if isinstance(raw, dict) else {}
    out = {key: int(number(raw.get(key, 0))) for key in COUNTERS}
    out["daily_correct"] = min(out["daily_correct"], out["daily_reviews"])
    out["daily_date"] = str(raw.get("daily_date", today))
    out["daily_time_spent"] = number(raw.get("daily_time_spent", 0))
    return out


def next_milestone(streak):
    return next((n for n in (5, 10, 20, 30, 50, 75, 100) if n > streak),
                (streak // 50 + 1) * 50)


@dataclass
class Session:
    total: int = 0
    correct: int = 0
    streak: int = 0
    misses: int = 0
    seconds: float = 0


@dataclass
class ReviewChange:
    before: dict
    after: dict
    session_before: Session
    session_after: Session
    day: str
    generation: int
    applied: bool = True


class Tracker:
    def __init__(self, saved=None, options=None, clock=time.monotonic, today=date.today):
        self.clock, self.today = clock, today
        self.options = settings(options)
        self.data = progress(saved, str(today()))
        self.session = Session()
        self.history = OrderedDict()
        self.generation = 0
        self.active = False
        self.last_tick = self.deadline = clock()
        self.dirty = False
        self.feedback = "One word at a time. Let's go."
        self.celebration = False
        self.event_id = 0
        self.rollover()

    def rollover(self):
        today = str(self.today())
        if self.data["daily_date"] == today:
            return False
        for key in DAILY_COUNTERS:
            self.data[key] = 0
        self.data.update(daily_date=today, daily_time_spent=0)
        self.reset_session()
        self.dirty = True
        return True

    def reset_session(self):
        self.session = Session()
        self.generation += 1
        self.last_tick = self.deadline = self.clock()
        self.feedback = "Fresh session. One word at a time."
        self.celebration = False
        self.event_id += 1

    def tick(self):
        now = self.clock()
        if self.rollover():
            # Do not charge the previous day's idle gap to the new day.
            self.deadline = now + 60 if self.active else now
        elapsed = max(0, min(now, self.deadline) - self.last_tick) if self.active else 0
        self.last_tick = now
        if elapsed:
            self.session.seconds += elapsed
            self.data["daily_time_spent"] += elapsed
            self.dirty = True

    def set_active(self, active):
        self.tick()
        if active != self.active:
            self.active = active
            self.last_tick = self.clock()
            self.deadline = self.last_tick + 60 if active else self.last_tick

    def activity(self):
        self.tick()
        self.deadline = self.clock() + 60

    def answer(self, ease, step):
        if ease not in (1, 2, 3, 4):
            return
        self.tick()
        before = {key: self.data[key] for key in COUNTERS}
        session_before = replace(self.session)
        self.session.total += 1
        self.data["daily_reviews"] += 1
        recalled = ease > 1
        milestone = next_milestone(self.session.streak)
        if recalled:
            self.session.correct += 1
            self.session.streak += 1
            self.session.misses = 0
            self.data["daily_correct"] += 1
            for key in ("best_streak", "daily_best_streak"):
                self.data[key] = max(self.data[key], self.session.streak)
        else:
            self.session.streak = 0
            self.session.misses += 1
            for key in ("worst_miss_streak", "daily_worst_miss_streak"):
                self.data[key] = max(self.data[key], self.session.misses)

        goal = self.options["daily_goal"]
        self.celebration = False
        if goal and self.data["daily_reviews"] == goal:
            self.feedback = "Daily goal complete. Nicely done!"
            self.celebration = True
        elif recalled and self.session.streak == milestone:
            self.feedback = f"{milestone} in a row. You're building momentum!"
            self.celebration = True
        elif recalled and self.session.streak > before["best_streak"] and before["best_streak"] >= 5:
            self.feedback = "A new personal best. Keep it going!"
        elif recalled and session_before.misses:
            self.feedback = "Back on track. That's how it sticks."
        elif recalled:
            self.feedback = ("One more word getting stronger.", "Good rep. Keep the rhythm.",
                             "A little more familiar every time.")[self.session.total % 3]
        else:
            self.feedback = "Another rep toward remembering. You've got this."
        self.event_id += 1
        # A new review invalidates the old redo branch, just like Anki.
        self.history = OrderedDict((k, v) for k, v in self.history.items() if v.applied)
        if step is not None:
            self.history[step] = ReviewChange(
                before, {key: self.data[key] for key in COUNTERS}, session_before,
                replace(self.session), self.data["daily_date"], self.generation,
            )
            while len(self.history) > 200:
                self.history.popitem(last=False)
        self.dirty = True

    def replay(self, counter, new_counter):
        """Match a successful native undo/redo by operation ID, not menu clicks."""
        self.tick()
        change = self.history.pop(counter, None)
        if change is None:
            return False
        target = change.before if change.applied else change.after
        for key in COUNTERS:
            if not key.startswith("daily_") or change.day == self.data["daily_date"]:
                self.data[key] = target[key]
        if change.generation == self.generation and change.day == self.data["daily_date"]:
            restored = change.session_before if change.applied else change.session_after
            # Undo ratings, not time actually spent studying.
            self.session = replace(restored, seconds=self.session.seconds)
        self.feedback = "Review undone." if change.applied else "Review restored."
        self.celebration = False
        self.event_id += 1
        change.applied = not change.applied
        self.history[new_counter] = change
        self.dirty = True
        return True
