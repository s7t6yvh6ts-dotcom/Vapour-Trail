/* Full Bars - the instant trade-in quote tool (sell pages).
   All prices come from quote.js (window.FullBarsQuote.quote). This file renders and
   collects; it never does its own arithmetic on prices.
   Device identifiers (IMEI, serial, EID, ICCID) are never asked for, put in a URL or
   put in an email: we check the IMEI ourselves when the phone arrives. */
(function () {
  'use strict';
  var Q = window.FullBarsQuote;
  var EMAIL = 'hello@fullbars.co.uk';
  if (!Q) return;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  /* Device identifiers never go into an email from this site:
     - any run of 14+ digits (IMEI, MEID, ICCID, EID), even split by spaces, line breaks, dots, slashes or dashes;
     - anything after the word "serial" or "S/N" that looks like a serial number (8-14 letters and digits).
     Short numbers and our SKUs (e.g. IP14-128-MID-VG-0247) are left alone. Same function as site.js. */
  function scrub(s) {
    return String(s || '')
      .replace(/\d[\d\s.\/\-]{12,}\d/g, function (m) { return m.replace(/\D/g, '').length >= 14 ? '[number removed]' : m; })
      .replace(/\b(serial|s\/n)(\s*(?:no\.?|number|num\.?))?(\s+is)?(\s*[:#]?\s*)(?=[a-z0-9]*\d)[a-z0-9]{8,14}\b/gi,
        function (m, w, n, is, sep) { return w + (n || '') + (is || '') + (sep || ' ') + '[number removed]'; });
  }

  /* ---------- "up to" figures and price tables (any sell page) ---------- */
  $all('[data-upto]').forEach(function (el) {
    try { el.textContent = Q.formatPounds(Q.priceTable(el.getAttribute('data-upto')).upTo); } catch (e) { el.textContent = 'ask us'; }
  });
  $all('[data-price-table]').forEach(function (tbl) {
    var t;
    try { t = Q.priceTable(tbl.getAttribute('data-price-table')); } catch (e) { return; }
    var head = '<thead><tr><th>Condition</th>' + t.storages.map(function (s) { return '<th class="num">' + esc(s) + '</th>'; }).join('') + '</tr></thead>';
    var body = '<tbody>' + t.rows.map(function (row) {
      return '<tr><td><b>' + esc(Q.GRADE_WORDS[row.grade]) + '</b></td>' + t.storages.map(function (s) {
        var v = row.byStorage[s];
        return '<td class="num tnum">' + (v === null || v === undefined ? '&mdash;' : esc(Q.formatPounds(v))) + '</td>';
      }).join('') + '</tr>';
    }).join('') + '</tbody>';
    /* guide prices, not offers: trade-ins aren't open yet (data-preview on the quote tool / preview banner) */
    tbl.innerHTML = '<caption>Guide prices for when trade-ins open, not an offer.</caption>' + head + body;
  });

  /* ---------- the quote tool ---------- */
  var tool = $('#qt');
  if (!tool) return;
  var preset = tool.getAttribute('data-model') || '';
  /* data-preview="1" on #qt in the page's HTML: the business isn't trading yet. The tool still gives a guide
     price, but there is no way to send it, and the wording says it isn't an offer. Remove the attribute at launch. */
  var preview = tool.getAttribute('data-preview') === '1';
  var state = { modelId: preset || null, storage: null, screen: null, body: null };
  var SCREEN_WORDS = {}, BODY_WORDS = {};
  $all('input[name="qtScreen"]', tool).forEach(function (r) { SCREEN_WORDS[r.value] = r.getAttribute('data-title'); });
  $all('input[name="qtBody"]', tool).forEach(function (r) { BODY_WORDS[r.value] = r.getAttribute('data-title'); });

  var steps = {
    model: $('#qtModelStep'), storage: $('#qtStorageStep'), screen: $('#qtScreenStep'),
    body: $('#qtBodyStep'), flags: $('#qtFlagsStep'), own: $('#qtOwnStep')
  };
  var figEl = $('#qtFig'), labelEl = $('#qtLabel'), subEl = $('#qtSub'), bar = $('#qtBar');
  var noticeEl = $('#qtNotice'), working = $('#qtWorking'), tableEl = $('#qtTable'), send = $('#qtSend'), jump = $('#qtJump');
  var previewNote = $('#qtPreview');
  /* the bar sticks to the bottom of the screen on phones: keep its height in --qt-bar-h so styles.css can
     scroll keyboard focus clear of it (WCAG 2.4.11). Its height changes with the answer shown. */
  if (bar && window.ResizeObserver) {
    new ResizeObserver(function () {
      document.documentElement.style.setProperty('--qt-bar-h', Math.ceil(bar.getBoundingClientRect().height) + 'px');
    }).observe(bar);
  }
  if (preview) send = null;   /* belt and braces: never offer to send a quote while not trading */

  function optHtml(name, value, title, detail, type) {
    return '<label class="opt qt-opt"><input type="' + (type || 'radio') + '" name="' + name + '" value="' + esc(value) + '" autocomplete="off"><span>' + esc(title) +
      (detail ? '<small>' + esc(detail) + '</small>' : '') + '</span></label>';
  }

  /* model choices come from quote.js, so the list can never drift from the prices */
  var modelBox = $('#qtModels');
  if (modelBox) modelBox.innerHTML = Q.MODELS.map(function (m) { return optHtml('qtModel', m.id, m.name); }).join('');

  function renderStorage() {
    var m = Q.getModel(state.modelId), box = $('#qtStorages');
    if (!m || !box) return;
    box.innerHTML = Object.keys(m.sellPrice).map(function (s) { return optHtml('qtStorage', s, s); }).join('');
  }

  function numberSteps() {
    var n = 0;
    ['model', 'storage', 'screen', 'body', 'flags', 'own'].forEach(function (k) {
      var st = steps[k]; if (!st || (k === 'model' && preset)) return;
      n++; var badge = $('.qt-n', st); if (badge) badge.textContent = n;
    });
  }

  function flag(name) { var el = $('input[name="qtFlag"][value="' + name + '"]', tool); return !!(el && el.checked); }

  function answers() {
    if (!state.modelId || !state.storage || !state.screen || !state.body) return null;
    return {
      modelId: state.modelId, storage: state.storage, screen: state.screen, body: state.body,
      wornBattery: flag('wornBattery'), networkLocked: flag('networkLocked'), activationLocked: flag('activationLocked'),
      deadDevice: flag('deadDevice'), blacklisted: flag('blacklisted'), outstandingFinance: flag('outstandingFinance')
    };
  }

  var BLOCKS = {
    'activation-locked': ['We can&rsquo;t quote this phone yet: it&rsquo;s still signed in',
      'A phone still signed in to iCloud (Find My and Activation Lock), a Google account (Factory Reset Protection) or a Samsung account (Reactivation Lock) can&rsquo;t be reset or used by anyone else, so we can&rsquo;t buy it. This is a hard stop, not a discount. Sign out on the phone, or remove it from your account online, then come back and we&rsquo;ll quote it properly. <a href="__PRE__guides/remove-find-my-before-selling-iphone.html">How to sign out and reset</a>.'],
    'blacklisted': ['We can&rsquo;t buy a phone that&rsquo;s blocked or reported lost or stolen',
      'If a phone is on a loss, theft or network blocklist, nobody in the UK can legally buy or use it, at any price. If it&rsquo;s yours and has been recovered, ask your network or insurer to clear the record first, then come back for a quote.'],
    'outstanding-finance': ['We can&rsquo;t buy a phone with money still owed on it',
      'A network can block a phone if its finance or device plan isn&rsquo;t paid off, even after it&rsquo;s been sold, so we never buy one with a balance outstanding. Pay off the balance (your network can tell you how much), then come back and we&rsquo;ll quote it.']
  };
  var pre = tool.getAttribute('data-pre') || '';

  function notice(tone, title, html) {
    return '<div class="callout' + (tone === 'stop' ? ' stop' : tone === 'warn' ? ' warn' : '') + '"><p><b>' + title + '</b><br>' + html + '</p></div>';
  }

  /* A cracked screen is priced as Fair plus the repair, but it isn't the Fair grade: say what it is. */
  function conditionLabel(a, r) {
    return a.screen === 'cracked' ? 'Cracked screen' : Q.GRADE_WORDS[r.breakdown.grade];
  }

  var current = null;
  function update() {
    /* progressive steps: each question appears once the one before it is answered */
    if (steps.storage) steps.storage.hidden = !state.modelId;
    if (steps.screen) steps.screen.hidden = !state.storage;
    if (steps.body) steps.body.hidden = !state.screen;
    if (steps.flags) steps.flags.hidden = !state.body;
    if (steps.own) steps.own.hidden = !state.body;
    var cracked = $('#qtCracked'); if (cracked) cracked.hidden = state.screen !== 'cracked';
    var dead = $('#qtDead'); if (dead) dead.hidden = !flag('deadDevice');

    var a = answers(), r = null;
    if (a) { try { r = Q.quote(a); } catch (e) { r = null; } }
    current = a && r ? { a: a, r: r } : null;
    var m = Q.getModel(state.modelId);
    var notes = '';

    if (!r) {
      labelEl.textContent = 'Your quote';
      figEl.textContent = 'Answer the questions';
      bar.classList.add('pending'); subEl.textContent = 'Takes under a minute.';
    } else if (r.kind === 'blocked') {
      labelEl.textContent = 'We can’t quote this phone';
      figEl.textContent = 'No quote';
      bar.classList.add('pending'); subEl.textContent = 'See why below.';
      notes += notice('stop', BLOCKS[r.reason][0], BLOCKS[r.reason][1].replace('__PRE__', pre));
    } else if (r.kind === 'below-minimum') {
      labelEl.textContent = 'Below our ' + Q.formatPounds(Q.ECONOMICS.minimumQuote) + ' minimum';
      figEl.textContent = 'Not worth posting';
      bar.classList.add('pending'); subEl.textContent = 'See why below.';
      notes += notice('warn', 'This one&rsquo;s worth less than the postage', 'In this condition the phone is worth less to us than ' + esc(Q.formatPounds(Q.ECONOMICS.minimumQuote)) + ' after testing, repairs and postage, so it isn&rsquo;t worth sending. Please recycle it responsibly, or <a href="#other">email us</a> if you think we&rsquo;ve got it wrong.');
    } else if (preview) {
      labelEl.textContent = m.name + ' ' + a.storage + ' · ' + conditionLabel(a, r);
      figEl.textContent = Q.formatPounds(r.customerQuote);
      bar.classList.remove('pending');
      subEl.textContent = 'Guide price only: trade-ins open soon.';
    } else {
      labelEl.textContent = m.name + ' ' + a.storage + ' · ' + conditionLabel(a, r);
      figEl.textContent = Q.formatPounds(r.customerQuote);
      bar.classList.remove('pending');
      subEl.textContent = 'Provisional until we inspect the phone.';
      notes += notice('', 'Provisional quote: ' + esc(Q.formatPounds(r.customerQuote)), 'This is what we pay if the phone matches your answers when we inspect it. It&rsquo;s locked for 14 days. If something is genuinely different, we send you photos and a revised offer, and if you&rsquo;d rather not accept it we post the phone back free.');
    }
    noticeEl.innerHTML = notes;
    if (jump) jump.hidden = !r;

    /* how we worked it out: the same steps as quote.js, in words */
    if (r && r.kind === 'quote') {
      var b = r.breakdown, E = Q.ECONOMICS;
      var rows = [['What a working ' + m.name + ' ' + a.storage + ' sells for', Q.formatPence(b.basePrice)],
        ['Adjusted for condition (' + conditionLabel(a, r).toLowerCase() + ')', '×' + b.conditionFactor.toFixed(2)]];
      if (b.networkLocked) rows.push(['Locked to one network', '×' + E.networkLockedMultiplier.toFixed(2)]);
      if (b.refurbCost > 0) rows.push(['Repairs we’ll need to do', '−' + Q.formatPence(b.refurbCost)]);
      rows.push(['Testing, postage, warranty and VAT', '−' + Q.formatPence(b.adjustedPrice - r.customerQuote - b.refurbCost)]);
      rows.push(['We pay you', Q.formatPounds(r.customerQuote)]);
      tableEl.innerHTML = rows.map(function (row, i) {
        return '<tr' + (i === rows.length - 1 ? ' class="total"' : '') + '><td>' + esc(row[0]) + '</td><td class="num tnum">' + esc(row[1]) + '</td></tr>';
      }).join('');
      working.hidden = false;
      if (send) send.hidden = false;
      if (previewNote) previewNote.hidden = false;
    } else {
      /* clear the old rows too: a blocked or below-minimum phone must not carry a price, even hidden */
      tableEl.innerHTML = '';
      working.hidden = true;
      if (send) send.hidden = true;
      if (previewNote) previewNote.hidden = true;
    }
  }

  /* Bring the script's answers into line with what is actually ticked on the page. Browsers can
     re-tick answers when someone comes Back to the page; without this the panel would say
     "Answer the questions" while the ticks look answered. It only reads ticks, never clears them. */
  function syncFromPage() {
    var mi = $('input[name="qtModel"]:checked', tool);
    var model = preset || (mi ? mi.value : null);
    var si = $('input[name="qtStorage"]:checked', tool);
    var st = si ? si.value : null;
    if (model !== state.modelId || !$('input[name="qtStorage"]', tool)) {
      state.modelId = model;
      renderStorage();
      var again = st ? $all('input[name="qtStorage"]', tool).filter(function (i) { return i.value === st; })[0] : null;
      if (again) again.checked = true; else st = null;
    }
    state.storage = model ? st : null;
    var sc = $('input[name="qtScreen"]:checked', tool), bo = $('input[name="qtBody"]:checked', tool);
    state.screen = sc ? sc.value : null;
    state.body = bo ? bo.value : null;
    update();
  }

  tool.addEventListener('change', function (e) {
    var t = e.target;
    if (t.name === 'qtModel') { state.modelId = t.value; state.storage = null; renderStorage(); }
    else if (t.name === 'qtStorage') state.storage = t.value;
    else if (t.name === 'qtScreen') state.screen = t.value;
    else if (t.name === 'qtBody') state.body = t.value;
    update();
  });

  /* ---------- send the quote by email (mailto; nothing is stored by the site) ---------- */
  var sendStatus = $('#qtStatus');
  function yesNo(v) { return v ? 'yes' : 'no'; }
  function composed() {
    if (!current || current.r.kind !== 'quote') return null;
    var a = current.a, r = current.r, m = Q.getModel(a.modelId);
    var name = scrub($('#qtName').value.trim()), notes = scrub($('#qtNotes').value.trim());
    var when = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    var body = 'Please send me a free postage label for this trade-in quote.\n\n' +
      'Phone: ' + m.name + ' ' + a.storage + '\n' +
      'Screen: ' + SCREEN_WORDS[a.screen] + '\n' +
      'Back and sides: ' + BODY_WORDS[a.body] + '\n' +
      'Battery worn out: ' + yesNo(a.wornBattery) + '\n' +
      'Locked to a network: ' + yesNo(a.networkLocked) + '\n' +
      'Won’t switch on: ' + yesNo(a.deadDevice) + '\n' +
      'Signed out of iCloud / Google / Samsung account: yes\n' +
      'Not lost, stolen or blocked, and no finance owed: confirmed\n' +
      'Grade from my answers: ' + Q.GRADE_WORDS[r.breakdown.grade] + (a.screen === 'cracked' ? ' (cracked screen)' : '') + '\n' +
      'Quote: ' + Q.formatPounds(r.customerQuote) + ' (provisional until inspected; quoted ' + when + ', locked for 14 days)\n' +
      'Full Bars re-checks this price against the answers above; a changed figure won’t be honoured.\n\n' +
      'Anything else: ' + (notes || '-') + '\n\n' + name;
    return { name: name, subject: 'Trade-in quote: ' + m.name + ' ' + a.storage + ', ' + Q.formatPounds(r.customerQuote), body: body };
  }
  if (send) {
    send.addEventListener('submit', function (e) {
      e.preventDefault();
      var c = composed();
      if (!c) return;
      if (!c.name) { sendStatus.textContent = 'Add your name first.'; return; }
      if (!$('#qtOwner').checked) { sendStatus.textContent = 'Please confirm the phone is yours to sell.'; return; }
      location.href = 'mailto:' + EMAIL + '?subject=' + encodeURIComponent(c.subject) + '&body=' + encodeURIComponent(c.body);
      sendStatus.textContent = 'Your email app should open with your quote ready: press send there. We reply within one working day with your free label. If nothing opened, use “Copy quote” and email it to ' + EMAIL + '.';
    });
    $('#qtCopy').addEventListener('click', function () {
      var c = composed(); if (!c) return;
      var text = 'To: ' + EMAIL + '\nSubject: ' + c.subject + '\n\n' + c.body;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { sendStatus.textContent = 'Copied. Paste it into a new email to ' + EMAIL + '.'; },
          function () { sendStatus.textContent = 'Couldn’t copy automatically. Email ' + EMAIL + ' with your answers.'; });
      } else sendStatus.textContent = 'Couldn’t copy automatically. Email ' + EMAIL + ' with your answers.';
    });
  }

  numberSteps();
  syncFromPage();
  /* again once the page has fully loaded and whenever it's shown from the Back/Forward cache,
     in case the browser restored ticks after this script first ran */
  window.addEventListener('load', syncFromPage);
  window.addEventListener('pageshow', syncFromPage);
})();
