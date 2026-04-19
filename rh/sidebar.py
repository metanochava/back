MENU = "Rh"
ICON = "menu"

SUBMENUS = [
    {
        "icon": "dashboard",
        "menu": "Dashboard",
        "role": "view_rh_dashboard",
        "rota": "view_rh_dashboard",
    },
    {
        "add_role": "add_departamento",
        "add_rota": "add_departamento",
        "crud": {"model": "Departamento", "module": "rh"},
        "icon": "home",
        "menu": "Departamento",
        "role": "list_departamento",
        "rota": "list_departamento",
    },
    {
        "add_role": "add_cargo",
        "add_rota": "add_cargo",
        "crud": {"model": "Cargo", "module": "rh"},
        "icon": "home",
        "menu": "Cargo",
        "role": "list_cargo",
        "rota": "list_cargo",
    },
    {
        "add_role": "add_funcionario",
        "add_rota": "add_funcionario",
        "crud": {"model": "Funcionario", "module": "rh"},
        "icon": "home",
        "menu": "Funcionario",
        "role": "list_funcionario",
        "rota": "list_funcionario",
    },
    {
        "add_role": "add_contrato",
        "add_rota": "add_contrato",
        "crud": {"model": "Contrato", "module": "rh"},
        "icon": "home",
        "menu": "Contrato",
        "role": "list_contrato",
        "rota": "list_contrato",
    },
    {
        "add_role": "add_funcionariocargo",
        "add_rota": "add_funcionariocargo",
        "icon": "list",
        "menu": "Funcionariocargo",
        "role": "list_funcionariocargo",
        "rota": "list_funcionariocargo",
    },
    {
        "add_role": "add_funcionariocargo",
        "add_rota": "add_funcionariocargo",
        "icon": "list",
        "menu": "FuncionarioCargo",
        "role": "list_funcionariocargo",
        "rota": "list_funcionariocargo",
    },
]
