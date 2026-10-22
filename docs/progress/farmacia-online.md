# Farmácia Online e marketplace de medicamentos — progresso

Fase actual: **1 a 6 implementadas em `dev`** (2026-10-18). Ver testes e limitações.
Repositórios alteráveis: `dev/back`, `dev/front`. `lib/django_resaas` e
`lib/quasar_resaas` só leitura.

## Estado inicial (2026-10-18)

| Repositório | Branch | Commit | Alterações locais |
|---|---|---|---|
| dev/back | develop | `d3f6d5d` (v1.0.80) | nenhuma |
| dev/front | main | `aa64df7` (v0.0.56) | 12 (sites por EntityType em `src/pages/`) |
| lib/django_resaas | develop | `56ddbb8f` (0.0.660) | nenhuma |
| lib/quasar_resaas | main | `0b7a6e29` (0.0.1461) | nenhuma |

## O que já existe e vai ser reutilizado

| Necessidade | Já existe | Onde |
|---|---|---|
| Farmácia (estabelecimento) | `Branch` de uma `Entity` do tipo `Farmacia` | django_resaas |
| Localização | `Branch` + `AddressMixin` (morada, `latitude`/`longitude`) | django_resaas `models/address.py` |
| Leitura pública de branches | `GET site/branches/` (por `Origin`, uma Entity) | django_resaas `public-sites.md` |
| Acções entre Entities | `BaseAPIView.cross_entity_actions` (opt-in por acção) | django_resaas `core/base/views.py` |
| Produto | `inventory.Product` (por Entity: `codigo`, `nome`, `preco_base`, `track_batches`) | dev/back |
| Stock, lotes, validade | `StockItem`, `Batch`, `BatchStock`, `allocate_batches` (FIFO/FEFO) | inventory |
| Reservas | `StockReservation`, `reserve_document` / `release_reservations` / `consume_reservations` | inventory |
| Movimentos auditáveis | `StockMovement`, `apply_movement`, `commit_sale_movements`, `commit_dispensation_movements` | inventory |
| Preço por estabelecimento | `PriceList` / `PriceListItem`, `get_price()` | inventory |
| Venda presencial | `sales.Sale` (rascunho → confirmada → paga / anulada), `reserve_sale_stock`, `confirm_sale`, `cancel_sale`, `add_payment` (numerário, M-Pesa, e-Mola, mKesh, cartão, ...) | sales |
| Receitas | `saude.ReceitaMedica` + `ItemReceita` → `saude.Medicamento` (`principio_ativo`, `forma_farmaceutica`, `dosagem`) | saude |
| Fila e dispensa | `FilaFarmacia` (pendente → aprovada → dispensada parcial/total), `Dispensa`, `ItemDispensa` (lote, produto, movimento) | farmacia |
| Código do paciente | `Paciente.nid` (único por Branch) + `PatientIdentifier` | saude |
| Acesso entre Entities a dados clínicos | `ConsentGrant` (pessoa, entidade origem → destino, `scope`, expiração, revogação), `EmergencyAccess`, `PatientAccessService.get_authorized_scope` | saude |
| Seeds de demonstração | `seed_saude_demo` (idempotente, `--dry-run`, recusa sem `--allow-production` com DEBUG off) | saude |

## Lacunas encontradas

1. **Não há catálogo comum de medicamentos.** `inventory.Product` e
   `saude.Medicamento` pertencem a cada Entity. Dois produtos de farmácias
   diferentes não têm nenhuma chave comum que prove que são o mesmo
   medicamento (substância, dosagem, forma, apresentação). Sem isso não se
   pode comparar preços com segurança (regra 4.8).
2. **Não há publicação no marketplace.** Não existe nada que diga que uma
   farmácia aceita aparecer, o seu horário, telefone público, se vende
   online ou se entrega. A Entity e a Branch estão na `lib` (só leitura).
3. **`Product` não sabe se exige receita** nem se pode ser vendido online.
4. **Não há encomenda online.** `Sale` é interna de cada Entity; não há
   pagamento online integrado (os métodos de `Payment` são registados ao
   balcão) nem entregas.
5. **O código do paciente não é global.** `Paciente.nid` é único por Branch;
   uma farmácia só vê receitas de outra Entity através de `ConsentGrant`.
6. **Farmácia depende de Saúde.** `FilaFarmacia.receita` e
   `ItemDispensa.medicamento` são FK para `saude` (o pedido quer Farmácia
   utilizável sem Saúde). A venda sem receita não passa por estas tabelas,
   por isso continua possível; a dispensa com receita continua a precisar
   de Saúde.

## Plano proposto

Todo o código novo vive em `dev/back/farmacia` (e `dev/front/src/pages/farmacia`),
reutilizando os serviços de inventory/sales/saude por chamadas aos seus
serviços públicos (a convenção que `farmacia/services.py` já segue).

**Modelos novos (farmacia)**

- `MedicineCatalogItem` — catálogo comum, de plataforma (gerido por Root):
  substância activa, dosagem, forma farmacêutica, apresentação, código
  (registo nacional / GTIN quando existir), `prescription_required`.
- `PharmacyListing` — uma por Branch publicada: `published` (por omissão
  `False`), telefone público, horário (texto estruturado só se preenchido),
  `online_orders` / `delivery` (por omissão `False`).
