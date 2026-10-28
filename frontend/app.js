"use strict";

const $ = (id) => document.getElementById(id);
const ICON = (name) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;

const RISK = {
  high: { label: "High risk", title: "Likely a scam", icon: "shield-alert" },
  medium: { label: "Be careful", title: "Some warning signs", icon: "alert" },
  low: { label: "Low risk", title: "No scam signs found", icon: "check" },
  unknown: { label: "Couldn't fully check", title: "We couldn't be sure", icon: "question" },
};

const EXAMPLES = [
  "Zenora Bank: your account has been suspended due to unusual activity. Verify your identity within 24 hours at http://rnicrosoft-secure-login.top/verify or it will be closed.",
  "Hi sweetie, I can't video call because we're offshore on the rig for security reasons. My daughter is in hospital and the doctor needs a $3,000 deposit. Please, you're the only one I trust.",
  "Congratulations! You've been selected for a remote job: earn $500 a day liking videos. Pay a $30 registration fee to start today.",
];

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) {} },
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function list(el, items, icon = "chev") {
  el.innerHTML = items.map((t) => `<li>${ICON(icon)}<span>${esc(t)}</span></li>`).join("");
}

/* ---------------- theme ---------------- */
function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  $("theme").setAttribute("aria-pressed", String(dark));
  document.querySelector('meta[name="theme-color"]').content = dark ? "#070a14" : "#f6f8fc";
  store.set("tt-theme", dark ? "dark" : "light");
}
$("theme").addEventListener("click", () => setTheme(document.documentElement.dataset.theme !== "dark"));
setTheme(document.documentElement.dataset.theme === "dark");

/* ---------------- routing ---------------- */
let lastVerdict = null;

