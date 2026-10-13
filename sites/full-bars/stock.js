/* Full Bars - stock, for the static (Stripe) route. The one place to say which phones you hold.
   For each phone, give its product handle (the page's name: products/iphone-13.html is "iphone-13"), then the number
   of units you hold for each storage and condition, counting every colour together (colour isn't tracked; the
   customer's colour is confirmed by email):
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
   Write it as JSON: keys in double quotes, counts as whole numbers. Change a count the moment a phone sells or
   arrives, then deploy the site again. There's no build step.
   Shopify route: leave this empty, because Shopify counts the stock. Empty (as in the preview) changes nothing. */
window.FULLBARS_STOCK = {
};