- `PharmacyOffer` — liga um `inventory.Product` da farmácia a um
  `MedicineCatalogItem` (é isto que torna dois produtos comparáveis) e diz
  se é vendável online.

**API (sempre com permissão por acção; ver tabela)**

| Endpoint | Acesso | Devolve |
|---|---|---|
| `GET farmacia/marketplace/pharmacies/?lat&lng&q&city` | PÚBLICO, com throttle | farmácias publicadas: nome, morada, distância (só com coordenadas reais), telefone e horário publicados |
| `GET farmacia/marketplace/medicines/?q&...` | PROTEGIDO (autenticado) | medicamentos do catálogo com ofertas por farmácia: preço de `get_price()`, disponibilidade calculada (stock − reservas − lotes expirados), sem custos, fornecedores ou movimentos |
| `POST farmacia/marketplace/orders/` | PROTEGIDO | uma encomenda **por farmácia** (`Sale` em rascunho + `StockReservation`), preço e stock revalidados no servidor, chave de idempotência |
| balcão (`counter/`) | PROTEGIDO, contexto da farmácia | `Sale` + `confirm_sale` + `commit_sale_movements`; com receita, `dispense()` existente |
| `GET farmacia/patients/lookup/?code=` | PROTEGIDO, permissão própria, auditado | paciente e receitas pendentes só da própria Entity ou com `ConsentGrant` activo com scope de receitas |

**Fases** — 1 catálogo + publicação + pesquisa; 2 disponibilidade + seed
`seed_pharmacy_demo` (padrão do `seed_saude_demo`); 3 encomenda online;
4 balcão; 5 paciente e receitas; 6 segurança, testes, documentação.

## Decisões pedidas ao proprietário

1. Catálogo comum de medicamentos (proposta acima) ou comparar só por código/GTIN.
2. Encomenda online = reserva e levantamento na farmácia com pagamento ao
   balcão (sem pagamento online nem entrega, que não existem hoje).
3. Acesso a receitas de outra Entity só com `ConsentGrant` (o código do
   paciente localiza, não autoriza).
4. Receitas em papel: registadas como "papel, verificada pelo
   farmacêutico", nunca como validadas pelo sistema; receitas externas
   ficam fora até haver uma integração real.

Decisões aprovadas pelo proprietário (2026-10-18): 1 catálogo comum, 2 reserva e
levantamento, 3 receitas de outra Entity só com `ConsentGrant`, 4 papel = "verificada
pelo farmacêutico".

## Fase 1 — implementado

| Peça | Onde |
|---|---|
| `MedicineCatalogItem` (TimeModel, plataforma), `PharmacyListing`, `PharmacyOffer` (BaseModel) | `farmacia/models/` |
| Migração `0002_marketplace` (não versionada, como todas as do farmacia: `.gitignore`) | `farmacia/migrations/` |
| `marketplace_service`: farmácias elegíveis (ficha publicada + módulo farmacia activo), distância (só com coordenadas da morada principal da Branch), ofertas com preço (`inventory.get_prices`) e disponibilidade (`inventory.branch_available_quantities`) | `farmacia/marketplace_service.py` |
| `GET farmacia/marketplace/pharmacies/` PÚBLICO (`public_actions`), `GET farmacia/marketplace/medicines/` PROTEGIDO (autenticado, sem contexto de tenant); throttle por endereço `FARMACIA_MARKETPLACE_THROTTLE_RATE` (600/hora); páginas de 20 (máx. 50) | `farmacia/views/marketplace.py` |
| CRUD `medicinecatalogitems/`, `pharmacylistings/`, `pharmacyoffers/` (BaseAPIView: permissão por acção, âmbito Entity/Branch) | `farmacia/views/` |
| Validação: produto e tabela de preços da própria Entity, um produto por Branch, uma ficha por Branch (inclui linhas apagadas), moeda ISO de 3 letras | `farmacia/serializers/` |
| Perfis: Pharmacy Manager gere ficha e ofertas e lê o catálogo; Pharmacist lê catálogo e ofertas; só Root escreve o catálogo | `farmacia/profiles.py` |
| Inventory (genérico): `get_prices()`, `branch_available_quantities()`, `ativo` em `get_product_snapshot()` | `inventory/services.py` |
| Front: site do EntityType Farmacia = Farmácia Online (farmácias próximas para todos, pesquisa com sessão); `/farmacia_online` na app; gestão com `s-auto-crud` | `front/src/pages/farmacia/` |
| Traduções pt/es/fr (71 chaves novas) | `farmacia/lang/` |

Regras de exposição: a quantidade exacta só aparece com `show_quantity`; os resultados
nunca incluem custo, fornecedor, movimentos ou o id do produto. A pesquisa avalia no
máximo 300 ofertas; acima disso responde `400 search_too_broad` em vez de truncar.

## Testes (executados)

