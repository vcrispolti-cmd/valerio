"""
Data model for the "Catalogo Ragionato" section.

Deliberately a cleaned-up version of the Access schema (Di_Cocco_Archivio.accdb),
not a 1:1 port: staging/parsing/audit tables from Access existed to work around
Access's weak relational data-entry UX. Django admin's inline forms solve that
natively, so this model only carries the tables that represent final, public data.
"""
from django.db import models


class OrderedLookup(models.Model):
    """Base for small controlled-vocabulary tables (mirrors the T_* tables in Access)."""

    nome = models.CharField(max_length=255, unique=True)
    ordine = models.PositiveIntegerField(default=0)
    attivo = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


class TipoOpera(OrderedLookup):
    """Top-level category — powers the catalog's section split (e.g. Dipinti / Opere su carta / Edizioni)."""

    slug = models.SlugField(max_length=50, unique=True)

    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo opera"
        verbose_name_plural = "Tipi opera (sezioni del catalogo)"


class TipoMostra(OrderedLookup):
    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo mostra"
        verbose_name_plural = "Tipi mostra"


class TipoCollezione(OrderedLookup):
    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo collezione"
        verbose_name_plural = "Tipi collezione"


class TipoImmagine(OrderedLookup):
    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo immagine"
        verbose_name_plural = "Tipi immagine"


class Collezione(models.Model):
    nome = models.CharField("Nome collezione", max_length=255)
    tipo = models.ForeignKey(TipoCollezione, on_delete=models.PROTECT, null=True, blank=True)
    citta = models.CharField(max_length=255, blank=True)
    paese = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Collezione"
        verbose_name_plural = "Collezioni"

    def __str__(self):
        return self.nome


class Sede(models.Model):
    """Exhibition venue."""

    nome = models.CharField("Nome sede", max_length=255)
    citta = models.CharField(max_length=255, blank=True)
    provincia = models.CharField(max_length=255, blank=True)
    regione = models.CharField(max_length=255, blank=True)
    paese = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Sede"
        verbose_name_plural = "Sedi"

    def __str__(self):
        return f"{self.nome} ({self.citta})" if self.citta else self.nome


class Mostra(models.Model):
    """A named exhibition (may span multiple venues via MostraSede)."""

    titolo = models.CharField("Titolo mostra", max_length=500)
    tipo_mostra = models.ForeignKey(TipoMostra, on_delete=models.PROTECT, null=True, blank=True)
    anno_inizio = models.PositiveIntegerField(null=True, blank=True)
    anno_fine = models.PositiveIntegerField(null=True, blank=True)
    data_testo = models.CharField("Date (testo)", max_length=255, blank=True)
    curatore = models.CharField(max_length=500, blank=True)
    note = models.TextField(blank=True)
    sedi = models.ManyToManyField(Sede, through="MostraSede", related_name="mostre")

    class Meta:
        ordering = ["-anno_inizio", "titolo"]
        verbose_name = "Mostra"
        verbose_name_plural = "Mostre"

    def __str__(self):
        anno = self.anno_inizio or ""
        return f"{self.titolo} ({anno})" if anno else self.titolo


class MostraSede(models.Model):
    """Join table: which venues hosted a given exhibition, and in what order."""

    mostra = models.ForeignKey(Mostra, on_delete=models.CASCADE)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT)
    ordine = models.PositiveIntegerField(default=0)
    ruolo_sede = models.CharField(max_length=100, blank=True)
    sala_sezione = models.CharField(max_length=255, blank=True)
    nota = models.TextField(blank=True)

    class Meta:
        ordering = ["ordine"]
        verbose_name = "Sede della mostra"
        verbose_name_plural = "Sedi della mostra"
        unique_together = ("mostra", "sede")

    def __str__(self):
        return f"{self.mostra} @ {self.sede}"


class FonteBibliografica(models.Model):
    """A publication/source — the single source of truth for author/title/publisher data."""

    tipo_fonte = models.CharField(max_length=100, blank=True)
    tipo_pubblicazione = models.CharField(max_length=100, blank=True)
    autore = models.TextField(blank=True)
    curatore = models.TextField(blank=True)
    contributi = models.TextField(blank=True)
    titolo = models.TextField()
    titolo_periodico = models.CharField(max_length=255, blank=True)
    editore = models.CharField(max_length=255, blank=True)
    luogo = models.CharField(max_length=255, blank=True)
    anno = models.CharField(max_length=20, blank=True)
    volume = models.CharField(max_length=100, blank=True)
    numero_periodico = models.CharField(max_length=100, blank=True)
    isbn = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["autore", "anno"]
        verbose_name = "Fonte bibliografica"
        verbose_name_plural = "Fonti bibliografiche"

    def __str__(self):
        anno = f", {self.anno}" if self.anno else ""
        return f"{self.autore or self.editore} — {self.titolo}{anno}"


