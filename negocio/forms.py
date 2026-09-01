import json
from datetime import datetime, time

from django import forms
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import AvailablePickupDate, CashEntry, Ingredient, Order, Recipe


class CheckoutForm(forms.Form):
    name = forms.CharField(label="Seu nome", max_length=120)
    phone = forms.CharField(label="WhatsApp", max_length=30)
    email = forms.EmailField(label="E-mail", required=False)
    requested_for = forms.ChoiceField(label="Data da retirada", choices=())
    payment_method = forms.ChoiceField(label="Forma de pagamento", choices=Order.PaymentMethod.choices)
    notes = forms.CharField(label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    items_json = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_dates = AvailablePickupDate.objects.filter(active=True, pickup_date__gte=timezone.localdate()).order_by("pickup_date")
        self.fields["requested_for"].choices = [
            ("", "Selecione uma data disponível"),
            *((item.pickup_date.isoformat(), item.pickup_date.strftime("%d/%m/%Y")) for item in available_dates),
        ]

    def clean_requested_for(self):
        value = self.cleaned_data["requested_for"]
        pickup_date = parse_date(value)
        if not pickup_date or not AvailablePickupDate.objects.filter(active=True, pickup_date=pickup_date, pickup_date__gte=timezone.localdate()).exists():
            raise forms.ValidationError("Essa data não está disponível. Escolha uma das opções liberadas.")
        return timezone.make_aware(datetime.combine(pickup_date, time(hour=12)))

    def clean_items_json(self):
        try:
            items = json.loads(self.cleaned_data["items_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            raise forms.ValidationError("O carrinho está inválido.")
        cleaned = []
        for item in items:
            try:
                product_id = int(item["product_id"])
                quantity = int(item["quantity"])
            except (KeyError, TypeError, ValueError):
                continue
            if quantity > 0:
                cleaned.append({"product_id": product_id, "quantity": min(quantity, 100)})
        if not cleaned:
            raise forms.ValidationError("Escolha pelo menos um produto.")
        return cleaned


class AvailablePickupDateForm(forms.ModelForm):
    class Meta:
        model = AvailablePickupDate
        fields = ["pickup_date"]
        widgets = {"pickup_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pickup_date"].widget.attrs["min"] = timezone.localdate().isoformat()

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "unit", "package_quantity", "package_price", "current_stock", "minimum_stock"]


class StockEntryForm(forms.Form):
    ingredient = forms.ModelChoiceField(label="Ingrediente", queryset=Ingredient.objects.filter(active=True))
    quantity = forms.DecimalField(label="Quantidade comprada", min_value=0.001, decimal_places=3)
    amount = forms.DecimalField(label="Valor pago", min_value=0, decimal_places=2)
    description = forms.CharField(label="Descrição", max_length=200, initial="Compra de insumo")


class ProductionForm(forms.Form):
    recipe = forms.ModelChoiceField(label="Receita", queryset=Recipe.objects.filter(active=True))
    batches = forms.DecimalField(label="Quantas receitas?", min_value=0.01, decimal_places=2, initial=1)
    notes = forms.CharField(label="Observações", required=False, max_length=255)


class CashEntryForm(forms.ModelForm):
    class Meta:
        model = CashEntry
        fields = ["date", "description", "kind", "amount"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class ReceivableForm(forms.Form):
    customer_name = forms.CharField(label="Nome do cliente", max_length=120)
    phone = forms.CharField(label="WhatsApp", max_length=30)
    description = forms.CharField(label="Descrição", max_length=200)
    due_date = forms.DateField(
        label="Data de vencimento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    amount = forms.DecimalField(label="Valor", min_value=0.01, max_digits=12, decimal_places=2)
