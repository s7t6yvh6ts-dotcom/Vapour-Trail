# Grace & Bloom: go-live checklist (digital downloads)

The shop at `grace-and-bloom/` is a **preview** and now sells **digital downloads only**: customers pay, then download files. Nothing is posted, so there's no postage, packing, stock or couriers to sort out. The preview can't take orders or payments, and it says so.

Anything in `[square brackets]` on the site is a gap waiting for a real answer. Never guess one: if you don't know it yet, leave it in brackets. `products-shopify.csv` (next to this file) holds all 19 products, ready to import into Shopify if you choose Shopify.

## At a glance

1. Make the decisions in section 1. The big ones: **where people pay** (Shopify, Etsy or Gumroad), **selling to EU customers** (VAT, with an accountant) and **what buyers may do with the files** (the licence).
2. Make the **real files** for all 19 products (two covers for the Focus planner) and **mock-up pictures** (section 6).
3. Set up the accounts in section 2.
4. Answer every `[placeholder]` in section 3.
5. Get the **cancellation tick box** and the **order email** working (section 4). This is the law, not a nice-to-have: without it customers keep their 14-day right to cancel even after downloading.
6. If Shopify: set it up, import `products-shopify.csv`, and attach each file with Shopify's free **Digital Products** app (section 5). If Etsy or Gumroad: list each product by hand (section 5b).
7. Make a **test purchase that actually downloads a file**, then refund it (step 5.8, or 5b on Etsy or Gumroad).
8. Switch off the preview (section 7).
9. Only then set the products to Active and open the shop.

The sections below are the detail. Sources are listed at the end. Some official pages couldn't be opened directly when this was written, so where the source note says "via search", re-read the live page before relying on the exact wording.

## 1. Decisions to make first

Items marked **(£)** cost money. If Ash is putting money in, agree those with him first.

1. **Business details.** Sole trader or limited company? You need the legal name (your full name if a sole trader), a trading address, a business email and a phone number. They go in the site footer, the refund policy and the model cancellation form. Show a company number only if you're a limited company.

2. **UK VAT.** Are you VAT-registered? You must register once your VAT-taxable turnover for the last 12 months goes over **£90,000**, or if you expect it to go over £90,000 in the next 30 days (gov.uk, "Register for VAT", threshold since 1 April 2024). If you're not registered, you must not charge UK VAT or show a VAT number. This decides the tax settings in step 5.1 and the footer's VAT line.

3. **Where people pay: Shopify, Etsy or Gumroad (£).** The site can't take payments or hand over files by itself. Check current fees on each provider's own pricing page. What each one means for you:
   - *Shopify* + Shopify's free **Digital Products** app: your own shop, your own customers, and the CSV is ready for it. **But you handle EU VAT yourself** (decision 1.5), and on Shopify's standard plans you **can't put a required tick box inside Shopify's checkout**: Shopify says required custom fields in checkout need Shopify Plus. The workaround (a tick box on the basket page, with "Buy it now" buttons turned off) is in section 4. Customers shop on Shopify, not on this HTML site (section 7, Path A), so you'd pick a Shopify theme and style it like the preview.
   - *Etsy*: listing and selling fees, and your products sit next to competitors'. **Etsy collects and pays the VAT on digital items** for buyers in the countries it lists (its help page "How VAT Works on Digital Items"; check the UK and EU are on the list), and Etsy's seller handbook says buyers of digital downloads tick a box giving up their right to cancel before they pay. Check you see the tick box in a test purchase.
   - *Gumroad*: says it is the **merchant of record** and collects and pays EU and UK VAT on digital sales for you. It isn't confirmed whether its checkout asks for the cancellation agreement in section 4. Ask Gumroad before choosing it; if it doesn't, you'd have to honour the 14 days (section 4, "If you can't get the tick box working").
   - **The basket on this site doesn't carry over** to any of them. Setting `checkoutUrl` only sends people to your shop's front page with an empty basket. See section 7.
   - Plain view: Etsy or Gumroad means the least admin and the least legal set-up, because they deal with EU VAT and (on Etsy) the tick box. Shopify gives you your own shop but leaves those two jobs to you. If you choose Shopify, budget for an hour with an accountant on decision 1.5.

