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
  /* JSON from a data- attribute, or null if it's missing or isn't valid JSON (e.g. a typo in a hand edit) */
  function dataJSON(el, name) {
    var raw = el && el.getAttribute(name);
    if (!raw) return null;
    try { var v = JSON.parse(raw); return v && typeof v === 'object' ? v : null; }
    catch (e) { if (window.console) console.warn('Full Bars: ' + name + ' is not valid JSON, so it is ignored', e); return null; }
  }
  function isObj(v) { return !!v && typeof v === 'object' && !Array.isArray(v); }

  /* ---------- stock (stock.js) ----------
     stock.js sets window.FULLBARS_STOCK = { "iphone-13": { "128GB|Good": 2, ... }, ... }: for each product handle (its
     page name), the units held per storage and condition. A handle that isn't there has no stock data. stock.js is
     loaded before this script; if it is missing or broken, this is {} and nothing changes. */
  var STOCK = isObj(window.FULLBARS_STOCK) ? window.FULLBARS_STOCK : {};
  function stockFor(handle) {
    var v = handle && Object.prototype.hasOwnProperty.call(STOCK, handle) ? STOCK[handle] : null;
    return isObj(v) ? v : null;
  }
  /* a count that means units held: a whole number above 0 */
  function held1(n) { return typeof n === 'number' && isFinite(n) && Math.floor(n) === n && n > 0; }
  function anyHeld(map) { return Object.keys(map).some(function (k) { return held1(map[k]); }); }
  /* "iphone-13" from a link or address such as ../products/iphone-13.html */
  function handleOf(href) { var m = /(?:^|\/)products\/([a-z0-9-]+)\.html(?:[?#]|$)/.exec(href || ''); return m ? m[1] : ''; }

  /* ---------- web fonts ----------
     Each page loads the Google Fonts stylesheet with media="print" so a slow or blocked fonts server can't hold
     up the first paint; its inline onload switches it on. This is the backup if inline handlers are blocked. */
  $all('link[data-fonts]').forEach(function (l) {
    if (l.media === 'all') return;
    function on() { l.media = 'all'; }
    if (l.sheet) on(); else l.addEventListener('load', on);
  });

  /* ---------- mobile menu ---------- */
  var menuBtn = $('#menuBtn'), drawer = $('#drawer');
  if (menuBtn && drawer) {
    var closeDrawer = function () { drawer.classList.remove('open'); menuBtn.setAttribute('aria-expanded', 'false'); };
    menuBtn.addEventListener('click', function () {
      var open = drawer.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    /* Escape closes the drawer and puts focus back on the button that opened it */
    document.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.key === 'Esc') && drawer.classList.contains('open')) {
        closeDrawer();
        menuBtn.focus();
      }
    });
    /* Tabbing on past the last menu link closes the menu, so focus never lands on the page hidden behind it.
       A tap on empty space, or the window losing focus, has no relatedTarget and leaves it open. */
    var siteHeader = menuBtn.closest ? menuBtn.closest('header') : null;
    if (siteHeader) siteHeader.addEventListener('focusout', function (e) {
      var to = e.relatedTarget;
      if (to && !siteHeader.contains(to) && drawer.classList.contains('open')) closeDrawer();
    });
    /* close it as the page is left, so coming Back from the Back/Forward cache doesn't show it still open */
    window.addEventListener('pagehide', function () { if (drawer.classList.contains('open')) closeDrawer(); });
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
    /* keyboard: browsers leave a partly visible chip half off the row when it takes focus, so bring it in */
    ul.addEventListener('focusin', function (e) {
      if (ul.scrollWidth <= ul.clientWidth) return;
      var ur = ul.getBoundingClientRect(), ar = e.target.getBoundingClientRect(), pad = 16;
      if (ar.right > ur.right - pad) ul.scrollLeft += ar.right - (ur.right - pad);
      else if (ar.left < ur.left + pad) ul.scrollLeft -= (ur.left + pad) - ar.left;
    });
  });

  /* ---------- toast + copy ---------- */
  var toastEl = $('#toast'), toastT;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg; toastEl.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(function () { toastEl.hidden = true; }, 2800);
  }
  function copyText(text, ok) {
    var fail = function () { toast('Couldn’t copy automatically — select the text and copy it.'); };
    /* some sandboxes and in-app browsers throw straight away instead of rejecting the promise */
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { toast(ok); }, fail);
      else fail();
    } catch (e) { fail(); }
  }
  $all('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () { copyText(b.getAttribute('data-copy'), 'Copied'); });
  });

  /* ---------- product option picker ----------
     The form carries every price as JSON in data-prices: { "128GB": { "Excellent": 249, ... }, ... }.
     Static route: the Order button goes to the contact page with the chosen phone filled in. If pay.js has a
     Stripe Payment Link for "<model> <storage> <grade>", the button becomes "Buy now" instead.
     Shopify route: go_live.py puts data-shop="https://<shop>/products/<handle>" on #picker. The Order button then
     always goes to that Shopify product (Shopify holds the stock), with ?variant=<id> when data-variants has an ID
     for the storage, condition and colour chosen, and no email-order (contact.html?order=) or Payment Link is ever
     built on that page, so the same phone can't be sold twice. */
  /* The picker's fieldsets ship disabled, so without this script (JavaScript off, or site.js failing to load) the
     ticked options can't be changed and always match the price shown. They are enabled below, once the script has
     taken over; if data-prices can't be read they stay disabled. Disabled rather than hidden: no layout shift. */
  var picker = $('#picker'), pickerPrices = dataJSON(picker, 'data-prices');
  /* Every storage and condition on the page needs a price. Without one, a click could tick an option the price and
     the Order link can't follow, so the options stay disabled instead (availability belongs in data-stock). */
  if (picker && pickerPrices && !$all('input[name="storage"]', picker).every(function (s) {
    return $all('input[name="grade"]', picker).every(function (g) {
      var row = pickerPrices[s.value], p = row && row[g.value];
      return typeof p === 'number' && isFinite(p) && p > 0;
    });
  })) {
    if (window.console) console.warn('Full Bars: data-prices has no price for every storage and condition on this page, so the options stay disabled');
    pickerPrices = null;
  }
  if (picker && pickerPrices) {
    var prices = pickerPrices;
    var model = picker.getAttribute('data-model');
    var contactUrl = picker.getAttribute('data-contact');
    var grades = dataJSON(picker, 'data-grades') || {};
    /* Stock: this phone's entry in stock.js (keyed by the handle in the page's canonical address), or else the
       page's own data-stock attribute (the older place; stock.js wins when both are there). Either way it is
       { "128GB|Good": 2, ... }, the number of units held for each storage and condition (colour isn't tracked).
       A missing key, 0 or anything that isn't a whole number above 0 means not in stock. With neither, every
       option counts as available and no 'not in stock' note is shown (go_live.py won't launch the static route
       like that). A data-stock that isn't valid JSON is ignored (with a console warning), so a typo can't freeze
       the price. */
    var canon = $('link[rel="canonical"]');
    var stock = stockFor(handleOf(canon && canon.getAttribute('href')) || handleOf(location.pathname)) || dataJSON(picker, 'data-stock');
    function inStock(key) { return held1(stock[key]); }
    /* Shopify route: data-variants (written by go_live.py --shop-variants) maps "storage|condition|colour" to that
       phone's Shopify variant ID, so the Order button can open Shopify on exactly the phone chosen here. */
    var variants = dataJSON(picker, 'data-variants') || {};
    /* Shopify route (see above). Only an https:// address is used; any other value is ignored with a warning,
       and the page still never offers an email order or a Payment Link. */
    var shopAttr = picker.getAttribute('data-shop');
    var shopMode = shopAttr !== null;
    var shopUrl = shopMode && /^https:\/\/[^\s"'<>]+$/.test(shopAttr) ? shopAttr : '';
    if (shopMode && !shopUrl && window.console) console.warn('Full Bars: data-shop is not an https:// address, so the Order button only offers a question');
    var priceEl = $('#pdPrice'), orderBtn = $('#orderBtn'), lineEl = $('#selLine'), gradeNote = $('#gradeNote');
    var buyNote = $('#buyNote'), stockNote = $('#stockNote'), emailNote = $('#emailNote'), fromEl = $('#pdFrom');
    var handoffNote = $('#handoffNote');
    /* the lowest price across every option, and which option it is: the 'from' price the cards show */
    var minP = null, minSt = '', minGr = '';
    Object.keys(prices).forEach(function (s) {
      Object.keys(prices[s] || {}).forEach(function (g) { var v = prices[s][g]; if (typeof v === 'number' && (minP === null || v < minP)) { minP = v; minSt = s; minGr = g; } });
    });
    /* data-preview="1" on #picker in the page's HTML: not trading yet, so no Order or Buy now route at all.
       Remove the attribute at launch. */
    var preview = picker.getAttribute('data-preview') === '1';
    /* At launch the Order button must be a link. If the page still has the preview's inert <span>, swap it for
       an <a> so every phone stays orderable (GO-LIVE.md also says to change the markup). */
    if (!preview && orderBtn && orderBtn.tagName !== 'A') {
      var realBtn = document.createElement('a');
      realBtn.id = 'orderBtn';
      realBtn.className = orderBtn.className.replace(/(^|\s)btn-off(?=\s|$)/g, ' ').replace(/\s+/g, ' ').trim();
      realBtn.textContent = orderBtn.textContent;
      orderBtn.parentNode.replaceChild(realBtn, orderBtn);
      orderBtn = realBtn;
    }
    function val(name) { var el = picker.querySelector('input[name="' + name + '"]:checked'); return el ? el.value : ''; }
    /* The choice is kept in the address (?storage=256GB&grade=Good&colour=Green), so Back, refresh and a shared
       link all show the same phone at the same price. Unknown values are ignored, and replaced in the address
       below (pickDropped) so it matches what's ticked, as the shop does with its filters. */
    var KEYS = ['storage', 'grade', 'colour'], pickDropped = false;
    try {
      var want = new URLSearchParams(location.search);
      KEYS.forEach(function (k) {
        if (!want.has(k)) return;
        var v = want.get(k);
        var r = v ? $all('input[name="' + k + '"]', picker).filter(function (i) { return i.value === v; })[0] : null;
        if (r) r.checked = true; else pickDropped = true;
      });
    } catch (e) { /* no URLSearchParams: keep the page's own default */ }
    function rememberPick() {
      try {
        var q = new URLSearchParams(location.search);
        KEYS.forEach(function (k) { var v = val(k); if (v) q.set(k, v); else q.delete(k); });
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
        var s = r.parentNode.querySelector('small'), v = prices[st][r.value]; if (s) s.textContent = v == null ? '' : gbp(v);
      });
      $all('input[name="storage"]', picker).forEach(function (r) {
        var s = r.parentNode.querySelector('small'), v = prices[r.value] && prices[r.value][gr]; if (s) s.textContent = v == null ? '' : gbp(v);
      });
      if (gradeNote && grades[gr]) gradeNote.textContent = grades[gr];
      $all('#pdArt [data-colour]').forEach(function (v) { v.hidden = v.getAttribute('data-colour') !== co; });
      var label = model + ' ' + st + ', ' + gr + (co ? ', ' + co : '');
      var held = !stock || inStock(st + '|' + gr);
      if (lineEl) lineEl.textContent = 'Selected: ' + label + ' — ' + gbp(price) + (held ? '' : ' (not in stock right now)');
      /* show which options are in stock when the owner tracks stock */
      if (stock) {
        $all('input[name="storage"]', picker).forEach(function (r) { r.parentNode.classList.toggle('na', !inStock(r.value + '|' + gr)); });
        $all('input[name="grade"]', picker).forEach(function (r) { r.parentNode.classList.toggle('na', !inStock(st + '|' + r.value)); });
      }
      /* never a Payment Link on a Shopify-route page */
      var link = shopMode ? '' : PAY[model + ' ' + st + ' ' + gr];
      var buyNow = !preview && held && link && /^https:\/\//.test(link) && price <= BUY_NOW_MAX;
      var handoff = false;
      if (preview) {
        orderBtn.textContent = 'Opening soon';
      } else if (shopMode && held && shopUrl) {
        /* Shopify route. With a variant ID for this storage, condition and colour, open Shopify on exactly that phone
           (?variant=), at the price shown here. Without one, Shopify would open on its own first variant, perhaps at
           another price, so the button names no price and the note under it says they'll choose again there. */
        var vid = variants[st + '|' + gr + '|' + co];
        vid = vid == null ? '' : String(vid);
        orderBtn.setAttribute('rel', 'noopener');
        if (/^[0-9]+$/.test(vid)) {
          orderBtn.setAttribute('href', shopUrl + (shopUrl.indexOf('?') < 0 ? '?' : '&') + 'variant=' + vid);
          orderBtn.textContent = 'Order — ' + gbp(price);
        } else {
          orderBtn.setAttribute('href', shopUrl);
          orderBtn.textContent = 'Choose and pay on the next page';
          handoff = true;
        }
      } else if (shopMode && held) {
        orderBtn.setAttribute('href', contactUrl + '?ask=' + encodeURIComponent(label) + '#form');
        orderBtn.removeAttribute('rel');
        orderBtn.textContent = 'Ask us about this phone';
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
      if (handoffNote) handoffNote.hidden = !handoff;
      /* screen readers hear the note with the button it explains */
      if (handoff && handoffNote) orderBtn.setAttribute('aria-describedby', 'handoffNote'); else orderBtn.removeAttribute('aria-describedby');
    }
    picker.addEventListener('change', function () { update(); rememberPick(); });
    update();
    $all('fieldset[disabled]', picker).forEach(function (f) { f.disabled = false; });
    /* a stale or hand-edited link (?storage=9TB): put what is actually ticked in the address instead */
    if (pickDropped) rememberPick();
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

  /* ---------- "None in stock right now" on cards and range tiles ----------
     Only for phones stock.js lists with no units at all. A phone it doesn't list says nothing (no stock data), and
     the card stays in place either way, with its "from" price (the lowest price of any option, held or not). */
  var NONE_IN_STOCK = 'None in stock right now';
  $all('article.card').forEach(function (card) {
    var a = $('a[href]', card), map = stockFor(handleOf(a && a.getAttribute('href'))), body = $('.card-body', card);
    if (!map || anyHeld(map) || !body || $('.card-stock', body)) return;
    var p = document.createElement('p');
    p.className = 'card-stock';
    p.textContent = NONE_IN_STOCK;
    body.appendChild(p);
  });
  /* a range tile (home page) lists its phones in data-handles: the note shows only when stock.js lists every one of
     them, with no units */
  $all('a.tile[data-handles]').forEach(function (tile) {
    var hs = tile.getAttribute('data-handles').split(/\s+/).filter(Boolean);
    if (!hs.length || $('.tile-stock', tile) || !hs.every(function (h) { var m = stockFor(h); return m && !anyHeld(m); })) return;
    var em = document.createElement('em');
    em.className = 'tile-stock';
    em.textContent = NONE_IN_STOCK;
    tile.appendChild(em);
  });

  /* ---------- shop filters ---------- */
  var filters = $('#filters'), grid = $('#shopGrid');
  if (filters && grid) {
    var cards = $all('.card', grid), countEl = $('#resultCount'), empty = $('#emptyMsg');
    var params = new URLSearchParams(location.search), dropped = false;
    /* only take a value the dropdown actually offers: an unknown one (a stale or hand-edited link) would blank it */
    ['series', 'type', 'max', 'sort'].forEach(function (k) {
      var el = filters.elements[k], v = params.get(k);
      if (!el || !v) return;
      if ($all('option', el).some(function (o) { return o.value === v; })) el.value = v; else dropped = true;
    });
    if (params.get('usbc') === '1') filters.elements.usbc.checked = true;
    else if (params.has('usbc')) dropped = true;
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
    /* 'Clear filters' by the count, and the one in the 'No phones match' box further down */
    var reset = $('#resetFilters');
    $all('#resetFilters, [data-reset-filters]').forEach(function (b) {
      b.addEventListener('click', function () {
        filters.reset(); apply(); rememberFilters();
        /* the box's own button disappears with the box: keep focus on the one that stays */
        if (b !== reset && reset) reset.focus();
      });
    });
    apply();
    /* drop values we couldn't use from the address, so it matches what the filters show */
    if (dropped) rememberFilters();
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
    /* data-preview: not trading yet. The form checks what was typed but never opens an email or sends anything,
       and says so plainly. Copy is hidden too: the address isn't live until we open. */
    var formPreview = form.getAttribute('data-preview') === '1';
    /* only pick a topic the list actually has (preview mode has no "Order a phone"); otherwise keep the first one */
    function hasTopic(v) { for (var j = 0; j < topic.options.length; j++) if (topic.options[j].value === v) return true; return false; }
    function setTopic(v) { if (hasTopic(v)) topic.value = v; }
    /* no Order route in preview, or on the Shopify route (go_live.py adds the "Order a phone" topic only on the
       static route), so an ?order= link there (an old or crafted one) is ignored instead of starting an email order */
    if (q.get('order') && !formPreview && hasTopic('Order a phone')) {
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
    if (formPreview && $('#copyMsg')) $('#copyMsg').hidden = true;
    /* Handled on the button's click as well as the form's submit: in a sandboxed frame without allow-forms the
       browser blocks the submission before 'submit' fires, but the click (and Enter in a field, which clicks the
       button) still arrives. preventDefault on the click stops the submission, so this never runs twice. */
    function onSend(e) {
      e.preventDefault();
      var c = composed();
      if (!c.name || !c.msg) { status.textContent = 'Add your name and a message first.'; return; }
      if (formPreview) {
        status.textContent = 'Nothing has been sent. Full Bars isn’t trading yet, so this form isn’t connected to an inbox and your message hasn’t left this page. When we open, this button will open your own email app with the message ready to send.';
        return;
      }
      mailto(c.topic + (c.name ? ' — ' + c.name : ''), c.body);
      status.textContent = 'Your email app should open with this message ready — press send there. If nothing opened, use “Copy message” and email it to ' + EMAIL + '.';
    }
    form.addEventListener('submit', onSend);
    $all('button[type="submit"]', form).forEach(function (b) { b.addEventListener('click', onSend); });
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
