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
