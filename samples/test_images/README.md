# Test images

All images are **fictional** and generated for testing. "Zenora Bank", "Lumen Trust Bank", the
people, numbers, apps and links are made up. No real logos. Safe to show in the demo video.

Run any image through the app (http://127.0.0.1:8000) or the check scripts.

## Scams (should be high or medium risk)

| File | Scam type |
|---|---|
| `sms_fake_bank_alert.png` | Fake bank SMS: account restricted, verify via `.top` link within 24 hours |
| `sms_delivery_fee_scam.png` | Fake DHL customs fee with a lookalike link |
| `sms_fake_credit_alert.png` | Fake credit alert asking you to confirm/release goods |
| `email_phishing_lookalike_microsoft.png` | Phishing email from `rnicrosoft-support.com` (lookalike letters) |
| `email_ceo_bank_details_change.png` | "CEO" from Gmail: urgent confidential payment to new bank details |
| `chat_romance_money_request.png` | Romance: offshore rig, no video calls, hospital deposit, Bitcoin, secrecy |
| `chat_pig_butchering_invite.png` | Dating match pushing a crypto trading platform |
| `chat_sugar_daddy_gift_card.png` | Sugar daddy: buy a gift card to "prove loyalty" |
| `chat_family_new_number_scam.png` | "Hi Mum, new number", urgent rent, don't call |
| `chat_whatsapp_code_takeover.png` | "I sent you a 6-digit code by mistake" (account takeover) |
| `chat_wrong_transfer_refund.png` | "I sent money by mistake, refund to this other account" |
| `chat_bank_safe_account.png` | Fake fraud desk: move your money to a "safe account" |
| `chat_recovery_scam.png` | Fake recovery agency charging an upfront fee |
| `chat_lottery_prize_fee.png` | Prize win, pay fee by gift card or Bitcoin |
| `chat_task_job_scam.png` | Task job: like videos, "recharge" with USDT first |
| `chat_visa_guarantee_scam.png` | Guaranteed visa with processing fee and fake scarcity |
| `chat_fake_apartment_agent.png` | Agent wants inspection + agency fees before showing the flat |
| `chat_sextortion_threat.png` | Blackmail threat demanding Bitcoin (should add safety advice) |
| `chat_apk_wedding_invite.png` | "Wedding_Invitation.pdf.apk" sent as a document |
| `receipt_edited_fictional_bank.jpg` | Edited receipt: amount in a different font on a blurred patch; date says **Monday** 27 Oct 2026 (it was a Tuesday) |
| `qr_parking_sign.png` | QR code to a fake parking payment site |
| `qr_traffic_fine_scam.png` | QR code to a fake government fine site |

## Normal (should be low risk: checks for false alarms)

| File | What it is |
|---|---|
| `chat_normal_family.png` | Family chat about Sunday lunch |
| `chat_normal_goodnight.png` | "Did you get home safely?" |
| `sms_legit_otp.png` | Real-looking OTP that warns you never to share it (no request) |
| `email_legit_statement.png` | Bank statement notice with no link and no request |
| `receipt_genuine_fictional_bank.png` | Clean receipt (still: confirm money in your own bank app) |
| `qr_legit_cafe_menu.png` | QR code to `https://example.org/menu` |

## Text and link test set

`samples/test_cases.csv` has 59 messages (47 scams across 40+ categories, 12 normal messages,
including real-brand links like paypal.com and amazon.com that must NOT be flagged).
Score TrueTick with `python scripts/evaluate.py` (or `--offline` for the free link checks only).
