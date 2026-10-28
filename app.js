var state = { data: null, history: [], paper: null, live: {}, selected: "" };
var charts = {};

function $(id) { return document.getElementById(id); }

function el(tag, text, cls) {
  var e = document.createElement(tag);
  if (text !== null && text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function money(n) {
  if (n === null || n === undefined || isNaN(n)) return "-";
  return "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function usd(n, signed) {
  if (n === null || n === undefined || isNaN(n)) return "-";
  var v = Number(n);
  var sign = v < 0 ? "-" : (signed && v > 0 ? "+" : "");
  return sign + "$" + Math.abs(v).toFixed(2);
}

function pct(n) { return n === null || n === undefined ? "-" : n + "%"; }
function safeId(s) { return typeof s === "string" && /^[A-Za-z0-9]+$/.test(s); }
function safeUrl(u) { return typeof u === "string" && u.indexOf("https://dexscreener.com/") === 0; }
function pairOf(c) { return safeUrl(c.url) ? c.url.split("/").pop() : ""; }
function setStatus(msg) { $("status").textContent = msg; }

function loadJson(path) {
  return fetch(path + "?t=" + Date.now()).then(function (r) {
    if (!r.ok) throw new Error(path);
    return r.json();
  });
}

function loadAll() {
  setStatus("Refreshing...");
  return Promise.all([
    loadJson("data.json"),
    loadJson("history.json").catch(function () { return []; }),
    loadJson("paper.json").catch(function () { return null; })
  ]).then(function (res) {
    state.data = res[0];
    state.history = res[1];
    state.paper = res[2];
    state.live = {};
    render();
    setStatus("Loaded at " + new Date().toLocaleTimeString());
  }).catch(function () {
    $("updated").textContent = "No scan data yet.";
    setStatus("Could not load data.json. Run the scanner first.");
  });
}

function liveRefresh() {
  var list = state.data ? state.data.candidates : [];
  var addrs = list.map(function (c) { return c.address; }).filter(safeId);
  if (!addrs.length) { setStatus("No tokens to refresh."); return; }
  setStatus("Fetching live prices...");
  var chunks = [];
  for (var i = 0; i < addrs.length; i += 30) chunks.push(addrs.slice(i, i + 30));
  Promise.all(chunks.map(function (ch) {
    return fetch("https://api.dexscreener.com/tokens/v1/solana/" + ch.join(",")).then(function (r) { return r.json(); });
  })).then(function (results) {
    var live = {};
    results.forEach(function (arr) {
      (arr || []).forEach(function (p) {
        var a = p.baseToken && p.baseToken.address;
        var liq = (p.liquidity && p.liquidity.usd) || 0;
        if (a && (!live[a] || liq > live[a].liq)) {
          live[a] = { price: p.priceUsd, change: p.priceChange ? p.priceChange.h24 : null, liq: liq };
        }
      });
    });
    state.live = live;
    render();
    setStatus("Live prices updated at " + new Date().toLocaleTimeString() + " (marked with a dot)");
  }).catch(function () {
    setStatus("Live price fetch failed. Try again, or use Refresh data.");
  });
}

function showTab(name) {
  document.querySelectorAll(".panel").forEach(function (p) { p.hidden = p.id !== name; });
  document.querySelectorAll(".tab").forEach(function (t) {
    t.classList.toggle("active", t.getAttribute("data-tab") === name);
  });
  if (name === "charts") renderCharts();
  if (name === "details") renderDetails();
}

function renderOverview() {
  var d = state.data;
  var box = $("stats");
  box.textContent = "";
  var top = d.candidates.length ? d.candidates[0].liquidity_usd : null;
  var rate = d.scanned ? (d.passed / d.scanned * 100).toFixed(1) + "%" : "-";
  [["Scanned", d.scanned], ["Passed", d.passed], ["Pass rate", rate], ["Top liquidity", money(top)]].forEach(function (s) {
    var card = el("div", null, "stat");
    card.appendChild(el("span", s[0], "dim"));
    card.appendChild(el("b", s[1]));
    box.appendChild(card);
  });

  var rows = $("rows");
  rows.textContent = "";
  if (!d.candidates.length) {
    var tr0 = el("tr");
    var td0 = el("td", "Nothing passed the filter in the last scan. That is normal.");
    td0.colSpan = 8;
    tr0.appendChild(td0);
    rows.appendChild(tr0);
  }
  d.candidates.forEach(function (c) {
    var live = state.live[c.address];
    var price = live ? live.price : c.price_usd;
    var change = live && live.change !== null && live.change !== undefined ? live.change : c.change_24h;
    var tr = el("tr", null, "click");
    tr.appendChild(el("td", (c.name || "?") + " (" + (c.symbol || "?") + ")"));
    tr.appendChild(el("td", "$" + price + (live ? " \u2022" : "")));
    tr.appendChild(el("td", money(c.liquidity_usd)));
    tr.appendChild(el("td", money(c.volume_24h)));
    tr.appendChild(el("td", pct(change), change >= 0 ? "up" : "down"));
    tr.appendChild(el("td", c.trades_24h));
    tr.appendChild(el("td", c.age_hours + "h"));
    var linkCell = el("td");
    if (safeUrl(c.url)) {
      var a = el("a", "DexScreener");
      a.href = c.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.addEventListener("click", function (e) { e.stopPropagation(); });
      linkCell.appendChild(a);
    }
    tr.appendChild(linkCell);
    tr.addEventListener("click", function () {
      state.selected = c.address;
      showTab("details");
    });
    rows.appendChild(tr);
  });

  var parts = Object.entries(d.rejection_reasons || {})
    .sort(function (a, b) { return b[1] - a[1]; })
    .map(function (e) { return e[0] + ": " + e[1]; });
  $("reasons").textContent = parts.join("  |  ") || "No rejections recorded.";
}

function renderPicker() {
  var picker = $("picker");
  picker.textContent = "";
  var list = state.data.candidates;
  if (!list.length) {
    picker.appendChild(el("option", "No tokens passed the last scan"));
    return;
  }
  if (!list.some(function (c) { return c.address === state.selected; })) {
    state.selected = list[0].address;
  }
  list.forEach(function (c) {
    var o = el("option", (c.name || "?") + " (" + (c.symbol || "?") + ")");
    o.value = c.address;
    if (c.address === state.selected) o.selected = true;
    picker.appendChild(o);
  });
}

function renderDetails() {
  if (!state.data) return;
  renderPicker();
  var stats = $("detailstats");
  var embed = $("embedbox");
  stats.textContent = "";
  embed.textContent = "";
  var c = state.data.candidates.filter(function (x) { return x.address === state.selected; })[0];
  if (!c) return;

  var live = state.live[c.address];
  [["Price", "$" + (live ? live.price : c.price_usd)], ["Liquidity", money(c.liquidity_usd)],
   ["24h volume", money(c.volume_24h)], ["24h change", pct(c.change_24h)],
   ["Trades (24h)", c.trades_24h], ["Age", c.age_hours + " hours"]].forEach(function (s) {
    var card = el("div", null, "stat");
    card.appendChild(el("span", s[0], "dim"));
    card.appendChild(el("b", s[1]));
    stats.appendChild(card);
  });

  var addr = el("p", "Token address: " + c.address, "dim");
  embed.appendChild(addr);

  var pair = pairOf(c);
  if (safeId(pair)) {
    var frame = document.createElement("iframe");
    frame.src = "https://dexscreener.com/solana/" + pair + "?embed=1&theme=dark&trades=0&info=0";
    frame.title = "DexScreener chart";
    embed.appendChild(frame);
  }

  var points = [];
  state.history.forEach(function (entry) {
    (entry.tokens || []).forEach(function (t) {
      if (t.address === c.address) points.push({ label: entry.updated.slice(5), price: t.price });
    });
  });
  if (typeof Chart !== "undefined" && points.length) {
    var first = points[0].price;
    makeChart("c_track", {
      type: "line",
      data: {
        labels: points.map(function (p) { return p.label; }),
        datasets: [{ label: "% change", data: points.map(function (p) { return (p.price / first - 1) * 100; }), borderColor: "#6cb6ff", tension: 0.25 }]
      },
      options: baseOpts()
    });
  } else if (charts.c_track) {
    charts.c_track.destroy();
    delete charts.c_track;
  }
}

function renderHistory() {
  var rows = $("histrows");
  rows.textContent = "";
  var list = state.history.slice().reverse();
  if (!list.length) {
    var tr0 = el("tr");
    var td0 = el("td", "No history yet. It builds up as scans run.");
    td0.colSpan = 4;
    tr0.appendChild(td0);
    rows.appendChild(tr0);
  }
  list.forEach(function (e) {
    var tr = el("tr");
    tr.appendChild(el("td", e.updated));
    tr.appendChild(el("td", e.scanned));
    tr.appendChild(el("td", e.passed));
    tr.appendChild(el("td", (e.tokens || []).map(function (t) { return t.symbol; }).join(", ") || "-"));
    rows.appendChild(tr);
  });
}

function profitCell(n) {
  return el("td", usd(n, true), n > 0 ? "up" : (n < 0 ? "down" : ""));
}

function renderPaper() {
  var p = state.paper;
  var open = (p && Array.isArray(p.open)) ? p.open : [];
  var closed = (p && Array.isArray(p.closed)) ? p.closed : [];
  $("paperbody").hidden = !(open.length || closed.length);
  if (!open.length && !closed.length) {
    $("papernote").textContent = "No paper data yet. Run export_results.py on your computer after the ticket bot has made some paper trades.";
    return;
  }
  $("papernote").textContent = "Exported " + p.updated + ". Pretend money only. Open trades are not counted in profit until they close. \"Now\" is the price at the ticket bot's last check.";

  var t = p.totals || {};
  var best = t.best_trade ? t.best_trade.symbol + " " + usd(t.best_trade.profit_usd, true) : "-";
  var stats = $("paperstats");
  stats.textContent = "";
  [["Closed trades", t.closed_trades],
   ["Win rate", t.win_rate_pct === null || t.win_rate_pct === undefined ? "-" : t.win_rate_pct + "%"],
   ["Total profit", usd(t.profit_usd, true)],
   ["Best trade", best],
   ["Profit without best trade", t.profit_without_best_usd === null || t.profit_without_best_usd === undefined ? "needs 2+ trades" : usd(t.profit_without_best_usd, true)],
   ["Open trades", t.open_trades]].forEach(function (s) {
    var card = el("div", null, "stat");
    card.appendChild(el("span", s[0], "dim"));
    card.appendChild(el("b", s[1]));
    stats.appendChild(card);
  });

  var orows = $("openrows");
  orows.textContent = "";
  if (!open.length) {
    var tr0 = el("tr");
    var td0 = el("td", "No open paper trades.");
    td0.colSpan = 7;
    tr0.appendChild(td0);
    orows.appendChild(tr0);
  }
  open.forEach(function (o) {
    var tr = el("tr");
    tr.appendChild(el("td", o.symbol || "?"));
    tr.appendChild(el("td", usd(o.invested_usd)));
    tr.appendChild(el("td", "$" + o.start_price));
    tr.appendChild(el("td", o.peak_mult === null || o.peak_mult === undefined ? "-" : o.peak_mult + "x"));
    var now = o.now_mult;
    var hasNow = now !== null && now !== undefined;
    tr.appendChild(el("td", hasNow ? now + "x" : "-", hasNow ? (now >= 1 ? "up" : "down") : ""));
    tr.appendChild(el("td", o.took_profit ? "Yes" : "No"));
    tr.appendChild(el("td", usd(o.cash_taken_usd)));
    orows.appendChild(tr);
  });

  var crows = $("closedrows");
  crows.textContent = "";
  if (!closed.length) {
    var tr1 = el("tr");
    var td1 = el("td", "No closed paper trades yet.");
    td1.colSpan = 5;
    tr1.appendChild(td1);
    crows.appendChild(tr1);
  }
  closed.forEach(function (c) {
    var tr = el("tr");
    tr.appendChild(el("td", c.closed_at || "-"));
    tr.appendChild(el("td", c.symbol || "?"));
    tr.appendChild(el("td", usd(c.invested_usd)));
    tr.appendChild(el("td", usd(c.returned_usd)));
    tr.appendChild(profitCell(c.profit_usd));
    crows.appendChild(tr);
  });
}

function renderRules() {
  var list = state.data.rules;
  if (!Array.isArray(list) || !list.length) return;
  var ul = $("rulelist");
  ul.textContent = "";
  list.forEach(function (r) { ul.appendChild(el("li", r)); });
}

function baseOpts() { return { responsive: true, maintainAspectRatio: false }; }

function makeChart(id, config) {
  if (typeof Chart === "undefined") return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), config);
}

