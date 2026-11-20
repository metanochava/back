"""Translations of the catalog module (pt-pt). Canonical keys are English;
the catalogue's older keys (Products, Product Categories, Prices, ...) stay in
inventory/lang, where they were, and shared keys live in django_resaas."""

key_value = {
    "Catalog": "Catálogo",
    "Catalog Manager": "Gestor de Catálogo",
    # the product's rules (catalog/serializers/product.py)
    "A service has no stock.": "Um serviço não tem stock.",
    "Lot tracking can only change before the product has stock movements.": "O controlo por lotes só pode mudar antes de o produto ter movimentos de stock.",
    "The type can only change before the product has stock movements.": "O tipo só pode mudar antes de o produto ter movimentos de stock.",
    # the manual forms (front: stock/product, productcategory, pricelist)
    "New product": "Novo produto",
    "Edit product": "Editar produto",
    "Product type": "Tipo de produto",
    "Goods": "Bem",
    "Identification": "Identificação",
    "Unit": "Unidade",
    "For example: un, kg, l, hour": "Por exemplo: un, kg, l, hora",
    "Base price": "Preço base",
    "A price list may give a customer another price": "Uma lista de preços pode dar outro preço a um cliente",
    "Minimum stock": "Stock mínimo",
    "Below it the product shows as low": "Abaixo dele o produto aparece como baixo",
    "Track lots": "Controlar lotes",
    "Stock is kept per lot, with expiry date": "O stock é guardado por lote, com data de validade",
    "Variant and image": "Variante e imagem",
    "Variant of": "Variante de",
    "Only for a size, colour... of another product": "Só para um tamanho, cor... de outro produto",
    "New product category": "Nova categoria de produto",
    "Edit product category": "Editar categoria de produto",
    "New price list": "Nova lista de preços",
    "Edit price list": "Editar lista de preços",
    "Validity": "Validade",
    "Until": "Até",
    "Leave both empty for a list that is always valid": "Deixe ambas vazias para uma lista sempre válida",
    "Prices": "Preços",
}
