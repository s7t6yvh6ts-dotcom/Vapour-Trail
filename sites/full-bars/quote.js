/* Full Bars - trade-in valuation (browser copy).

   This is a line-for-line port of lib/valuation.ts, with the constants copied from
   lib/pricing-config.ts, in the business app (Claude Code\phones-business).
   The repo is the source of truth. When pricing-config.ts changes, copy the same
   numbers into PRICING below, rebuild, then open private\quote-test.html: every case
   from lib/valuation.test.ts must still pass.

   The formula, under the VAT Margin Scheme:
     adjusted = basePrice x conditionFactor      (x 0.92 if network locked)
     other    = adjusted x variableRate + fixedCosts + refurbCost
     maxQuote = adjusted - 1.2 x targetMargin x adjusted - 1.2 x (other - inputVat)
     offered  = maxQuote x (1 - offerBelowCeiling)
     customer = floor(offered / 500) * 500       (ALWAYS round down)

   Why 1.2: margin-scheme VAT is (sale - purchase) / 6, so solving the net-profit
   equation for the purchase price brings in a factor of 6/5.

   Rules: money is integer pence; never quote above maxQuote; never round up;
   hard stops (activation lock, blacklisted, outstanding finance) get no price at all.
   Every quote shown on the website is provisional until the phone is inspected. */
