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
- **Stripe, PayPal and Square prohibit vapes and tobacco.** Nicotine needs a high-risk merchant account.
- **Disposable vapes** are illegal to sell in the UK (since 1 June 2025). Refillable, TPD-compliant, MHRA-notified only.
- **Nicotine pouches become 18+ by law on 29 October 2026.** A real online age check (Yoti, AgeChecked, credit-reference) must be live before then.
- **Tobacco** must be UK duty-paid with fiscal marks. Never import it.
- **Peptides** sold for human use are unlicensed medicines. Keep Faren to cosmetic serums with cosmetic claims.
- **Used phones:** check every IMEI on CheckMEND and refuse anything activation-locked. Buying a stolen phone is handling stolen goods.
- **Used bikes:** check every frame number on BikeRegister. **E-bikes:** 250W max, assist cuts out at 15.5 mph, no throttle above walking pace. Never sell derestriction kits.

# Tools

- `tools/margin.py` and `tools/reorder.py` (Vapour Trail branch `claude/jolly-volta-93nljx`): margin per order and the reorder planner. See `PLAYBOOK.md` on that branch.
- `shopify/`: UK policies and the launch checklist for putting Full Bars or Chainline on Shopify.
- Connected on claude.ai: Gmail, Google Calendar, Google Drive, monday.com (Vapour Trail HQ board), Shopify, Canva, Figma, Linear.
