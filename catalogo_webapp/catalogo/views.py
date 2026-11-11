import re

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .filters import OperaFilter
from .models import Opera, TipoOpera

PAGE_SIZE = 24

_MESI = {
    m: i for i, m in enumerate(
        ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
         "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
        start=1,
    )
}


def _mese_ordine(data_pubblicazione):
    """Best-effort month number from free-text data_pubblicazione ('maggio-giugno 1989',
    '24 luglio 1989') — used only to break same-year ties in bibliography order so it
    matches the reference scheda's chronological-within-year sequence."""
    testo = (data_pubblicazione or "").lower()
    for nome, numero in _MESI.items():
        if nome in testo:
            return numero
    return 0


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


def opera_detail(request, numero_scheda):
    opera = get_object_or_404(
        Opera.objects.select_related("tipo_opera", "collezione").prefetch_related(
            "immagini__tipo_immagine",
            "bibliografia__fonte",
            "operamostra_set__mostra_sede__mostra__tipo_esposizione",
            "operamostra_set__mostra_sede__sede",
        ),
        numero_scheda=numero_scheda,
        pubblicata=True,
    )

    # Split into "personali"/"collettive" (the catalogue's own long-standing distinction)
    # instead of one flat "Esposizioni" list — anything whose TipoEsposizione doesn't say
    # one or the other (e.g. "Da verificare", or simply not set) falls into "altre". Sorted
    # chronologically ascending within each group, matching the reference scheda — the
    # model's default OperaMostra ordering (by mostra_sede id) doesn't reflect exhibition
    # year at all.
    esposizioni_personali, esposizioni_collettive, esposizioni_altre = [], [], []
    for om in sorted(opera.operamostra_set.all(), key=lambda om: om.mostra_sede.mostra.anno_testo or ""):
        tipo = om.mostra_sede.mostra.tipo_esposizione
        label = ((tipo.normalizzato or tipo.nome) if tipo else "").lower()
        if "personal" in label:
            esposizioni_personali.append(om)
        elif "collettiv" in label:
            esposizioni_collettive.append(om)
        else:
            esposizioni_altre.append(om)

    # Recto/verso are the work's own front/back; anything else (preparatory stages,
    # installation shots, exhibition documentation...) is clearly separate "additional"
    # material — mixing them undistinguished was exactly the complaint.
    immagini_recto_verso, immagini_altre = [], []
    for img in opera.immagini_con_file:
        label = img.tipo_immagine.nome.lower() if img.tipo_immagine else ""
        if "recto" in label or "verso" in label:
            immagini_recto_verso.append(img)
        else:
            immagini_altre.append(img)

    # Prev/next step through published works in the same section, in the model's default
    # (chronological) order — same ordering the browse grid uses, so "next" here matches
    # what you'd hit moving forward through that section's grid.
    siblings = list(
        Opera.objects.filter(pubblicata=True, tipo_opera=opera.tipo_opera)
        .values_list("numero_scheda", flat=True)
    )
    prev_opera = next_opera = None
    if numero_scheda in siblings:
        idx = siblings.index(numero_scheda)
        if idx > 0:
            prev_opera = Opera.objects.filter(numero_scheda=siblings[idx - 1]).first()
        if idx < len(siblings) - 1:
            next_opera = Opera.objects.filter(numero_scheda=siblings[idx + 1]).first()

    # Chronological, matching the reference scheda — RiferimentoBibliografico's default
    # ordering is by fonte (effectively by author), which scrambles the publication timeline.
    bibliografia = sorted(
        opera.bibliografia.all(),
        key=lambda cit: (cit.fonte.anno or 0, _mese_ordine(cit.fonte.data_pubblicazione), cit.pk),
    )

    return render(
        request,
        "catalogo/opera_detail.html",
        {
            "opera": opera,
            "prev_opera": prev_opera,
            "next_opera": next_opera,
            "esposizioni_personali": esposizioni_personali,
            "esposizioni_collettive": esposizioni_collettive,
            "esposizioni_altre": esposizioni_altre,
            "immagini_recto_verso": immagini_recto_verso,
            "immagini_altre": immagini_altre,
            "bibliografia": bibliografia,
        },
    )
