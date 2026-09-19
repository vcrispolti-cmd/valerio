"""
Data model for the "Catalogo Ragionato" section.

Kept in sync with Di_Cocco_Archivio.accdb (re-synced 2026-09: the source database was
substantially rebuilt since the first pass — Bibliografia became RiferimentiBibliografici
with the duplicated FontiBibliografiche columns removed, OpereMostre now links to a specific
exhibition venue-stop (MostraSede) rather than the exhibition as a whole, and soft-delete
(Eliminata) tracking was added across several tables).

Two kinds of fields live here:
- Access-sourced fields: named and shaped to match the source table directly.
- Website-only additions (clearly marked below): TipoOpera and Collezione/TipoCollezione
  don't exist in Access yet — they fill a gap flagged early in this project (Access has no
  work-category/section field and no structured collection/owner table). Kept as Django-side
  additions, editable from the admin, until/unless they're added to the source database too.

T_F06_RisultatiRicerca (an Access-internal cached search-results table backing one of its
own forms) is deliberately not modeled — it's UI plumbing for Access, not catalog data, and
the Django site has its own filtering (see filters.py).
"""
from django.db import models


class LegacyIdMixin(models.Model):
    """Carries the original Access primary key, so the import script can safely re-run
    (update_or_create keyed on legacy_id) instead of duplicating rows on every run.
    Null for records that only ever exist on the website side (the Tipo*/Collezione
    website-only additions)."""

    legacy_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class OrderedLookup(LegacyIdMixin, models.Model):
    """Base for small controlled-vocabulary tables (mirrors the Tipo_* tables in Access)."""

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
    """Website-only: top-level category powering the catalog's section split. Not in Access."""

    slug = models.SlugField(max_length=50, unique=True)

    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo opera"
        verbose_name_plural = "Tipi opera (sezioni del catalogo) — solo sito"


class TipoEsposizione(LegacyIdMixin, models.Model):
    """Mirrors Access's Tipo_Esposizione (only 3 values: Personale/Collettiva/Da verificare)."""

    nome = models.CharField("Tipo esposizione", max_length=100, unique=True)
    normalizzato = models.CharField("Tipo esposizione (normalizzato)", max_length=255, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Tipo esposizione"
        verbose_name_plural = "Tipi esposizione"

    def __str__(self):
        return self.nome


class TipoImmagine(OrderedLookup):
    """Mirrors Access's Tipo_Immagine."""

    descrizione_tipo = models.CharField(max_length=255, blank=True)

    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo immagine"
        verbose_name_plural = "Tipi immagine"


class TipoFonteBibliografica(OrderedLookup):
    """Mirrors Access's Tipo_Fonte_Bibliografica (pick-list for FonteBibliografica.tipo_pubblicazione)."""

    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo fonte bibliografica"
        verbose_name_plural = "Tipi fonte bibliografica"


class TipoRiferimentoInFonte(OrderedLookup):
    """Mirrors Access's Tipo_Riferimento_in_Fonte. Not currently linked to a field on any
    other table in the source — preserved for completeness/future use."""

    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo riferimento in fonte"
        verbose_name_plural = "Tipi riferimento in fonte"


class TipoCollezione(OrderedLookup):
    """Website-only, see module docstring. Not in Access."""

    class Meta(OrderedLookup.Meta):
        verbose_name = "Tipo collezione"
        verbose_name_plural = "Tipi collezione — solo sito"


class Collezione(models.Model):
    """Website-only, see module docstring. Not in Access — Opere.Collocazione stays free text."""

    nome = models.CharField("Nome collezione", max_length=255)
    tipo = models.ForeignKey(TipoCollezione, on_delete=models.PROTECT, null=True, blank=True)
    citta = models.CharField(max_length=255, blank=True)
    paese = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Collezione"
        verbose_name_plural = "Collezioni — solo sito"

    def __str__(self):
        return self.nome


class Sede(LegacyIdMixin, models.Model):
    nome = models.CharField("Nome sede", max_length=255)
    istituzione = models.CharField(max_length=255, blank=True)
    citta = models.CharField(max_length=255, blank=True)
    indirizzo = models.CharField(max_length=255, blank=True)
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


class Mostra(LegacyIdMixin, models.Model):
    """A named exhibition (may span multiple venues via MostraSede)."""

    titolo = models.CharField("Titolo mostra", max_length=500)
    tipo_esposizione = models.ForeignKey(TipoEsposizione, on_delete=models.PROTECT, null=True, blank=True)
    curatore = models.CharField(max_length=500, blank=True)
    data_inizio = models.DateField(null=True, blank=True, help_text="Spesso non ancora compilata: vedi anno_testo.")
    data_fine = models.DateField(null=True, blank=True)
    periodo_testo = models.CharField("Periodo (testo)", max_length=255, blank=True)
    anno_testo = models.CharField("Anno (testo)", max_length=50, blank=True)
    da_verificare = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    sedi = models.ManyToManyField(Sede, through="MostraSede", related_name="mostre")

    class Meta:
        ordering = ["anno_testo", "titolo"]
        verbose_name = "Mostra"
        verbose_name_plural = "Mostre"

    def __str__(self):
        return f"{self.titolo} ({self.anno_testo})" if self.anno_testo else self.titolo


class MostraSede(LegacyIdMixin, models.Model):
    """Join table: one venue-stop of an exhibition. OperaMostra links to this, not to Mostra
    directly, so the catalog can record exactly which stop of a touring show a work appeared in."""

    mostra = models.ForeignKey(Mostra, on_delete=models.CASCADE)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT)
    data_inizio_sede = models.CharField("Data inizio (testo)", max_length=255, blank=True)
    data_fine_sede = models.CharField("Data fine (testo)", max_length=255, blank=True)
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordine"]
        verbose_name = "Sede della mostra"
        verbose_name_plural = "Sedi della mostra"
        unique_together = ("mostra", "sede")

    def __str__(self):
        return f"{self.mostra} @ {self.sede}"


