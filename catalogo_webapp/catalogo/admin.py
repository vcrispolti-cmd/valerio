from django.contrib import admin

from .models import (
    Bibliografia,
    Collezione,
    FonteBibliografica,
    Immagine,
    Mostra,
    MostraSede,
    Opera,
    OperaMostra,
    Sede,
    TipoCollezione,
    TipoImmagine,
    TipoMostra,
    TipoOpera,
)


class ImmagineInline(admin.TabularInline):
    model = Immagine
    extra = 1
    fields = ("file", "tipo_immagine", "didascalia", "ordine_visualizzazione")


class BibliografiaInline(admin.TabularInline):
    model = Bibliografia
    extra = 1
    autocomplete_fields = ["fonte"]
    fields = ("fonte", "riferimento_pagine", "riferimento_tavola", "riprodotto", "note")


class OperaMostraInline(admin.TabularInline):
    model = OperaMostra
    extra = 1
    autocomplete_fields = ["mostra"]
    fields = ("mostra", "sala", "numero_catalogo", "nota")


@admin.register(Opera)
class OperaAdmin(admin.ModelAdmin):
    list_display = ("numero_archivio", "titolo", "tipo_opera", "anno_testo", "pubblicata")
    list_filter = ("tipo_opera", "pubblicata", "collezione__tipo")
    search_fields = ("numero_archivio", "titolo", "tecnica")
    autocomplete_fields = ["collezione"]
    inlines = [ImmagineInline, BibliografiaInline, OperaMostraInline]
    fieldsets = (
        (None, {"fields": ("numero_archivio", "titolo", "tipo_opera", "pubblicata")}),
        ("Datazione", {"fields": ("anno_testo", "anno_inizio", "anno_fine")}),
        ("Tecnica e dimensioni", {
            "fields": (
                "tecnica", "dimensioni_testo",
                ("altezza_cm", "larghezza_cm", "profondita_cm", "diametro_cm"),
            ),
        }),
        ("Collezione e provenienza", {"fields": ("collezione", "provenienza")}),
        ("Segni e note", {"fields": ("segni_recto", "segni_verso", "note"), "classes": ("collapse",)}),
    )


class MostraSedeInline(admin.TabularInline):
    model = MostraSede
    extra = 1
    autocomplete_fields = ["sede"]


class OperaMostraInlineForMostra(admin.TabularInline):
    model = OperaMostra
    extra = 1
    autocomplete_fields = ["opera"]
    fields = ("opera", "sala", "numero_catalogo", "nota")


@admin.register(Mostra)
class MostraAdmin(admin.ModelAdmin):
    list_display = ("titolo", "anno_inizio", "anno_fine", "tipo_mostra")
    list_filter = ("tipo_mostra",)
    search_fields = ("titolo", "curatore")
    inlines = [MostraSedeInline, OperaMostraInlineForMostra]


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nome", "citta", "paese")
    search_fields = ("nome", "citta", "paese")


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


for lookup_model in (TipoOpera, TipoMostra, TipoCollezione, TipoImmagine):
    admin.site.register(lookup_model)
