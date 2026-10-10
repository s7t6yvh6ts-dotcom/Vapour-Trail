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
    var buyNote = $('#buyNote'), stockNote = $('#stockNote'), emailNote = $('#emailNote');
    /* data-preview="1" on #picker in the page's HTML: not trading yet, so no Order or Buy now route at all.
       Remove the attribute at launch. */
    var preview = picker.getAttribute('data-preview') === '1';
    function val(name) { var el = picker.querySelector('input[name="' + name + '"]:checked'); return el ? el.value : ''; }
    function update() {
      var st = val('storage'), gr = val('grade'), co = val('colour');
      var price = prices[st] && prices[st][gr];
      if (price == null) return;
      priceEl.textContent = gbp(price);
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
    picker.addEventListener('change', update);
    update();
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
    filters.addEventListener('change', apply);
    filters.addEventListener('submit', function (e) { e.preventDefault(); apply(); });
    var reset = $('#resetFilters');
    if (reset) reset.addEventListener('click', function () { filters.reset(); apply(); });
    apply();
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
