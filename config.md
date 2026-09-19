# Anki Gamified

- **daily_goal**: reviews to aim for each day (default `100`). Every rating counts, including Again. Set to `0` to hide the target.
- **sound_mode**: `"all"` plays on each recalled answer, `"milestones"` plays only at streak milestones and goal completion, `"off"` mutes rewards.
- **sound_volume**: `0.0` to `1.0` (default `0.35`). Card pronunciation audio is separate.
- **show_details**: expand session/daily recall, records and the New session button. Also available through **Stats** on the card.
- **animations**: enable the brief milestone glow. Your system's reduced-motion preference is also respected.

Settings apply immediately. **Sound** and **Stats** on the card are quick toggles.

Hard, Good and Easy count as recalled; Again resets the streak but still advances the review goal. Rate honestly: the add-on never changes scheduling.

Progress is saved locally per Anki profile in `user_files/progress.json`. Existing legacy stats are imported into the first profile opened after upgrading. Old counter fields in this editor are retained only for migration; changing them does not change the new progress file.