| Comando | Resultado |
|---|---|
| `pytest --nomigrations farmacia` | 66 passed (19 do marketplace) |
| `pytest --nomigrations inventory farmacia/tests/test_access_guard.py` | 100 passed, 7 subtests |
| `npx vitest run` (front) | 14 passed |
| `eslint` (ficheiros novos do front) | sem erros |
| `manage.py check`, `makemigrations --check` | sem problemas / sem alterações |
| `pytest --nomigrations farmacia/tests/test_demo_seed.py` | 9 passed |
| **Fase 6** `pytest --nomigrations farmacia inventory sales` | 315 passed + 3 traduções em falta → corrigidas; `test_translations_complete` 50 passed |
| novos: `test_online_orders.py` (25), `test_patient_lookup.py` (7), `test_access_guard.py` | incluídos acima |
| `npx vitest run` (front, inclui `useMarketplace.spec.js` e a resolução de todas as páginas) | 18 passed |
| `eslint src/pages/farmacia` | sem erros |
| `manage.py check`, `makemigrations --check`, `git diff --check` | sem problemas |
| `dev`: `migrate farmacia` (0002, 0003), `seed_pharmacy_demo`, `sync_actions` | aplicado; 3 farmácias demo, 24 ofertas, 447 unidades |

## Limitações conhecidas

- Gestão das ofertas: o produto escolhe-se pelo id (`s-auto-crud`); falta um seletor de produtos.
- Não há preço de referência legal nem "lote bloqueado" no inventory: não são mostrados.
- A ordenação por preço é feita sobre as ofertas candidatas (tecto de 300), não na base de dados.

## Fase 2 — stock real e dados de demonstração

A disponibilidade já é a real desde a fase 1 (`branch_available_quantities`: stock dos
armazéns activos − reservas − lotes expirados). A fase 2 acrescenta o seed:

```
python manage.py seed_pharmacy_demo --actor-user <utilizador> [--region mozambique|ahmedabad] [--pharmacies N] [--entity-type Farmacia] [--dry-run]
```

| Regra | Como |
|---|---|
| Fictício e identificado | cada farmácia é uma **Entity nova** `[DEMO] Farmácia Demo ...`; produtos `DEMO-001...` com "(demo)" no nome; horário "Demo pharmacy - fictitious data"; telefone `+258 00 000 0000` |
| Nunca em produção por omissão | com `DEBUG` desligado recusa sem `--allow-production` |
| Não toca farmácias reais | só escreve em Entities `[DEMO]` que ele próprio cria; itens do catálogo já existentes são reutilizados sem alteração; os em falta são criados com código `DEMO-MED-...` |
| Idempotente | farmácia, produto, oferta e ficha reutilizados; o stock só entra (movimento `entrada` com lote e validade) quando o produto é criado |
| Auditável | o autor é um utilizador existente (`--actor-user`); nenhum utilizador ou palavra-passe é criado |
| `--dry-run` | corre numa transacção revertida e mostra as contagens |

Conteúdo: 8 medicamentos (4 com receita obrigatória) em até 5 farmácias de Maputo e
Matola com coordenadas; preços ±15% à volta de um preço base (comparáveis entre
farmácias); algumas ofertas esgotadas de propósito; `show_quantity` em farmácias alternadas.

Serviço `farmacia/demo_seed_service.py`; comando `farmacia/management/commands/seed_pharmacy_demo.py`;
`--region` (`REGIONS` no serviço) escolhe onde ficam as farmácias, com país, moeda e telefone fictício
da região: `mozambique` (por omissão, 5, MZN) ou `ahmedabad` (2 em Chandkheda, Índia, INR — para testar o mapa
e o raio de 3 km a partir dali). Em `dev` (2026-10-20): `--region ahmedabad --pharmacies 2` → 2 farmácias,
16 ofertas, 278 unidades.
testes `farmacia/tests/test_demo_seed.py` (10, inclui a região; criação, aparece na pesquisa com preços
diferentes, segunda execução não cria nada, acrescentar farmácias, dry-run, farmácia e
catálogo reais intactos, entradas explícitas, recusa sem `DEBUG`, contagens do comando).

Limitação: as farmácias demo não têm utilizadores; para as gerir (fase 4, balcão) é preciso
associar um utilizador à Entity pelo processo normal.

## Fase 3 — encomenda online (reserva e levantamento)

Fluxo: o comprador (qualquer utilizador com sessão, de qualquer Entity) junta ofertas de
várias farmácias; o servidor cria **uma `OnlineOrder` por farmácia**, com as linhas e os
preços tirados nesse momento (`get_price` com a quantidade), e reserva o stock no
`inventory` (`StockReservation`, origem `farmacia.online_order`) num armazém da farmácia
que tenha a quantidade toda. Não há pagamento online nem entrega: paga-se ao levantar.

| Endpoint | Acesso | Efeito |
|---|---|---|
| `GET farmacia/marketplace/orders/` | PROTEGIDO (autenticado) | as encomendas do próprio comprador (nunca armazém, venda, chave) |
| `POST farmacia/marketplace/orders/` `{lines:[{offer_id, quantity}], contact_name, contact_phone, idempotency_key}` | PROTEGIDO | 201; tudo ou nada |
| `POST farmacia/marketplace/orders/{id}/cancel/` | PROTEGIDO, só a própria | liberta a reserva; outra pessoa recebe 404 |
| `GET farmacia/onlineorders/` / `{id}/` | `list_onlineorder` / `view_onlineorder`, Entity + Branch da farmácia | lista com `effective_status` |
| `POST farmacia/onlineorders/{id}/collect/` | `collect_onlineorder` | venda ao balcão da encomenda (fase 4) |
| `POST farmacia/onlineorders/{id}/cancel/` `{reason}` | `cancel_onlineorder` | liberta a reserva |

