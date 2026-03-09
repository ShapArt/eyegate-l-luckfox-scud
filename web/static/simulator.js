(() => {
  const d1Dot = document.getElementById("d1-dot");
  const d2Dot = document.getElementById("d2-dot");
  const d1Label = document.getElementById("d1-label");
  const d2Label = document.getElementById("d2-label");
  const overrideCount = document.getElementById("override-count");
  const overrideMatch = document.getElementById("override-match");
  const overrideNote = document.getElementById("override-note");
  eg.setLogElement(overrideNote);

  function doorClass(doors, idx, alarm) {
    if (alarm) return "dot state-alarm";
    const closed = idx === 1 ? doors?.door1_closed : doors?.door2_closed;
    const unlocked = idx === 1 ? doors?.lock1_unlocked : doors?.lock2_unlocked;
    if (!closed) return "dot state-open";
    if (unlocked) return "dot state-unlocked";
    return "dot state-locked";
  }

  function doorText(doors, idx) {
    const closed = idx === 1 ? doors?.door1_closed : doors?.door2_closed;
    const unlocked = idx === 1 ? doors?.lock1_unlocked : doors?.lock2_unlocked;
    if (!closed) return "open";
    if (unlocked) return "unlocked";
    return "locked";
  }

  async function refresh() {
    try {
      const st = await eg.api("/api/status/");
      const doors = st.doors || {};
      const alarm = st.state === "ALARM";
      d1Dot.className = doorClass(doors, 1, alarm);
      d2Dot.className = doorClass(doors, 2, alarm);
      d1Label.textContent = doorText(doors, 1);
      d2Label.textContent = doorText(doors, 2);
      if (st.vision?.provider === "VisionServiceDummyControl") {
        overrideNote.textContent = "Dummy vision active, overrides will be applied.";
        overrideCount.disabled = false;
        overrideMatch.disabled = false;
      } else {
        overrideNote.textContent = "Overrides are available only when dummy vision is active.";
        overrideCount.disabled = true;
        overrideMatch.disabled = true;
      }
      eg.toast("Статус обновлён", "info");
    } catch (err) {
      eg.toast(err.message, "error");
    }
  }

  async function toggleDoor(door, action) {
    try {
      await eg.api(`/api/sim/door/${door}/${action}`, { method: "POST" });
      await refresh();
    } catch (err) {
      console.error(err);
    }
  }

  document.querySelectorAll("[data-door]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const door = btn.dataset.door;
      const action = btn.dataset.action;
      toggleDoor(door, action);
    });
  });

  document.getElementById("refresh-btn")?.addEventListener("click", refresh);

  document.getElementById("send-override")?.addEventListener("click", async () => {
    const peopleCount = Number(overrideCount.value || 0);
    const matchVal = overrideMatch.value;
    const face_match =
      matchVal === "match" ? "MATCH" : matchVal === "nomatch" ? "NO_MATCH" : null;
    try {
      await eg.api("/api/vision_dummy", {
        method: "POST",
        body: {
          people_count: peopleCount,
          face_match,
          delay_ms: 0,
        },
      });
      eg.toast("Override отправлен", "ok");
    } catch (err) {
      eg.toast(err.message, "error");
    }
  });

  eg.connectStatus(refresh);
  refresh();
})();
