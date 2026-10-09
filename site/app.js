const S = window.SHOP, $ = id => document.getElementById(id);
const money = n => S.currency + n.toFixed(2);
// cart = [{id, qty}]. Each product has `stock` (default 1 = one-off piece, 0 = sold out).
let products = [], cart = [], cat = "All";
try { cart = JSON.parse(localStorage.getItem("cart3") || "[]"); } catch (e) {}
const save = () => { try { localStorage.setItem("cart3", JSON.stringify(cart)); } catch (e) {} };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const stockOf = p => p.stock === undefined ? 1 : p.stock;
const inCart = id => (cart.find(i => i.id === id) || { qty: 0 }).qty;

function renderFilters() {
  const cats = ["All", ...new Set(products.map(p => p.category))];
  $("filters").innerHTML = "";
  cats.forEach(c => {
    const b = document.createElement("button");
    b.textContent = c; b.className = c === cat ? "on" : "";
    b.onclick = () => { cat = c; renderFilters(); renderGrid(); };
    $("filters").appendChild(b);
  });
}
function renderGrid() {
  $("grid").innerHTML = "";
  products.filter(p => cat === "All" || p.category === cat)
    .sort((a, b) => (stockOf(a) === 0) - (stockOf(b) === 0))   // available pieces first
    .forEach(p => {
      const stock = stockOf(p), soldOut = stock === 0, maxed = inCart(p.id) >= stock;
      const el = document.createElement("article"); el.className = "card" + (soldOut ? " sold" : "");
      el.innerHTML = `<div class="img" style="background:${p.colour}">${esc(p.name)}${soldOut ? '<span class="tag">SOLD</span>' : ""}</div>
        <div class="body"><h3>${esc(p.name)}</h3>
        <p><b>${esc(p.era)}</b> · Size ${esc(p.size)}</p>
        <p>${esc(p.condition)}</p><p class="small">${esc(p.measurements)}</p>
        ${stock > 1 ? `<p class="small">${stock} available</p>` : ""}
        <div class="row"><strong>${money(p.price)}</strong>
        <button class="add" ${maxed ? "disabled" : ""}>${soldOut ? "Sold" : maxed ? "In basket" : "Add"}</button></div></div>`;
      el.querySelector(".add").onclick = () => {
        const hit = cart.find(i => i.id === p.id); hit ? hit.qty++ : cart.push({ id: p.id, qty: 1 });
        save(); renderCart(); renderGrid(); $("drawer").classList.add("open");
      };
      $("grid").appendChild(el);
    });
}
function renderCart() {
  // drop anything that sold out and cap quantities at current stock
  cart = cart.filter(i => { const p = products.find(x => x.id === i.id); if (!p || stockOf(p) === 0) return false; i.qty = Math.min(i.qty, stockOf(p)); return true; });
  let sub = 0, n = 0; $("items").innerHTML = "";
  cart.forEach(i => {
    const p = products.find(x => x.id === i.id); sub += p.price * i.qty; n += i.qty;
    const row = document.createElement("div"); row.className = "item";
    row.innerHTML = `<div>${esc(p.name)}<br><small>${esc(p.era)} · Size ${esc(p.size)}${i.qty > 1 ? " × " + i.qty : ""}</small></div><div>${money(p.price * i.qty)}<br><button>Remove</button></div>`;
    row.querySelector("button").onclick = () => { cart = cart.filter(x => x.id !== i.id); save(); renderCart(); renderGrid(); };
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