class Opera(models.Model):
    """A single work — the core catalog record."""

    numero_archivio = models.CharField(
        "Numero di archivio", max_length=100, unique=True,
        help_text="Identificativo permanente dell'opera (es. FDC-0001), usato anche nell'URL pubblico.",
    )
    titolo = models.TextField()
    tipo_opera = models.ForeignKey(
        TipoOpera, on_delete=models.PROTECT, related_name="opere",
        help_text="Sezione del catalogo (dipinti/sculture, opere su carta, edizioni...).",
    )

    anno_testo = models.CharField("Anno (testo)", max_length=50, blank=True, help_text="Es. \"1965 ca.\"")
    anno_inizio = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    anno_fine = models.PositiveIntegerField(null=True, blank=True)

    tecnica = models.TextField(blank=True)

    dimensioni_testo = models.CharField(max_length=255, blank=True, help_text="Es. \"cm 67 x 49\"")
    altezza_cm = models.FloatField(null=True, blank=True)
    larghezza_cm = models.FloatField(null=True, blank=True)
    profondita_cm = models.FloatField(null=True, blank=True)
    diametro_cm = models.FloatField(null=True, blank=True)

    collezione = models.ForeignKey(
        Collezione, on_delete=models.SET_NULL, null=True, blank=True, related_name="opere",
    )
    provenienza = models.TextField(blank=True)
    segni_recto = models.TextField("Segni e iscrizioni (recto)", blank=True)
    segni_verso = models.TextField("Segni e iscrizioni (verso)", blank=True)
    note = models.TextField(blank=True)

    pubblicata = models.BooleanField(
        default=False,
        help_text="Solo le opere pubblicate compaiono sul sito pubblico.",
    )

    mostre = models.ManyToManyField(Mostra, through="OperaMostra", related_name="opere")
    fonti = models.ManyToManyField(FonteBibliografica, through="Bibliografia", related_name="opere")

    class Meta:
        ordering = ["anno_inizio", "numero_archivio"]
        verbose_name = "Opera"
        verbose_name_plural = "Opere"

    def __str__(self):
        return f"{self.numero_archivio} — {self.titolo}"


class Immagine(models.Model):
    opera = models.ForeignKey(Opera, on_delete=models.CASCADE, related_name="immagini")
    tipo_immagine = models.ForeignKey(TipoImmagine, on_delete=models.PROTECT, null=True, blank=True)
    file = models.ImageField(upload_to="opere/%Y/")
    didascalia = models.CharField(max_length=500, blank=True)
    descrizione = models.TextField(blank=True)
    ordine_visualizzazione = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordine_visualizzazione", "id"]
        verbose_name = "Immagine"
        verbose_name_plural = "Immagini"

    def __str__(self):
        return f"Immagine {self.ordine_visualizzazione} — {self.opera.numero_archivio}"


class OperaMostra(models.Model):
    """Join table: which works were shown in which exhibitions."""

    opera = models.ForeignKey(Opera, on_delete=models.CASCADE)
    mostra = models.ForeignKey(Mostra, on_delete=models.CASCADE)
    sala = models.CharField(max_length=100, blank=True)
    numero_catalogo = models.CharField(max_length=100, blank=True)
    nota = models.TextField(blank=True)

    class Meta:
        ordering = ["mostra"]
        verbose_name = "Opera in mostra"
        verbose_name_plural = "Opere in mostra"
        unique_together = ("opera", "mostra")

    def __str__(self):
        return f"{self.opera.numero_archivio} @ {self.mostra}"


class Bibliografia(models.Model):
    """Work-specific citation. Author/title/publisher data lives only on FonteBibliografica."""

    opera = models.ForeignKey(Opera, on_delete=models.CASCADE, related_name="bibliografia")
    fonte = models.ForeignKey(FonteBibliografica, on_delete=models.PROTECT, related_name="citazioni")
    riferimento_pagine = models.CharField(max_length=255, blank=True)
    riferimento_tavola = models.CharField(max_length=255, blank=True)
    riferimento_numero = models.CharField(max_length=255, blank=True)
    riprodotto = models.BooleanField(default=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["fonte"]
        verbose_name = "Riferimento bibliografico"
        verbose_name_plural = "Bibliografia"
        unique_together = ("opera", "fonte")

    def __str__(self):
        return f"{self.opera.numero_archivio} — {self.fonte}"
