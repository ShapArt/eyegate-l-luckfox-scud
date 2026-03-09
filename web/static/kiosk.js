(() => {
  const stateEl = document.getElementById("fsm-state");
  const hintEl = document.getElementById("hint-text");
  const door1Dot = document.getElementById("door1-dot");
  const door2Dot = document.getElementById("door2-dot");
  const cardEl = document.getElementById("card-id");
  const userEl = document.getElementById("user-id");
  const visionEl = document.getElementById("vision-line");
  const pinForm = document.getElementById("pin-form");
  const pinInput = document.getElementById("pin-input");
  const pinMessage = document.getElementById("pin-message");
  eg.setLogElement(pinMessage);

  function doorClass(doors, idx, alarm) {
    if (alarm) return "state-alarm";
    const closed = idx === 1 ? doors?.door1_closed : doors?.door2_closed;
    const unlocked = idx === 1 ? doors?.lock1_unlocked : doors?.lock2_unlocked;
    if (!closed) return "state-open";
    if (unlocked) return "state-unlocked";
    return "state-locked";
  }

  function hintForState(state) {
    switch (state) {
      case "WAIT_ENTER":
        return "Open Door 1, enter, then close it.";
      case "CHECK_ROOM":
        return "Close Door 1. Stand still, camera is checking.";
      case "ACCESS_GRANTED":
        return "Open Door 2 and exit.";
      case "ALARM":
        return "Alarm! Keep both doors closed, reset from admin.";
      case "RESET":
        return "Resetting... wait a second.";
      default:
        return "Enter PIN to start.";
    }
  }

  function updateStatus(data) {
    stateEl.textContent = data.state || "-";
    hintEl.textContent = hintForState(data.state);
    const alarm = data.state === "ALARM";
    const doors = data.doors || {};
    door1Dot.className = `dot ${doorClass(doors, 1, alarm)}`;
    door2Dot.className = `dot ${doorClass(doors, 2, alarm)}`;
    cardEl.textContent = data.current_card_id || "-";
    userEl.textContent = data.current_user_id || "-";
    if (data.vision) {
      visionEl.textContent = `Vision: ${data.vision.stale ? "stale" : "fresh"} / people=${data.vision.people_count ?? "-"} / match=${data.vision.match ?? "-"}`;
    }
  }

  async function loadInitial() {
    try {
      const st = await eg.api("/api/status/");
      updateStatus(st);
      eg.toast("Статус обновлён", "info");
    } catch (err) {
      eg.toast(err.message || "Ошибка статуса", "error");
    }
  }

  function setupWS() {
    eg.connectStatus(updateStatus);
  }

  pinForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    eg.toast("");
    const pin = pinInput.value.trim();
    if (!pin) return;
    try {
      await eg.api("/api/auth/pin", {
        method: "POST",
        body: { pin },
      });
      eg.toast("PIN отправлен. Следите за дверями.", "ok");
      pinInput.value = "";
      await loadInitial();
    } catch (err) {
      eg.toast(err.message, "error");
    }
  });

  loadInitial();
  setupWS();
})();
