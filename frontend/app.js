const $ = (id) => document.getElementById(id);

const LABELS = {
  high: "🚨 High risk",
  medium: "⚠️ Be careful",
  low: "✅ Low risk",
  unknown: "🤔 Couldn't fully check",
};

const EXAMPLES = [
  "Dear customer, your account has been suspended due to unusual activity. Verify your identity within 24 hours at http://rnicrosoft-secure-login.top/verify or it will be closed.",
  "Hi sweetie, I can't video call because we're offshore on the rig for security reasons. My daughter is in hospital and the doctor needs a $3,000 deposit. Please, you're the only one I trust.",
  "Congratulations! You've been selected for a remote job: earn $500 a day liking videos. Pay a $30 registration fee to start today.",
];
let exampleIndex = 0;
let lastVerdict = null;

function fillList(el, items) {
  el.replaceChildren(...items.map((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    return li;
  }));
}

function render(v) {
  lastVerdict = v;
  const result = $("result");
  result.className = `card result risk-border-${v.risk}`;
  const badge = $("risk-badge");
  badge.className = `risk-badge risk-${v.risk}`;
  badge.textContent = LABELS[v.risk] || LABELS.unknown;

  $("scam-type").textContent = v.scam_type || "";
  $("scam-type").hidden = !v.scam_type;
  $("summary").textContent = v.summary || "";

  const reasons = [...(v.reasons || []), ...(v.findings || []).map((f) => f.message)];
  fillList($("reasons"), [...new Set(reasons)]);
  $("reasons-block").hidden = reasons.length === 0;

  const marked = v.annotated_image || "";
  $("marked-block").hidden = !marked;
  if (marked) $("marked-image").src = marked;
  else $("marked-image").removeAttribute("src");
  fillList($("marked-list"), v.marked_regions || []);

  const inside = v.extracted_text || "";
  $("extracted-title").textContent =
    v.input_type === "audio" ? "What the voice note says" :
    v.input_type === "image" ? "Text we read from the image" : "What we found inside";
  $("extracted").textContent = inside.length > 1200 ? inside.slice(0, 1200) + "…" : inside;
  $("extracted-block").hidden = !inside;
  const fixes = v.corrections || [];
  $("corrections").textContent = fixes.length ? `We fixed words the recording may have misheard: ${fixes.join(", ")}` : "";
  $("corrections").hidden = !fixes.length;

  $("what-next").textContent = v.what_next || "";
  $("next-block").hidden = !v.what_next;

  fillList($("advice"), v.advice || []);
  $("advice-block").hidden = !(v.advice || []).length;

  const story = (v.timeline || []).length || v.stage;
  $("story-block").hidden = !story;
  $("stage").textContent = v.stage ? `Stage: ${v.stage}` : "";
  $("stage").hidden = !v.stage;
  fillList($("timeline"), v.timeline || []);
  fillList($("contradictions"), v.contradictions || []);
  $("contradictions-block").hidden = !(v.contradictions || []).length;

  const risky = ["high", "medium"].includes(v.risk);
  $("visit-block").hidden = true;
  if ((v.links || []).length && v.risk !== "low") visitSite(v.links[0]);
  $("report-btn").hidden = !risky;
  $("card-btn").hidden = !risky;
  $("report-panel").hidden = true;
  $("card-panel").hidden = true;

  result.hidden = false;
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function check(event) {
  event.preventDefault();
  const text = $("message").value.trim();
  const files = [...$("file").files];
  const file = files[0];
  if (!text && !file) {
    $("message").focus();
    return;
  }
  const btn = $("check-btn");
  btn.disabled = true;
  btn.textContent = file && file.type.startsWith("audio") ? "Listening…" : "Checking…";
  try {
    const form = new FormData();
    if (text) form.append("text", text);
    const together = files.length > 1;
    if (together) {
      btn.textContent = `Reading ${files.length} screenshots…`;
      files.forEach((f) => form.append("files", f));
    } else if (file) form.append("file", file);
    const res = await fetch(together ? "/api/check/conversation" : "/api/check", { method: "POST", body: form });
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail || ""; } catch (_) {}
      throw new Error(typeof detail === "string" && detail ? detail : `HTTP ${res.status}`);
    }
    render(await res.json());
  } catch (err) {
    const msg = err && err.message && !err.message.startsWith("HTTP") ? err.message : "";
    render({
      risk: "unknown",
      summary: msg || "Something went wrong while checking. Please try again in a moment.",
      advice: ["Meanwhile, don't send money, codes or card details."],
    });
  } finally {
    btn.disabled = false;
    btn.textContent = "Check it";
  }
}

