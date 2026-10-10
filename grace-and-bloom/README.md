# Grace & Bloom

Static storefront for cards, prints, keepsakes, journals and planners. No build step, no framework.

- Open `index.html` in a browser to preview it (or serve the folder: `python3 -m http.server`).
- Edit prices, names and wording in `assets/js/products.js`.
- Set your checkout / Etsy link in `GB.config.checkoutUrl` (same file). It becomes a normal link that opens in a new tab. Until it's set, "Checkout" shows an in-basket note that the shop is a preview. The basket here does not carry over to Etsy.
- Set `GB.config.newsletterAction` to a Formspree/Mailchimp form URL to make the email box live. Until then the form says sign-ups open soon and stores nothing.
- All artwork is painted in code (`assets/js/art.js`); swap in real product photos before trading.
- Light and dark themes follow the visitor's device, with a toggle in the header. Every colour is a token at the top of `assets/css/styles.css`.

## Before taking real orders
Everything in `[square brackets]` on the page (highlighted) must be filled in or removed:
- Business details in the footer: legal name, trading/returns address, email, phone; company number and registered office if it's a limited company; VAT number if VAT-registered.
- Delivery: countries served, how many working days to pack an order (shown as [1–3] in the FAQ and Delivery section), carrier and service, typical delivery time, pre-order dispatch date for the 2027 calendar (also in `products.js`).
- Returns: confirm who pays return postage.
- Privacy: payment provider and how long order data is kept.
- Remove the "Preview · we're not taking orders yet" bar and footer note once checkout and payments really work.
- Badges and labels: review every "New" and "Seasonal" badge (`badge:` in `products.js`) and the "New · Journals & planners" heading at launch, and take "New" off after a set period (say 3 months). A "New" label left up for ever becomes misleading.
- Prices: a product with options that cost more shows "From £x" in the grid. Check every price, and keep them VAT-inclusive.

## Putting it online
- **Netlify Drop (fastest):** go to https://app.netlify.com/drop and drag the `grace-and-bloom` folder (or the zip) onto it.
- **GitHub Pages:** merge to `main`, then Settings → Pages → Source: GitHub Actions. The included workflow publishes this folder.
- Point your own domain (e.g. graceandbloom.co.uk) at either from the host's domain settings.