Regras (no servidor): oferta activa, `online_sale`, ficha publicada com `online_orders`,
módulos `farmacia` **e `sales`** activos (sem `sales` o marketplace mostra "só na farmácia");
1–20 linhas, quantidades inteiras 1–100; reserva com `select_for_update` na linha de stock
(dois compradores nunca seguram as mesmas unidades); mesma `idempotency_key` = mesmas
encomendas (constraint `(buyer, idempotency_key, branch)`); reserva até
`FARMACIA_ONLINE_ORDER_HOLD_HOURS` (24 h por omissão).

Expiração: a reserva deixa de contar no `expires_at` por si (regra do `inventory`); a
leitura mostra `expired` sem escrever (GET nunca muda estado); `manage.py
expire_online_orders` (cron, p. ex. de 15 em 15 min) grava o estado e fecha as reservas.

Erros: `invalid_lines`, `invalid_quantity`, `invalid_idempotency_key` (400),
`offer_unavailable`, `insufficient_stock`, `order_not_reserved` (409), `order_not_found` (404).

## Fase 4 — venda ao balcão

`online_order_service.sell()` reutiliza o `sales`: `create_sale()` (novo, genérico) →
`reserve_sale_stock()` → `confirm_sale()` (movimentos de saída com lotes FEFO/FIFO, consome
a reserva) → `add_payment()` pelo total. Tudo numa transacção. Ao levantar uma encomenda,
a reserva da encomenda é libertada e reservada de novo para a venda sob o mesmo lock;
a encomenda fica `collected` com `sale_id`.

| Endpoint | Permissão | |
|---|---|---|
| `GET farmacia/countersales/offers/?q=` | `add_countersale` | ofertas da Branch actual (publicada ou não) com preço e quantidade vendável |
| `POST farmacia/countersales/` `{lines, payment_method, payment_reference?, prescription_verified?, prescription_reference?, idempotency_key}` | `add_countersale` | 201 `CounterSale` |
| `GET farmacia/countersales/` / `{id}/` | `list_countersale` / `view_countersale` | |

- Ao balcão não se vende o que está reservado online (409 `insufficient_stock`).
- Linha com receita obrigatória: exige `prescription_verified=true`
  (400 `prescription_not_verified`); grava-se **quem** verificou
  (`prescription_verified_by`) e a referência escrita na receita em papel. É uma
  declaração do farmacêutico, nunca uma validação do sistema (decisão 4).
- `payment_method` = códigos de `sales.Payment` (`sales.services.PAYMENT_METHODS`).
- `sales_module_inactive` (409) quando a Entity não tem `sales` activo.

## Fase 5 — paciente por código e receitas

| Endpoint | Permissão | |
|---|---|---|
| `POST farmacia/filafarmacias/lookup_patient/` `{code}` | `lookup_patient_filafarmacia` | paciente, receitas (até 20, com proveniência), alergias, `consent_scope` |
| `POST farmacia/filafarmacias/enqueue/` `{receita_id}` | `enqueue_filafarmacia` | põe a receita na fila desta farmácia (`enqueue_prescription`, idempotente); a dispensa segue o fluxo existente (`revisar` → `dispensar` → `concluir`) |

- O código procura `Paciente.nid` e `PatientIdentifier.identifier` (sem distinguir maiúsculas).
- Paciente da própria Entity: mostrado. Só de outra Entity: só com `ConsentGrant` activo
  (ou `EmergencyAccess` em curso) para a Entity da farmácia com `"prescriptions"` no scope
  (`PatientAccessService`, a mesma regra da timeline); alergias só com `"allergies"`.
- Sem autorização a resposta é **igual** à de código inexistente (404 `patient_not_found`):
  o código não revela que o paciente existe noutro lado. Vários pacientes com o mesmo
  código: 409 `ambiguous_patient_code`.
- POST e não GET: o código não fica em URLs nem nos logs de acesso, e cada pesquisa
  escreve uma linha de auditoria `PatientLookup` (quem, onde, código, resultado
  `own`/`consent`/`denied`/`not_found`, pessoa mostrada).

## Perfis (código: `farmacia/profiles.py`)

| Perfil | Novas permissões |
|---|---|
| Pharmacy Manager e Pharmacist | `list/view_onlineorder`, `collect_onlineorder`, `cancel_onlineorder`, `list/view/add_countersale`, `lookup_patient_filafarmacia`, `enqueue_filafarmacia` |
| Pharmacy Technician, Dispensing Assistant | nenhuma (não verificam receitas nem vendem) |

As permissões das acções (`collect_`, `cancel_`, `lookup_patient_`, `enqueue_`) são criadas
por `sync_actions`; os perfis aplicam-se com `group_creator` (no `pro`, via `migrate`/setup).

## Frontend (`front/src/pages/farmacia/`)

