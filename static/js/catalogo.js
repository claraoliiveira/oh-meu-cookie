const cards = [...document.querySelectorAll("[data-product]")];
const dialog = document.querySelector("[data-cart-dialog]");
const count = document.querySelector("[data-cart-count]");
const itemsBox = document.querySelector("[data-cart-items]");
const totalBox = document.querySelector("[data-cart-total]");
const itemsInput = document.querySelector("#id_items_json");
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function selectedItems() {
  return cards.map((card) => ({
    product_id: Number(card.dataset.id),
    name: card.dataset.name,
    price: Number(card.dataset.price.replace(",", ".")),
    quantity: Number(card.querySelector("[data-quantity]").value),
  })).filter((item) => item.quantity > 0);
}

function renderCart() {
  const items = selectedItems();
  const quantity = items.reduce((sum, item) => sum + item.quantity, 0);
  const total = items.reduce((sum, item) => sum + item.quantity * item.price, 0);
  count.textContent = quantity;
  itemsInput.value = JSON.stringify(items.map(({ product_id, quantity: itemQuantity }) => ({ product_id, quantity: itemQuantity })));
  itemsBox.innerHTML = items.length ? items.map((item) => `
    <div class="cart-line"><div><strong>${item.quantity}x ${item.name}</strong><small>${money.format(item.price)} cada</small></div><strong>${money.format(item.price * item.quantity)}</strong></div>
  `).join("") : '<div class="empty-cart">Sua sacola ainda está vazia. Escolha um cookie — ou vários. 🍪</div>';
  totalBox.textContent = money.format(total);
}

cards.forEach((card) => {
  const output = card.querySelector("[data-quantity]");
  const maximum = Number(card.dataset.max || 0);
  card.querySelector("[data-plus]").addEventListener("click", () => { output.value = Math.min(Number(output.value) + 1, maximum); renderCart(); });
  card.querySelector("[data-minus]").addEventListener("click", () => { output.value = Math.max(Number(output.value) - 1, 0); renderCart(); });
});

document.querySelector("[data-open-cart]")?.addEventListener("click", () => { renderCart(); dialog.showModal(); });
document.querySelector("[data-checkout-form]")?.addEventListener("submit", (event) => {
  renderCart();
  if (!selectedItems().length) { event.preventDefault(); alert("Escolha pelo menos um cookie antes de enviar o pedido."); }
});
renderCart();
