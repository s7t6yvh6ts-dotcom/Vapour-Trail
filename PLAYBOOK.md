# Vapour Trail playbook

To-do list with deadlines: **Vapour Trail HQ** board in monday.com. This file explains the reasoning behind it.

## Shopify has banned vapes

Shopify told US merchants on 23–24 June 2026 to remove all e-cigarettes, e-liquids, pods, coils and refills by 7–8 July, and extended the ban worldwide, UK included, by mid-July. It applies even to MHRA-notified, fully legal products, and stores that don't comply risk termination. Pouches aren't named in the notice, but at least one UK agency reads it as covering every nicotine product. Shopify Payments has never allowed tobacco or e-cigarettes.

1. **Today: export your customers and orders** (Shopify admin → Customers → Export, Orders → Export). If the store gets shut down, the customer list goes with it.
2. **Move vapes to a platform that allows them.** WooCommerce (self-hosted, no blanket ban, cheapest), Swell or Shoplazza. Pair it with a high-risk merchant account (see *Taking payments*).
3. **Don't build anything else on Shopify for nicotine.**


## The dates

| When | What happens | What you do |
|---|---|---|
| **Wed 30 Sep 2026** | Last working day before the holiday in China | Confirm every open order and pay deposits **today** |
| **1 Oct** | — | Export customers and orders from Shopify (backup before any suspension) |
| 1–7 Oct | Golden Week (National Day). Factories and most sales reps are off | Sell what's in stock (below). Reps often still read WeChat, so chase anything unconfirmed |
| 8–10 Oct | Back to work (Sat 10 Oct is a make-up workday) | Chase for dispatch dates and tracking on the 8th |
| ~12–20 Oct | Backlog clears and orders ship | Air freight means UK arrival around late October |
| **29 Oct** | UK law: nicotine pouches become 18+ only | Proper online age checks live before this date |
| **by 1 Dec** | Last safe date for the Chinese New Year order | Order enough to get through to March |
| 30 Jan – 21 Feb 2027 | Chinese New Year (6 Feb). Factories shut, with slowdowns before and after | Nothing moves. If you don't already have stock, you won't get any |

## Message to send suppliers today (WeChat / Alibaba)

> Hi [name], before the National Day holiday please confirm my order: [items + quantities]. I'll pay the deposit today. Please put it first in line when you're back on 8 October and send tracking as soon as it ships. Also, what is your last dispatch date before Chinese New Year 2027?
>
> 您好[名字]，国庆假期前请确认我的订单：[产品 + 数量]。我今天付定金。请10月8日上班后第一时间安排发货，发货后马上发我物流单号。另外，请告诉我2027年春节前最后的发货日期。谢谢！

When they answer the Chinese New Year question, write the date down. It sets your December deadline.

## This week: sell what's in stock (vapes and pouches)

1. **Check how much stock you have first.** Run the reorder planner (below). If a product will run out before the restock lands, don't promote it.
2. **Pouches are a repeat buy, so sell them in multiples.** Postage and card fees eat single-tin orders. With typical UK wholesale costs, one tin can make pennies. Set a minimum order (e.g. 3 tins) or free postage from 5 tins, and keep the bundle discount small (5–10%). Check your real numbers first:
   ```bash
   python3 tools/margin.py --cost 3.80 --price 6.00 --postage 1.55   # use your own numbers
   ```
3. **Vapes: bundle a device with a spare pack of pods or coils.** Accessories carry the margin.
4. **Restock list for out-of-stock lines.** Post: *"Some lines are back late October. DM 'LIST' to be first in line."* That keeps the customer without taking money for stock you haven't got.
5. **Don't take payment for pre-orders with no confirmed ship date.** Refunds and chargebacks cost more than the sale.

### Ready-to-post (Telegram / socials), 18+ only

- **Day 1:** *Pouch bundle is live: 5 tins for £[X], this week only. 18+ only, ID checked. DM or order at [link].*
- **Day 3:** *Kit + spare pods for £[X]. Refillable, UK-compliant. 18+.*
- **Day 5:** *Last few pouch bundles at this price. Restock list is open for everything else: DM 'LIST'.*

## Reorder planner

`tools/reorder.py` works out when each product runs out and the last day to order so the restock lands in time. It allows for Golden Week and Chinese New Year automatically, but only on stock that comes from China.

```bash
cp tools/stock.example.csv stock.csv   # fill in your real numbers
python3 tools/reorder.py stock.csv
```

- `sold_last_30d`: from your shop's sales report (Shopify: Analytics → Reports → Sales by product)
- `lead_time_days`: order to door in a normal month (China air ~21, sea ~45, UK wholesale 1–2)
- `on_order`: units you've ordered that haven't arrived. **Keep this up to date**, or the planner tells you to order the same stock twice
- `origin`: `China` or `UK`. Leave it blank for China
- `--safety-days` (default 7): buffer so stock lands before you run out
- `--cover-days` (default 30): how many days of sales each order should cover

