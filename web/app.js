const $ = (id) => document.getElementById(id);
const API = window.API_BASE || "http://127.0.0.1:5000";

const el = {
  jur: $("jurisdiction"),
  file: $("file"),
  text: $("text"),
  btnReview: $("btn-review"),
  btnClear: $("btn-clear"),
  btnRisky: $("btn-load-risky"),
  btnGood: $("btn-load-good"),
  summary: $("summary"),
  issues: $("issues"),
  raw: $("raw"),
  apiStatus: $("api-status"),
};

async function healthcheck() {
  try {
    const r = await fetch(`${API}/`);
    if (!r.ok) throw new Error("bad");
    const j = await r.json();
    el.apiStatus.textContent = `API OK • Rules: ${j.rules_loaded}`;
    el.apiStatus.className = "badge";
  } catch {
    el.apiStatus.textContent = "API Offline";
    el.apiStatus.className = "badge high";
  }
}

function setLoading(isLoading) {
  el.btnReview.disabled = isLoading;
  el.btnClear.disabled = isLoading;
  el.btnRisky.disabled = isLoading;
  el.btnGood.disabled = isLoading;
}

function badge(cls, text) {
  const span = document.createElement("span");
  span.className = `badge ${cls}`;
  span.textContent = text;
  return span;
}

function renderResult(data) {
  el.summary.innerHTML = "";
  el.issues.innerHTML = "";
  el.raw.textContent = JSON.stringify(data, null, 2);

  if (!data || data.error) {
    el.summary.appendChild(badge("high", data?.error || "Request failed"));
    return;
  }

  const s = data.summary || { high: 0, med: 0, low: 0 };
  el.summary.append(
    badge("high", `High: ${s.high}`),
    badge("med", `Med: ${s.med}`),
    badge("low", `Low: ${s.low}`),
    badge("", `Score: ${data.risk_score}`)
  );

  (data.issues || []).forEach(it => {
    const div = document.createElement("div");
    div.className = "issue";
    div.innerHTML = `
      <div class="title">
        <span class="badge ${it.severity}">${it.severity.toUpperCase()}</span>
        <strong>${it.id}</strong>
      </div>
      <div class="desc">${it.message || ""}</div>
      <div class="muted">${it.rationale || ""}</div>
    `;
    if (it.suggested_fix) {
      const details = document.createElement("details");
      details.innerHTML = `<summary>Suggested fix</summary><pre>${it.suggested_fix}</pre>`;
      div.appendChild(details);
    }
    el.issues.appendChild(div);
  });
}

async function review() {
  const text = el.text.value.trim();
  if (!text) { renderResult({ error: "Paste or upload contract text first." }); return; }
  setLoading(true);
  try {
    const res = await fetch(`${API}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, jurisdiction: el.jur.value })
    });
    const data = await res.json().catch(() => ({ error: "Invalid JSON response" }));
    renderResult(data);
  } catch (e) {
    renderResult({ error: e.message || "Network error" });
  } finally {
    setLoading(false);
  }
}

function clearAll() {
  el.text.value = "";
  el.summary.innerHTML = "";
  el.issues.innerHTML = "";
  el.raw.textContent = "—";
}

async function loadSample(name) {
  try {
    const r = await fetch(`/samples/${name}.txt`);
    el.text.value = r.ok ? await r.text() : "";
  } catch { /* ignore */ }
}

el.file.addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  if (!f) return;
  const text = await f.text();
  el.text.value = text;
});

el.btnReview.addEventListener("click", review);
el.btnClear.addEventListener("click", clearAll);
el.btnRisky.addEventListener("click", () => loadSample("nda_risky"));
el.btnGood.addEventListener("click", () => loadSample("nda_good"));

healthcheck();
