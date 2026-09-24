# Patient Longitudinal Identity, Health & Pharmacy — Architecture Analysis

> See also: [Health operational dashboards](health-operational-dashboards.md) (Reception, Nursing, Doctor; waiting time).

> Status: **análise apenas — nenhuma implementação feita.** Aprovação
> explícita necessária antes de qualquer Phase abaixo arrancar.
>
> Âmbito real: `/var/www/dev/back` (Django, apps `saude`, `farmacia`,
> `inventory`, `sales`, consome `django_resaas` via pip) +
> `/var/www/dev/front` (Quasar, consome `quasar_resaas`). Uma análise
> anterior enganou-se ao inspeccionar só `/var/www/lib` (as bibliotecas
> genéricas) e concluiu — incorrectamente — que `saude`/`farmacia`/
> `inventory`/`sales` não existiam. Foi apagada; esta é a versão
> correcta, baseada no código real e a correr em produção/dev.

---

## 0. Nota operacional

`back` tinha, no momento desta análise, alterações locais **não
commitadas** e não feitas por esta análise: `Makefile`,
`inventory/services.py`, `saas/settings.py`, `sales/sidebar.py`,
`saude/apps.py`. Foram lidas como estado actual (working tree), mas
não tocadas. `saude/apps.py` em particular já tem uma edição em curso
(comentário `🔥 FIX` no `create_saude_groups`) — não assumir que o que
está descrito aqui é o HEAD commitado.

**Version drift**: `pip show django_resaas` reporta `0.0.468`, mas
existe um `.dist-info` de `0.0.479` no mesmo venv
(`back/venv/lib/python3.10/site-packages/`). O venv está inconsistente
— não é claro qual versão do pacote está de facto a ser importada em
runtime. Isto é um risco operacional a resolver (reinstalar o venv)
antes de depender de qualquer capability nova de `django_resaas` nesta
iniciativa; não corrigido aqui por estar fora do âmbito "análise
apenas".

---

## 1. Current State Analysis

### 1.1 RESAAS core (`django_resaas`, instalado via pip em `back/venv`)

`MY_APPS` real (`back/saas/settings.py`): `django_resaas.engine`,
`django_resaas.hr`, `django_resaas.notifications` + `saude`,
`farmacia`, `inventory`, `sales` (apps locais do projecto `back`, não
do pacote `django_resaas`). `AUTH_USER_MODEL = 'django_resaas.User'`.

Isto confirma a separação exigida pelo CLAUDE.md: `saude`/`farmacia`/
`inventory`/`sales` são aplicações verticais **fora** de
`django_resaas`, tal como o pedido do utilizador exige — já está
correcto, não é preciso mover nada.

### 1.2 Person model (`django_resaas.engine.models.person.Person`)

- Herda de `TimeModel`, **não** de `BaseModel` → confirmado: `Person`
  não tem `entity`/`branch`. É identidade global, tenant-agnostic, por
  desenho.
- Campos: `name`, `surname`, `full_name` (auto-gerado), `gender`,
  `date_of_birth`, `nationality`, `email` (**unique globalmente**),
  `phone`, `alternative_phone`, `address` (FK), `documents`
  (`GenericRelation` para `django_resaas.Document`), `user`
  (OneToOne, opcional).
- **Sem campo de foto.** `documents` (GenericRelation genérica) é o
  mecanismo existente para anexar ficheiros a uma Person — inclui
  potencialmente uma foto de perfil, mas não há hoje nenhum "purpose"
  dedicado testado para isso (ver 1.7).
- `email` único globalmente é um sinal de matching forte já disponível
  de graça — duas Entities não podem criar duas Persons com o mesmo
  email.

### 1.3 Tenant model (Entity/Branch) e request context

Confirmado indirectamente via uso consistente em todos os módulos
(`entity_id`, `branch_id` como colunas obrigatórias em todo o
`BaseModel`, `EntityApp` para activação por módulo, `EntityType` para
templates de grupo). Não foi necessário reabrir `BaseModel`/
`BaseAPIView` nesta passagem — o comportamento observado nos 4 apps
(`saude`, `farmacia`, `inventory`, `sales`) é 100% consistente com o
descrito no CLAUDE.md §6–§11: filtragem obrigatória por
`entity_id`/`branch_id`, sem excepção observada.