| Página / componente | Rota | Usa |
|---|---|---|
| `marketplace/PharmaciesMap.vue` (dentro de `NearbyPharmacies.vue`, no site e em `/farmacia_online`) | — | `usePharmacies` (GET público `pharmacies/`), `mapPoints`, `loadMaps` |
| `marketplace/ReservationCart.vue`, `MyOrders.vue` (no site e em `/farmacia_online`) | — | `useCart`, `placeOrders`, `useMyOrders`, `cancelMyOrder` |
| `counter/CounterPage.vue` | `farmacia_counter` | `counterOffers`, `sellAtCounter`, `PaymentFields.vue` |
| `counter/OnlineOrdersPage.vue` | `farmacia_online_orders` | `onlineOrders`, `collectOrder`, `cancelOrder` |
| `counter/PatientLookupPage.vue` | `farmacia_patient_lookup` | `lookupPatient`, `enqueuePrescription` |

**Disposição.** O site da Farmácia (`SitePage.vue`) e `/farmacia_online` (`MarketplacePage.vue`)
usam o mesmo `marketplace/MarketplaceLayout.vue` (prop `signedIn`; slot `signed-out` para o aviso de
login do site). A partir de `md` (1024px): duas colunas, à esquerda pesquisa, carrinho e reservas
(`col-md-7`), à direita as farmácias no mapa (`col-md-5`, `position: sticky`, `top: 72px`, como
`UserAccountPage` do quasar_resaas).

*Telemóvel e tablet (abaixo de `md`, 2026-10-20).* Uma secção de cada vez, escolhida por separadores
(`q-tabs`, ícone sobre o texto, 56px): **Medicines**, **Pharmacies** e, com sessão, **Reservations**
(com o número de unidades no carrinho). Os separadores são uma barra fixa em baixo, colada ao rodapé
(`q-page-sticky position="bottom"`, que usa a altura do rodapé do layout; indicador em cima, 56px); o botão
"View reservation" fica 12px acima dela. Na pesquisa, "In stock" está na mesma linha do campo de pesquisa e a
dica "Type at least two letters of a medicine." é o `hint` desse campo, só a partir de `md` (no telemóvel não aparece). A partir de `md`, por baixo, "Sort by", preço mínimo e máximo ficam a `col-4` cada (espaço vertical `xs`). No telemóvel (2026-10-20) a secção é só o campo de pesquisa, sem título: "In stock", "Sort by" e o intervalo de preço estão num menu (`q-menu`) aberto pelo botão `tune` dentro do campo, à direita, com um contador dos filtros fora do valor por defeito. O menu abre centrado por baixo do campo e com a largura dele (`target` = o campo, `fit`, `no-parent-event`: tocar no campo para escrever não o abre); o campo fica fixo 8px (sm) por baixo do cabeçalho da app enquanto os resultados fazem scroll (`position: sticky`); não há padding à volta - o próprio campo é o cartão (fundo branco e sombra, sem espaço de dica por baixo). Regra (2026-10-20): todos os botões têm tooltip - `<s-tooltip>` com o próprio rótulo nos `s-btn`/`q-btn`, `title` nos botões do cartão do mapa. O campo de pesquisa (`PharmacySearchField.vue`, texto dentro: "Nearby pharmacies: name or address", sem rótulo por cima; o próprio campo é o cartão, sem padding, fundo branco e sombra) fica a flutuar no topo do mapa, centrado (slot `top` de `PharmaciesMap`, até 440px), também no ecrã inteiro; a barra da rota fica 8px por baixo dele. No telemóvel (abaixo de `md`) a grelha não tem gutter (uma coluna de cada vez) e o mapa vai de margem a margem, sem bordas nem cantos redondos. A altura do mapa é calculada para acabar onde começa a barra de separadores (`--marketplace-map-height`, `fitMapHeight` em `MarketplaceLayout.vue`: altura da janela menos o topo do mapa, o rodapé e a barra; recalculada ao redimensionar, ao voltar ao separador e quando muda o que está por cima; mínimo 240px - num ecrã muito baixo há scroll). O mapa mostra-se mesmo quando a pesquisa não encontra farmácias (o campo não pode desaparecer enquanto se escreve); sem chave do Google ou com o script falhado, o campo volta para cima da lista. "Use my location" é um botão-ícone dentro do campo "Name or address" (verde enquanto a posição está em uso). A secção Pharmacies pede a posição do dispositivo ao abrir (como se "Use my location" fosse carregado; recusada, a lista fica e aparece a mensagem habitual). "Pharmacies near you are highlighted. (≤ N km)" fica dentro do mapa, em baixo e centrado (slot `bottom` de `PharmaciesMap`, `NearbyRadius.vue`), com − / + para mudar o raio pelos passos `RADIUS_STEPS_KM` (1, 2, 3, 5, 10, 20 km; começa em `NEARBY_RADIUS_KM` = 3; `stepRadius`): o círculo, os pinos destacados e a contagem seguem o raio, também no ecrã inteiro; os botões desactivam-se nos extremos.
As secções são escondidas com `v-show`, não destruídas: a pesquisa, o carrinho e a rota sobrevivem à
troca; ao voltar a "Pharmacies" o mapa reenquadra-se (`NearbyPharmacies.refreshMap()` →
`PharmaciesMap.refresh()`). "Medicines at this pharmacy" no mapa abre "Medicines" já filtrado. Com o
carrinho cheio, um botão flutuante "View reservation" (`q-page-sticky` em baixo, acima do rodapé) leva às
reservas a partir de qualquer secção; "Reserve" numa oferta confirma com uma notificação curta
("Added to the reservation."). Regras de UX aplicadas: alvos de toque de 36–40px (Reserve de tamanho médio, 36px, a toda a
largura no telemóvel; no carrinho − / + e apagar são `sm`, 24px), texto de 16px nos campos (evita o zoom do iOS), filtros secundários escondidos
(medicamentos: preço atrás de "Price"; farmácias: um só campo "Name or address" - 2026-10-20 - em que cada palavra tem de aparecer no nome, organização, morada, bairro, cidade ou país, `_matches_place`; os parâmetros `city`/`neighborhood`/`country` da API continuam a funcionar),
título de secção repetido omitido (o separador já o diz), "Use my location" a toda a largura, telefone
com `type="tel"` e `autocomplete`, sem scroll horizontal, mapa com 62vh, e no ecrã inteiro o mapa move-se
com um dedo (`gestureHandling: 'greedy'`; na página continua `cooperative` para não prender o scroll).
As ofertas são cartões (`.offer`, grelha CSS): foto, medicamento e farmácia; preço, stock e "Reserve" ao
lado, ou por baixo em ecrãs < 600px. O "hero" do site encolhe abaixo de `md` e, sem sessão, não tem botões e, com sessão, só aparece a partir de `md` (2026-10-20): no telemóvel com sessão o site começa logo nas secções; entrar, registar e sair ficam no menu do utilizador do cabeçalho. Verificado no browser a
360, 390, 768 e 1440px (com a pesquisa e as reservas servidas por mocks: o fluxo com sessão real não
foi testado).
O carrinho (2026-10-20) é o store Pinia `useMarketplaceCartStore` (`marketplace/cartStore.js`), criado com
`createBaseStore` só para usar a persistência do RESAAS (`persist: { include: ['lines'], scope: 'user', ttl: 24 h }`):
sobrevive a um recarregar da página, por utilizador (outro utilizador no mesmo dispositivo não o vê) e o logout
apaga-o (`clearPersistedStates`). Não há recurso da API por trás (as acções CRUD do BaseStore não são usadas; a
reserva é `placeOrders`). Cada linha guarda só o que o carrinho mostra e envia (`cartRow`: oferta, preço, moeda,
stock mostrado, nome/dosagem/apresentação/receita do medicamento, id e nome da farmácia) - nunca as fotos/vídeos
(URLs assinados). `useCart()` mantém a mesma API. Testes: `useMarketplace.spec.js` (campos guardados, recarregar
com o mesmo utilizador, outro utilizador vazio); browser: 2 linhas e quantidades iguais depois de recarregar.
No carrinho a quantidade muda com botões − / + (`useCart().step`, entre 1 e 100 ou o stock
mostrado pela farmácia); remover é o botão vermelho (`negative`).

