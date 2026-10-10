const S = window.SHOP || {}, $ = id => document.getElementById(id);
const CUR = S.currency || "£";
const money = n => CUR + n.toFixed(2);
// Whole amounts without ".00" for running text: "free over £100", "UK delivery £3.95".
const pounds = n => Math.round(n * 100) % 100 === 0 ? CUR + Math.round(n) : money(n);
// product.stock = { size: unitsLeft }. Vintage one-offs are just { "L": 1 }.
// cart = [{id, size, qty}]
let products = [], cart = [], cat = "All", type = "All";
const chosen = {}; // product id -> selected size, kept across re-renders
// Whatever is in storage gets checked: one bad entry mustn't break the basket or the shop.
const validLine = i => i && typeof i === "object" && typeof i.id === "string" && typeof i.size === "string";
try { cart = JSON.parse(localStorage.getItem("cart4") || "[]"); if (!Array.isArray(cart)) cart = []; } catch (e) { cart = []; }
cart = cart.filter(validLine);
const save = () => { try { localStorage.setItem("cart4", JSON.stringify(cart)); } catch (e) {} };
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Escape, then flag any [placeholder] so it stands out until it's filled in.
const flag = s => esc(s).replace(/\[[^\]]*\]/g, m => `<span class="ph">${m}</span>`);
const inCart = (p, size) => (cart.find(i => i.id === p.id && i.size === size) || { qty: 0 }).qty;
const left = (p, size) => (p.stock[size] || 0) - inCart(p, size);
const totalLeft = p => Object.keys(p.stock).reduce((n, s) => n + p.stock[s], 0);
const reduceMotion = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Colours and silhouettes for the placeholder product art */
const SHAPES = { Tops: "tee", Knitwear: "long", Outerwear: "long", Bottoms: "legs", Accessories: "hat" };
const shapeOf = p => ["tee", "long", "legs", "hat"].includes(p.shape) ? p.shape : SHAPES[p.category] || "tee";
const colourOf = p => /^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(p.colour || "") ? p.colour : "";
function isLight(hex) {
  if (!hex) return false;
  let h = hex.slice(1); if (h.length === 3) h = h.replace(/./g, c => c + c);
  const [r, g, b] = [0, 2, 4].map(i => { const v = parseInt(h.substr(i, 2), 16) / 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); });
  return .2126 * r + .7152 * g + .0722 * b > .3;
}
const swatch = p => colourOf(p) ? ` style="--swatch:${colourOf(p)}"` : "";
const tone = p => isLight(colourOf(p)) ? " is-light" : "";

/* Shop details from config.js */
const cfg = path => path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), S);
const isEmail = v => /^[^\s@\[\]]+@[^\s@\[\]]+\.[^\s@\[\]]+$/.test(v);
function fillConfig() {
  document.querySelectorAll("[data-row]").forEach(el => { el.hidden = !cfg(el.dataset.row); });
  document.querySelectorAll("[data-cfg]").forEach(el => {
    const v = cfg(el.dataset.cfg);
    if (!v) { el.textContent = ""; return; }
    // The address stays visible as text: mail links don't open for every viewer.
    el.innerHTML = isEmail(v) ? `<a href="mailto:${esc(v)}">${esc(v)}</a>` : flag(v);
  });
}
function deliveryLine() {
  if (!(S.shipping > 0)) return "Free UK delivery on every order.";
  return S.freeShippingOver ? `UK delivery ${pounds(S.shipping)}, free over ${pounds(S.freeShippingOver)}.` : `UK delivery ${pounds(S.shipping)} per order.`;
}
function renderStatic() {
  $("shopname").textContent = S.name || "Second Rail";
  if (S.tagline) $("tagline").textContent = S.tagline;
  const facts = S.shipping > 0
    ? [[`UK delivery ${pounds(S.shipping)}`, "#delivery"], ...(S.freeShippingOver ? [[`Free over ${pounds(S.freeShippingOver)}`, "#delivery"]] : [])]
    : [["Free UK delivery", "#delivery"]];
  facts.push(["14 days to change your mind", "#returns"]);
  $("facts").innerHTML = facts.map(([t, h]) => `<li><a href="${h}">${esc(t)}</a></li>`).join("");
  $("foot-delivery").textContent = `${deliveryLine()} 14 days to change your mind.`;
  $("info-delivery").textContent = S.shipping > 0
    ? `UK delivery is ${pounds(S.shipping)} per order${S.freeShippingOver ? `, and free on orders over ${pounds(S.freeShippingOver)}` : ""}. The basket shows the delivery charge and the full total before you check out.`
    : "UK delivery is free on every order.";
  fillConfig();
}

