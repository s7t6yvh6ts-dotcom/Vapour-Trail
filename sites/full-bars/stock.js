/* Full Bars - stock. The one place that says which phones you hold, read by site.js on every page with cards or a
   product picker. For each phone, give its product handle (the page's name: products/iphone-13.html is "iphone-13"),
   then the number of units you hold for each storage and condition, counting every colour together (colour isn't
   tracked):
     window.FULLBARS_STOCK = {
       "iphone-13": { "128GB|Good": 2, "256GB|Very Good": 1 },
       "pixel-8": {}
     };
   - A storage and condition missing from a phone's list, or 0, is not in stock: its product page button reads
     "Not in stock — ask us".
   - A phone listed with no units at all (like "pixel-8" above) also shows "None in stock right now" on its cards.
   - A phone that isn't listed has no stock data here. Its product page then uses that page's old data-stock
     attribute if it has one (stock.js wins when both are there), or else shows every option as available, so
     go_live.py --checkout stripe won't launch until every phone is listed here or has data-stock.
   Write it as JSON: keys in double quotes, counts as whole numbers. There's no build step.
   Static (Stripe) route: you keep this file by hand. Change a count the moment a phone sells or arrives, then deploy
   the site again.
   Shopify route: Shopify counts the stock and refuses a sold-out variant, so this file never sells anything. Don't
   edit it by hand: write it from Shopify with fetch_shopify_variants.py --write-stock (GO-LIVE.md section 5, step 13),
   which counts each variant Shopify says is available, any colour counting 1. Then fetch again and deploy the site
   whenever stock changes in Shopify: straight after you add stock, and at least daily. Until you do, the snapshot is
   wrong both ways: a phone sold since still shows as in stock (its button opens a sold-out Shopify page), and a phone
   added since shows "Not in stock — ask us". Colour isn't in the key, so the colour chosen can still be sold out on
   Shopify. Left empty (as in the preview), every option shows as orderable and Shopify shows what's sold out. */
window.FULLBARS_STOCK = {
};
