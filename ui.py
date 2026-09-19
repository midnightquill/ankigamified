"""Small, scoped reviewer HUD. All interpolated strings are escaped."""

from html import escape

from .core import next_milestone


def duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def percent(correct, total):
    return f"{round(100 * correct / total)}%" if total else "—"


def render(tracker):
    s, d, options = tracker.session, tracker.data, tracker.options
    goal = options["daily_goal"]
    total = d["daily_reviews"]
    reached = goal > 0 and total >= goal
    goal_number = f'<span class="ag-target"> / {goal:,}</span>' if goal else ""
    goal_caption = "goal complete" if reached else "reviews today"
    goal_caption += f" · {total - goal:,} extra" if reached and total > goal else ""
    goal_progress = ""
    if goal:
        fill = min(100, total * 100 / goal)
        goal_progress = (f'<div class="ag-track" role="progressbar" aria-label="Daily review goal" '
                         f'aria-valuemin="0" aria-valuemax="{goal}" aria-valuenow="{min(total, goal)}">'
                         f'<div class="ag-fill" style="width:{fill:.2f}%"></div></div>')
    milestone = next_milestone(s.streak)
    sound_on = options["sound_mode"] != "off"
    details = "" if options["show_details"] else " hidden"
    motion = "true" if options["animations"] else "false"
    celebrate = "true" if tracker.celebration else "false"
    return f"""<section id="ag-hud" aria-label="Anki Gamified progress" dir="ltr"
        data-event="{tracker.event_id}" data-celebrate="{celebrate}" data-motion="{motion}"
        class="{'ag-complete' if reached else ''}">
      <div class="ag-top">
        <span class="ag-brand"><span class="ag-spark" aria-hidden="true">✦</span> VOCAB QUEST</span>
        <div class="ag-actions">
          <button type="button" data-ag-action="sound" aria-label="{'Mute' if sound_on else 'Enable'} reward sounds"
            aria-pressed="{str(sound_on).lower()}" title="Toggle reward sounds">{'♫ Sound' if sound_on else '♪ Muted'}</button>
          <button type="button" data-ag-action="details" aria-expanded="{str(options['show_details']).lower()}"
            aria-controls="ag-details">Stats</button>
        </div>
      </div>
      <div class="ag-main">
        <div class="ag-goal"><div class="ag-count">{total:,}{goal_number}</div>
          <div class="ag-label">{goal_caption}</div></div>
        <div class="ag-streak"><span class="ag-flame" aria-hidden="true">🔥</span>
          <span><strong>{s.streak}</strong> <span class="ag-label">in a row</span>
          <span class="ag-next">Next milestone · {milestone}</span></span></div>
      </div>
      {goal_progress}
      <div class="ag-bottom"><span id="ag-feedback">{escape(tracker.feedback)}</span>
        <span class="ag-session" title="Reviews this session and active study time">
          {s.total:,} reps <span aria-hidden="true">·</span> <span id="ag-session-time">{duration(s.seconds)}</span>
        </span></div>
      <div id="ag-details"{details}>
        <div class="ag-metrics">
          <div><span>Session recall</span><strong title="Hard, Good and Easy count as recalled">{percent(s.correct, s.total)}</strong></div>
          <div><span>Today recall</span><strong>{percent(d['daily_correct'], total)}</strong></div>
          <div><span>Today's best</span><strong>{d['daily_best_streak']:,}</strong></div>
          <div><span>Personal best</span><strong>{d['best_streak']:,}</strong></div>
        </div>
        <div class="ag-detail-footer"><span>Active today <span id="ag-day-time">{duration(d['daily_time_spent'])}</span></span>
          <button type="button" data-ag-action="reset" title="Reset only this session; today's progress is kept">New session</button>
        </div>
      </div>
    </section>"""
