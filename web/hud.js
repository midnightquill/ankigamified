(() => {
  if (window.AnkiGamified) return;
  let lastEvent = null;
  let resetDeadline = 0;
  let resetButton = null;
  function mount() {
    const root = document.getElementById("ag-hud");
    if (!root) return;
    if (resetButton && !resetButton.isConnected) {
      resetButton = null;
      resetDeadline = 0;
    }
    if (root.dataset.event !== lastEvent) {
      lastEvent = root.dataset.event;
      if (root.dataset.celebrate === "true" && root.dataset.motion === "true") {
        root.classList.add("ag-celebrate");
      }
    }
  }
  window.AnkiGamified = {
    mount,
    replace(html) {
      const root = document.getElementById("ag-hud");
      if (root) { root.outerHTML = html; mount(); }
    },
    time(session, daily) {
      const s = document.getElementById("ag-session-time");
      const d = document.getElementById("ag-day-time");
      if (s && s.textContent !== session) s.textContent = session;
      if (d && d.textContent !== daily) d.textContent = daily;
    }
  };
  // Delegation survives question/answer replacement without accumulating listeners.
  document.addEventListener("click", (event) => {
    const button = event.target.closest("#ag-hud button[data-ag-action]");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    const action = button.dataset.agAction;
    if (action === "reset" && (button !== resetButton || performance.now() > resetDeadline)) {
      resetDeadline = performance.now() + 3500;
      resetButton = button;
      button.textContent = "Confirm reset";
      setTimeout(() => { if (button.isConnected) button.textContent = "New session"; }, 3500);
      return;
    }
    resetDeadline = 0;
    resetButton = null;
    if (typeof pycmd === "function") pycmd(`ankigamified:${action}`);
    button.blur();
  });
})();