(function (root) {
  'use strict';

  /* ---------- PRICING: copied from lib/pricing-config.ts (integer pence) ---------- */
  /* sellPrice = realistic 30-day selling price for a VERY GOOD unit, by storage. */
  var MODELS = [
    { id: 'iphone-13', name: 'iPhone 13', sellPrice: { '128GB': 23000, '256GB': 25500 }, screenRepairCost: 6200 },
    { id: 'iphone-13-pro', name: 'iPhone 13 Pro', sellPrice: { '128GB': 31000, '256GB': 34000 }, screenRepairCost: 8800 },
    { id: 'iphone-14', name: 'iPhone 14', sellPrice: { '128GB': 33000, '256GB': 36000 }, screenRepairCost: 7800 },
    { id: 'iphone-14-pro', name: 'iPhone 14 Pro', sellPrice: { '128GB': 43000, '256GB': 47000 }, screenRepairCost: 10500 },
    { id: 'galaxy-s23', name: 'Galaxy S23', sellPrice: { '128GB': 27000, '256GB': 29500 }, screenRepairCost: 8200 },
    { id: 'pixel-8', name: 'Pixel 8', sellPrice: { '128GB': 25000, '256GB': 28000 }, screenRepairCost: 7000 }
  ];

  var ECONOMICS = {
    targetMargin: 0.15,          /* net margin floor, 0.15 = 15% */
    variableRate: 0.015,         /* payment processing share of sale price */
    fixedCosts: 6070,            /* per unit, pence, excluding parts */
    inputVat: 600,               /* recoverable input VAT, pence */
    batteryCost: 2200,           /* battery replacement, pence */
    roundDownTo: 500,            /* customer quotes round DOWN to this, pence */
    networkLockedMultiplier: 0.92,
    minimumQuote: 1000,          /* below this it isn't worth the postage, pence */
    offerBelowCeiling: 0.05      /* offer 5% under the ceiling */
  };

  /* Mirrors the published grading standard (business plan section 7.3). */
  var CONDITION_FACTORS = { excellent: 1.0, verygood: 0.94, good: 0.86, fair: 0.72, faulty: 0.3 };

  /* ---------- valuation (port of lib/valuation.ts) ---------- */
  var GRADE_ORDER = ['excellent', 'verygood', 'good', 'fair'];

  /* Customer-facing words for each grade (lib/grades.ts), capitalised "Very Good" to match the shop,
     product pickers, grading page and pay.js keys. Labels only: no price depends on them. */
  var GRADE_WORDS = { excellent: 'Excellent', verygood: 'Very Good', good: 'Good', fair: 'Fair', faulty: 'Not working' };

  function getModel(id) {
    for (var i = 0; i < MODELS.length; i++) { if (MODELS[i].id === id) return MODELS[i]; }
    return undefined;
  }

  /* Cosmetic grade is the WORSE of screen and body. A cracked screen forces Fair. */
  function resolveGrade(screen, body) {
    var screenGrade = screen === 'cracked' ? 'fair' : screen;
    var worst = Math.max(GRADE_ORDER.indexOf(screenGrade), GRADE_ORDER.indexOf(body));
    var g = GRADE_ORDER[worst];
    return g === undefined ? 'fair' : g;
  }

  function blockReason(a) {
    if (a.activationLocked) return 'activation-locked';
    if (a.blacklisted) return 'blacklisted';
    if (a.outstandingFinance) return 'outstanding-finance';
    return null;
  }

  function quote(answers, econ) {
    econ = econ || ECONOMICS;
    var blocked = blockReason(answers);
    if (blocked) return { kind: 'blocked', reason: blocked };

    var model = getModel(answers.modelId);
    if (!model) throw new Error('Unknown model: ' + answers.modelId);

    var basePrice = Object.prototype.hasOwnProperty.call(model.sellPrice, answers.storage) ? model.sellPrice[answers.storage] : undefined;
    if (basePrice === undefined) throw new Error('No price for ' + model.name + ' ' + answers.storage);

    var grade = answers.deadDevice ? 'faulty' : resolveGrade(answers.screen, answers.body);
    var conditionFactor = CONDITION_FACTORS[grade];

    var refurbCost = 0;
    if (answers.screen === 'cracked') refurbCost += model.screenRepairCost;
    if (answers.wornBattery) refurbCost += econ.batteryCost;

    var networkLocked = answers.networkLocked === true;
    var adjustedPrice = basePrice * conditionFactor;
    if (networkLocked) adjustedPrice *= econ.networkLockedMultiplier;
    adjustedPrice = Math.round(adjustedPrice);

    var otherCosts = Math.round(adjustedPrice * econ.variableRate + econ.fixedCosts + refurbCost);

    var maxQuote = Math.round(
      adjustedPrice -
        1.2 * econ.targetMargin * adjustedPrice -
        1.2 * (otherCosts - econ.inputVat)
    );

    var breakdown = {
      basePrice: basePrice,
      grade: grade,
      conditionFactor: conditionFactor,
      networkLocked: networkLocked,
      adjustedPrice: adjustedPrice,
      refurbCost: refurbCost,
      otherCosts: otherCosts,
      inputVat: econ.inputVat,
      maxQuote: maxQuote
    };

    /* Offer a little under the ceiling, then round DOWN. Both steps only ever reduce
       the number, so "never above maxQuote" holds by construction. */
    var offered = Math.max(0, maxQuote) * (1 - econ.offerBelowCeiling);
    var customerQuote = Math.floor(offered / econ.roundDownTo) * econ.roundDownTo;

    if (customerQuote < econ.minimumQuote) return { kind: 'below-minimum', breakdown: breakdown };
    return { kind: 'quote', customerQuote: customerQuote, breakdown: breakdown };
  }

  /* Expected net profit at a given acquisition price, pence. */
  function netProfitAt(acquisitionPrice, breakdown) {
    var vatOnMargin = Math.max(0, Math.round((breakdown.adjustedPrice - acquisitionPrice) / 6));
    return Math.round(breakdown.adjustedPrice - acquisitionPrice - breakdown.otherCosts - vatOnMargin + breakdown.inputVat);
  }

  /* Display boundary only. */
  function formatPence(pence) { return '£' + (pence / 100).toFixed(2); }
  function formatPounds(pence) { return '£' + Math.round(pence / 100); }

  /* Best case for a model (unlocked, healthy battery, Excellent): the "up to" figure.
     Like lib/price-table.ts, it only ever calls quote(). */
  var TABLE_GRADES = ['excellent', 'verygood', 'good', 'fair'];
  function priceTable(modelId) {
    var model = getModel(modelId);
    if (!model) throw new Error('Unknown model: ' + modelId);
    var storages = Object.keys(model.sellPrice), upTo = 0;
    var rows = TABLE_GRADES.map(function (grade) {
      var byStorage = {};
      storages.forEach(function (storage) {
        var r = quote({ modelId: modelId, storage: storage, screen: grade, body: grade });
        var value = r.kind === 'quote' ? r.customerQuote : null;
        byStorage[storage] = value;
        if (value !== null && value > upTo) upTo = value;
      });
      return { grade: grade, byStorage: byStorage };
    });
    return { modelId: modelId, modelName: model.name, storages: storages, rows: rows, upTo: upTo };
  }

  root.FullBarsQuote = {
    MODELS: MODELS, ECONOMICS: ECONOMICS, CONDITION_FACTORS: CONDITION_FACTORS, GRADE_WORDS: GRADE_WORDS,
    getModel: getModel, resolveGrade: resolveGrade, quote: quote, netProfitAt: netProfitAt,
    formatPence: formatPence, formatPounds: formatPounds, priceTable: priceTable
  };
})(window);
