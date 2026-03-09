(() => {
  const usersTable = document.querySelector("#users-table tbody");
  const createForm = document.getElementById("create-user-form");
  const eventsList = document.getElementById("events-list");
  const enrollSelect = document.getElementById("enroll-user");
  const enrollHint = document.getElementById("enroll-hint");
  const btnCapture = document.getElementById("btn-capture");
  const snapshotImg = document.getElementById("enroll-snapshot");
  eg.setLogElement(enrollHint);

  async function loadUsers() {
    try {
      const users = await eg.api("/api/users/");
      renderUsers(users);
      renderEnrollOptions(users);
      eg.toast("Пользователи обновлены", "info");
    } catch (err) {
      eg.toast(err.message, "error");
    }
  }

  async function loadEvents() {
    try {
      const events = await eg.api("/api/events/?limit=100");
      eventsList.innerHTML = "";
      events.forEach((e) => {
        const div = document.createElement("div");
        div.className = "chip";
        div.textContent = `${e.timestamp} · ${e.level} · ${e.message}`;
        eventsList.appendChild(div);
      });
      eg.toast("События обновлены", "info");
    } catch (err) {
      eg.toast(err.message, "error");
    }
  }

  function renderUsers(users) {
    usersTable.innerHTML = "";
    users.forEach((u) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${u.id}</td><td>${u.login}</td><td>${u.status}</td><td>${u.role}</td>
        <td class="row">
          <button class="btn secondary" data-act="approve" data-id="${u.id}">Approve</button>
          <button class="btn secondary" data-act="reject" data-id="${u.id}">Reject</button>
        </td>`;
      usersTable.appendChild(tr);
    });
  }

  function renderEnrollOptions(users) {
    enrollSelect.innerHTML = "";
    users.forEach((u) => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = `${u.id}: ${u.login} (${u.status})`;
      enrollSelect.appendChild(opt);
    });
  }

  async function captureFace() {
    const userId = enrollSelect.value;
    if (!userId) {
      eg.toast("Выберите пользователя", "error");
      return;
    }
    btnCapture.disabled = true;
    enrollHint.textContent = "Захват лица через камеру шлюза...";
    try {
      await eg.api(`/api/users/${userId}/enroll`, { method: "POST" });
      eg.toast("Лицо захвачено сервером", "ok");
      await refreshSnapshot();
      await loadUsers();
    } catch (err) {
      eg.toast(err.message, "error");
    } finally {
      btnCapture.disabled = false;
    }
  }

  function refreshSnapshot() {
    if (snapshotImg) {
      snapshotImg.src = `/api/video/snapshot?_=${Date.now()}`;
    }
  }

  usersTable?.addEventListener("click", async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const act = target.dataset.act;
    const userId = target.dataset.id;
    if (!act || !userId) return;
    try {
      if (act === "approve") {
        await eg.api(`/api/users/${userId}/approve`, { method: "POST" });
      } else if (act === "reject") {
        await eg.api(`/api/users/${userId}/reject`, { method: "POST" });
      }
      await loadUsers();
      await loadEvents();
    } catch (err) {
      alert(err.message);
    }
  });

  createForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(createForm);
    try {
      await eg.api("/api/users/", {
        method: "POST",
        body: {
          name: form.get("name"),
          login: form.get("login"),
          password: form.get("password"),
          card_id: form.get("card_id"),
          access_level: 1,
          is_blocked: false,
          role: "user",
        },
      });
      createForm.reset();
      await loadUsers();
    } catch (err) {
      eg.toast(err.message, "error");
    }
  });

  document.getElementById("reload-btn")?.addEventListener("click", async () => {
    await loadUsers();
    await loadEvents();
    refreshSnapshot();
  });

  btnCapture?.addEventListener("click", captureFace);

  refreshSnapshot();
  loadUsers();
  loadEvents();
})();
