/* Full Bars - site behaviour: menu, product option picker, shop filters,
   contact + trade-in forms (they open the visitor's own email app; nothing is sent or stored by the site). */
(function () {
  var EMAIL = 'hello@fullbars.co.uk';
  var PAY = window.FULLBARS_PAY || {};
  /* First-order value cap in pounds, set here (no build step). Buy now takes payment at once, so it's only
     offered at or below the cap; dearer phones stay email-order, where a new customer can be checked first. */
  var BUY_NOW_MAX = Number('450') || 0;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function gbp(n) { return '£' + Number(n).toLocaleString('en-GB'); }

  /* ---------- mobile menu ---------- */
  var menuBtn = $('#menuBtn'), drawer = $('#drawer');
  if (menuBtn && drawer) {
    menuBtn.addEventListener('click', function () {
      var open = drawer.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    /* Escape closes the drawer and puts focus back on the button that opened it */
    document.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.key === 'Esc') && drawer.classList.contains('open')) {
        drawer.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
        menuBtn.focus();
      }
    });
  }

  /* ---------- wide tables ----------
     Each .table-wrap ships as a focusable, labelled region so keyboard users can scroll it sideways.
     When the table fits, that's a tab stop that does nothing, so drop it; put it back if the table overflows again. */
  var wraps = $all('.table-wrap[tabindex]');
  if (wraps.length) {
    wraps.forEach(function (w) { w.setAttribute('data-label', w.getAttribute('aria-label') || ''); });
    /* .more-right fades the right edge while there is more table to scroll to (styles.css) */
    var edge = function (w) { w.classList.toggle('more-right', w.scrollLeft + w.clientWidth < w.scrollWidth - 2); };
    wraps.forEach(function (w) { w.addEventListener('scroll', function () { edge(w); }, { passive: true }); });
    var fitWraps = function () {
      wraps.forEach(function (w) {
        edge(w);
        if (w.scrollWidth > w.clientWidth + 1) {
          w.setAttribute('tabindex', '0'); w.setAttribute('role', 'region'); w.setAttribute('aria-label', w.getAttribute('data-label'));
        } else if (document.activeElement !== w) {
          w.removeAttribute('tabindex'); w.removeAttribute('role'); w.removeAttribute('aria-label');
        }
      });
    };
    fitWraps();
    /* watch the table as well as the wrapper: a late web font can widen the table without resizing the wrapper */
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(fitWraps);
      wraps.forEach(function (w) { ro.observe(w); if (w.firstElementChild) ro.observe(w.firstElementChild); });
    }
    else window.addEventListener('resize', fitWraps);
  }

  /* ---------- range chips ----------
     On phones the chips are one sideways-scrolling row: bring the current page's chip into view within the row
     (the row only, never the page). */
  $all('.chips-scroll').forEach(function (ul) {
    var cur = $('[aria-current="page"]', ul);
    if (cur && ul.scrollWidth > ul.clientWidth) ul.scrollLeft += cur.getBoundingClientRect().left - ul.getBoundingClientRect().left - 16;
  });

  /* ---------- toast + copy ---------- */
  var toastEl = $('#toast'), toastT;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg; toastEl.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(function () { toastEl.hidden = true; }, 2800);
  }
  function copyText(text, ok) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast(ok); },
        function () { toast('Couldn’t copy automatically — select the text and copy it.'); });
    } else toast('Couldn’t copy automatically — select the text and copy it.');
  }
  $all('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () { copyText(b.getAttribute('data-copy'), 'Copied'); });
  });

  /* ---------- product option picker ----------
     The form carries every price as JSON in data-prices: { "128GB": { "Excellent": 249, ... }, ... }.
     The Order button goes to the contact page with the chosen phone filled in. If pay.js has a
     Stripe Payment Link for "<model> <storage> <grade>", the button becomes "Buy now" instead. */
  var picker = $('#picker');
  if (picker) {
    var prices = JSON.parse(picker.getAttribute('data-prices'));
    var model = picker.getAttribute('data-model');
    var contactUrl = picker.getAttribute('data-contact');
    var grades = JSON.parse(picker.getAttribute('data-grades'));
    /* data-stock goes on the product page's #picker form once there is real stock: { "128GB|Very Good": 1, ... }.
       Without it, every option counts as available and no 'not in stock' note is shown. */
    var stock = picker.getAttribute('data-stock') ? JSON.parse(picker.getAttribute('data-stock')) : null;
    var priceEl = $('#pdPrice'), orderBtn = $('#orderBtn'), lineEl = $('#selLine'), gradeNote = $('#gradeNote');
    var buyNote = $('#buyNote'), stockNote = $('#stockNote'), emailNote = $('#emailNote'), fromEl = $('#pdFrom');
    /* the lowest price across every option, and which option it is: the 'from' price the cards show */
    var minP = null, minSt = '', minGr = '';
    Object.keys(prices).forEach(function (s) {
      Object.keys(prices[s]).forEach(function (g) { if (minP === null || prices[s][g] < minP) { minP = prices[s][g]; minSt = s; minGr = g; } });
    });
    /* data-preview="1" on #picker in the page's HTML: not trading yet, so no Order or Buy now route at all.
       Remove the attribute at launch. */
    var preview = picker.getAttribute('data-preview') === '1';
    function val(name) { var el = picker.querySelector('input[name="' + name + '"]:checked'); return el ? el.value : ''; }
    /* The choice is kept in the address (?storage=256GB&grade=Good&colour=Green), so Back, refresh and a shared
       link all show the same phone at the same price. Unknown values are ignored. */
    var KEYS = ['storage', 'grade', 'colour'];
    try {
      var want = new URLSearchParams(location.search);
      KEYS.forEach(function (k) {
        var v = want.get(k);
        var r = v ? $all('input[name="' + k + '"]', picker).filter(function (i) { return i.value === v; })[0] : null;
        if (r) r.checked = true;
      });
    } catch (e) { /* no URLSearchParams: keep the page's own default */ }
    function rememberPick() {
      try {
        var q = new URLSearchParams(location.search);
        KEYS.forEach(function (k) { var v = val(k); if (v) q.set(k, v); });
        history.replaceState(history.state, '', location.pathname + '?' + q.toString() + location.hash);
      } catch (e) { /* sandboxed frame or old browser: the picker still works, the address just doesn't follow it */ }
    }
    function update() {
      var st = val('storage'), gr = val('grade'), co = val('colour');
      var price = prices[st] && prices[st][gr];
      if (price == null) return;
      priceEl.textContent = gbp(price);
      /* say which option the big price is for, and the lowest price, so it matches the 'from' price on the cards */
      if (fromEl) {
        fromEl.textContent = 'Price for ' + st + ' in ' + gr + (price === minP ? ': the lowest for this phone.'
          : '. From ' + gbp(minP) + (minSt === st ? '' : ' for ' + minSt) + ' in ' + minGr + '.');
      }
      /* show each grade's price for the chosen storage */
      $all('input[name="grade"]', picker).forEach(function (r) {
        var s = r.parentNode.querySelector('small'); if (s) s.textContent = gbp(prices[st][r.value]);
      });
      $all('input[name="storage"]', picker).forEach(function (r) {
        var s = r.parentNode.querySelector('small'); if (s) s.textContent = gbp(prices[r.value][gr]);
      });
      if (gradeNote && grades[gr]) gradeNote.textContent = grades[gr];
      $all('#pdArt [data-colour]').forEach(function (v) { v.hidden = v.getAttribute('data-colour') !== co; });
      var label = model + ' ' + st + ', ' + gr + (co ? ', ' + co : '');
      var held = !stock || stock[st + '|' + gr] === 1;
      lineEl.textContent = 'Selected: ' + label + ' — ' + gbp(price) + (held ? '' : ' (not in stock right now)');
      /* show which options are in stock when the owner tracks stock */
      if (stock) {
        $all('input[name="storage"]', picker).forEach(function (r) { r.parentNode.classList.toggle('na', stock[r.value + '|' + gr] !== 1); });
        $all('input[name="grade"]', picker).forEach(function (r) { r.parentNode.classList.toggle('na', stock[st + '|' + r.value] !== 1); });
      }
      var link = PAY[model + ' ' + st + ' ' + gr];
      var buyNow = !preview && held && link && /^https:\/\//.test(link) && price <= BUY_NOW_MAX;
      if (preview) {
        orderBtn.textContent = 'Opening soon';
      } else if (buyNow) {
        orderBtn.setAttribute('href', link);
        orderBtn.setAttribute('rel', 'noopener');
        orderBtn.textContent = 'Buy now — ' + gbp(price);
      } else if (!held) {
        orderBtn.setAttribute('href', contactUrl + '?ask=' + encodeURIComponent(label) + '#form');
        orderBtn.removeAttribute('rel');
        orderBtn.textContent = 'Not in stock — ask us';
      } else {
        orderBtn.setAttribute('href', contactUrl + '?order=' + encodeURIComponent(label) + '&price=' + price + '#form');
        orderBtn.removeAttribute('rel');
        orderBtn.textContent = 'Order — ' + gbp(price);
      }
      /* Buy now takes payment straight away, so show what is confirmed afterwards (and the refund promise) above the button */
      if (buyNote) buyNote.hidden = !buyNow;
      if (stockNote) stockNote.hidden = buyNow;
      if (emailNote) emailNote.hidden = buyNow;
    }
    picker.addEventListener('change', function () { update(); rememberPick(); });
    update();
    /* Coming Back to the page, the browser can re-tick the options after this script has run, without a change
       event: refresh everything (price, notes, Order link) from what is actually ticked. */
    window.addEventListener('pageshow', update);
    /* Preview: questions can't be sent yet, so point 'Ask a question' at the answers on this page instead */
    var askBtn = $('#askBtn');
    if (preview && askBtn) {
      askBtn.setAttribute('href', $('#questions') ? '#questions' : '../faq.html');
      askBtn.textContent = 'Common questions';
    }
  }

  /* ---------- shop filters ---------- */
  var filters = $('#filters'), grid = $('#shopGrid');
  if (filters && grid) {
    var cards = $all('.card', grid), countEl = $('#resultCount'), empty = $('#emptyMsg');
    var params = new URLSearchParams(location.search);
    ['series', 'type', 'max', 'sort'].forEach(function (k) {
      var el = filters.elements[k]; if (el && params.get(k)) el.value = params.get(k);
    });
    if (params.get('usbc') === '1') filters.elements.usbc.checked = true;
    function apply() {
      var f = filters.elements, series = f.series.value, type = f.type.value, max = Number(f.max.value || 0),
          usbc = f.usbc.checked, sort = f.sort.value, shown = 0;
      cards.forEach(function (c) {
        var ok = (!series || c.dataset.series === series) &&
                 (!type || (' ' + c.dataset.type + ' ').indexOf(' ' + type + ' ') > -1) &&
                 (!max || Number(c.dataset.from) <= max) &&
                 (!usbc || c.dataset.usbc === '1');
        c.hidden = !ok; if (ok) shown++;
      });
      var sorted = cards.slice().sort(function (a, b) {
        if (sort === 'price-asc') return a.dataset.from - b.dataset.from;
        if (sort === 'price-desc') return b.dataset.from - a.dataset.from;
        if (sort === 'oldest') return a.dataset.order - b.dataset.order;
        return b.dataset.order - a.dataset.order;
      });
      sorted.forEach(function (c) { grid.appendChild(c); });
      countEl.textContent = shown + (shown === 1 ? ' phone' : ' phones');
      empty.classList.toggle('show', shown === 0);
    }
    /* keep the filters in the address (same names as above), so Back, refresh and shared links show the same list */
    function rememberFilters() {
      try {
        var f = filters.elements, q = new URLSearchParams(location.search);
        ['series', 'type', 'max', 'sort', 'usbc'].forEach(function (k) { q.delete(k); });
        ['series', 'type', 'max', 'sort'].forEach(function (k) {
          var v = f[k].value; if (v && !(k === 'sort' && v === 'newest')) q.set(k, v);
        });
        if (f.usbc.checked) q.set('usbc', '1');
        var qs = q.toString();
        history.replaceState(history.state, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
      } catch (e) { /* the filters still work; the address just doesn't follow them */ }
    }
    filters.addEventListener('change', function () { apply(); rememberFilters(); });
    filters.addEventListener('submit', function (e) { e.preventDefault(); apply(); });
    var reset = $('#resetFilters');
    if (reset) reset.addEventListener('click', function () { filters.reset(); apply(); rememberFilters(); });
    apply();
    /* the browser can restore the dropdowns on Back after this script ran: re-filter from what they actually show */
    window.addEventListener('pageshow', apply);
  }

  /* ---------- email-composing forms ---------- */
  /* Device identifiers never go into an email from this site:
     - any run of 14+ digits (IMEI, MEID, ICCID, EID), even split by spaces, line breaks, dots, slashes or dashes;
     - anything after the word "serial" or "S/N" that looks like a serial number (8-14 letters and digits).
     Short numbers and our SKUs (e.g. IP14-128-MID-VG-0247) are left alone. Same function as quote-ui.js. */
  function scrub(s) {
    return String(s || '')
      .replace(/\d[\d\s.\/\-]{12,}\d/g, function (m) { return m.replace(/\D/g, '').length >= 14 ? '[number removed]' : m; })
      .replace(/\b(serial|s\/n)(\s*(?:no\.?|number|num\.?))?(\s+is)?(\s*[:#]?\s*)(?=[a-z0-9]*\d)[a-z0-9]{8,14}\b/gi,
        function (m, w, n, is, sep) { return w + (n || '') + (is || '') + (sep || ' ') + '[number removed]'; });
  }
  function mailto(subject, body) {
    location.href = 'mailto:' + EMAIL + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
  }

  /* contact page: ?order=<phone>&price=<n> or ?ask=<model> starts the message */
  var form = $('#contactForm');
  if (form) {
    var topic = $('#cTopic'), nameEl = $('#cName'), msgEl = $('#cMsg'), status = $('#status');
    var q = new URLSearchParams(location.search);
    /* only pick a topic the list actually has (preview mode has no "Order a phone"); otherwise keep the first one */
    function setTopic(v) { for (var j = 0; j < topic.options.length; j++) if (topic.options[j].value === v) { topic.value = v; return; } }
    if (q.get('order')) {
      setTopic('Order a phone');
      var pr = q.get('price') && /^\d+$/.test(q.get('price')) ? ' (' + gbp(q.get('price')) + ')' : '';
      msgEl.value = 'I’d like to order:\n- ' + q.get('order') + pr + '\n\nDelivery address:\n\n\nPhone number (for the courier):\n';
    } else if (q.get('ask')) {
      setTopic('Question about a phone');
      msgEl.value = 'Question about the ' + q.get('ask') + ':\n';
    } else if (q.get('topic')) {
      setTopic(q.get('topic'));
    }
    if (q.get('ask') && form.getAttribute('data-preview') === '1') {
      status.textContent = 'Full Bars isn’t trading yet, so questions can’t be sent through the site. You can draft one here, but nothing will be sent.';
    }
    function composed() {
      var name = scrub(nameEl.value.trim()), msg = scrub(msgEl.value.trim());
      return { topic: topic.value, name: name, msg: msg, body: msg + (name ? '\n\n' + name : '') };
    }
    /* data-preview: not trading yet. The form checks what was typed but never opens an email or sends anything,
       and says so plainly. Copy is hidden too: the address isn't live until we open. */
    var formPreview = form.getAttribute('data-preview') === '1';
    if (formPreview && $('#copyMsg')) $('#copyMsg').hidden = true;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var c = composed();
      if (!c.name || !c.msg) { status.textContent = 'Add your name and a message first.'; return; }
      if (formPreview) {
        status.textContent = 'Nothing has been sent. Full Bars isn’t trading yet, so this form isn’t connected to an inbox and your message hasn’t left this page. When we open, this button will open your own email app with the message ready to send.';
        return;
      }
      mailto(c.topic + (c.name ? ' — ' + c.name : ''), c.body);
      status.textContent = 'Your email app should open with this message ready — press send there. If nothing opened, use “Copy message” and email it to ' + EMAIL + '.';
    });
    if ($('#copyMsg')) $('#copyMsg').addEventListener('click', function () {
      var c = composed();
      if (!c.msg) { status.textContent = 'Write your message first.'; return; }
      copyText('To: ' + EMAIL + '\nSubject: ' + c.topic + '\n\n' + c.body, 'Message copied — paste it into an email to us');
      status.textContent = 'Copied. Paste it into a new email to ' + EMAIL + '.';
    });
  }

  /* sell page: quote request for a model the instant quote tool doesn't cover.
     No IMEI is asked for or sent: we check it ourselves when the phone arrives. */
  var sell = $('#sellForm');
  if (sell) {
    var sStatus = $('#sellStatus');
    function sellBody() {
      var f = sell.elements;
      var model = scrub(f.model.value.trim());
      return {
        ok: model && f.storage.value && f.condition.value && f.sname.value.trim(),
        subject: 'Trade-in quote: ' + model + ' ' + f.storage.value,
        body: 'Please quote me for my phone.\n\n' +
          'Model: ' + model + '\n' +
          'Storage: ' + f.storage.value + '\n' +
          'Condition: ' + f.condition.value + '\n' +
          'Battery health: ' + (f.battery.value ? f.battery.value + '%' : 'not sure') + '\n' +
          'Network: ' + f.network.value + '\n' +
          'Signed out of iCloud / Google / Samsung account and reset before sending: ' + (f.findmy.checked ? 'yes' : 'not yet') + '\n' +
          'I own this phone, it is not lost, stolen or blocked, there is no finance owing on it, and I can show proof of ownership and photo ID: ' + (f.owner.checked ? 'yes' : 'NOT CONFIRMED') + '\n\n' +
          'Anything else: ' + (scrub(f.notes.value.trim()) || '-') + '\n\n' + scrub(f.sname.value.trim())
      };
    }
    sell.addEventListener('submit', function (e) {
      e.preventDefault();
      var b = sellBody();
      if (!b.ok) { sStatus.textContent = 'Add the model, storage, condition and your name.'; return; }
      if (!sell.elements.owner.checked) { sStatus.textContent = 'Please confirm the phone is yours to sell, with no finance owing, and that you can show proof of ownership and photo ID.'; return; }
      mailto(b.subject, b.body);
      sStatus.textContent = 'Your email app should open with your quote request ready — press send there. We reply within one working day.';
    });
    $('#sellCopy').addEventListener('click', function () {
      var b = sellBody();
      copyText('To: ' + EMAIL + '\nSubject: ' + b.subject + '\n\n' + b.body, 'Quote request copied — paste it into an email to us');
    });
  }
})();
