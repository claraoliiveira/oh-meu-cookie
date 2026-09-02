from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AvailablePickupDateForm, CashEntryForm, CheckoutForm, IngredientForm, ProductForm, ProductionForm, ReceivableForm, StockEntryForm
from .models import AvailablePickupDate, CashEntry, Customer, Ingredient, Order, OrderItem, Product, Receivable, Recipe
from .services import atualizar_pedido, marcar_recebivel_pago, registrar_entrada_estoque, registrar_producao


def catalogo(request):
    products = Product.objects.filter(active=True).select_related("recipe")
    available_dates = AvailablePickupDate.objects.filter(active=True, pickup_date__gte=timezone.localdate()).order_by("pickup_date")
    return render(request, "loja/catalogo.html", {"products": products, "form": CheckoutForm(), "available_dates": available_dates})


@transaction.atomic
def finalizar_pedido(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Envie o formulário do pedido.")
    form = CheckoutForm(request.POST)
    products = Product.objects.filter(active=True).select_related("recipe")
    if not form.is_valid():
        available_dates = AvailablePickupDate.objects.filter(active=True, pickup_date__gte=timezone.localdate()).order_by("pickup_date")
        return render(request, "loja/catalogo.html", {"products": products, "form": form, "available_dates": available_dates}, status=400)

    data = form.cleaned_data
    requested_items = data["items_json"]
    selected_products = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=[item["product_id"] for item in requested_items],
            active=True,
        )
    }
    availability_errors = []
    for item in requested_items:
        product = selected_products.get(item["product_id"])
        if not product:
            availability_errors.append("Um dos produtos não está mais disponível.")
        elif item["quantity"] > product.available_quantity:
            availability_errors.append(
                f"{product.name}: escolha até {product.available_quantity} unidade(s)."
            )
    if availability_errors:
        form.add_error("items_json", " ".join(availability_errors))
        available_dates = AvailablePickupDate.objects.filter(active=True, pickup_date__gte=timezone.localdate()).order_by("pickup_date")
        return render(request, "loja/catalogo.html", {"products": products, "form": form, "available_dates": available_dates}, status=400)

    customer = Customer.objects.filter(phone=data["phone"]).first()
    if customer:
        customer.name = data["name"]
        customer.email = data["email"]
        customer.save()
    else:
        customer = Customer.objects.create(name=data["name"], phone=data["phone"], email=data["email"])

    order = Order.objects.create(
        customer=customer,
        delivery_type=Order.DeliveryType.PICKUP,
        delivery_address="",
        requested_for=data["requested_for"],
        payment_method=data["payment_method"],
        delivery_fee=Decimal("0"),
        notes=data["notes"],
    )
    for item in requested_items:
        product = selected_products.get(item["product_id"])
        if product:
            OrderItem.objects.create(order=order, product=product, quantity=item["quantity"], unit_price=product.sale_price)
    if not order.items.exists():
        order.delete()
        form.add_error("items_json", "Os produtos escolhidos não estão disponíveis.")
        available_dates = AvailablePickupDate.objects.filter(active=True, pickup_date__gte=timezone.localdate()).order_by("pickup_date")
        return render(request, "loja/catalogo.html", {"products": products, "form": form, "available_dates": available_dates}, status=400)
    order.recalculate_total()
    return redirect("pedido_sucesso", pk=order.pk)


