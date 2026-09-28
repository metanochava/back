"""The standard exam catalogue seeded by `manage.py seed_exam_catalogue`
(saude/services/exam_catalogue_service.py).

Structure (TipoExameMedico -> ClasseExameMedico -> ExameMedico -> ExamParameter)
follows the usual international organisation of a clinical laboratory and of
imaging/functional exams. Names, units and choices are data of the Entity's
catalogue (shown as-is on request and result screens), written in Portuguese
as used in Mozambique; the laboratory may rename, deactivate or extend them.

Units are the conventional ones on most analysers; where a unit depends on the
assay (troponin, D-dimer, ...) the laboratory adjusts it to its method.

NO REFERENCE RANGES and no critical limits here: reference intervals depend on
the method, the analyser and the population and must be verified by each
laboratory (CLSI EP28 / ISO 15189). They are laboratory configuration
(ExamReferenceRange) - see docs/architecture/health-operational-dashboards.md.

Codes: `code` of a parameter is its stable technical key (history and
evolution follow it); `codigo` of an exam is this catalogue's internal code
(not a LOINC code - terminology mappings are future work).
"""


def dec(code, name, unit, places=1, required=True):
    return {"code": code, "name": name, "data_type": "decimal", "unit": unit,
            "decimal_places": places, "required": required}


def num(code, name, unit, required=True):
    return {"code": code, "name": name, "data_type": "integer", "unit": unit, "required": required}


def txt(code, name, required=True):
    return {"code": code, "name": name, "data_type": "text", "required": required}


def opt(code, name, choices, required=True):
    return {"code": code, "name": name, "data_type": "choice", "choices": list(choices), "required": required}


def exam(codigo, nome, params, amostra=None, prazo_horas=None, preparacao=None, descricao=None):
    return {"codigo": codigo, "nome": nome, "params": params, "amostra": amostra,
            "prazo_horas": prazo_horas, "preparacao": preparacao, "descricao": descricao}


POS_NEG = ["Positivo", "Negativo"]
REACTIVE = ["Reactivo", "Não reactivo"]
REACTIVE_IND = ["Reactivo", "Não reactivo", "Indeterminado"]
DETECTED = ["Detectado", "Não detectado"]
DIPSTICK = ["Negativo", "Vestígios", "1+", "2+", "3+", "4+"]
GROWTH = ["Sem crescimento", "Com crescimento"]
YES_NO = ["Sim", "Não"]

FASTING = "Jejum de 8 a 12 horas (água permitida)."
SERUM = "Soro"
PLASMA_CIT = "Plasma citratado"
EDTA = "Sangue total (EDTA)"
URINE = "Urina (jacto médio)"


def report(extra=()):
    """Imaging / functional exams: a structured report."""
    return [*extra, txt("achados", "Achados"), txt("conclusao", "Conclusão")]


def culture(sample, codigo, nome, prazo=72, extra=()):
    return exam(codigo, nome, [
        *extra,
        opt("crescimento", "Crescimento", GROWTH),
        txt("microrganismo", "Microrganismo isolado", required=False),
        txt("contagem", "Contagem", required=False),
        txt("antibiograma", "Antibiograma (TSA)", required=False),
        txt("observacao", "Observações", required=False),
    ], amostra=sample, prazo_horas=prazo)


def igg_igm(prefix, codigo, nome):
    return exam(codigo, nome, [
        opt(f"{prefix}_igg", "IgG", REACTIVE_IND),
        opt(f"{prefix}_igm", "IgM", REACTIVE_IND),
    ], amostra=SERUM, prazo_horas=24)


CBC = [
    dec("hb", "Hemoglobina", "g/dL"),
    dec("hct", "Hematócrito", "%"),
    dec("rbc", "Eritrócitos", "x10⁶/µL", 2),
    dec("mcv", "VGM", "fL"),
    dec("mch", "HGM", "pg"),
    dec("mchc", "CHGM", "g/dL"),
    dec("rdw", "RDW-CV", "%"),
    dec("wbc", "Leucócitos", "x10³/µL", 2),
    dec("neut_pct", "Neutrófilos", "%"),
    dec("lymph_pct", "Linfócitos", "%"),
    dec("mono_pct", "Monócitos", "%"),
    dec("eos_pct", "Eosinófilos", "%"),
    dec("baso_pct", "Basófilos", "%"),
    dec("neut_abs", "Neutrófilos (absoluto)", "x10³/µL", 2),
    dec("lymph_abs", "Linfócitos (absoluto)", "x10³/µL", 2),
    dec("mono_abs", "Monócitos (absoluto)", "x10³/µL", 2),
    dec("eos_abs", "Eosinófilos (absoluto)", "x10³/µL", 2),
    dec("baso_abs", "Basófilos (absoluto)", "x10³/µL", 2),
    num("plt", "Plaquetas", "x10³/µL"),
    dec("mpv", "VPM", "fL", required=False),
]

LIVER = [
    num("ast", "AST (TGO)", "U/L"),
    num("alt", "ALT (TGP)", "U/L"),
    num("alp", "Fosfatase alcalina", "U/L"),
    num("ggt", "Gama-GT", "U/L"),
    dec("bil_total", "Bilirrubina total", "mg/dL", 2),
    dec("bil_direct", "Bilirrubina directa", "mg/dL", 2),
    dec("bil_indirect", "Bilirrubina indirecta", "mg/dL", 2, required=False),
    dec("protein_total", "Proteínas totais", "g/dL"),
    dec("albumin", "Albumina", "g/dL"),
]