function route() {
  let name = (location.hash.replace(/^#\/?/, "").split("?")[0] || "home");
  if (name === "result" && !lastVerdict) name = "home";
  if (!document.querySelector(`[data-view="${name}"]`)) name = "home";
  document.querySelectorAll("[data-view]").forEach((v) => (v.hidden = v.dataset.view !== name));
  document.querySelectorAll("[data-route]").forEach((a) => {
    const on = a.dataset.route === name || (name === "result" && a.dataset.route === "home");
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if (name !== "live" && live.running) stopLive();
  if (name === "report") loadStandaloneReport();
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", route);

/* ---------------- checker ---------------- */
let picked = [];   // File objects
const MAX_SHOTS = 8;

function renderFiles() {
  const box = $("files");
  box.hidden = picked.length === 0;
  box.innerHTML = picked.map((f, i) =>
    `<span class="file-chip">${ICON(f.type.startsWith("audio") ? "mic" : f.type.startsWith("image") ? "image" : "file")}<span>${esc(f.name)}</span>` +
    `<button type="button" data-remove="${i}" aria-label="Remove ${esc(f.name)}">${ICON("x")}</button></span>`).join("");
  const n = picked.length;
  $("check-btn").querySelector(".label").textContent =
    n > 1 ? `Check ${n} screenshots` : "Check it";
}

$("files").addEventListener("click", (e) => {
  const b = e.target.closest("[data-remove]");
  if (!b) return;
  picked.splice(Number(b.dataset.remove), 1);
  renderFiles();
});

function openPicker(kind) {
  if (location.hash && location.hash !== "#/") location.hash = "#/";
  $(`pick-${kind}`).click();
}
document.addEventListener("click", (e) => {
  const p = e.target.closest("[data-pick]");
  if (p) { e.preventDefault(); openPicker(p.dataset.pick); }
  const f = e.target.closest("[data-focus]");
  if (f) { e.preventDefault(); $("message").focus(); }
});

["image", "audio", "qr", "file"].forEach((kind) => {
  $(`pick-${kind}`).addEventListener("change", (e) => {
    const chosen = [...e.target.files];
    e.target.value = "";
    if (!chosen.length) return;
    const allImages = (arr) => arr.every((f) => f.type.startsWith("image/"));
    // Several screenshots stay together (read as one conversation); anything else replaces the selection.
    if (kind === "image" && allImages(picked)) picked = [...picked, ...chosen].slice(0, MAX_SHOTS);
    else picked = chosen.slice(0, kind === "image" ? MAX_SHOTS : 1);
    renderFiles();
    hideError();
  });
});

document.querySelectorAll("[data-example]").forEach((b) =>
  b.addEventListener("click", () => {
    $("message").value = EXAMPLES[Number(b.dataset.example)];
    picked = []; renderFiles(); hideError(); autoGrow();
    $("message").focus();
  }));

// The message box grows with its text (up to its max height).
function autoGrow() { const m = $("message"); m.style.height = "auto"; m.style.height = Math.min(m.scrollHeight, 260) + "px"; }
$("message").addEventListener("input", () => { autoGrow(); hideError(); });

function showError(msg) { $("form-error").textContent = msg; $("form-error").hidden = false; }
function hideError() { $("form-error").hidden = true; }

function busy(on, text) {
  const b = $("check-btn");
  b.disabled = on;
  b.querySelector(".label").textContent = on ? text : "Check it";
  b.querySelector("i").innerHTML = on ? '<span class="spinner"></span>' : ICON("arrow");
  if (!on) renderFiles();
}

async function postForm(url, form) {
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch (_) {}
    throw new Error(typeof detail === "string" && detail ? detail : "Something went wrong. Please try again.");
  }
  return res.json();
}

$("checker").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();
  const text = $("message").value.trim();
  if (!text && !picked.length) { showError("Paste a message or add a screenshot, voice note or file."); $("message").focus(); return; }

  const form = new FormData();
  if (text) form.append("text", text);
  const together = picked.length > 1;
  const isAudio = picked[0] && picked[0].type.startsWith("audio");
  busy(true, together ? `Reading ${picked.length} screenshots…` : isAudio ? "Listening…" : "Checking…");
  try {
    let v;
    if (together) {
      picked.forEach((f) => form.append("files", f));
      v = await postForm("/api/check/conversation", form);
    } else {
      if (picked[0]) form.append("file", picked[0]);
      v = await postForm("/api/check", form);
    }
    showResult(v);
  } catch (err) {
    showError(err.message);
  } finally {
    busy(false);
  }
});

/* ---------------- result ---------------- */
function showResult(v) {
  lastVerdict = v;
  const r = RISK[v.risk] || RISK.unknown;
  $("r-verdict").className = `card risk-${RISK[v.risk] ? v.risk : "unknown"}`;
  $("r-icon").setAttribute("href", `#i-${r.icon}`);
  $("r-risk").textContent = r.label;
  $("r-title").textContent = v.scam_type || r.title;
  $("r-summary").textContent = v.summary || "";
  $("r-stage").hidden = !v.stage;
  $("r-stage").textContent = v.stage ? `Stage: ${v.stage}` : "";

  const why = [...new Set([...(v.reasons || []), ...(v.findings || []).map((f) => f.message)])];
  list($("r-why"), why);
  $("r-why-card").hidden = !why.length;
  $("r-next").textContent = v.what_next || "";
  $("r-next-card").hidden = !v.what_next;
  list($("r-advice"), v.advice || [], "check");
  $("r-advice-card").hidden = !(v.advice || []).length;

  $("r-marked").hidden = !v.annotated_image;
  if (v.annotated_image) {
    $("r-marked-img").src = v.annotated_image;
    $("r-marked-list").innerHTML = (v.marked_regions || []).map((t) => `<li>${esc(t.replace(/^\d+\.\s*/, ""))}</li>`).join("");
  }

  const tl = v.timeline || [], contra = v.contradictions || [];
  $("r-story").hidden = !tl.length && !contra.length;
  $("r-timeline").innerHTML = tl.map((t) => `<li>${esc(t)}</li>`).join("");
  $("r-contra-wrap").hidden = !contra.length;
  list($("r-contra"), contra, "alert");

  const inside = v.extracted_text || "";
  $("r-text").hidden = !inside;
  $("r-text").open = false;
  $("r-text-title").textContent = v.input_type === "audio" ? "What the voice note says" : v.input_type === "image" ? "Text we read from the image" : "What we found inside";
  $("r-text-body").textContent = inside;
  const fixes = v.corrections || [];
  $("r-fixes").hidden = !fixes.length;
  $("r-fixes").textContent = fixes.length ? `We fixed words the recording may have misheard: ${fixes.join(", ")}` : "";

  const risky = v.risk === "high" || v.risk === "medium";
  $("report-btn").hidden = !risky;
  $("card-btn").hidden = !risky;

  $("r-visit").hidden = true;
  if ((v.links || []).length && v.risk !== "low") visitSite(v.links[0]);

  location.hash = "#/result";
  if (location.hash === "#/result") route();
}

let visitToken = 0;
async function visitSite(url) {
  const token = ++visitToken;
  $("r-visit").hidden = false;
  $("r-visit-status").textContent = "Opening the link safely on our server. This takes a few seconds.";
  $("r-visit-img").hidden = true;
  $("r-visit-summary").textContent = "";
  $("r-visit-list").innerHTML = "";
  try {
    const res = await fetch("/api/visit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    const s = await res.json();
    if (token !== visitToken) return;
    if (s.error) { $("r-visit-status").textContent = s.error; return; }
    $("r-visit-status").textContent = s.final_url && s.final_url !== url ? `The link took us to ${s.final_url}` : `We opened ${url}`;
    if (s.screenshot) { $("r-visit-img").src = s.screenshot; $("r-visit-img").hidden = false; }
    $("r-visit-summary").textContent = s.summary || "";
    list($("r-visit-list"), (s.findings || []).map((f) => f.message), "alert");
  } catch (_) {
    if (token === visitToken) $("r-visit-status").textContent = "We couldn't open the website right now.";
  }
}

function shareText(v) {
  const r = RISK[v.risk] || RISK.unknown;
  return [
    `TrueTick checked a message: ${r.label}`,
    v.scam_type ? `Type: ${v.scam_type}` : "",
    v.summary || "",
    v.what_next ? `What usually happens next: ${v.what_next}` : "",
    (v.advice || []).length ? `What to do: ${v.advice.join(" ")}` : "",
    `Check your own messages: ${location.origin}`,
  ].filter(Boolean).join("\n");
}

async function copyText(text, btn, done) {
  try {
    await navigator.clipboard.writeText(text);
    const label = btn.querySelector("span") || btn;
    const old = label.textContent;
    label.textContent = done;
    setTimeout(() => (label.textContent = old), 2200);
  } catch (_) {}
}

$("share-btn").addEventListener("click", async () => {
  if (!lastVerdict) return;
  const text = shareText(lastVerdict);
  if (navigator.share) { try { await navigator.share({ title: "TrueTick", text }); } catch (_) {} return; }
  copyText(text, $("share-btn"), "Copied. Paste it to your family");
});

/* ---------------- sheets ---------------- */
function openSheet(id) { $(id).hidden = false; $(id).querySelector("[data-close]").focus(); }
function closeSheets() { document.querySelectorAll(".sheet-backdrop").forEach((s) => (s.hidden = true)); }
document.querySelectorAll(".sheet-backdrop").forEach((s) =>
  s.addEventListener("click", (e) => { if (e.target === s || e.target.closest("[data-close]")) closeSheets(); }));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheets(); });

/* ---------------- report ---------------- */
let countriesLoaded = null;
const TZ_COUNTRY = { "Africa/Lagos": "NG", "Europe/London": "GB", "Europe/Belfast": "GB" };
function guessCountry() {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (TZ_COUNTRY[tz]) return TZ_COUNTRY[tz];
    if (tz.startsWith("America/") && navigator.language === "en-US") return "US";
  } catch (_) {}
  return "";
}
async function loadCountries() {
  if (!countriesLoaded) {
    countriesLoaded = fetch("/api/report/countries").then((r) => r.json()).catch(() => []);
  }
  const list = await countriesLoaded;
  for (const sel of [$("report-country"), $("sr-country")]) {
    if (sel.options.length > 1) continue;
    for (const c of [...list].reverse()) sel.insertBefore(new Option(c.name, c.code), sel.firstChild);
    sel.value = guessCountry();
  }
}
function renderLinks(ul, links) {
  ul.innerHTML = (links || []).map((l) =>
    `<li><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer"><span>${esc(l.name)}</span>${ICON("external")}</a></li>`).join("");
}
async function fetchReport(verdict, country) {
  const res = await fetch("/api/report", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verdict: { ...verdict, annotated_image: "" }, country }),
  });
  return res.json();
}

