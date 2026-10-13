/* Grace & Bloom — store settings and product catalogue.
   Everything here is a digital download. Edit this file to change prices, names or wording.
   Details written in [square brackets] are shown highlighted on the page as things to confirm. */
window.GB = window.GB || {};

GB.config = {
  shopName: 'Grace & Bloom',
  currency: '£',
  // Where "Checkout" sends people. Paste your Etsy shop (or any payment/checkout) link here.
  // e.g. 'https://www.etsy.com/shop/YourShopName'. It becomes a normal link that opens in a new tab.
  // Note: the basket here does not travel to Etsy; customers re-add items there.
  // Nothing on this site takes payment or delivers files by itself. Those come from the checkout you connect.
  checkoutUrl: '',
  // Optional per-product Etsy link: add  etsyUrl: 'https://www.etsy.com/listing/...'  to any product below.
  // Optional: a Formspree / Mailchimp / ConvertKit form endpoint for the email sign-up box.
  // Leave empty until it's set up: the form then says honestly that sign-ups open soon.
  newsletterAction: ''
};

GB.categories = [
  { id: 'cards',     label: 'Cards',               blurb: 'Birthdays, Christmas and every little moment', rep: 'peony-birthday' },
  { id: 'prints',    label: 'Prints',              blurb: 'Soft florals for walls that feel like home',   rep: 'dusk-dahlia' },
  { id: 'keepsakes', label: 'Keepsakes',           blurb: 'Small extras to print and keep',               rep: 'pressed-bookmark' },
  { id: 'journals',  label: 'Journals & Planners', blurb: 'ADHD-friendly, weekly, wonderfully calm',      rep: 'focus-planner' },
  { id: 'selfhelp',  label: 'Self-Help',           blurb: 'Gym, home and money, to build the life you want', rep: 'money-planner' }
];

/* kind: card | print | journal | pad | calendar | bookmark   (how the artwork is previewed)
   art:  palette, bloom (peony|daisy|anemone|dahlia|sweetpea), layout, text lines */
