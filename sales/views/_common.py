from sales.models import Sale


def _active_sales_in_period(view, request):
    data_inicio, data_fim = view.require_period(request)

    qs = view.apply_scope(
        request,
        Sale.objects.filter(data__gte=data_inicio, data__lte=data_fim)
        .exclude(estado=Sale.ESTADO_ANULADA)
    )

    return qs, data_inicio, data_fim
