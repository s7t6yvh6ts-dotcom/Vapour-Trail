# Full Bars: go-live checklist

As of 13 October 2026 the site (`sites/full-bars/`) is a preview. Search engines are blocked, every page has a "not trading yet" banner, and it can't take orders, messages or trade-ins. Work down this page in order. Nothing here is done unless it says so.

## Launch order

1. Accountant: VAT registration and the second-hand margin scheme. Then choose Shopify or Stripe links. ([§1](#1-decide-first-your-call))
2. Decide WEEE take-back, courier cover, the buy-now cap and the prices. ([§1](#1-decide-first-your-call))
3. Set up the company, bank, ICO fee, domain, inbox, CheckMEND, Royal Mail account and waste carrier. ([§2](#2-business-and-accounts))
4. Fill every [placeholder], including the log-retention `[30]` in `privacy.html`. ([§3](#3-fill-every-placeholder))
5. Buy stock, IMEI-check it, photograph it, weigh one packed parcel. ([§4](#4-pictures-and-stock-needs-real-data))
6. Shopify: prove the CSV on one hand-made test product, then import and set up the store. ([§5](#5-if-you-choose-shopify)) Static site instead: ([§6](#6-if-you-stay-on-the-static-site))
7. Launch day: flip the switches and put one real order through. ([§7](#7-launch-day-switches))

The files in this folder are listed at the end.

## 1. Decide first (your call)

1. **Checkout: Shopify, or the static site with Stripe Payment Links (`pay.js`).** I'd pick Shopify. Every phone is a one-off. Shopify counts stock per variant and won't sell the same phone twice. A Payment Link has to be switched off by hand after every sale, and `pay.js` has 183 of them. Don't run both at once: you'd double-sell.
2. **VAT, for your accountant (I'm not deciding this):** do you register for VAT? Registration is compulsory once taxable turnover passes £90,000 in any rolling 12 months, or as soon as you expect it to pass £90,000 in the next 30 days alone. And does the **VAT margin scheme for second-hand goods** apply to these phones? The answer changes four things:
   - the CSV's `Charge tax` column (currently TRUE);
   - whether receipts may show VAT (`terms.html` already says margin-scheme receipts won't);
   - the trade-in formula in `quote.js`, which assumes the margin scheme;
   - the VAT line in every footer.
3. **WEEE take-back.** You sell electrical equipment, so you may have retailer take-back duties, and the site says nothing about them yet. The duty (regulation 42 of the WEEE Regulations 2013) is worded for distributors that supply *new* electrical equipment, and I couldn't find official guidance on whether refurbished phones (or the new cable in each box) count, so ask, or play safe. Either join the Distributor Take Back Scheme (allowed if you sell under £100,000 of electrical equipment a year or sell only online; the current fee covers you to 31 December 2026, so budget for 2027), or offer your own free like-for-like take-back. Then add the wording to `delivery-returns.html` and `faq.html`. If you'll import phones yourself rather than buy them in the UK, ask whether that makes you a "producer" as well.
4. **Courier.** The site promises Royal Mail Special Delivery "or an equivalent service" (insured, tracked and signed for). Special Delivery's standard cover is £750. 13 of the site's prices are above that, the highest being the iPhone 16 Pro Max 1TB Excellent at £969, so those parcels need the £1,000 or £2,500 cover band.
5. **Buy-now cap** (static route only). `BUY_NOW_MAX` in `site.js` is £450, which covers 97 of the 183 prices. Keep it or change it.
6. **Prices.** The site calls them "preview prices". Check them against the market before launch. Change them with `set_prices.py`, never by hand: one price can show up in dozens of places (cards, "from" lines, titles, structured data, collection lines; cutting the iPhone 13's lowest price touches 39 places in 15 files), and the tool rewrites them all. From the repo root:
   - See what it would change: `python3 launch/full-bars/set_prices.py --set "iPhone 13" 128GB Good 199 sites/full-bars --dry-run`
   - Do it: the same command without `--dry-run`. Repeat `--set` to change several prices at once (for example Very Good and Good together, so a better condition never costs less).
   - If it lists anything under NEEDS A HAND EDIT (a phone crossing £300, the "Lowest price" badge, a trade-in price in `quote.js`), it writes nothing. Make that edit first and run it again, or add `--allow-hand-edits` and make the edit straight after.
   - Then rebuild and check the CSV: `python3 launch/full-bars/build_shopify_csv.py && python3 launch/full-bars/validate_shopify_csv.py`.
7. **Trade-in prices** in `quote.js` are copied from `lib/pricing-config.ts` in the phones-business repo. Confirm them before you open trade-ins.

## 2. Business and accounts

| Set up | Why |
|---|---|
| Company (or sole trader), business bank account | Fills the trader details in section 3. If the company itself is called Full Bars, reword "Full Bars is a trading name of…". |
| ICO data protection fee | You'll hold customer and seller data, including ID checks and crime-prevention records, which aren't among the exempt purposes, so expect to pay. Tier 1 (turnover up to £632,000 or no more than 10 staff) is £52 a year, £47 by direct debit; the ICO's online self-assessment confirms it. Put the registration number in `privacy.html`. (The regulator became the Information Commission on 30 September 2026 but still uses the name ICO.) |
| Domain `fullbars.co.uk` | Check it's free and buy it. It appears 828 times across 60 files: canonical links, social tags, sitemap, structured data and the email address. A different domain means changing all of them. |
| Inbox `hello@fullbars.co.uk` | Used on every page and in `site.js` / `quote-ui.js`. Set up SPF, DKIM and DMARC so replies don't land in spam. |
| CheckMEND business account | Before you buy a single phone. Check every IMEI when you buy and again before dispatch, and refuse anything activation-locked, blacklisted or reported stolen. Never alter an IMEI. The site promises all of this. |
| Shopify **or** Stripe | Depends on decision 1. |
| Royal Mail business account (Click & Drop) | Special Delivery labels and prepaid return labels, which the site promises for returns and trade-ins. |
| Registered waste carrier | `about.html` says old batteries go to one. Carriers are registered, not licensed: check it on the Environment Agency's public register (SEPA or Natural Resources Wales if you're in Scotland or Wales). |
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

**Done:** the three handset weights that didn't match the makers' figures (iPhone 12 Pro 189g, iPhone 13 174g on the iPhone 13 mini page, iPhone 13 Pro Max 240g) were corrected on 13 October 2026.

## 4. Pictures and stock (needs real data)

- **Photos.** The CSV has no images. `og/products/<handle>-1x1.png` (plus 4x3 and 16x9 versions) are ready-made illustrations you can upload. Each CSV description already carries the site's "pictures are illustrations" line, so keep that line for as long as you use them. Real photos are better for refurbished phones.
- **Stock.** Stock is 0 everywhere and the site has no `data-stock`, so nothing can be bought until you enter real stock. For each phone you buy and pass, add 1 to the exact variant (storage, condition, colour). Keep its IMEI and unit number in your own records, never on the product page. The site's SKU style is `IP14-128-MID-VG-0247`, which is the CSV's variant SKU plus a unit number.
- **Weights.** The CSV uses the maker's handset weight plus a 200 g packing estimate (341–440 g). Handset weights live in one place: `weight_g` in `facts.json`, which `check_site_facts.py` checks every page against and `build_shopify_csv.py` reads. Weigh one packed parcel and change `PACKING_G` in `build_shopify_csv.py` (the packing, not the handsets), then rebuild the CSV.
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
3. **Order button and options.** On all 19 product pages the button is a dead `<span id="orderBtn" aria-disabled="true">Opening soon</span>`, and the three option `<fieldset>`s (storage, condition, colour) ship `disabled`.
   - Once `data-preview` is gone from `#picker`, `site.js` swaps the span for a link by itself. Change the markup anyway, to `<a class="btn btn-hot btn-block" id="orderBtn" href="../contact.html">Order</a>`, so the button still goes somewhere if `site.js` fails to load. `site.js` then fills in the chosen phone and price.
   - Leave the fieldsets `disabled` in the HTML. `site.js` switches them on only after it has read `data-prices` and found a price for every storage and condition on that page. That way, without the script, the ticked options always match the price shown.
   - **The catch:** if `data-prices` is mistyped, or a storage and condition has no price, that page keeps greyed-out options and its "Opening soon" span, so the phone can't be ordered. Nothing on the page says why: the browser console shows a warning starting "Full Bars: data-prices", and `check_site_prices.py` stops with a Python error (a traceback, not FAIL lines). Use `data-stock`, never a missing price, to show something isn't available. The launch-day check in section 7 catches the rest.
4. **`contact.html`.** Add an "Order a phone" topic (`site.js` looks for it), and remove the "Not trading yet" panel and the preview note.
5. **Hosting.** Use a real web host, where `404.html`'s root-relative links work.
6. **Leave the script fallbacks in place.** They only show when a script doesn't run:
   - `#qtFallback` on `sell.html` and the 6 `sell/*.html` pages ("The instant quote hasn't loaded…"). `quote-ui.js` hides it once the quote tool is drawn. `styles.css` keeps it invisible for the first 3 seconds, so a slow script doesn't flash it, and the `<noscript>` style in each page's head shows it at once when JavaScript is off.
   - `[data-needs-quote]` on the sell pages: each "up to £…" phrase ships `hidden`, and `quote-ui.js` shows it once `quote.js` has filled in the figure. `styles.css` keeps its space meanwhile, so the page doesn't jump, and drops it after 3 seconds if the figure never arrives. Don't remove `hidden` by hand, or a failed script leaves "up to" with no figure.
   - The `onerror` on every page's `site.js` tag. If `site.js` fails to load, it adds `no-site-js` to the page, so the header shows "Shop phones" instead of a menu button that does nothing, the shop filters and contact form are hidden, and the contact page says the form didn't load. Keep it if you edit the script tags.

## 7. Launch day switches

`go_live.py` does the mechanical switches in one go, puts your new wording in place of the preview wording, and refuses to run while anything blocks launch. Dry runs and `--check-only` change nothing, so run them anywhere. Do the real run on a git branch (or on a copy of `sites/full-bars`), never on your only copy, and keep the report and the wording file outside the site folder so they don't get published. The published artifact is built from `sites/full-bars` (see `sites/README.md`), so the switch only goes live once that branch is merged, or, if you worked on a copy instead, once you've copied the checked folder back over `sites/full-bars`. Then republish.

- [ ] **Dry run.** From the repo root: `python3 launch/full-bars/go_live.py --site sites/full-bars --domain fullbars.co.uk --checkout stripe --dry-run --out ~/go-live-report.txt --rewrites-template ~/rewrites.json` (or `--checkout shopify`). It changes nothing in the site. It lists every change it would make (file, line, before, after), the blockers, and what's left for you, and writes `~/rewrites.json`. `--check-only` lists just the blockers.
- [ ] **Write the new wording.** The preview wording ("Preview prices: we're not taking orders yet.", "When we open, …", the contact form's notes, the FAQ answers) is in the future tense, so no script can switch it. `~/rewrites.json` has one sentence per line, as a customer reads it, each set to `null`. Replace each `null` with the new wording in plain text, or `""` to delete the sentence. Each sentence is replaced everywhere it appears: in the page text, in the meta descriptions and in the FAQ structured data, with quotes and `&` made safe for each place. Tags (`<` and `>`) are refused, so links and bold stay as they are on the page.
- [ ] **Fix the blockers, then dry-run again with `--rewrites ~/rewrites.json`** until it says "No blockers". It refuses while any of these remain:
  - a `[placeholder]` on any page (section 3). The "leave these alone" ones are allowed, and CSS in the pages such as `[hidden]` doesn't count, though section 3's grep lists it;
  - any problem `check_site_prices.py` or `set_prices.py --check` finds (including a stale "Price for … From" line and a "Lowest price" badge on a phone that's no longer the cheapest);
  - any handset spec that disagrees with `facts.json` (`check_site_facts.py`);
  - checkout not matching `pay.js`: `--checkout stripe` needs at least one `https://` Payment Link, and `--checkout shopify` needs `pay.js` empty, or you'd sell the same phone twice;
  - a `data-stock` that isn't valid JSON (`site.js` would ignore it and show everything in stock);
  - `--trade-ins open` while the sell pages have no form to send a quote;
  - preview wording that would still be on the live pages. To switch anyway and fix it by hand afterwards, add `--allow-preview-wording`: the run then ends "NOT READY TO PUBLISH" (exit code 3), and you don't publish until the wording is done.
- [ ] **Run it:** the same command without `--dry-run` and `--rewrites-template`, with `--rewrites ~/rewrites.json`. It edits the folder in place:
  - `robots.txt` allows crawling, and its preview comments go;
  - `noindex` becomes `index,follow` on 55 pages. `404.html` keeps `noindex` on purpose: an error page shouldn't be in search results;
  - the preview banner goes from all 56 pages;
  - `data-preview="1"` goes from the 19 product pickers and the contact form;
  - each product page's dead "Opening soon" span becomes `<a class="btn btn-hot btn-block" id="orderBtn" href="../contact.html">Order</a>` (section 6, step 3);
  - the "Not trading yet" boxes on `terms`, `privacy`, `cookies`, `warranty` and `delivery-returns`, and the panel on `contact`, go;
  - the contact form gets its "Order a phone" topic;
  - "Last updated" on those five legal pages and every `lastmod` in `sitemap.xml` become the launch date (`--launch-date`, default today). That happens only in the run that switches the site out of preview: run it again later (to change more wording, say) and the dates stay as they are unless you pass `--launch-date`;
  - your new wording replaces the preview wording;
  - if `--domain` isn't `fullbars.co.uk`, every `https://www.fullbars.co.uk` link and `hello@fullbars.co.uk` address follows it.

  Then it re-checks the switched site, its prices, the badge and the specs, and exits with an error if anything didn't switch. "RESULT: done … no preview wording is left" (exit code 0) means it's ready to publish.
- [ ] **Do what it lists under STILL TO DO BY HAND.** Every line `grep -rniE "preview|when we open|once we open|open soon|opening soon|not trading|trading yet" sites/full-bars` finds afterwards is in the report: as trade-in wording left until trade-ins open, as a hook or code that only runs in preview, or (if you used `--allow-preview-wording`) as wording still to rewrite.
- [ ] **Trade-ins stay closed** unless you add `--trade-ins open`. The quote tool keeps giving guide prices, and its trade-in wording (including the "Trade-ins open soon" box on the sell pages) stays, because it's still true. Before you open them: the sell pages have no form to send a quote (`quote-ui.js` expects `#qtSend`, `#qtName`, `#qtNotes`, `#qtOwner` and `#qtStatus`), so add one. Confirm the trade-in prices (section 1, item 7). Then dry-run with `--trade-ins open --rewrites-template ~/rewrites-trade-ins.json`: the trade-in wording, including the price-table caption in `quote-ui.js` ("Guide prices for when trade-ins open"), is then wording to rewrite. Fill it in and run with `--trade-ins open --rewrites ~/rewrites-trade-ins.json`.
- [ ] Checkout: Shopify products set to Active and published, **or** the Payment Links filled in `pay.js`. On Shopify, the static product pages' Order buttons still take email orders, so point them at Shopify or retire the static shop.
- [ ] Merge the branch (or copy the checked folder back over `sites/full-bars`), republish the site and test one order end to end.
- [ ] Static site: once it's republished, open all 19 product pages. Each must have a clickable button reading "Order — £…" ("Buy now — £…" with a Payment Link, "Not in stock — ask us" for an option you don't hold), and changing storage, condition or colour must change it. "Opening soon" or greyed-out options mean `data-preview` is still on that page's `#picker`, `site.js` didn't load, or `data-prices` is wrong (see section 6, step 3). `check_site_prices.py` doesn't check the button. Then open `sell.html`: the quote questions must appear, not "The instant quote hasn't loaded".

**Sources.**
- Shopify CSV columns and rules come from [Using CSV files to import and export products](https://help.shopify.com/en/manual/products/import-export/using-csv): current column names, one row per variant, Status of active/draft/archived, Product category as a breadcrumb or an ID but not both, up to 3 options and 2,048 variants, `deny`/`continue`, 15 MB file limit.
- The older column names come from [Common import issues](https://help.shopify.com/en/manual/products/import-export/common-import-issues).
- I couldn't open help.shopify.com from my sandbox (DNS lookup fails). I checked both pages only through search results that quote them, so the validator's built-in column list is my transcription, not proof. Step 5.3 is the real check: it compares the CSV with files your own store produces.
- Category: Shopify Standard Product Taxonomy `el-4-8-5`.
- Take-back: [gov.uk Distributor Take Back Scheme](https://www.gov.uk/electricalwaste-producer-supplier-responsibilities/join-the-distributor-takeback-scheme) and [WEEE Regulations 2013, regulation 42](https://www.legislation.gov.uk/uksi/2013/3113/regulation/42).
- VAT threshold: [gov.uk When to register for VAT](https://www.gov.uk/register-for-vat).
- ICO fee: [ICO guide to the data protection fee](https://ico.org.uk/for-organisations/data-protection-fee/data-protection-fee/).
- Courier cover: [Royal Mail Special Delivery](https://www.royalmail.com/sending/uk/special-delivery-guaranteed-1pm).
- I couldn't open gov.uk, legislation.gov.uk, ico.org.uk or royalmail.com from my sandbox on 13 October 2026, so the take-back, VAT, ICO and courier figures were checked through search results that quote those pages.

**In this folder**

Each tool explains itself with `--help`. All commands are from the repo root.

- `products-shopify.csv`: all 19 phones the site sells, 873 variants (storage × condition × colour). Prices are copied from the site. Every product is draft and unpublished, with stock 0 and no images.
- `products-shopify-legacy-headers.csv`: the same rows under Shopify's older column names. Use it only if the 5.3 check says your store uses the older column names.
- `build_shopify_csv.py` and `validate_shopify_csv.py`: rebuild and re-check the CSVs after any price or weight change. Never edit the CSV by hand. `python3 launch/full-bars/build_shopify_csv.py && python3 launch/full-bars/validate_shopify_csv.py`. Add `--template` and `--export` as in 5.3 once you have a store.
- `set_prices.py`: change a price in one place and it updates every page that shows it (section 1, item 6). `python3 launch/full-bars/set_prices.py --set "iPhone 13" 128GB Good 199 sites/full-bars --dry-run`. `--check` checks every shown price, the "From" lines and the "Lowest price" badge without changing anything.
- `check_site_prices.py`: checks that every price shown on the site matches the price data on the product pages (1,006 checks, all passing today). `python3 launch/full-bars/check_site_prices.py`
- `facts.json`: the one place each phone's specs are written down (weight, screen, chip, port, battery, year, camera, updates, water resistance and so on). `build_shopify_csv.py` takes the handset weights from it.
- `check_site_facts.py`: checks every spec stated on any page against `facts.json` and names the page and line of any that disagree. `python3 launch/full-bars/check_site_facts.py`. To see everywhere one fact appears: `--where "iPhone 13" weight_g`.
- `go_live.py`: the launch-day switch (section 7). `python3 launch/full-bars/go_live.py --site sites/full-bars --domain fullbars.co.uk --checkout stripe --check-only`
- `tests/`: tests for the three tools above, each on a temporary copy of the site. `python3 launch/full-bars/tests/test_set_prices.py`, `test_site_facts.py`, `test_go_live.py`.

**After any edit to the site**, run `python3 launch/full-bars/set_prices.py --check && python3 launch/full-bars/check_site_facts.py` (prices, badge and specs), then rebuild the CSV if a price or weight changed.
