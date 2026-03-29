
MENU = "Rh"
ICON = "menu"
SUBMENUS = [
    {
        "menu": "Dashboard",
        "icon": "dashboard",
        "role": "view_rh_dashboard",
        "rota": "view_rh_dashboard",
    },   
    {
        "menu": "Departamento",
        "icon": "home",
        "role": "list_departamento",
        "rota": "list_departamento",
        "add_role": "add_departamento",
        "add_rota": "add_departamento",
        'crud': { 'module': 'rh', 'model': 'Departamento' }
    },   
    {
        "menu": "Cargo",
        "icon": "home",
        "role": "list_cargo",
        "rota": "list_cargo",
        "add_role": "add_cargo",
        "add_rota": "add_cargo",
        'crud': { 'module': 'rh', 'model': 'Cargo' }
    },   
    {
        "menu": "Funcionario",
        "icon": "home",
        "role": "list_funcionario",
        "rota": "list_funcionario",
        "add_role": "add_funcionario",
        "add_rota": "add_funcionario",
        'crud': { 'module': 'rh', 'model': 'Funcionario' }
    },   
    {
        "menu": "Contrato",
        "icon": "home",
        "role": "list_contrato",
        "rota": "list_contrato",
        "add_role": "add_contrato",
        "add_rota": "add_contrato",
        'crud': { 'module': 'rh', 'model': 'Contrato' }
    }, 
]