function renderCharts() {
  if (!state.data) return;
  if (typeof Chart === "undefined") {
    $("chartwarn").textContent = "The chart library did not load. Check your connection and refresh the page.";
    return;
  }
  $("chartwarn").textContent = "";
  Chart.defaults.color = "#8b93a1";
  Chart.defaults.borderColor = "#262c36";
  var d = state.data;
  var h = state.history;
  var list = d.candidates.slice(0, 15);

  makeChart("c_passed", {
    type: "line",
    data: {
      labels: h.map(function (e) { return e.updated.slice(5); }),
      datasets: [{ label: "Tokens passed", data: h.map(function (e) { return e.passed; }), borderColor: "#3ddc97", tension: 0.25 }]
    },
    options: baseOpts()
  });

  var reasons = Object.entries(d.rejection_reasons || {}).sort(function (a, b) { return b[1] - a[1]; });
  makeChart("c_reasons", {
    type: "bar",
    data: {
      labels: reasons.map(function (r) { return r[0]; }),
      datasets: [{ label: "Tokens rejected", data: reasons.map(function (r) { return r[1]; }), backgroundColor: "#ff6b6b" }]
    },
    options: baseOpts()
  });

  makeChart("c_liq", {
    type: "bar",
    data: {
      labels: list.map(function (c) { return c.symbol; }),
      datasets: [{ label: "Liquidity (USD)", data: list.map(function (c) { return c.liquidity_usd; }), backgroundColor: "#6cb6ff" }]
    },
    options: baseOpts()
  });

  makeChart("c_change", {
    type: "bar",
    data: {
      labels: list.map(function (c) { return c.symbol; }),
      datasets: [{
        label: "24h change (%)",
        data: list.map(function (c) { return c.change_24h; }),
        backgroundColor: list.map(function (c) { return c.change_24h >= 0 ? "#3ddc97" : "#ff6b6b"; })
      }]
    },
    options: baseOpts()
  });
}

function render() {
  var d = state.data;
  if (!d) return;
  $("updated").textContent = "Last scan: " + d.updated;
  renderOverview();
  renderHistory();
  renderRules();
  renderPaper();
  if (!$("charts").hidden) renderCharts();
  if (!$("details").hidden) renderDetails();
}

document.querySelectorAll(".tab").forEach(function (t) {
  t.addEventListener("click", function () { showTab(t.getAttribute("data-tab")); });
});
$("refresh").addEventListener("click", loadAll);
$("live").addEventListener("click", liveRefresh);
$("picker").addEventListener("change", function (e) {
  state.selected = e.target.value;
  renderDetails();
});

setInterval(loadAll, 300000);
loadAll();
