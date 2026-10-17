# Chainline Cycles: go-live checklist

As of 14 October 2026 the site (`sites/chainline/index.html`, one page) is a **preview**, published only as a claude.ai artifact. It's kept out of search engines, it says "Prototype" in the banner and the footer, and it can't take orders, bookings or bikes: checkout and the two forms send nothing, and say so. The stock, the e-bike courier price, the business details and several policy timings are [placeholders].

Work down this page in order. Nothing here is done unless it says so. Where something is a legal or tax judgement, it's flagged for an adviser: this checklist doesn't decide it.

## Launch order

1. Make the decisions in [section 1](#1-decide-first-your-call), with your accountant and advisers where marked.
2. Set up the business and accounts ([section 2](#2-business-and-accounts)).
3. Fill every placeholder ([section 3](#3-fill-every-placeholder)).
4. Buy, check and list the real bikes ([section 4](#4-every-bike-before-its-listed)).
5. Set up checkout: Shopify recommended ([section 5](#5-checkout-shopify-recommended-or-stripe)).
6. Book the couriers, including a specialist for e-bikes ([section 6](#6-couriers-e-bikes-and-lithium-batteries)).
7. Get the adviser answers in [section 7](#7-for-your-advisers-not-decided-here).
8. Set up the workshop paperwork ([section 8](#8-the-workshop)).
9. Choose a web host ([section 9](#9-hosting-and-deploying)).
10. Launch day: flip the preview switches, deploy and check ([section 10](#10-preview-to-live-switches)).
11. Put a test order through, then a real one ([section 11](#11-test-order)).

The files in this folder are listed at the end.

## 1. Decide first (your call)

From the 14 October 2026 legal audit, plus what the build left open. Where the page already says something, it's noted, so you know what you're changing.

1. **Warranty scope.** The page now uses **Option A: the whole bike**, parts and labour, for 3 months. That's what the old promise strip already said ("Parts and labour"), and under CRA s30(3) a warranty binds on its advertising too, so it was the safe reading. If you want **Option B (only what the workshop fitted or adjusted)**, change the promise strip, the FAQ answer, the `#warranty` block, both order emails and the CSV builder's "3-month warranty on the whole bike" together; `check_site.py` checks the strip and the FAQ say the same thing. Also decide:
   - whether to add exclusions the old page didn't have (normal wear to chain and cables; faults from repairs by someone else). I didn't add them, because they'd narrow the warranty you'd already advertised;
   - a battery threshold (for example "health below [70]%"). Not on the page yet;
   - **who pays to collect and return a delivered bike for a warranty claim that isn't a Consumer Rights Act fault**, and what it costs. The warranty's "How to claim" (on the page and in both emails) has the placeholder `[who pays to collect and return the bike, and what it costs]`; fill it with your answer (for example free, or a price each way, or "bring it in"). For a CRA fault the page already says you pay, because the law says so.
   - If you change the warranty's length, change it everywhere it's stated (the strip, the cards, the FAQ, the small print, the meta description, both emails and the CSV builder) and in `check_site.py`'s RULES, which pin it at 3 months.
2. **E-bike delivery and return prices.** The page shows `£[e-bike delivery price]` and `£[e-bike collection price]`, and the basket says "+ e-bike courier" instead of a total while the price isn't set. Get courier quotes (section 6), then set `"ebike"` in the bike data and fill both placeholders. Also decide which areas you don't deliver to or charge more for (the Highlands, the islands): the `[list any areas…]` placeholder in Delivery. `check_site.py` fails if the e-bike price on the page, the cards, the emails and the CSV don't all agree with `"ebike"`.
3. **Checkout: Shopify or Stripe.** I'd pick Shopify (section 5). Also: when the contract is made. The terms say on your acceptance email, within [one working day]; keep that, or rewrite terms clause 3, the FAQ and both emails together if you want it made at checkout.
4. **Workshop bookings.** Done on the page as the audit recommended: the form sends a **request, not a booking**, nothing is paid online, you phone to confirm, and the contract is made at the counter (so no 14-day cancellation right applies). If you ever take payment or deposits online, the Consumer Contracts Regulations apply to the booking (express-request wording, a confirmation email); ask before doing it.
5. **Prices to set.** The tube price (`£[tube price]`), and whether workshop consumables are included: the bracketed sentence under the service list. Keep it (remove the brackets) or delete it. "Include VAT where applicable" is true either way.
6. **Accountant:** VAT registration (compulsory past £90,000 turnover in a rolling 12 months), the VAT margin scheme for bikes bought from the public, the stock book and self-billed purchase invoices, and `Charge tax` in the CSV (section 7).
7. **WEEE and waste batteries** (section 7).
8. **Dangerous goods:** carrying and storing used and waste lithium batteries, and whether you need a dangerous goods safety adviser (section 6).
9. **Second-hand dealer licensing:** ask your council (section 7).
10. **Real photos or drawings.** The page says the drawings are illustrations, not photos, and to ask for photos. Real photos are strongly advised for used bikes, and Google won't show product results without an image.
11. **Uncollected workshop bikes:** the `[14]` days and `[3 months]` in Workshop terms, and the notice process. Have a solicitor check it (Torts (Interference with Goods) Act 1977 Sch 1; Scotland differs).
12. **Throttles: decided, no fast throttles.** As CLAUDE.md says, the page now states that every e-bike you sell has no throttle, or one that stops at walking pace (6 km/h), and that you don't sell any e-bike with a faster throttle, even a type-approved one or a pre-2016 twist-and-go (the page still explains those, as facts). `check_site.py` fails if that wording changes. Still your call: will the workshop *service* e-bikes that aren't road-legal (not EAPCs)?
13. **Company or sole trader**, and whether the registered office is the workshop.
14. **Insurance** (section 7).
15. **Order email:** send the full frame number (the `.md` template does) and offer to register sold bikes to buyers on BikeRegister (needs their consent)?
16. **Paying sellers:** the page says bank transfer, never cash (done), `[within one working day]` of the checks (your call).
17. **Battery tests:** the method and tools (the maker's diagnostic tool, or a discharge tester) behind each battery-health figure. The page defines health as a share of rated capacity, so the test has to measure that.
18. **ADR (alternative dispute resolution):** the DMCC Act 2024's new regime replaced the 2015 regulations on 6 April 2026. The audit couldn't confirm what traders must now tell customers: ask before launch whether to name a scheme.
19. **An extra satisfaction guarantee** (optional). Full Bars offers 30 days; Chainline offers the statutory 14.
20. **Policy timings the page brackets:** dispatch `[3]` working days, transit `[2 to 3]`, ready for collection `[2]`, acceptance email `[one working day]`, free check-up within `[8]` weeks, server logs kept `[30]` days. The numbers in brackets are suggestions; confirm or change each.
21. **Retention periods** in the privacy notice (six years for sales and purchase records, two years for bookings and enquiries) are Full Bars' and the audit's. Confirm them with your accountant.
22. **Bike names to check against the real bikes:** the Trek is now "FX 2 Disc" (the audit says that was its 2021 name); check the Cube Nuroad's groupset (2x8 or 2x9) and size band, the Carrera Crossfire-E's gears, and which Islabikes Beinn 20 (Small or Large). All the stock is placeholder anyway (section 4).
23. **Northern Ireland: sell there from day one, or not yet?** Bikes sold into Northern Ireland come under the EU's product safety rules, not GB's, and need a responsible operator in NI or the EU (section 7). Either get that advice and set it up, or don't deliver to NI at first: fill `[list any areas…]` with "We don't deliver to Northern Ireland yet" and leave NI out of Shopify's shipping zone.

**Prices: no inconsistencies found, and none changed.** `check_site.py` now checks every price that appears more than once, everywhere it appears: each bike (data, card, structured data, CSV and every row of the example ticket), each service and the tube price (price list and booking form), UK delivery, the e-bike courier, and both return-collection prices, on the page, in both order emails and in the CSV. A [placeholder] counts as a value: the same placeholder everywhere passes, a mix of placeholder and price fails. It also pins the rules that can close the business: 250W, 15.5 mph, 14+, the walking-pace throttle rule, no derestriction kits, the 3-month warranty and the 14-day cancellation wording.

## 2. Business and accounts

| Set up | Why |
|---|---|
| Company (or sole trader) and a business bank account | Fills the trader details (section 3). Sole trader: "Chainline Cycles is run by [your name], [Workshop address]." and delete the company clauses, in the footer, terms clause 1, the warranty, the cancellation form, the privacy notice and both emails. |
| ICO data protection fee | You'll hold customer and seller data, including ID checks for bikes you buy. Tier 1 is £52 a year (£47 by direct debit). Put the number in the privacy notice. (The regulator became the Information Commission on 30 September 2026 but still uses the name ICO.) |
| Domain | Needed for the canonical link, the social tags, the structured data's `url` and the email address (section 10). |
| Web host with HTTPS whose terms allow a shop | Section 9. |
| Inbox on the domain, with SPF, DKIM and DMARC | The workshop email on the page and in both order emails. |
| A geographic (01/02) or 03 phone number | Never 084 or 087: customer lines must be basic rate (CCR reg 41). |
| BikeRegister | BikeChecker on every frame number you buy or sell. Ask whether there's a trade account. Consider a second stolen-bike check too, because BikeChecker only finds bikes registered as stolen on BikeRegister. |
| Shopify (or Stripe) | Section 5. |
| A bike courier, and a specialist e-bike courier that accepts UN3171 | Section 6. Cover at least the dearest bike (the Raleigh Motus Tour is listed at £1,149). |
| Registered waste carrier and a battery take-back route | Check it on the Environment Agency register (SEPA or NRW in Scotland or Wales). |
| Battery test tools | Decision 17. |
| Accountant, and the advisers in section 7 | |

## 3. Fill every placeholder

`python3 launch/chainline/check_site.py` lists every one still on the page, with a count. `--launch` fails until they're all gone. The customer's own blanks in the cancellation form (`[bike, size, ticket number]`, `[date]`, `[your name]`, `[your address]`) stay: `check_site.py` never counts them. Fill the same values in both order emails.

| Placeholder | Where on the page | What to put |
|---|---|---|
| `[Company name]` | Footer, terms 1, warranty, cancellation form, privacy, structured data (`legalName`) | Legal name, or your own name if a sole trader |
| `[England and Wales]` | Footer, terms 1 | Where the company is registered. Delete if a sole trader. |
| `[Company number]` | Footer, terms 1 | Companies House number. Delete if a sole trader. |
| `[Registered office address]` | Footer, terms 1 | Registered office |
| `[Workshop address]` | Footer, terms 1, warranty, delivery (collection), cancellation form, privacy | A real postal address. Customers need it to cancel, collect and complain; a PO box isn't enough. |
| `[Workshop street address]`, `[Town]`, `[Postcode]` | Structured data (`#ld-store`, in the head) | The same address, split up |
| `[VAT number, if registered]` | Footer, terms 1, structured data (`vatID`) | Or delete the sentence (and `vatID`) if not registered |
| `[Workshop email]` | Footer (link text **and** `mailto:`), terms 1, warranty, cancellation form, privacy, no-JS notes, structured data | The inbox (section 2) |
| `[Phone number]` | Footer (link text **and** `tel:`; use `tel:+44…`, for example `href="tel:+441914960000">0191 496 0000</a>`), terms 1, warranty, no-JS note, structured data | Section 2. `check_site.py` treats +44 and a leading 0 as the same and ignores spaces, so the link must dial exactly the number it shows. |
| `[Opening hours]` | Footer, booking form hint, delivery (collection), structured data | Your hours. In the structured data use schema.org's format, for example `Mo-Sa 09:00-17:30`. |
| `[Website address]` | Structured data (`url`) | `https://www.your-domain/` |
| `[ICO registration number]` | Privacy | Section 2 |
| `[payment provider]` | Terms 4, privacy (twice), cookies | "Shopify Payments" or "Stripe" |
| `[payment methods]` | Basket note | The cards and wallets your checkout takes |
| `[the law of England and Wales]`, `[the courts of England and Wales]` | Terms 11 | Ask your solicitor if you're not in England or Wales |
| `[launch date]` | Terms, "Last updated" | The date the terms take effect. Save a dated PDF (see the end of `order-confirmation-email.md`). |
| `[one working day]`, `[within one working day]` | Terms 3 (acceptance email), selling terms (paying sellers) | Decisions 3 and 16 |
| `[3]`, `[2 to 3]`, `[2]` | Delivery (dispatch, transit, ready to collect) | Decision 20 |
| `[8]` | Promise strip (free check-up) | Decision 20 |
| `[30]` | Privacy (server log retention) | Your host's log period (section 9) |
| `[14]`, `[3 months]` | Workshop terms (uncollected bikes) | Decision 11 |
| `[e-bike delivery price]` | Terms 4, delivery, FAQ, the e-bike cards and the basket (from the data) | Decision 2. Set `"ebike": 39` (or whatever) in the bike data, run `sync_bikes.py`, then replace the text in terms 4, Delivery and the FAQ. |
| `[e-bike collection price]` | Cancelling an order, FAQ, both emails | Decision 2 |
| `[list any areas you don't deliver to, or charge more for]` | Delivery | Decision 2. Delete it if you deliver everywhere in the UK at the same price. |
| `[tube price]` | Puncture repair (service list and booking form) | Decision 5 |
| `[Workshop consumables, … are included.]` | Under the service list | Decision 5: keep it without the brackets, or delete it |
| `[check date]` | The hero bike's `"checked"` in the bike data (shown on the example workshop ticket) | The date that bike's frame number was checked on BikeRegister. The ticket must describe a real bike that's in stock. |
| `[who pays to collect and return the bike, and what it costs]` | Warranty "How to claim", both emails | Decision 1 |
| `[wheels]`, `[brakes]`, `[condition notes]`, `[motor maker and power]`, `[rated Wh]`, `[test date]` | Each bike's details, in the bike data (they show on the cards and in the CSV) | The real bike's details (section 4) |
| `"ebike": null` | The bike data (`#shop-data`) | The e-bike courier price in pounds (decision 2) |

## 4. Every bike, before it's listed

The ten bikes on the page are placeholder stock. Replace them with real ones. Record each step on the bike's workshop ticket and keep it for six years.

1. **Buying it.** The seller's photo ID and proof of ownership, recorded. A signed seller declaration: 18 or over, owns it outright, no finance owed, not on Cycle to Work or other hire, not reported lost or stolen. The BikeChecker result and its date. Refuse a frame number that's filed, re-stamped or missing. If it's listed as stolen, don't buy it, and call the police on 101. Pay by bank transfer, never cash. Make a stock-book entry if the accountant puts you on the margin scheme.
2. **Recall check** against the maker's notices and gov.uk's product recalls and alerts.
3. **The 30-point check**, done and signed. The card's tag (what was fitted or tested) must match the ticket.
4. **E-bikes only:**
   - a plate showing the maker, the power (250W or less), and the voltage or the top assisted speed;
   - assistance cuts out at 15.5 mph;
   - no throttle that works above walking pace (6 km/h) without pedalling;
   - no "off-road" or "unlimited" mode, and the speed limit not tampered with;
   - the capacity test recorded: method, date, measured Wh against the rated Wh on the label;
   - the maker's own charger present;
   - no swelling, cracks or water damage. A damaged battery is never sold or shipped.
5. **Listing facts:** the maker's exact model name, year, frame size, wheels, gears, brakes, honest condition notes and real photos; for e-bikes, the motor and the battery's rated Wh.

**Putting a bike on the site, or taking one off when it sells.** The bike data block near the end of `index.html` (`<script type="application/json" id="shop-data">`) is the only place a bike is typed. One line per bike: `id` (lower case and hyphens; it becomes the Shopify handle), `no` (the ticket number), `make`, `model`, `year`, `type` (road, hybrid, gravel, ebike, folding or kids), `size`, `band` (the size filter: XS to XXL, ONE, or K14 to K26), `gears`, `specs` (any other details, as `["Label", "value"]` pairs, ending with Condition), `tagLabel` and `tag` (what the workshop fitted or tested), and `price` (whole pounds). At the top, `"heroTicket"` names the bike the example workshop ticket describes; that bike's `"checked"` (its BikeRegister check date) and `"ticketRows"` (extra workshop notes, as pairs) appear only on the ticket. The hero drawing is of that Trek (its 17.5in frame and 700x35c tyre labels): if you point the ticket at another bike, change the drawing's title (`check_site.py` checks it names the bike) and its labels. Then, from the repo root:

```
python3 launch/chainline/sync_bikes.py          # writes the cards, the structured data, the count and the whole example ticket
python3 launch/chainline/build_shopify_csv.py   # only before the first Shopify import
python3 launch/chainline/check_site.py          # must end with no FAIL
```

`sync_bikes.py` stops if `"heroTicket"` names a bike that's gone: point it at one that's in stock. After launch, never re-import the CSV to change stock or prices: change them in Shopify admin and on the site in the same sitting (section 5).

## 5. Checkout: Shopify (recommended) or Stripe

**Shopify is fine for bikes.** Its ban is on vapes and e-liquids, not bikes (CLAUDE.md). Every bike is a one-off, and Shopify counts stock, so with stock 1 and "don't continue selling" the same bike can never be sold twice. Stripe Payment Links can't take a basket of several bikes, and a link doesn't know when the bike has sold on the site.

1. **Settings.** UK store, GBP. Prices must **include** tax, or Shopify adds 20% on top. Ask the accountant how to set `Charge tax` (the CSV says TRUE). Under the margin scheme Shopify can't work out the VAT, so don't file returns from Shopify's tax figures.
2. **Prove the format on one product first.** Make one test product by hand (one variant, draft, track quantity, quantity 1, don't continue selling, physical product). Download Shopify's sample CSV (Products > Import) and run `python3 launch/chainline/validate_shopify_csv.py --template <the sample>`. Every line must say PASS (or NOTE for placeholders). Delete the test product.
3. **Import `products-shopify.csv`** once the placeholders are filled (`validate_shopify_csv.py --launch` must pass). You should get 10 draft products (one per bike), stock 1 each, not on the Online Store, each with a 1 kg shipping weight (step 4). Pick each product's category in admin (Bicycles, or the e-bike category Shopify offers): the CSV leaves it blank on purpose. Add real photos.
3a. **Make the bikes buyable, before you wire the site's basket to Shopify (section 10, step 7).** The import leaves every bike a draft, and a cart link to a draft or unpublished product fails. In Products, select every bike, set the status to **Active**, and under **Sales channels** make them available on **Online Store** (or on whichever channel your cart links go through). Then open `https://<your shop>/cart/<one bike's variant id>:1` in a private window and check it reaches checkout with that bike at the site's price.
4. **Shipping.**
   - **Local pickup** at the workshop, free.
   - **UK delivery, £39 per bike, set up so Shopify charges exactly what the site's basket adds up.** Shopify's built-in rates are per order, not per item. So every bike in the CSV carries the same nominal shipping weight, 1 kg. That isn't its real weight: it's a counter (`validate_shopify_csv.py` checks every bike has it). In Settings > Shipping and delivery, in the general profile's UK zone, add rates **based on order weight**: 0 to 1 kg £39 ("UK delivery, 1 bike"), 1.01 to 2 kg £78, 2.01 to 3 kg £117, 3.01 to 4 kg £156, and so on, up to the most bikes you'd expect in one order. Don't change a bike's weight in admin. If a courier ever prices by real weight, put real weights in and redo these rates and the site's basket together.
   - **A separate shipping profile for e-bikes** (they're tagged `Specialist courier` in the CSV): move the e-bikes into it, and give its UK zone the same 1 kg bands at the e-bike courier's price (1 e-bike, 2 e-bikes, …), once you have it (decision 2). With bikes from both profiles in one order, Shopify adds the two profiles' rates together, which is what the site's basket does (bikes × £39 + e-bikes × the e-bike price). Prove it in the test order (section 11).
   - UK only, and exclude any areas you decided to (decision 2).
5. **Policies.** Put the trader details in Store details. Paste the terms, privacy notice, delivery and returns, and cancellation sections into Settings > Policies.
6. **Cookies.** The site promises no tracking, but Shopify sets its own cookies: turn on Shopify's cookie banner for UK visitors, and add no marketing pixels. The site's privacy notice already says checkout uses its own cookies.
7. **Honest selling (DMCC Act 2024).** No compare-at prices unless they're real previous prices, no countdown or "selling fast" apps, no review apps until you have real reviews.
8. **Theme.** Dark, to match the site.
9. **Order confirmation email** (the law requires it; `order-confirmation-email.md` explains). Fill the [placeholders] in `order-confirmation-email.html`, paste it into Settings > Notifications > Order confirmation (Edit code, replacing the whole template), and check `delivery_method` and `line.product.type` in Preview. Within [one working day] of every order, send the `.md` email with the bike's frame number, ticket and battery details: that's the acceptance.
10. **Connect the site's basket to Shopify** (section 10, step 7).

**Stripe instead (not recommended).** One Payment Link per bike with "Limit the number of payments" set to 1, quantity fixed at 1, a shipping rate for collection (free) and for UK delivery, the UK shipping address collected, and "require terms of service" on. The site's basket would have to go: each card would get its own "Buy" link, so a customer buying two bikes pays twice. After every sale, delete the bike from the site's data and deploy. Stripe's receipt isn't enough: send the `.md` email for every order.

## 6. Couriers, e-bikes and lithium batteries

- **Royal Mail and Parcelforce won't carry e-bikes.** Their prohibited-items guidance lists electric bicycles and "all battery powered vehicles (UN3171)". Royal Mail caps lithium batteries in equipment at 100Wh, far below an e-bike pack. Parcelforce takes batteries on their own only from contract customers, after an approval process. So e-bikes need a specialist courier that accepts UN3171. The page says so in the FAQ, the delivery section and the basket.
- **Ask the e-bike courier** whether it takes used batteries, how they must be packed and labelled, and what cover it gives. Never ship a battery that's damaged or failed its test.
- **Ask an adviser** whether carrying and storing used and waste lithium batteries brings you under the carriage of dangerous goods rules (ADR) and whether you need a dangerous goods safety adviser or an exemption. The audit couldn't confirm the exact ADR provisions for UN3171 or for damaged batteries.
- **Pedal bikes:** check each courier's size and weight limits for a boxed bike before you promise £39 everywhere (decision 2). Cover at least the bike's price.
- **Spare batteries** can't go by Royal Mail, and only by Parcelforce on a contract. A battery sent on its own (a spare, or a warranty replacement) is **UN3480**, not UN3171, and needs a courier and packaging approved for UN3480.

## 7. For your advisers (not decided here)

| Topic | The question | Who |
|---|---|---|
| **VAT and the margin scheme** | Register now or at the £90,000 threshold? Can bikes bought from the public go on the margin scheme (Notice 718: one total price on the invoice with no VAT shown, a scheme label, self-billed purchase invoices for private sellers, a stock book; refurbishment parts can't go into the purchase price but their VAT is reclaimable; VAT is one-sixth of the margin)? Workshop labour and new parts are standard-rated. Then set `Charge tax` in the CSV and in Shopify. The page already says margin-scheme receipts don't show VAT. | Accountant |
| **WEEE and batteries** | E-bikes are electrical equipment under the WEEE Regulations 2013 (only type-approved electric two-wheelers are excluded), and the chargers you supply may count as new equipment. Do you have distributor take-back duties? The Distributor Take Back Scheme is open if you sell under £100,000 of electrical equipment a year, or only online; its current fee covers you to 31 December 2026, so budget for 2027. E-bike batteries are "industrial batteries": waste ones from the workshop go to a registered waste carrier and an approved treatment site. Then add a take-back sentence to the terms and the FAQ. | WEEE / environmental adviser |
| **Second-hand dealer licensing** | In Scotland, the Civic Government (Scotland) Act 1982 s24 needs a licence where the council has adopted it, and a refurbished-bike shop probably isn't "incidental" dealing. In England and Wales there's no general licence, but ask whether any local Act applies. | Council licensing team |
| **Insurance** | Product and public liability (you're the "producer" of every bike you recondition, under the General Product Safety Regulations 2005), customers' bikes in your custody, stock in transit, and employer's liability (compulsory once you have staff). | Insurance broker |
| **Northern Ireland sales** | Since 13 December 2024, consumer products placed on the Northern Ireland market come under the EU General Product Safety Regulation (EU) 2023/988 (under the Windsor Framework), not the GB rules. It covers used, repaired and reconditioned products as well as new ones (gov.uk guidance). A product can only be placed on the NI market if there's a responsible economic operator established in NI or the EU, and online offers must show the manufacturer's name and contact details (and the responsible person's where needed). Ask whether you, as the refurbisher, count as the manufacturer, and what you'd need to set up. Or decide not to deliver to NI at first (decision 23). The e-bike legal limits in NI are the same as GB's (the page already says so). Sources: gov.uk, "EU Regulation 2023/988 on General Product Safety: detailed guidance"; nibusinessinfo.co.uk, "Product safety law in Northern Ireland". | Trading Standards or a product-safety adviser |
| **Product safety** | As a refurbisher you're a producer under the GPSR 2005. Check recalls before sale (section 4), put a set-up sheet with torque figures in every box, follow the gov.uk statutory guidelines on lithium-ion battery safety for e-bikes, and only ever supply the maker's battery and charger (the page promises that). | Your own process; Trading Standards if unsure |
| **Dispute resolution (ADR)** | What, if anything, the DMCC Act regime (from 6 April 2026) needs you to tell customers. | Solicitor or Trading Standards |
| **Uncollected bikes** | The notice process for selling an uncollected bike (decision 11). | Solicitor |

## 8. The workshop

- **Drop-off ticket** with the trader identity, the customer's name and phone, the bike and its frame number, the agreed work and price, "we phone before any extra work", and the collection deadline. That's when the contract is made (the page says so).
- **Booking requests** arrive as requests (section 10, step 6). Phone to confirm; nothing is paid online.
- **Uncollected bikes:** follow the procedure your solicitor gives you (decision 11), with notices by recorded delivery.
- **Job records**, kept with the ticket.

## 9. Hosting and deploying

The page is one self-contained file: `sites/chainline/index.html`. The favicon is built in, and the only outside requests are Google Fonts. Any host that serves static files over HTTPS on your own domain will do. Before you pay for one, check:

- **its terms allow a shop.** GitHub Pages doesn't;
- **it sends `Content-Type: text/html; charset=utf-8`**, or at least respects the page's own `<meta charset="utf-8">`. The page now declares it, so the old garbled "Â£" is gone either way;
- **how long it keeps server logs.** That's the `[30]` in the privacy notice;
- it serves your domain over HTTPS and redirects `http://` to `https://`.

**Deploying:**

1. Copy `sites/chainline/index.html` to a release folder, make the section 10 switches there, and run `python3 launch/chainline/check_site.py --site <that folder> --launch`. It must end with no FAIL.
2. Upload that `index.html` to the host's web root. Add a `robots.txt` that allows crawling (`User-agent: *` and an empty `Disallow:`) and a `/favicon.ico` if you want to stop browsers asking for one.
3. Point the domain at the host (its DNS instructions) and wait for HTTPS.
4. Check the live page on a phone and a computer: the bikes, the basket, both forms, the small print and the footer links. Check it with JavaScript off too (the bikes and prices still show).
5. **The claude.ai artifact stays a preview copy.** Never publish the switched, live page to it (`sites/README.md`). After launch, `sites/chainline/index.html` holds the live page, so republish the artifact only from a preview copy, or stop updating it.

**If you put the preview on a real host before launch,** keep the page's `noindex` and add a `robots.txt` with `Disallow: /`.

## 10. Preview-to-live switches

Make these on launch day, in the release copy (section 9), then run `check_site.py --launch` (it fails on each one still left) and `validate_shopify_csv.py --launch`.

1. **Search engines:** delete `<meta name="robots" content="noindex">` and the comment above it.
2. **Canonical and social tags:** add, in the head, `<link rel="canonical" href="https://www.your-domain/">`, `<meta property="og:url" content="https://www.your-domain/">` and `<meta property="og:image" content="https://www.your-domain/og.png">` (a 1200×630 image you host; a real photo is best). Fill `[Website address]` in the structured data.
3. **The prototype banner:** delete `<section class="banner" id="top" …>…</section>` and put `id="top"` on `<header class="site-header">` instead (the logo links to `#top`).
4. **The footer's prototype line:** delete `<p>Prototype: placeholder stock, prices and contact details.</p>`.
5. **The small print:** delete the "Not trading yet" note, and the privacy notice's "In this preview the forms don't send anything."
6. **The two forms.** In the page's script, the functions passed to `onSend(...)` for `#book` and `#sell-form` show the "Prototype: … aren't sent" replies. Replace each with a real send. The simplest, with no new data processor: open the visitor's own email app with the details filled in, as Full Bars does (`location.href = 'mailto:…?subject=…&body=…'`), and reply "Your email app should open with your request filled in. Press send there; nothing is sent until you do." A form service instead must be named in the privacy notice ("Who we share it with"). Keep the validation and the "request, not a booking" wording.
7. **Checkout.** The Checkout button only shows "Payments aren't connected yet". On Shopify, add each bike's Shopify variant ID to the bike data (for example `"variant": 44123456789012`) and change the button's handler to send the basket to Shopify's cart: `https://<your shop>/cart/<variant>:1,<variant>:1`. Shopify then takes the delivery choice, the address and payment. Keep the site's basket totals exactly equal to Shopify's shipping rates (section 5, step 4). On Stripe, remove the basket (section 5).
   **Once a bike sells,** Shopify won't sell it again (stock 1), but the site still shows it until you take it out of the bike data. Do that the same day (section 4: edit the data, run `sync_bikes.py`, deploy), or a second customer adds it to the basket and lands on Shopify's sold-out page.
8. **E-bike courier price:** set `"ebike"` in the bike data and run `sync_bikes.py` (section 3).
9. **Every placeholder filled** (section 3), and the bikes replaced with real stock (section 4).
10. Run `check_site.py --launch`, `validate_shopify_csv.py --launch` and the tests (`cd launch/chainline && python3 -m unittest discover -s tests`), then deploy (section 9).

## 11. Test order

1. Check every bike shows as **Active** and on the **Online Store** channel (section 5, step 3a), and that a cart link for each opens checkout with the right bike and price.
2. With Shopify in test mode, put each of these through from the site's basket, and check Shopify's shipping line and total equal the site's basket exactly: one bike for collection (£0 delivery); one bike for delivery (£39); **two bikes for delivery (£78)**; and, once the e-bike price is set, one bike and one e-bike for delivery (£39 plus the e-bike price). If any differs, fix the rates (section 5, step 4) before launch. Check the final button says "Pay now" or similar (CCR reg 14: it must be clear that pressing it means paying).
3. Read the Shopify confirmation email on a phone and a computer: every [placeholder] filled, the collection paragraph for the collection order and the delivery one otherwise, the e-bike section only for e-bikes, "Paid by" naming the card once, the cancellation form intact.
4. Send yourself the acceptance email (`order-confirmation-email.md`) with a real bike's details.
5. Then one real order on your own card, and refund it.
6. Send a booking request and an offer request from the live site and check they reach the inbox.

## Files in this folder

| File | What it is |
|---|---|
| `GO-LIVE.md` | This checklist |
| `sync_bikes.py` | Writes the bike cards, the structured data, the bike count and the whole example workshop ticket into the page from the bike data. `--check` changes nothing and fails if they're out of date. |
| `check_site.py` | Checks the page and the two emails: head, artifact rules, every repeated price agreeing everywhere, the rules that can close the business, legal sections, honesty, contact details, preview switches and placeholders. `--launch` also fails while any preview switch or placeholder is left on the page or in either email. |
| `build_shopify_csv.py` | Builds `products-shopify.csv` from the page's bike data: one draft product per bike, stock 1, never oversold. |
| `validate_shopify_csv.py` | Checks the CSV against Shopify's template (the same header as Full Bars) and against the site's prices, three ways. `--template` checks against Shopify's own sample; `--launch` fails on placeholders. |
| `products-shopify.csv` | The import file, built from the preview data. Rebuild it once the real bikes and details are in. |
| `order-confirmation-email.md` | The acceptance email to send for every order, and why the law needs it |
| `order-confirmation-email.html` | The Shopify order confirmation template (Liquid) |
| `tests/` | `python3 -m unittest discover -s tests` from this folder: the scripts (`test_tools.py`), the emails (`test_email.py`) and the page in Chromium (`test_site_browser.py`: JavaScript off, reload and Back, the basket, the forms, a sandboxed iframe; skipped without Node and Playwright). |

**Also done (Full Bars, found in passing by the legal audit):** `sites/full-bars/privacy.html` now says customers can complain to Full Bars itself and that it acknowledges complaints within 30 days (DPA 2018 s164A).
