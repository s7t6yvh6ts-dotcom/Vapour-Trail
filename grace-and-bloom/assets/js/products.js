/* Grace & Bloom — store settings and product catalogue.
   Edit this file to change prices, names, wording or to add products. */
window.GB = window.GB || {};

GB.config = {
  shopName: 'Grace & Bloom',
  currency: '£',
  freeShippingOver: 40,
  shippingFlat: 3.95,
  // Where "Checkout" sends people. Paste your Etsy shop (or any payment/checkout) link here.
  // e.g. 'https://www.etsy.com/shop/YourShopName'. It becomes a normal link that opens in a new tab.
  // Note: the basket here does not travel to Etsy; customers re-add items there.
  checkoutUrl: '',
  // Optional per-product Etsy link: add  etsyUrl: 'https://www.etsy.com/listing/...'  to any product below.
  // Optional: a Formspree / Mailchimp / ConvertKit form endpoint for the email sign-up box.
  // Leave empty until it's set up: the form then says honestly that sign-ups open soon.
  newsletterAction: ''
};

GB.categories = [
  { id: 'cards',     label: 'Cards',               blurb: 'Birthdays, Christmas & every little moment', rep: 'peony-birthday' },
  { id: 'prints',    label: 'Prints',              blurb: 'Soft florals for walls that feel like home', rep: 'dusk-dahlia' },
  { id: 'keepsakes', label: 'Keepsakes',           blurb: 'Small things to hold on to',                 rep: 'pressed-bookmark' },
  { id: 'journals',  label: 'Journals & Planners', blurb: 'ADHD-friendly, weekly, wonderfully calm',    rep: 'focus-planner' },
  { id: 'selfhelp',  label: 'Self-Help',           blurb: 'Gym, home, money — build the life you want', rep: 'money-planner' }
];

/* kind: card | print | journal | pad | calendar | bookmark
   art:  palette, bloom (peony|daisy|anemone|dahlia|sweetpea), layout, text lines */