**Mapa das farmácias.** "Farmácias próximas" mostra só o mapa (Google Maps, chave
`GOOGLE_MAPS_API_KEY` do `.env`, via `quasar.config.js`), com um marcador por farmácia
listada nas `coordinates` da morada principal da sucursal; a janela do marcador é um
cartão (`.pharmacy-pin`, CSS global em `PharmaciesMap.vue` porque vive dentro da InfoWindow
do Google; compacto, 214px, sem scroll - o CSS anula o `overflow`/`max-height` da InfoWindow só para este cartão (`:has(.pharmacy-pin)`) - e botões pequenos de 30px, um por linha, à largura do cartão e nunca mais largos; a distância vai no cabeçalho da InfoWindow (`setHeaderContent`), na linha do botão de fechar; cada texto numa linha, com "..." quando é longo e o texto inteiro no `title`): nome, organização, distância, morada, telefone (`tel:`), horário, selo "Online
reservation"/"In-store only", botão "Medicines at this pharmacy" (com sessão) e "Directions"
(Google Maps, nova janela). Todo o texto entra por `textContent`.

**Rota no mapa.** Com a posição partilhada, o botão do cartão diz "Show route" e desenha a
rota no próprio mapa (Google `DirectionsService` + `DirectionsRenderer`, linha na cor do tema,
sem esconder os nossos pinos). Uma barra no topo do mapa mostra a farmácia, tempo e distância,
alterna carro/a pé e limpa a rota. Sem posição, o botão
diz "Directions" e abre o Google Maps; se o serviço de rotas falhar (API não activa para a
chave, sem rota), também abre o Google Maps. O controlo de ecrã inteiro do Google está
desligado (o nosso "Expand map" faz isso).

