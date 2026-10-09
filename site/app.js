const S = window.SHOP, $ = id => document.getElementById(id);
const money = n => S.currency + n.toFixed(2);
// product.stock = { size: unitsLeft }. Vintage one-offs are just { "L": 1 }.
// cart = [{id, size, qty}]
let products = [], cart = [], cat = "All", type = "All";
try { cart = JSON.parse(localStorage.getItem("cart4") || "[]"); } catch (e) {}
const save = () => { try { localStorage.setItem("cart4", JSON.stringify(cart)); } catch (e) {} };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const left = (p, size) => (p.stock[size] || 0) - ((cart.find(i => i.id === p.id && i.size === size) || { qty: 0 }).qty);
const totalLeft = p => Object.keys(p.stock).reduce((n, s) => n + p.stock[s], 0);

function chips(el, items, current, set) {
  el.innerHTML = "";
  items.forEach(c => { const b = document.createElement("button"); b.textContent = c; b.className = c === current ? "on" : ""; b.onclick = () => set(c); el.appendChild(b); });
}
function renderFilters() {
  chips($("types"), ["All", "New", "Vintage"], type === "All" ? "All" : type === "new" ? "New" : "Vintage", c => { type = c === "All" ? "All" : c.toLowerCase(); renderFilters(); renderGrid(); });
  chips($("filters"), ["All", ...new Set(products.map(p => p.category))], cat, c => { cat = c; renderFilters(); renderGrid(); });
}
function renderGrid() {
  $("grid").innerHTML = "";
  products.filter(p => (cat === "All" || p.category === cat) && (type === "All" || p.type === type))
    .sort((a, b) => (totalLeft(a) === 0) - (totalLeft(b) === 0))
    .forEach(p => {
      const sizes = Object.keys(p.stock), soldOut = totalLeft(p) === 0;
      let sel = sizes.length === 1 && left(p, sizes[0]) > 0 ? sizes[0] : null;
      const el = document.createElement("article"); el.className = "card" + (soldOut ? " sold" : "");
      el.innerHTML = `<div class="img" style="background:${p.colour}">${esc(p.name)}<span class="tag">${soldOut ? "SOLD OUT" : p.type === "vintage" ? "VINTAGE" : "NEW"}</span></div>
        <div class="body"><h3>${esc(p.name)}</h3>
        ${p.type === "vintage" ? `<p><b>${esc(p.era)}</b> · ${esc(p.condition)}</p><p class="small">${esc(p.measurements)}</p>` : `<p>${esc(p.desc)}</p>`}
        <div class="sizes"></div><p class="small stockmsg">&nbsp;</p>
        <div class="row"><strong>${money(p.price)}</strong><button class="add"></button></div></div>`;
      const sz = el.querySelector(".sizes"), msg = el.querySelector(".stockmsg"), add = el.querySelector(".add");
      const refresh = () => {
        sz.innerHTML = "";
        sizes.forEach(s => {
          const b = document.createElement("button"), n = left(p, s);
          b.textContent = s; b.className = "size" + (s === sel ? " on" : "") + (n <= 0 ? " out" : ""); b.disabled = n <= 0;
          b.onclick = () => { sel = s; refresh(); }; sz.appendChild(b);
        });
        const n = sel ? left(p, sel) : null;
        msg.textContent = soldOut ? "" : sel === null ? "Select a size" : n <= 3 ? `Only ${n} left` : "In stock";
        msg.className = "small stockmsg" + (n !== null && n <= 3 ? " low" : "");
        add.disabled = soldOut || sel === null || n <= 0;
        add.textContent = soldOut ? "Sold out" : sel === null ? "Select size" : n <= 0 ? "In basket" : "Add";
      };
      add.onclick = () => {
        const hit = cart.find(i => i.id === p.id && i.size === sel); hit ? hit.qty++ : cart.push({ id: p.id, size: sel, qty: 1 });
        save(); renderCart(); refresh(); $("drawer").classList.add("open");
      };
      refresh(); $("grid").appendChild(el);
    });
}
function renderCart() {
  cart = cart.filter(i => { const p = products.find(x => x.id === i.id); if (!p || !(p.stock[i.size] > 0)) return false; i.qty = Math.min(i.qty, p.stock[i.size]); return true; });
  let sub = 0, n = 0; $("items").innerHTML = "";
  cart.forEach(i => {
    const p = products.find(x => x.id === i.id); sub += p.price * i.qty; n += i.qty;
    const row = document.createElement("div"); row.className = "item";
    row.innerHTML = `<div>${esc(p.name)}<br><small>Size ${esc(i.size)}${i.qty > 1 ? " × " + i.qty : ""}</small></div><div>${money(p.price * i.qty)}<br><button>Remove</button></div>`;
    row.querySelector("button").onclick = () => { cart = cart.filter(x => x !== i); save(); renderCart(); renderGrid(); };
    $("items").appendChild(row);
  });
  const ship = sub === 0 || sub >= S.freeShippingOver ? 0 : S.shipping;
  $("count").textContent = n; $("sub").textContent = money(sub);
  $("ship").textContent = sub === 0 ? "Your basket is empty." : ship === 0 ? "Free UK delivery." : `UK delivery ${money(ship)} (free over ${money(S.freeShippingOver)}). Total ${money(sub + ship)}.`;
  $("checkout").disabled = sub === 0;
  $("mode").textContent = S.checkoutUrl ? "" : "Demo mode: no payment taken. Add a payment link in config.js to go live.";
}
$("checkout").onclick = () => {
  if (S.checkoutUrl) location.href = S.checkoutUrl;
  else alert("Demo mode: this is where the customer would pay.\nSet checkoutUrl in config.js to take real payments.");
};
$("open").onclick = () => $("drawer").classList.add("open");
$("close").onclick = () => $("drawer").classList.remove("open");
$("shopname").textContent = S.name; $("tagline").textContent = S.tagline;
fetch("products.json").then(r => r.json()).then(d => { products = d; renderFilters(); renderGrid(); renderCart(); });
