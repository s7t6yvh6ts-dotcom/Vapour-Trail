/* Grace & Bloom — storefront: product grid, quick view, basket, small interactions. */
(function () {
  var GB = window.GB, cfg = GB.config;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var money = function (n) { return cfg.currency + n.toFixed(2); };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var touch = window.matchMedia && window.matchMedia('(hover: none)').matches;
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  var esc = function (s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  /* [square brackets] in product copy mark things still to confirm, and are highlighted */
  var rich = function (s) { return esc(s).replace(/\[([^\]]+)\]/g, '<span class="ph">[$1]</span>'); };

  /* ---------- artwork ----------
     Pictures are painted only when they near the screen (then the rest in idle time), one at a time,
     after the display fonts load, and encoded with toBlob, which runs off the main thread. Until a
     picture is ready its <img> shows blank paper of the right size, so nothing shifts or blocks taps. */
  var PAINT = {}, sameKey = {}, queued = {}, queue = [], pending = [], busy = false, fontsReady = false, bgOk = false;
  function dims(p) { return p.kind === 'bookmark' ? [320, 860] : [640, 800]; }
  function blank(p) {
    var d = dims(p), pal = (GB.palettes && GB.palettes[p.art.palette]) || { bg: ['#f4f1ee'] };
    return 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + d[0] + ' ' + d[1] + '"><rect width="100%" height="100%" fill="' + pal.bg[0] + '"/></svg>');
  }
  /* blob: pictures are encoded off the main thread; if the host's security policy blocks blob: images, use data: URLs instead */
  var useBlob = null;
  (function () {
    var c = document.createElement('canvas'); c.width = c.height = 1;
    if (!(c.toBlob && window.URL && URL.createObjectURL)) { useBlob = false; return; }
    try {
      c.toBlob(function (b) {
        if (!b) { useBlob = false; return pump(); }
        var u = URL.createObjectURL(b), im = new Image();
        im.onload = function () { useBlob = true; pump(); };
        im.onerror = function () { useBlob = false; pump(); };
        im.src = u;
      }, 'image/png');
    } catch (e) { useBlob = false; }
  })();
  function idle(fn, ms) { if (window.requestIdleCallback) requestIdleCallback(fn, { timeout: ms || 2000 }); else setTimeout(fn, 120); }
  var lazy = 'IntersectionObserver' in window ? new IntersectionObserver(function (en) {
    en.forEach(function (e) { if (e.isIntersecting) fire(e.target); });
  }, { rootMargin: '400px 0px' }) : null;
  function later(el, run) { el._run = run; pending.push(el); if (lazy) lazy.observe(el); else fire(el); }
  function fire(el) { var run = el._run; if (!run) return; el._run = null; if (lazy) lazy.unobserve(el); run(); }
  function pump() {
    if (busy || !fontsReady || useBlob === null) return;
    var job = queue.shift();
    if (!job) { if (bgOk) fill(); return; }
    busy = true;
    var over = false, done = function () { if (over) return; over = true; busy = false; setTimeout(pump, 0); };
    try { job(done); } catch (e) { done(); }
  }
  var filling = false;
  function fill() {
    if (filling) return; filling = true;
    idle(function () {
      filling = false;
      while (pending.length && !(pending[0]._run && pending[0].isConnected)) pending.shift();
      if (pending.length) fire(pending.shift());
    }, 300); // background pictures wait for a quiet moment, but never long, so scrolling rarely meets blank paper
  }
  function paintArt(j, next) {
    var cv = GB.art.make(j.p, j.s);
    function finish(u) {
      // every <img> of this picture gets it now, wherever it is on the page
      if (u) { PAINT[j.key] = u; (sameKey[j.key] || []).forEach(function (im) { im.src = u; if (im._run) { im._run = null; if (lazy) lazy.unobserve(im); } }); delete sameKey[j.key]; }
      delete queued[j.key];
      GB.art.release(j.p, j.s);
      if (j.s === 1) cv.width = cv.height = 0; // only this script uses scale 1 (the 3D hero paints its own), so free the pixels now
      next();
    }
    function jpeg() { try { return cv.toDataURL('image/jpeg', 0.9); } catch (e) { return ''; } }
    if (useBlob) {
      try { cv.toBlob(function (b) { finish(b ? URL.createObjectURL(b) : jpeg()); }, 'image/jpeg', 0.9); return; } catch (e) {}
    }
    finish(jpeg());
  }
  function want(img, j) {
    if (PAINT[j.key]) img.src = PAINT[j.key];
    else if (!queued[j.key]) { queued[j.key] = true; queue.push(function (next) { paintArt(j, next); }); }
    pump();
  }
  /* point an <img> at a product's picture: at once if it's painted, otherwise when it nears the screen */
  function bindArt(img, p, scale) {
    var key = p.id + '@' + scale, d = dims(p);
    img.width = d[0]; img.height = d[1]; img.decoding = 'async'; img.draggable = false;
    img.src = PAINT[key] || PAINT[p.id + '@1'] || blank(p);
    if (!PAINT[key]) { (sameKey[key] = sameKey[key] || []).push(img); later(img, function () { want(img, { p: p, s: scale, key: key }); }); }
    return img;
  }

  /* ---------- 3D-ish product mockups (pure CSS transforms) ---------- */
  function mock(p, scale, alt) {
    var el = document.createElement('div');
    el.className = 'mock mock--' + p.kind;
    var inner = '<div class="obj">';
    if (p.kind === 'calendar') inner += '<i class="rings"></i><i class="hook"></i>';
    inner += '<img alt="' + esc(alt || '') + '">';
    inner += '<i class="gloss"></i></div><i class="drop"></i>';
    el.innerHTML = inner;
    bindArt($('img', el), p, scale || 1);
    return el;
  }
  function tilt(host, target) {
    if (reduce || touch) return;
    target = target || host;
    host.addEventListener('pointermove', function (e) {
      var r = host.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      target.style.setProperty('--ry', (x * 10).toFixed(1) + 'deg');
      target.style.setProperty('--rx', (-y * 7).toFixed(1) + 'deg');
      target.style.setProperty('--gx', ((x + 0.5) * 100).toFixed(0) + '%');
      target.style.setProperty('--gy', ((y + 0.5) * 100).toFixed(0) + '%');
    });
    host.addEventListener('pointerleave', function () {
      target.style.setProperty('--ry', '0deg'); target.style.setProperty('--rx', '0deg');
    });
  }
  /* hero picture first, so it is the first thing painted */
  var fb = $('.hero-stage .fallback');
  if (fb) fb.appendChild(mock(GB.byId('peony-birthday'), 1, ''));

  /* ---------- shop ---------- */
  var grid = $('#grid'), state = { cat: 'all', occ: -1, q: '', sort: 'featured' };
  var OCCASIONS = [
    ['Birthday', function (p) { return has(p, 'birthday'); }],
    ['Christmas', function (p) { return has(p, 'christmas'); }],
    ['Thank you', function (p) { return has(p, 'thank you'); }],
    ['Get organised', function (p) { return has(p, 'organise'); }],
    ['Money & goals', function (p) { return has(p, 'money') || has(p, 'goals'); }],
    ['For the wall', function (p) { return has(p, 'wall art'); }]
  ];
  function has(p, t) { return (GB.tags[p.id] || []).indexOf(t) > -1; }
  function catLabel(id) { var c = GB.categories.filter(function (c) { return c.id === id; })[0]; return c ? c.label : id; }
  function inCart(id) { return cart.some(function (l) { return l.id === id; }); }

  function card(p, i) {
    var a = document.createElement('article');
    a.className = 'product reveal'; a.style.setProperty('--d', (i % 4) * 70 + 'ms'); a.dataset.id = p.id;
    a.innerHTML =
      '<button class="stage" type="button" aria-haspopup="dialog" aria-label="Quick view: ' + esc(p.name) + '"></button>' +
      (p.badge ? '<span class="badge">' + esc(p.badge) + '</span>' : '') +
      '<button class="fav" type="button" aria-label="Save ' + esc(p.name) + '" aria-pressed="false"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-7.5-10A4.2 4.2 0 0 1 12 8a4.2 4.2 0 0 1 7.5 2.5c0 5.4-7.5 10-7.5 10z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></button>' +
      '<div class="meta"><h3>' + esc(p.name) + '</h3><p class="cat">' + esc(catLabel(p.cat)) + '</p>' +
      // products with options open the quick view to choose them; the hidden name gives screen readers context
      '<div class="row"><span class="price">' + money(p.price) + '</span><button class="add" type="button" data-add="' + p.id + '"' + (p.variants ? ' aria-haspopup="dialog"' : '') + '><span class="add-t"></span><span class="sr">: ' + esc(p.name) + '</span></button></div></div>';
    var st = $('.stage', a); st.appendChild(mock(p, 1)); tilt(st, $('.mock', st));
    st.addEventListener('click', function () { openModal(p); });
    var fav = $('.fav', a), favs = store.get('gb-favs', []);
    if (favs.indexOf(p.id) > -1) { fav.setAttribute('aria-pressed', 'true'); }
    fav.addEventListener('click', function () {
      var f = store.get('gb-favs', []), on = f.indexOf(p.id) > -1;
      f = on ? f.filter(function (x) { return x !== p.id; }) : f.concat(p.id);
      store.set('gb-favs', f); fav.setAttribute('aria-pressed', String(!on)); toast(on ? 'Removed from favourites' : 'Saved to favourites (on this device)');
    });
    return a;
  }
  /* "Add" becomes "In basket" once a design is in the basket: each download is bought once */
  function syncAdd() {
    $$('.add[data-add]').forEach(function (b) {
      var p = GB.byId(b.dataset.add), on = inCart(p.id);
      b.classList.toggle('is-in', on);
      $('.add-t', b).textContent = on ? 'In basket' : (p.variants ? 'Choose' : 'Add');
    });
  }
  function haystack(p) { return (p.name + ' ' + p.blurb + ' ' + catLabel(p.cat) + ' ' + (GB.tags[p.id] || []).join(' ')).toLowerCase(); }
  var gridStatus = $('#grid-status');
  function status(el, msg, wait) { clearTimeout(el._t); el._t = setTimeout(function () { el.textContent = msg; }, wait || 0); }
  function render(announce) {
    grid.innerHTML = '';
    var q = state.q.trim().toLowerCase();
    var items = GB.products.filter(function (p) {
      return (state.cat === 'all' || p.cat === state.cat) && (state.occ < 0 || OCCASIONS[state.occ][1](p)) && (!q || haystack(p).indexOf(q) > -1);
    });
    if (state.sort === 'low') items.sort(function (x, y) { return x.price - y.price; });
    else if (state.sort === 'high') items.sort(function (x, y) { return y.price - x.price; });
    if (!items.length) grid.innerHTML = '<p class="none">Nothing matches that yet. Try “birthday”, “planner” or “print”, or clear the filters.</p>';
    items.forEach(function (p, i) { grid.appendChild(card(p, i)); });
    $('#count').textContent = items.length === GB.products.length ? GB.products.length + ' designs' : 'Showing ' + items.length + ' of ' + GB.products.length + ' designs';
    $$('#chips .chip').forEach(function (c) { c.setAttribute('aria-pressed', String(state.occ < 0 && c.dataset.filter === state.cat)); });
    $$('#occasions .chip').forEach(function (c, i) { c.setAttribute('aria-pressed', String(i === state.occ)); });
    syncAdd(); observe();
    if (announce) status(gridStatus, (items.length ? 'Showing ' + items.length + (items.length === 1 ? ' product' : ' products') : 'No products') +
      (state.occ >= 0 ? ' for ' + OCCASIONS[state.occ][0] : state.cat === 'all' ? '' : ' in ' + catLabel(state.cat)) + (q ? ' matching “' + state.q.trim() + '”' : '') + '.', announce === 'typing' ? 600 : 0);
  }
  function setCat(c, announce) { state.cat = c; state.occ = -1; render(announce); }
  var chips = $('#chips');
  [{ id: 'all', label: 'All' }].concat(GB.categories).forEach(function (c) {
    var b = document.createElement('button'); b.className = 'chip'; b.dataset.filter = c.id; b.textContent = c.label;
    b.type = 'button'; b.addEventListener('click', function () { setCat(c.id, true); }); chips.appendChild(b);
  });
  OCCASIONS.forEach(function (o, i) {
    var b = document.createElement('button'); b.className = 'chip chip--sm'; b.type = 'button'; b.textContent = o[0];
    b.addEventListener('click', function () { state.occ = state.occ === i ? -1 : i; state.cat = 'all'; render(true); }); $('#occasions').appendChild(b);
  });
  $('#q').addEventListener('input', function (e) { state.q = e.target.value; render('typing'); });
  $('#sort').addEventListener('change', function (e) { state.sort = e.target.value; render(true); });

  /* ---------- collections ---------- */
  var cols = $('#collections-grid');
  GB.categories.forEach(function (c, i) {
    var p = GB.byId(c.rep), a = document.createElement('a');
    a.href = '#shop'; a.className = 'collection reveal'; a.style.setProperty('--d', i * 80 + 'ms');
    a.innerHTML = '<div class="cstage"></div><h3>' + esc(c.label) + '</h3><p>' + esc(c.blurb) + '</p><span class="more">Explore&nbsp;→</span>';
    $('.cstage', a).appendChild(mock(p, 1, '')); tilt(a, $('.mock', a));
    a.addEventListener('click', function () { setCat(c.id, true); });
    cols.appendChild(a);
  });

  /* ---------- ADHD spotlight fan ---------- */
  var fan = $('#fan');
  if (fan) {
    ['focus-planner', 'brain-dump-pad', 'weekly-reset'].forEach(function (id, i) {
      var h = document.createElement('div'); h.className = 'fan-item fan-' + i; h.appendChild(mock(GB.byId(id), 1)); fan.appendChild(h);
    });
    tilt(fan, fan);
  }

  /* ---------- quick view ---------- */
  var modal = $('#modal'), mbody = $('#modal-body'), lastFocus, qv, modalT, drawerT, mOpen = false;
  /* while a dialog is open, everything behind it is inert (no focus, hidden from screen readers) */
  var drawerEl = $('#cart');
  var behind = $$('body > *').filter(function (el) { return el !== modal && el !== drawerEl && el.id !== 'toast' && el.tagName !== 'SCRIPT'; });
  function setInert(on) { behind.forEach(function (el) { if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert'); }); }
  function relatedHtml(p) {
    var r = GB.products.filter(function (x) { return x.cat === p.cat && x.id !== p.id; });
    if (r.length < 3) r = r.concat(GB.products.filter(function (x) { return x.cat !== p.cat && x.id !== p.id; }));
    return '<div class="related"><h3>You may also like</h3><div class="rel-row">' + r.slice(0, 3).map(function (x) {
      return '<button class="rel" type="button" data-rel="' + x.id + '"><img alt="" data-art="' + x.id + '"><span>' + esc(x.name) + '</span><small>' + money(x.price) + '</small></button>';
    }).join('') + '</div></div>';
  }
  function openModal(p) {
    // swap: a related product replaces the one on show, so focus still returns to whatever first opened the dialog
    var swap = mOpen;
    if (!swap) lastFocus = document.activeElement;
    mOpen = true; qv = { p: p, v: 0 }; clearTimeout(modalT);
    var no = GB.products.indexOf(p) + 1;
    var vr = p.variants;
    mbody.innerHTML =
      '<div class="qv-stage"></div><div class="qv-info">' +
      '<p class="cat">' + esc(catLabel(p.cat)) + ' · No.&nbsp;' + (no < 10 ? '0' : '') + no + '</p><h2 id="modal-title" tabindex="-1">' + esc(p.name) + '</h2>' +
      '<p class="qv-price" id="qv-price"></p><p class="blurb">' + esc(p.blurb) + '</p>' +
      (vr ? '<fieldset class="opts"><legend>' + esc(vr.label) + '</legend>' + vr.options.map(function (o, i) { return '<label><input type="radio" name="v" value="' + i + '"' + (i === 0 ? ' checked' : '') + '><span>' + esc(o[0]) + '</span></label>'; }).join('') + '</fieldset>' : '') +
      '<button class="btn btn--primary btn--block" id="qv-add" type="button"></button>' +
      '<p class="digital"><b>Digital download.</b> You receive the files after purchase and nothing is posted. Formats and sizes: <span class="ph">[to confirm]</span>.</p>' +
      (p.etsyUrl ? '<a class="etsy" href="' + esc(p.etsyUrl) + '" target="_blank" rel="noopener">Also available on Etsy →</a>' : '') + '<ul class="details">' + p.details.map(function (d) { return '<li>' + rich(d) + '</li>'; }).join('') + '</ul>' + relatedHtml(p) + '</div>';
    $$('[data-rel]', mbody).forEach(function (b) { b.addEventListener('click', function () { openModal(GB.byId(b.dataset.rel)); }); });
    $$('.related img[data-art]', mbody).forEach(function (im) { bindArt(im, GB.byId(im.dataset.art), 1); });
    var st = $('.qv-stage', mbody); st.appendChild(mock(p, 1.3, p.name)); tilt(st, $('.mock', st));
    function price() { return p.price + (vr ? vr.options[qv.v][1] : 0); }
    function upd() { $('#qv-price').textContent = money(price()); $('#qv-add').textContent = inCart(p.id) ? 'In your basket' : 'Add to basket'; }
    upd();
    $$('input[name=v]', mbody).forEach(function (r) { r.addEventListener('change', function () { qv.v = +r.value; upd(); }); });
    $('#qv-add').addEventListener('click', function () { add(p.id, qv.v, true); closeModal(); openCart(); });
    modal.hidden = false; document.body.classList.add('locked'); setInert(true);
    // the clicked related button has just been replaced, so focus moves to the new product's name (screen readers hear what changed)
    if (swap) { $('.modal-box', modal).scrollTop = 0; $('#modal-title').focus({ preventScroll: true }); }
    else requestAnimationFrame(function () { modal.classList.add('on'); $('.modal-close', modal).focus(); });
  }
  function closeModal() {
    mOpen = false; modal.classList.remove('on'); document.body.classList.remove('locked'); setInert(false);
    modalT = setTimeout(function () { modal.hidden = true; }, 250); if (lastFocus) lastFocus.focus();
  }
  $('.modal-close', modal).addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });

  /* ---------- basket ---------- */
  /* each download is bought once: any saved quantity or duplicate from an older version is tidied to one */
  var cart = store.get('gb-cart', []).filter(function (l) {
    var p = l && GB.byId(l.id);
    return p && (!p.variants || p.variants.options[l.v]);
  }).filter(function (l, i, a) { return a.findIndex(function (x) { return x.id === l.id; }) === i; }).map(function (l) { return { id: l.id, v: l.v || 0 }; });
  var drawer = $('#cart'), list = $('#cart-list'), checkout = $('#cart-checkout');
  function add(id, v, quiet) {
    if (inCart(id)) { if (!quiet) toast('Already in your basket'); return false; }
    cart.push({ id: id, v: v || 0 });
    save(); if (!quiet) toast('Added to your basket');
    return true;
  }
  function unit(l) { var p = GB.byId(l.id); return p.price + (p.variants ? p.variants.options[l.v][1] : 0); }
  function save() { store.set('gb-cart', cart); var m = $('#checkout-msg'); if (m) m.textContent = ''; paint(); }
  function paint() {
    var n = cart.length, sub = cart.reduce(function (s, l) { return s + unit(l); }, 0);
    $$('.cart-count').forEach(function (c) { c.textContent = n; c.hidden = !n; });
    // the visible count is part of the button's name, so screen readers hear it too
    $$('[data-open-cart]').forEach(function (b) { b.setAttribute('aria-label', n ? 'Open basket, ' + n + (n === 1 ? ' item' : ' items') : 'Open basket'); });
    if (!cart.length) list.innerHTML = '<li class="empty"><p>Your basket is empty.</p><a class="btn btn--ghost" href="#shop" data-close>Browse the shop</a></li>';
    else list.innerHTML = cart.map(function (l, i) {
      var p = GB.byId(l.id);
      return '<li><img alt="" data-art="' + esc(p.id) + '"><div><h3>' + esc(p.name) + '</h3><small>' + (p.variants ? esc(p.variants.options[l.v][0]) + ' · ' : '') + 'Digital download</small></div>' +
        '<div class="end"><strong>' + money(unit(l)) + '</strong><button class="rm" type="button" data-rm="' + i + '" aria-label="Remove ' + esc(p.name) + '">Remove</button></div></li>';
    }).join('');
    $$('img[data-art]', list).forEach(function (im) { bindArt(im, GB.byId(im.dataset.art), 1); });
    $('#cart-total').textContent = money(sub);
    if (checkout.tagName === 'A') { if (cart.length) checkout.removeAttribute('aria-disabled'); else checkout.setAttribute('aria-disabled', 'true'); }
    else checkout.disabled = !cart.length;
    var up = $('#upsell'), tags = GB.byId('posy-gift-tags');
    var want = tags && cart.some(function (l) { return GB.byId(l.id).cat === 'cards'; }) && !inCart(tags.id);
    up.hidden = !want;
    if (want) { up.innerHTML = '<img alt="" data-art="' + tags.id + '"><div><b>Complete the gift</b>Add ' + esc(tags.name) + ' for ' + money(tags.price) + '</div><button class="btn btn--ghost" type="button" data-upsell>Add<span class="sr"> ' + esc(tags.name) + '</span></button>'; bindArt($('img', up), tags, 1); }
    syncAdd();
  }
  /* the basket redraws on every change, so keyboard focus is put back by hand and the change is announced */
  var cartStatus = $('#cart-status');
  function say(msg) { cartStatus.textContent = ''; status(cartStatus, msg + ' Total ' + $('#cart-total').textContent + '.', 60); }
  $('#upsell').addEventListener('click', function (e) {
    if (!e.target.closest('[data-upsell]')) return;
    add('posy-gift-tags', 0, true);
    checkout.focus(); // the offer has gone, so carry on to the next control rather than dropping focus to the page
    say(GB.byId('posy-gift-tags').name + ' added.');
  });
  list.addEventListener('click', function (e) {
    var t = e.target.closest('button, a'); if (!t) return;
    if (t.hasAttribute('data-close')) return closeCart();
    if (!t.dataset.rm) return;
    var i = +t.dataset.rm, l = cart[i];
    cart.splice(i, 1); save();
    // next line's Remove button, else the one before, else the empty-basket link
    ($('[data-rm="' + Math.min(i, cart.length - 1) + '"]', list) || $('a[data-close]', list)).focus();
    say(GB.byId(l.id).name + ' removed.');
  });
  var cartFocus;
  function openCart() { hideToast(); clearTimeout(drawerT); cartFocus = document.activeElement; drawer.hidden = false; document.body.classList.add('locked'); setInert(true); requestAnimationFrame(function () { drawer.classList.add('on'); $('.drawer-close', drawer).focus(); }); }
  function closeCart() { drawer.classList.remove('on'); document.body.classList.remove('locked'); setInert(false); drawerT = setTimeout(function () { drawer.hidden = true; }, 300); if (cartFocus && cartFocus.focus) cartFocus.focus(); }
  /* keep Tab inside an open dialog */
  function trap(box, e) {
    var f = $$('a[href], button:not([disabled]), input, select, [tabindex]:not([tabindex="-1"])', box).filter(function (el) { return el.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  $$('[data-open-cart]').forEach(function (b) { b.addEventListener('click', openCart); });
  $('.drawer-close', drawer).addEventListener('click', closeCart);
  drawer.addEventListener('click', function (e) { if (e.target === drawer) closeCart(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { if (!modal.hidden) closeModal(); else if (!drawer.hidden) closeCart(); else if (nav.classList.contains('open')) closeNav(); }
    if (e.key === 'Tab') { if (!modal.hidden) trap(modal, e); else if (!drawer.hidden) trap(drawer, e); }
  });
  grid.addEventListener('click', function (e) {
    var b = e.target.closest('[data-add]'); if (!b) return;
    var p = GB.byId(b.dataset.add);
    if (inCart(p.id)) openCart(); else if (p.variants) openModal(p); else add(p.id, 0);
  });
  if (cfg.checkoutUrl) {
    // a real link: works in the artifact viewer and on a normal host (window.open is blocked in many viewers)
    var link = document.createElement('a');
    link.id = 'cart-checkout'; link.className = checkout.className; link.href = cfg.checkoutUrl;
    link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Continue to checkout';
    checkout.parentNode.replaceChild(link, checkout); checkout = link;
    checkout.addEventListener('click', function (e) { if (!cart.length) e.preventDefault(); });
  } else {
    checkout.addEventListener('click', function () { $('#checkout-msg').textContent = 'Checkout isn’t open yet. This shop is a preview, so no order has been placed and nothing has been charged.'; });
  }

  /* ---------- toast ---------- */
  var tt;
  function toast(msg) {
    var t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(tt); tt = setTimeout(hideToast, msg.length > 50 ? 4200 : 2400);
  }
  /* the basket shows the same news itself, so opening it clears the toast rather than covering the drawer footer */
  function hideToast() { clearTimeout(tt); $('#toast').classList.remove('on'); }

  /* ---------- newsletter ---------- */
  var newsMsg = $('#news-msg');
  $('#news').addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target, email = f.email.value.trim();
    if (!/^\S+@\S+\.\S+$/.test(email)) { newsMsg.textContent = 'Please enter a full email address, like name@example.com.'; f.email.focus(); return; }
    if (!cfg.newsletterAction) { newsMsg.textContent = 'Sign-ups open soon. Nothing has been sent and your email hasn’t been saved, so please check back.'; return; }
    newsMsg.textContent = 'Sending…';
    fetch(cfg.newsletterAction, { method: 'POST', headers: { 'Accept': 'application/json' }, body: new FormData(f) })
      .then(function (r) { newsMsg.textContent = r.ok ? 'You’re signed up. Thank you.' : 'That didn’t go through. Please try again later.'; if (r.ok) f.reset(); })
      .catch(function () { newsMsg.textContent = 'That didn’t go through. Please try again later.'; });
  });

  /* ---------- nav + reveal ---------- */
  var nav = $('.nav'), burger = $('#burger');
  function closeNav() { nav.classList.remove('open'); burger.setAttribute('aria-expanded', 'false'); }
  burger.addEventListener('click', function () { var o = nav.classList.toggle('open'); burger.setAttribute('aria-expanded', String(o)); });
  $$('.nav a').forEach(function (a) { a.addEventListener('click', closeNav); });
  var scrolled = function () { document.body.classList.toggle('scrolled', window.scrollY > 24); };
  window.addEventListener('scroll', scrolled, { passive: true }); scrolled();
  /* reading progress: decorative; scaled (not resized) once per frame, so scrolling never triggers layout */
  var prog = $('#progress'), progQ = false;
  function progress() { progQ = false; var m = document.documentElement.scrollHeight - innerHeight; prog.style.transform = 'scaleX(' + (m > 0 ? Math.min(1, Math.max(0, scrollY / m)) : 0).toFixed(4) + ')'; }
  function progressSoon() { if (!progQ) { progQ = true; requestAnimationFrame(progress); } }
  window.addEventListener('scroll', progressSoon, { passive: true });
  window.addEventListener('resize', progressSoon);
  progressSoon();

  /* the nav underlines the section you are in */
  if ('IntersectionObserver' in window) {
    var links = {}; $$('.nav a').forEach(function (l) { links[l.getAttribute('href')] = l; });
    var spy = new IntersectionObserver(function (en) {
      en.forEach(function (e) {
        var l = links['#' + e.target.id]; if (!l) return;
        if (e.isIntersecting) { $$('.nav a').forEach(function (x) { x.removeAttribute('aria-current'); }); l.setAttribute('aria-current', 'true'); } else l.removeAttribute('aria-current');
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    ['collections', 'shop', 'focus', 'story', 'faq'].forEach(function (id) { var el = document.getElementById(id); if (el) spy.observe(el); });
  }

  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (en) {
    en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }) : null;
  function observe() { $$('.reveal:not(.in)').forEach(function (el) { io ? io.observe(el) : el.classList.add('in'); }); }

  /* journal call-to-action filters the shop */
  $$('[data-filter-link]').forEach(function (a) { a.addEventListener('click', function () { setCat(a.dataset.filterLink, true); }); });

  /* story artwork (painted when it nears the screen) */
  var sc = $('#story-canvas');
  if (sc) later(sc, function () {
    queue.push(function (next) {
      var p = GB.byId('peony-birthday');
      sc.getContext('2d').drawImage(GB.art.make(p, 1), 0, 0, 640, 800);
      var cv = GB.art.release(p, 1); if (cv) cv.width = cv.height = 0;
      next();
    });
    pump();
  });

  $('#year').textContent = new Date().getFullYear();

  /* ---------- light / dark ---------- */
  var root = document.documentElement, themeBtn = $('#theme-btn');
  var darkMq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function isDark() { var t = root.getAttribute('data-theme'); return t ? t === 'dark' : !!(darkMq && darkMq.matches); }
  function syncTheme() {
    var d = isDark();
    themeBtn.setAttribute('aria-pressed', String(d));
    if (root.getAttribute('data-theme')) $$('meta[name="theme-color"]').forEach(function (m) { m.setAttribute('content', d ? '#1b1817' : '#efedeb'); });
    document.dispatchEvent(new CustomEvent('gb-themechange'));
  }
  themeBtn.addEventListener('click', function () {
    var next = isDark() ? 'light' : 'dark';
    root.setAttribute('data-theme', next); try { localStorage.setItem('gb-theme', next); } catch (e) {} syncTheme();
  });
  if (darkMq && darkMq.addEventListener) darkMq.addEventListener('change', syncTheme);
  syncTheme();

  /* ---------- pause motion (hero scene, marquee, scroll cue) ---------- */
  var motionBtn = $('#motion-btn');
  function syncMotion() { if (motionBtn) motionBtn.setAttribute('aria-pressed', String(root.classList.contains('still'))); }
  if (motionBtn) motionBtn.addEventListener('click', function () {
    var still = root.classList.toggle('still');
    try { if (still) localStorage.setItem('gb-motion', 'still'); else localStorage.removeItem('gb-motion'); } catch (e) {}
    syncMotion(); document.dispatchEvent(new CustomEvent('gb-motionchange'));
  });
  syncMotion();

  /* products, basket and reveals are ready straight away; only the pictures wait for the fonts */
  render(); paint(); observe();

  /* ---------- 3D hero: three.min.js (~600 KB) loads only after the page is usable and the hero is near view ---------- */
  function load3d() {
    var st = $('#hero-stage');
    if (!st) return;
    var keepStill = function () { st.classList.add('no-webgl'); };
    if (navigator.connection && navigator.connection.saveData) return keepStill(); // data saver: keep the painted card
    if (navigator.deviceMemory && navigator.deviceMemory <= 2) return keepStill(); // phones with 2 GB of memory or less (Chrome tells us): the scene would cost them most
    var add = function (src, then) { var s = document.createElement('script'); s.src = src; s.onload = then || null; s.onerror = keepStill; document.body.appendChild(s); };
    add('assets/vendor/three.min.js', function () { add('assets/js/hero3d.js'); });
  }
  function nearView(el, fn) {
    if (!el || !('IntersectionObserver' in window)) return fn();
    var o = new IntersectionObserver(function (en) { if (en.some(function (e) { return e.isIntersecting; })) { o.disconnect(); fn(); } }, { rootMargin: '300px 0px' });
    o.observe(el);
  }
  function afterLoad(fn) { if (document.readyState === 'complete') fn(); else window.addEventListener('load', fn); }

  // wait briefly for the display fonts so the painted artwork uses them
  var ready = (document.fonts && document.fonts.load) ? Promise.race([
    Promise.all([document.fonts.load('italic 500 40px "Cormorant Garamond"'), document.fonts.load('500 20px "Jost"')]),
    new Promise(function (r) { setTimeout(r, 1800); })
  ]) : Promise.resolve();
  ready.catch(function () {}).then(function () {
    fontsReady = true; pump();
    afterLoad(function () {
      bgOk = true; pump();
      idle(function () { nearView($('#hero-stage'), load3d); }, 1500);
    });
  });

  GB.live = true; // tells the page's load check that the shop is running
})();