*Rota partilhada e seguimento (2026-10-20).* A rota é o estado `useMapRoute()` (`useMarketplace.js`),
criado em `NearbyPharmacies.vue` e passado (`route`) ao mapa da página e ao de ecrã inteiro: abrir ou
fechar o ecrã inteiro mantém a rota e só há um pedido ao Google (cada mapa tem o seu `DirectionsRenderer`
e desenha o mesmo resultado). Enquanto a rota está aberta, `watchPosition` (alta precisão) segue o
dispositivo — só nesse período, nunca guardado nem enviado ao backend; `clear()` pára-o, também ao sair
da página. O ponto azul acompanha-o e o mapa centra-o se sair da vista. Se o utilizador ficar a mais de
`OFF_ROUTE_METERS` (50 m) do traçado — e mais do que a precisão do GPS — a rota é recalculada a partir
de onde está (`isOffRoute`, `distanceToPathMeters`), no máximo uma vez a cada `REROUTE_INTERVAL_MS`
(15 s) para não multiplicar pedidos ao Directions; um recálculo que falhe mantém a rota já desenhada.
Testes: `useMarketplace.spec.js` (distância ao traçado, limiar/precisão/intervalo, recálculo a partir da
posição, falha mantém a rota, `clear` pára o seguimento); browser em Chandkheda: rota → ecrã inteiro
(mesma rota, 1 pedido) → 400 m fora da rota → recalculada (5 min · 2,3 km → 7 min · 2,8 km) → fechar
mantém → limpar pára o seguimento (sem novos pedidos).

A posição do dispositivo, se partilhada, é um ponto azul. Com a posição partilhada, um círculo
de 3 km (`NEARBY_RADIUS_KM`, em `useMarketplace.js`; 3 km ≈ 35–40 min a pé ou uma viagem
curta na cidade — 5 km cobria quase toda a cidade de Maputo) é desenhado à volta dela: as farmácias com `distance_km <= 3`
(`isNearby`, só a distância calculada pelo backend com coordenadas reais) ficam com um pino
maior na cor do tema e por cima; as outras com um pino cinzento menor. A vista enquadra o
círculo e as farmácias próximas (ou todas, se nenhuma estiver no raio) e a página indica
quantas estão no raio. Sem posição, nenhuma é destacada. Farmácias sem
coordenadas nunca são colocadas num ponto inventado: ficam fora do mapa e uma nota
indica quantas. Sem chave ou se o script falhar, a página volta a mostrar a lista em
cartões. Os filtros e "Show more" (mais marcadores) mantêm-se. O botão "Expand map" (canto inferior
esquerdo do mapa) abre o mesmo mapa em ecrã inteiro (`q-dialog maximized` + `s-modal-card
fullscreen flush`, q-bar com fechar); escolher "Medicines at this pharmacy" aí fecha o diálogo
e filtra a pesquisa por essa farmácia. O carregador replica o
de `quasar_resaas/services/googleMaps.js` (mesmo script e callback) porque o pacote
não o exporta; proposta: exportá-lo em `quasar_resaas` e remover a cópia.

Os modais usam `s-modal-card`; confirmações `sDialog`; erros pelo funil de alertas do cliente HTTP.
Cada tentativa leva uma `idempotency_key` nova (`requestKey()`), mantida num retry.

## Migrações

`farmacia/0003_online_orders_counter_lookup` (`OnlineOrder`, `OnlineOrderItem`, `CounterSale`,
`PatientLookup`; não versionada, como as outras do farmacia). Aditiva, sem dados a migrar.
Genérico: `inventory.services.branch_warehouse_for()`, `sales.services.create_sale()` e
`PAYMENT_METHODS` (sem migração).

## Limitações conhecidas (fases 3–5)

- Sem pagamento online nem entrega (não existem no sistema).
- Uma encomenda é servida por um único armazém da farmácia.
- Receitas electrónicas dispensadas pela fila (`dispense()`) não geram `Sale`: a cobrança
  dessas fica fora (a venda ao balcão é para receitas em papel e venda livre).
- A expiração grava-se pelo comando `expire_online_orders`; é preciso agendá-lo (cron).
- As farmácias demo não têm utilizadores; para testar o balcão associe um utilizador.

## Fotos e vídeos dos medicamentos (catálogo)

As fotos e vídeos são do medicamento do **catálogo comum** (âmbito plataforma, escrito pelo
Root), não do produto de cada farmácia: aparecem iguais em todas as farmácias. O
`inventory.Product.imagem`/`ProductMedia` de cada farmácia não é usado no marketplace.