GB.products = [
  {
    id: 'peony-birthday', name: 'Peony Birthday Card', cat: 'cards', kind: 'card', price: 4.5,
    blurb: 'A soft blush peony in full bloom, with space inside for your own words.',
    details: ['Blank inside, ready for your own message'],
    art: { palette: 'blush', bloom: 'peony', layout: 'bouquet', text: ['Happy', 'Birthday'] }
  },
  {
    id: 'sweetpea-thanks', name: 'Sweet Pea Thank You Card', cat: 'cards', kind: 'card', price: 4.25,
    blurb: 'Dreamy lilac sweet peas for the people who deserve a proper thank you.',
    details: ['Blank inside, ready for your own message'],
    art: { palette: 'lilac', bloom: 'sweetpea', layout: 'bouquet', text: ['Thank', 'You'] }
  },
  {
    id: 'winter-bloom-xmas', name: 'Winter Bloom Christmas Card', cat: 'cards', kind: 'card', price: 4.5,
    badge: 'Seasonal',
    blurb: 'Frosted hellebores and winter berries, a quiet and timeless take on the Christmas card.',
    details: ['Blank inside, ready for your own message'],
    art: { palette: 'frost', bloom: 'anemone', layout: 'bouquet', text: ['Merry', 'Christmas'], berries: true }
  },
  {
    id: 'anemone-thinking', name: 'Anemone Thinking of You Card', cat: 'cards', kind: 'card', price: 4.25,
    blurb: 'Dusty blue anemones with an inky centre. For the cards that are really hugs.',
    details: ['Blank inside, ready for your own message'],
    art: { palette: 'blue', bloom: 'anemone', layout: 'bouquet', text: ['Thinking', 'of You'] }
  },
  {
    id: 'birthday-collection', name: 'Birthday Card Collection (Set of 5)', cat: 'cards', kind: 'card', price: 19,
    badge: 'Bundle',
    blurb: 'Five different bloom designs in one bundle, so there is always a card to hand.',
    details: ['Five card designs', 'Blank inside, ready for your own message'],
    art: { palette: 'peach', bloom: 'daisy', layout: 'bouquet', text: ['Celebrate', 'You'] }
  },

  {
    id: 'dusk-dahlia', name: 'Dusk Dahlia Art Print', cat: 'prints', kind: 'print', price: 14,
    blurb: 'A moody, velvety dahlia in deep plum tones, made for a quiet corner of the wall.',
    details: ['An art print to frame and hang at home'],
    art: { palette: 'plum', bloom: 'dahlia', layout: 'single', text: ['Dahlia'] }
  },
  {
    id: 'wild-meadow', name: 'Wild Meadow Print', cat: 'prints', kind: 'print', price: 14,
    blurb: 'Soft sage daisies, light and airy. The easiest way to calm a room.',
    details: ['An art print to frame and hang at home'],
    art: { palette: 'sage', bloom: 'daisy', layout: 'single', text: ['Meadow'] }
  },
  {
    id: 'birth-flower', name: 'Birth Flower Print', cat: 'prints', kind: 'print', price: 16,
    blurb: 'A soft botanical print for a birthday, a new baby or a keepsake wall.',
    details: ['An art print to frame and hang at home'],
    art: { palette: 'butter', bloom: 'sweetpea', layout: 'single', text: ['Birth', 'Flower'] }
  },
  {
    id: 'botanical-trio', name: 'Soft Botanicals Trio', cat: 'prints', kind: 'print', price: 34,
    blurb: 'Three coordinating prints for a gallery wall that looks collected, not bought in one go.',
    details: ['A set of three prints'],
    art: { palette: 'blush', bloom: 'anemone', layout: 'single', text: ['Botanicals'] }
  },

  {
    id: 'pressed-bookmark', name: 'Bloom Bookmark', cat: 'keepsakes', kind: 'bookmark', price: 3.95,
    blurb: 'A slim floral bookmark to print, trim and tuck into a book or a card.',
    details: ['Slim format, made to be trimmed to size'],
    art: { palette: 'lilac', bloom: 'daisy', layout: 'bookmark', text: [] }
  },
  {
    id: 'posy-gift-tags', name: 'Posy Gift Tags (Set of 12)', cat: 'keepsakes', kind: 'card', price: 5.5,
    blurb: 'Tiny floral tags for presents, to print and cut out. Makes anything look thoughtfully wrapped.',
    details: ['Twelve tags in three designs', 'Blank on the back for a name or message'],
    art: { palette: 'peach', bloom: 'peony', layout: 'bouquet', text: ['With', 'Love'] }
  },

  {
    id: 'focus-planner', name: 'Focus Day Planner · ADHD-Friendly', cat: 'journals', kind: 'journal', price: 12.5,
    badge: 'New',
    blurb: 'Made for busy, brilliant brains: one big brain-dump page, three priorities, gentle time blocks and a wins log. No guilt, no blank-page dread.',
    details: ['Undated, so you can start on any day', 'Brain dump, top 3, time blocks and a wins log', 'Designed with ADHD brains in mind. Not a medical product.'],
    variants: { label: 'Cover', options: [['Charcoal bloom', 0], ['Blush bloom', 0]] },
    art: { palette: 'ink', bloom: 'anemone', layout: 'cover', text: ['Focus', 'Day Planner'], sub: 'made for busy brains' }
  },
  {
    id: 'weekly-reset', name: 'Weekly Reset Journal', cat: 'journals', kind: 'journal', price: 11,
    blurb: 'A calm Sunday-night ritual: look back, plan ahead, choose three things that matter.',
    details: ['Undated weekly pages', 'Habit tracker and a meal and movement planner'],
    art: { palette: 'sage', bloom: 'daisy', layout: 'cover', text: ['Weekly', 'Reset'], sub: 'plan softly, live fully' }
  },
  {
    id: 'brain-dump-pad', name: 'Brain Dump Pages', cat: 'journals', kind: 'pad', price: 7.5,
    blurb: 'Get it all out of your head, then sort what is urgent, what is not, and what can wait.',
    details: ['Sort into Now / Next / Later'],
    art: { palette: 'butter', bloom: 'daisy', layout: 'pad', text: ['Brain', 'Dump'] }
  },
  {
    id: 'wall-calendar-2027', name: 'Bloom Calendar 2027', cat: 'journals', kind: 'calendar', price: 13,
    blurb: 'Twelve months, twelve blooms, with generous date boxes. January starts the year in blush peonies.',
    details: ['Twelve illustrated months', 'Generous date boxes'],
    art: { palette: 'blush', bloom: 'peony', layout: 'calendar', text: ['January'], year: 2027, month: 0 }
  },

  {
    id: 'gym-journal', name: 'Gym Progress Journal', cat: 'selfhelp', kind: 'journal', price: 10.5,
    blurb: 'Log lifts, runs, measurements and how you actually felt. Because progress is more than the number on the bar.',
    details: ['Undated', 'Workout logs, a PB page and body check-ins'],
    art: { palette: 'slate', bloom: 'dahlia', layout: 'cover', text: ['Gym', 'Progress'], sub: 'strong looks soft too' }
  },
  {
    id: 'home-reset', name: 'Home Reset Cleaning Planner', cat: 'selfhelp', kind: 'journal', price: 9.5,
    blurb: 'Tiny daily resets, a weekly deep-clean rotation and a 15-minute rescue list for when life gets loud.',
    details: ['Undated', 'Room-by-room checklists and a shopping list'],
    art: { palette: 'blue', bloom: 'sweetpea', layout: 'cover', text: ['Home', 'Reset'], sub: 'calm space, calm mind' }
  },
  {
    id: 'money-planner', name: 'Money & Goals Planner', cat: 'selfhelp', kind: 'journal', price: 12,
    blurb: 'Budget, save and chase the big goals, with monthly money maps and a five-year vision page.',
    details: ['Undated', 'Budget, savings and net-worth trackers'],
    art: { palette: 'gold', bloom: 'peony', layout: 'cover', text: ['Money &', 'Goals'], sub: 'plan it, track it, gently' }
  },
  {
    id: 'habit-pad', name: 'Habit & Wins Tracker Pages', cat: 'selfhelp', kind: 'pad', price: 7.5,
    blurb: 'Track the small things that add up. Tick, colour, celebrate, repeat.',
    details: ['A habit grid and a weekly wins page'],
    art: { palette: 'lilac', bloom: 'sweetpea', layout: 'pad', text: ['Habits', '& Wins'] }
  }
];

