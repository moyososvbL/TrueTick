// Adds the permissions TrueTick needs: microphone (Live Call Guard, voice notes) and camera (QR scanner).
import { readFileSync, writeFileSync } from "node:fs";

const path = "android/app/src/main/AndroidManifest.xml";
let xml = readFileSync(path, "utf8");
const perms = [
  "android.permission.RECORD_AUDIO",
  "android.permission.MODIFY_AUDIO_SETTINGS",
  "android.permission.CAMERA",
];
for (const p of perms) {
  if (!xml.includes(`"${p}"`)) xml = xml.replace("</manifest>", `    <uses-permission android:name="${p}" />\n</manifest>`);
}
if (!xml.includes("android.hardware.camera")) {
  xml = xml.replace("</manifest>", `    <uses-feature android:name="android.hardware.camera" android:required="false" />\n</manifest>`);
}
writeFileSync(path, xml);
console.log("Permissions added:", perms.join(", "));