URINALYSIS = [
    opt("cor", "Cor", ["Amarelo claro", "Amarelo", "Amarelo escuro", "Âmbar", "Avermelhado", "Outra"]),
    opt("aspecto", "Aspecto", ["Límpido", "Ligeiramente turvo", "Turvo"]),
    dec("densidade", "Densidade", None, 3),
    dec("ph", "pH", None),
    opt("proteinas", "Proteínas", DIPSTICK),
    opt("glicose", "Glicose", DIPSTICK),
    opt("cetonas", "Corpos cetónicos", DIPSTICK),
    opt("sangue", "Sangue (hemoglobina)", DIPSTICK),
    opt("bilirrubina", "Bilirrubina", DIPSTICK),
    opt("urobilinogenio", "Urobilinogénio", ["Normal", "1+", "2+", "3+", "4+"]),
    opt("nitritos", "Nitritos", POS_NEG),
    opt("leucocitos_tira", "Leucócitos (tira)", DIPSTICK),
    txt("sed_leucocitos", "Sedimento: leucócitos (/campo)"),
    txt("sed_eritrocitos", "Sedimento: eritrócitos (/campo)"),
    txt("sed_epiteliais", "Sedimento: células epiteliais", required=False),
    txt("sed_cilindros", "Sedimento: cilindros", required=False),
    txt("sed_cristais", "Sedimento: cristais", required=False),
    txt("sed_bacterias", "Sedimento: bactérias", required=False),
    txt("sed_outros", "Sedimento: outros elementos", required=False),
]

BODY_FLUID = [
    txt("aspecto", "Aspecto"),
    num("celulas", "Contagem celular", "células/µL"),
    txt("formula", "Fórmula leucocitária", required=False),
    num("glicose", "Glicose", "mg/dL"),
    num("proteinas", "Proteínas", "mg/dL"),
    num("ldh", "LDH", "U/L", required=False),
    txt("gram", "Coloração de Gram", required=False),
]

