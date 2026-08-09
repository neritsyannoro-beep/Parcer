/* Лента крипто-новостей: читает data/feed.json и рисует список.
   Никаких зависимостей — файл открывается даже с локального диска. */

(() => {
  "use strict";

  const FEED_URL = "data/feed.json";
  const SEEN_KEY = "cryptoradar.seen.v1";
  const AUTO_REFRESH_MS = 5 * 60 * 1000;

  const el = {
    feed: document.getElementById("feed"),
    tabs: document.getElementById("tabs"),
    chips: document.getElementById("chips"),
    search: document.getElementById("search"),
    updated: document.getElementById("updated"),
    counts: document.getElementById("counts"),
    refresh: document.getElementById("refresh"),
    toast: document.getElementById("toast"),
  };

  const state = {
    data: null,
    tier: "all",
    tags: new Set(),
    query: "",
    seen: loadSeen(),
  };

  // ------------------------------------------------------------- утилиты

  function loadSeen() {
    try {
      return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"));
    } catch {
      return new Set();
    }
  }

  function saveSeen(ids) {
    // Храним только последние 800 id, иначе localStorage разрастается.
    const merged = [...new Set([...ids, ...state.seen])].slice(0, 800);
    state.seen = new Set(merged);
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify(merged));
    } catch { /* приватный режим — не критично */ }
  }

  function ago(hours) {
    if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} мин назад`;
    if (hours < 24) return `${Math.round(hours)} ч назад`;
    const d = Math.round(hours / 24);
    return `${d} ${d === 1 ? "день" : d < 5 ? "дня" : "дней"} назад`;
  }

  function plural(n, one, few, many) {
    const m100 = n % 100, m10 = n % 10;
    if (m100 >= 11 && m100 <= 14) return many;
    if (m10 === 1) return one;
    if (m10 >= 2 && m10 <= 4) return few;
    return many;
  }

  let toastTimer;
  function toast(message) {
    el.toast.textContent = message;
    el.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.remove("show"), 2000);
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fallback для старых мобильных браузеров и http-контекста.
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      ta.remove();
      return ok;
    }
  }

  // ------------------------------------------------------------- загрузка

  async function load({ silent = false } = {}) {
    if (!silent) el.refresh.classList.add("spinning");
    try {
      // cache-bust: GitHub Pages кэширует агрессивно.
      const res = await fetch(`${FEED_URL}?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.data = await res.json();
      renderControls();
      render();
      if (!silent) toast("Лента обновлена");
    } catch (err) {
      if (!state.data) {
        el.feed.innerHTML =
          `<div class="empty">Не удалось загрузить ленту.<br>${String(err.message)}
           <br><br>Если парсер ещё не отработал, файла data/feed.json пока нет.</div>`;
      } else if (!silent) {
        toast("Обновить не получилось");
      }
    } finally {
      el.refresh.classList.remove("spinning");
    }
  }

  // ------------------------------------------------------------- контролы

  function renderControls() {
    const d = state.data;
    const total = d.stats.total;

    const tiers = [{ id: "all", label: "Все", emoji: "", count: total }, ...d.tiers];
    el.tabs.innerHTML = tiers
      .map(
        (t) => `<button class="tab" role="tab" data-tier="${t.id}"
                 aria-selected="${state.tier === t.id}">
                 ${t.emoji} ${t.label} <span class="n">${t.count}</span></button>`
      )
      .join("");

    el.chips.innerHTML = d.tags
      .map(
        (t) => `<button class="chip" data-tag="${t.id}"
                 aria-pressed="${state.tags.has(t.id)}">
                 ${t.emoji} ${t.label} <span class="n">${t.count}</span></button>`
      )
      .join("");

    const dt = new Date(d.generated_at);
    el.updated.textContent = `Обновлено ${dt.toLocaleString("ru-RU", {
      day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    })}`;
    el.counts.textContent =
      `${total} ${plural(total, "новость", "новости", "новостей")} · ` +
      `${d.stats.sources} ${plural(d.stats.sources, "источник", "источника", "источников")} · ` +
      `${d.stats.new} новых`;
  }

  // --------------------------------------------------------------- рендер

  function visibleItems() {
    const q = state.query.trim().toLowerCase();
    return state.data.items.filter((it) => {
      if (state.tier !== "all" && it.tier !== state.tier) return false;
      if (state.tags.size && !it.tags.some((t) => state.tags.has(t))) return false;
      if (q) {
        const haystack = `${it.title} ${it.summary} ${it.source} ${it.entities.join(" ")}`;
        if (!haystack.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }

  function tagLabel(id) {
    const t = state.data.tags.find((x) => x.id === id);
    return t ? `${t.emoji} ${t.label}` : id;
  }

  function cardHTML(it) {
    const isNew = it.is_new && !state.seen.has(it.id);
    const badges =
      (isNew ? '<span class="badge-new">new</span>' : "") +
      (it.is_rising ? '<span class="badge-rising">↑ растёт</span>' : "");

    const sources =
      it.cluster_size > 1
        ? ` · ${it.cluster_size} ${plural(it.cluster_size, "источник", "источника", "источников")}`
        : "";

    const breakdown = Object.entries(it.breakdown)
      .filter(([, v]) => v !== 0)
      .map(([k, v]) => `<tr><td>${k}</td><td>${v > 0 ? "+" : ""}${v}</td></tr>`)
      .join("");

    return `
      <article class="card ${it.tier}" data-id="${it.id}">
        <div class="card-head">
          <span class="score">${Math.round(it.score)}</span>
          <span>${escapeHTML(it.source || it.domain)}</span>
          <span>${ago(it.age_hours)}${sources}</span>
          ${badges}
        </div>
        <h2 class="title">
          <a href="${escapeAttr(it.url)}" target="_blank" rel="noopener noreferrer">
            ${escapeHTML(it.title)}
          </a>
        </h2>
        ${it.hook ? `<p class="hook">${escapeHTML(it.hook)}</p>` : ""}
        ${it.summary ? `<p class="summary">${escapeHTML(it.summary)}</p>` : ""}
        ${
          it.tags.length
            ? `<div class="tags">${it.tags
                .map((t) => `<span class="tag">${tagLabel(t)}</span>`)
                .join("")}</div>`
            : ""
        }
        ${
          it.reasons.length
            ? `<details class="why">
                 <summary>Почему в этом месте: ${escapeHTML(it.reasons.join(", "))}</summary>
                 <table>${breakdown}</table>
               </details>`
            : ""
        }
        <div class="actions">
          <a class="btn" href="${escapeAttr(it.url)}" target="_blank"
             rel="noopener noreferrer">Открыть</a>
          <button class="btn primary" data-copy="${escapeAttr(it.tweet)}">
            Копировать для X
          </button>
        </div>
      </article>`;
  }

  function render() {
    const items = visibleItems();
    if (!items.length) {
      el.feed.innerHTML = '<div class="empty">Под этот фильтр ничего не нашлось.</div>';
      return;
    }

    let html = "";
    if (state.tier === "all") {
      // В общем списке разделяем блоки заголовками, чтобы было видно границы.
      for (const tier of state.data.tiers) {
        const group = items.filter((i) => i.tier === tier.id);
        if (!group.length) continue;
        html += `<p class="group-label">${tier.emoji} ${tier.label} — ${group.length}</p>`;
        html += group.map(cardHTML).join("");
      }
    } else {
      html = items.map(cardHTML).join("");
    }
    el.feed.innerHTML = html;

    // Метка «new» держится один показ: после отрисовки считаем всё увиденным.
    saveSeen(items.map((i) => i.id));
  }

  function escapeHTML(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }
  const escapeAttr = escapeHTML;

  // -------------------------------------------------------------- события

  el.tabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    state.tier = tab.dataset.tier;
    [...el.tabs.children].forEach((t) =>
      t.setAttribute("aria-selected", String(t === tab))
    );
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  el.chips.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const tag = chip.dataset.tag;
    if (state.tags.has(tag)) state.tags.delete(tag);
    else state.tags.add(tag);
    chip.setAttribute("aria-pressed", String(state.tags.has(tag)));
    render();
  });

  let searchTimer;
  el.search.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const value = e.target.value;
    searchTimer = setTimeout(() => {
      state.query = value;
      render();
    }, 180);
  });

  el.feed.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    const ok = await copy(btn.dataset.copy);
    toast(ok ? "Пост скопирован — вставляй в X" : "Копирование недоступно");
  });

  el.refresh.addEventListener("click", () => load());

  // Автообновление: только когда вкладка активна, чтобы не жечь трафик.
  setInterval(() => {
    if (!document.hidden) load({ silent: true });
  }, AUTO_REFRESH_MS);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.data) {
      const age = Date.now() - state.data.generated_ts * 1000;
      if (age > AUTO_REFRESH_MS) load({ silent: true });
    }
  });

  load();
})();