function shareText(v) {
  const lines = [
    `TrueTick checked a message: ${LABELS[v.risk] || ""}`,
    v.scam_type ? `Type: ${v.scam_type}` : "",
    v.summary || "",
    v.what_next ? `What usually happens next: ${v.what_next}` : "",
    (v.advice || []).length ? `What to do: ${v.advice.join(" ")}` : "",
    `Check your own messages: ${location.origin}`,
  ];
  return lines.filter(Boolean).join("\n");
}

async function share() {
  if (!lastVerdict) return;
  const text = shareText(lastVerdict);
  try {
    if (navigator.share) {
      await navigator.share({ title: "TrueTick", text });
      return;
    }
    await navigator.clipboard.writeText(text);
    $("share-btn").textContent = "Copied! Paste it to your family";
    setTimeout(() => ($("share-btn").textContent = "Share with family"), 2500);
  } catch (_) {
    /* user cancelled sharing */
  }
}

$("check-form").addEventListener("submit", check);
$("share-btn").addEventListener("click", share);
$("file").addEventListener("change", () => {
  const fs = [...$("file").files];
  $("file-name").textContent = fs.length > 1 ? `Selected ${fs.length} screenshots (we'll read them as one conversation)` :
    fs.length ? `Selected: ${fs[0].name}` : "";
  $("file-name").hidden = !fs.length;
});
$("again-btn").addEventListener("click", () => {
  $("result").hidden = true;
  $("message").value = "";
  $("file").value = "";
  $("file-name").hidden = true;
  $("message").focus();
});
$("example-btn").addEventListener("click", () => {
  $("message").value = EXAMPLES[exampleIndex % EXAMPLES.length];
  exampleIndex += 1;
});

// ---------- Report this scam ----------
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
  try {
    const list = await (await fetch("/api/report/countries")).json();
    const sel = $("country");
    for (const c of [...list].reverse()) {
      const o = document.createElement("option");
      o.value = c.code;
      o.textContent = c.name;
      sel.insertBefore(o, sel.firstChild);
    }
    sel.value = guessCountry();
  } catch (_) {}
}

let lastReport = null;

async function loadReport() {
  if (!lastVerdict) return;
  const res = await fetch("/api/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verdict: { ...lastVerdict, annotated_image: "" }, country: $("country").value }),
  });
  lastReport = await res.json();
  const o = lastReport.options;
  fillList($("always-list"), o.always || []);
  $("report-links").replaceChildren(...(o.links || []).map((l) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = l.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = l.name;
    li.append(a);
    return li;
  }));
  $("report-note").textContent = o.note || "";
  $("report-note").hidden = !o.note;
}

$("report-btn").addEventListener("click", async () => {
  $("report-panel").hidden = false;
  await loadReport();
  $("report-panel").scrollIntoView({ behavior: "smooth", block: "start" });
});
$("country").addEventListener("change", loadReport);
$("copy-report-btn").addEventListener("click", async () => {
  if (!lastReport) return;
  try {
    await navigator.clipboard.writeText(lastReport.summary);
    $("copy-report-btn").textContent = "Copied! Paste it into your report";
    setTimeout(() => ($("copy-report-btn").textContent = "Copy a report summary"), 2500);
  } catch (_) {}
});
loadCountries();

// ---------- Family warning card (Muse Image illustration + TrueTick text) ----------
let cardBlob = null;

$("card-btn").addEventListener("click", async () => {
  if (!lastVerdict) return;
  $("card-panel").hidden = false;
  $("card-status").textContent = "Creating your card… (the first one of each type takes a few seconds)";
  $("card-status").hidden = false;
  $("card-image").hidden = true;
  $("card-share-btn").hidden = true;
  $("card-download").hidden = true;
  $("card-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const res = await fetch("/api/card", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern_id: lastVerdict.pattern_id, scam_type: lastVerdict.scam_type || "" }),
    });
    if (!res.ok) throw new Error();
    cardBlob = await res.blob();
    const url = URL.createObjectURL(cardBlob);
    $("card-image").src = url;
    $("card-image").hidden = false;
    $("card-download").href = url;
    $("card-download").hidden = false;
    $("card-share-btn").hidden = !(navigator.canShare && navigator.canShare({ files: [new File([cardBlob], "a.png", { type: "image/png" })] }));
    $("card-status").hidden = true;
  } catch (_) {
    $("card-status").textContent = "Sorry, we couldn't make the card right now. Please try again.";
  }
});