### 1.4 `saude` — estado real do domínio clínico

Modelos já existentes e usados em produção (nomes portugueses
legados, exactamente os que o CLAUDE.md §28 pede para inspeccionar
antes de mexer): `Paciente`, `Consulta`, `Medico`,
`PedidoExameMedico`, `ItemPedidoExameMedico`, `ResultadoExameMedico`,
`TipoExameMedico`/`ClasseExameMedico`/`ParametroExameMedico`,
`ReceitaMedica`/`ItemReceita`, `Medicamento`, `Internamento`,
`Cirurgia`, `EpisodioClinico`, `ObservacaoClinica`, `DadoVital`,
`Imunizacao`/`Vacina`, `AlergiaCorrente`, `AlergiaMedicamentosa`,
`DoencaCorrente`, `Diagnostico`, `GuiaTransferencia`, `Agenda`/
`HorarioMedico`, `Consultorio`, `AtestadoMedico`, `RelatorioMedico`,
`Procedimento`.

**`Paciente` (achado central):**

```python
class Paciente(BaseModel):
    nid = models.CharField(max_length=50, unique=True)
    person = models.ForeignKey('django_resaas.Person', related_name='pacientes')
    profissao, religiao, person_a_contactar, numero_a_contactar = ...

    class Meta:
        unique_together = ("person", "branch")
```

- **Já correcto**: `Paciente` não duplica identidade — usa `person`
  como FK para `django_resaas.Person`. Nenhuma violação do CLAUDE.md
  §9/§12 aqui.
- **`Paciente` é `BaseModel`** → tem `entity`/`branch` próprios. E
  `unique_together = (person, branch)` → **uma mesma Person pode ter
  múltiplos registos `Paciente` distintos, um por Branch** (e por
  Entity, transitivamente). Cada um com o seu próprio `nid`,
  `profissao`, etc.
- **Isto é exactamente o gap #12/#13 do pedido do utilizador,
  materializado no código real**: hoje, se um paciente for atendido no
  Hospital A e depois no Hospital B, nascem **dois `Paciente` row
  completamente independentes**, ligados apenas pelo `person`
  partilhado — sem qualquer identificador cruzado, sem histórico
  visível entre eles, sem noção de "mesmo paciente, proveniências
  diferentes". `nid` é único globalmente (`unique=True` na coluna,
  sem `unique_together` com entity) — o que sugere que a intenção
  original já era ID nacional único, mas não há hoje nenhum mecanismo
  de *matching* que o use para sugerir "este `nid` já existe noutra
  Entity, queres ligar em vez de duplicar?".
- `Consulta` liga a `saude.Paciente` (não a `Person` directamente) —
  ou seja, o histórico clínico (`Consulta`, e tudo o resto que
  penduram de `Consulta`) está scoped ao `Paciente` de uma Branch
  específica, não à Person. Confirma que hoje **não existe
  timeline cruzada entre Entities** nem por acidente.

### 1.5 `farmacia` — estado real (Health↔Pharmacy)

Já implementado com um desenho de integração deliberado e
bem-documentado no próprio código (`farmacia/services.py`,
docstring):

```
farmacia depende de saude, inventory e sales, nunca o contrário:
  - saude:      FK direta a ReceitaMedica/ItemReceita/Medicamento
                 (farmacia não existe sem saude activo).
  - inventory:  só inventory.services (nunca inventory.models).
  - sales:      só sales.services (nunca sales.models).
```

- **`FilaFarmacia`**: workflow explícito (`pendente → em_revisao →
  aprovada/rejeitada → dispensada_parcial → dispensada/cancelada`),
  FK directa a `saude.ReceitaMedica` — decisão consciente, não uma
  omissão (`saude` é um pré-requisito rígido de `farmacia`, ao
  contrário de `inventory`/`sales` que são opcionais).
  `unique_together = (entity, receita)`.
