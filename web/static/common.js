(() => {
  const eg = {
    logEl: null,
    setLogElement(el) {
      eg.logEl = el;
    },
    toast(msg, type = "info") {
      if (!eg.logEl) return;
      eg.logEl.textContent = msg;
      eg.logEl.dataset.type = type;
    },
    getAdminToken() {
      return localStorage.getItem("eg_admin_token") || "";
    },
    setAdminToken(value) {
      localStorage.setItem("eg_admin_token", value || "");
      document.querySelectorAll("[data-admin-token]").forEach((el) => {
        el.value = value || "";
      });
    },
    headers(extra = {}) {
      const h = { ...extra };
      const token = eg.getAdminToken();
      if (token) {
        h["X-Admin-Token"] = token;
      }
      return h;
    },
    async api(path, options = {}) {
      const opts = { ...options };
      opts.headers = eg.headers(opts.headers || {});
      if (opts.body && !(opts.body instanceof FormData) && typeof opts.body !== "string") {
        opts.body = JSON.stringify(opts.body);
        opts.headers["Content-Type"] = "application/json";
      }
      const resp = await fetch(path, opts);
      let data = null;
      const ct = resp.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        data = await resp.json();
      } else {
        data = await resp.text();
      }
      if (!resp.ok) {
        const detail = typeof data === "string" ? data : data?.detail;
        throw new Error(detail || `HTTP ${resp.status}`);
      }
      return data;
    },
    connectStatus(onMessage) {
      const wsUrl = `${location.origin.replace(/^http/, "ws")}/ws/status`;
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (evt) => {
        try {
          onMessage(JSON.parse(evt.data));
        } catch (e) {
          console.error("WS parse error", e);
        }
      };
      ws.onerror = (e) => console.warn("WS error", e);
      return ws;
    },
  };

  window.eg = eg;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-admin-token]").forEach((input) => {
      input.value = eg.getAdminToken();
      input.addEventListener("change", (e) => eg.setAdminToken(e.target.value.trim()));
    });
  });
})();