/* The rail: what's hanging up right now, drawn from products.json */
function renderRail() {
  // In-stock pieces first, then an empty hanger for each sold-out one. A dozen is plenty for the hero.
  const order = [...products].sort((a, b) => (totalLeft(a) === 0) - (totalLeft(b) === 0)).slice(0, 12);
  $("rail").innerHTML = order.map((p, i) => {
    const hook = `<svg class="hook" viewBox="0 0 40 24" aria-hidden="true" focusable="false"><use href="#hanger"/></svg>`;
    if (totalLeft(p) === 0) return `<span class="hang empty" style="--i:${i}" aria-hidden="true">${hook}</span>`;
    return `<a class="hang" href="#p-${esc(p.id)}" data-id="${esc(p.id)}" style="--i:${i}${colourOf(p) ? ";--swatch:" + colourOf(p) : ""}">${hook}<span class="garment g-${shapeOf(p)}"></span><span class="sr">${esc(p.name)}, ${money(p.price)}</span></a>`;
  }).join("");
}
$("rail").addEventListener("click", e => {
  const a = e.target.closest("a.hang"); if (!a) return;
  e.preventDefault();
  let card = $("p-" + a.dataset.id);
  if (!card) { cat = "All"; type = "All"; renderFilters(); renderGrid(); card = $("p-" + a.dataset.id); }
  if (!card) return;
  card.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
  card.focus({ preventScroll: true });
  card.classList.add("flash"); setTimeout(() => card.classList.remove("flash"), 1400);
});

/* Filters */
function chips(el, items, current, set) {
  el.innerHTML = "";
  items.forEach(c => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = c; b.setAttribute("aria-pressed", String(c === current));
    b.onclick = () => set(c); el.appendChild(b);
  });
}
function renderFilters() {
  chips($("types"), ["All", "New", "Vintage"], type === "All" ? "All" : type === "new" ? "New" : "Vintage", c => { type = c === "All" ? "All" : c.toLowerCase(); renderFilters(); renderGrid(); });
  const cats = ["All categories", ...new Set(products.filter(p => type === "All" || p.type === type).map(p => p.category))];
  if (!cats.includes(cat)) cat = "All";
  chips($("filters"), cats, cat === "All" ? "All categories" : cat, c => { cat = c === "All categories" ? "All" : c; renderFilters(); renderGrid(); });
}