- **`Dispensa`/`ItemDispensa`**: usam **referências soltas por UUID**
  (`warehouse_id`, `sale_id`, `produto_id`, `stock_movement_id`) em
  vez de FK para `inventory`/`sales` — exactamente o padrão pedido no
  §29 do pedido do utilizador ("Inventory não precisa conhecer
  Patient... através de referências públicas"), já implementado, só
  que na direcção `farmacia → inventory/sales`.
- `farmacia/services.dispense()`: `transaction.atomic()`, valida
  estado antes de agir, degrada graciosamente se `inventory` não
  estiver activo para a Entity (`inventory_module_active(entity_id)`),
  cria `Dispensa`+`ItemDispensa`, e só move stock via
  `inventory_services.commit_dispensation_movements(...)` — nunca
  escreve `StockMovement` directamente.
- **`farmacia/listeners.py`**: escuta `saude.prescription.created` via
  `EventDispatcher` (import local de `saude.models.receitamedica`
  só dentro do handler, evita import prematuro no arranque da app) —
  desacoplamento correcto, `farmacia` não importa `saude` a nível de
  módulo para se subscrever.
- **Conclusão: a integração Health↔Pharmacy já existe e já segue os
  princípios do pedido do utilizador** (eventos para o
  desencadeamento, FK directa só onde documentadamente necessário,
  UUID solto para tudo o resto, idempotência via `get_or_create` no
  enqueue). Não há violação a corrigir aqui — o trabalho novo é
  **estender**, não **consertar**.

### 1.6 `inventory` / `sales` — confirmação do isolamento tenant

`inventory/services.py` é o único ponto de escrita de stock
(`apply_movement`, sempre dentro de `transaction.atomic()` +
`select_for_update()` na linha de `StockItem`), com ledger
append-only (nunca apaga `StockMovement`, reversões criam novos
movimentos de sentido oposto). `sales/services.py` só chama
`inventory.services` (nunca `inventory.models`), tem máquina de
estados explícita (`ALLOWED_TRANSITIONS`) e degrada graciosamente
quando `inventory` não está activo.

Os 3 ficheiros de teste de `inventory` e 4 de `sales` já cobrem, e
passam hoje, exactamente os requisitos do §21–§23/§49 do pedido do
utilizador: isolamento por Entity em list/retrieve directo por ID,
403 quando módulo não activo, dashboard agregado nunca vaza dados de
outra Entity. **Nenhum destes testes precisa de ser reinventado** —
qualquer teste novo de Patient/Health/Pharmacy cross-entity deve
seguir o padrão de `testutils.tenant.bootstrap_tenant(...)` já usado
neles.

### 1.7 Schema 1.0 / Quasar — upload e câmara

- `quasar_resaas/components/engine/UploadComponent.vue` — componente
  genérico de upload de ficheiro já existente (usado por `saude` em
  `UploadDialog.vue`, ex.: anexar resultado de exame).
- `front/src/components/CameraScannerDialog.vue` — **já existe uma
  captura de câmara funcional**, mas orientada a leitura de
  código de barras/QR (usa `html5-qrcode`, `facingMode: 'environment'`
  fixo, sem selector de múltiplas câmaras, sem captura de fotografia
  estática). Padrões reutilizáveis dele: tratamento de erro
  (`NotAllowedError`, `NotFoundError`, contexto não-seguro/HTTPS),
  ciclo de vida (`start`/`stop` em `watch` do `modelValue`, cleanup em
  `onBeforeUnmount`), suporte a torch/flash.
- **Não existe** nenhum componente de captura de fotografia (retrato/
  identificação) com preview, retake, ou selector de câmara via
  `enumerateDevices()`/`deviceId`. Gap genuíno confirmado.
- `saude`/`Paciente` não têm hoje nenhum campo de foto no formulário
  (`PacienteSEPage.vue` não referencia foto/avatar/imagem do
  paciente).

---

## 2. Dependency Analysis

Grafo de dependências **real**, confirmado por leitura directa dos
imports:

```
django_resaas (engine, hr, notifications)
        ▲              ▲            ▲
        │              │            │
     saude          farmacia     inventory ◄── sales
        ▲              │              ▲          │
        └──────────────┘              └──────────┘
     (FK directa,               (só via *.services,
      documentada,               nunca *.models —
      farmacia exige              já correcto)
      saude activo)
```

- `django_resaas` não importa nenhum dos 4 apps verticais — confirmado
  (nenhuma referência inversa encontrada).
- `farmacia → saude`: FK directa e intencional (não um "gap").
- `farmacia → inventory`, `farmacia → sales`, `sales → inventory`:
  só via camada `services`, nunca `models` — já correcto.
- `inventory` e `sales` **não conhecem** `saude` nem `farmacia` — zero
  referências encontradas. Correcto e a preservar.

**Nenhuma violação de dependência a corrigir.** O grafo real já
corresponde ao grafo pedido pelo utilizador nas secções 1–2 do pedido
original.

---

## 3. Ownership Matrix

| Conceito | Owner actual | Confirmado? |
|---|---|---|
| Person | `django_resaas` (engine) | ✅ existe |
| User / Employee | `django_resaas` / `django_resaas.hr` | ✅ existe |
| Paciente (Patient) | `saude` | ✅ existe, por Branch |
| Consulta / Diagnóstico / Receita / Exames | `saude` | ✅ existe |
| FilaFarmacia / Dispensa (workflow) | `farmacia` | ✅ existe |
| Product / Warehouse / StockItem / StockMovement | `inventory` | ✅ existe |
| Sale / SaleItem / Payment | `sales` | ✅ existe |
| **Patient cross-Entity identity** | — | ❌ não existe |
| **Patient Identifier (multi-issuer)** | — | ❌ não existe (só `nid` único plano) |
| **Consent / cross-entity grant** | — | ❌ não existe |
| **Break-glass / emergency access** | — | ❌ não existe |
| **Patient Photo** | — | ❌ não existe |
| **Camera multi-device capture** | — | ❌ não existe (só QR/barcode) |
| Cross-entity opt-in em `BaseAPIView` (`cross_branch_actions`/`cross_entity_actions` do CLAUDE.md §10) | — | ⚠️ não verificado nesta passagem — **assumir não confirmado**, não usar sem reler `BaseAPIView` antes da Phase 0 |

---

## 4. Gap Analysis

| Capability | Actual | Gap | Acção | Owner | Tenant scope | Prioridade |
|---|---|---|---|---|---|---|
| Person↔Patient link | `Paciente.person` FK, sem duplicação | Nenhum | — | saude | Entity/Branch (Paciente) | — |
| Patient multi-Branch continuity | `unique_together(person, branch)` → 1 Paciente por Branch, sem ligação visível entre eles | Falta noção de "mesma pessoa, registos clínicos em Branches/Entities diferentes" | CREATE (novo modelo fino de agregação, ver §6) | saude | cross-branch/cross-entity, opt-in | Alta |
| Patient Identifier múltiplo | Só `nid` (único, plano) | Sem tipo/emissor/validade | EXTEND (`nid` fica, adiciona `PatientIdentifier` para os restantes tipos) | saude | Entity/Branch | Média |
| Patient matching antes de criar | Inexistente — `nid unique=True` só rejeita duplicado exacto, sem sugestão | Sem serviço de matching | CREATE (`PatientMatchingService`) | saude | consulta cross-entity limitada a campos de matching | Alta |
| Patient merge | Inexistente | Sem estratégia de duplicado | CREATE (`PatientMergeService`), fase posterior | saude | Entity/Branch | Baixa (não bloqueia Phase 1) |
| Cross-entity consent/grant | Inexistente | Sem mecanismo de partilha autorizada | CREATE (`ConsentGrant`) | saude | explícito, por scope | Alta |
| Break-glass | Inexistente | Sem acesso de emergência auditado | CREATE (`EmergencyAccess`) | saude | explícito, temporário, auditado | Média |
| Prescription↔Pharmacy contract | Já existe (`ReceitaMedica` + evento + FK) | Nenhum | REUSE | saude/farmacia | já correcto | — |
| Inventory/Sales integration da dispensação | Já existe (`inventory.services`, UUID solto) | Nenhum | REUSE | inventory/sales/farmacia | já correcto | — |
| Batch/lote em Inventory | `ItemDispensa.lote` é `CharField` livre — comentário no código admite "inventory ainda não tem rastreio de lote nativo" | Sem `Batch`/expiry/FEFO nativo em `inventory` | EXTEND `inventory` (genérico, útil fora de Health — CLAUDE.md §46) | inventory | Entity/Branch | Média |
| Patient photo | Inexistente | Sem campo/foto de identificação | EXTEND `Person` ou `Document` (ver §6) | django_resaas (campo) / saude (uso) | n/a (Person é global) | Alta |
| Camera capture genérica multi-device | Só QR/barcode (`CameraScannerDialog.vue`) | Sem captura de fotografia com selector de câmara | CREATE componente Quasar genérico | quasar_resaas | n/a (frontend) | Alta |
| Audit de acesso cross-entity | Inexistente | Sem trilha de quem acedeu a quê, de que Entity | CREATE, via `EventDispatcher` existente | saude | por evento | Alta |
| `BaseAPIView` cross-entity opt-in | Não confirmado nesta passagem | A confirmar antes de Phase 0 | Reler `BaseAPIView` antes de decidir REUSE/CREATE | django_resaas | core | Bloqueante para tudo cross-entity |

---

## 5. Proposed Architecture

```
                         django_resaas (core, inalterado)
                    engine / hr / notifications / inventory* / sales*
                                    ▲
        ┌───────────────────────────┼────────────────────────────┐
        │                           │                            │
      saude                    inventory                       sales
   (Paciente, Consulta,        (Product, Stock,               (Sale, Payment)
    Receita, ...)               StockMovement)                     ▲
        │  ▲                        ▲                               │
        │  │ eventos                │ *.services                    │
        │  └────── farmacia ────────┴───────────────────────────────┘
        │        (FilaFarmacia,
        │         Dispensa)
        │
        ├── NOVO: PatientIdentifier   (EXTEND saude)
        ├── NOVO: ConsentGrant         (CREATE saude)
        ├── NOVO: EmergencyAccess      (CREATE saude)
        └── NOVO: Patient photo        (EXTEND django_resaas.Person +
                                         quasar_resaas SImageCapture)
```

*`inventory`/`sales` aparecem sob `django_resaas` no diagrama por
serem também apps genéricas reutilizáveis (não domínio de Health), mas
continuam a viver fisicamente em `back/`, não em `django_resaas` — a
separação física actual (pip package vs. apps locais do projecto) já
está correcta e não deve mudar.

Cada novo item classificado:

- **`PatientIdentifier`** → CREATE (EXTEND conceptualmente `saude`,
  novo modelo).
- **`ConsentGrant`** → CREATE.
- **`EmergencyAccess`** → CREATE.
- **Patient photo** → EXTEND `Person` (novo campo/relação) + EXTEND
  `Document` (purpose dedicado) — a decidir em Phase 1 qual dos dois
  (ver riscos, §17).
- **`SImageCapture`** (Quasar) → CREATE, mas reutilizando o padrão de
  ciclo-de-vida/erro já validado em `CameraScannerDialog.vue`.
- **Cross-entity `BaseAPIView` opt-in** → estado a confirmar; se não
  existir, CREATE mínimo em `django_resaas.engine` (core, genérico,
  100% backward-compatible por defeito `[]`).

---

## 6. Proposed Models (novos, todos fora de `django_resaas`)

Apenas onde a Gap Analysis (§4) confirma ausência real:

```python
# saude/models/patient_identifier.py
class PatientIdentifier(BaseModel):
    paciente = models.ForeignKey('saude.Paciente', related_name='identifiers')
    identifier_type = models.CharField(...)   # nacional, seguro, legado, ...
    identifier = models.CharField(...)
    issuer = models.CharField(..., null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
```

```python
# saude/models/consent_grant.py
class ConsentGrant(BaseModel):
    person = models.ForeignKey('django_resaas.Person', related_name='consent_grants')
    source_entity = models.ForeignKey('django_resaas.Entity', related_name='+')
    target_entity = models.ForeignKey('django_resaas.Entity', related_name='+')
    scope = models.JSONField()  # ex.: ["allergies", "medications", "prescriptions"]
    reason = models.TextField(null=True, blank=True)
    granted_by = models.ForeignKey('django_resaas.User', related_name='+')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(choices=[("active","Active"),("revoked","Revoked"),("expired","Expired")])
```

```python
# saude/models/emergency_access.py
class EmergencyAccess(BaseModel):
    person = models.ForeignKey('django_resaas.Person', related_name='emergency_accesses')
    accessed_by = models.ForeignKey('django_resaas.User', related_name='+')
    reason = models.TextField()
    scope = models.JSONField()
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey('django_resaas.User', null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
```

Note: `Patient` continua a ser `saude.Paciente` — **não** renomeado,
**não** substituído. `nid` mantém-se. Nenhum destes novos modelos
altera o schema de `Paciente`.

---

## 7. Proposed Services / Contracts

- `saude.services.PatientMatchingService.find_candidates(nid=None,
  email=None, phone=None, name=None, date_of_birth=None) ->
  list[MatchCandidate]` — pesquisa por `Person` (campos globais) +
  `PatientIdentifier` (cross-entity), nunca cria automaticamente.
- `saude.services.PatientAccessService.get_authorized_scope(person,
  requesting_entity) -> set[str]` — consulta `ConsentGrant`
  activos + `EmergencyAccess` em curso; usado por qualquer view que
  precise decidir o que mostrar de fora da Entity actual.
- `saude.services.ConsentService.grant(...)`,
  `.revoke(...)` — únicos pontos de escrita de `ConsentGrant`.
- Reutilizar tal e qual (nenhuma mudança): `farmacia.services`,
  `inventory.services`, `sales.services`, `EventDispatcher`.

---

## 8. Proposed Events

Seguindo a convenção já em uso (`farmacia.worklist.enqueued`,
`farmacia.prescription.reviewed`, `farmacia.dispensation.created`,
`farmacia.dispensation.completed`, `saude.prescription.created`):

```
patient.registered
patient.matched
patient.merged
patient.record.shared          (ConsentGrant criado)
patient.record.access_revoked  (ConsentGrant revogado/expirado)
patient.record.emergency_accessed
```

---

## 9. Proposed Permissions (funcionais, seguindo a convenção real de
`@resaas_action`/`ACTION_PERMISSIONS` já usada em `farmacia/signals.py`)

