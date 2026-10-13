// Reads the site's own catalogue (assets/js/products.js) in a sandbox and prints it as JSON,
// with every price worked out the way the shop shows it (shop.js).
// Usage: node load_products.cjs <path to grace-and-bloom folder>
//
// How shop.js shows prices (digital-downloads version, October 2026):
//   money(n)  = GB.config.currency + n.toFixed(2)
//   grid card, "You may also like" and the gift-tag offer: money(p.price)
//   quick view: price() = p.price + (vr ? vr.options[qv.v][1] : 0)
//   basket:     unit(l) = p.price + (p.variants ? p.variants.options[l.v][1] : 0)
// Each design is bought once, so there are no quantities to multiply by.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const site = process.argv[2];
if (!site) { console.error('usage: node load_products.cjs <site folder>'); process.exit(2); }
const src = fs.readFileSync(path.join(site, 'assets/js/products.js'), 'utf8');
// in a browser, window is the global object: products.js sets window.GB, then uses the bare name GB
const sandbox = {};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'products.js' });
const GB = sandbox.GB;
if (!GB || !Array.isArray(GB.products)) { console.error('could not read GB.products'); process.exit(1); }

const bad = GB.products.filter(p => typeof p.price !== 'number' || !(p.price > 0));
if (bad.length) { console.error('price is not a positive number for: ' + bad.map(p => p.id).join(', ')); process.exit(1); }

const out = {
  config: GB.config,
  categories: GB.categories,
  tags: GB.tags,
  products: GB.products.map(p => ({
    id: p.id, name: p.name, cat: p.cat, kind: p.kind, badge: p.badge || null, blurb: p.blurb, details: p.details,
    price: p.price,
    optionLabel: p.variants ? p.variants.label : null,
    // one row per option the quick view offers (or one row when there are none), priced as the basket adds it
    rows: (p.variants ? p.variants.options : [[null, 0]]).map(o => ({
      option: o[0], surcharge: o[1], shown: (p.price + o[1]).toFixed(2)
    })),
    // what the grid card shows: always the base price, with no "From"
    gridShown: (p.price).toFixed(2)
  }))
};
process.stdout.write(JSON.stringify(out, null, 1));
