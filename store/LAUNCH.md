# Vapour Trail store: launch in an afternoon

Why WooCommerce and not Shopify: Shopify has banned vapes worldwide since July 2026, and stores that list them get shut down. WooCommerce runs on your own hosting, so no platform can switch you off. AgeChecked and the UK high-risk card processors all have plugins for it.

**What you pay for:** hosting with a domain, about £3–£10 a month. WooCommerce itself is free. Age checks cost a few pence each.

**What's ready in this folder:**
- `products.csv`: your product list in WooCommerce's import format. Everything imports as a draft, so nothing goes live until you add prices.
- `pages/`: home page, terms and conditions, privacy policy, delivery and returns, and age verification policy. Card processors check that these exist before they approve you.

---

## 1. Hosting and domain (15 min, needs your card)

1. Pick a host that offers **one-click WordPress + WooCommerce**. Before you pay, read its acceptable use policy and check that it allows e-cigarette and nicotine sales.
2. Buy the domain at the same time, e.g. `vapourtrail.co.uk`. Check it's free first.
3. Choose the WooCommerce install option. Use a business email for the admin login, not your personal Gmail.

## 2. Store settings (10 min)

WooCommerce → Settings:
- **General:** selling location *United Kingdom only*, currency *£ GBP*.
- **Shipping:** add a zone "UK" with *Flat rate* (e.g. £1.55 for a large letter) and *Free shipping* above your bundle threshold (e.g. 5 tins). Use your real postage costs; `tools/margin.py` shows the effect.
- **Tax:** leave off unless you're VAT-registered (the £90k turnover threshold).
- **Accounts & Privacy:** link the privacy policy and terms pages from step 4.

## 3. Products (10 min)

1. Products → **Import** → upload `products.csv` → *Run the importer*.
2. Open each product, add **price, stock, photos**, then press **Publish**.
3. Only list what's UK-legal: refillable kits (2 ml tank, 20 mg/ml max, MHRA-notified), pouches and accessories. **No disposables, no tobacco without duty paid, no peptides.**

## 4. Pages (10 min)

Pages → Add New, once for each file in `pages/`. Paste the text in and replace every `[BRACKET]` with your details. Then:
- Settings → Reading → set **Home page** to the home page.
- Add the four policy pages to the footer menu (Appearance → Menus).

## 5. Age verification (10 min) — legally required for pouches from 29 Oct 2026

1. Plugins → Add New → search **AgeChecked** (or **Token of Trust** / **Yoti**) → install → activate.
2. Create an account with them and paste your API key into the plugin.
3. Set it to check **every product**.
4. Turn on an **18+ age gate** popup as well (the same plugins do it). The popup alone doesn't count; the real check happens at checkout.

## 6. Payments

1. With the site live (even with no products published yet), apply for a **high-risk merchant account** that approves vape/nicotine in writing. Brokers are listed in `../PLAYBOOK.md`. They'll want your URL, the policy pages, and proof of age checks.
2. Install the WooCommerce plugin they give you.
3. **Don't** use Stripe, PayPal or Square for nicotine. They freeze accounts after approval.
4. While you wait for approval (usually 6–8 weeks), go to **WooCommerce → Settings → Payments**, switch on **Direct bank transfer**, and add your account details. In the instructions box, write: "Use your order number as the reference. We dispatch as soon as the payment lands." Turn it off once card payments are live, or keep it as a second option.

## 7. Test and go live

- Place a test order on your phone and check that the age check fires, the postage is right and the confirmation email arrives.
- Register with the **ICO** (the data protection fee, a small annual fee). It's required because you store customer data.
- Post the link in your Telegram channel.
