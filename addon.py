"""Anki/Qt lifecycle, cached audio and a small reviewer-only web bridge."""

import json
import logging
from pathlib import Path

from anki.collection import Collection
from anki.hooks import wrap
from aqt import gui_hooks, mw
from aqt.qt import QTimer, QUrl
from aqt.reviewer import Reviewer
from aqt.utils import tooltip

from .core import Tracker, settings
from .storage import ProgressStore
from .ui import duration, percent, render

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).parent


class Gamified:
    def __init__(self, module):
        self.module = module
        self.tracker = None
        self.store = None
        self.profile = None
        self.collection = None
        self.players = {}
        self.sound_before_mute = "all"
        self.storage_warning_shown = False
        self.timer = QTimer(mw)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.pulse)
        self.save_timer = QTimer(mw)
        self.save_timer.setInterval(15000)
        self.save_timer.timeout.connect(self.flush)

    def open_profile(self):
        self.profile = mw.pm.name
        self.collection = mw.col
        self.storage_warning_shown = False
        config = mw.addonManager.getConfig(self.module) or {}
        try:
            self.store = ProgressStore(ROOT / "user_files" / "progress.json")
            saved = self.store.load_profile(self.profile, config)
        except (OSError, ValueError) as exc:
            self.store = None
            saved = config
            self.storage_warning(exc)
        self.tracker = Tracker(saved, config)
        self.tracker.dirty = True
        self.prepare_audio()
        self.flush()
        self.save_timer.start()

    def close_profile(self):
        self.timer.stop()
        self.save_timer.stop()
        if self.tracker:
            self.tracker.set_active(False)
            self.flush()
        self.tracker = None
        self.collection = None
        self.stop_audio()

    def storage_warning(self, exc):
        LOG.warning("Anki Gamified progress could not be saved/loaded: %s", exc)
        if not self.storage_warning_shown:
            self.storage_warning_shown = True
            tooltip("Anki Gamified couldn't save/load progress. Existing data is preserved. "
                    "Check user_files/progress.json and folder permissions.", period=7000)

    def flush(self):
        if not self.tracker or not self.tracker.dirty or not self.store:
            return
        try:
            self.store.save(self.profile, self.tracker.data)
            self.tracker.dirty = False
        except (OSError, ValueError) as exc:
            self.storage_warning(exc)

    def prepare_audio(self):
        if self.players or not self.tracker or self.tracker.options["sound_mode"] == "off":
            return
        try:
            from PyQt6.QtMultimedia import QSoundEffect
            for name in ("ding.wav", "ding_10.wav", "ding_20.wav", "ding_30.wav"):
                path = ROOT / name
                if path.is_file():
                    player = QSoundEffect(mw)
                    player.setSource(QUrl.fromLocalFile(str(path)))
                    self.players[name] = player
        except (ImportError, RuntimeError):
            LOG.warning("Anki Gamified reward audio is unavailable", exc_info=True)

    def stop_audio(self):
        for player in self.players.values():
            player.stop()

    def play_reward(self, ease):
        t = self.tracker
        if t.options["sound_mode"] == "off" or (ease == 1 and not t.celebration):
            return
        if t.options["sound_mode"] == "milestones" and not t.celebration:
            return
        streak = t.session.streak
        name = ("ding_30.wav" if streak >= 30 else "ding_20.wav" if streak >= 20
                else "ding_10.wav" if streak >= 10 else "ding.wav")
        player = self.players.get(name) or self.players.get("ding.wav")
        if player:
            self.stop_audio()
            player.setVolume(t.options["sound_volume"])
            player.play()

    def state_change(self, state, old_state):
        if not self.tracker:
            return
        if state == "review":
            self.tracker.set_active(mw.isActiveWindow())
            self.timer.start()
        elif old_state == "review":
            self.tracker.set_active(False)
            self.timer.stop()
            self.flush()
            s = self.tracker.session
            if s.total:
                message = (f"Session: {s.total:,} reviews · {percent(s.correct, s.total)} recalled "
                           f"· {duration(s.seconds)} active")
                if self.tracker.celebration:
                    message = self.tracker.feedback + "<br>" + message
                tooltip(message, period=4000)

    def pulse(self):
        if not self.tracker or mw.state != "review":
            return
        event = self.tracker.event_id
        before = (int(self.tracker.session.seconds), int(self.tracker.data["daily_time_spent"]))
        self.tracker.set_active(mw.isActiveWindow())
        if self.tracker.event_id != event:
            self.refresh()
        elif before != (int(self.tracker.session.seconds), int(self.tracker.data["daily_time_spent"])):
            self.evaluate("time", duration(self.tracker.session.seconds),
                          duration(self.tracker.data["daily_time_spent"]))

    def evaluate(self, method, *args):
        if mw.state == "review":
            values = ",".join(json.dumps(arg) for arg in args)
            mw.reviewer.web.eval(f"window.AnkiGamified && window.AnkiGamified.{method}({values});")

    def refresh(self):
        if self.tracker:
            self.evaluate("replace", render(self.tracker))

    def web_content(self, content, context):
        if isinstance(context, Reviewer):
            package = mw.addonManager.addonFromModule(self.module)
            base = f"/_addons/{package}/web"
            content.css.append(f"{base}/hud.css")
            content.js.append(f"{base}/hud.js")

    def card_html(self, text, card, kind):
        if kind not in ("reviewQuestion", "reviewAnswer") or not self.tracker or mw.state != "review":
            return text
        if mw.col is not self.collection:
            # A full sync can reopen the collection without reopening the profile.
            self.collection = mw.col
            self.tracker.history.clear()
        self.tracker.set_active(mw.isActiveWindow())
        self.tracker.activity()
        return render(self.tracker) + text

    def shown(self, card):
        # Card rendering is asynchronous (including MathJax). Queue behind it.
        if mw.state == "review":
            mw.reviewer.web.eval(
                "_queueAction(() => { window.AnkiGamified && window.AnkiGamified.mount(); });"
            )

    def answer(self, reviewer, card, ease):
        if not self.tracker or mw.col is not self.collection:
            return
        self.tracker.answer(ease, mw.col.undo_status().last_step)
        self.play_reward(ease)

    def replay(self, collection, counter, new_counter):
        if self.tracker and collection is self.collection:
            if self.tracker.replay(counter, new_counter):
                self.stop_audio()
                self.refresh()
                self.flush()

    def config_updated(self, config):
        if self.tracker:
            self.tracker.options = settings(config)
            self.stop_audio()
            self.prepare_audio()
            self.refresh()

    def message(self, handled, message, context):
        if (handled[0] or not isinstance(context, Reviewer) or context is not mw.reviewer
                or not self.tracker or mw.state != "review"):
            return handled
        action = message.removeprefix("ankigamified:") if message.startswith("ankigamified:") else None
        if action not in ("sound", "details", "reset"):
            return handled
        if action == "reset":
            self.tracker.tick()
            self.tracker.reset_session()
            self.tracker.activity()
        else:
            config = mw.addonManager.getConfig(self.module) or {}
            if action == "details":
                config["show_details"] = not self.tracker.options["show_details"]
            else:
                current = self.tracker.options["sound_mode"]
                if current == "off":
                    config["sound_mode"] = self.sound_before_mute
                else:
                    self.sound_before_mute = current
                    config["sound_mode"] = "off"
            mw.addonManager.writeConfig(self.module, config)
            self.config_updated(config)
        if action == "reset":
            self.refresh()
        return (True, None)


