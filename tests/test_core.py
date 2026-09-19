import unittest
from datetime import date

import support
from gamified_under_test.core import DEFAULTS, Tracker, next_milestone, settings
from gamified_under_test.ui import render, duration


class Clock:
    now = 0
    day = date(2026, 9, 19)

    def advance(self, seconds):
        self.now += seconds


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.t = Tracker(clock=lambda: self.clock.now, today=lambda: self.clock.day)

    def test_ratings_and_recovery(self):
        for step, ease in enumerate((2, 3, 4, 1, 1, 3), 1):
            self.t.answer(ease, step)
        self.assertEqual((self.t.session.total, self.t.session.correct, self.t.session.streak), (6, 4, 1))
        self.assertEqual(self.t.data['best_streak'], 3)
        self.assertEqual(self.t.data['worst_miss_streak'], 2)
        self.assertIn('Back on track', self.t.feedback)

    def test_goal_counts_again(self):
        self.t.options['daily_goal'] = 1
        self.t.answer(1, 1)
        self.assertTrue(self.t.celebration)
        self.assertIn('Daily goal complete', self.t.feedback)
        self.assertIn('aria-valuenow="1"', render(self.t))

    def test_goal_does_not_keep_celebrating(self):
        self.t.options['daily_goal'] = 1
        self.t.answer(3, 1)
        self.t.answer(3, 2)
        self.assertFalse(self.t.celebration)
        self.assertIn('1 extra', render(self.t))

    def test_milestones(self):
        for step in range(1, 106):
            self.t.answer(3, step)
            self.assertEqual(self.t.celebration, step in (5, 10, 20, 30, 50, 75, 100))
        self.assertEqual(next_milestone(105), 150)

    def test_invalid_rating_is_no_op(self):
        self.t.answer(0, 1)
        self.assertEqual(self.t.session.total, 0)

    def test_idle_cap_survives_repeated_timer_ticks(self):
        self.t.set_active(True)
        for _ in range(600):
            self.clock.advance(1)
            self.t.tick()
        self.assertEqual(self.t.session.seconds, 60)
        self.assertEqual(self.t.data['daily_time_spent'], 60)
        self.t.activity()
        self.clock.advance(5)
        self.t.tick()
        self.assertEqual(self.t.session.seconds, 65)

    def test_time_pauses_away_from_reviewer(self):
        self.t.set_active(True)
        self.clock.advance(4)
        self.t.set_active(False)
        self.clock.advance(3600)
        self.t.set_active(True)
        self.clock.advance(3)
        self.t.tick()
        self.assertEqual(self.t.session.seconds, 7)

    def test_preview_or_inactive_time_does_not_count(self):
        self.clock.advance(300)
        self.t.tick()
        self.assertEqual(self.t.session.seconds, 0)

    def test_unrelated_undo_does_not_touch_progress(self):
        self.t.answer(3, 11)
        self.assertFalse(self.t.replay(12, 13))
        self.assertEqual(self.t.session.total, 1)

    def test_undo_redo_and_undo_redone_review(self):
        self.t.answer(3, 1)
        self.t.answer(1, 2)
        self.assertTrue(self.t.replay(2, 3))
        self.assertEqual((self.t.session.total, self.t.session.streak), (1, 1))
        self.assertTrue(self.t.replay(3, 4))
        self.assertEqual((self.t.session.total, self.t.session.streak), (2, 0))
        self.assertTrue(self.t.replay(4, 5))
        self.assertEqual(self.t.data['daily_correct'], 1)
        self.assertEqual(self.t.data['daily_reviews'], 1)

    def test_undo_preserves_time_and_settings(self):
        self.t.set_active(True)
        self.clock.advance(7)
        self.t.answer(3, 1)
        self.clock.advance(4)
        self.t.options['sound_mode'] = 'off'
        self.t.replay(1, 2)
        self.assertEqual(self.t.session.seconds, 11)
        self.assertEqual(self.t.options['sound_mode'], 'off')
        self.assertEqual(self.t.data['best_streak'], 0)

    def test_new_answer_invalidates_redo_branch(self):
        self.t.answer(3, 1)
        self.t.replay(1, 2)
        self.t.answer(4, 3)
        self.assertFalse(self.t.replay(2, 4))
        self.assertEqual(self.t.session.total, 1)

    def test_reset_preserves_daily_and_daily_undo(self):
        self.t.answer(3, 1)
        self.t.reset_session()
        self.assertEqual(self.t.data['daily_reviews'], 1)
        self.t.replay(1, 2)
        self.assertEqual(self.t.session.total, 0)
        self.assertEqual(self.t.data['daily_reviews'], 0)
        self.t.replay(2, 3)
        self.assertEqual(self.t.data['daily_reviews'], 1)
        self.assertEqual(self.t.session.total, 0)

    def test_rollover_does_not_resurrect_yesterday(self):
        self.t.set_active(True)
        self.clock.advance(20)
        self.t.answer(3, 1)
        self.clock.day = date(2026, 9, 20)
        self.clock.advance(3600)
        self.t.tick()
        self.assertEqual(self.t.session.total, 0)
        self.assertEqual(self.t.data['daily_time_spent'], 0)
        self.assertEqual(self.t.data['best_streak'], 1)
        self.t.replay(1, 2)
        self.assertEqual(self.t.data['daily_reviews'], 0)
        self.assertEqual(self.t.data['best_streak'], 0)

    def test_history_is_bounded(self):
        for step in range(1000):
            self.t.answer(3, step)
        self.assertEqual(len(self.t.history), 200)
        self.assertEqual(self.t.data['daily_reviews'], 1000)

    def test_malformed_settings_are_sanitized(self):
        self.assertEqual(settings(None), DEFAULTS)
        opts = settings({'daily_goal': 'oops', 'sound_volume': float('nan'),
                         'sound_mode': [], 'show_details': 'false'})
        self.assertEqual(opts, DEFAULTS)
        self.assertEqual(settings({'daily_goal': -1, 'sound_volume': 4})['daily_goal'], 0)
        self.assertEqual(settings({'sound_volume': 4})['sound_volume'], 1)

    def test_malformed_saved_counters(self):
        t = Tracker({'daily_reviews': '5', 'daily_correct': 100,
                     'daily_time_spent': -20, 'best_streak': None})
        self.assertEqual(t.data['daily_correct'], 5)
        self.assertEqual(t.data['daily_time_spent'], 0)

    def test_render_empty_disabled_goal_and_escaping(self):
        self.t.options['daily_goal'] = 0
        self.t.feedback = '<script>bad()</script>'
        html = render(self.t)
        self.assertNotIn('role="progressbar"', html)
        self.assertNotIn('<script>', html)
        self.assertIn('—', html)
        self.assertEqual(duration(3661), '1:01:01')


if __name__ == '__main__':
    unittest.main()