GB.products = [
  {
    id: 'peony-birthday', name: 'Peony Birthday Card', cat: 'cards', kind: 'card', price: 4.5,
    blurb: 'A hand-painted blush peony on heavyweight textured card, left blank inside for your own words. Comes with a soft grey envelope.',
    details: ['A6 · 105 × 148 mm', '350gsm textured card', 'Blank inside', 'Soft grey envelope included'],
    variants: { label: 'Finish', options: [['Standard', 0], ['Gold foil edge', 1.5]] },
    art: { palette: 'blush', bloom: 'peony', layout: 'bouquet', text: ['Happy', 'Birthday'] }
  },
  {
    id: 'sweetpea-thanks', name: 'Sweet Pea Thank You Card', cat: 'cards', kind: 'card', price: 4.25,
    blurb: 'Dreamy lilac sweet peas for the people who deserve a proper thank you.',
    details: ['A6 · 105 × 148 mm', '350gsm textured card', 'Blank inside', 'Soft grey envelope included'],
    art: { palette: 'lilac', bloom: 'sweetpea', layout: 'bouquet', text: ['Thank', 'You'] }
  },
  {
    id: 'winter-bloom-xmas', name: 'Winter Bloom Christmas Card', cat: 'cards', kind: 'card', price: 4.5,
    badge: 'Seasonal',
    blurb: 'Frosted hellebores and winter berries — a quiet, timeless take on the Christmas card.',
    details: ['A6 · 105 × 148 mm', '350gsm textured card', 'Blank inside', 'Sold singly or in sets of 10'],
    variants: { label: 'Quantity', options: [['Single card', 0], ['Set of 10', 28]] },
    art: { palette: 'frost', bloom: 'anemone', layout: 'bouquet', text: ['Merry', 'Christmas'], berries: true }
  },
  {
    id: 'anemone-thinking', name: 'Anemone Thinking of You Card', cat: 'cards', kind: 'card', price: 4.25,
    blurb: 'Dusty blue anemones with an inky centre. For the cards that are really hugs.',
    details: ['A6 · 105 × 148 mm', '350gsm textured card', 'Blank inside', 'Soft grey envelope included'],
    art: { palette: 'blue', bloom: 'anemone', layout: 'bouquet', text: ['Thinking', 'of You'] }
  },
  {
    id: 'birthday-collection', name: 'Birthday Card Collection (Set of 5)', cat: 'cards', kind: 'card', price: 19,
    blurb: 'Five different bloom designs, boxed and ribbon-tied — always have the right card ready.',
    details: ['5 × A6 cards', 'Kraft keepsake box', 'Blank inside', 'Envelopes included'],
    art: { palette: 'peach', bloom: 'daisy', layout: 'bouquet', text: ['Celebrate', 'You'] }
  },

  {
    id: 'dusk-dahlia', name: 'Dusk Dahlia Art Print', cat: 'prints', kind: 'print', price: 14,
    badge: 'New',
    blurb: 'A moody, velvety dahlia, giclée-printed on cotton rag paper. Looks like a painting, costs like a print.',
    details: ['Giclée print on 310gsm cotton rag', 'Unframed', 'Ships flat in a rigid mailer'],
    variants: { label: 'Size', options: [['A5', 0], ['A4', 6], ['A3', 14]] },
    art: { palette: 'plum', bloom: 'dahlia', layout: 'single', text: ['Dahlia'] }
  },
  {
    id: 'wild-meadow', name: 'Wild Meadow Print', cat: 'prints', kind: 'print', price: 14,
    blurb: 'Soft sage daisies, light and airy. The easiest way to calm a room.',
    details: ['Giclée print on 310gsm cotton rag', 'Unframed', 'Ships flat in a rigid mailer'],
    variants: { label: 'Size', options: [['A5', 0], ['A4', 6], ['A3', 14]] },
    art: { palette: 'sage', bloom: 'daisy', layout: 'single', text: ['Meadow'] }
  },
  {
    id: 'birth-flower', name: 'Personalised Birth Flower Print', cat: 'prints', kind: 'print', price: 16,
    badge: 'Personalised',
    blurb: 'Every month has its flower. Tell us the birthday and we will add the bloom, the month and a name in soft lettering.',
    details: ['Personalised with a name & month', 'Giclée print on 310gsm cotton rag', 'Digital proof within 48 hours', 'Made to order: can’t be cancelled once made, unless faulty'],
    variants: { label: 'Size', options: [['A5', 0], ['A4', 6], ['A3', 14]] },
    art: { palette: 'butter', bloom: 'sweetpea', layout: 'single', text: ['Birth', 'Flower'] }
  },
  {
    id: 'botanical-trio', name: 'Soft Botanicals Trio', cat: 'prints', kind: 'print', price: 34,
    blurb: 'Three coordinating prints for a gallery wall that looks collected, not bought in one go.',
    details: ['Set of 3 prints', 'Giclée on 310gsm cotton rag', 'Unframed'],
    variants: { label: 'Size', options: [['A5', 0], ['A4', 14]] },
    art: { palette: 'blush', bloom: 'anemone', layout: 'single', text: ['Botanicals'] }
  },

  {
    id: 'pressed-bookmark', name: 'Pressed Bloom Bookmark', cat: 'keepsakes', kind: 'bookmark', price: 3.95,
    badge: 'Stocking filler',
    blurb: 'A slim keepsake with a silk tassel. Tuck it in a card, a book or a gift bag.',
    details: ['50 × 150 mm', 'Laminated soft-touch finish', 'Silk tassel'],
    art: { palette: 'lilac', bloom: 'daisy', layout: 'bookmark', text: [] }
  },
  {
    id: 'posy-gift-tags', name: 'Posy Gift Tags (Set of 12)', cat: 'keepsakes', kind: 'card', price: 5.5,
    blurb: 'Tiny painted posies with natural twine. Makes anything look thoughtfully wrapped.',
    details: ['12 tags + twine', '3 designs', 'Blank on the back'],
    art: { palette: 'peach', bloom: 'peony', layout: 'bouquet', text: ['With', 'Love'] }
  },

  {
    id: 'focus-planner', name: 'Focus Day Planner · ADHD-Friendly', cat: 'journals', kind: 'journal', price: 12.5,
    badge: 'New',
    blurb: 'Made for busy, brilliant brains: one big brain-dump page, three priorities, gentle time blocks and a wins log. No guilt, no blank-page dread.',
    details: ['Undated · 90 days', 'A5 · lay-flat binding', 'Brain dump, top 3, time blocks, wins', 'Designed with ADHD brains in mind — not a medical product'],
    variants: { label: 'Cover', options: [['Charcoal bloom', 0], ['Blush bloom', 0]] },
    art: { palette: 'ink', bloom: 'anemone', layout: 'cover', text: ['Focus', 'Day Planner'], sub: 'made for busy brains' }
  },
  {
    id: 'weekly-reset', name: 'Weekly Reset Journal', cat: 'journals', kind: 'journal', price: 11,
    blurb: 'A calm Sunday-night ritual in a book: look back, plan ahead, choose three things that matter.',
    details: ['Undated · 52 weeks', 'A5 · lay-flat binding', 'Habit tracker + meal & movement planner'],
    art: { palette: 'sage', bloom: 'daisy', layout: 'cover', text: ['Weekly', 'Reset'], sub: 'plan softly, live fully' }
  },
  {
    id: 'brain-dump-pad', name: 'Brain Dump Notepad', cat: 'journals', kind: 'pad', price: 7.5,
    blurb: 'Get it all out of your head. 50 tear-off pages with space to sort what is urgent, what is not, and what can wait.',
    details: ['50 tear-off sheets', 'A5 · magnetic back', 'Sort into Now / Next / Later'],
    art: { palette: 'butter', bloom: 'daisy', layout: 'pad', text: ['Brain', 'Dump'] }
  },
  {
    id: 'wall-calendar-2027', name: 'Bloom Wall Calendar 2027', cat: 'journals', kind: 'calendar', price: 13,
    badge: 'Pre-order',
    blurb: 'Twelve months, twelve blooms, with generous date boxes. January starts the year in blush peonies.',
    details: ['Pre-order: dispatches from [date to confirm]', 'A4 · opens to A3', '12 illustrated months', 'Wire-bound with hanging hole', 'UK & US holidays marked'],
    art: { palette: 'blush', bloom: 'peony', layout: 'calendar', text: ['January'], year: 2027, month: 0 }
  },

  {
    id: 'gym-journal', name: 'Gym Progress Journal', cat: 'selfhelp', kind: 'journal', price: 10.5,
    blurb: 'Log lifts, runs, measurements and how you actually felt. Because progress is more than the number on the bar.',
    details: ['Undated · 12 weeks', 'A5 · lay-flat binding', 'Workout logs, PB page, body check-ins'],
    art: { palette: 'slate', bloom: 'dahlia', layout: 'cover', text: ['Gym', 'Progress'], sub: 'strong looks soft too' }
  },
  {
    id: 'home-reset', name: 'Home Reset Cleaning Planner', cat: 'selfhelp', kind: 'journal', price: 9.5,
    blurb: 'Tiny daily resets, a weekly deep-clean rotation and a 15-minute rescue list for when life got loud.',
    details: ['Undated · 26 weeks', 'A5 · lay-flat binding', 'Room-by-room checklists + shopping list'],
    art: { palette: 'blue', bloom: 'sweetpea', layout: 'cover', text: ['Home', 'Reset'], sub: 'calm space, calm mind' }
  },
  {
    id: 'money-planner', name: 'Money & Goals Planner', cat: 'selfhelp', kind: 'journal', price: 12,
    blurb: 'Budget, save, invest and chase the big goals. Monthly money maps, debt and savings trackers, and a 5-year vision page.',
    details: ['Undated · 12 months', 'A5 · lay-flat binding', 'Budget, savings & net-worth trackers'],
    art: { palette: 'gold', bloom: 'peony', layout: 'cover', text: ['Money &', 'Goals'], sub: 'plan it, track it, gently' }
  },
  {
    id: 'habit-pad', name: 'Habit & Wins Tracker Pad', cat: 'selfhelp', kind: 'pad', price: 7.5,
    blurb: 'Track the small things that add up. Tick, colour, celebrate — repeat.',
    details: ['50 tear-off sheets', 'A5 · magnetic back', '30-day habit grid + weekly wins'],
    art: { palette: 'lilac', bloom: 'sweetpea', layout: 'pad', text: ['Habits', '& Wins'] }
  }
];

