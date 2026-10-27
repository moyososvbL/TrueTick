# Test images

All images are **fictional** and generated for testing: "Zenora Bank", "Lumen Trust Bank",
the names, numbers and links are made up. No real people, brands or logos.

| File | What it is | Expected TrueTick result |
|---|---|---|
| `sms_fake_bank_alert.png` | SMS from "ZENORA-BNK": account restricted, verify via a `.top` link within 24 hours | **High risk**: fake bank alert, phishing link, urgency |
| `chat_romance_money_request.png` | WhatsApp-style chat: offshore rig, no video calls, daughter in hospital, $3,000 by Bitcoin, "don't tell anyone" | **High risk**: romance scam, money request stage |
| `receipt_genuine_fictional_bank.png` | Clean transfer receipt for ₦250,000.00 | **Low/medium**: no editing signs, but "confirm in your own bank app" |
| `receipt_edited_fictional_bank.jpg` | Same receipt edited: amount changed to ₦2,500,000.00 in a different font on a slightly different, blurred patch; date says **Monday** 27 Oct 2026 (it was a Tuesday) | **High risk**: edited receipt (font mismatch, pasted patch, wrong weekday) |
| `qr_parking_sign.png` | "City Parking, scan to pay" sign with a QR code to `citypark-pay.top` | **Medium/high**: QR leads to a suspicious payment page |
| `chat_normal_family.png` | Normal family chat about Sunday lunch | **Low risk** (checks for false alarms) |
