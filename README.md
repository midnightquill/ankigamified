# 🎮 Anki Gamified 

Transform your Anki review sessions from a chore into a highly addictive arcade experience! 

Whether you're grinding through thousands of hours of Japanese flashcards or prepping for an exam, this add-on injects real-time gamification directly into your Anki dashboard. It seamlessly tracks your daily progress, monitors your streaks, and provides satisfying audio feedback without interrupting your card's native audio.

## ✨ Features

* **🔥 Live Streak Tracking:** Watch your streak climb as you answer correctly. Hit a bad streak? The UI dynamically shifts to a red 💔 Misses counter to keep you honest.
* **⏱️ Precision Timers:** Tracks both your current session time and your total daily study time. Includes an idle-cap of 60 seconds per card so your daily stats stay perfectly accurate even if you step away.
* **📅 Daily & All-Time Stats:** Automatically rolls over at exactly midnight your local time. Tracks:
  * Total daily reviews
  * Daily accuracy percentage
  * Daily best/worst streaks
  * All-time best/worst streaks
* **🔊 Milestone Audio Engine:** Built on PyQt6's low-latency `QSoundEffect` engine. This means your "ding!" plays simultaneously *with* your flashcard's native pronunciation audio without colliding or cutting out. 
  * Features dynamic audio milestones that play unique sounds when you hit streaks of 10, 20, and 30!
* **🎨 Seamless Theming:** Uses Anki's native CSS variables to perfectly blend with your custom Anki setup, supporting both Light and Dark modes automatically.
* **↩️ Full Undo Support:** Accidentally pressed the wrong button? The add-on fully supports Anki's native Undo function (`Ctrl+Z` / `Ctrl+Y`), rolling back your timers, scores, and streaks flawlessly.
* **🔄 Quick Clear:** A dedicated, unintrusive UI button to instantly wipe your current session stats and start fresh without losing your daily totals.

---

## 🚀 Installation & Setup

1. Open Anki and navigate to **Tools** > **Add-ons**.
2. Click **View Files** in the bottom right corner to open your local Anki `addons21` directory.
3. Create a new folder named `AnkiGamified` (or clone this repository directly into the `addons21` folder).
4. Ensure `__init__.py` is inside the folder.
5. **Restart Anki.**

### 🎵 Adding the Audio Files

For the zero-latency audio engine to work, **you must use `.wav` files** (not `.mp3`). 

Drop your sound effects directly into the `AnkiGamified` folder. *(Pro tip: Make sure the volume isn't so loud that it wakes up Fuji and Waffles while you're grinding reviews!)*

* `ding.wav` *(Required: Your standard correct answer sound)*
* `ding_10.wav` *(Optional: Plays at a streak of 10+)*
* `ding_20.wav` *(Optional: Plays at a streak of 20+)*
* `ding_30.wav` *(Optional: Plays at a streak of 30+)*

*Note: If the code crosses a milestone but cannot find the specific file (e.g., `ding_20.wav`), it will safely fall back to your standard `ding.wav`.*

---

## 💻 Tech Stack & Compatibility

* **Anki Version:** 25.0+ (Requires Qt6 / PyQt6)
* **Language:** Python 3
* **Audio:** `PyQt6.QtMultimedia.QSoundEffect`
* **UI Integration:** Injects via `gui_hooks.card_will_show` using native HTML/CSS.

## 📝 License

MIT License - Feel free to fork, modify, and improve!
