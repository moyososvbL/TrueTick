// Writes capacitor.config.json. The app opens the live TrueTick site (TRUETICK_URL, https only).
import { writeFileSync } from "node:fs";

const url = (process.env.TRUETICK_URL || "").trim().replace(/\/+$/, "");
if (!/^https:\/\/[^\s/]+/.test(url)) {
  console.error("TRUETICK_URL must be the https address of the live TrueTick site, e.g. https://name-truetick.hf.space");
  process.exit(1);
}
const config = {
  appId: "app.truetick.android",
  appName: "TrueTick",
  webDir: "www",
  server: { url, cleartext: false, errorPath: "index.html" },
  android: { backgroundColor: "#f6f8fc" },
};
writeFileSync("capacitor.config.json", JSON.stringify(config, null, 2));
console.log("TrueTick app will open:", url);
