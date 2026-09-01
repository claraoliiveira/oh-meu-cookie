from django.contrib import admin

from .models import (
    AvailablePickupDate,
    CashEntry,
    Customer,
    Ingredient,
    Order,
    OrderItem,
    Product,
    ProductionBatch,
    Receivable,
    Recipe,
    RecipeItem,
    StockMovement,
)


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "yield_quantity", "total_cost_display", "unit_cost_display", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    inlines = [RecipeItemInline]

    @admin.display(description="Custo total")
    def total_cost_display(self, obj):
        return f"R$ {obj.total_cost:.2f}"

    @admin.display(description="Custo/unidade")
    def unit_cost_display(self, obj):
        return f"R$ {obj.unit_cost:.2f}"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "payment_status", "delivery_type", "total", "created_at")
    list_filter = ("status", "payment_status", "delivery_type", "payment_method")
    search_fields = ("customer__name", "customer__phone")
    exclude = ("delivery_address", "delivery_fee")
    readonly_fields = ("delivery_type",)
    inlines = [OrderItemInline]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "current_stock", "unit", "minimum_stock", "unit_cost_display", "active")
    search_fields = ("name",)
    list_filter = ("unit", "active")

    @admin.display(description="Custo por unidade")
    def unit_cost_display(self, obj):
        return f"R$ {obj.unit_cost:.4f}"


admin.site.register([Product, Customer, AvailablePickupDate, StockMovement, ProductionBatch, Receivable, CashEntry])
admin.site.site_header = "Oh! Meu Cookie — Administração"
admin.site.site_title = "Oh! Meu Cookie"