class FonteBibliografica(LegacyIdMixin, models.Model):
    """A publication/source — the single source of truth for author/title/publisher data."""

    tipo_fonte = models.CharField(max_length=100, blank=True)
    tipo_pubblicazione = models.ForeignKey(
        TipoFonteBibliografica, on_delete=models.PROTECT, null=True, blank=True,
    )
    autore = models.TextField(blank=True)
    curatore = models.TextField(blank=True)
    contributi = models.TextField(blank=True)
    titolo = models.TextField()
    titolo_variante = models.TextField(blank=True)
    titolo_periodico = models.CharField(max_length=255, blank=True)
    numero_periodico = models.CharField(max_length=100, blank=True)
    volume = models.CharField(max_length=100, blank=True)
    editore = models.CharField(max_length=255, blank=True)
    luogo = models.CharField(max_length=255, blank=True)
    anno = models.IntegerField(null=True, blank=True)
    data_pubblicazione = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["autore", "anno"]
        verbose_name = "Fonte bibliografica"
        verbose_name_plural = "Fonti bibliografiche"

    def __str__(self):
        anno = f", {self.anno}" if self.anno else ""
        return f"{self.autore or self.editore} — {self.titolo}{anno}"


class Opera(LegacyIdMixin, models.Model):
    """A single work — the core catalog record."""

    numero_scheda = models.CharField(max_length=100, blank=True)
    numero_archivio = models.CharField(
        "Numero di archivio", max_length=100, unique=True,
        help_text="Identificativo permanente dell'opera, usato anche nell'URL pubblico.",
    )
    titolo = models.TextField()
    tipo_opera = models.ForeignKey(
        TipoOpera, on_delete=models.PROTECT, related_name="opere",
        help_text="Sezione del catalogo — campo solo sito, non presente in Access.",
    )

    anno_testo = models.CharField("Anno (testo)", max_length=50, blank=True, help_text="Es. \"1965 ca.\"")
    anno_inizio = models.PositiveIntegerField(
        null=True, blank=True, db_index=True,
        help_text="Campo solo sito (Access ha solo 'Anno' come testo libero) — usato per il filtro per anno.",
    )
    anno_fine = models.PositiveIntegerField(null=True, blank=True)

    tecnica = models.TextField(blank=True)
    supporto = models.CharField(max_length=255, blank=True)

    altezza = models.FloatField(null=True, blank=True)
    larghezza = models.FloatField(null=True, blank=True)
    profondita = models.FloatField(null=True, blank=True)
    diametro = models.FloatField(null=True, blank=True)
    unita_misura = models.CharField(max_length=20, blank=True)
    dimensioni_note = models.TextField(blank=True)

    firma = models.TextField(blank=True)
    iscrizioni = models.TextField(blank=True)
    stato_conservazione = models.CharField(max_length=255, blank=True)

    collezione = models.ForeignKey(
        Collezione, on_delete=models.SET_NULL, null=True, blank=True, related_name="opere",
        help_text="Campo solo sito — Access ha solo il testo libero 'collocazione'.",
    )
    collocazione = models.TextField(blank=True)
    provenienza = models.TextField(blank=True)
    note = models.TextField(blank=True)

    pubblicata = models.BooleanField(
        default=False,
        help_text="Solo le opere pubblicate compaiono sul sito pubblico.",
    )

    mostre_sedi = models.ManyToManyField(MostraSede, through="OperaMostra", related_name="opere")
    fonti = models.ManyToManyField(FonteBibliografica, through="RiferimentoBibliografico", related_name="opere")

    class Meta:
        ordering = ["anno_testo", "numero_archivio"]
        verbose_name = "Opera"
        verbose_name_plural = "Opere"

    def __str__(self):
        return f"{self.numero_archivio} — {self.titolo}"

    @property
    def immagini_con_file(self):
        """Images that actually have a file attached — many imported Immagine rows don't yet
        (the Access file only records the original filename/path, not the file itself)."""
        return self.immagini.exclude(file="")

    @property
    def immagine_principale(self):
        return self.immagini_con_file.first()

    @property
    def dimensioni_display(self):
        parts = [v for v in (self.altezza, self.larghezza, self.profondita) if v]
        if not parts:
            return self.dimensioni_note
        dims = " x ".join(str(v).rstrip("0").rstrip(".") if "." in str(v) else str(v) for v in parts)
        unit = self.unita_misura or "cm"
        return f"{unit} {dims}"