```
saude.view_patient_cross_entity
saude.grant_patient_consent
saude.revoke_patient_consent
saude.perform_emergency_access
saude.review_emergency_access
saude.merge_patient
```

Nunca checks por nome de grupo — os grupos clínicos já existentes em
`saude/apps.py` (`create_saude_groups`: "Médico Geral", "Enfermeiro",
etc.) continuam a ser apenas templates de atribuição, não pontos de
decisão de autorização.

---

## 10. Proposed API/Actions

- `@resaas_action` em `PacienteViewSet`: `request_cross_entity_access`,
  `grant_consent`, `revoke_consent` — mesmo padrão de acções
  explícitas já usado por `farmacia` (`revisar_filafarmacia`,
  `dispensar_filafarmacia`, `concluir_filafarmacia`).
- Endpoint de matching: acção customizada `search_candidates` no
  `PacienteViewSet` (não um `list` genérico) — evita expor pesquisa
  ampla de Person entre Entities via CRUD genérico.

---

## 11. Proposed Quasar Changes

- Novo componente `quasar_resaas/components/engine/SImageCapture.vue`
  (convenção `s-*` desta base de código): upload OU câmara, com
  `navigator.mediaDevices.enumerateDevices()` para listar
  `videoinput` e permitir escolha de `deviceId`, preview + retake,
  reutilizando o tratamento de erro de `CameraScannerDialog.vue`
  (`NotAllowedError`/`NotFoundError`/contexto não-seguro). MVP: sem
  crop/rotate — proposto como fase futura, não bloqueante.
