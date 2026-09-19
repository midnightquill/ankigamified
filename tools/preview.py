"""Render and exercise the HUD in Qt WebEngine without opening a real profile.

Usage: python tools/preview.py --output <directory>
Set ANKI_PACKAGE_PATH to the installed Anki app_packages if PyQt6 isn't on PATH.
"""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import types

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
if os.environ.get('ANKI_PACKAGE_PATH'):
    sys.path.insert(0, os.environ['ANKI_PACKAGE_PATH'])
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --no-sandbox')

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

root = Path(__file__).resolve().parents[1]
package = types.ModuleType('gamified_preview')
package.__path__ = [str(root)]
sys.modules[package.__name__] = package
Tracker = importlib.import_module('gamified_preview.core').Tracker
render = importlib.import_module('gamified_preview.ui').render
css = (root / 'web/hud.css').read_text(encoding='utf-8')
script = (root / 'web/hud.js').read_text(encoding='utf-8')
app = QApplication(['anki-gamified-preview'])
errors = []


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == self.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            errors.append(message)


view = QWebEngineView()
view.setPage(Page(view))


def wait(milliseconds=150):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def evaluate(script):
    loop = QEventLoop()
    result = []
    def done(value):
        result.append(value)
        loop.quit()
    view.page().runJavaScript(script, done)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    if not result:
        raise RuntimeError('JavaScript evaluation timed out')
    return result[0]


report = []
for name, dark, width, details, reviews in [
    ('dark', True, 900, False, 67),
    ('light', False, 900, True, 67),
    ('narrow', True, 360, True, 67),
    ('goal', True, 900, False, 100),
]:
    tracker = Tracker(options={'show_details': details})
    tracker.data.update(daily_reviews=reviews-10, daily_correct=reviews-15,
                        best_streak=54, daily_best_streak=27, daily_time_spent=1425)
    tracker.session.seconds = 347
    for step in range(10):
        tracker.answer(3, step)
    background, ink = ('#1b1d27', '#edeefa') if dark else ('#f4f5f9', '#253047')
    html = f'''<!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>html,body{{margin:0;min-height:100%;background:{background};color:{ink}}}
    body{{padding:28px 22px;font-family:"Segoe UI",sans-serif;box-sizing:border-box}}
    .card{{text-align:center;font-size:22px}} .demo-label{{text-align:center;font-size:10px;
    letter-spacing:2px;opacity:.5;margin-bottom:23px}} .word{{font-size:54px;margin:48px 0 8px}}
    .reading{{font-size:17px;opacity:.55}} .meaning{{font-size:20px;margin-top:30px}}
    .demo-footer{{font-size:11px;opacity:.45;margin-top:64px}}
    @media(max-width:420px){{body{{padding:18px 12px}} .word{{font-size:42px;margin-top:35px}}}}
    {css}</style></head><body class="card {'nightMode' if dark else ''}">
    <div class="demo-label">ANKI GAMIFIED · REVIEW PREVIEW</div>
    {render(tracker)}<div class="word">続ける</div><div class="reading">つづける</div>
    <div class="meaning">to continue</div><div class="demo-footer">One word at a time.</div>
    <script>window.commands=[];window.pycmd=(command)=>commands.push(command);{script}
    AnkiGamified.mount();</script></body></html>'''
    (args.output / f'{name}.html').write_text(html, encoding='utf-8')
    view.resize(width, 660 if width < 420 else 610)
    loaded = QEventLoop()
    view.loadFinished.connect(loaded.quit)
    view.setHtml(html)
    view.show()
    QTimer.singleShot(10000, loaded.quit)
    loaded.exec()
    view.loadFinished.disconnect(loaded.quit)
    wait(800)
    measurements = json.loads(evaluate('''JSON.stringify({
      overflow: document.documentElement.scrollWidth > window.innerWidth,
      hud: document.querySelectorAll('#ag-hud').length,
      width: document.getElementById('ag-hud').getBoundingClientRect().width,
      height: document.getElementById('ag-hud').getBoundingClientRect().height,
      details: !document.getElementById('ag-details').hidden,
      progress: document.querySelector('[role=progressbar]').getAttribute('aria-valuenow')
    })'''))
    assert not measurements['overflow'], measurements
    assert measurements['hud'] == 1
    assert measurements['details'] == details
    assert int(measurements['progress']) == reviews
    assert view.grab().save(str(args.output / f'{name}.png'))

    # The controls route once even after the root is replaced repeatedly.
    evaluate(f"AnkiGamified.replace({json.dumps(render(tracker))});")
    evaluate(f"AnkiGamified.replace({json.dumps(render(tracker))});")
    evaluate("document.querySelector('[data-ag-action=sound]').click();")
    assert evaluate('commands.join()') == 'ankigamified:sound'
    evaluate("document.getElementById('ag-details').hidden=false;")
    evaluate("document.querySelector('[data-ag-action=reset]').click();")
    assert evaluate('commands.length') == 1
    # A newly rendered card must never inherit an armed reset confirmation.
    evaluate(f"AnkiGamified.replace({json.dumps(render(tracker))});")
    evaluate("document.getElementById('ag-details').hidden=false;")
    evaluate("document.querySelector('[data-ag-action=reset]').click();")
    assert evaluate('commands.length') == 1
    evaluate("document.querySelector('[data-ag-action=reset]').click();")
    assert evaluate('commands.join()') == 'ankigamified:sound,ankigamified:reset'
    evaluate("AnkiGamified.time('07:03','1:02:03')")
    assert evaluate("document.getElementById('ag-session-time').textContent") == '07:03'
    report.append({'layout': name, **measurements, 'controls': 'passed'})

assert not errors, errors
(args.output / 'qa.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
view.close()