GB.byId = function (id) { return GB.products.find(function (p) { return p.id === id; }); };

/* Search / gift-finder keywords. */
GB.tags = {
  'peony-birthday': ['birthday', 'card', 'mum', 'friend'],
  'sweetpea-thanks': ['thank you', 'card', 'teacher'],
  'winter-bloom-xmas': ['christmas', 'card', 'seasonal'],
  'anemone-thinking': ['thinking of you', 'sympathy', 'card'],
  'birthday-collection': ['birthday', 'card', 'gift', 'set'],
  'dusk-dahlia': ['print', 'wall art', 'home'],
  'wild-meadow': ['print', 'wall art', 'home'],
  'birth-flower': ['personalised', 'birthday', 'gift', 'print'],
  'botanical-trio': ['print', 'gift', 'wall art', 'home'],
  'pressed-bookmark': ['gift', 'stocking filler', 'reader', 'keepsake'],
  'posy-gift-tags': ['gift wrap', 'keepsake', 'christmas', 'birthday'],
  'focus-planner': ['adhd', 'organise', 'planner', 'focus', 'productivity'],
  'weekly-reset': ['organise', 'journal', 'weekly', 'self-care'],
  'brain-dump-pad': ['adhd', 'organise', 'notepad', 'focus'],
  'wall-calendar-2027': ['calendar', 'gift', 'home', '2027'],
  'gym-journal': ['gym', 'fitness', 'self-care', 'goals'],
  'home-reset': ['cleaning', 'home', 'organise'],
  'money-planner': ['money', 'budget', 'savings', 'goals', 'wealth'],
  'habit-pad': ['habits', 'self-care', 'organise', 'goals']
};