- `PacienteSEPage.vue` ganha o campo de foto usando este componente.
- Novo `PatientTimelinePage.vue` em `saude` (ou secção dentro de
  `PacienteVPage.vue`) para mostrar eventos autorizados de outras
  Entities, com badge de proveniência (Entity/Branch de origem) —
  nunca misturado visualmente com dados da Entity actual sem essa
  etiqueta.

---

## 12. Proposed Schema 1.0 Changes

Nenhuma mudança estrutural ao Schema 1.0 necessária — `photo` pode ser
descrito como um campo de tipo `file`/`image` já suportado, com um
atributo adicional opcional `capture: true` para o frontend saber que
deve oferecer `SImageCapture` em vez do `UploadComponent` genérico.
Backward-compatible: campo ausente ⇒ comportamento actual inalterado.

---

## 13. Migration Impact

- `saude`: 1 migration nova (`PatientIdentifier`, `ConsentGrant`,
  `EmergencyAccess`) — todos aditivos, nenhuma alteração a `Paciente`,
  `Consulta` ou qualquer tabela existente.
- `django_resaas`: só se a foto for adicionada directamente a
  `Person` (1 coluna nullable) — a decidir em Phase 1 (ver §17); a
  alternativa (usar `Document` com `purpose='patient_photo'`) exige
  **zero migration**.