| Peça | Onde |
|---|---|
| Ficheiros = `django_resaas.File` (o modelo de ficheiros da plataforma): cada foto/vídeo é uma linha `File` da Entity/Branch de quem carrega (normalmente o Root), com `model`, `funcionalidade="Photo"`, `chamador="farmacia.catalogue"` e `size`, por isso conta no uso de disco dessa Entity | `farmacia/catalogue_media_service.py` |
| Foto principal: `MedicineCatalogItem.main_photo` (FK `File`, opcional, `SET_NULL`) | `farmacia/models/medicine_catalog_item.py` |
| Galeria: `MedicineCatalogMedia` (TimeModel: `catalog_item` → `media`, `media_file` FK `File` `PROTECT`, `caption`, `position`; ordem `position`, `created_at`; `kind` = `image`/`video` pela extensão) | `farmacia/models/medicine_catalog_media.py` |
| Escrita só por upload, nunca por id (ninguém liga um `File` de outro tenant): `PATCH medicinecatalogitems/{id}/` com `upload_main_photo` (cria o `File`) ou `remove_main_photo: true`; `POST medicinecatalogmedia/` com `upload` + `catalog_item`, `caption`, `position`. `main_photo`/`media_file` são só de leitura e devolvem `{id, url, name, ext, kind, size}`. O ficheiro de um item da galeria não se troca (400): apaga-se e adiciona-se outro | `farmacia/serializers/` |
| CRUD `GET/POST farmacia/medicinecatalogmedia/`, `GET/PATCH/DELETE …/{id}/`, filtro `?catalog_item=<id>` — PROTEGIDO (BaseAPIView, `list/view/add/change/delete_medicinecatalogmedia`; a foto principal com `change_medicinecatalogitem`). Apagar é soft (`deleted_at`) e o `File` fica, para o restore | `farmacia/views/` |
| Validação (`catalogue_media_service.validate_upload`): fotos png/jpg/jpeg/webp até 5 MB e verificadas com Pillow; vídeos mp4/webm/mov até 50 MB (só na galeria); no máximo 10 itens por medicamento (`MAX_MEDIA_PER_ITEM`); sem contexto de tenant não há dono → 400. Nada é gravado quando a validação falha | idem |
| Porque não o endpoint do core: `POST django_resaas/files/` chama `DiskManegarService.freeSpace()`, que o django_resaas não implementa (500); o catálogo cria o `File` ele próprio. A relação usa a classe `File` importada (não `"django_resaas.File"`): `django_resaas.saas.models` não importa `file.py` e o nome ficaria uma relação por resolver | — |
| URLs com token permanente (`permanent_fields_files`): multimédia de produto, não dados de tenant | idem |
| `medicine.image` (URL ou `null`) e `medicine.media` (`[{url, kind, caption}]`) em `GET marketplace/medicines/` e `GET countersales/offers/` (`marketplace_service.photo_urls`, só na página devolvida) | `farmacia/marketplace_service.py` |
| Perfis: Pharmacy Manager e Pharmacist ganham `list/view_medicinecatalogmedia` (leitura); escrever fica com o Root | `farmacia/profiles.py` |
| Migrações em dev: `0004_medicine_media` e `0005_catalogue_files` (troca os campos de ficheiro pelas FKs `File`; sem dados a migrar — o `makemigrations` pede um valor provisório para `media_file`, inofensivo com a tabela vazia) | `farmacia/migrations/` |

Frontend: no catálogo (`list_medicinecatalogitem`, `main_photo` fora do formulário) a acção
"Photos" abre `view_medicine_media/:id` (`MedicineMediaPage.vue`): foto principal (escolher com
`s-file`, guardar/remover), galeria (`s-file` + legenda + posição, `BaseStore.create` envia
multipart), apagar com `sDialog`; botões conforme `User.can(...)`, o backend decide. O store usa `url:
'farmacia/medicinecatalogmedia'` porque a view não segue a convenção `{model}s`.

Na pesquisa (`MedicineSearch.vue`) cada resultado mostra a miniatura (`medicineThumbnail`: a
foto principal, senão a primeira foto da galeria; ícone de play se só houver vídeos; ícone de
medicamento sem nada). Um clique abre `MedicineMediaViewer.vue` (`s-modal-card`), no estilo
de galeria de loja: o item escolhido em grande (vídeo com controlos), miniaturas à esquerda
(em baixo no telemóvel; vídeos com ícone de play; passar o rato ou clicar muda), setas e
teclas ← →, legenda e "n / total". Nas fotos, passar o rato amplia 2,2× no ponto do cursor
(só em ecrãs com rato); as miniaturas de vídeo mostram o primeiro fotograma (`#t=0.1`).
Verificado no browser (Chromium headless, 2026-10-19) montando o componente real na app de `dev`
com um medicamento de exemplo: miniaturas, hover, clique, vídeo a tocar, setas, teclado, ciclo,
lupa, fechar e disposição em telemóvel. A ordem é `medicineMedia()`: principal, depois a galeria.

Problemas: foto/vídeo não aparece → ver `FILE_TOKEN.KEY`/`ENABLE_PERMANENT` e o serviço de
`/media/` do servidor (um vídeo precisa também de pedidos `Range` para avançar); acção
"Photos" não aparece → permissão `list_medicinecatalogmedia` sincronizada (`sync_actions`/
perfis) no grupo do utilizador.

## Fase 6 — segurança, testes, documentação

Coberto por testes: isolamento (outra farmácia não vê nem levanta encomendas; outro comprador
recebe 404; ofertas de outra Branch recusadas ao balcão), permissões (403 sem
`add_countersale` / `lookup_patient_filafarmacia`), sessão obrigatória, idempotência
(encomenda, levantamento, venda), concorrência (dois compradores, balcão vs reserva),
validação, expiração, receita em papel, consentimento activo/expirado/revogado, auditoria,
nenhuma vista do farmacia pública por omissão (`test_access_guard`), traduções pt/es/fr.
Regressão genérica: suítes `inventory` e `sales` passam sem Saúde.

Não validado: build de produção do front (`quasar build`) e teste manual no browser.

## Próximo passo

1. Agendar `manage.py expire_online_orders` (cron) em `dev`.
2. Com autorização do proprietário, no `pro`: instalar o código, `migrate farmacia`
   (0002, 0003), `sync_actions`, perfis; **não** correr o seed em produção.
3. Associar um utilizador de teste a uma farmácia demo para testar balcão e levantamento.
