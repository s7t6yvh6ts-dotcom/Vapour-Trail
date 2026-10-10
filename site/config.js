// Edit this file to set up the shop. No other code changes needed.
// Anything in [square brackets] is a placeholder: replace it before the shop opens.
// Placeholders show up highlighted on the page so none get missed.
window.SHOP = {
  name: "Second Rail",
  tagline: "New drops and vintage finds.",
  currency: "£",

  // Delivery (UK only). Shown on every product, in the basket and in the footer.
  shipping: 3.95,
  freeShippingOver: 100,
  dispatch: "[within N working days]",
  courier: "[delivery service, e.g. Royal Mail Tracked 48]",

  // "Only 2 left in this size" comes from the stock counts in products.json.
  // Leave this on only while those counts are real and kept up to date: urgency
  // that isn't true is banned (DMCC Act 2024). If a piece also sells somewhere
  // else (Depop, Vinted, a market stall), set it to false until stock syncs.
  lowStockMessages: true,

  // Who pays to post a change-of-mind return. If the page doesn't say the
  // customer pays, the law says we do. Faulty returns are always on us.
  returnPostage: "[you / us: pick one]",

  // Checkout. Leave empty to keep the preview's "nothing is charged" message.
  // A single payment link can't see what's in the basket, so it only works for
  // a fixed amount. For real orders this needs a checkout that receives the
  // basket (clothing is fine on Shopify or Stripe).
  checkoutUrl: "",
  paymentMethods: "[payment methods, e.g. debit or credit card]",
  paymentProvider: "[payment provider]",

  // Contact and trader details. The law requires these on the site.
  // Leave company or vat as "" to hide that line if it doesn't apply.
  contactEmail: "[email address]",
  trader: {
    legalName: "[registered business name, or owner’s full name if a sole trader]",
    address: "[trading address: street, town, postcode, not a PO box]",
    phone: "[phone number]",
    company: "[company name, number, registered office and where registered (e.g. England and Wales), if a limited company]",
    vat: "[VAT number, if VAT-registered]"
  }
};
