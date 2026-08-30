from django.shortcuts import get_object_or_404, render

from .filters import OperaFilter
from .models import Opera, TipoOpera


def catalogo_landing(request):
    """Landing page: one entry per section (TipoOpera), like the 3-section split on the reference site."""
    sezioni = TipoOpera.objects.filter(attivo=True).annotate()
    return render(request, "catalogo/landing.html", {"sezioni": sezioni})


def opera_browse(request, sezione_slug=None):
    """Browse/grid view, filterable, optionally scoped to one section."""
    queryset = Opera.objects.filter(pubblicata=True).select_related("tipo_opera")

    sezione = None
    if sezione_slug:
        sezione = get_object_or_404(TipoOpera, slug=sezione_slug)
        queryset = queryset.filter(tipo_opera=sezione)

    opera_filter = OperaFilter(request.GET, queryset=queryset)

    return render(
        request,
        "catalogo/browse.html",
        {
            "sezione": sezione,
            "sezioni": TipoOpera.objects.filter(attivo=True),
            "filter": opera_filter,
            "opere": opera_filter.qs,
        },
    )


def opera_detail(request, numero_archivio):
    opera = get_object_or_404(
        Opera.objects.select_related("tipo_opera", "collezione").prefetch_related(
            "immagini",
            "bibliografia__fonte",
            "operamostra_set__mostra__mostrasede_set__sede",
        ),
        numero_archivio=numero_archivio,
        pubblicata=True,
    )
    return render(request, "catalogo/opera_detail.html", {"opera": opera})
