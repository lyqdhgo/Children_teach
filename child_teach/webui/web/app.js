/* 小星老师 · 前端逻辑（原生 JS，无框架、无外部请求） */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const chat = $("chat");
  const quick = $("quick");
  const sayInput = $("sayInput");
  const parentNote = $("parentNote");

  let busy = false;
  let speakOn = true;

  /* ---------------------------------------------------------- 网络 */
  async function api(path, body) {
    const options = body === undefined
      ? { method: "GET" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        };
    const res = await fetch(path, options);
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  /* ---------------------------------------------------------- 渲染 */
  function addMsg(text, mine = false) {
    const row = document.createElement("div");
    row.className = "row-msg" + (mine ? " me" : "");
    row.innerHTML = `<div class="avatar">${mine ? "🧒" : "🐣"}</div>`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    row.appendChild(bubble);
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
    return bubble;
  }

  function renderQuick(items) {
    quick.innerHTML = "";
    (items || []).forEach((label) => {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.onclick = () => send(label);
      quick.appendChild(btn);
    });
  }

  function renderStats(status) {
    if (!status) return;
    $("statStars").textContent = status.stars ?? 0;
    $("statMinutes").textContent = Math.round(status.minutes ?? 0);
    $("statTasks").textContent = status.tasks ?? 0;
    $("statAcc").textContent =
      status.graded ? Math.round((status.accuracy ?? 0) * 100) + "%" : "—";
    $("stateBadge").textContent = status.state ?? "";
  }

  /* 朗读：用浏览器自带语音，帮助识字量有限的孩子 */
  function speak(text) {
    if (!speakOn || !("speechSynthesis" in window) || !text) return;
    const clean = text
      .replace(/[\u{1F000}-\u{1FAFF}\u{2190}-\u{27BF}\u{FE0F}\u{2B00}-\u{2BFF}]/gu, "")
      .replace(/[①-④]/g, " ")
      .trim();
    if (!clean) return;
    const utter = new SpeechSynthesisUtterance(clean);
    utter.lang = "zh-CN";
    utter.rate = 0.92;
    utter.pitch = 1.15;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }

  function render(payload) {
    if (payload.echo) addMsg(payload.echo, true);
    if (payload.child_text) addMsg(payload.child_text, false);
    renderStats(payload.status);
    renderQuick(payload.suggestions);
    if (payload.parent_note) {
      parentNote.textContent = "📋 给家长的简报：\n" + payload.parent_note;
      parentNote.classList.remove("hidden");
    } else {
      parentNote.classList.add("hidden");
    }
    speak(payload.child_text || "");
    if (payload.habit_sync) loadHabit();
  }

  async function call(fn) {
    if (busy) return;
    busy = true;
    try {
      render(await fn());
    } catch (err) {
      addMsg("哎呀，连接不上小星老师了～（" + err.message + "）", false);
    } finally {
      busy = false;
      sayInput.focus();
    }
  }

  const send = (text) => {
    const value = (text ?? sayInput.value).trim();
    if (!value) return;
    sayInput.value = "";
    call(async () => {
      const payload = await api("/api/say", { text: value });
      payload.echo = value;
      return payload;
    });
  };

  /* ---------------------------------------------------------- 学习面板 */
  $("sayForm").addEventListener("submit", (event) => {
    event.preventDefault();
    send();
  });

  $("btnRestart").addEventListener("click", () => {
    chat.innerHTML = "";
    parentNote.classList.add("hidden");
    quick.innerHTML = "";
    window.speechSynthesis && window.speechSynthesis.cancel();
    call(() => api("/api/start", {}));
  });

  const speakBtn = $("btnSpeak");
  speakBtn.addEventListener("click", () => {
    speakOn = !speakOn;
    speakBtn.classList.toggle("on", speakOn);
    speakBtn.textContent = speakOn ? "🔊 朗读" : "🔇 静音";
    if (!speakOn && "speechSynthesis" in window) window.speechSynthesis.cancel();
  });

  /* ---------------------------------------------------------- 标签页 */
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $("panel-" + tab.dataset.panel).classList.add("active");
      if (tab.dataset.panel === "habit") loadHabit();
      if (tab.dataset.panel === "parent") loadBankInfo();
    });
  });

  /* ---------------------------------------------------------- 打卡面板 */
  async function loadHabit() {
    try {
      const data = await api("/api/habit");
      $("goalNow").textContent = data.goal
        ? "今天的小目标：" + data.goal
        : "还没有定小目标，写一个吧～";
      $("goalInput").placeholder = data.suggestions[0] || "例如：坐姿棒棒的";

      const list = $("habitList");
      list.innerHTML = "";
      data.items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "habit-item" + (item.done ? " done" : "");
        row.innerHTML =
          `<div class="label">${item.done ? "✅" : "⬜"} ${item.label}` +
          `<span class="ask">${item.child_prompt}</span></div>`;
        const btn = document.createElement("button");
        btn.textContent = item.done ? "撤销" : "做到了";
        btn.className = item.done ? "undo" : "";
        btn.onclick = async () => {
          await api("/api/habit/check", { key: item.key, done: !item.done });
          loadHabit();
        };
        row.appendChild(btn);
        list.appendChild(row);
      });
      $("habitSummary").textContent = data.summary;
      $("habitWeek").textContent = data.weekly;
    } catch (err) {
      $("habitSummary").textContent = "加载失败：" + err.message;
    }
  }

  $("goalSave").addEventListener("click", async () => {
    const goal = $("goalInput").value.trim();
    if (!goal) return;
    await api("/api/habit/goal", { goal });
    $("goalInput").value = "";
    loadHabit();
  });

  /* ---------------------------------------------------------- 家长面板 */
  async function showReport(kind) {
    const path = { today: "/api/parent/summary", week: "/api/parent/week",
                   advice: "/api/parent/advice" }[kind];
    try {
      const data = await api(path);
      $("parentReport").textContent = data.report;
    } catch (err) {
      $("parentReport").textContent = "加载失败：" + err.message;
    }
  }

  document.querySelectorAll("[data-report]").forEach((btn) => {
    btn.addEventListener("click", () => showReport(btn.dataset.report));
  });

  async function ask(text) {
    const value = (text ?? $("askInput").value).trim();
    if (!value) return;
    $("askInput").value = "";
    try {
      const data = await api("/api/parent/ask", { query: value });
      $("askAnswer").textContent = "Q：" + value + "\nA：" + data.answer;
    } catch (err) {
      $("askAnswer").textContent = "加载失败：" + err.message;
    }
  }

  $("askSend").addEventListener("click", () => ask());
  $("askInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") ask();
  });
  document.querySelectorAll("[data-ask]").forEach((btn) => {
    btn.addEventListener("click", () => ask(btn.dataset.ask));
  });

  async function loadBankInfo() {
    try {
      const data = await api("/api/bank");
      $("bankInfo").textContent = data.report;
    } catch (err) {
      $("bankInfo").textContent = "加载失败：" + err.message;
    }
  }

  /* ---------------------------------------------------------- 启动 */
  call(() => api("/api/start", {}));
})();
