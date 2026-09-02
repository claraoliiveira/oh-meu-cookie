# Oh! Meu Cookie — pedidos e gestão

Aplicação Django para receber pedidos e controlar produtos, clientes, receitas, custos, estoque de insumos, produções, contas a receber e fluxo de caixa. A estrutura foi baseada nas abas e regras da planilha `minha planilha confeitaria.xlsm.xlsx`.

## O que já está pronto

- Loja pública responsiva com catálogo, carrinho e checkout.
- Pedido salvo no banco e mensagem pronta para confirmação no WhatsApp.
- Loja de pedidos separada do painel de gestão.
- Painel protegido por usuário e senha, com botão interno para abrir a loja de pedidos.
- Pedidos somente para retirada, com pagamento por Pix ou cartão.
- Agenda de datas de retirada controlada pelo painel: o cliente só finaliza em uma data liberada.
- Painel protegido por login.
- Produtos e preços ligados às receitas.
- Cadastro, edição e ativação de produtos diretamente pelo painel de gestão.
- Custo total, custo unitário, lucro unitário e percentual de margem calculados automaticamente.
- Estoque de insumos com alerta de mínimo e histórico de movimentações.
- Produção que confere e desconta os ingredientes do estoque.
- Clientes e lembrete de aniversários.
- Contas a receber: marcar como pago cria automaticamente uma entrada no caixa.
- Fluxo de caixa mensal com entradas, saídas e saldo.
- Comando de importação da planilha original.
- Testes das principais regras de negócio.

## Instalação no Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py popular_demo
python manage.py runserver
```

Abra `http://127.0.0.1:8000/` para a loja e `http://127.0.0.1:8000/gestao/` para o painel.

No painel, acesse **Datas de retirada** para liberar ou remover os dias que aparecerão no checkout da loja.

O comando `popular_demo` cria temporariamente a usuária `clara` com a senha `troque-esta-senha`. Entre e troque a senha imediatamente.

## Importar a planilha

Depois de executar as migrações:

```powershell
python manage.py importar_planilha "C:\caminho\minha planilha confeitaria.xlsm.xlsx"
```

O importador lê as abas `Tabela de Custos`, `Receitas de doces`, `Clientes`, `Contas a Receber` e `Fluxo de Caixa`.

## Configuração do WhatsApp

No arquivo `.env`, informe o número com código do país e DDD, somente números:

```env
COOKIE_WHATSAPP_NUMBER=5533991254014
```

## Próxima etapa recomendada

Antes de colocar a aplicação aberta ao público, configure PostgreSQL, HTTPS, backups e uma conta administrativa com senha exclusiva. O SQLite incluído é ótimo para desenvolvimento e para começar em um único computador.
