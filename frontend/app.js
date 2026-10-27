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

  const risky = ["high", "medium"].includes(v.risk);
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
  const file = $("file").files[0];
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
    if (file) form.append("file", file);
    const res = await fetch("/api/check", { method: "POST", body: form });
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
  const f = $("file").files[0];
  $("file-name").textContent = f ? `Selected: ${f.name}` : "";
  $("file-name").hidden = !f;
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
