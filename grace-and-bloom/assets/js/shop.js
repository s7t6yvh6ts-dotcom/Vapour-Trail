/* Grace & Bloom — storefront: product grid, quick view, basket, small interactions. */
(function () {
  var GB = window.GB, cfg = GB.config;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var money = function (n) { return cfg.currency + n.toFixed(2); };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  var esc = function (s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };

  /* ---------- 3D-ish product mockups (pure CSS transforms) ---------- */
  var artUrl = {};
  function url(p, scale) {
    var k = p.id + scale;
    return artUrl[k] || (artUrl[k] = GB.art.make(p, scale).toDataURL('image/jpeg', 0.9));
  }
  function mock(p, scale) {
    var el = document.createElement('div');
    el.className = 'mock mock--' + p.kind;
    var inner = '<div class="obj">';
    if (p.kind === 'card') inner += '<i class="env"></i>';
    if (p.kind === 'calendar') inner += '<i class="rings"></i><i class="hook"></i>';
    if (p.kind === 'bookmark') inner += '<i class="tassel"></i>';
    inner += '<img alt="' + esc(p.name) + '" src="' + url(p, scale || 1) + '" draggable="false">';
    inner += '<i class="gloss"></i></div><i class="drop"></i>';
    el.innerHTML = inner;
    return el;
  }
  function tilt(host, target) {
    if (reduce) return;
    target = target || host;
    host.addEventListener('pointermove', function (e) {
      var r = host.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      target.style.setProperty('--ry', (x * 22).toFixed(1) + 'deg');
      target.style.setProperty('--rx', (-y * 16).toFixed(1) + 'deg');
      target.style.setProperty('--gx', ((x + 0.5) * 100).toFixed(0) + '%');
      target.style.setProperty('--gy', ((y + 0.5) * 100).toFixed(0) + '%');
    });
    host.addEventListener('pointerleave', function () {
      target.style.setProperty('--ry', '0deg'); target.style.setProperty('--rx', '0deg');
    });
  }
  /* ---------- grid ---------- */
  var grid = $('#grid'), current = 'all';
  function card(p, i) {
    var a = document.createElement('article');
    a.className = 'product reveal'; a.style.setProperty('--d', (i % 4) * 70 + 'ms'); a.dataset.id = p.id;
    a.innerHTML =
      '<button class="stage" aria-label="Quick view: ' + esc(p.name) + '"></button>' +
      (p.badge ? '<span class="badge">' + esc(p.badge) + '</span>' : '') +
      '<button class="fav" aria-label="Save ' + esc(p.name) + '" aria-pressed="false"><svg viewBox="0 0 24 24" width="18" height="18"><path d="M12 20.5s-7.5-4.6-7.5-10A4.2 4.2 0 0 1 12 8a4.2 4.2 0 0 1 7.5 2.5c0 5.4-7.5 10-7.5 10z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></button>' +
      '<div class="meta"><div><h3>' + esc(p.name) + '</h3><p class="cat">' + esc(catLabel(p.cat)) + '</p></div>' +
      '<div class="row"><span class="price">' + (fromPrice(p) ? 'From ' : '') + money(p.price) + '</span></div></div>' +
      '<button class="btn btn--ghost add" data-add="' + p.id + '">Add to basket</button>';
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
  /* a product whose options cost more is priced "From" its lowest price */
  function fromPrice(p) { return !!(p.variants && p.variants.options.some(function (o) { return o[1] > 0; })); }
  function catLabel(id) { var c = GB.categories.filter(function (c) { return c.id === id; })[0]; return c ? c.label : id; }
  var query = '', sortBy = 'featured';
  function haystack(p) { return (p.name + ' ' + p.blurb + ' ' + catLabel(p.cat) + ' ' + (GB.tags[p.id] || []).join(' ')).toLowerCase(); }
  function sorted(a) {
    var b = a.slice();
    if (sortBy === 'low') b.sort(function (x, y) { return x.price - y.price; });
    else if (sortBy === 'high') b.sort(function (x, y) { return y.price - x.price; });
    return b;
  }
  function render(filter) {
    current = filter; grid.innerHTML = '';
    var q = query.trim().toLowerCase();
    var items = sorted(GB.products.filter(function (p) { return (filter === 'all' || p.cat === filter) && (!q || haystack(p).indexOf(q) > -1); }));
    if (!items.length) grid.innerHTML = '<p class="none">Nothing ' + (filter === 'all' ? '' : 'in ' + esc(catLabel(filter)) + ' ') + 'matches “' + esc(query) + '”. ' + (filter === 'all' ? 'Try “birthday”, “planner” or “print”.' : 'Try the All filter, or “birthday”, “planner” or “print”.') + '</p>';
    items.forEach(function (p, i) { grid.appendChild(card(p, i)); });
    $$('.chip[data-filter]').forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.filter === filter)); });
    observe();
  }
  var chips = $('#chips');
  [{ id: 'all', label: 'All' }].concat(GB.categories).forEach(function (c) {
    var b = document.createElement('button'); b.className = 'chip'; b.dataset.filter = c.id; b.textContent = c.label;
    b.addEventListener('click', function () { render(c.id); }); chips.appendChild(b);
  });

  $('#q').addEventListener('input', function (e) { query = e.target.value; render(current); });
  $('#sort').addEventListener('change', function (e) { sortBy = e.target.value; render(current); });

  /* ---------- gift finder ---------- */
  var FINDER = [
    ['A birthday card', function (p) { return has(p, 'birthday') && p.cat === 'cards'; }],
    ['A Christmas card', function (p) { return has(p, 'christmas'); }],
    ['A thank you', function (p) { return has(p, 'thank you') || has(p, 'thinking of you'); }],
    ['Under £15', function (p) { return p.price <= 15; }],
    ['A gift for her', function (p) { return has(p, 'gift') || has(p, 'personalised'); }],
    ['Get organised', function (p) { return has(p, 'organise'); }],
    ['Money & goals', function (p) { return has(p, 'money') || has(p, 'goals'); }],
    ['Something for the wall', function (p) { return has(p, 'wall art') || has(p, 'calendar'); }]
  ];
  function has(p, t) { return (GB.tags[p.id] || []).indexOf(t) > -1; }
  var fchips = $('#finder-chips'), fres = $('#finder-results');
  function pick(i) {
    $$('.chip', fchips).forEach(function (c, j) { c.setAttribute('aria-pressed', String(i === j)); });
    fres.innerHTML = '';
    GB.products.filter(FINDER[i][1]).slice(0, 4).forEach(function (p, k) { var c = card(p, k); c.classList.add('in'); fres.appendChild(c); });
  }
  FINDER.forEach(function (f, i) {
    var b = document.createElement('button'); b.className = 'chip'; b.textContent = f[0]; b.addEventListener('click', function () { pick(i); }); fchips.appendChild(b);
  });
  pick(0);

  /* ---------- collections ---------- */
  var cols = $('#collections-grid');
  GB.categories.forEach(function (c, i) {
    var p = GB.byId(c.rep), a = document.createElement('a');
    a.href = '#shop'; a.className = 'collection reveal'; a.style.setProperty('--d', i * 80 + 'ms');
    a.innerHTML = '<div class="cstage"></div><h3>' + esc(c.label) + '</h3><p>' + esc(c.blurb) + '</p><span class="more">Shop ' + esc(c.label.toLowerCase()) + '&nbsp;→</span>';
    $('.cstage', a).appendChild(mock(p, 1)); tilt(a, $('.mock', a));
    a.addEventListener('click', function () { render(c.id); });
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
  var modal = $('#modal'), mbody = $('#modal-body'), lastFocus, qv;
  function openModal(p) {
    lastFocus = document.activeElement; qv = { p: p, v: 0, q: 1 };
    var vr = p.variants;
    mbody.innerHTML =
      '<div class="qv-stage"></div><div class="qv-info">' +
      '<p class="cat">' + esc(catLabel(p.cat)) + '</p><h2 id="modal-title">' + esc(p.name) + '</h2>' +
      '<p class="qv-price" id="qv-price"></p><p class="blurb">' + esc(p.blurb) + '</p>' +
      (vr ? '<fieldset class="opts"><legend>' + esc(vr.label) + '</legend>' + vr.options.map(function (o, i) { return '<label><input type="radio" name="v" value="' + i + '"' + (i === 0 ? ' checked' : '') + '><span>' + esc(o[0]) + '</span></label>'; }).join('') + '</fieldset>' : '') +
      '<div class="qty-row"><div class="qty" role="group" aria-label="Quantity"><button data-q="-1" aria-label="One fewer">−</button><output id="qv-q" aria-live="polite">1</output><button data-q="1" aria-label="One more">+</button></div>' +
      '<button class="btn btn--primary" id="qv-add">Add to basket</button></div>' +
      (p.etsyUrl ? '<a class="etsy" href="' + esc(p.etsyUrl) + '" target="_blank" rel="noopener">Also available on Etsy →</a>' : '') + '<ul class="details">' + p.details.map(function (d) { return '<li>' + esc(d) + '</li>'; }).join('') + '</ul></div>';
    var st = $('.qv-stage', mbody); st.appendChild(mock(p, 1.3)); tilt(st, $('.mock', st));
    function price() { return p.price + (vr ? vr.options[qv.v][1] : 0); }
    function upd() { $('#qv-price').textContent = money(price()); $('#qv-q').textContent = qv.q; }
    upd();
    $$('input[name=v]', mbody).forEach(function (r) { r.addEventListener('change', function () { qv.v = +r.value; upd(); }); });
    $$('[data-q]', mbody).forEach(function (b) { b.addEventListener('click', function () { qv.q = Math.max(1, Math.min(20, qv.q + +b.dataset.q)); upd(); }); });
    $('#qv-add').addEventListener('click', function () { add(p.id, qv.v, qv.q, true); closeModal(); openCart(); });
    modal.hidden = false; document.body.classList.add('locked');
    requestAnimationFrame(function () { modal.classList.add('on'); $('.modal-close', modal).focus(); });
  }
  function closeModal() {
    modal.classList.remove('on'); document.body.classList.remove('locked');
    setTimeout(function () { modal.hidden = true; }, 250); if (lastFocus) lastFocus.focus();
  }
  $('.modal-close', modal).addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });

  /* ---------- basket ---------- */
  var cart = store.get('gb-cart', []).filter(function (l) {
    var p = l && GB.byId(l.id);
    return p && l.q > 0 && (!p.variants || p.variants.options[l.v]);
  }), drawer = $('#cart'), list = $('#cart-list'), checkout = $('#cart-checkout');
  function add(id, v, q, quiet) {
    var ex = cart.filter(function (l) { return l.id === id && l.v === v; })[0];
    if (ex) ex.q += q; else cart.push({ id: id, v: v, q: q });
    save(); if (!quiet) toast('Added to your basket');
  }
  function unit(l) { var p = GB.byId(l.id); return p.price + (p.variants ? p.variants.options[l.v][1] : 0); }
  function save() { store.set('gb-cart', cart); var m = $('#checkout-msg'); if (m) m.textContent = ''; paint(); }
  function paint() {
    var n = cart.reduce(function (s, l) { return s + l.q; }, 0), sub = cart.reduce(function (s, l) { return s + unit(l) * l.q; }, 0);
    $$('.cart-count').forEach(function (c) { c.textContent = n; c.hidden = !n; });
    if (!cart.length) list.innerHTML = '<div class="empty"><p>Your basket is empty.</p><a class="btn btn--ghost" href="#shop" data-close>Find something lovely</a></div>';
    else list.innerHTML = cart.map(function (l, i) {
      var p = GB.byId(l.id);
      return '<li><img src="' + url(p, 1) + '" alt=""><div><h4>' + esc(p.name) + '</h4>' + (p.variants ? '<small>' + esc(p.variants.options[l.v][0]) + '</small>' : '') +
        '<div class="qty qty--sm" role="group" aria-label="Quantity of ' + esc(p.name) + '"><button data-ci="' + i + '" data-d="-1" aria-label="One fewer">−</button><output>' + l.q + '</output><button data-ci="' + i + '" data-d="1" aria-label="One more">+</button></div></div>' +
        '<div class="end"><strong>' + money(unit(l) * l.q) + '</strong><button class="rm" data-rm="' + i + '" aria-label="Remove ' + esc(p.name) + '">Remove</button></div></li>';
    }).join('');
    var left = Math.max(0, cfg.freeShippingOver - sub), pct = Math.min(100, (sub / cfg.freeShippingOver) * 100);
    var ship = !cart.length ? 0 : left > 0 ? cfg.shippingFlat : 0;
    $('#ship-msg').innerHTML = !cart.length ? 'Free UK delivery on orders of ' + money(cfg.freeShippingOver) + ' or more' : left > 0 ? 'Add <strong>' + money(left) + '</strong> more for free UK delivery' : 'Your order qualifies for <strong>free UK delivery</strong>';
    $('#ship-bar').style.width = (cart.length ? pct : 0) + '%';
    $('#cart-sub').textContent = money(sub);
    $('#cart-ship').textContent = !cart.length ? money(0) : ship ? money(ship) : 'Free';
    $('#cart-total').textContent = money(sub + ship);
    if (checkout.tagName === 'A') { if (cart.length) checkout.removeAttribute('aria-disabled'); else checkout.setAttribute('aria-disabled', 'true'); }
    else checkout.disabled = !cart.length;
  }
  list.addEventListener('click', function (e) {
    var t = e.target;
    if (t.dataset.d) { var l = cart[+t.dataset.ci]; l.q += +t.dataset.d; if (l.q < 1) cart.splice(+t.dataset.ci, 1); save(); }
    if (t.dataset.rm) { cart.splice(+t.dataset.rm, 1); save(); }
    if (t.hasAttribute('data-close')) closeCart();
  });
  var cartFocus;
  function openCart() { hideToast(); cartFocus = document.activeElement; drawer.hidden = false; document.body.classList.add('locked'); requestAnimationFrame(function () { drawer.classList.add('on'); $('.drawer-close', drawer).focus(); }); }
  function closeCart() { drawer.classList.remove('on'); document.body.classList.remove('locked'); setTimeout(function () { drawer.hidden = true; }, 300); if (cartFocus && cartFocus.focus) cartFocus.focus(); }
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
  [grid, fres].forEach(function (g) { g.addEventListener('click', function (e) {
    var b = e.target.closest('[data-add]'); if (!b) return;
    var p = GB.byId(b.dataset.add);
    if (p.variants) openModal(p); else add(p.id, 0, 1);
  }); });
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

  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (en) {
    en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }) : null;
  function observe() { $$('.reveal:not(.in)').forEach(function (el) { io ? io.observe(el) : el.classList.add('in'); }); }

  /* journal call-to-action filters the shop */
  $$('[data-filter-link]').forEach(function (a) { a.addEventListener('click', function () { render(a.dataset.filterLink); }); });

  /* story artwork + hero fallback */
  var sc = $('#story-canvas');
  if (sc) { sc.getContext('2d').drawImage(GB.art.make(GB.byId('peony-birthday'), 1), 0, 0, 640, 800); }
  var fb = $('.hero-stage .fallback');
  if (fb) { fb.appendChild(mock(GB.byId('peony-birthday'), 1)); }

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

  var go = function () { render('all'); paint(); observe(); };
  // wait briefly for the display fonts so the painted artwork uses them
  var ready = (document.fonts && document.fonts.load) ? Promise.race([
    Promise.all([document.fonts.load('italic 500 40px "Cormorant Garamond"'), document.fonts.load('500 20px "Jost"')]),
    new Promise(function (r) { setTimeout(r, 1800); })
  ]) : Promise.resolve();
  ready.catch(function () {}).then(function () {
    var s = document.createElement('script'); s.src = 'assets/js/hero3d.js';
    s.onerror = function () { var st = $('#hero-stage'); if (st) st.classList.add('no-webgl'); };
    document.body.appendChild(s);
    go();
  });
})();