/* Product cards */
function stockMessage(p, sel, soldOut) {
  if (soldOut) return ["", false];
  if (sel === null) return ["Choose a size", false];
  const n = left(p, sel), had = p.stock[sel] || 0;
  if (n <= 0) return [had === 1 ? "The only one is in your basket" : "All we have in this size is in your basket", false];
  if (p.type === "vintage" && had === 1) return ["One-off piece", false];
  // Only shown when config.js says the products.json counts are real (DMCC Act 2024: no urgency that isn't true).
  if (n <= 3 && S.lowStockMessages !== false) return [`Only ${n} left in this size`, true];
  return ["In stock", false];
}
function cardHTML(p, soldOut) {
  const isVintage = p.type === "vintage";
  const tag = soldOut ? "Sold out" : isVintage ? "Vintage" : "New";
  const meta = isVintage ? `${esc(p.era)} · ${esc(p.category)}` : esc(p.category);
  const desc = isVintage ? `Condition: ${p.condition}` : p.desc;
  const spec = [];
  if (isVintage && p.measurements) spec.push(["Measured", p.measurements]);
  if (p.fabric) spec.push(["Fibre", String(p.fabric).replace(/^Fibre:\s*/i, "")]);
  const free = S.freeShippingOver && p.price >= S.freeShippingOver;
  const deliv = !(S.shipping > 0) || free ? "Free UK delivery" : `+ ${pounds(S.shipping)} UK delivery${S.freeShippingOver ? `, free over ${pounds(S.freeShippingOver)}` : ""}`;
  const art = p.image
    ? `<img src="${esc(p.image)}" alt="${esc(p.alt || p.name)}" loading="lazy">`
    : `<span class="fig" aria-hidden="true"><svg class="hook" viewBox="0 0 40 24" focusable="false"><use href="#hanger"/></svg><span class="garment g-${shapeOf(p)}"></span></span>`;
  return `<div class="pic${tone(p)}${p.image ? " has-img" : ""}"${swatch(p)}>${art}<span class="tag" aria-hidden="true">${tag}</span></div>
    <div class="body">
      <p class="meta">${meta}</p>
      <h3 id="t-${esc(p.id)}">${esc(p.name)}</h3>
      ${desc ? `<p class="desc">${flag(desc)}</p>` : ""}
      ${spec.length ? `<dl class="spec">${spec.map(([k, v]) => `<div><dt>${k}</dt><dd>${flag(v)}</dd></div>`).join("")}</dl>` : ""}
      <div class="buy">
        <div class="sizes" role="group" aria-label="Size"></div>
        <p class="stockmsg" aria-live="polite"></p>
        <div class="row"><strong class="price">${money(p.price)}</strong><button class="add" type="button" aria-describedby="t-${esc(p.id)}">Add to basket</button></div>
        <p class="deliv">${deliv}</p>
      </div>
    </div>`;
}
function renderGrid() {
  const grid = $("grid");
  const list = products.filter(p => (cat === "All" || p.category === cat) && (type === "All" || p.type === type))
    .sort((a, b) => (totalLeft(a) === 0) - (totalLeft(b) === 0));
  grid.innerHTML = "";
  $("resultcount").textContent = `${list.length} ${list.length === 1 ? "piece" : "pieces"}`;
  if (!list.length) {
    grid.innerHTML = `<div class="emptystate"><p>Nothing on the rail matches that right now.</p><button class="pill ghost" type="button" id="reset">Show everything</button></div>`;
    $("reset").onclick = () => { cat = "All"; type = "All"; renderFilters(); renderGrid(); };
    return;
  }
  list.forEach(p => {
    const sizes = Object.keys(p.stock), soldOut = totalLeft(p) === 0;
    let sel = chosen[p.id] !== undefined && left(p, chosen[p.id]) > 0 ? chosen[p.id]
      : sizes.length === 1 && left(p, sizes[0]) > 0 ? sizes[0] : null;
    const el = document.createElement("article");
    el.className = "card" + (soldOut ? " sold" : "");
    el.id = "p-" + p.id; el.tabIndex = -1; el.setAttribute("aria-labelledby", "t-" + p.id);
    el.innerHTML = cardHTML(p, soldOut);
    const sz = el.querySelector(".sizes"), msg = el.querySelector(".stockmsg"), add = el.querySelector(".add");
    const refresh = () => {
      sz.innerHTML = "";
      sizes.forEach(s => {
        const b = document.createElement("button"), n = left(p, s), out = n <= 0;
        b.type = "button"; b.className = "size"; b.textContent = s; b.disabled = out;
        b.setAttribute("aria-pressed", String(s === sel));
        if (out) b.setAttribute("aria-label", `${s}, ${(p.stock[s] || 0) > 0 ? "in your basket" : "sold out"}`);
        b.onclick = () => { sel = s; chosen[p.id] = s; refresh(); sz.querySelector(`[aria-pressed="true"]`)?.focus(); };
        sz.appendChild(b);
      });
      const [text, low] = stockMessage(p, sel, soldOut);
      msg.textContent = text; msg.className = "stockmsg" + (low ? " low" : "");
      const n = sel === null ? 0 : left(p, sel);
      add.disabled = soldOut || sel === null || n <= 0;
      add.textContent = soldOut ? "Sold out" : sel !== null && n <= 0 ? "In basket" : "Add to basket";
    };
    add.onclick = () => {
      if (sel === null || left(p, sel) <= 0) return;
      const hit = cart.find(i => i.id === p.id && i.size === sel); hit ? hit.qty++ : cart.push({ id: p.id, size: sel, qty: 1 });
      save(); renderCart(); refresh(); bump(); openDrawer();
    };
    refresh(); grid.appendChild(el);
  });
}