GB.byId = function (id) { return GB.products.find(function (p) { return p.id === id; }); };

/* Search / "shop by occasion" keywords. */
GB.tags = {
  'peony-birthday': ['birthday', 'card', 'mum', 'friend'],
  'sweetpea-thanks': ['thank you', 'card', 'teacher'],
  'winter-bloom-xmas': ['christmas', 'card', 'seasonal'],
  'anemone-thinking': ['thinking of you', 'thank you', 'sympathy', 'card'],
  'birthday-collection': ['birthday', 'card', 'gift', 'set', 'bundle'],
  'dusk-dahlia': ['print', 'wall art', 'home'],
  'wild-meadow': ['print', 'wall art', 'home'],
  'birth-flower': ['birthday', 'gift', 'print', 'wall art', 'baby'],
  'botanical-trio': ['print', 'gift', 'wall art', 'home'],
  'pressed-bookmark': ['gift', 'reader', 'keepsake', 'bookmark'],
  'posy-gift-tags': ['gift wrap', 'keepsake', 'christmas', 'birthday', 'tags'],
  'focus-planner': ['adhd', 'organise', 'planner', 'focus', 'productivity'],
  'weekly-reset': ['organise', 'journal', 'weekly', 'self-care'],
  'brain-dump-pad': ['adhd', 'organise', 'notepad', 'focus'],
  'wall-calendar-2027': ['calendar', 'gift', 'home', '2027', 'wall art'],
  'gym-journal': ['gym', 'fitness', 'self-care', 'goals'],
  'home-reset': ['cleaning', 'home', 'organise'],
  'money-planner': ['money', 'budget', 'savings', 'goals', 'wealth'],
  'habit-pad': ['habits', 'self-care', 'organise', 'goals']
};