- `inventory`: sem migration nesta iniciativa (Batch/FEFO fica para
  gap futuro, não bloqueante — ver §4).

---

## 14. Backward Compatibility Impact

Nenhuma. `Paciente.nid`, `unique_together(person, branch)`, todas as
FKs existentes de `Consulta`/`PedidoExameMedico`/`ReceitaMedica`
mantêm-se exactamente como estão. As novas capabilities são
estritamente aditivas e opt-in (uma Entity sem `ConsentGrant` nenhum
continua a comportar-se exactamente como hoje: isolamento total).

---

## 15. Test Strategy

Reutilizar `testutils.tenant.bootstrap_tenant(...)` (já usado pelos 7
ficheiros de teste de `inventory`/`sales`). Testes obrigatórios novos,
em `saude/tests/`:

```
Entity A não acede a Inventory da Entity B (já coberto, inventory/tests/test_tenant_isolation.py — reconfirmar sem alteração)
Entity A não acede a Sales da Entity B (já coberto, sales/tests/test_tenant_isolation.py — idem)
Entity A não vê Paciente/Consulta da Entity B por omissão
Mesma Person em 2 Branches não expõe cross-branch sem ConsentGrant
ConsentGrant activo expõe só o scope concedido, nada mais
ConsentGrant revogado deixa de funcionar imediatamente
ConsentGrant expirado (valid_until passado) deixa de funcionar
EmergencyAccess exige permission + reason, fica registado em evento
Patient matching nunca cria Paciente automaticamente por match ambíguo
Merge de Paciente preserva Consulta/Receita históricas (sem perda de FK)
Dispensação de receita "externa" usa inventory/sales da Entity ACTUAL, nunca da Entity de origem da receita (regressão sobre farmacia/services.dispense, já parcialmente coberta pela ausência de FK directa a inventory/sales)
```

