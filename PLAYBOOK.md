# Vapour Trail playbook

To-do list with deadlines: **Vapour Trail HQ** board in monday.com. This file explains the reasoning behind it.

## Shopify has banned vapes

Shopify told US merchants on 23–24 June 2026 to remove all e-cigarettes, e-liquids, pods, coils and refills, with or without nicotine, by 7–8 July, and extended the ban outside the US, UK included, by mid-July. It applies even to MHRA-notified, fully legal products, and stores that don't comply risk termination. Pouches aren't in the notice yet. Assume they're next. Shopify Payments doesn't allow tobacco, e-cigarettes or e-liquid.

1. **Today: export your customers and orders** (Shopify admin → Customers → Export, Orders → Export). If the store gets shut down, the customer list goes with it.
2. **Move vapes to a platform that allows them.** WooCommerce (self-hosted and cheapest; the software has no ban, but you can't use WooPayments, WooCommerce Shipping or WooCommerce Tax for vapes), Swell or Shoplazza. Get the platform's OK for vapes and pouches in writing before you move. Pair it with a high-risk merchant account (see *Taking payments*).
3. **Don't build anything else on Shopify for nicotine.**


## The dates

| When | What happens | What you do |
|---|---|---|
| **Wed 30 Sep 2026** | Last working day before the holiday in China | Confirm every open order and pay deposits **today**. Devices, empty pods and coils only (see *1 October 2026: vaping duty starts*) |
| **1 Oct** | Vaping Products Duty and duty stamps start. Tobacco duty goes up | Export customers and orders from Shopify (backup before any suspension). Buy e-liquid and prefilled pods duty-stamped from UK suppliers only |
| 1–7 Oct | Golden Week (National Day). Factories and most sales reps are off | Sell what's in stock (below). Reps often still read WeChat, so chase anything unconfirmed |
| 8–10 Oct | Back to work (Sat 10 Oct is a make-up workday) | Chase for dispatch dates and tracking on the 8th |
| ~12–20 Oct | Backlog clears and orders ship | Air freight means UK arrival around late October. Anything with e-liquid in it and no UK duty stamp gets seized |
| **29 Oct** | UK law: nicotine pouches become 18+ only. Free samples and big promotional discounts on vapes and pouches become offences | Proper online age checks live before this date |
| **by 1 Dec** | Last safe date for the Chinese New Year order | Order enough to get through to March |
| 30 Jan – 21 Feb 2027 | Chinese New Year (Sat 6 Feb). Official holiday dates come out around November; this window allows for factories closing early and reopening late | Nothing moves. If you don't already have stock, you won't get any |
| **31 Mar 2027** | Last day to sell unstamped vaping stock you held before 1 Oct | Sell it through before then |
| **1 Jun 2027** (planned) | Ban on advertising vapes and nicotine products, pouches included | No more pouch promos on social media |

## Message to send suppliers today (WeChat / Alibaba)

**Devices, empty pods and coils only.** From 1 October it's illegal to import e-liquid or prefilled pods without UK duty stamps, and a Chinese factory can't get stamps unless it has an HMRC-approved UK representative. If an open order includes any liquid, take it off the order and buy it from a UK wholesaler instead.

> Hi [name], before the National Day holiday please confirm my order: [items + quantities]. I'll pay the deposit today. Please put it first in line when you're back on 8 October and send tracking as soon as it ships. Also, what is your last dispatch date before Chinese New Year 2027?
>
> 您好[名字]，国庆假期前请确认我的订单：[产品 + 数量]。我今天付定金。请10月8日上班后第一时间安排发货，发货后马上发我物流单号。另外，请告诉我2027年春节前最后的发货日期。谢谢！

When they answer the Chinese New Year question, write the date down. It sets your December deadline.

## This week: sell what's in stock (vapes and pouches)

1. **Check how much stock you have first.** Run the reorder planner (below). If a product will run out before the restock lands, don't promote it.
2. **Pouches are a repeat buy, so sell them in multiples.** Postage and card fees eat single-tin orders. With typical UK wholesale costs, one tin can make pennies. Set a minimum order (e.g. 3 tins) or free postage from 5 tins, and keep the bundle discount small (5–10%). From 29 October, giving nicotine products away or selling them at a big discount to promote them is an offence. Check your real numbers first:
   ```bash
   python3 tools/margin.py --cost 3.80 --price 6.00 --postage 1.55   # use your own numbers
   ```
3. **Vapes: bundle a device with a spare pack of pods or coils.** Accessories carry the margin. List them on your own site and mention them in DMs, not in public posts (see below).
4. **Restock list for out-of-stock lines.** Post: *"Some lines are back late October. DM 'LIST' to be first in line."* That keeps the customer without taking money for stock you haven't got.
5. **Don't take payment for pre-orders with no confirmed ship date.** Refunds and chargebacks cost more than the sale.

### Ready-to-post pouch posts (Telegram / socials), 18+ only

**Never promote vapes in public posts, public Telegram channels included.** Advertising nicotine vapes online is already banned. You're allowed factual product information on your own website, and one-to-one messages with customers. Pouch posts are allowed until the planned ban on all nicotine advertising on 1 June 2027. Only say "this week only" or "last few" if it's true.

- **Day 1:** *Pouch bundle is live: 5 tins for £[X], this week only. 18+ only, ID checked. DM or order at [link].*
- **Day 3:** *New in: [flavour, strength] pouches. 18+ only, ID checked. DM or order at [link].*
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

The big pouch brands (ZYN, Velo, Pablo, Killa) are made in Europe or the US, so there's no reason for them to be stuck behind a Chinese holiday. E-liquid is the same: from 1 October, buy it duty-stamped from UK wholesalers. UK trade wholesalers deliver next day:

- [Wholesale Nicotine Pouches](https://www.wholesalenicotinepouches.co.uk/): free trade account (ZYN, Velo, Pablo, Killa)
- [SnusBlast Wholesale](https://snusblast.co.uk/wholesale/): trade accounts need approval
- [Nico Distribution](https://nicodistribution.com/): takes newer retailers
- [Vape UK Wholesale](https://vapeukwholesale.co.uk/collections/wholesale-nicotine-pouches): Manchester, also sells compliant vapes. Check the minimum order and delivery charge

Unit cost is higher than buying direct from China. But you restock in 24 hours, the products are genuine branded and UK-legal, and you never sit on dead stock waiting for a holiday to end. Run both prices through `tools/margin.py` before deciding. Check any wholesaler (company number, reviews) before your first order.

## 1 October 2026: vaping duty starts

- **Vaping Products Duty** is £2.20 per 10 ml of vaping liquid, with or without nicotine. That covers bottles, shortfills, pods, cartridges and prefilled devices. Empty devices, empty pods and coils aren't taxed.
- Duty-paid products carry a **UK vaping duty stamp**. If you only buy duty-paid stock from UK suppliers, you don't need HMRC approval. Check new stock has stamps, and keep the invoices.
- Unstamped stock you already hold can be sold until **31 March 2027**. Selling it after that is an offence.
- **Don't import e-liquid or prefilled pods yourself.** From 1 October it's illegal to bring them in without stamps, unless they go into an HMRC-approved duty warehouse. Shipments get seized.
- Tobacco duty goes up the same day: RPI plus 2 points, plus £2.20 per 100 cigarettes or per 50 g of other tobacco.
- UK wholesale prices will include the duty, so recheck your margins. If a quote leaves it out, add it with `--excise` in `tools/margin.py`: £2.20 for a 10 ml bottle, £0.88 for a 2-pack of 2 ml pods.

Source: [HMRC, handling wholesale or retail vaping products](https://www.gov.uk/guidance/handling-wholesale-or-retail-vaping-products-in-the-uk).

## 29 October 2026: the law changes

The **Tobacco and Vapes Act 2026** got Royal Assent on 29 April 2026. From **29 October 2026**:

- It's an offence to sell **nicotine pouches** (and zero-nicotine vapes) to under-18s, online included. Before this, pouches had no legal age limit.
- It's also an offence to give vaping or nicotine products away, or sell them at a substantial discount, to promote them. A 5–10% bundle deal is unlikely to count. Free samples do.
- Trading Standards can issue a £200 fixed penalty (28 days to pay), and a court can fine up to £2,500. Three offences in two years can get you banned from selling these products for up to 12 months.
- **Retail licensing** for tobacco, vape and nicotine sellers (online included) is coming in England, Wales and Northern Ireland. There's no date yet; trade press expects a consultation in 2027.

Source: [DHSC, selling vaping and nicotine products](https://www.gov.uk/guidance/selling-vaping-and-nicotine-products).

**Online age checks that actually count:** an "Are you 18?" box on its own isn't enough. You need a real check against an independent source (Yoti facial age estimation, AgeChecked, or a credit-reference check) before dispatch, and "18+, ID on delivery" on the parcel. Never deliver to parcel lockers. Get this live **before 29 October**. If you're based in Scotland, check the Scottish retailer register rules too.

Plugins for WooCommerce: [AgeChecked](https://www.agechecked.com/woocommerce-plugin/) (UK-built; the plugin is free and you pay per check), [Yoti](https://developers.yoti.com/age-verification/woocommerce-integration) (selfie age estimation), and [Token of Trust](https://en-gb.wordpress.org/plugins/token-of-trust/).

**Also coming:**

- **1 January 2027:** it becomes illegal to sell tobacco or cigarette papers to anyone born on or after 1 January 2009. Age checks for tobacco must check the date of birth, not just 18+.
- **1 June 2027 (planned):** a ban on advertising vaping and nicotine products, pouches included, across all media including social. Factual information on your own site stays allowed.

## Taking payments

For online vape and nicotine sales, don't use Stripe, PayPal, Square or Shopify Payments. Stripe restricts them, PayPal bans them without prior written approval, Square only takes them in person, and Shopify Payments bans them. You need a **high-risk merchant account** that approves vape/nicotine in writing. UK brokers include [We Tranxact](https://www.wetranxact.co.uk/e-cig-and-vape-merchant-account/) (Birmingham) and [Merchant Advice Service](https://www.merchantadviceservice.co.uk/high-risk-merchant-accounts/electronic-cigarette-merchant-accounts/). Brokers quote around 3–6% plus a rolling reserve; get real quotes. Put the fee % into `tools/margin.py --fee`.

## What can shut the business down

A missed restock costs you a week of sales. These can close the business:

- **Payments.** Online, Stripe restricts vapes and tobacco, PayPal bans them without written approval, and Square only takes them in person. Stripe also restricts peptides. Accounts get approved at signup and then frozen after review, and PayPal can hold your money for up to 180 days. See *Taking payments* above.
- **Vaping duty.** From 1 October 2026, e-liquid and prefilled pods need UK duty stamps. Importing unstamped stock gets it seized, and selling unstamped stock after 31 March 2027 is an offence. See *1 October 2026: vaping duty starts* above.
- **Disposable vapes** have been illegal to sell in the UK since 1 June 2025. Sell only refillable, TPD-compliant products: 2 ml tank max, 10 ml refill bottles max, nicotine 20 mg/ml max, and on the MHRA's published list before you sell them. If you import a device yourself, you're the producer and must notify it to the MHRA. "10,000-puff" Alibaba devices are not UK-legal, and Trading Standards seize them.
- **Advertising.** Public posts promoting nicotine vapes are already banned, and the ban covers pouches from 1 June 2027 (planned).
- **Tobacco** needs UK duty paid, plus fiscal marks on cigarettes and hand-rolling tobacco. Importing from China and reselling without duty means HMRC seizure and penalties. Buy tobacco from a UK duty-paid wholesaler. From 1 January 2027, no tobacco or cigarette papers to anyone born on or after 1 January 2009.
- **Peptides** sold to inject or swallow, or with health claims, are medicines, and selling them without a licence is a crime. Skincare peptides with cosmetic claims only are cosmetics.
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