class Immagine(LegacyIdMixin, models.Model):
    opera = models.ForeignKey(Opera, on_delete=models.CASCADE, related_name="immagini")
    tipo_immagine = models.ForeignKey(TipoImmagine, on_delete=models.PROTECT, null=True, blank=True)
    file = models.ImageField(
        upload_to="opere/%Y/", blank=True,
        help_text="La cartella immagini di Access non è dentro il file .accdb — questo campo "
        "resta vuoto finché il file corrispondente non viene individuato e collegato.",
    )
    nome_file = models.CharField(max_length=255, blank=True, help_text="Nome file originale (riferimento di importazione).")
    percorso_relativo = models.CharField(max_length=255, blank=True, help_text="Percorso originale in Access (riferimento di importazione).")
    segni_particolari = models.TextField(blank=True)
    stato_verifica = models.CharField(max_length=100, blank=True)
    descrizione = models.TextField(blank=True)
    note = models.TextField(blank=True)
    ordine_visualizzazione = models.PositiveIntegerField(default=0)

    eliminata = models.BooleanField(default=False)
    data_eliminazione = models.DateTimeField(null=True, blank=True)
    eliminata_da = models.CharField(max_length=255, blank=True)
    motivo_eliminazione = models.TextField(blank=True)

    class Meta:
        ordering = ["ordine_visualizzazione", "id"]
        verbose_name = "Immagine"
        verbose_name_plural = "Immagini"

    def __str__(self):
        return f"Immagine {self.ordine_visualizzazione} — {self.opera.numero_archivio}"


class OperaMostra(LegacyIdMixin, models.Model):
    """Join table: which works were shown at which exhibition venue-stop."""

    opera = models.ForeignKey(Opera, on_delete=models.CASCADE)
    mostra_sede = models.ForeignKey(
        MostraSede, on_delete=models.CASCADE, verbose_name="Sede della mostra",
    )
    collocazione_in_fonte = models.TextField(blank=True)
    numero_catalogo = models.CharField(max_length=100, blank=True)
    titolo_alternativo = models.TextField(blank=True)
    da_verificare = models.BooleanField(default=False)
    note = models.TextField(blank=True)

    eliminata = models.BooleanField(default=False)
    data_eliminazione = models.DateTimeField(null=True, blank=True)
    motivo_eliminazione = models.TextField(blank=True)

    class Meta:
        ordering = ["mostra_sede"]
        verbose_name = "Opera in mostra"
        verbose_name_plural = "Opere in mostra"
        # No unique_together on (opera, mostra_sede) — the real data has a couple of
        # legitimate cases of the same work appearing twice at one venue-stop.

    def __str__(self):
        return f"{self.opera.numero_archivio} @ {self.mostra_sede}"


class RiferimentoBibliografico(LegacyIdMixin, models.Model):
    """Work-specific citation (Access: RiferimentiBibliografici). Author/title/publisher data
    lives only on FonteBibliografica — this table deliberately does not repeat it."""

    opera = models.ForeignKey(Opera, on_delete=models.CASCADE, related_name="bibliografia")
    fonte = models.ForeignKey(FonteBibliografica, on_delete=models.PROTECT, related_name="citazioni")
    nome_opera_citata = models.CharField(
        max_length=500, blank=True,
        help_text="Se la fonte cita l'opera con un titolo diverso da quello corrente.",
    )
    pagina = models.CharField(max_length=100, blank=True)
    tavola = models.CharField(max_length=100, blank=True)
    numero_riproduzione = models.CharField(max_length=100, blank=True)
    sala = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    da_verificare = models.BooleanField(default=False)

    eliminata = models.BooleanField(default=False)
    data_eliminazione = models.DateTimeField(null=True, blank=True)
    motivo_eliminazione = models.TextField(blank=True)

    class Meta:
        ordering = ["fonte"]
        verbose_name = "Riferimento bibliografico"
        verbose_name_plural = "Riferimenti bibliografici"
        # No unique_together on (opera, fonte) — the real data legitimately cites the same
        # source multiple times for the same work (different pages/plates): 93 of 254
        # distinct (opera, fonte) pairs have more than one citation row.

    def __str__(self):
        return f"{self.opera.numero_archivio} — {self.fonte}"
