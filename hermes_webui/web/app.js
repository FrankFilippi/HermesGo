/* HermesWebUI shell front-end.
 *
 * Talks only to our local shell server (same origin). Responsibilities:
 *  - sidebar view switching
 *  - load the Hermes dashboard into the Chat iframe (via the /dashboard proxy)
 *  - the xterm.js terminal wired to /ws/terminal
 *  - the workspace file drawer (/api/files, /api/file)
 *  - the skills grid (/api/skills) and the Skill Market button (/api/open-external)
 */
(function () {
  "use strict";

  let info = null;
  const state = { filesPath: "", term: null, fit: null, ws: null, termStarted: false };

  async function getJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(url + " -> " + r.status);
    return r.json();
  }

  // --- view switching ---------------------------------------------------
  function showView(name) {
    document.querySelectorAll(".nav-item").forEach((b) =>
      b.classList.toggle("active", b.dataset.view === name)
    );
    document.querySelectorAll(".view").forEach((v) =>
      v.classList.toggle("active", v.id === "view-" + name)
    );
    if (name === "terminal") ensureTerminal();
    if (name === "files") loadFiles(state.filesPath);
    if (name === "skills") loadSkills();
    if (name === "terminal" && state.fit) setTimeout(() => state.fit.fit(), 50);
  }

  // --- chat / dashboard -------------------------------------------------
  function loadDashboard() {
    const frame = document.getElementById("dashboard-frame");
    // In proxy mode we load same-origin so it sits happily in our chrome.
    frame.src = info.embed_mode === "proxy" ? info.dashboard_proxy_path : info.dashboard_url;
  }

  // --- terminal ---------------------------------------------------------
  function ensureTerminal() {
    if (state.termStarted) return;
    state.termStarted = true;

    const term = new Terminal({
      fontFamily: "ui-monospace, Consolas, 'Cascadia Mono', monospace",
      fontSize: 13,
      theme: { background: "#0b0d12", foreground: "#e6e8ee", cursor: "#7c5cff" },
      cursorBlink: true,
    });
    const fit = new FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(document.getElementById("terminal"));
    fit.fit();
    state.term = term;
    state.fit = fit;

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/terminal`);
    state.ws = ws;
    const status = document.getElementById("term-status");

    ws.onopen = () => {
      status.textContent = "connected";
      sendResize();
    };
    ws.onclose = () => (status.textContent = "disconnected");
    ws.onerror = () => (status.textContent = "error");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "data") term.write(msg.data);
      else if (msg.type === "exit") {
        term.write("\r\n\x1b[90m[process exited]\x1b[0m\r\n");
        status.textContent = "exited";
      } else if (msg.type === "error") {
        term.write("\r\n\x1b[31m" + msg.message + "\x1b[0m\r\n");
      }
    };

    term.onData((d) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "data", data: d }));
    });

    function sendResize() {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
    }
    window.addEventListener("resize", () => {
      if (document.getElementById("view-terminal").classList.contains("active")) sendResize();
    });
  }

  // --- files ------------------------------------------------------------
  async function loadFiles(path) {
    try {
      const data = await getJSON("/api/files?path=" + encodeURIComponent(path || ""));
      state.filesPath = data.path || "";
      document.getElementById("files-path").textContent =
        data.root + (state.filesPath ? "\\" + state.filesPath : "");
      const list = document.getElementById("file-list");
      list.innerHTML = "";
      data.entries.forEach((e) => {
        const li = document.createElement("li");
        li.className = e.is_dir ? "dir" : "file";
        const name = document.createElement("span");
        name.className = "fname";
        name.textContent = e.name;
        const size = document.createElement("span");
        size.className = "fsize";
        size.textContent = e.is_dir ? "" : humanSize(e.size);
        li.appendChild(name);
        li.appendChild(size);
        li.onclick = () => {
          const child = (state.filesPath ? state.filesPath + "/" : "") + e.name;
          if (e.is_dir) loadFiles(child);
          else previewFile(child);
        };
        list.appendChild(li);
      });
      if (!data.entries.length) list.innerHTML = '<li class="empty">Empty folder</li>';
    } catch (err) {
      document.getElementById("file-list").innerHTML =
        '<li class="empty">' + err.message + "</li>";
    }
  }

  async function previewFile(path) {
    const pre = document.getElementById("file-preview");
    pre.textContent = "Loading…";
    try {
      const data = await getJSON("/api/file?path=" + encodeURIComponent(path));
      pre.textContent = data.content;
      pre.classList.remove("muted");
    } catch (err) {
      pre.textContent = "Cannot preview: " + err.message;
    }
  }

  function goUp() {
    if (!state.filesPath) return;
    const parts = state.filesPath.split(/[\\/]/).filter(Boolean);
    parts.pop();
    loadFiles(parts.join("/"));
  }

  function humanSize(n) {
    if (n == null) return "";
    const u = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) {
      n /= 1024;
      i++;
    }
    return n.toFixed(i ? 1 : 0) + " " + u[i];
  }

  // --- skills -----------------------------------------------------------
  async function loadSkills() {
    const grid = document.getElementById("skills-grid");
    try {
      const data = await getJSON("/api/skills");
      document.getElementById("skills-dir").textContent = data.skills_dir;
      grid.innerHTML = "";
      if (!data.skills.length) {
        grid.innerHTML = '<div class="empty">No skills installed yet. Open the Skill Market to add some.</div>';
        return;
      }
      data.skills.forEach((s) => {
        const card = document.createElement("div");
        card.className = "skill-card";
        const h = document.createElement("h3");
        h.textContent = s.name;
        const p = document.createElement("p");
        p.textContent = s.description || "No description.";
        card.appendChild(h);
        card.appendChild(p);
        grid.appendChild(card);
      });
    } catch (err) {
      grid.innerHTML = '<div class="empty">' + err.message + "</div>";
    }
  }

  // --- external links ---------------------------------------------------
  async function openExternal(url) {
    try {
      await fetch("/api/open-external", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
    } catch (e) {
      window.open(url, "_blank");
    }
  }

  // --- wire up ----------------------------------------------------------
  async function init() {
    info = await getJSON("/api/info");
    loadDashboard();

    document.querySelectorAll(".nav-item[data-view]").forEach((b) =>
      b.addEventListener("click", () => showView(b.dataset.view))
    );
    document.getElementById("skill-market").addEventListener("click", () =>
      openExternal(info.skill_market_url)
    );
    document.getElementById("open-logs").addEventListener("click", () =>
      alert("Logs folder:\n" + info.logs_dir)
    );
    document.getElementById("files-up").addEventListener("click", goUp);
  }

  init().catch((e) => {
    document.body.innerHTML =
      '<pre style="color:#ff7b72;padding:24px">Failed to initialise UI: ' + e.message + "</pre>";
  });
})();
