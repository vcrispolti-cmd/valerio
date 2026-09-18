from django.contrib import admin

from .models import (
    Collezione,
    FonteBibliografica,
    Immagine,
    Mostra,
    MostraSede,
    Opera,
    OperaMostra,
    RiferimentoBibliografico,
    Sede,
    TipoCollezione,
    TipoEsposizione,
    TipoFonteBibliografica,
    TipoImmagine,
    TipoOpera,
    TipoRiferimentoInFonte,
)


class ImmagineInline(admin.TabularInline):
    model = Immagine
    extra = 1
    fields = ("file", "tipo_immagine", "descrizione", "ordine_visualizzazione", "eliminata")


class BibliografiaInline(admin.TabularInline):
    model = RiferimentoBibliografico
    extra = 1
    autocomplete_fields = ["fonte"]
    fields = ("fonte", "pagina", "tavola", "numero_riproduzione", "note", "da_verificare")


class OperaMostraInline(admin.TabularInline):
    model = OperaMostra
    extra = 1
    autocomplete_fields = ["mostra_sede"]
    fields = ("mostra_sede", "numero_catalogo", "note", "da_verificare")


@admin.register(Opera)
class OperaAdmin(admin.ModelAdmin):
    list_display = ("numero_archivio", "titolo", "tipo_opera", "anno_testo", "pubblicata")
    list_filter = ("tipo_opera", "pubblicata", "collezione__tipo")
    search_fields = ("numero_archivio", "numero_scheda", "titolo", "tecnica")
    autocomplete_fields = ["collezione"]
    inlines = [ImmagineInline, BibliografiaInline, OperaMostraInline]
    fieldsets = (
        (None, {"fields": ("numero_archivio", "numero_scheda", "titolo", "tipo_opera", "pubblicata")}),
        ("Datazione", {"fields": ("anno_testo", ("anno_inizio", "anno_fine"))}),
        ("Tecnica e dimensioni", {
            "fields": (
                "tecnica", "supporto",
                ("altezza", "larghezza", "profondita", "diametro", "unita_misura"),
                "dimensioni_note",
            ),
        }),
        ("Collezione e provenienza", {"fields": ("collezione", "collocazione", "provenienza")}),
        ("Firma, iscrizioni e conservazione", {
            "fields": ("firma", "iscrizioni", "stato_conservazione", "note"),
            "classes": ("collapse",),
        }),
    )


class MostraSedeInline(admin.TabularInline):
    model = MostraSede
    extra = 1
    autocomplete_fields = ["sede"]


@admin.register(Mostra)
class MostraAdmin(admin.ModelAdmin):
    list_display = ("titolo", "anno_testo", "tipo_esposizione", "da_verificare")
    list_filter = ("tipo_esposizione", "da_verificare")
    search_fields = ("titolo", "curatore")
    inlines = [MostraSedeInline]


class OperaMostraInlineForMostraSede(admin.TabularInline):
    model = OperaMostra
    extra = 1
    autocomplete_fields = ["opera"]
    fields = ("opera", "numero_catalogo", "note", "da_verificare")


@admin.register(MostraSede)
class MostraSedeAdmin(admin.ModelAdmin):
    """Standalone page per exhibition venue-stop — this is where you record which works
    were shown at that specific stop (OperaMostra links here, not to Mostra directly)."""

    list_display = ("mostra", "sede", "ordine")
    search_fields = ("mostra__titolo", "sede__nome")
    autocomplete_fields = ["mostra", "sede"]
    inlines = [OperaMostraInlineForMostraSede]


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nome", "citta", "paese")
    search_fields = ("nome", "citta", "istituzione")


@admin.register(FonteBibliografica)
class FonteBibliograficaAdmin(admin.ModelAdmin):
    list_display = ("titolo", "autore", "anno", "tipo_pubblicazione")
    search_fields = ("titolo", "autore", "editore")
    list_filter = ("tipo_pubblicazione",)


@admin.register(Collezione)
class CollezioneAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "citta", "paese")
    list_filter = ("tipo",)
    search_fields = ("nome", "citta")


for lookup_model in (
    TipoOpera, TipoEsposizione, TipoCollezione, TipoImmagine,
    TipoFonteBibliografica, TipoRiferimentoInFonte,
):
    admin.site.register(lookup_model)
