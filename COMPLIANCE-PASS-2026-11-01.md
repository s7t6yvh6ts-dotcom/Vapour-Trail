# Compliance pass: Vapour Trail and Tobacco Direct (1 Nov 2026)

Checked against the rules in `CLAUDE.md`. Sources read: the live claude.ai artifacts (Vapour Trail `UjqHzmyA76mscTut9C8VbD`, Tobacco Direct `1AdMkyBfhGzixrhgnusFF5`) and the repo's `store/` pages.

## Fixed

- **Vapour Trail, checkout payment note** (live artifact, now version 9). It said mainstream gateways accept vape and pouch merchants. The rules say Stripe, PayPal, Square and Shopify Payments won't. The note now says so and asks for a high-risk merchant account. Verified: the live `data.js` has the new text.
- **`store/LAUNCH.md` section 5 and `PLAYBOOK.md` dates table.** Both treated 29 October as a future date. It passed on 29 October, so the pouch age check is already the law. Both now say so and say to stop taking pouch orders until the check is live.

## Checked and fine

- Tobacco Direct price list matches the catalogue. The lowest pack is £13.95 (Sterling Dual), so the sleeve is £139.50. The lowest 30g pouch is £23.60 (Cutters Choice).
- Tobacco Direct 2027 rule (born on or after 1 January 2009) is stated correctly on the gate, FAQ and footer.
- Vapour Trail products, delivery prices and the 18+ wording match the rules. Vape strengths are at or under 20mg/ml and the bottles are 10ml.

## Not fixed: needs your decision

1. **Age checks are self-declared, but the copy says they're verified.** Vapour Trail's delivery page says "Your date of birth is verified at checkout". Tobacco Direct says the same at checkout. Both owner notes say a real provider (Yoti, GBG or Experian) must be connected first. The shop is a prototype with simulated payment, so nothing takes real orders yet. Before it does, a provider needs connecting, and that costs money, so it's your call.
2. **Pouch bundles are discounted.** "Value pack" is 10% off five tins, and the e-liquid triples are about 8% off. The playbook says 5–10% shouldn't count as a substantial discount. Check with Trading Standards if you want certainty.
3. **Vapour Trail's footer and the public Shop owner login link.** The footer links to the Shop owner login and the pre-launch checklist. Remove them before launch.
4. **Tobacco Direct: Rothmans Blue is listed as a pack of 24.** The card and "by the pack" copy say 20. Check the product data.
5. **Tobacco Direct: UK fiscal marks.** The rules need UK fiscal marks on cigarettes and rolling tobacco. Nothing in the catalogue or copy mentions them. Confirm with the supplier.
6. **Vapour Trail FAQ: "The name on the ID does not have to match the order."** That weakens the ID check. Consider requiring the person who signs to be the person who ordered, or at least someone at the address who is 18+.
