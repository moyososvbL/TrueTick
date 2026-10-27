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
  if (!text) return;
  const btn = $("check-btn");
  btn.disabled = true;
  btn.textContent = "Checking…";
  try {
    const res = await fetch("/api/check/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
  } catch (err) {
    render({
      risk: "unknown",
      summary: "Something went wrong while checking. Please try again in a moment.",
      advice: ["Meanwhile, don't send money, codes or card details."],
    });
  } finally {
    btn.disabled = false;
    btn.textContent = "Check message";
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
$("again-btn").addEventListener("click", () => {
  $("result").hidden = true;
  $("message").value = "";
  $("message").focus();
});
$("example-btn").addEventListener("click", () => {
  $("message").value = EXAMPLES[exampleIndex % EXAMPLES.length];
  exampleIndex += 1;
});
