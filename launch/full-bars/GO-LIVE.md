# Full Bars: go-live checklist

As of 13 October 2026 the site (`sites/full-bars/`) is a preview. Search engines are blocked, every page has a "not trading yet" banner, and it can't take orders, messages or trade-ins. Work down this page in order. Nothing here is done unless it says so.

## Launch order

1. Accountant: VAT registration and the second-hand margin scheme. Then choose Shopify or Stripe links. ([§1](#1-decide-first-your-call))
2. Decide WEEE take-back, courier cover, the buy-now cap and the prices. ([§1](#1-decide-first-your-call))
3. Set up the company, bank, ICO fee, domain, inbox, CheckMEND, Royal Mail account and waste carrier. ([§2](#2-business-and-accounts))
4. Fill every [placeholder], including the log-retention `[30]` in `privacy.html`, and fix the three handset weights. ([§3](#3-fill-every-placeholder))
5. Buy stock, IMEI-check it, photograph it, weigh one packed parcel. ([§4](#4-pictures-and-stock-needs-real-data))
6. Shopify: prove the CSV on one hand-made test product, then import and set up the store. ([§5](#5-if-you-choose-shopify)) Static site instead: ([§6](#6-if-you-stay-on-the-static-site))
7. Launch day: flip the switches and put one real order through. ([§7](#7-launch-day-switches))

The files in this folder are listed at the end.

## 1. Decide first (your call)

1. **Checkout: Shopify, or the static site with Stripe Payment Links (`pay.js`).** I'd pick Shopify. Every phone is a one-off. Shopify counts stock per variant and won't sell the same phone twice. A Payment Link has to be switched off by hand after every sale, and `pay.js` has 183 of them. Don't run both at once: you'd double-sell.
2. **VAT, for your accountant (I'm not deciding this):** do you register for VAT? Registration is compulsory once taxable turnover passes £90,000 in any 12 months. And does the **VAT margin scheme for second-hand goods** apply to these phones? The answer changes four things:
   - the CSV's `Charge tax` column (currently TRUE);
   - whether receipts may show VAT (`terms.html` already says margin-scheme receipts won't);
   - the trade-in formula in `quote.js`, which assumes the margin scheme;
   - the VAT line in every footer.
3. **WEEE take-back.** You sell electrical equipment, so you have retailer take-back duties, and the site says nothing about them yet. Either join the Distributor Take Back Scheme (allowed if you sell under £100,000 of electrical equipment a year or sell only online; the current fee covers you to 31 December 2026, so budget for 2027), or offer your own free like-for-like take-back. Then add the wording to `delivery-returns.html` and `faq.html`. If you'll import phones yourself rather than buy them in the UK, ask whether that makes you a "producer" as well.
4. **Courier.** The site promises Royal Mail Special Delivery "or an equivalent service" (insured, tracked and signed for). Special Delivery's standard cover is £750. 13 of the site's prices are above that, the highest being the iPhone 16 Pro Max 1TB Excellent at £969, so those parcels need the £1,000 or £2,500 cover band.
5. **Buy-now cap** (static route only). `BUY_NOW_MAX` in `site.js` is £450, which covers 97 of the 183 prices. Keep it or change it.
6. **Prices.** The site calls them "preview prices". Check them against the market before launch. To change one, edit `data-prices` on that product page. Then run `check_site_prices.py`: it lists every other place that number appears (cards, "from" lines, titles, structured data). Cutting the iPhone 13's lowest price, for example, needs 36 other edits. Fix those, then rebuild the CSV.
7. **Trade-in prices** in `quote.js` are copied from `lib/pricing-config.ts` in the phones-business repo. Confirm them before you open trade-ins.

## 2. Business and accounts

| Set up | Why |
|---|---|
| Company (or sole trader), business bank account | Fills the trader details in section 3. If the company itself is called Full Bars, reword "Full Bars is a trading name of…". |
| ICO data protection fee | You'll hold customer and seller data. Put the registration number in `privacy.html`. |
| Domain `fullbars.co.uk` | Check it's free and buy it. It appears 828 times across 60 files: canonical links, social tags, sitemap, structured data and the email address. A different domain means changing all of them. |
| Inbox `hello@fullbars.co.uk` | Used on every page and in `site.js` / `quote-ui.js`. Set up SPF, DKIM and DMARC so replies don't land in spam. |
| CheckMEND business account | Before you buy a single phone. Check every IMEI when you buy and again before dispatch, and refuse anything activation-locked, blacklisted or reported stolen. Never alter an IMEI. The site promises all of this. |
| Shopify **or** Stripe | Depends on decision 1. |
| Royal Mail business account (Click & Drop) | Special Delivery labels and prepaid return labels, which the site promises for returns and trade-ins. |
| Licensed waste carrier | `about.html` says old batteries go to one. |
| Accountant | Decision 2. |

## 3. Fill every placeholder

| Placeholder | Where | What to put |
|---|---|---|
| `[Company name]` | Footer of all 56 pages, plus `terms`, `privacy`, `contact`, `delivery-returns` (cancellation form), `about`, `warranty` | Legal name of the company, or your own name if you're a sole trader |
| `[registered in England and Wales]` | Footers, `terms` | Where the company is registered. Delete it if you're a sole trader. |
| `[Company number]` | Footers, `terms`, `about` | Companies House number. Delete it if you're a sole trader. |
| `[Registered business address]` | Footers, `terms`, `privacy`, `contact`, `delivery-returns`, `warranty` | A real postal address. Customers need it to cancel or complain, and a PO box isn't enough. |
| `[VAT number, if registered]` | Footers, `terms` | VAT number, or delete the VAT sentence |
| `[Phone number]` | `contact`, `terms` | Business number, or delete the line |
| `[Opening hours]` | `contact` | When you answer |
| `[Town, County]` | `about` | Where you're based |
| `[ICO registration number]` | `privacy` | From section 2 |
| `[the law of England and Wales]`, `[the courts of England and Wales]` | `terms` | Keep them, without the brackets, if you're in England or Wales. Ask if you're in Scotland or Northern Ireland. |
| `[30]` | `privacy` ("Who we share it with") | How many days your web host (or Shopify) actually keeps server logs with IP addresses, from the host's own terms. Remove the brackets. |

`privacy.html` names services by type ("our website host", "our email provider"). Once you've chosen them, name the actual host and email provider there.

**Leave these alone:** `[phone, storage, grade, colour]`, `[date]`, `[your name]` and `[your address]` in the cancellation form on `delivery-returns.html` are for customers to fill in. "Settings > [your name]" in `guides/remove-find-my-before-selling-iphone.html` is an iPhone menu name, and the bracketed text in `site.js` and `quote-ui.js` is code. To find any you've missed, run this from the repo root. It lists every bracketed placeholder in the pages, so only the "leave these alone" ones above should be left: `grep -rnoE "\[[^]<>\"=]+\]" sites/full-bars --include=*.html`

**Also fix before launch:** three handset weights on the site don't match the makers' figures. The iPhone 12 Pro page says 187g (it's 189g). The iPhone 13 mini page compares against the iPhone 13 at 173g (it's 174g). The iPhone 13 Pro Max page says 238g (it's 240g).

## 4. Pictures and stock (needs real data)

- **Photos.** The CSV has no images. `og/products/<handle>-1x1.png` (plus 4x3 and 16x9 versions) are ready-made illustrations you can upload. Each CSV description already carries the site's "pictures are illustrations" line, so keep that line for as long as you use them. Real photos are better for refurbished phones.
- **Stock.** Stock is 0 everywhere and the site has no `data-stock`, so nothing can be bought until you enter real stock. For each phone you buy and pass, add 1 to the exact variant (storage, condition, colour). Keep its IMEI and unit number in your own records, never on the product page. The site's SKU style is `IP14-128-MID-VG-0247`, which is the CSV's variant SKU plus a unit number.
- **Weights.** The CSV uses the maker's handset weight plus a 200 g packing estimate (341–440 g). Weigh one packed parcel and change `PACKING_G` in `build_shopify_csv.py`.
- **Battery %.** Each unit's figure goes in the confirmation email within 1 working day. The site promises this.

## 5. If you choose Shopify

1. **Settings.** UK store, GBP. Prices must **include** tax, or Shopify adds 20% on top of these VAT-inclusive prices. Ask the accountant how to set `Charge tax` (the CSV has TRUE). Under the margin scheme VAT is still due on your margin, and Shopify won't calculate it, so it has to be worked out outside Shopify. With `Charge tax` on, Shopify's reports show VAT on the full price; with it off, £0. Neither is the margin VAT, so don't file returns from Shopify's tax figures.
2. **Shipping.** One free rate, UK only, as the terms say.
3. **Prove the format on one product first.** I couldn't open Shopify's help pages from my sandbox, so the CSV's column names and values (`draft`, `deny`, `TRUE`, `g`) haven't been checked against Shopify itself.
   - Make one test product by hand: options Storage, Condition and Colour with two values each; status Draft; not on the Online Store; track quantity on; don't continue selling when out of stock; physical product; charge tax ticked; weight in g; category "Mobile & Smart Phones".
   - Export it as a plain CSV. Download the sample CSV from Products > Import too.
   - Run `python3 launch/full-bars/validate_shopify_csv.py --template <the sample> --export <your export>`. Every line must say PASS or NOTE (a NOTE means your export leaves that column out, so there was nothing to compare). If only "your store uses the current column names" fails, import `products-shopify-legacy-headers.csv` instead. If a value line fails (say your store writes `DENY` where the CSV has `deny`), don't import: the builder needs changing first.
   - Delete the test product.
4. **Import** the file step 5.3 picked. You should end up with 19 draft products, 873 variants and 0 stock. Check that the category reads "Mobile & Smart Phones".
5. **Collections.** Make them automated, by tag, so they match the site:
   - "iPhone 12 series" to "iPhone 16 series": one tag each
   - "Samsung Galaxy", "Google Pixel": one tag each
   - Pro iPhones: tags `Pro` and `iPhone`
   - Big screen: tag `Big screen`
   - USB-C iPhones: tags `USB-C` and `iPhone`
   - Under £300: tag `Under £300`, which the builder recalculates from the prices on every rebuild

   The validator checks that the tags rebuild all 11 site collections exactly.
6. **Policies and trader details.** Put the section 3 trader details in Store details. Paste terms, privacy, delivery and returns into Settings > Policies.
7. **Wording that changes with Shopify.**
   - `terms.html` and `faq.html` say you take payment through Stripe. Change them to whatever you actually use.
   - `privacy.html` must name Shopify and its payment processor.
   - The site promises no tracking, but Shopify sets its own cookies. Turn on Shopify's cookie banner for UK visitors, add no marketing pixels, and rewrite `cookies.html`.
8. **Honest selling (DMCC Act 2024).**
   - No compare-at prices unless it's a real previous price.
   - No countdown or "selling fast" apps.
   - No review apps until you have real reviews.
   - Stock messages only if they're true.
9. **Theme.** Dark, to match the site.
10. **Test.** Place an order in test mode, then a real order and refund on your own card.

## 6. If you stay on the static site

1. **`pay.js`.** Add a Payment Link only for a phone you hold that meets the rules in the file's header: original parts only, at or under the cap, terms accepted, quantity 1, UK address, colour field, Radar rules. Clear the link the moment that phone sells.
2. **`data-stock`.** Add it to each product page's `#picker` form. The format is in `site.js`.
3. **Order button.** On all 19 product pages it's a dead `<span id="orderBtn" aria-disabled="true">Opening soon</span>`. `site.js` only sets its link, so it must become `<a class="btn btn-hot btn-block" id="orderBtn" href="../contact.html">Order</a>`. If you skip this, nothing on the product pages can be clicked to order.
4. **`contact.html`.** Add an "Order a phone" topic (`site.js` looks for it), and remove the "Not trading yet" panel and the preview note.
5. **Hosting.** Use a real web host, where `404.html`'s root-relative links work.

## 7. Launch day switches

- [ ] `robots.txt`: change `Disallow: /` to `Allow: /` (the comment in the file says how).
- [ ] All 56 pages: change `<meta name="robots" content="noindex">` to `index,follow`.
- [ ] All 56 pages: remove the `<div class="preview-bar">` banner.
- [ ] Remove `data-preview="1"` from 27 places: 19 product pickers, the contact form, and the quote tool on `sell.html` and the 6 `sell/*.html` pages.
- [ ] Rewrite the preview wording:
  - "Preview prices…" on 32 pages
  - "when we open", "open soon" and "Opening soon" on about 58 files, including `site.js` and `quote-ui.js`
  - the "Not trading yet" boxes on `contact`, `terms`, `delivery-returns`, `warranty`, `privacy` and `cookies`

  To find all of it: `grep -rniE "preview|when we open|once we open|open soon|opening soon|not trading|trading yet" sites/full-bars`.
- [ ] Change "Last updated October 2026" on `terms`, `privacy`, `cookies`, `warranty` and `delivery-returns` to the launch date. Update the `lastmod` dates in `sitemap.xml`.
- [ ] Checkout: Shopify products set to Active and published, **or** the Payment Links filled in `pay.js`.
- [ ] Republish the site and test one order end to end.

**Sources.**
- Shopify CSV columns and rules come from [Using CSV files to import and export products](https://help.shopify.com/en/manual/products/import-export/using-csv): current column names, one row per variant, Status of active/draft/archived, Product category as a breadcrumb or an ID but not both, up to 3 options and 2,048 variants, `deny`/`continue`, 15 MB file limit.
- The older column names come from [Common import issues](https://help.shopify.com/en/manual/products/import-export/common-import-issues).
- I couldn't open help.shopify.com from my sandbox (DNS lookup fails). I checked both pages only through search results that quote them, so the validator's built-in column list is my transcription, not proof. Step 5.3 is the real check: it compares the CSV with files your own store produces.
- Category: Shopify Standard Product Taxonomy `el-4-8-5`.
- Take-back: [gov.uk Distributor Take Back Scheme](https://www.gov.uk/electricalwaste-producer-supplier-responsibilities/join-the-distributor-takeback-scheme).
- Courier cover: [Royal Mail Special Delivery](https://www.royalmail.com/sending/uk/special-delivery-guaranteed-1pm).

**In this folder**

- `products-shopify.csv`: all 19 phones the site sells, 873 variants (storage × condition × colour). Prices are copied from the site. Every product is draft and unpublished, with stock 0 and no images.
- `products-shopify-legacy-headers.csv`: the same rows under Shopify's older column names. Use it only if the 5.3 check says your store uses the older column names.
- `build_shopify_csv.py` and `validate_shopify_csv.py`: after any price change on the site, rebuild and re-check the CSVs. Never edit the CSV by hand. From the repo root, run `python3 launch/full-bars/build_shopify_csv.py && python3 launch/full-bars/validate_shopify_csv.py`. Add `--template` and `--export` as in 5.3 once you have a store.
- `check_site_prices.py`: checks that every price shown on the site matches the price data on the product pages (983 checks, all passing today).
