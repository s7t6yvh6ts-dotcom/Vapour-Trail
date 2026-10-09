const S = window.SHOP, $ = id => document.getElementById(id);
const money = n => S.currency + n.toFixed(2);
let products = [], cart = [], cat = "All";
try { cart = JSON.parse(localStorage.getItem("cart") || "[]"); } catch (e) {}
const save = () => { try { localStorage.setItem("cart", JSON.stringify(cart)); } catch (e) {} };

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
  products.filter(p => cat === "All" || p.category === cat).forEach(p => {
    const el = document.createElement("article"); el.className = "card";
    el.innerHTML = `<div class="img" style="background:${p.colour}">${p.name}</div>
      <div class="body"><h3>${p.name} — ${money(p.price)}</h3><p>${p.desc}</p>
      <div class="row"><select aria-label="Size">${p.sizes.map(s => `<option>${s}</option>`).join("")}</select>
      <button class="add">Add</button></div></div>`;
    el.querySelector(".add").onclick = () => {
      const size = el.querySelector("select").value;
      const hit = cart.find(i => i.id === p.id && i.size === size);
      hit ? hit.qty++ : cart.push({ id: p.id, size, qty: 1 });
      save(); renderCart(); $("drawer").classList.add("open");
    };
    $("grid").appendChild(el);
  });
}
function renderCart() {
  let sub = 0, n = 0; $("items").innerHTML = "";
  cart.forEach((i, idx) => {
    const p = products.find(x => x.id === i.id); if (!p) return;
    sub += p.price * i.qty; n += i.qty;
    const row = document.createElement("div"); row.className = "item";
    row.innerHTML = `<div>${p.name}<br><small>Size ${i.size} × ${i.qty}</small></div><div>${money(p.price * i.qty)}<br><button>Remove</button></div>`;
    row.querySelector("button").onclick = () => { cart.splice(idx, 1); save(); renderCart(); };
    $("items").appendChild(row);
  });
  const ship = sub === 0 ? 0 : sub >= S.freeShippingOver ? 0 : S.shipping;
  $("count").textContent = n; $("sub").textContent = money(sub);
  $("ship").textContent = sub === 0 ? "Your basket is empty." : ship === 0 ? "Free UK delivery." : `UK delivery ${money(ship)} (free over ${money(S.freeShippingOver)}).`;
  $("checkout").disabled = sub === 0;
  $("mode").textContent = S.checkoutUrl ? "" : "Demo mode: no payment taken. Add a payment link in config.js to go live.";
}
$("checkout").onclick = () => {
  if (S.checkoutUrl) location.href = S.checkoutUrl;
  else alert("Demo mode: this is where the customer would pay.\nSet checkoutUrl in config.js to take real payments.");
};
$("open").onclick = () => $("drawer").classList.add("open");
$("close").onclick = () => $("drawer").classList.remove("open");
$("shopname").textContent = S.name;
fetch("products.json").then(r => r.json()).then(d => { products = d; renderFilters(); renderGrid(); renderCart(); });
