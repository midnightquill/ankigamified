# Anki Gamified

A small vocabulary-review companion: a daily quest, satisfying streaks, gentle encouragement, and reward sounds that play alongside card audio. Your ratings and Anki's scheduler work normally.

## What's new

- A compact, responsive review panel with light/dark themes. The card stays the focus; **Stats** expands the details.
- A configurable daily review goal (100 by default). Every completed review counts, including **Again**.
- Streak milestones at 5, 10, 20, 30, 50, 75, 100, and every 50 afterward. Brief celebrations respect reduced-motion preferences.
- Encouraging recovery messages, personal records, active study time, and a session summary when you leave the reviewer.
- Preloaded sound effects, adjustable volume, a one-click mute, and an optional milestones-only mode.
- Native undo **and redo** tracking tied to successful review operations. Undoing an unrelated edit leaves review stats alone.
- Progress stored separately for each profile, with automatic migration of legacy records.

## Use

Restart Anki after installing or updating the add-on, then review normally.

- **Sound / Muted** toggles reward audio.
- **Stats** shows session/daily recall, today's best streak, your personal best, and active time.
- **New session**, inside Stats, resets only the session. Click again to confirm within 3.5 seconds. Daily totals and records stay intact.
- **Tools → Add-ons → AnkiGamified → Config** changes the goal, sound volume/mode, details, and animations. Changes apply immediately. See [configuration help](config.md).

Hard, Good, and Easy count as recalled, matching the previous add-on. Again resets the streak but advances the daily review goal. These are rating-based stats, not a separate measure of vocabulary mastery.

## Progress and timing

Daily counters reset on the next update after local midnight. Sessions survive deck changes, and reset when you restart/switch profiles, start a new session, or cross midnight. This add-on uses the local calendar day, independently of Anki's configurable scheduler day boundary.

Active time uses a monotonic clock. It pauses when the main review window loses focus (checked once a second), and stops accumulating after 60 seconds without showing a new question or revealing an answer. Browsing and template previews do not advance progress. Undo restores ratings, streaks, and records; actual time spent studying remains counted.

Progress is saved locally in `user_files/progress.json`, keyed by profile name. It is written at most every 15 seconds during reviews, plus when leaving review, closing a profile, or undoing/redoing a review. Saves use atomic replacement. An abrupt crash can lose the most recent unsaved interval. Back up this file with your profile; it does not sync through AnkiWeb. A renamed profile uses a new progress entry.

On the first launch after upgrading, the first profile opened inherits the old combined counters (including the existing best streak). Later profiles begin with their own counters. Legacy values in `meta.json` remain untouched as a migration fallback. The old daily date is respected, so an old day's totals do not become today's totals.

Undo/redo history is kept in memory for up to 200 review operations in the open collection. Starting a new session preserves the ability to undo its earlier daily totals. Collection reloads and restarts clear this in-memory history, as they clear Anki's native undo history.

## Installation and audio

Place this folder in Anki's `addons21` directory and restart Anki. Keep `__init__.py`, the other Python modules, and `web/` together.

The bundled WAV files provide the reward tiers:

| File | Streak |
| --- | --- |
| `ding.wav` | Below 10 |
| `ding_10.wav` | 10–19 |
| `ding_20.wav` | 20–29 |
| `ding_30.wav` | 30+ |

Missing tier files fall back to `ding.wav`. Missing audio support does not disable review tracking. The original MP3 is retained but is not used by the player. Reward sounds use Qt's separate audio player and do not replace Anki's pronunciation playback.

## Implementation and checks

Targets modern Qt6 Anki; verified against the installed **Anki 26.09.2** backend and Qt WebEngine. No new third-party runtime dependencies.

- `core.py`: ratings, timing, milestones, and operation-specific undo history.
- `storage.py`: per-profile progress and atomic persistence.
- `addon.py`: Anki lifecycle hooks, cached audio, and scoped web messages.
- `ui.py`, `web/`: escaped markup and reviewer-only styles/scripts.

Run the standalone regression tests:

```powershell
python -m unittest discover -s tests -v
```

Include the real installed Anki backend tests by setting its package directory:

```powershell
$env:ANKI_PACKAGE_PATH = 'C:\path\to\Anki\app_packages'
python -m unittest discover -s tests -v
python tools/preview.py --output "$env:TEMP\anki-gamified-preview"
```

The integration tests create disposable collections, never open your study collection, and check rating/undo/redo behavior, profile isolation, bridge handling, and rendering without per-card saves. The preview tool renders light, dark, narrow, and goal-complete layouts in Qt WebEngine, saves screenshots, and checks for overflow, duplicate controls, reset confirmation, and timer updates.

The upgrade removes repeated config reads/writes from card rendering, deep copies of the entire config on each review, per-answer audio file checks/source reloads, and the unsafe Undo-menu signal handler. CSS and JavaScript load once per review webview; timer updates change only their text nodes and stop sending updates when idle.

## License

MIT, as declared by the original project.