$("card-share-btn").addEventListener("click", async () => {
  if (!cardBlob) return;
  try {
    await navigator.share({ files: [new File([cardBlob], "truetick-warning.png", { type: "image/png" })],
                            title: "Scam alert", text: "Please read this and stay safe." });
  } catch (_) {}
});


// ---------- Live Call Guard ----------
// Records the (speakerphone) call in short complete pieces, sends each to /api/live/chunk
// (Muse Voice Transcribe + instant checks), and asks Muse Spark about the whole call every few pieces.
const LIVE_PIECE_MS = 5000;
const live = { stream: null, recorder: null, transcript: "", running: false, pieces: 0, shown: new Set(), assessing: false };

function liveStatus(text) {
  $("live-status").textContent = text;
  $("live-status").hidden = !text;
}

function showLiveAlert(a) {
  if (live.shown.has(a.id)) return;
  live.shown.add(a.id);
  $("live-alert").className = `live-alert ${a.severity === "stop" ? "" : "warn"}`;
  $("live-alert-title").textContent = (a.severity === "stop" ? "⚠️ STOP: " : "⚠️ Careful: ") + a.title;
  $("live-alert-advice").textContent = a.advice;
  $("live-alert").hidden = false;
  if (navigator.vibrate) navigator.vibrate(a.severity === "stop" ? [400, 150, 400, 150, 400] : [300]);
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
    $("live-badge").className = `risk-badge risk-${v.risk}`;
    $("live-badge").textContent = LABELS[v.risk] || LABELS.unknown;
    $("live-type").textContent = v.scam_type || "";
    $("live-summary").textContent = v.summary || "";
    $("live-verdict").hidden = false;
    if (v.risk === "high" && navigator.vibrate) navigator.vibrate([400, 150, 400]);
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
    if (body.text) {
      live.transcript = `${live.transcript} ${body.text}`.trim();
      $("live-transcript").textContent = live.transcript;
      $("live-transcript-block").hidden = false;
    }
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
  rec.onstop = () => {
    sendPiece(new Blob(parts, { type: rec.mimeType || "audio/webm" }));
    recordPiece(); // start the next piece straight away so nothing is missed
  };
  live.recorder = rec;
  rec.start();
  setTimeout(() => rec.state === "recording" && rec.stop(), LIVE_PIECE_MS);
}

async function startLive() {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    liveStatus("This browser can't listen. Try Chrome or Safari, and open TrueTick over https.");
    return;
  }
  try {
    live.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true },
    });
  } catch (_) {
    liveStatus("We need microphone permission to listen. Allow it in your browser settings and try again.");
    return;
  }
  Object.assign(live, { running: true, transcript: "", pieces: 0, shown: new Set() });
  ["live-alert", "live-verdict", "live-transcript-block"].forEach((id) => ($(id).hidden = true));
  $("live-start").hidden = true;
  $("live-stop").hidden = false;
  liveStatus("🎧 Listening… keep the call on speaker, near this device.");
  recordPiece();
}

function stopLive() {
  live.running = false;
  if (live.recorder && live.recorder.state === "recording") live.recorder.stop();
  if (live.stream) live.stream.getTracks().forEach((t) => t.stop());
  $("live-start").hidden = false;
  $("live-stop").hidden = true;
  liveStatus(live.transcript ? "Stopped. Here's what we found." : "Stopped.");
  setTimeout(liveAssess, 800);
}

$("live-start").addEventListener("click", startLive);
$("live-stop").addEventListener("click", stopLive);


// ---------- "We visited the website for you" ----------
let visitToken = 0;

async function visitSite(url) {
  const token = ++visitToken;
  $("visit-block").hidden = false;
  $("visit-status").textContent = "Opening the link safely… (takes about 10 seconds)";
  $("visit-status").hidden = false;
  $("visit-image").hidden = true;
  $("visit-summary").textContent = "";
  fillList($("visit-findings"), []);
  try {
    const res = await fetch("/api/visit", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }),
    });
    const s = await res.json();
    if (token !== visitToken) return; // a newer check started
    if (s.error) {
      $("visit-status").textContent = s.error;
      return;
    }
    $("visit-status").textContent = s.final_url && s.final_url !== url ? `The link took us to: ${s.final_url}` : "";
    $("visit-status").hidden = !$("visit-status").textContent;
    if (s.screenshot) {
      $("visit-image").src = s.screenshot;
      $("visit-image").hidden = false;
    }
    $("visit-summary").textContent = s.summary || "";
    fillList($("visit-findings"), (s.findings || []).map((f) => f.message));
  } catch (_) {
    if (token === visitToken) $("visit-status").textContent = "We couldn't open the website right now.";
  }
}
