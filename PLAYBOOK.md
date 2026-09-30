# Vapour Trail: Golden Week and Chinese New Year playbook

## The dates

| When | What happens | What you do |
|---|---|---|
| **Wed 30 Sep 2026** | Last working day before the holiday in China | Confirm every open order and pay deposits **today** |
| 1–7 Oct | Golden Week (National Day). Factories and most sales reps are off | Sell what's in stock (below). Reps often still read WeChat, so chase anything unconfirmed |
| 8–10 Oct | Back to work (Sat 10 Oct is a make-up workday) | Chase for dispatch dates and tracking on the 8th |
| ~12–20 Oct | Backlog clears and orders ship | Air freight means UK arrival around late October |
| **by 1 Dec** | Last safe date for the Chinese New Year order | Order enough to get through to March |
| 30 Jan – 21 Feb 2027 | Chinese New Year (6 Feb). Factories shut, with slowdowns before and after | Nothing moves. If you don't already have stock, you won't get any |

## Message to send suppliers today (WeChat / Alibaba)

> Hi [name], before the National Day holiday please confirm my order: [items + quantities]. I'll pay the deposit today. Please put it first in line when you're back on 8 October and send tracking as soon as it ships. Also, what is your last dispatch date before Chinese New Year 2027?
>
> 您好[名字]，国庆假期前请确认我的订单：[产品 + 数量]。我今天付定金。请10月8日上班后第一时间安排发货，发货后马上发我物流单号。另外，请告诉我2027年春节前最后的发货日期。谢谢！

When they answer the Chinese New Year question, write the date down. It sets your December deadline.

## This week: sell what's in stock (vapes and pouches)

1. **Check how much stock you have first.** Run the reorder planner (below). If a product will run out before the restock lands, don't promote it.
2. **Pouches are a repeat buy, so sell them in multiples.** Offer a 5-tin bundle at 10–15% under the single-tin price. That raises order value without selling below cost.
3. **Vapes: bundle a device with a spare pack of pods or coils.** Accessories carry the margin.
4. **Restock list for out-of-stock lines.** Post: *"Some lines are back late October. DM 'LIST' to be first in line."* That keeps the customer without taking money for stock you haven't got.
5. **Don't take payment for pre-orders with no confirmed ship date.** Refunds and chargebacks cost more than the sale.

### Ready-to-post (Telegram / socials), 18+ only

- **Day 1:** *Pouch bundle is live: 5 tins for £[X], this week only. 18+ only, ID checked. DM or order at [link].*
- **Day 3:** *Kit + spare pods for £[X]. Refillable, UK-compliant. 18+.*
- **Day 5:** *Last few pouch bundles at this price. Restock list is open for everything else: DM 'LIST'.*

## Reorder planner

`tools/reorder.py` works out when each product runs out and the last day to order so the restock lands in time. It allows for Golden Week and Chinese New Year automatically.

```bash
cp tools/stock.example.csv stock.csv   # fill in your real numbers
python3 tools/reorder.py stock.csv
```

- `sold_last_30d`: from Shopify, Analytics → Reports → Sales by product
- `lead_time_days`: order to door in a normal month (air ~21, sea ~45)
- `--safety-days` (default 7): buffer so stock lands before you run out
- `--cover-days` (default 30): how many days of sales each order should cover

Run it every Monday. Anything marked `LATE - ORDER NOW` or `ORDER THIS WEEK` gets ordered that day. Before Chinese New Year it automatically raises the order quantity so the December order lasts through the shutdown.

## What can shut the business down

A missed restock costs you a week of sales. These can close the business:

- **Payments.** Stripe, PayPal and Square list e-cigarettes, vapes and peptides as prohibited or restricted. Accounts get approved at signup and then frozen after review, with funds held 90–180+ days. Use a high-risk merchant account that approves vape/nicotine in writing *before* you take volume.
- **Disposable vapes** have been illegal to sell in the UK since 1 June 2025. Sell only refillable, TPD-compliant products: 2 ml tank max, nicotine 20 mg/ml max, notified to the MHRA. "10,000-puff" Alibaba devices are not UK-legal, and Trading Standards seize them.
- **Tobacco** needs UK duty paid, plus fiscal marks on cigarettes and hand-rolling tobacco. Importing from China and reselling without duty means HMRC seizure and penalties. Buy tobacco from a UK duty-paid wholesaler.
- **Peptides** sold for human use are unlicensed medicines under MHRA rules.
- **Age verification** on every order. 18+, checked.