/* Basket */
function renderCart(focusKey) {
  cart = cart.filter(i => { if (!validLine(i)) return false; const p = products.find(x => x.id === i.id); if (!p || !(p.stock[i.size] > 0)) return false; i.qty = Math.max(1, Math.min(i.qty | 0, p.stock[i.size])); return true; });
  let sub = 0, n = 0;
  const box = $("items"); box.innerHTML = "";
  if (!cart.length) {
    box.innerHTML = `<div class="basket-empty"><svg viewBox="0 0 40 24" aria-hidden="true" focusable="false"><use href="#hanger"/></svg><p><strong>Your basket is empty.</strong></p><p>Pick a size on anything on the rail and it lands here.</p></div>`;
  }
  cart.forEach(i => {
    const p = products.find(x => x.id === i.id), line = p.price * i.qty, max = p.stock[i.size], key = `${p.id}|${i.size}`;
    sub += line; n += i.qty;
    const row = document.createElement("div"); row.className = "item";
    row.innerHTML = `<span class="thumb${tone(p)}"${swatch(p)} aria-hidden="true"><span class="garment g-${shapeOf(p)}"></span></span>
      <div class="item-main">
        <p class="item-name">${esc(p.name)}</p>
        <p class="item-meta">Size ${esc(i.size)} · ${p.type === "vintage" ? "Vintage" : "New"} · ${money(p.price)} each</p>
        ${max > 1 ? `<div class="qty" role="group" aria-label="Quantity of ${esc(p.name)}, size ${esc(i.size)}">
          <button type="button" data-k="${esc(key)}|dec" aria-label="One fewer"${i.qty <= 1 ? " disabled" : ""}>−</button>
          <output aria-live="polite">${i.qty}</output>
          <button type="button" data-k="${esc(key)}|inc" aria-label="One more"${i.qty >= max ? " disabled" : ""}>+</button></div>` : ""}
      </div>
      <div class="item-side"><span class="item-price">${money(line)}</span><button class="linkbtn" type="button" data-k="${esc(key)}|rm" aria-label="Remove ${esc(p.name)}, size ${esc(i.size)}">Remove</button></div>`;
    row.querySelectorAll("button").forEach(b => b.onclick = () => {
      const act = b.dataset.k.split("|").pop();
      if (act === "rm") { const idx = cart.indexOf(i); cart = cart.filter(x => x !== i); save(); renderCart(cart[idx] ? `${cart[idx].id}|${cart[idx].size}|rm` : "close"); renderGrid(); return; }
      i.qty += act === "inc" ? 1 : -1; save(); renderCart(b.dataset.k); renderGrid();
    });
    box.appendChild(row);
  });
  const free = S.freeShippingOver && sub >= S.freeShippingOver;
  const ship = sub === 0 || free || !(S.shipping > 0) ? 0 : S.shipping;
  $("count").textContent = n;
  $("sub").textContent = money(sub);
  $("shipcost").textContent = sub === 0 ? "–" : ship === 0 ? "Free" : money(ship);
  $("total").textContent = money(sub + ship);
  $("ship").textContent = sub === 0 ? deliveryLine() : ship === 0 ? "Your order gets free UK delivery." : S.freeShippingOver ? `Free UK delivery on orders over ${pounds(S.freeShippingOver)}.` : "";
  $("checkout").disabled = sub === 0;
  const mode = $("mode");
  mode.className = "note"; mode.textContent = S.checkoutUrl ? "" : "Preview: checkout isn’t connected yet.";
  if (focusKey) {
    const target = focusKey === "close" ? $("close") : box.querySelector(`[data-k="${CSS.escape(focusKey)}"]`);
    (target && !target.disabled ? target : $("close")).focus();
  }
}
$("checkout").onclick = () => {
  if (S.checkoutUrl) { location.href = S.checkoutUrl; return; }
  const m = $("mode");
  m.textContent = "Checkout isn’t connected yet, so nothing has been ordered and no payment was taken. When the shop opens, this button will take you to a secure payment page.";
  m.className = "note demo";
};
function bump() {
  const b = $("open"); b.classList.remove("bump"); void b.offsetWidth; b.classList.add("bump");
}

