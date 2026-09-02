from django.urls import path

from . import views


urlpatterns = [
    path("", views.catalogo, name="catalogo"),
    path("pedido/finalizar/", views.finalizar_pedido, name="finalizar_pedido"),
    path("pedido/<int:pk>/sucesso/", views.pedido_sucesso, name="pedido_sucesso"),
    path("gestao/", views.gestao_dashboard, name="gestao_dashboard"),
    path("gestao/pedidos/", views.gestao_pedidos, name="gestao_pedidos"),
    path("gestao/produtos/", views.gestao_produtos, name="gestao_produtos"),
    path("gestao/produtos/<int:pk>/editar/", views.gestao_produto_editar, name="gestao_produto_editar"),
    path("gestao/estoque/", views.gestao_estoque, name="gestao_estoque"),
    path("gestao/receitas/", views.gestao_receitas, name="gestao_receitas"),
    path("gestao/producao/", views.gestao_producao, name="gestao_producao"),
    path("gestao/datas-retirada/", views.gestao_datas_retirada, name="gestao_datas_retirada"),
    path("gestao/financeiro/", views.gestao_financeiro, name="gestao_financeiro"),
]