CATALOGUE = [
    {
        "nome": "Laboratório",
        "descricao": "Análises clínicas (patologia clínica).",
        "classes": [
            {"nome": "Hematologia", "exames": [
                exam("HEM-01", "Hemograma completo", CBC, amostra=EDTA, prazo_horas=4),
                exam("HEM-02", "Velocidade de sedimentação", [num("vs", "VS (1.ª hora, Westergren)", "mm/h")],
                     amostra=EDTA, prazo_horas=4),
                exam("HEM-03", "Contagem de reticulócitos", [
                    dec("retic_pct", "Reticulócitos", "%", 2),
                    dec("retic_abs", "Reticulócitos (absoluto)", "x10³/µL", 1, required=False),
                ], amostra=EDTA, prazo_horas=24),
                exam("HEM-04", "Esfregaço de sangue periférico", [
                    txt("eritrocitos", "Série vermelha"), txt("leucocitos", "Série branca"),
                    txt("plaquetas", "Plaquetas"), txt("conclusao", "Conclusão"),
                ], amostra=EDTA, prazo_horas=24),
                exam("HEM-05", "Teste de falciformação", [opt("resultado", "Resultado", POS_NEG)],
                     amostra=EDTA, prazo_horas=24),
                exam("HEM-06", "Electroforese de hemoglobina", [
                    dec("hba", "HbA", "%"), dec("hba2", "HbA2", "%"), dec("hbf", "HbF", "%"),
                    dec("hbs", "HbS", "%", required=False), dec("hbc", "HbC", "%", required=False),
                    txt("interpretacao", "Interpretação"),
                ], amostra=EDTA, prazo_horas=72),
                exam("HEM-07", "Glicose-6-fosfato desidrogenase (G6PD)", [
                    dec("g6pd", "G6PD", "U/g Hb"),
                ], amostra=EDTA, prazo_horas=48),
            ]},
            {"nome": "Hemostase", "exames": [
                exam("COA-01", "Tempo de protrombina e INR", [
                    dec("tp", "Tempo de protrombina", "s"),
                    num("tp_actividade", "Actividade de protrombina", "%", required=False),
                    dec("inr", "INR", None, 2),
                ], amostra=PLASMA_CIT, prazo_horas=4),
                exam("COA-02", "Tempo de tromboplastina parcial activada (aPTT)", [
                    dec("aptt", "aPTT", "s"), dec("aptt_ratio", "Razão aPTT", None, 2, required=False),
                ], amostra=PLASMA_CIT, prazo_horas=4),
                exam("COA-03", "Fibrinogénio", [num("fibrinogenio", "Fibrinogénio", "mg/dL")],
                     amostra=PLASMA_CIT, prazo_horas=4),
                exam("COA-04", "D-dímeros", [num("d_dimeros", "D-dímeros", "ng/mL FEU")],
                     amostra=PLASMA_CIT, prazo_horas=4),
            ]},
            {"nome": "Imuno-hematologia", "exames": [
                exam("IMH-01", "Grupo sanguíneo e factor Rh", [
                    opt("abo", "Grupo ABO", ["A", "B", "AB", "O"]),
                    opt("rh", "Factor Rh (D)", ["Positivo", "Negativo"]),
                ], amostra=EDTA, prazo_horas=2),
                exam("IMH-02", "Teste de Coombs directo", [opt("resultado", "Resultado", POS_NEG)],
                     amostra=EDTA, prazo_horas=24),
                exam("IMH-03", "Teste de Coombs indirecto", [opt("resultado", "Resultado", POS_NEG)],
                     amostra=SERUM, prazo_horas=24),
                exam("IMH-04", "Prova de compatibilidade transfusional", [
                    opt("resultado", "Resultado", ["Compatível", "Incompatível"]),
                    txt("unidade", "Unidade de sangue testada", required=False),
                ], amostra=EDTA, prazo_horas=2),
            ]},
            {"nome": "Bioquímica", "exames": [
                exam("BIO-01", "Glicemia em jejum", [num("glicose", "Glicose", "mg/dL")],
                     amostra=SERUM, prazo_horas=4, preparacao=FASTING),
                exam("BIO-04", "Glicemia ocasional", [num("glicose", "Glicose", "mg/dL")],
                     amostra=SERUM, prazo_horas=2),
                exam("BIO-05", "Prova de tolerância à glicose oral (75 g)", [
                    num("glicose_0", "Glicose basal", "mg/dL"),
                    num("glicose_60", "Glicose aos 60 minutos", "mg/dL", required=False),
                    num("glicose_120", "Glicose aos 120 minutos", "mg/dL"),
                ], amostra=SERUM, prazo_horas=6, preparacao=FASTING + " Repouso durante a prova."),
                exam("BIO-06", "Hemoglobina glicada (HbA1c)", [dec("hba1c", "HbA1c", "%")],
                     amostra=EDTA, prazo_horas=24),
                exam("BIO-07", "Ureia", [num("ureia", "Ureia", "mg/dL")], amostra=SERUM, prazo_horas=4),
                exam("BIO-02", "Creatinina", [
                    dec("creatinina", "Creatinina", "mg/dL", 2),
                    num("tfge", "Taxa de filtração glomerular estimada", "mL/min/1,73 m²", required=False),
                ], amostra=SERUM, prazo_horas=4),
                exam("BIO-08", "Ácido úrico", [dec("acido_urico", "Ácido úrico", "mg/dL")],
                     amostra=SERUM, prazo_horas=4),
                exam("BIO-09", "Função renal", [
                    num("ureia", "Ureia", "mg/dL"), dec("creatinina", "Creatinina", "mg/dL", 2),
                    dec("acido_urico", "Ácido úrico", "mg/dL", required=False),
                    num("tfge", "Taxa de filtração glomerular estimada", "mL/min/1,73 m²", required=False),
                ], amostra=SERUM, prazo_horas=4),
                exam("BIO-10", "Ionograma", [
                    num("sodio", "Sódio", "mmol/L"), dec("potassio", "Potássio", "mmol/L"),
                    num("cloro", "Cloro", "mmol/L"), num("bicarbonato", "Bicarbonato", "mmol/L", required=False),
                ], amostra=SERUM, prazo_horas=4),
                exam("BIO-11", "Cálcio total", [dec("calcio", "Cálcio total", "mg/dL")], amostra=SERUM, prazo_horas=4),
                exam("BIO-12", "Cálcio ionizado", [dec("calcio_ionizado", "Cálcio ionizado", "mmol/L", 2)],
                     amostra="Sangue total heparinizado", prazo_horas=2),
                exam("BIO-13", "Magnésio", [dec("magnesio", "Magnésio", "mg/dL")], amostra=SERUM, prazo_horas=4),
                exam("BIO-14", "Fósforo", [dec("fosforo", "Fósforo", "mg/dL")], amostra=SERUM, prazo_horas=4),
                exam("BIO-03", "Colesterol total", [num("colesterol_total", "Colesterol total", "mg/dL")],
                     amostra=SERUM, prazo_horas=4, preparacao=FASTING),
                exam("BIO-15", "Perfil lipídico", [
                    num("colesterol_total", "Colesterol total", "mg/dL"),
                    num("hdl", "Colesterol HDL", "mg/dL"),
                    num("ldl", "Colesterol LDL", "mg/dL"),
                    num("trigliceridos", "Triglicéridos", "mg/dL"),
                    num("nao_hdl", "Colesterol não-HDL", "mg/dL", required=False),
                ], amostra=SERUM, prazo_horas=4, preparacao=FASTING),
                exam("BIO-16", "Provas de função hepática", LIVER, amostra=SERUM, prazo_horas=4),
                exam("BIO-17", "Transaminases (AST e ALT)", [
                    num("ast", "AST (TGO)", "U/L"), num("alt", "ALT (TGP)", "U/L"),
                ], amostra=SERUM, prazo_horas=4),
                exam("BIO-18", "Bilirrubinas", [
                    dec("bil_total", "Bilirrubina total", "mg/dL", 2),
                    dec("bil_direct", "Bilirrubina directa", "mg/dL", 2),
                    dec("bil_indirect", "Bilirrubina indirecta", "mg/dL", 2, required=False),
                ], amostra=SERUM, prazo_horas=4),
                exam("BIO-19", "Proteínas totais e albumina", [
                    dec("protein_total", "Proteínas totais", "g/dL"), dec("albumin", "Albumina", "g/dL"),
                ], amostra=SERUM, prazo_horas=4),
                exam("BIO-20", "Amilase", [num("amilase", "Amilase", "U/L")], amostra=SERUM, prazo_horas=4),
                exam("BIO-21", "Lipase", [num("lipase", "Lipase", "U/L")], amostra=SERUM, prazo_horas=4),
                exam("BIO-22", "Creatina quinase (CK)", [num("ck", "CK total", "U/L")], amostra=SERUM, prazo_horas=4),
                exam("BIO-23", "CK-MB", [dec("ck_mb", "CK-MB", "ng/mL")], amostra=SERUM, prazo_horas=2),
                exam("BIO-24", "Troponina", [
                    dec("troponina", "Troponina (unidade conforme o método)", "ng/L"),
                    opt("tipo", "Tipo", ["Troponina I", "Troponina T"]),
                ], amostra=SERUM, prazo_horas=2),
                exam("BIO-25", "Desidrogenase láctica (LDH)", [num("ldh", "LDH", "U/L")], amostra=SERUM, prazo_horas=4),
                exam("BIO-26", "Proteína C reactiva (PCR)", [dec("pcr", "PCR", "mg/L")], amostra=SERUM, prazo_horas=4),
                exam("BIO-27", "Estudo do ferro", [
                    num("ferro", "Ferro sérico", "µg/dL"),
                    num("ctff", "Capacidade total de fixação do ferro", "µg/dL", required=False),
                    num("transferrina", "Transferrina", "mg/dL", required=False),
                    num("saturacao_transferrina", "Saturação da transferrina", "%", required=False),
                    dec("ferritina", "Ferritina", "ng/mL", required=False),
                ], amostra=SERUM, prazo_horas=24, preparacao="Colheita de manhã, em jejum."),
                exam("BIO-28", "Ferritina", [dec("ferritina", "Ferritina", "ng/mL")], amostra=SERUM, prazo_horas=24),
                exam("BIO-29", "Vitamina B12", [num("vitamina_b12", "Vitamina B12", "pg/mL")], amostra=SERUM, prazo_horas=48),
                exam("BIO-30", "Ácido fólico", [dec("acido_folico", "Ácido fólico", "ng/mL")], amostra=SERUM, prazo_horas=48),
                exam("BIO-31", "Vitamina D (25-OH)", [dec("vitamina_d", "25-OH vitamina D", "ng/mL")],
                     amostra=SERUM, prazo_horas=72),
                exam("BIO-32", "Gasometria arterial", [
                    dec("ph", "pH", None, 2), dec("pco2", "pCO2", "mmHg"), dec("po2", "pO2", "mmHg"),
                    dec("hco3", "HCO3⁻", "mmol/L"), dec("be", "Excesso de bases", "mmol/L"),
                    dec("sao2", "SaO2", "%"), dec("lactato", "Lactato", "mmol/L", required=False),
                    dec("fio2", "FiO2", "%", required=False),
                ], amostra="Sangue arterial heparinizado", prazo_horas=1),
                exam("BIO-33", "Lactato", [dec("lactato", "Lactato", "mmol/L")],
                     amostra="Plasma (fluoreto) ou sangue arterial", prazo_horas=1),
                exam("BIO-34", "NT-proBNP", [num("nt_probnp", "NT-proBNP", "pg/mL")], amostra=SERUM, prazo_horas=4),
                exam("BIO-35", "Razão albumina/creatinina na urina", [
                    dec("albumina_urina", "Albumina", "mg/L"),
                    dec("creatinina_urina", "Creatinina", "mg/dL"),
                    dec("rac", "Razão albumina/creatinina", "mg/g"),
                ], amostra="Urina (primeira da manhã)", prazo_horas=24),
                exam("BIO-36", "Proteinúria de 24 horas", [
                    num("volume", "Volume urinário", "mL"), num("proteinuria", "Proteinúria", "mg/24 h"),
                ], amostra="Urina de 24 horas", prazo_horas=24,
                     preparacao="Desprezar a primeira urina da manhã e colher toda a urina das 24 horas seguintes."),
                exam("BIO-37", "Depuração da creatinina", [
                    num("volume", "Volume urinário", "mL"),
                    dec("creatinina_serica", "Creatinina sérica", "mg/dL", 2),
                    dec("creatinina_urinaria", "Creatinina urinária", "mg/dL"),
                    num("depuracao", "Depuração da creatinina", "mL/min"),
                ], amostra="Urina de 24 horas e soro", prazo_horas=24),
            ]},
            {"nome": "Endocrinologia", "exames": [
                exam("END-01", "TSH", [dec("tsh", "TSH", "µUI/mL", 2)], amostra=SERUM, prazo_horas=24),
                exam("END-02", "T4 livre", [dec("t4_livre", "T4 livre", "ng/dL", 2)], amostra=SERUM, prazo_horas=24),
                exam("END-03", "T3 livre", [dec("t3_livre", "T3 livre", "pg/mL", 2)], amostra=SERUM, prazo_horas=24),
                exam("END-04", "Função tiroideia (TSH, T4 livre, T3 livre)", [
                    dec("tsh", "TSH", "µUI/mL", 2), dec("t4_livre", "T4 livre", "ng/dL", 2),
                    dec("t3_livre", "T3 livre", "pg/mL", 2, required=False),
                ], amostra=SERUM, prazo_horas=24),
                exam("END-05", "Beta-hCG quantitativa", [dec("beta_hcg", "Beta-hCG", "mUI/mL")],
                     amostra=SERUM, prazo_horas=4),
                exam("END-06", "Prolactina", [dec("prolactina", "Prolactina", "ng/mL")], amostra=SERUM, prazo_horas=24),
                exam("END-07", "FSH", [dec("fsh", "FSH", "mUI/mL")], amostra=SERUM, prazo_horas=24),
                exam("END-08", "LH", [dec("lh", "LH", "mUI/mL")], amostra=SERUM, prazo_horas=24),
                exam("END-09", "Estradiol", [num("estradiol", "Estradiol", "pg/mL")], amostra=SERUM, prazo_horas=24),
                exam("END-10", "Progesterona", [dec("progesterona", "Progesterona", "ng/mL")], amostra=SERUM, prazo_horas=24),
                exam("END-11", "Testosterona total", [num("testosterona", "Testosterona total", "ng/dL")],
                     amostra=SERUM, prazo_horas=24, preparacao="Colheita de manhã (entre as 7 e as 10 horas)."),
                exam("END-12", "Cortisol", [dec("cortisol", "Cortisol", "µg/dL"),
                                            opt("hora", "Hora da colheita", ["Manhã (8 h)", "Tarde (16 h)", "Outra"])],
                     amostra=SERUM, prazo_horas=24),
                exam("END-13", "Insulina", [dec("insulina", "Insulina", "µUI/mL")],
                     amostra=SERUM, prazo_horas=24, preparacao=FASTING),
                exam("END-14", "Paratormona (PTH)", [dec("pth", "PTH intacta", "pg/mL")], amostra=SERUM, prazo_horas=48),
            ]},
            {"nome": "Marcadores tumorais", "exames": [
                exam("MT-01", "PSA total", [dec("psa_total", "PSA total", "ng/mL", 2)], amostra=SERUM, prazo_horas=24),
                exam("MT-02", "PSA livre e razão", [
                    dec("psa_total", "PSA total", "ng/mL", 2), dec("psa_livre", "PSA livre", "ng/mL", 2),
                    num("razao", "Razão PSA livre/total", "%"),
                ], amostra=SERUM, prazo_horas=48),
                exam("MT-03", "CEA", [dec("cea", "CEA", "ng/mL")], amostra=SERUM, prazo_horas=48),
                exam("MT-04", "CA 125", [dec("ca125", "CA 125", "U/mL")], amostra=SERUM, prazo_horas=48),
                exam("MT-05", "CA 19-9", [dec("ca19_9", "CA 19-9", "U/mL")], amostra=SERUM, prazo_horas=48),
                exam("MT-06", "CA 15-3", [dec("ca15_3", "CA 15-3", "U/mL")], amostra=SERUM, prazo_horas=48),
                exam("MT-07", "Alfa-fetoproteína (AFP)", [dec("afp", "AFP", "ng/mL")], amostra=SERUM, prazo_horas=48),
            ]},
            {"nome": "Imunologia e serologia", "exames": [
                exam("SER-01", "Teste rápido de VIH 1/2", [
                    opt("teste_1", "Teste 1 (rastreio)", REACTIVE),
                    opt("teste_2", "Teste 2 (confirmação)", REACTIVE, required=False),
                    opt("resultado", "Resultado final", ["Positivo", "Negativo", "Indeterminado"]),
                ], amostra="Sangue capilar ou soro", prazo_horas=1,
                     descricao="Algoritmo nacional de testagem: o teste 2 só é feito se o teste 1 for reactivo."),
                exam("SER-02", "Contagem de linfócitos CD4", [
                    num("cd4", "Linfócitos CD4", "células/µL"),
                    dec("cd4_pct", "Linfócitos CD4", "%", required=False),
                ], amostra=EDTA, prazo_horas=24),
                exam("SER-03", "Antigénio de superfície da hepatite B (AgHBs)", [opt("resultado", "Resultado", REACTIVE)],
                     amostra=SERUM, prazo_horas=24),
                exam("SER-04", "Anticorpo anti-HBs", [dec("anti_hbs", "Anti-HBs", "mUI/mL")], amostra=SERUM, prazo_horas=48),
                exam("SER-05", "Anticorpo anti-HBc total", [opt("resultado", "Resultado", REACTIVE)], amostra=SERUM, prazo_horas=48),
                exam("SER-06", "Anticorpo anti-VHC (hepatite C)", [opt("resultado", "Resultado", REACTIVE)],
                     amostra=SERUM, prazo_horas=24),
                exam("SER-07", "Sífilis - teste não treponémico (RPR/VDRL)", [
                    opt("resultado", "Resultado", REACTIVE), txt("titulo", "Título", required=False),
                ], amostra=SERUM, prazo_horas=24),
                exam("SER-08", "Sífilis - teste treponémico (TPHA/teste rápido)", [opt("resultado", "Resultado", REACTIVE)],
                     amostra=SERUM, prazo_horas=24),
                exam("SER-09", "Teste de gravidez na urina", [opt("resultado", "Resultado", POS_NEG)],
                     amostra="Urina (primeira da manhã)", prazo_horas=1),
                exam("SER-10", "Reacção de Widal", [
                    opt("to", "Antigénio O (S. Typhi)", ["< 1/80", "1/80", "1/160", "1/320", "≥ 1/640"]),
                    opt("th", "Antigénio H (S. Typhi)", ["< 1/80", "1/80", "1/160", "1/320", "≥ 1/640"]),
                ], amostra=SERUM, prazo_horas=24),
                exam("SER-11", "Factor reumatóide", [dec("fr", "Factor reumatóide", "UI/mL")], amostra=SERUM, prazo_horas=24),
                exam("SER-12", "Antiestreptolisina O (ASO)", [num("aso", "ASO", "UI/mL")], amostra=SERUM, prazo_horas=24),
                exam("SER-13", "Anticorpos antinucleares (ANA)", [
                    opt("resultado", "Resultado", POS_NEG), txt("titulo", "Título", required=False),
                    txt("padrao", "Padrão", required=False),
                ], amostra=SERUM, prazo_horas=72),
                igg_igm("toxo", "SER-14", "Toxoplasmose (IgG e IgM)"),
                igg_igm("rubeola", "SER-15", "Rubéola (IgG e IgM)"),
                igg_igm("cmv", "SER-16", "Citomegalovírus (IgG e IgM)"),
                exam("SER-17", "Dengue (NS1, IgM e IgG)", [
                    opt("ns1", "Antigénio NS1", REACTIVE), opt("igm", "IgM", REACTIVE), opt("igg", "IgG", REACTIVE),
                ], amostra=SERUM, prazo_horas=2),
                exam("SER-18", "Antigénio de Helicobacter pylori nas fezes", [opt("resultado", "Resultado", POS_NEG)],
                     amostra="Fezes", prazo_horas=24),
                exam("SER-19", "Antigénio criptocócico (CrAg)", [opt("resultado", "Resultado", POS_NEG)],
                     amostra="Soro ou LCR", prazo_horas=2),
                exam("SER-20", "Teste rápido de antigénio SARS-CoV-2", [opt("resultado", "Resultado", POS_NEG)],
                     amostra="Zaragatoa nasofaríngea", prazo_horas=1),
            ]},
            {"nome": "Biologia molecular", "exames": [
                exam("MOL-01", "Carga viral do VIH-1", [
                    num("carga_viral", "Carga viral", "cópias/mL"),
                    dec("log", "Carga viral (log10)", "log10", 2, required=False),
                    opt("detectavel", "Resultado", ["Detectável", "Indetectável"]),
                ], amostra="Plasma (EDTA)", prazo_horas=168),
                exam("MOL-02", "GeneXpert MTB/RIF", [
                    opt("mtb", "Mycobacterium tuberculosis", ["Detectado", "Não detectado", "Inválido/Erro"]),
                    opt("rif", "Resistência à rifampicina", ["Detectada", "Não detectada", "Indeterminada"], required=False),
                ], amostra="Expectoração", prazo_horas=24),
                exam("MOL-03", "PCR SARS-CoV-2", [opt("resultado", "Resultado", DETECTED)],
                     amostra="Zaragatoa nasofaríngea", prazo_horas=48),
                exam("MOL-04", "Carga viral da hepatite B", [num("carga_viral", "Carga viral", "UI/mL")],
                     amostra="Plasma (EDTA)", prazo_horas=168),
            ]},
            {"nome": "Microbiologia", "exames": [
                culture("Sangue (frascos de hemocultura)", "MIC-01", "Hemocultura", prazo=120),
                culture(URINE, "MIC-02", "Urocultura com antibiograma"),
                culture("Fezes", "MIC-03", "Coprocultura"),
                culture("Expectoração", "MIC-04", "Cultura de expectoração"),
                culture("Pus / exsudado de ferida", "MIC-05", "Cultura de pus / exsudado"),
                culture("Exsudado vaginal", "MIC-06", "Exsudado vaginal", extra=[
                    txt("exame_directo", "Exame directo", required=False),
                ]),
                culture("Exsudado uretral", "MIC-07", "Exsudado uretral", extra=[
                    txt("exame_directo", "Exame directo", required=False),
                ]),
                culture("Líquido cefalorraquidiano", "MIC-08", "Cultura do líquido cefalorraquidiano"),
                exam("MIC-09", "Coloração de Gram", [txt("resultado", "Resultado")], amostra="Conforme o pedido", prazo_horas=2),
                exam("MIC-10", "Baciloscopia (BAAR, Ziehl-Neelsen)", [
                    opt("resultado", "Resultado",
                        ["Negativo", "Escasso (1-9 BAAR/100 campos)", "1+", "2+", "3+"]),
                    num("amostra_n", "Número da amostra", None, required=False),
                ], amostra="Expectoração", prazo_horas=24),
                exam("MIC-11", "TB-LAM na urina", [opt("resultado", "Resultado", POS_NEG)], amostra="Urina", prazo_horas=1),
                exam("MIC-12", "Pesquisa de fungos (exame directo KOH)", [txt("resultado", "Resultado")],
                     amostra="Pele, unhas ou cabelo", prazo_horas=24),
            ]},
            {"nome": "Parasitologia", "exames": [
                exam("PAR-03", "Pesquisa de Plasmodium (gota espessa e esfregaço)", [
                    opt("resultado", "Resultado", POS_NEG),
                    opt("especie", "Espécie",
                        ["P. falciparum", "P. malariae", "P. ovale", "P. vivax", "Infecção mista"], required=False),
                    num("densidade", "Densidade parasitária", "parasitas/µL", required=False),
                    opt("gametocitos", "Gametócitos", ["Presentes", "Ausentes"], required=False),
                ], amostra=EDTA, prazo_horas=2),
                exam("PAR-01", "Teste rápido de malária", [opt("resultado", "Resultado", POS_NEG)],
                     amostra="Sangue capilar", prazo_horas=1),
                exam("PAR-02", "Exame parasitológico de fezes", [
                    opt("resultado", "Resultado", ["Não foram observados parasitas", "Parasitas observados"]),
                    txt("parasitas", "Parasitas observados", required=False),
                    txt("aspecto", "Aspecto macroscópico", required=False),
                ], amostra="Fezes", prazo_horas=24),
                exam("PAR-04", "Pesquisa de Schistosoma na urina", [
                    opt("resultado", "Resultado", POS_NEG),
                    num("ovos", "Ovos", "ovos/10 mL", required=False),
                ], amostra="Urina (entre as 10 e as 14 horas)", prazo_horas=24),
                exam("PAR-05", "Pesquisa de sangue oculto nas fezes", [opt("resultado", "Resultado", POS_NEG)],
                     amostra="Fezes", prazo_horas=24),
            ]},
            {"nome": "Urina", "exames": [
                exam("URI-01", "Urina tipo II (exame sumário)", URINALYSIS, amostra=URINE, prazo_horas=4,
                     preparacao="Higiene local; colher o jacto médio da primeira urina da manhã."),
            ]},
            {"nome": "Líquidos biológicos", "exames": [
                exam("LIQ-01", "Exame citoquímico do líquido cefalorraquidiano", [
                    *BODY_FLUID, opt("tinta_china", "Tinta-da-china (Cryptococcus)", POS_NEG, required=False),
                ], amostra="Líquido cefalorraquidiano", prazo_horas=2),
                exam("LIQ-02", "Exame citoquímico do líquido pleural", BODY_FLUID, amostra="Líquido pleural", prazo_horas=4),
                exam("LIQ-03", "Exame citoquímico do líquido ascítico", BODY_FLUID, amostra="Líquido ascítico", prazo_horas=4),
                exam("LIQ-04", "Espermograma", [
                    dec("volume", "Volume", "mL"), dec("ph", "pH", None),
                    dec("concentracao", "Concentração", "x10⁶/mL"), dec("total", "Número total", "x10⁶"),
                    num("motilidade_progressiva", "Motilidade progressiva", "%"),
                    num("motilidade_total", "Motilidade total", "%"),
                    num("morfologia_normal", "Formas normais", "%"),
                    num("vitalidade", "Vitalidade", "%", required=False),
                    txt("observacao", "Observações", required=False),
                ], amostra="Esperma", prazo_horas=24, preparacao="Abstinência sexual de 2 a 7 dias."),
            ]},
            {"nome": "Anatomia patológica", "exames": [
                exam("AP-01", "Exame histopatológico (biópsia/peça)", [
                    txt("macroscopia", "Exame macroscópico"), txt("microscopia", "Exame microscópico"),
                    txt("diagnostico", "Diagnóstico"),
                ], amostra="Tecido em formol a 10%", prazo_horas=168),
                exam("AP-02", "Citologia cervicovaginal (Papanicolau)", [
                    opt("adequacao", "Adequação da amostra", ["Satisfatória", "Insatisfatória"]),
                    opt("resultado", "Resultado (Bethesda)", [
                        "Negativo para lesão intraepitelial ou malignidade", "ASC-US", "ASC-H", "LSIL", "HSIL",
                        "Carcinoma pavimentocelular", "AGC", "Adenocarcinoma",
                    ]),
                    txt("observacao", "Observações", required=False),
                ], amostra="Esfregaço cervical", prazo_horas=168),
                exam("AP-03", "Citologia aspirativa por agulha fina (CAAF)", [
                    txt("descricao", "Descrição"), txt("diagnostico", "Diagnóstico"),
                ], amostra="Aspirado", prazo_horas=120),
            ]},
        ],
    },
    {
        "nome": "Imagiologia",
        "descricao": "Diagnóstico por imagem.",
        "classes": [
            {"nome": "Radiologia", "exames": [
                exam("RAD-01", "Raio-X do tórax", report(), prazo_horas=24),
                exam("RAD-02", "Raio-X do abdómen", report(), prazo_horas=24),
                exam("RAD-03", "Raio-X da coluna cervical", report(), prazo_horas=24),
                exam("RAD-04", "Raio-X da coluna dorsal", report(), prazo_horas=24),
                exam("RAD-05", "Raio-X da coluna lombar", report(), prazo_horas=24),
                exam("RAD-06", "Raio-X da bacia", report(), prazo_horas=24),
                exam("RAD-07", "Raio-X do crânio", report(), prazo_horas=24),
                exam("RAD-08", "Raio-X dos seios perinasais", report(), prazo_horas=24),
                exam("RAD-09", "Raio-X do membro superior", report([txt("regiao", "Região e lado")]), prazo_horas=24),
                exam("RAD-10", "Raio-X do membro inferior", report([txt("regiao", "Região e lado")]), prazo_horas=24),
            ]},
            {"nome": "Ecografia", "exames": [
                exam("ECO-01", "Ecografia abdominal", report(), prazo_horas=24),
                exam("ECO-02", "Ecografia pélvica", report(), prazo_horas=24,
                     preparacao="Bexiga cheia: beber 1 litro de água 1 hora antes e não urinar."),
                exam("ECO-03", "Ecografia obstétrica", report([
                    dec("idade_gestacional", "Idade gestacional", "semanas"),
                    num("bcf", "Batimentos cardíacos fetais", "bpm", required=False),
                    opt("apresentacao", "Apresentação", ["Cefálica", "Pélvica", "Transversa", "Indeterminada"],
                        required=False),
                    txt("placenta", "Placenta", required=False),
                    opt("liquido_amniotico", "Líquido amniótico", ["Normal", "Diminuído", "Aumentado"], required=False),
                    num("peso_fetal", "Peso fetal estimado", "g", required=False),
                ]), prazo_horas=24),
                exam("ECO-04", "Ecografia transvaginal", report(), prazo_horas=24),
                exam("ECO-05", "Ecografia renal e vesical", report(), prazo_horas=24),
                exam("ECO-06", "Ecografia prostática", report([dec("volume_prostata", "Volume prostático", "mL", required=False)]),
                     prazo_horas=24),
                exam("ECO-07", "Ecografia da tiroide", report(), prazo_horas=24),
                exam("ECO-08", "Ecografia mamária", report([
                    opt("birads", "Categoria BI-RADS", ["0", "1", "2", "3", "4", "5", "6"]),
                ]), prazo_horas=24),
                exam("ECO-09", "Ecografia de partes moles", report([txt("regiao", "Região")]), prazo_horas=24),
                exam("ECO-10", "Ecografia testicular", report(), prazo_horas=24),
                exam("ECO-11", "Eco-Doppler venoso dos membros inferiores", report(), prazo_horas=24),
                exam("ECO-12", "Eco-Doppler das artérias carótidas", report(), prazo_horas=24),
            ]},
            {"nome": "Tomografia computorizada", "exames": [
                exam("TC-01", "TC do crânio", report([opt("contraste", "Contraste", YES_NO)]), prazo_horas=24),
                exam("TC-02", "TC do tórax", report([opt("contraste", "Contraste", YES_NO)]), prazo_horas=24),
                exam("TC-03", "TC do abdómen e pélvis", report([opt("contraste", "Contraste", YES_NO)]), prazo_horas=24),
                exam("TC-04", "TC da coluna", report([txt("segmento", "Segmento")]), prazo_horas=24),
                exam("TC-05", "Angio-TC", report([txt("territorio", "Território vascular")]), prazo_horas=24),
            ]},
            {"nome": "Ressonância magnética", "exames": [
                exam("RM-01", "RM do crânio (encefálica)", report([opt("contraste", "Contraste", YES_NO)]), prazo_horas=48),
                exam("RM-02", "RM da coluna", report([txt("segmento", "Segmento")]), prazo_horas=48),
                exam("RM-03", "RM articular", report([txt("articulacao", "Articulação e lado")]), prazo_horas=48),
            ]},
            {"nome": "Mamografia", "exames": [
                exam("MAM-01", "Mamografia bilateral", report([
                    opt("densidade", "Densidade mamária (ACR)", ["A", "B", "C", "D"]),
                    opt("birads", "Categoria BI-RADS", ["0", "1", "2", "3", "4", "5", "6"]),
                ]), prazo_horas=48),
            ]},
            {"nome": "Densitometria óssea", "exames": [
                exam("DXA-01", "Densitometria óssea (DXA)", report([
                    dec("t_score_coluna", "T-score coluna lombar", None, required=False),
                    dec("t_score_colo", "T-score colo do fémur", None, required=False),
                    dec("z_score", "Z-score", None, required=False),
                ]), prazo_horas=48),
            ]},
        ],
    },
    {
        "nome": "Exames funcionais",
        "descricao": "Cardiologia, pneumologia, neurofisiologia e audiologia.",
        "classes": [
            {"nome": "Cardiologia", "exames": [
                exam("CAR-01", "Electrocardiograma (ECG)", [
                    txt("ritmo", "Ritmo"), num("fc", "Frequência cardíaca", "bpm"),
                    num("pr", "Intervalo PR", "ms", required=False), num("qrs", "Duração do QRS", "ms", required=False),
                    num("qtc", "QTc", "ms", required=False), txt("conclusao", "Conclusão"),
                ], prazo_horas=1),
                exam("CAR-02", "Ecocardiograma transtorácico", report([
                    num("fevi", "Fracção de ejecção do VE", "%"),
                ]), prazo_horas=24),
                exam("CAR-03", "Holter de 24 horas", report(), prazo_horas=72),
                exam("CAR-04", "Monitorização ambulatória da pressão arterial (MAPA 24 h)", report([
                    num("pas_media", "PA sistólica média", "mmHg"), num("pad_media", "PA diastólica média", "mmHg"),
                ]), prazo_horas=72),
                exam("CAR-05", "Prova de esforço", report(), prazo_horas=24),
            ]},
            {"nome": "Pneumologia", "exames": [
                exam("PNE-01", "Espirometria", [
                    dec("fev1", "FEV1", "L", 2), dec("fvc", "FVC", "L", 2), dec("fev1_fvc", "FEV1/FVC", "%"),
                    opt("broncodilatacao", "Prova de broncodilatação", ["Positiva", "Negativa", "Não realizada"],
                        required=False),
                    txt("conclusao", "Conclusão"),
                ], prazo_horas=24),
            ]},
            {"nome": "Neurofisiologia", "exames": [
                exam("NEU-01", "Electroencefalograma (EEG)", report(), prazo_horas=72),
            ]},
            {"nome": "Audiologia", "exames": [
                exam("AUD-01", "Audiometria tonal", report(), prazo_horas=24),
            ]},
        ],
    },
    {
        "nome": "Endoscopia",
        "descricao": "Endoscopia digestiva.",
        "classes": [
            {"nome": "Endoscopia digestiva", "exames": [
                exam("END-D-01", "Endoscopia digestiva alta", report([opt("biopsia", "Biópsia colhida", YES_NO)]),
                     prazo_horas=24, preparacao="Jejum de 8 horas."),
                exam("END-D-02", "Colonoscopia", report([opt("biopsia", "Biópsia colhida", YES_NO)]),
                     prazo_horas=24, preparacao="Preparação intestinal conforme a folha entregue na marcação."),
                exam("END-D-03", "Rectossigmoidoscopia", report([opt("biopsia", "Biópsia colhida", YES_NO)]),
                     prazo_horas=24),
            ]},
        ],
    },
]
