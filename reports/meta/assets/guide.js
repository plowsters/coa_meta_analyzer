(() => {
  const THEME_KEY = "coa-theme";
  function applyTheme(value) {
    const theme = value === "void" ? "void" : "fel";
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-theme-btn]").forEach(btn => {
      btn.setAttribute("aria-pressed", String(btn.getAttribute("data-theme-value") === theme));
    });
    window.__coaTheme = theme;
    if (typeof window.__coaEmberRecolor === "function") window.__coaEmberRecolor(theme);
  }
  function initTheme() {
    let stored = "fel";
    try { stored = localStorage.getItem(THEME_KEY) || "fel"; } catch (_e) {}
    applyTheme(stored);
    document.addEventListener("click", event => {
      const btn = event.target.closest("[data-theme-btn]");
      if (!btn) return;
      const value = btn.getAttribute("data-theme-value");
      try { localStorage.setItem(THEME_KEY, value); } catch (_e) {}
      applyTheme(value);
    });
  }
  document.addEventListener("DOMContentLoaded", initTheme);
  const FEL_PAL = [[108,240,107],[154,107,255],[255,207,92]];
  const VOID_PAL = [[168,121,255],[108,240,107],[255,207,92]];
  let emberPalette = FEL_PAL, emberParts = [], emberCanvas, emberCtx, emberRaf, emberW, emberH;
  window.__coaEmberRecolor = theme => { emberPalette = theme === "void" ? VOID_PAL : FEL_PAL; };
  function sizeEmberCanvas() {
    if (!emberCanvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    emberW = window.innerWidth; emberH = window.innerHeight;
    emberCanvas.width = emberW * dpr; emberCanvas.height = emberH * dpr;
    emberCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function startEmbers() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    emberCanvas = document.createElement("canvas");
    emberCanvas.setAttribute("data-embers", "");
    emberCanvas.setAttribute("aria-hidden", "true");
    emberCanvas.style.cssText = "position:fixed;inset:0;width:100%;height:100%;z-index:-2;pointer-events:none;";
    document.body.insertBefore(emberCanvas, document.body.firstChild);
    emberCtx = emberCanvas.getContext("2d");
    sizeEmberCanvas();
    const rnd = (a, b) => a + Math.random() * (b - a);
    const n = Math.min(74, Math.round(emberW / 17));
    emberParts = Array.from({ length: n }, () => ({ x: rnd(0, emberW), y: rnd(0, emberH), r: rnd(0.7, 2.5), vy: rnd(-0.5, -0.13), vx: rnd(-0.15, 0.15), a: rnd(0.14, 0.66), tw: rnd(0.004, 0.02), ph: rnd(0, 6.28), ci: Math.random() < 0.12 ? 2 : (Math.random() < 0.4 ? 1 : 0) }));
    const loop = () => {
      emberCtx.clearRect(0, 0, emberW, emberH); emberCtx.globalCompositeOperation = "lighter";
      for (const p of emberParts) {
        p.y += p.vy; p.x += p.vx; p.ph += p.tw;
        if (p.y < -10) { p.y = emberH + 10; p.x = rnd(0, emberW); }
        if (p.x < -10) p.x = emberW + 10; if (p.x > emberW + 10) p.x = -10;
        const c = emberPalette[p.ci], al = p.a * (0.55 + 0.45 * Math.sin(p.ph));
        const g = emberCtx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4.5);
        g.addColorStop(0, "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + al + ")");
        g.addColorStop(1, "rgba(" + c[0] + "," + c[1] + "," + c[2] + ",0)");
        emberCtx.fillStyle = g; emberCtx.beginPath(); emberCtx.arc(p.x, p.y, p.r * 4.5, 0, 6.2832); emberCtx.fill();
      }
      emberCtx.globalCompositeOperation = "source-over"; emberRaf = requestAnimationFrame(loop);
    };
    loop();
    window.addEventListener("resize", sizeEmberCanvas);
  }
  document.addEventListener("DOMContentLoaded", startEmbers);
  const tooltipData = window.COA_TOOLTIPS || {};
  const pins = new Map();
  let hoverEl = null, hoverAnchor = null;
  function makeTip(id, pinned) {
    const tip = tooltipData[id];
    if (!tip) return null;
    const el = document.createElement("div");
    el.className = "tooltip" + (pinned ? " is-pinned" : "");
    el.innerHTML = tip.html || tip.text || "";
    if (pinned) {
      const hint = document.createElement("div");
      hint.className = "pin-hint";
      hint.textContent = "pinned · click again or press Esc to clear all";
      el.appendChild(hint);
    }
    document.body.appendChild(el);
    return el;
  }
  function placeTip(el, anchor) {
    const rect = anchor.getBoundingClientRect();
    const width = el.offsetWidth || 320;
    const left = Math.max(12, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - 12));
    el.style.left = left + "px";
    const below = rect.bottom + 12;
    if (below + el.offsetHeight < window.innerHeight - 16) {
      el.style.top = below + "px"; el.style.bottom = "auto";
    } else {
      el.style.top = "auto"; el.style.bottom = (window.innerHeight - rect.top + 12) + "px";
    }
  }
  function clearHover() {
    if (hoverEl) hoverEl.remove();
    hoverEl = null; hoverAnchor = null;
  }
  function showHover(anchor) {
    const id = anchor.getAttribute("data-tooltip-id");
    if (!id || pins.has(anchor)) return;
    clearHover();
    hoverEl = makeTip(id, false); hoverAnchor = anchor;
    if (hoverEl) placeTip(hoverEl, anchor);
  }
  function togglePin(anchor) {
    const id = anchor.getAttribute("data-tooltip-id");
    if (!id) return;
    if (pins.has(anchor)) {
      pins.get(anchor).el.remove(); pins.delete(anchor);
      return;
    }
    clearHover();
    const el = makeTip(id, true);
    if (!el) return;
    pins.set(anchor, { el, anchor }); placeTip(el, anchor);
  }
  function repositionPins() {
    pins.forEach(pin => placeTip(pin.el, pin.anchor));
    if (hoverEl && hoverAnchor) placeTip(hoverEl, hoverAnchor);
  }
  document.addEventListener("mouseover", event => {
    const target = event.target.closest("[data-tooltip-id]");
    if (target) showHover(target);
  });
  document.addEventListener("focusin", event => {
    const target = event.target.closest("[data-tooltip-id]");
    if (target) showHover(target);
  });
  document.addEventListener("mouseout", event => {
    const target = event.target.closest("[data-tooltip-id]");
    if (!target) return;
    const related = event.relatedTarget;
    if (related && target.contains(related)) return;
    clearHover();
  });
  document.addEventListener("focusout", event => {
    const target = event.target.closest("[data-tooltip-id]");
    if (!target || target !== hoverAnchor) return;
    const related = event.relatedTarget;
    if (related && target.contains(related)) return;
    clearHover();
  });
  document.addEventListener("click", event => {
    const target = event.target.closest("[data-tooltip-id]");
    if (!target) return;
    event.preventDefault();
    togglePin(target);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      clearHover();
      pins.forEach(pin => pin.el.remove());
      pins.clear();
    }
  });
  window.addEventListener("scroll", repositionPins, true);
  window.addEventListener("resize", repositionPins);
  document.addEventListener("click", event => {
    const filter = event.target.closest("[data-role-filter]");
    if (!filter) return;
    const buttons = Array.from(document.querySelectorAll("[data-role-filter]"));
    const roleButtons = buttons.filter(button => button.getAttribute("data-role-filter") !== "all");
    const allButton = buttons.find(button => button.getAttribute("data-role-filter") === "all");
    const selected = new Set(roleButtons.filter(button => button.getAttribute("aria-pressed") === "true").map(button => button.getAttribute("data-role-filter")));
    const clicked = filter.getAttribute("data-role-filter");
    if (clicked === "all") selected.clear();
    else if (selected.has(clicked)) selected.delete(clicked);
    else selected.add(clicked);
    const showAll = selected.size === 0;
    roleButtons.forEach(button => {
      const active = selected.has(button.getAttribute("data-role-filter"));
      button.setAttribute("aria-pressed", String(active));
      button.classList.toggle("is-active", active);
    });
    if (allButton) {
      allButton.setAttribute("aria-pressed", String(showAll));
      allButton.classList.toggle("is-active", showAll);
    }
    document.querySelectorAll("[data-role]").forEach(card => {
      const roles = (card.getAttribute("data-role") || "").split(/\s+/).filter(Boolean);
      card.hidden = showAll ? false : !roles.some(role => selected.has(role));
    });
    document.querySelectorAll("[data-role-section]").forEach(section => {
      section.hidden = showAll ? false : !selected.has(section.getAttribute("data-role-section"));
    });
  });
  function parseJson(value, fallback) {
    try { return JSON.parse(value || ""); } catch (_error) { return fallback; }
  }
  function stateClass(state) {
    if (state === "selected" || state === "free" || state === "available" || state === "over_budget") return "is-" + state.replace("_", "-");
    if ((state || "").startsWith("gated_")) return "is-gated";
    return "is-inactive";
  }
  function applySnapshot(panel, tree, level) {
    const snapshots = parseJson(tree.getAttribute("data-tree-snapshots"), []);
    const snapshot = snapshots.find(item => String(item.level) === String(level)) || snapshots[snapshots.length - 1] || {};
    const selected = new Set((snapshot.selected_node_ids || []).map(String));
    const free = new Set((snapshot.free_node_ids || []).map(String));
    const available = new Set((snapshot.available_node_ids || []).map(String));
    const gated = new Map((snapshot.gated_nodes || []).map(item => [String(item.node_id), item.state]));
    tree.querySelectorAll("[data-tree-node-id]").forEach(node => {
      const id = node.getAttribute("data-tree-node-id");
      node.classList.remove("is-selected", "is-free", "is-available", "is-gated", "is-inactive", "is-over-budget");
      let state = "inactive";
      if (free.has(id)) state = "free";
      else if (selected.has(id)) state = "selected";
      else if (available.has(id)) state = "available";
      else if (gated.has(id)) state = gated.get(id);
      node.classList.add(stateClass(state));
      node.setAttribute("data-state", state);
    });
    const summary = panel.querySelector("[data-tree-budget-summary]");
    if (summary) summary.textContent = `AE ${snapshot.ae_spent || 0}/${snapshot.max_ae || 0} - TE ${snapshot.te_spent || 0}/${snapshot.max_te || 0}`;
    drawTreeLinks(tree);
  }
  function drawTreeLinks(tree) {
    const svg = tree.querySelector(".tree-links");
    if (!svg) return;
    const edges = parseJson(svg.getAttribute("data-tree-edges"), []);
    const canvas = svg.closest(".talent-tree") || tree;
    const treeRect = canvas.getBoundingClientRect();
    svg.innerHTML = "";
    edges.forEach(edge => {
      const source = canvas.querySelector(`[data-tree-node-id="${edge.source_id}"]`);
      const target = canvas.querySelector(`[data-tree-node-id="${edge.target_id}"]`);
      if (!source || !target) return;
      const a = source.getBoundingClientRect();
      const b = target.getBoundingClientRect();
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(a.left + a.width / 2 - treeRect.left));
      line.setAttribute("y1", String(a.top + a.height / 2 - treeRect.top));
      line.setAttribute("x2", String(b.left + b.width / 2 - treeRect.left));
      line.setAttribute("y2", String(b.top + b.height / 2 - treeRect.top));
      line.classList.add("is-" + (edge.state || "inactive"));
      svg.appendChild(line);
    });
  }
  function initTrees() {
    document.querySelectorAll("[data-guide-tree-panel]").forEach(panel => {
      const buildSelector = panel.querySelector("[data-tree-build-selector]");
      const levelSelector = panel.querySelector("[data-tree-level-selector]");
      const levelLabel = panel.querySelector("[data-tree-level-label]");
      const levels = levelSelector ? parseJson(levelSelector.getAttribute("data-tree-levels"), []) : [];
      function currentLevel() {
        if (!levelSelector) return null;
        if (levels.length) {
          const index = Math.max(0, Math.min(parseInt(levelSelector.value, 10) || 0, levels.length - 1));
          return levels[index];
        }
        return levelSelector.value;
      }
      function currentBuildPanel() {
        const id = buildSelector ? buildSelector.value : panel.querySelector("[data-tree-build-panel]")?.getAttribute("data-tree-build-panel");
        return panel.querySelector(`[data-tree-build-panel="${id}"]`) || panel.querySelector("[data-tree-build-panel]");
      }
      function refresh() {
        const level = currentLevel();
        if (levelLabel && level != null) levelLabel.textContent = "Lv " + level;
        panel.querySelectorAll("[data-level-tick]").forEach(tick => {
          tick.classList.toggle("is-active", tick.getAttribute("data-level-tick") === String(level));
        });
        const activePanel = currentBuildPanel();
        panel.querySelectorAll("[data-tree-build-panel]").forEach(buildPanel => { buildPanel.hidden = buildPanel !== activePanel; });
        if (!activePanel) return;
        activePanel.querySelectorAll("[data-tree-kind]").forEach(tree => {
          applySnapshot(panel, tree, level != null ? level : tree.getAttribute("data-tree-level"));
        });
      }
      if (buildSelector) buildSelector.addEventListener("change", refresh);
      if (levelSelector) {
        levelSelector.addEventListener("change", refresh);
        levelSelector.addEventListener("input", refresh);
      }
      refresh();
    });
  }
  function initSectionNav() {
    const links = Array.from(document.querySelectorAll(".guide-nav a[href^='#']"));
    if (!links.length || typeof IntersectionObserver === "undefined") return;
    const byId = new Map(links.map(link => [link.getAttribute("href").slice(1), link]));
    const sections = Array.from(byId.keys()).map(id => document.getElementById(id)).filter(Boolean);
    if (!sections.length) return;
    const io = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        links.forEach(link => link.classList.remove("is-active"));
        const link = byId.get(entry.target.id);
        if (link) link.classList.add("is-active");
      });
    }, { rootMargin: "-140px 0px -62% 0px", threshold: 0 });
    sections.forEach(section => io.observe(section));
  }
  window.addEventListener("resize", () => document.querySelectorAll("[data-tree-kind]").forEach(drawTreeLinks));
  document.addEventListener("DOMContentLoaded", initTrees);
  document.addEventListener("DOMContentLoaded", initSectionNav);
})();