let lastReport = null;
async function refreshSheetReport() {
  lastReport = await fetchReport(lastVerdict, $("sr-country").value);
  renderLinks($("sr-links"), lastReport.options.links);
  $("sr-note").textContent = lastReport.options.note || "";
  $("sr-note").hidden = !lastReport.options.note;
}
$("report-btn").addEventListener("click", async () => {
  if (!lastVerdict) return;
  openSheet("sheet-report");
  await loadCountries();
  refreshSheetReport();
});
$("sr-country").addEventListener("change", refreshSheetReport);
$("sr-copy").addEventListener("click", () => lastReport && copyText(lastReport.summary, $("sr-copy"), "Copied. Paste it into your report"));

async function loadStandaloneReport() {
  await loadCountries();
  const data = await fetchReport({ risk: "unknown" }, $("report-country").value);
  renderLinks($("report-links"), data.options.links);
  $("report-note").textContent = data.options.note || "";
  $("report-note").hidden = !data.options.note;
  list($("report-always"), data.options.always || [], "check");
}
$("report-country").addEventListener("change", loadStandaloneReport);

/* ---------------- warning card ---------------- */
let cardBlob = null;
$("card-btn").addEventListener("click", async () => {
  if (!lastVerdict) return;
  openSheet("sheet-card");
  $("sc-status").hidden = false;
  $("sc-status").textContent = "Making your card. The first one of each scam type takes a few seconds.";
  ["sc-img", "sc-share", "sc-download"].forEach((id) => ($(id).hidden = true));
  try {
    const res = await fetch("/api/card", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern_id: lastVerdict.pattern_id, scam_type: lastVerdict.scam_type || "" }),
    });
    if (!res.ok) throw new Error();
    cardBlob = await res.blob();
    const url = URL.createObjectURL(cardBlob);
    $("sc-img").src = url; $("sc-img").hidden = false;
    $("sc-download").href = url; $("sc-download").hidden = false;
    const file = new File([cardBlob], "truetick-warning.png", { type: "image/png" });
    $("sc-share").hidden = !(navigator.canShare && navigator.canShare({ files: [file] }));
    $("sc-status").hidden = true;
  } catch (_) {
    $("sc-status").textContent = "We couldn't make the card right now. Please try again.";
  }
});
$("sc-share").addEventListener("click", async () => {
  if (!cardBlob) return;
  try { await navigator.share({ files: [new File([cardBlob], "truetick-warning.png", { type: "image/png" })], title: "Scam alert" }); } catch (_) {}
});

