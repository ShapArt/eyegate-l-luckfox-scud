(() => {
  const img = document.getElementById("video");
  const overlay = document.getElementById("overlay");
  const btnReload = document.getElementById("btn-reload");
  const hint = document.getElementById("camera-hint");
  const peopleEl = document.getElementById("people-count");
  const matchEl = document.getElementById("match-status");
  const distanceEl = document.getElementById("match-distance");
  const tsEl = document.getElementById("last-ts");
  const wsStatusEl = document.getElementById("ws-status");
  eg.setLogElement(hint);

  let ws;
  let retryDelay = 1000;
  let retryTimer = null;

  function nextDelay(current) {
    if (current === 1000) return 2000;
    return 5000;
  }

  function setStreamSource() {
    if (!img) return;
    const url = new URL("/api/video/mjpeg", window.location.origin);
    url.searchParams.set("_", Date.now().toString());
    img.src = url.toString();
  }

  function drawOverlay(vision) {
    if (!overlay || !img || !vision) return;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    const displayW = img.clientWidth || img.naturalWidth || 1;
    const displayH = img.clientHeight || img.naturalHeight || 1;
    overlay.width = displayW;
    overlay.height = displayH;
    ctx.clearRect(0, 0, displayW, displayH);
    if (!vision.boxes || !vision.boxes.length) return;

    const faces = Array.isArray(vision.faces) && vision.faces.length
      ? vision.faces
      : vision.boxes.map((box, idx) => ({
          box,
          user_id: vision.recognized_user_ids?.[idx] ?? null,
          score: vision.recognized_scores?.[idx] ?? null,
          label: null,
          is_known: null,
        }));

    const frameW = vision.frame_w || img.naturalWidth || displayW;
    const frameH = vision.frame_h || img.naturalHeight || displayH;

    faces.forEach((face) => {
      const box = face.box;
      if (!box) return;
      const x = (box.x / frameW) * displayW;
      const y = (box.y / frameH) * displayH;
      const w = (box.w / frameW) * displayW;
      const h = (box.h / frameH) * displayH;
      const label = face.label || (face.user_id != null ? `ID ${face.user_id}` : "Shapovalov");
      const known = face.is_known === true || label !== "Shapovalov";
      const tone = known ? "#22c55e" : "#22c55e";
      ctx.strokeStyle = tone;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);
      const text = `${label}${face.score != null ? ` (${face.score.toFixed(2)})` : ""}`;
      const pad = 6;
      const textW = ctx.measureText(text).width + pad * 2;
      const textH = 18;
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(x, Math.max(0, y - textH), textW, textH);
      ctx.fillStyle = tone;
      ctx.font = "12px sans-serif";
      ctx.fillText(text, x + pad, y - 6);
    });
  }

  function updateStatus(data) {
    if (!data || !data.vision) return;
    const vision = data.vision;
    peopleEl.textContent = vision.people_count ?? "-";
    matchEl.textContent = vision.match ?? "-";
    distanceEl.textContent = vision.match_distance ?? "-";
    tsEl.textContent = vision.last_frame_ts ? new Date(vision.last_frame_ts * 1000).toISOString() : "-";
    if (vision.camera_ok === false) {
      hint.textContent = "CAMERA DOWN";
    }
    drawOverlay(vision);
  }

  function connectWS() {
    ws = eg.connectStatus((data) => {
      wsStatusEl.textContent = "connected";
      updateStatus(data);
    });
    ws.onclose = () => {
      wsStatusEl.textContent = "disconnected";
      setTimeout(connectWS, 2000);
    };
  }

  if (img) {
    img.onload = () => {
      retryDelay = 1000;
      if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      hint.textContent = "Stream active (backend MJPEG)";
      drawOverlay(null);
    };
    img.onerror = () => {
      hint.textContent = "STREAM DISCONNECTED";
      if (!retryTimer) {
        retryTimer = setTimeout(() => {
          retryTimer = null;
          retryDelay = nextDelay(retryDelay);
          setStreamSource();
        }, retryDelay);
      }
    };
    setStreamSource();
  }

  btnReload?.addEventListener("click", () => {
    retryDelay = 1000;
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    setStreamSource();
  });

  connectWS();
})();