---

## 16. Implementation Phases (revisto após inspeccionar o repositório real)

```
Phase 0 — Pré-requisito
  Confirmar/implementar o mecanismo opt-in cross_branch_actions/
  cross_entity_actions no BaseAPIView (django_resaas). Sem isto,
  nenhuma Phase seguinte que exponha dados cross-entity é segura.

Phase 1 — Patient Identifier + Matching (read-only)
  PatientIdentifier, PatientMatchingService (sugestão, sem merge
  automático), endpoint search_candidates. Não altera Paciente
  existente.

Phase 2 — Consent + Emergency Access + Audit
  ConsentGrant, EmergencyAccess, eventos patient.record.*,
  PatientAccessService. Ainda sem timeline visual.

Phase 3 — Patient Photo + Camera capture
  SImageCapture (Quasar), campo/Document em Person, uso em
  PacienteSEPage.

Phase 4 — Patient Timeline (leitura autorizada cross-entity)
  Agregação de Consulta/Receita/Exames através de ConsentGrant/
  EmergencyAccess, com proveniência sempre visível.

Phase 5 — Patient Merge
  PatientMergeService, transacional, auditado. Última fase por ser a
  mais arriscada (irreversibilidade parcial).
```

Não incluído nesta iniciativa (fora de âmbito, gap identificado mas
de prioridade menor): Batch/FEFO nativo em `inventory` (§4).