/* ---------------- Live Call Guard ---------------- */
// Records the speakerphone call in short complete pieces, sends each to /api/live/chunk
// (Muse Voice Transcribe + instant checks), and asks Muse Spark about the whole call every few pieces.
const LIVE_PIECE_MS = 5000;
const live = { stream: null, recorder: null, transcript: "", running: false, pieces: 0, shown: new Set(), assessing: false, wake: null };

function liveIdle(text) {
  $("live-on").hidden = true;
  $("live-start").hidden = false;
  $("live-stop").hidden = true;
  if (text) $("live-sub").textContent = text;
}

function showLiveAlert(a) {
  if (live.shown.has(a.id)) return;
  live.shown.add(a.id);
  $("live-alert").className = `card live-alert${a.severity === "stop" ? "" : " warn"}`;
  $("live-alert-kind").textContent = a.severity === "stop" ? "Stop" : "Careful";
  $("live-alert-title").textContent = a.title;
  $("live-alert-advice").textContent = a.advice;
  $("live-alert").hidden = false;
  $("live-alert").scrollIntoView({ behavior: "smooth", block: "center" });
  if (navigator.vibrate) navigator.vibrate(a.severity === "stop" ? [400, 150, 400, 150, 400] : [300]);
}

function renderTranscript(latest) {
  const before = live.transcript.slice(0, live.transcript.length - latest.length).trim();
  const mark = document.createElement("mark");
  mark.textContent = latest;
  $("live-transcript").replaceChildren(document.createTextNode(before ? before + " " : ""), mark);
  $("live-transcript-card").hidden = false;
}

