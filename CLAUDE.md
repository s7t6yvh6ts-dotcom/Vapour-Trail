# Working with Ash

- Be blunt and honest. No filler, no hype. The goal is making money: say plainly when something won't.
- UK business, UK English, prices in £.
- **Dark mode on everything.** Every site, page or artifact built for Ash is dark by default.
- Act, don't ask, when the next step is obvious. Ask only when it's really Ash's call (money, legal risk, contacting customers or suppliers).

# The businesses

| Business | What it sells | Where it lives |
|---|---|---|
| Vapour Trail | Refillable vape kits, e-liquids, coils/pods, nicotine pouches (18+) | This repo, plus the pinned "Vapour Trail" artifact on claude.ai |
| Tobacco Direct | Cigarettes, rolling tobacco, papers and filters | claude.ai artifact |
| Faren | Peptide skincare serums | `s7t6yvh6ts-dotcom/FarenPeptides` repo, claude.ai artifact |
| Full Bars | Refurbished phones, trade-ins, repairs (new idea) | `sites/full-bars/` in this repo |
| Chainline Cycles | Refurbished bikes, UK-legal e-bikes, workshop (new idea) | `sites/chainline/` in this repo |

`sites/*/index.html` are the source for their claude.ai artifacts. Edit the file, then republish it to the same artifact URL (listed in `sites/README.md`).

# Rules that can close a business

- **Shopify banned vapes and e-liquids worldwide (July 2026).** Don't build anything nicotine on Shopify. Phones and bikes are fine on Shopify.
- **Online, Stripe, PayPal and Square won't take vapes or tobacco** (Square allows them in person only). Nicotine needs a high-risk merchant account.
- **Vaping Products Duty from 1 October 2026:** £2.20 per 10 ml of e-liquid, nicotine or not. Buy e-liquid and prefilled pods duty-stamped from UK suppliers only. Importing unstamped stock is illegal, and unstamped stock can't be sold after 31 March 2027.
- **Disposable vapes** are illegal to sell in the UK (since 1 June 2025). Refillable, TPD-compliant (2 ml tanks, 10 ml bottles, 20 mg/ml max), MHRA-notified only.
- **Nicotine pouches become 18+ by law on 29 October 2026.** A real online age check (Yoti, AgeChecked, credit-reference) must be live before then, and no parcel lockers. Free samples and big promotional discounts on vapes and pouches become offences the same day.
- **Advertising:** no public posts promoting nicotine vapes, on any social platform. Pouches join the ban on 1 June 2027 (planned). Factual info on our own site is fine.
- **Tobacco** must be UK duty-paid, and cigarettes and rolling tobacco need a UK fiscal mark. Never import it. From 1 January 2027 it's illegal to sell tobacco or cigarette papers to anyone born on or after 1 January 2009, so the age check must check date of birth.
- **Peptides** sold to inject or swallow, or with health claims, are medicines, and selling them unlicensed is a crime. Keep Faren to cosmetic serums with cosmetic claims.
- **Used phones:** check every IMEI on CheckMEND and refuse anything activation-locked. Buying a phone you know or believe is stolen is handling stolen goods, and if it turns out to be stolen the police take it back and the money's gone. Never change an IMEI: that's a crime too.
- **Used bikes:** check every frame number on BikeRegister. **E-bikes:** 250W max, assist cuts out at 15.5 mph, no throttle above walking pace. Never sell derestriction kits. Royal Mail and Parcelforce won't carry e-bikes or their batteries, so they need a specialist courier.
- **Warranties** on phones, repairs and bikes are on top of the customer's legal rights (Consumer Rights Act 2015), and the site must say so.

# Tools

- `tools/margin.py` and `tools/reorder.py`: margin per order and the reorder planner. See `PLAYBOOK.md`.
- Connected on claude.ai: Gmail, Google Calendar, Google Drive, monday.com (Vapour Trail HQ board), Shopify, Canva, Figma, Linear.
