MENU = "Rh"
ICON = "badge"  # 🔥 RH / colaboradores

SUBMENUS = [
    {
        "icon": "space_dashboard",  # moderno
        "menu": "Dashboard",
        "role": "view_rh_dashboard",
        "route": "view_rh_dashboard",
    },
    {
        "add_role": "add_departamento",
        "add_route": "add_departamento",
        "crud": {"model": "Departamento", "module": "rh"},
        "icon": "apartment",  # 🔥 estrutura organizacional
        "menu": "Departamento",
        "role": "list_departamento",
        "route": "list_departamento",
    },
    {
        "add_role": "add_cargo",
        "add_route": "add_cargo",
        "crud": {"model": "Cargo", "module": "rh"},
        "icon": "work",  # 🔥 cargo / função
        "menu": "Cargo",
        "role": "list_cargo",
        "route": "list_cargo",
    },
    {
        "add_role": "add_funcionario",
        "add_route": "add_funcionario",
        "crud": {"model": "Funcionario", "module": "rh"},
        "icon": "badge",  # 🔥 funcionário
        "menu": "Funcionario",
        "role": "list_funcionario",
        "route": "list_funcionario",
    },
    {
        "add_role": "add_contrato",
        "add_route": "add_contrato",
        "crud": {"model": "Contrato", "module": "rh"},
        "icon": "description",  # 🔥 contrato/documento
        "menu": "Contrato",
        "role": "list_contrato",
        "route": "list_contrato",
    },
    {
        "add_role": "add_funcionariocargo",
        "add_route": "add_funcionariocargo",
        "icon": "account_tree",  # 🔥 relação estrutura
        "menu": "Funcionariocargo",
        "role": "list_funcionariocargo",
        "route": "list_funcionariocargo",
    },
    {
        "add_role": "add_funcionariocargo",
        "add_route": "add_funcionariocargo",
        "icon": "link",  # 🔥 ligação entre entitys
        "menu": "FuncionarioCargo",
        "role": "list_funcionariocargo",
        "route": "list_funcionariocargo",
    },
]