async function liveAssess() {
  if (live.assessing || !live.transcript) return;
  live.assessing = true;
  try {
    const res = await fetch("/api/live/assess", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: live.transcript.slice(-12000) }),
    });
    if (!res.ok) return;
    const v = await res.json();
    const r = RISK[v.risk] || RISK.unknown;
    $("live-verdict").className = `card risk-${RISK[v.risk] ? v.risk : "unknown"}`;
    $("live-v-icon").setAttribute("href", `#i-${r.icon}`);
    $("live-v-risk").textContent = r.label;
    $("live-v-title").textContent = v.scam_type || r.title;
    $("live-v-summary").textContent = v.summary || "";
    $("live-verdict").hidden = false;
  } catch (_) {
  } finally {
    live.assessing = false;
  }
}

async function sendPiece(blob) {
  if (blob.size < 2000) return;
  const form = new FormData();
  form.append("audio", blob, "piece.webm");
  form.append("so_far", live.transcript.slice(-12000));
  try {
    const res = await fetch("/api/live/chunk", { method: "POST", body: form });
    if (!res.ok) return;
    const body = await res.json();
    if (body.text) { live.transcript = `${live.transcript} ${body.text}`.trim(); renderTranscript(body.text); }
    (body.alerts || []).forEach(showLiveAlert);
    live.pieces += 1;
    if (body.text && (live.pieces % 2 === 0 || (body.alerts || []).length)) liveAssess();
  } catch (_) {}
}

function recordPiece() {
  if (!live.running) return;
  const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find(
    (t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(live.stream, type ? { mimeType: type } : undefined);
  const parts = [];
  rec.ondataavailable = (e) => e.data.size && parts.push(e.data);
  rec.onstop = () => { sendPiece(new Blob(parts, { type: rec.mimeType || "audio/webm" })); recordPiece(); };
  live.recorder = rec;
  rec.start();
  setTimeout(() => rec.state === "recording" && rec.stop(), LIVE_PIECE_MS);
}

async function keepScreenOn(on) {
  try {
    if (on && "wakeLock" in navigator) live.wake = await navigator.wakeLock.request("screen");
    else if (!on && live.wake) { await live.wake.release(); live.wake = null; }
  } catch (_) {}
}

async function startLive() {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    $("live-sub").textContent = "This browser can't listen. Try Chrome or Safari over a secure (https) link.";
    return;
  }
  try {
    live.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true } });
  } catch (_) {
    $("live-sub").textContent = "We need the microphone to listen. Allow it in your browser settings, then try again.";
    return;
  }
  Object.assign(live, { running: true, transcript: "", pieces: 0, shown: new Set() });
  ["live-alert", "live-verdict", "live-transcript-card"].forEach((id) => ($(id).hidden = true));
  $("live-head").textContent = "Listening to your call";
  $("live-sub").textContent = "Keep the call on speaker, close to this device.";
  $("live-on").hidden = false;
  $("live-start").hidden = true;
  $("live-stop").hidden = false;
  keepScreenOn(true);
  recordPiece();
}

function stopLive() {
  live.running = false;
  if (live.recorder && live.recorder.state === "recording") live.recorder.stop();
  if (live.stream) live.stream.getTracks().forEach((t) => t.stop());
  keepScreenOn(false);
  $("live-head").textContent = live.transcript ? "Call check finished" : "On a call you're unsure about?";
  liveIdle(live.transcript ? "Here's what we found." : "Put the call on speaker, then start listening on this device.");
  if (live.transcript) setTimeout(liveAssess, 800);
}

$("live-start").addEventListener("click", startLive);
$("live-stop").addEventListener("click", stopLive);

/* ---------------- start ---------------- */
route();