def setup(module):
    controller = Gamified(module)
    mw.addonManager.setWebExports(module, r"web/.*\.(css|js)")
    mw.addonManager.setConfigUpdatedAction(module, controller.config_updated)
    gui_hooks.profile_did_open.append(controller.open_profile)
    gui_hooks.profile_will_close.append(controller.close_profile)
    gui_hooks.state_did_change.append(controller.state_change)
    gui_hooks.webview_will_set_content.append(controller.web_content)
    gui_hooks.card_will_show.append(controller.card_html)
    gui_hooks.reviewer_did_show_question.append(controller.shown)
    gui_hooks.reviewer_did_show_answer.append(controller.shown)
    gui_hooks.reviewer_did_answer_card.append(controller.answer)
    gui_hooks.webview_did_receive_js_message.append(controller.message)

    def after_replay(collection, _old):
        # Runs in Anki's worker. Never touch Qt or mutable tracker state here.
        result = _old(collection)
        counter, new_counter = result.counter, result.new_status.last_step
        mw.taskman.run_on_main(lambda: controller.replay(collection, counter, new_counter))
        return result

    # There is no GUI redo-completed hook. Wrap successful backend operations so
    # keyboard/menu undo, redo, unrelated edits and failed operations all agree.
    Collection.undo = wrap(Collection.undo, after_replay, "around")
    Collection.redo = wrap(Collection.redo, after_replay, "around")
