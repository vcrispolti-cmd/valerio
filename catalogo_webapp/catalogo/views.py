from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .filters import OperaFilter
from .models import Opera, TipoOpera

PAGE_SIZE = 24


def catalogo_landing(request):
    """Landing page: one entry per section (TipoOpera), like the 3-section split on the reference site."""
    sezioni = TipoOpera.objects.filter(attivo=True).annotate()
    return render(request, "catalogo/landing.html", {"sezioni": sezioni})


def opera_browse(request, sezione_slug=None):
    """Browse/grid view, filterable, optionally scoped to one section."""
    queryset = (
        Opera.objects.filter(pubblicata=True, immagini__file__gt="")
        .select_related("tipo_opera")
        .distinct()
    )

    sezione = None
    if sezione_slug:
        sezione = get_object_or_404(TipoOpera, slug=sezione_slug)
        queryset = queryset.filter(tipo_opera=sezione)

    opera_filter = OperaFilter(request.GET, queryset=queryset)

    paginator = Paginator(opera_filter.qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Filter params only, without "page", so pagination links keep the current filters.
    querystring = request.GET.copy()
    querystring.pop("page", None)

    return render(
        request,
        "catalogo/browse.html",
        {
            "sezione": sezione,
            "sezioni": TipoOpera.objects.filter(attivo=True),
            "filter": opera_filter,
            "opere": page_obj,
            "page_obj": page_obj,
            "querystring": querystring.urlencode(),
        },
    )


def opera_detail(request, numero_archivio):
    opera = get_object_or_404(
        Opera.objects.select_related("tipo_opera", "collezione").prefetch_related(
            "immagini",
            "bibliografia__fonte",
            "operamostra_set__mostra_sede__mostra",
            "operamostra_set__mostra_sede__sede",
        ),
        numero_archivio=numero_archivio,
        pubblicata=True,
    )

    # Prev/next step through published works in the same section, in the model's default
    # (chronological) order — same ordering the browse grid uses, so "next" here matches
    # what you'd hit moving forward through that section's grid.
    siblings = list(
        Opera.objects.filter(pubblicata=True, tipo_opera=opera.tipo_opera)
        .values_list("numero_archivio", flat=True)
    )
    prev_opera = next_opera = None
    if numero_archivio in siblings:
        idx = siblings.index(numero_archivio)
        if idx > 0:
            prev_opera = Opera.objects.filter(numero_archivio=siblings[idx - 1]).first()
        if idx < len(siblings) - 1:
            next_opera = Opera.objects.filter(numero_archivio=siblings[idx + 1]).first()

    return render(
        request,
        "catalogo/opera_detail.html",
        {"opera": opera, "prev_opera": prev_opera, "next_opera": next_opera},
    )
