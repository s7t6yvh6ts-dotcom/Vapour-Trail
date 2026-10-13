# Grace & Bloom

Static storefront for cards, prints, keepsakes, journals and planners. No build step, no framework.

- Open `index.html` in a browser to preview it (or serve the folder: `python3 -m http.server`).
- Edit prices, names and wording in `assets/js/products.js`.
- Set your checkout / Etsy link in `GB.config.checkoutUrl` (same file). It becomes a normal link that opens in a new tab. Until it's set, "Checkout" shows an in-basket note that the shop is a preview. The basket here does not carry over to Etsy.
- Set `GB.config.newsletterAction` to a Formspree/Mailchimp form URL to make the email box live. Until then the form says sign-ups open soon and stores nothing.
- All artwork is painted in code (`assets/js/art.js`); swap in real product photos before trading. Pictures are painted only as they near the screen (then the rest in idle time), so the page is usable straight away.
- The 3D hero (`assets/vendor/three.min.js`, ~600 KB, plus `assets/js/hero3d.js`) never blocks the page: a painted card shows first, and the 3D scene loads after the page has finished loading and the hero is near view, then fades in. It's skipped for visitors with Data Saver on, and the painted card stays if WebGL isn't available.
- A small pause button on the hero stops the 3D scene, the scrolling word strip and the scroll cue (needed for accessibility: moving content must be pausable). Visitors who ask their device for reduced motion get a still page anyway.
- Light and dark themes follow the visitor's device, with a toggle in the header. Every colour is a token at the top of `assets/css/styles.css`.
- Without JavaScript the page says so at the top and hides the controls that can't work; delivery, returns, privacy, FAQ and business details stay readable.

## Before taking real orders
Everything in `[square brackets]` on the page (highlighted) must be filled in or removed:
- Business details in the footer: legal name, trading/returns address, email, phone; company number and registered office if it's a limited company; VAT number if VAT-registered.
- Delivery: countries served, how many working days to pack an order (shown as [1–3] in the FAQ and Delivery section), carrier and service, typical delivery time, pre-order dispatch date for the 2027 calendar (also in `products.js`).
- Returns: confirm who pays return postage.
- Privacy: payment provider and how long order data is kept.
- Remove the "Preview · we're not taking orders yet" bar and footer note once checkout and payments really work, and the "Shop preview: not taking orders yet" sentence at the end of the `description` and `og:description` tags in `index.html`.
- Link previews: once the domain is known, add `<meta property="og:url" content="https://your-domain/">` and an `og:image` (an absolute URL to a 1200 × 630 picture) so shared links show a picture, and change `twitter:card` to `summary_large_image`.
- Badges and labels: review every "New" and "Seasonal" badge (`badge:` in `products.js`) and the "New · Journals & planners" heading at launch, and take "New" off after a set period (say 3 months). A "New" label left up for ever becomes misleading.
- Prices: a product with options that cost more shows "From £x" in the grid. Check every price, and keep them VAT-inclusive.

## Putting it online
- **Netlify Drop (fastest):** go to https://app.netlify.com/drop and drag the `grace-and-bloom` folder (or the zip) onto it.
- **GitHub Pages:** merge to `main`, then Settings → Pages → Source: GitHub Actions. The included workflow publishes this folder.
- Point your own domain (e.g. graceandbloom.co.uk) at either from the host's domain settings.