4. **Licence: what buyers may do with the files.** Personal use only (print and use or give as a gift), or small-business use too (for example, printing cards to sell)? Either way, say what isn't allowed, such as reselling or sharing the files. This one answer goes in three places: the site FAQ "Can I print the designs?", every product description (`LICENCE` in `tools/build_csv.py`, or in Shopify), and your Shopify terms of service or Etsy/Gumroad listing.

5. **Selling to customers in the EU (VAT). Take this to an accountant; don't decide it alone.** What's been checked:
   - A download sold to an EU consumer is taxed in **the customer's EU country**, at that country's VAT rate.
   - For a business **not established in the EU** (a UK shop), there is **no threshold**: VAT is due from the first EU sale. (The EU's €10,000 threshold only applies to sellers based in the EU.)
   - The usual way to pay it is the EU's **non-Union One Stop Shop (OSS)**: register in one EU country you choose and file one quarterly EU VAT return there. The alternative is registering in every EU country you sell to.
   - This applies **even if you're not UK VAT-registered**.
   - What each route means for you:
     - *Etsy*: Etsy collects and pays the VAT on digital items for the buyer countries it lists. You don't add VAT to your prices.
     - *Gumroad*: says it collects and pays EU and UK VAT as merchant of record.
     - *Shopify*: **you** register (non-Union OSS or per country), then switch on "Charge VAT on digital goods" (step 5.1) and file the returns. Shopify's own help pages are muddled on this for UK shops. One says a UK seller of digital goods needs non-Union OSS. Another says OSS registrations "don't apply" when your fulfilment location is outside the EU and points to registering in each EU country. Its admin also has no separate non-Union OSS option. Ask the accountant and Shopify support how to set it up before you sell to anyone in the EU.
   - Also ask the accountant: whether to keep one price everywhere (EU VAT rates differ, so what you keep would vary by country) and whether you can or should sell to UK customers only at first.

6. **File formats and sizes.** For each product, decide the file type (for example PDF), the page sizes (for example A4, or A4 and US Letter), how many files and pages, and what a buyer needs to open them (for example any PDF reader). The law says you must tell buyers what the files need to work before they buy. The answers fill the "Formats and sizes" placeholders (section 3) and `FORMATS` in `tools/build_csv.py`. If formats differ between products, the site needs a small change, because the product pop-up shows one line for all of them (section 3, row 19).

7. **Product facts.** Each description must match the real file. A file that isn't as described gives the customer a legal remedy. Check:
   - What each planner and journal contains (brain dump, top 3, time blocks, wins log, habit tracker, meal and movement planner, budget and net-worth trackers, room-by-room checklists, and so on) and that they're undated where the site says so.
   - The counts: five card designs in the Birthday Card Collection, three prints in the Soft Botanicals Trio, twelve tags in three designs in the Posy Gift Tags, twelve months in the Bloom Calendar 2027.
   - The Focus Day Planner's **Cover** choice (Charcoal bloom, Blush bloom) needs two real files. If you only make one, remove the option in `assets/js/products.js` and in Shopify.
   - "Designed with ADHD brains in mind. Not a medical product." stays. Don't add any claim that a planner treats or helps a condition.
   - The **Bloom Calendar 2027** is now a download like everything else, so there's no dispatch date to set. It's only worth selling until early 2027: put a reminder in to take it down, or make a 2028 one.

8. **Newsletter provider.** On Shopify, Shopify Email keeps subscribers with your customers. Otherwise Mailchimp, Kit or Formspree. Name the provider in Privacy, and only email people who signed up.

9. **Name check.** Search the UK trade mark register (gov.uk, "search for a trade mark") and Companies House for "Grace & Bloom" before you spend money on branding.

## 2. Accounts to set up
- **Domain name and business email** on that domain. The email goes on the site and in the order emails.
- **Shopify** (with Shopify Payments and/or PayPal connected) **and its free Digital Products app**; or an **Etsy** seller account; or a **Gumroad** account.
- The **newsletter provider** from step 1.8.
- **HMRC**: register as self-employed, or set up a limited company at Companies House. Register for UK VAT only if step 1.2 says you must (or you choose to). Open a separate bank account for the shop.
- **EU VAT** (non-Union OSS or per-country registration), only if decision 1.5 says you need it. Do this with the accountant, before the first EU sale.
- **ICO**: check on ico.org.uk whether you need to pay the data protection fee. Shops that keep customer details usually do.

No courier or postage account is needed.

## 3. Answer every placeholder

These are all the highlighted placeholders on the site as of 13 October 2026. On Path A (section 7) the answers go into your Shopify policies, pages and product descriptions; on Path B, into the site files. Rows 1 to 18 are in `index.html`; row 19 is in `assets/js/shop.js`.

| # | File, section | On the page now | Put there |
|---|---|---|---|
| 1 | `index.html`, FAQ "What will I receive?" | `[confirm formats and sizes]` | File type and page sizes (decision 1.6), e.g. "PDF, A4". If they differ by product, say "listed on each product". |
| 2 | `index.html`, FAQ "How do I get my files?" | `[explain how: order page, email link, or both]` | How your checkout delivers files. Shopify Digital Products: a download email, plus a download link on the order page if you add its block (step 5.4). Etsy or Gumroad: what you see in your test purchase. At launch also reword "This is a preview, so nothing can be bought yet. When the shop opens," |
| 3 | `index.html`, FAQ "Can I print the designs?" | `[State what you may do with the files: personal use only, or small-business use, and what isn’t allowed, such as reselling.]` | Your licence wording (decision 1.4) |
| 4 | `index.html`, Digital delivery | `[explain how: on the order confirmation page, by email, or both]` | Same answer as row 2 |
| 5 | `index.html`, Digital delivery | `[file formats]` | The file type and what opens it, e.g. "PDF files (any PDF reader)" |
| 6 | `index.html`, Digital delivery | `[email@example.com]` | Shop email |
| 7 | `index.html`, Refunds & cancellations | `[Checkout must ask for this agreement and confirm it afterwards. Have this wording checked before you trade.]` | Delete it only when section 4 works on your checkout and someone qualified has checked the wording |
| 8 | `index.html`, Refunds & cancellations | `[email@example.com]` | Shop email |
| 9 | `index.html`, Model cancellation form | `[Registered business name]`, `[trading address]`, `[email@example.com]` | Legal name, trading address, shop email |
| 10 | `index.html`, Privacy | `[Registered business name]` | Legal name |
| 11 | `index.html`, Privacy | `[period]` | How long you keep order records. HMRC sets a minimum: see gov.uk "keeping records for your business" |
| 12 | `index.html`, Privacy | `[payment provider]` | Shopify Payments, PayPal, Etsy or Gumroad |
| 13 | `index.html`, Privacy | `[email@example.com]` | Shop email |
| 14 | `index.html`, footer Business details | `[registered business name, or owner’s full name if a sole trader]` | Legal name |
| 15 | `index.html`, footer | `[Trading address]`, `[town]`, `[postcode]` | Full trading address |
| 16 | `index.html`, footer | `[email@example.com]`, `[phone number]` | Shop email and phone |
| 17 | `index.html`, footer | `[If a limited company: Registered in England and Wales, company no. [number]. Registered office: [address].]` | Fill it in if you're a company, otherwise delete the whole bracket |
| 18 | `index.html`, footer | `[If VAT-registered: VAT no. GB[number].]` | Fill it in only if you're UK VAT-registered (step 1.2), otherwise delete it |
| 19 | `assets/js/shop.js`, product pop-up (every product) | `Formats and sizes: [to confirm].` | Same answer as row 1. It's one line shared by all 19 products. If formats differ, the site needs a per-product field: ask whoever looks after the site |

**In the Shopify descriptions** (from `products-shopify.csv`) every product also has three placeholders: `Formats and sizes: [to confirm]`, `How you get your files: [to confirm: …]` and `What you may do with the files: [to confirm: …]`. Easiest: give the answers to whoever looks after the site. They put them in `FORMATS`, `HOW_YOU_GET_FILES` and `LICENCE` at the top of `tools/build_csv.py`, rebuild the CSV, and you import that. Otherwise edit each description in Shopify by hand.

When you've finished, search the site files for `[`. The only brackets left should be in code.

## 4. The cancellation rule: must work before the first sale

**What the law says.** Online customers normally have 14 days to cancel. For digital content (a download), the 14 days start the day after the order. The right ends once the download starts, but **only if, before buying, the customer both:**
- **(a)** gave **express consent** to getting the download straight away, and
- **(b)** **acknowledged** that they lose their right to cancel once it starts.

Then, after the order, **you must confirm both on a "durable medium"**, which includes email. That's the Consumer Contracts (Information, Cancellation and Additional Charges) Regulations 2013: regulation 37(1) and (2) for (a), (b) and the right ending, and regulation 16(3) for the confirmation. If the customer didn't consent, didn't acknowledge, or **you didn't send that confirmation**, then if they cancel, regulation 37 says they **pay nothing** for what they downloaded during the 14 days. You must also tell buyers before they pay when they lose the right (Schedule 2), which the site's Refunds section and every product description do.

**What the checkout must show.** A tick box the customer must tick before they can pay. It must **not** be ticked already. Suggested wording (have it checked):

> ☐ Please make my download available straight away. I understand that once the download starts, I lose my 14-day right to cancel.

How to get it on each route:
- **Shopify (not Plus).** A required tick box *inside* Shopify's checkout needs Shopify Plus. On other plans:
  1. Put the required tick box on the **basket (cart) page**, with a theme edit or a "terms checkbox" app.
  2. Make sure it blocks **every** way to pay, including any express-pay buttons on the basket page.
  3. Turn off "Buy it now" on product pages: Online Store › Themes › Customize › Product pages › untick "Show dynamic checkout buttons". Shopify says those buttons skip the basket, so customers using them would never see your tick box.
  4. Have the tick saved onto the order (an order note or attribute) so you can prove each customer agreed.
  5. Ask whoever builds it, or someone qualified, to confirm this setup meets the rule.
- **Shopify Plus.** Use a required checkbox field in checkout (Checkout Blocks custom field).
- **Etsy.** Etsy's seller handbook says buyers tick a box for digital downloads. Check you see it in your test purchase, and say in each listing that the right to cancel ends once the download starts.
- **Gumroad.** Not confirmed. Ask Gumroad.

**What the order email must say.** On Shopify, add this to **Settings › Notifications › Customer notifications › Order confirmation** (Edit code), and to the "digital product ready" email in **Apps › Digital Products › Settings**:

> You asked for your files to be available straight away and confirmed you understood that your 14-day right to cancel ends once your download starts. If a file is faulty, can't be opened or isn't as described, email us at [shop email]. Your rights under the Consumer Rights Act 2015 are not affected.

Only send that sentence if the tick box really is enforced. Regulation 16 also sets out what else the order confirmation must contain. It couldn't be read in full for this guide, so have the whole email checked along with the tick-box wording. Make sure it shows at least your business name and contact details, what was bought, the price, and a link to your refund policy.

**If you can't get the tick box working:** don't pretend it's there. Keep the 14-day right and refund anyone who cancels within 14 days of ordering, even after downloading. Then change the wording to match in three places: the site's Refunds and FAQ, the order email, and the "Cancelling" paragraph in every product description. For whoever looks after the tools: that paragraph is `CANCEL_TEXT` in `build_csv.py`, and the expected wording in `validate_csv.py` changes with it.

**Faulty files: always applies.** Under the Consumer Rights Act 2015, digital content must be of **satisfactory quality**, **fit for purpose** and **as described** (sections 34 to 36). If it isn't, the customer can ask for a **repair or replacement** (section 43). If that can't be done or doesn't fix it, they're owed a **price reduction**, which can be up to a full refund (section 44). Nothing you write can take those rights away.

## 5. Shopify set-up and import (if you chose Shopify)
1. Set up **Settings** first.
   - Store currency: **GBP**.
   - **UK VAT (step 1.2).** Every price in the CSV is the final price the customer pays, the same as on the site.
     - *Not UK VAT-registered:* don't set up VAT collection for the United Kingdom (Settings › Taxes and duties). The price shown is the price. "Charge tax: TRUE" in the CSV does nothing until VAT collection is on.
     - *UK VAT-registered:* Settings › Taxes and duties › United Kingdom › Collect VAT, and enter your VAT number. Then make sure prices include tax: the setting is "Include sales tax in product price and shipping rate" (older help pages call it "All prices include tax"). If it's off, Shopify adds 20% on top. Shopify's help pages "Setting up UK taxes" and "Include taxes in product prices" show the current screens.
   - **EU VAT (decision 1.5), only once you're registered:** Settings › Taxes and duties › tick **Charge VAT on digital goods**. Shopify then makes a collection called "Digital Goods VAT Tax"; put every product in it. Get the registration set up with your accountant and Shopify support first.
   - **No shipping set-up is needed**: nothing is posted.
   - Policies (Settings › Policies): the Refunds & cancellations text and model cancellation form into the refund policy, with the placeholders filled in. Your licence (1.4) into the terms of service. Business details into contact information.
2. **Install the Digital Products app** (free, made by Shopify; search the Shopify App Store for "Digital Products". Some older Shopify pages call it "Digital Downloads").
3. **Import the CSV.** Go to **Products › Import** and choose `products-shopify.csv`.
   - It brings in **19 products and 20 variants** (the Focus Day Planner has two covers). They arrive as **draft**, not on the online store, with **Requires shipping off**, **no weight** and **stock not tracked** (a download never runs out, so it never shows as sold out). Prices match the site to the penny.
   - The file follows Shopify's current product CSV template (help.shopify.com › Using CSV files to import and export products). If Shopify rejects a column name, export one product from your store and compare the headers.
   - **If you imported the earlier physical-products file before**, delete those draft products first. Several products had different sizes and options then.
4. **Attach the files.**
   - In **Apps › Digital Products**, add each file to its product, and to each cover of the Focus planner. You can add several files, or one .zip. Shopify's help shows the current steps.
   - Leave delivery on **send automatically** (the default). Then the files go out, and the order is marked fulfilled, as soon as payment is taken.
   - In the app's Settings, add the **Digital Products block to the Thank you and Order status pages**, so buyers get a download link there as well as by email. Without the block they only get the email.
   - Optional: set a download limit per link.
5. For each product:
   - Check the Shipping section says it isn't a physical product.
   - Fill in the three description placeholders (section 3) and correct any product fact from step 1.7.
   - Add **mock-up pictures with alt text** (section 6).
   - The **Product category** is set to Shopify's "Media > Printables" categories, which suit printables. Change it if Shopify suggests something better.
6. Make **automated collections** by product type: Cards, Prints, Keepsakes, Journals & Planners, Self-Help.
7. Set up the **basket tick box, turn off "Buy it now"** and **edit the two emails** (section 4).
8. **Test purchase that really downloads a file.**
   - Use Shopify's test mode (see Shopify Help, "placing a test order"). Buy one product and the Blush cover of the Focus planner.
   - Check:
     - (a) you can't reach payment without ticking the box;
     - (b) there's no "Buy it now" way round it;
     - (c) the order shows the tick was recorded;
     - (d) the order email and the download email arrive and contain the cancellation sentence;
     - (e) the download link works from the email and from the order page;
     - (f) **the files open, are the right design and cover, and print at the size you claim**.
   - If a test-mode order doesn't send the file, buy the cheapest item with a real card and refund it. Payment fees may not come back on a refund.
9. Only then set each product to **Active** and publish it to the Online Store.

Note: Shopify lets a customer change the quantity, while this site sells each design once. If your theme can hide the quantity box on product pages, hide it; otherwise refund any accidental duplicates.

## 5b. Etsy or Gumroad instead
- `products-shopify.csv` is for Shopify only. On Etsy or Gumroad you create the 19 listings by hand. The Focus planner's two covers become a choice on one listing, or two files.
- Use the same name, price and wording as the site. The CSV's Description column has each product's full text, including the digital-download and cancellation wording. Open the CSV in a text editor, not Excel, which can garble £ and curly quotes.
- **Etsy:** sell each item as an **automatic (instant) download** with the file uploaded to the listing. Don't email files by hand. An older Etsy guide says its VAT collection on digital items doesn't cover items delivered by email.
- Put your licence (1.4) and "your right to cancel ends once the download starts" in each listing and in your shop policies.
- **Test purchase:** do the same checks as step 5.8 (tick box, emails, the download opens and is the right file). If Etsy won't let you buy from your own shop, ask a friend to buy one cheap item, then refund it.
- For the HTML site to send people to the right listing, see section 7, Path B.

## 6. Still needed: real files and real pictures
- **The files themselves** for all 19 products, plus both Focus covers. That's every card design (five in the Birthday Collection), every print (three in the Trio) and twelve gift tags. Open and print each one before it goes on sale: what's in the file must match the description.
- **Product pictures.** Mock-ups showing what the buyer actually gets, for all 19 products and both Focus covers.
  - If a picture shows a frame, an envelope or a printed object, say it's a digital file and those aren't included.
  - Also needed: pictures for the hero, the collections, the story, and a 1200 × 630 share picture.
  - Every picture on the site now is drawn by code. Once real ones are in, change "Pictures are illustrated previews of the artwork" in the shop intro to match.

## 7. Switch at launch (preview → live)

Pick one path, not both.

**Path A: Shopify is the shop.** Customers browse and pay on your Shopify store; this HTML site is only the model for it.
- Point your domain at Shopify. Keep the store password on until launch day (Online Store › Preferences).
- Don't put this preview on your domain. If it's online anywhere, add `<meta name="robots" content="noindex">` to `index.html` or take it down, so Google doesn't list a page saying "not taking orders". Once the shop is open, ask Ash to take down the claude.ai preview or point it at the real shop. The Path B edits don't apply.
- Copy the words across with the placeholders filled in: Digital delivery and FAQ into pages; Refunds & cancellations and the model form into the refund policy; licence into the terms of service; business details into contact information. The story becomes a page.
- Rewrite Privacy for Shopify. Shopify and its checkout set their own cookies, so:
  - turn on Shopify's cookie banner;
  - name your payment provider;
  - drop "no tracking" and anything else that isn't true there.
- Newsletter: Shopify Email and your theme's sign-up form.

**Path B: keep this HTML site as the shop front** (Etsy, Gumroad or Shopify behind it).
- **The catch.** The site has one checkout link for the whole basket (`checkoutUrl` in `assets/js/products.js`). Setting it only sends people to your shop's front page with an empty basket, and they must find and add everything again. Don't launch like that.
  - Each product needs to reach its own listing: an Etsy or Gumroad link per product, or a Shopify "cart permalink" that carries the basket across.
  - Today `etsyUrl` only adds "Also available on Etsy" in the product pop-up.
  - Either way it needs a small code change: ask Ash.
- **Preview notices.**
  - Remove `<b>Preview</b> · we’re not taking orders yet` from the top bar; keep "Everything here is a digital download".
  - Remove "Preview: not taking orders yet." from the footer.
  - Remove "Shop preview: not taking orders yet." from the `description` and `og:description` tags in `index.html`.
- **Wording.** Put these into the present tense:
  - FAQ "How do I get my files?": "This is a preview, so nothing can be bought yet. When the shop opens, …"
  - Digital delivery: "This is a preview, so there is nothing to deliver yet. When the shop opens:"
- **Newsletter.** Paste the provider's form URL into `newsletterAction` in `products.js`, then delete "Sign-ups open soon." from the newsletter section.
- **Privacy.** Rewrite the first paragraph ("This is a preview. It takes no orders…"), put "When we start trading" into the present tense, and say who handles checkout and that they set their own cookies.
- **Search engines.** The preview has no `noindex` tag and no `robots.txt`. Add `<meta name="robots" content="noindex">` while it's online before launch; remove it on launch day.
- **Link previews.** Once the domain is known, add `og:url`, an `og:image` (1200 × 630) and `twitter:card` = `summary_large_image`.
- **Badges.** Review "New" (Focus planner, and the "New · Journals & planners" heading), "Seasonal" (Christmas card) and "Bundle", and remove "New" after about 3 months.

## 8. Site wording to fix before launch
These are on the preview site itself. Whoever edits the site should fix them:
1. **"Your right to cancel ends once your download starts"** (Refunds section and the FAQ "Can I get a refund?") is only true once section 4 is in place: a required tick box on every route to payment, plus the confirmation email. Until then, say customers have 14 days to cancel.
2. **The FAQ says a faulty file gets "a repair, replacement or refund".** For digital content the Consumer Rights Act 2015 gives repair or replacement first, then a price reduction, which can be a full refund. There's no straight right to reject. Reword to match.
3. **"Formats and sizes: [to confirm]"** is written into `assets/js/shop.js` once for every product. If formats differ between products, add a field per product in `products.js`.
4. **Some pictures still look like physical products.** The calendar has binding rings and a hook, and the hero's screen-reader label says "a framed print". Add a short "digital file" note near the product pictures.
5. **"Each design is bought once"** is only how this site's basket works. Shopify and Etsy allow quantities, so either match that or say so.

## Sources

Checked on 13 October 2026. legislation.gov.uk, gov.uk, help.shopify.com, Etsy, Gumroad and the EU sites couldn't be opened directly from here, so these were read through search results limited to those sites ("via search"). Re-read the live pages before relying on the exact wording. The Shopify taxonomy was downloaded directly.

- Consumer Contracts Regulations 2013 (SI 2013/3134), via search:
  - regulation 37: https://www.legislation.gov.uk/uksi/2013/3134/regulation/37
  - regulation 16: https://www.legislation.gov.uk/uksi/2013/3134/regulation/16
  - full PDF: https://www.legislation.gov.uk/uksi/2013/3134/pdfs/uksi_20133134_en.pdf
- Government guidance on those Regulations (BIS), via search: https://assets.publishing.service.gov.uk/media/5a817b92ed915d74e33fe73a/bis-13-1368-consumer-contracts-information-cancellation-and-additional-payments-regulations-guidance.pdf
- Trading Standards Business Companion, distance sales, via search: https://www.businesscompanion.info/en/quick-guides/distance-sales/consumer-contracts-distance-sales
- Consumer Rights Act 2015, via search:
  - section 34: https://www.legislation.gov.uk/ukpga/2015/15/section/34
  - section 42: https://www.legislation.gov.uk/ukpga/2015/15/section/42
  - section 43: https://www.legislation.gov.uk/ukpga/2015/15/section/43
  - digital content chapter: https://www.legislation.gov.uk/ukpga/2015/15/part/1/chapter/3
  - Explanatory Notes: https://www.legislation.gov.uk/ukpga/2015/15/notes/division/3/1/4
- UK VAT threshold £90,000, via search: https://www.gov.uk/register-for-vat and https://www.gov.uk/how-vat-works/vat-thresholds
- UK guidance on digital services to EU consumers, via search (older, still refers to MOSS): https://www.gov.uk/guidance/the-vat-rules-if-you-supply-digital-services-to-private-consumers
- EU One Stop Shop (non-Union scheme; no threshold for non-EU sellers), via search:
  - https://vat-one-stop-shop.ec.europa.eu/one-stop-shop_en
  - Commission explanatory notes: https://vat-one-stop-shop.ec.europa.eu/system/files/2021-07/vatecommerceexplanatory_notes_28102020_en.pdf
  - https://europa.eu/youreurope/business/finance-and-tax/vat/one-stop-shop/index_en.htm
- Shopify Help Center, via search:
  - Digital Products app: https://help.shopify.com/en/manual/products/digital-service-product/digital-downloads
  - product CSV: https://help.shopify.com/en/manual/products/import-export/using-csv
  - common import issues: https://help.shopify.com/en/manual/products/import-export/common-import-issues
  - tax on digital products: https://help.shopify.com/en/manual/taxes/tax-on-digital-products
  - EU tax set-up: https://help.shopify.com/en/manual/taxes/eu/eu-tax-setup
  - checkout custom fields (Plus): https://help.shopify.com/en/manual/checkout-settings/checkout-blocks/blocks/create-block/custom-field
  - dynamic checkout buttons: https://help.shopify.com/en/manual/online-store/dynamic-checkout
  - notification templates: https://help.shopify.com/en/manual/fulfillment/setup/notifications/customizing-notification-template
  - product category: https://help.shopify.com/en/manual/products/details/product-category
- Shopify Standard Product Taxonomy, release v2026-08, downloaded: https://github.com/Shopify/product-taxonomy (dist/en/categories.txt)
- Etsy, via search:
  - How VAT Works on Digital Items: https://help.etsy.com/hc/en-gb/articles/115015587567-How-VAT-Works-on-Digital-Items
  - right of withdrawal: https://www.etsy.com/uk/legal/policy/eu-directive-on-consumer-rights-right-of/242644519829
  - seller handbook: https://www.etsy.com/es/seller-handbook/article/what-etsy-sellers-should-know-about-the/22504428267
  - older handbook post on EU digital sales and automatic downloads: https://www.etsy.com/seller-handbook/article/22848011323
- Gumroad, via search:
  - EU & UK VAT: https://help.gumroad.com/article/10-dealing-with-vat
  - terms: https://gumroad.com/terms

## Files in this folder
- `products-shopify.csv`: the Shopify import file (19 products, 20 variants, all downloads).
- `tools/`: whoever looks after the site can rebuild and re-check the CSV whenever `assets/js/products.js` changes. Run them from inside `tools/`:
  - `python3 build_csv.py ../../../grace-and-bloom ../products-shopify.csv` rebuilds it. The answers for formats, how files arrive and the licence go in at the top of `build_csv.py`.
  - `python3 validate_csv.py ../products-shopify.csv ../../../grace-and-bloom [categories.txt]` checks the file:
    - the header against Shopify's template;
    - every price against the site, and the product count;
    - unique options;
    - no shipping, weight or stock tracking;
    - no physical wording, such as postage, envelope, gsm, giclée, A6 or delivery;
    - the cancellation wording.

    Pass Shopify's `categories.txt` (from the taxonomy link above) to check the categories too; without it that one check says SKIP.
  - Both need Python 3 and Node.js.
