"""Optional real-backend checks. Set ANKI_PACKAGE_PATH to Anki's app_packages."""

import importlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import support
from gamified_under_test.core import Tracker

ANKI_PATH = os.environ.get('ANKI_PACKAGE_PATH')


@unittest.skipUnless(ANKI_PATH, 'Set ANKI_PACKAGE_PATH for installed-Anki integration checks')
class AnkiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(ANKI_PATH)
        sys.path[:0] = [str(base), str(base / 'win32'), str(base / 'win32/lib'),
                        str(base / 'pywin32_system32')]
        cls.dll_handles = []
        if os.name == 'nt':
            cls.dll_handles = [os.add_dll_directory(str(p)) for p in
                               (base, base / 'pywin32_system32') if p.exists()]
        from anki.lang import set_lang
        from anki.collection import Collection
        from aqt.reviewer import Reviewer
        set_lang('en')
        cls.Collection, cls.Reviewer = Collection, Reviewer
        cls.adapter = importlib.import_module('gamified_under_test.addon')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.col = self.Collection(str(Path(self.directory.name) / 'collection.anki2'))
        self.addCleanup(self.col.close)
        self.reviewer = object.__new__(self.Reviewer)
        self.reviewer.web = SimpleNamespace(eval=MagicMock())
        self.callbacks = []
        self.mw = SimpleNamespace(
            col=self.col, reviewer=self.reviewer, state='review',
            pm=SimpleNamespace(name='Test profile'), isActiveWindow=lambda: True,
            addonManager=MagicMock(),
            taskman=SimpleNamespace(run_on_main=self.callbacks.append),
        )
        self.mw.addonManager.getConfig.return_value = {'sound_mode': 'off', 'best_streak': 54}
        self.mw.addonManager.addonFromModule.return_value = 'AnkiGamified'
        for target, value in [('mw', self.mw), ('QTimer', MagicMock()),
                              ('ROOT', Path(self.directory.name)), ('tooltip', MagicMock())]:
            p = patch.object(self.adapter, target, value)
            p.start()
            self.addCleanup(p.stop)
        self.controller = self.adapter.Gamified('AnkiGamified')
        self.controller.open_profile()

    def answer(self, ease=3):
        from anki.scheduler.v3 import CardAnswer
        queued = self.col.sched.get_queued_cards().cards[0]
        card = self.col.get_card(queued.card.id)
        card.start_timer()
        rating = (CardAnswer.AGAIN, CardAnswer.HARD, CardAnswer.GOOD, CardAnswer.EASY)[ease - 1]
        self.col.sched.answer_card(self.col.sched.build_answer(card=card, states=queued.states, rating=rating))
        self.controller.answer(self.reviewer, card, ease)
        return card

    def add_card(self, text='word'):
        note = self.col.new_note(self.col.models.by_name('Basic'))
        note['Front'], note['Back'] = text, 'meaning'
        self.col.add_note(note, 1)
        return note

    def test_actual_review_unrelated_edit_and_native_undo_redo(self):
        self.add_card()
        self.answer()
        tracker = self.controller.tracker
        self.assertEqual(tracker.data['daily_reviews'], 1)
        self.add_card('unrelated add')
        out = self.col.undo()
        self.assertFalse(tracker.replay(out.counter, out.new_status.last_step))
        self.assertEqual(tracker.data['daily_reviews'], 1)
        for operation, expected in [(self.col.undo, 0), (self.col.redo, 1), (self.col.undo, 0)]:
            out = operation()
            self.assertTrue(tracker.replay(out.counter, out.new_status.last_step))
            self.assertEqual(tracker.data['daily_reviews'], expected)

    def test_previews_and_rendering_do_not_write_config_or_progress(self):
        original = '<div id="vocab">word</div>'
        for kind in ['previewQuestion', 'previewAnswer', 'clayoutQuestion', 'clayoutAnswer']:
            self.assertEqual(self.controller.card_html(original, None, kind), original)
        with patch.object(self.controller.store, 'save') as save:
            for _ in range(100):
                for kind in ['reviewQuestion', 'reviewAnswer']:
                    self.assertTrue(self.controller.card_html(original, None, kind).endswith(original))
            save.assert_not_called()
        self.mw.addonManager.writeConfig.assert_not_called()

    def test_bridge_scoping_and_immediate_session_reset(self):
        self.add_card()
        self.answer()
        handled = (True, 'another addon')
        self.assertEqual(self.controller.message(handled, 'ankigamified:reset', self.reviewer), handled)
        self.assertEqual(self.controller.message((False, None), 'ankigamified:reset', object()), (False, None))
        self.assertEqual(self.controller.tracker.session.total, 1)
        self.controller.message((False, None), 'ankigamified:reset', self.reviewer)
        self.assertEqual(self.controller.tracker.session.total, 0)
        self.assertEqual(self.controller.tracker.data['daily_reviews'], 1)
        self.reviewer.web.eval.assert_called()

    def test_profile_switch_and_pending_callback_isolation(self):
        self.add_card()
        self.answer()
        self.controller.close_profile()
        self.mw.pm.name = 'Other profile'
        self.controller.open_profile()
        self.assertEqual(self.controller.tracker.data['best_streak'], 0)
        self.assertEqual(self.controller.tracker.session.total, 0)
        self.controller.replay(object(), 1, 2)
        self.controller.close_profile()
        self.mw.pm.name = 'Test profile'
        self.controller.open_profile()
        self.assertEqual(self.controller.tracker.data['best_streak'], 54)
        self.assertEqual(self.controller.tracker.data['daily_reviews'], 1)

    def test_completed_operation_wrapper_dispatches_to_main_thread(self):
        # Exercise the real anki.hooks.wrap call and successful backend results.
        undo, redo = self.Collection.undo, self.Collection.redo
        self.addCleanup(setattr, self.Collection, 'undo', undo)
        self.addCleanup(setattr, self.Collection, 'redo', redo)
        with patch.object(self.adapter, 'Gamified', return_value=self.controller), \
                patch.object(self.adapter, 'gui_hooks', MagicMock()):
            self.adapter.setup('AnkiGamified')
        self.add_card()
        self.answer()
        self.col.undo()
        self.assertEqual(self.controller.tracker.session.total, 1)
        self.assertEqual(len(self.callbacks), 1)
        self.callbacks.pop(0)()
        self.assertEqual(self.controller.tracker.session.total, 0)
        self.col.redo()
        self.callbacks.pop(0)()
        self.assertEqual(self.controller.tracker.session.total, 1)
        self.controller.close_profile()
        self.col.undo()
        self.callbacks.pop(0)()
        self.assertIsNone(self.controller.tracker)

    def test_reviewer_assets_loaded_once_outside_card_html(self):
        content = SimpleNamespace(css=[], js=[])
        self.controller.web_content(content, object())
        self.assertEqual(content.css, [])
        self.controller.web_content(content, self.reviewer)
        self.assertEqual(content.css, ['/_addons/AnkiGamified/web/hud.css'])
        self.assertEqual(content.js, ['/_addons/AnkiGamified/web/hud.js'])

    def test_audio_is_preloaded_once_and_uses_cached_tiers(self):
        self.controller.tracker.options['sound_mode'] = 'all'
        with patch.object(self.adapter, 'ROOT', support.ROOT), \
                patch('PyQt6.QtMultimedia.QSoundEffect') as effect:
            effect.side_effect = lambda *args: MagicMock()
            self.controller.prepare_audio()
            self.controller.prepare_audio()
            self.assertEqual(effect.call_count, 4)
        self.controller.tracker.session.streak = 15
        self.controller.play_reward(3)
        player = self.controller.players['ding_10.wav']
        player.play.assert_called_once()
        player.setSource.assert_called_once()
        player.setVolume.assert_called_with(.35)
        self.controller.tracker.options['sound_mode'] = 'milestones'
        self.controller.play_reward(3)
        player.play.assert_called_once()
        del self.controller.players['ding_10.wav']
        self.controller.tracker.celebration = True
        self.controller.play_reward(3)
        self.controller.players['ding.wav'].play.assert_called_once()

    def test_failed_undo_does_not_dispatch_or_change_stats(self):
        from anki.errors import UndoEmpty
        undo, redo = self.Collection.undo, self.Collection.redo
        self.addCleanup(setattr, self.Collection, 'undo', undo)
        self.addCleanup(setattr, self.Collection, 'redo', redo)
        with patch.object(self.adapter, 'Gamified', return_value=self.controller), \
                patch.object(self.adapter, 'gui_hooks', MagicMock()):
            self.adapter.setup('AnkiGamified')
        with self.assertRaises(UndoEmpty):
            self.col.undo()
        self.assertEqual(self.callbacks, [])
        self.assertEqual(self.controller.tracker.session.total, 0)


if __name__ == '__main__':
    unittest.main()