/* Drawer open/close, with focus kept inside while it's open */
const drawer = $("drawer"), scrim = $("scrim");
let returnFocus = null;
function openDrawer() {
  if (drawer.classList.contains("open")) return;
  returnFocus = document.activeElement;
  drawer.inert = false; drawer.removeAttribute("inert"); drawer.setAttribute("aria-hidden", "false");
  drawer.classList.add("open"); scrim.classList.add("on");
  document.documentElement.classList.add("locked");
  $("close").focus({ preventScroll: true });
}
function closeDrawer() {
  if (!drawer.classList.contains("open")) return;
  drawer.classList.remove("open"); scrim.classList.remove("on");
  drawer.setAttribute("aria-hidden", "true"); drawer.inert = true; drawer.setAttribute("inert", "");
  document.documentElement.classList.remove("locked");
  (returnFocus && document.contains(returnFocus) ? returnFocus : $("open")).focus({ preventScroll: true });
}
$("open").onclick = openDrawer;
$("close").onclick = closeDrawer;
scrim.onclick = closeDrawer;
drawer.addEventListener("keydown", e => {
  if (e.key === "Escape") { e.preventDefault(); closeDrawer(); return; }
  if (e.key !== "Tab") return;
  const f = [...drawer.querySelectorAll("button:not([disabled]), a[href]")].filter(el => el.offsetParent !== null);
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

/* The rail scrolls sideways when there are more pieces than fit: fade the edge that has more */
function railEdges() {
  const r = $("rail"), more = r.scrollWidth - r.clientWidth > 1;
  r.classList.toggle("more-end", more && r.scrollLeft < r.scrollWidth - r.clientWidth - 2);
  r.classList.toggle("more-start", more && r.scrollLeft > 2);
}
$("rail").addEventListener("scroll", railEdges, { passive: true });
window.addEventListener("resize", railEdges);

/* The footer only says every product lists its fibre once none is still a [placeholder] */
function fibreLine() {
  const done = products.length && products.every(p => p.fabric && !/\[[^\]]*\]/.test(p.fabric));
  $("foot-fibre").textContent = done ? "Every product lists its fibre composition." : "Every product will list its fibre composition before it goes on sale.";
}

/* A basket fault is kept apart from the product list: if it can't be drawn, it's emptied, not the shop */
function safeRenderCart() {
  try { renderCart(); } catch (e) { cart = []; save(); try { renderCart(); } catch (e2) {} }
}

/* Start */
renderStatic();
fetch("products.json")
  .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
  .then(d => {
    products = Array.isArray(d) ? d.filter(p => p && typeof p === "object" && typeof p.id === "string" && p.stock && typeof p.stock === "object") : [];
    renderFilters(); renderGrid(); renderRail(); railEdges(); fibreLine();
  }, () => {
    $("grid").innerHTML = `<p class="loading">The product list didn’t load. Refresh the page to try again.</p>`;
  })
  .finally(safeRenderCart);