def pedido_sucesso(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer").prefetch_related("items__product"), pk=pk)
    lines = [f"Olá! Acabei de fazer o pedido #{order.pk} pelo site:"]
    lines.extend(f"• {item.quantity}x {item.product.name} — R$ {item.subtotal:.2f}" for item in order.items.all())
    lines.append(f"Total: R$ {order.total:.2f}")
    lines.append("Recebimento: Retirada no local")
    if order.requested_for:
        lines.append(f"Data da retirada: {timezone.localtime(order.requested_for):%d/%m/%Y}")
    lines.append(f"Pagamento: {order.get_payment_method_display()}")
    whatsapp_url = f"https://wa.me/{settings.COOKIE_WHATSAPP_NUMBER}?text={quote(chr(10).join(lines))}"
    return render(request, "loja/sucesso.html", {"order": order, "whatsapp_url": whatsapp_url})


@login_required
def gestao_dashboard(request):
    today = timezone.localdate()
    month_entries = CashEntry.objects.filter(date__year=today.year, date__month=today.month)
    income = month_entries.filter(kind=CashEntry.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expense = month_entries.filter(kind=CashEntry.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    context = {
        "new_orders": Order.objects.filter(status=Order.Status.NEW).count(),
        "low_stock": Ingredient.objects.filter(active=True, current_stock__lte=models_f_min_stock()).count(),
        "pending_receivables": Receivable.objects.filter(status=Receivable.Status.PENDING).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "recent_orders": Order.objects.select_related("customer").prefetch_related("items")[:8],
        "birthday_customers": Customer.objects.filter(birthday__month=today.month, birthday__day=today.day),
    }
    return render(request, "gestao/dashboard.html", context)


def models_f_min_stock():
    from django.db.models import F

    return F("minimum_stock")


@login_required
def gestao_pedidos(request):
    if request.method == "POST":
        order = get_object_or_404(Order, pk=request.POST.get("order_id"))
        status = request.POST.get("status")
        payment_status = request.POST.get("payment_status")
        if status in Order.Status.values and payment_status in Order.PaymentStatus.values:
            had_stock_deducted = bool(order.stock_deducted_at)
            try:
                updated_order = atualizar_pedido(order, status, payment_status)
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
            else:
                if updated_order.stock_deducted_at and status == Order.Status.APPROVED:
                    messages.success(request, f"Pedido #{order.pk} aprovado e quantidade pronta atualizada.")
                elif status == Order.Status.CANCELLED and had_stock_deducted:
                    messages.success(request, f"Pedido #{order.pk} cancelado. As unidades reservadas voltaram ao estoque.")
                else:
                    messages.success(request, f"Pedido #{order.pk} atualizado.")
        return redirect("gestao_pedidos")
    query = request.GET.get("q", "").strip()
    orders = Order.objects.select_related("customer").prefetch_related("items__product")
    if query:
        orders = orders.filter(Q(customer__name__icontains=query) | Q(customer__phone__icontains=query))
    return render(
        request,
        "gestao/pedidos.html",
        {
            "orders": orders[:100],
            "statuses": Order.Status.choices,
            "payment_statuses": Order.PaymentStatus.choices,
            "query": query,
        },
    )


@login_required
def gestao_produtos(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add" and form.is_valid():
            product = form.save()
            messages.success(request, f"Produto {product.name} cadastrado.")
            return redirect("gestao_produtos")
        if action == "toggle":
            product = get_object_or_404(Product, pk=request.POST.get("product_id"))
            product.active = not product.active
            product.save(update_fields=["active"])
            state = "ativado na loja" if product.active else "retirado da loja"
            messages.success(request, f"Produto {product.name} {state}.")
            return redirect("gestao_produtos")

    products = Product.objects.select_related("recipe").order_by("-active", "-featured", "name")
    return render(request, "gestao/produtos.html", {"form": form, "products": products})


@login_required
def gestao_produto_editar(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"Produto {product.name} atualizado.")
        return redirect("gestao_produtos")
    return render(request, "gestao/produto_form.html", {"form": form, "product": product})


@login_required
def gestao_estoque(request):
    ingredient_form = IngredientForm(prefix="ingredient")
    entry_form = StockEntryForm(prefix="entry")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "ingredient":
            ingredient_form = IngredientForm(request.POST, prefix="ingredient")
            if ingredient_form.is_valid():
                ingredient_form.save()
                messages.success(request, "Ingrediente cadastrado.")
                return redirect("gestao_estoque")
        if action == "entry":
            entry_form = StockEntryForm(request.POST, prefix="entry")
            if entry_form.is_valid():
                registrar_entrada_estoque(**entry_form.cleaned_data)
                messages.success(request, "Entrada registrada no estoque.")
                return redirect("gestao_estoque")
    ingredients = Ingredient.objects.filter(active=True)
    return render(request, "gestao/estoque.html", {"ingredients": ingredients, "ingredient_form": ingredient_form, "entry_form": entry_form})


@login_required
def gestao_receitas(request):
    recipes = Recipe.objects.filter(active=True).prefetch_related("items__ingredient", "products")
    return render(request, "gestao/receitas.html", {"recipes": recipes})


@login_required
def gestao_producao(request):
    form = ProductionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            batch = registrar_producao(**form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, f"Produção registrada: {batch.units_produced} unidades.")
            return redirect("gestao_producao")
    from .models import ProductionBatch

    return render(request, "gestao/producao.html", {"form": form, "batches": ProductionBatch.objects.select_related("recipe")[:50]})


@login_required
def gestao_datas_retirada(request):
    form = AvailablePickupDateForm(request.POST or None)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            pickup_date = get_object_or_404(AvailablePickupDate, pk=request.POST.get("date_id"))
            pickup_date.delete()
            messages.success(request, "Data removida das opções de retirada.")
            return redirect("gestao_datas_retirada")
        if action == "add" and form.is_valid():
            pickup_date = form.save(commit=False)
            pickup_date.active = True
            pickup_date.save()
            messages.success(request, "Data liberada para novos pedidos.")
            return redirect("gestao_datas_retirada")

    available_dates = AvailablePickupDate.objects.filter(active=True, pickup_date__gte=timezone.localdate()).order_by("pickup_date")
    return render(request, "gestao/datas_retirada.html", {"form": form, "available_dates": available_dates})


@login_required
def gestao_financeiro(request):
    cash_form = CashEntryForm(prefix="cash")
    receivable_form = ReceivableForm(prefix="receivable")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "cash":
            cash_form = CashEntryForm(request.POST, prefix="cash")
            if cash_form.is_valid():
                cash_form.save()
                messages.success(request, "Lançamento adicionado ao caixa.")
                return redirect("gestao_financeiro")
        if action == "receivable":
            receivable_form = ReceivableForm(request.POST, prefix="receivable")
            if receivable_form.is_valid():
                data = receivable_form.cleaned_data
                customer = Customer.objects.filter(phone=data["phone"]).first()
                if customer:
                    customer.name = data["customer_name"]
                    customer.save(update_fields=["name"])
                else:
                    customer = Customer.objects.create(name=data["customer_name"], phone=data["phone"])
                Receivable.objects.create(
                    customer=customer,
                    description=data["description"],
                    due_date=data["due_date"],
                    amount=data["amount"],
                )
                messages.success(request, "Conta a receber cadastrada.")
                return redirect("gestao_financeiro")
        if action == "pay":
            receivable = get_object_or_404(Receivable, pk=request.POST.get("receivable_id"))
            marcar_recebivel_pago(receivable)
            messages.success(request, "Conta marcada como paga e incluída nas entradas.")
            return redirect("gestao_financeiro")

    today = timezone.localdate()
    entries = CashEntry.objects.filter(date__year=today.year, date__month=today.month)
    income = entries.filter(kind=CashEntry.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expense = entries.filter(kind=CashEntry.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return render(
        request,
        "gestao/financeiro.html",
        {
            "cash_form": cash_form,
            "receivable_form": receivable_form,
            "entries": entries[:100],
            "receivables": Receivable.objects.select_related("customer", "order")[:100],
            "income": income,
            "expense": expense,
            "balance": income - expense,
        },
    )