---

## 17. Risks and Unresolved Architectural Decisions

1. **`BaseAPIView` cross-entity opt-in — estado real não confirmado
   nesta passagem.** Antes de Phase 0, reler
   `django_resaas.engine.core.base.views` (ou equivalente) para
   confirmar se `cross_branch_actions`/`cross_entity_actions` já
   existe, parcialmente ou não existe. Esta análise assume "a
   confirmar", não "não existe" — não repetir o erro da passagem
   anterior de afirmar ausência sem verificar directamente o ficheiro.
2. **Venv com versões inconsistentes de `django_resaas`** (pip
   metadata `0.0.468` vs dist-info `0.0.479`) — recomienda-se
   reinstalar o venv (`pip install --force-reinstall`) antes de
   começar Phase 0, para garantir que qualquer extensão a
   `BaseAPIView` feita em `/var/www/lib/django_resaas` chega
   efectivamente a `back`.
3. **Onde vive a foto: `Person.photo` (novo campo) vs. `Document`
   (purpose dedicado)?** `Person` é global (sem entity/branch) — uma
   coluna de foto aí serve automaticamente Employee e Patient ao
   mesmo tempo, sem duplicação, mas acopla um conceito
   "identificação visual" ao core. `Document` já existe e já está
   ligado a `Person` via `GenericRelation`, custa zero migration, mas
   obriga a uma convenção de `purpose` e uma query extra para achar
   "a" foto de perfil. Recomendação: `Document` com
   `purpose='profile_photo'` — evita migration em `django_resaas` e
   é mais consistente com "não adicionar conceitos ao core para
   facilitar Health" (CLAUDE.md §4). **Decisão pendente de
   aprovação explícita.**
4. **`nid` já é `unique=True` sem scope de entity** — na prática já
   impede duas Entities de criarem `Paciente` com o mesmo `nid`
   (lançaria `IntegrityError`), o que sugere que a intenção original
   já era usá-lo como identificador nacional único. Isto facilita o
   matching (não é preciso migrar dados), mas significa que hoje, se
   duas Entities *tentassem* registar a mesma pessoa com o mesmo
   `nid`, a segunda falharia com erro de integridade em vez de
   accionar o fluxo de matching/sugestão — comportamento a
   substituir explicitamente na Phase 1 (capturar o
   `IntegrityError`/pré-validar e oferecer o fluxo de matching em vez
   de deixar rebentar).
5. **`ItemDispensa.lote` é texto livre**, não uma FK a um `Batch` de
   `inventory` — rastreabilidade de lote para recall (§29 do pedido
   original) não é possível hoje de forma fiável. Fora do âmbito
   desta iniciativa (é um gap de `inventory`, não de Patient/Health/
   Pharmacy per se) mas relevante se um recall de medicamento for
   pedido no futuro.
6. **`front`/`back` são repositórios git próprios**, distintos de
   `django_resaas`/`quasar_resaas` (`/var/www/lib`). Qualquer extensão
   a `BaseAPIView`/`Person`/componentes Quasar genéricos tem de ser
   feita em `/var/www/lib` e só chega a `/var/www/dev` através do
   pipeline de release + reinstalação de dependências — confirmar
   este fluxo de deploy antes de Phase 0 para não haver expectativa
   de que uma alteração em `/var/www/lib` apareça instantaneamente em
   `/var/www/dev`.