Run it every Monday. Anything marked `LATE - ORDER NOW` or `ORDER THIS WEEK` gets ordered that day: add the quantity to `on_order`, then move it to `on_hand` when it arrives. If the order after this one would run into Chinese New Year, it raises this order's quantity so it lasts through the shutdown.

## Stop waiting on China for pouches and vapes

Nicotine pouches are made in Europe, so there's no reason for them to be stuck behind a Chinese holiday. UK trade wholesalers deliver next day:

- [Wholesale Nicotine Pouches](https://www.wholesalenicotinepouches.co.uk/): free trade account (ZYN, Velo, Pablo, Killa)
- [SnusBlast Wholesale](https://snusblast.co.uk/wholesale/): next day if ordered by 1pm
- [Nico Distribution](https://nicodistribution.com/): takes newer retailers
- [Vape UK Wholesale](https://vapeukwholesale.co.uk/collections/wholesale-nicotine-pouches): next day, £200 minimum (also sells compliant vapes)

Unit cost is higher than buying direct from China. But you restock in 24 hours, the products are genuine branded and UK-legal, and you never sit on dead stock waiting for a holiday to end. Run both prices through `tools/margin.py` before deciding. Check any wholesaler (company number, reviews) before your first order.

## 29 October 2026: the law changes

The **Tobacco and Vapes Act 2026** got Royal Assent on 29 April 2026. From **29 October 2026**:

- It's an offence to sell **nicotine pouches** (and zero-nicotine vapes) to under-18s. Before this, pouches had no legal age limit.
- Trading Standards can issue a £200 on-the-spot fine, and fines go up to £2,500. Repeat offences will cost you your licence once licensing starts.
- **Retail licensing** for tobacco, vapes and nicotine (online sellers included) is coming. Consultation is expected in early 2027, so watch for it.

**Online age checks that actually count:** an "Are you 18?" box on its own isn't enough. You need a real check against an independent source (Yoti facial age estimation, AgeChecked, or a credit-reference check) before dispatch, and "18+, ID on delivery" on the parcel. Get this live **before 29 October**.

Plugins for WooCommerce: [AgeChecked](https://www.agechecked.com/woocommerce-plugin/) (UK-built; the plugin is free and you pay per check), [Yoti](https://developers.yoti.com/age-verification/woocommerce-integration) (selfie age estimation), and [Token of Trust](https://en-gb.wordpress.org/plugins/token-of-trust/).

## Taking payments

Stripe, PayPal, Square and Shopify Payments prohibit vapes. Don't build the business on them. You need a **high-risk merchant account** that approves vape/nicotine in writing. UK brokers include [We Tranxact](https://www.wetranxact.co.uk/e-cig-and-vape-merchant-account/) (Birmingham) and [Merchant Advice Service](https://www.merchantadviceservice.co.uk/high-risk-merchant-accounts/electronic-cigarette-merchant-accounts/). Expect 3–6% fees and a rolling reserve. Put that fee % into `tools/margin.py`.

## What can shut the business down

A missed restock costs you a week of sales. These can close the business:

- **Payments.** Stripe, PayPal and Square list e-cigarettes, vapes and peptides as prohibited or restricted. Accounts get approved at signup and then frozen after review, with funds held 90–180+ days. See *Taking payments* above.
- **Disposable vapes** have been illegal to sell in the UK since 1 June 2025. Sell only refillable, TPD-compliant products: 2 ml tank max, nicotine 20 mg/ml max, notified to the MHRA. "10,000-puff" Alibaba devices are not UK-legal, and Trading Standards seize them.
- **Tobacco** needs UK duty paid, plus fiscal marks on cigarettes and hand-rolling tobacco. Importing from China and reselling without duty means HMRC seizure and penalties. Buy tobacco from a UK duty-paid wholesaler.
- **Peptides** sold for human use are unlicensed medicines under MHRA rules.
- **Age verification** on every order. 18+, checked against an independent source. Legally required for pouches from 29 Oct 2026 (see above).

## Tools and plugins

| What | Status | Use it for |
|---|---|---|
| monday.com | Connected (Pro trial) | **Vapour Trail HQ** board: every task with its deadline |
| Google Calendar | Connected | Reminders on 8 Oct (chase suppliers), 22 Oct (age checks), 1 Dec (CNY order) |
| Gmail / Google Drive | Connected | Supplier emails, backups of the Shopify export |
| Canva | Connected | Promo graphics for pouch bundles |
| Shopify | **Needs reconnecting** | Pull real sales and stock numbers for `tools/reorder.py` while you're still on it |
| Stripe | Half set up | Don't use it for vape or nicotine sales |
| Claude **Small Business** plugin (Anthropic) | Not installed | Inventory planner, restock, cash-flow snapshot, inbox manager, social content, tax prep. Install it from claude.ai → Plugins |
