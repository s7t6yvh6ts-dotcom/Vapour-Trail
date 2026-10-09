# Grace & Bloom

Static storefront for cards, prints, keepsakes, journals and planners. No build step, no framework.

- Open `index.html` in a browser to preview it.
- Edit prices, names and wording in `assets/js/products.js`.
- Set your checkout / Etsy link in `GB.config.checkoutUrl` (same file). Until then, "Checkout" shows a preview message.
- Set `GB.config.newsletterAction` to a Formspree/Mailchimp form URL to make the email box live.
- All artwork is painted in code (`assets/js/art.js`); swap in real product photos later if you like.

## Putting it online
- **Netlify Drop (fastest):** go to https://app.netlify.com/drop and drag the `grace-and-bloom` folder (or the zip) onto it.
- **GitHub Pages:** merge to `main`, then Settings → Pages → Source: GitHub Actions. The included workflow publishes this folder.
- Point your own domain (e.g. graceandbloom.co.uk) at either from the host's domain settings.
