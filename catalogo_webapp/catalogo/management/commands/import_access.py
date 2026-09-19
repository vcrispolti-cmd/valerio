"""
Import Di_Cocco_Archivio.accdb into the Django models.

Usage:
    python manage.py import_access /path/to/Di_Cocco_Archivio.accdb
    python manage.py import_access /path/to/Di_Cocco_Archivio.accdb --dry-run
    python manage.py import_access /path/to/Di_Cocco_Archivio.accdb --images-dir /path/to/images
    python manage.py import_access /path/to/Di_Cocco_Archivio.accdb --only opere,immagini

Requires `mdb-export` on PATH (part of mdbtools): `apt-get install mdbtools` (Linux) or
`brew install mdbtools` (Mac). Nothing else talks to the .accdb file directly — every table
is read once via mdb-export and parsed as CSV.

Safe to re-run: every table it writes to carries a `legacy_id` (the original Access primary
key), and rows are upserted with `update_or_create(legacy_id=...)` rather than blindly
inserted, so re-running after new Access edits updates existing rows instead of duplicating
them. Two exceptions, deliberately: `Opera.tipo_opera` (category) and `Opera.pubblicata`
(publication flag) are only set the first time a work is created — these are curatorial
decisions made on the website, and a re-run must not clobber them just because Access has no
equivalent field to compare against.

Images are never required to be present at import time. Every Immagine row with a Nome_File
gets Immagine.file pointed at media/immagini/<Nome_File> by reference only (no bytes read, no
existence check) — this is what makes the resulting database portable: it can be copied to any
machine, and the site works as soon as the real image files are dropped (flat, original
filenames) into that machine's media/immagini/ folder. --images-dir is only for physically
copying files into media/opere/%Y/ when they're already sitting locally at import time.

T_F06_RisultatiRicerca is not imported — see the note in models.py.

Import order follows FK dependencies: lookups -> Sedi -> FontiBibliografiche -> Mostre ->
Opere -> Immagini -> MostreSedi -> OpereMostre -> RiferimentiBibliografici.
"""
import csv
import io
import re
import shutil
import subprocess
from datetime import datetime

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from catalogo.models import (
    FonteBibliografica,
    Immagine,
    Mostra,
    MostraSede,
    Opera,
    OperaMostra,
    RiferimentoBibliografico,
    Sede,
    TipoEsposizione,
    TipoFonteBibliografica,
    TipoImmagine,
    TipoOpera,
    TipoRiferimentoInFonte,
)

YEAR_RANGE_RE = re.compile(r"(\d{4})\s*[-/]\s*(\d{2,4})")
SINGLE_YEAR_RE = re.compile(r"(\d{4})")
ACCESS_DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{2})\s")


class DryRunRollback(Exception):
    """Raised at the end of a --dry-run to force the outer transaction to roll back."""


def parse_bool(value):
    return (value or "").strip() in ("1", "-1", "True", "true", "Yes")


def parse_int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_float(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_year_range(text):
    """'1913-16' -> (1913, 1916); '1923-1926' -> (1923, 1926); '1917' -> (1917, 1917).

    The 2-digit end-year form assumes the same century as the start year — correct for this
    archive (an early/mid-20th-century Italian artist), and cheap to spot-check: every
    multi-year Opere.Anno value in the source follows this pattern.
    """
    text = (text or "").strip()
    if not text:
        return None, None
    m = YEAR_RANGE_RE.search(text)
    if m:
        y1 = int(m.group(1))
        g2 = m.group(2)
        y2 = int(g2) if len(g2) == 4 else (y1 // 100) * 100 + int(g2)
        if y2 < y1:
            y2 += 100
        return y1, y2
    m = SINGLE_YEAR_RE.search(text)
    if m:
        y = int(m.group(1))
        return y, y
    return None, None


def parse_access_date(text):
    """mdb-export renders Access DateTime as 'MM/DD/YY HH:MM:SS'. Python's %y would read
    a 2-digit year as 2000-2068/1969-1999 (POSIX rule) which is wrong for this archive's
    historical dates (e.g. '49' must be 1949, not 2049) — so the century is fixed at 1900
    explicitly rather than relying on strptime's guess.
    """
    text = (text or "").strip()
    if not text:
        return None
    m = ACCESS_DATE_RE.match(text)
    if not m:
        return None
    mm, dd, yy = (int(g) for g in m.groups())
    try:
        return datetime(1900 + yy, mm, dd).date()
    except ValueError:
        return None


class Stats:
    def __init__(self):
        self.counts = {}
        self.warnings = []

    def bump(self, table, kind):
        key = (table, kind)
        self.counts[key] = self.counts.get(key, 0) + 1

    def warn(self, message):
        self.warnings.append(message)

    def report(self, stdout):
        tables = sorted({t for t, _ in self.counts})
        for table in tables:
            created = self.counts.get((table, "created"), 0)
            updated = self.counts.get((table, "updated"), 0)
            skipped = self.counts.get((table, "skipped"), 0)
            stdout.write(f"  {table:28s} created={created:<5} updated={updated:<5} skipped={skipped}")
        if self.warnings:
            stdout.write(f"\n{len(self.warnings)} warning(s):")
            for w in self.warnings[:200]:
                stdout.write(f"  - {w}")
            if len(self.warnings) > 200:
                stdout.write(f"  ... and {len(self.warnings) - 200} more")


def mdb_export(accdb_path, table):
    result = subprocess.run(
        ["mdb-export", accdb_path, table],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise CommandError(f"mdb-export failed for table {table!r}: {result.stderr.strip()}")
    return list(csv.DictReader(io.StringIO(result.stdout)))


def resolve_or_create_lookup(model, text, stats, table_label):
    text = (text or "").strip()
    if not text:
        return None
    obj = model.objects.filter(nome__iexact=text).first()
    if obj:
        return obj
    obj = model.objects.create(nome=text)
    stats.warn(f"{table_label}: valore '{text}' non presente tra i tipi noti — creato al volo")
    return obj


class Command(BaseCommand):
    help = "Import Di_Cocco_Archivio.accdb into the catalog models."

    def add_arguments(self, parser):
        parser.add_argument("accdb_path")
        parser.add_argument("--dry-run", action="store_true", help="Roll back at the end; nothing is saved.")
        parser.add_argument(
            "--images-dir", default=None,
            help="Optional local folder mirroring Access's Percorso_Relativo. If a matching file "
                 "is found there, it is physically copied into Immagine.file (media/opere/%%Y/). "
                 "Every Immagine row with a Nome_File always gets a reference to "
                 "media/immagini/<Nome_File> regardless of --images-dir, so the site works once "
                 "someone drops the real files into that folder — no re-import needed, and the "
                 "database itself never needs to carry the image bytes to be portable.",
        )
        parser.add_argument(
            "--only", default=None,
            help="Comma-separated subset of stages to run (lookups,sedi,fonti,mostre,opere,"
                 "immagini,mostre_sedi,opere_mostre,riferimenti). Mainly for iterative testing — "
                 "skipping a prerequisite stage on an empty database just yields zero rows "
                 "downstream, it won't crash.",
        )

    def handle(self, *args, **options):
        if not shutil.which("mdb-export"):
            raise CommandError(
                "mdb-export not found on PATH. Install mdbtools: "
                "`apt-get install mdbtools` (Linux) or `brew install mdbtools` (Mac)."
            )

        accdb_path = options["accdb_path"]
        images_dir = options["images_dir"]
        only = set(options["only"].split(",")) if options["only"] else None
        stats = Stats()

        stages = [
            ("lookups", self.import_lookups),
            ("sedi", self.import_sedi),
            ("fonti", self.import_fonti),
            ("mostre", self.import_mostre),
            ("opere", self.import_opere),
            ("immagini", self.import_immagini),
            ("mostre_sedi", self.import_mostre_sedi),
            ("opere_mostre", self.import_opere_mostre),
            ("riferimenti", self.import_riferimenti),
        ]

        try:
            with transaction.atomic():
                for name, fn in stages:
                    if only and name not in only:
                        continue
                    self.stdout.write(f"-- {name} --")
                    if name == "immagini":
                        fn(accdb_path, stats, images_dir)
                    else:
                        fn(accdb_path, stats)

                if options["dry_run"]:
                    raise DryRunRollback()
        except DryRunRollback:
            self.stdout.write(self.style.WARNING("\nDRY RUN — rolled back, nothing was saved.\n"))
        else:
            self.stdout.write(self.style.SUCCESS("\nImport committed.\n"))

        stats.report(self.stdout)

    # ------------------------------------------------------------------
    # Lookup tables
    # ------------------------------------------------------------------
    def import_lookups(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "Tipo_Esposizione"):
            _, created = TipoEsposizione.objects.update_or_create(
                legacy_id=parse_int(row["ID_TipoEsposizione"]),
                defaults=dict(nome=row["Tipo_Esposizione"], normalizzato=row.get("Tipo_Esposizione_Normalizzato") or ""),
            )
            stats.bump("Tipo_Esposizione", "created" if created else "updated")

        for row in mdb_export(accdb_path, "Tipo_Immagine"):
            _, created = TipoImmagine.objects.update_or_create(
                legacy_id=parse_int(row["ID_TipoImmagine"]),
                defaults=dict(
                    nome=row["Tipo_Immagine"],
                    descrizione_tipo=row.get("Descrizione_Tipo") or "",
                    ordine=parse_int(row.get("Ordine_Visualizzazione")) or 0,
                    attivo=parse_bool(row.get("Attivo")),
                    note=row.get("Note") or "",
                ),
            )
            stats.bump("Tipo_Immagine", "created" if created else "updated")

        for row in mdb_export(accdb_path, "Tipo_Fonte_Bibliografica"):
            _, created = TipoFonteBibliografica.objects.update_or_create(
                legacy_id=parse_int(row["ID"]),
                defaults=dict(
                    nome=row["Tipo_Pubblicazione"],
                    ordine=parse_int(row.get("Ordine")) or 0,
                    attivo=parse_bool(row.get("Attivo")),
                    note=row.get("Note") or "",
                ),
            )
            stats.bump("Tipo_Fonte_Bibliografica", "created" if created else "updated")

        for row in mdb_export(accdb_path, "Tipo_Riferimento_in_Fonte"):
            _, created = TipoRiferimentoInFonte.objects.update_or_create(
                legacy_id=parse_int(row["ID"]),
                defaults=dict(
                    nome=row["Tipo_Fonte"],
                    ordine=parse_int(row.get("Ordine")) or 0,
                    attivo=parse_bool(row.get("Attivo")),
                    note=row.get("Note") or "",
                ),
            )
            stats.bump("Tipo_Riferimento_in_Fonte", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_sedi(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "Sedi"):
            _, created = Sede.objects.update_or_create(
                legacy_id=parse_int(row["ID_Sede"]),
                defaults=dict(
                    nome=row["Nome_Sede"] or "",
                    istituzione=row.get("Istituzione") or "",
                    citta=row.get("Citta") or "",
                    indirizzo=row.get("Indirizzo") or "",
                    provincia=row.get("Provincia") or "",
                    regione=row.get("Regione") or "",
                    paese=row.get("Paese") or "",
                    note=row.get("Note_Sede") or "",
                ),
            )
            stats.bump("Sedi", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_fonti(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "FontiBibliografiche"):
            tipo_pubblicazione = resolve_or_create_lookup(
                TipoFonteBibliografica, row.get("Tipo_Pubblicazione"), stats, "FontiBibliografiche.Tipo_Pubblicazione"
            )
            _, created = FonteBibliografica.objects.update_or_create(
                legacy_id=parse_int(row["ID_Fonte"]),
                defaults=dict(
                    tipo_fonte=row.get("Tipo_Fonte") or "",
                    tipo_pubblicazione=tipo_pubblicazione,
                    autore=row.get("Autore") or "",
                    curatore=row.get("Curatore") or "",
                    contributi=row.get("Contributi") or "",
                    titolo=row.get("Titolo") or "",
                    titolo_variante=row.get("Titolo_Variante") or "",
                    titolo_periodico=row.get("Titolo_Periodico") or "",
                    numero_periodico=row.get("Numero_Periodico") or "",
                    volume=row.get("Volume") or "",
                    editore=row.get("Editore") or "",
                    luogo=row.get("Luogo") or "",
                    anno=parse_int(row.get("Anno")),
                    data_pubblicazione=row.get("Data_Pubblicazione") or "",
                    note=row.get("Note_Fonte") or "",
                ),
            )
            if not row.get("Titolo", "").strip():
                stats.warn(f"FontiBibliografiche ID_Fonte={row['ID_Fonte']}: titolo mancante")
            stats.bump("FontiBibliografiche", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_mostre(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "Mostre"):
            code = parse_int(row.get("Tipo_Mostra"))
            tipo_esposizione = TipoEsposizione.objects.filter(legacy_id=code).first() if code is not None else None
            if code is not None and tipo_esposizione is None:
                stats.warn(f"Mostre ID_Mostra={row['ID_Mostra']}: Tipo_Mostra={code} non trovato in Tipo_Esposizione")

            _, created = Mostra.objects.update_or_create(
                legacy_id=parse_int(row["ID_Mostra"]),
                defaults=dict(
                    titolo=row.get("Titolo_Mostra") or "",
                    tipo_esposizione=tipo_esposizione,
                    curatore=row.get("Curatore") or "",
                    data_inizio=parse_access_date(row.get("Data_Inizio")),
                    data_fine=parse_access_date(row.get("Data_Fine")),
                    periodo_testo=row.get("Periodo_Mostra") or "",
                    anno_testo=row.get("Anno_Mostra") or "",
                    da_verificare=parse_bool(row.get("Da_Verificare")),
                    note=row.get("Note_Mostra") or "",
                ),
            )
            stats.bump("Mostre", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_opere(self, accdb_path, stats):
        default_tipo_opera, _ = TipoOpera.objects.get_or_create(
            slug="da-classificare", defaults={"nome": "Da classificare", "ordine": 999},
        )
        seen_numero_archivio = set(
            Opera.objects.exclude(legacy_id=None).values_list("legacy_id", "numero_archivio")
        )
        existing_na = {na for _, na in seen_numero_archivio}

        for row in mdb_export(accdb_path, "Opere"):
            legacy_id = parse_int(row["ID_Opera"])
            anno_inizio, anno_fine = parse_year_range(row.get("Anno"))

            numero_archivio = (row.get("Numero_Archivio") or "").strip()
            if not numero_archivio:
                numero_archivio = f"SENZA-NUMERO-{legacy_id}"
                stats.warn(f"Opere ID_Opera={legacy_id}: Numero_Archivio mancante, assegnato '{numero_archivio}'")
            elif numero_archivio in existing_na and (legacy_id, numero_archivio) not in seen_numero_archivio:
                original = numero_archivio
                numero_archivio = f"{numero_archivio}-DUP{legacy_id}"
                stats.warn(f"Opere ID_Opera={legacy_id}: Numero_Archivio '{original}' duplicato, reso univoco come '{numero_archivio}'")
            existing_na.add(numero_archivio)

            fields = dict(
                numero_scheda=row.get("Numero_Scheda") or "",
                numero_archivio=numero_archivio,
                titolo=row.get("Titolo") or "",
                anno_testo=row.get("Anno") or "",
                anno_inizio=anno_inizio,
                anno_fine=anno_fine,
                tecnica=row.get("Tecnica") or "",
                supporto=row.get("Supporto") or "",
                altezza=parse_float(row.get("Altezza")),
                larghezza=parse_float(row.get("Larghezza")),
                profondita=parse_float(row.get("Profondita")),
                diametro=parse_float(row.get("Diametro")),
                unita_misura=row.get("Unita_Misura") or "",
                dimensioni_note=row.get("Dimensioni_Note") or "",
                firma=row.get("Firma") or "",
                iscrizioni=row.get("Iscrizioni") or "",
                collocazione=row.get("Collocazione") or "",
                provenienza=row.get("Provenienza") or "",
                note=row.get("Note_Opera") or "",
                stato_conservazione=row.get("Stato_Conservazione") or "",
                # tipo_opera and pubblicata are deliberately NOT here — see module docstring.
            )
            # tipo_opera has no model-level default, so it must be supplied on creation or the
            # INSERT fails its NOT NULL constraint. create_defaults REPLACES defaults entirely
            # on the create path (it does not merge) — so it must carry every field, not just
            # tipo_opera, or a newly-created Opera would come out with only that field set.
            obj, created = Opera.objects.update_or_create(
                legacy_id=legacy_id,
                defaults=fields,
                create_defaults={**fields, "tipo_opera": default_tipo_opera},
            )
            if not row.get("Titolo", "").strip():
                stats.warn(f"Opere ID_Opera={legacy_id}: titolo mancante")
            stats.bump("Opere", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_immagini(self, accdb_path, stats, images_dir):
        for row in mdb_export(accdb_path, "Immagini"):
            opera_legacy_id = parse_int(row.get("ID_Opera"))
            opera = Opera.objects.filter(legacy_id=opera_legacy_id).first()
            if opera is None:
                stats.warn(f"Immagini ID_Immagine={row['ID_Immagine']}: Opera ID_Opera={opera_legacy_id} non trovata, riga saltata")
                stats.bump("Immagini", "skipped")
                continue

            tipo_immagine = resolve_or_create_lookup(TipoImmagine, row.get("Tipo_Immagine"), stats, "Immagini.Tipo_Immagine")

            obj, created = Immagine.objects.update_or_create(
                legacy_id=parse_int(row["ID_Immagine"]),
                defaults=dict(
                    opera=opera,
                    tipo_immagine=tipo_immagine,
                    nome_file=row.get("Nome_File") or "",
                    percorso_relativo=row.get("Percorso_Relativo") or "",
                    segni_particolari=row.get("Segni_Particolari") or "",
                    stato_verifica=row.get("Stato_Verifica") or "",
                    descrizione=row.get("Descrizione_Immagine") or "",
                    note=row.get("Note_Immagine") or "",
                    ordine_visualizzazione=parse_int(row.get("Ordine_Visualizzazione")) or 0,
                    eliminata=parse_bool(row.get("Eliminata")),
                    data_eliminazione=parse_access_date(row.get("Data_Eliminazione")),
                    eliminata_da=row.get("Eliminata_Da") or "",
                    motivo_eliminazione=row.get("Motivo_Eliminazione") or "",
                ),
            )
            stats.bump("Immagini", "created" if created else "updated")

            if not obj.file:
                self._attach_image_file(obj, images_dir, stats)

    def _attach_image_file(self, immagine, images_dir, stats):
        import os

        basename = immagine.nome_file or (
            os.path.basename(immagine.percorso_relativo.replace("\\", "/"))
            if immagine.percorso_relativo else ""
        )
        if not basename:
            stats.warn(f"Immagini legacy_id={immagine.legacy_id}: né Nome_File né Percorso_Relativo valorizzati, nessun riferimento immagine creato")
            return

        if images_dir:
            candidates = [c for c in (immagine.percorso_relativo, immagine.nome_file) if c]
            for rel in candidates:
                candidate_path = os.path.join(images_dir, rel)
                if os.path.isfile(candidate_path):
                    with open(candidate_path, "rb") as fh:
                        immagine.file.save(basename, File(fh), save=True)
                    return

        # Reference-only, no bytes required: points at media/immagini/<basename> without
        # copying or even checking it exists yet. This is what makes the database portable —
        # ship it (or the whole project) without any image files, then drop the real files into
        # media/immagini/ on whatever machine runs the site (matched by original filename) and
        # every reference resolves with no re-import.
        immagine.file.name = f"immagini/{basename}"
        immagine.save(update_fields=["file"])

    # ------------------------------------------------------------------
    def import_mostre_sedi(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "MostreSedi"):
            mostra = Mostra.objects.filter(legacy_id=parse_int(row.get("ID_Mostra"))).first()
            sede = Sede.objects.filter(legacy_id=parse_int(row.get("ID_Sede"))).first()
            if mostra is None or sede is None:
                stats.warn(f"MostreSedi ID_MostraSede={row['ID_MostraSede']}: Mostra o Sede non trovata, riga saltata")
                stats.bump("MostreSedi", "skipped")
                continue

            try:
                with transaction.atomic():
                    _, created = MostraSede.objects.update_or_create(
                        legacy_id=parse_int(row["ID_MostraSede"]),
                        defaults=dict(
                            mostra=mostra,
                            sede=sede,
                            data_inizio_sede=row.get("Data_Inizio_Sede") or "",
                            data_fine_sede=row.get("Data_Fine_Sede") or "",
                            ordine=parse_int(row.get("Ordine_Sede")) or 0,
                        ),
                    )
            except IntegrityError as exc:
                stats.warn(f"MostreSedi ID_MostraSede={row['ID_MostraSede']}: {exc}")
                stats.bump("MostreSedi", "skipped")
                continue
            stats.bump("MostreSedi", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_opere_mostre(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "OpereMostre"):
            opera = Opera.objects.filter(legacy_id=parse_int(row.get("ID_Opera"))).first()
            mostra_sede = MostraSede.objects.filter(legacy_id=parse_int(row.get("ID_MostraSede"))).first()
            if opera is None or mostra_sede is None:
                stats.warn(f"OpereMostre ID_OperaMostra={row['ID_OperaMostra']}: Opera o MostraSede non trovata, riga saltata")
                stats.bump("OpereMostre", "skipped")
                continue

            try:
                with transaction.atomic():
                    _, created = OperaMostra.objects.update_or_create(
                        legacy_id=parse_int(row["ID_OperaMostra"]),
                        defaults=dict(
                            opera=opera,
                            mostra_sede=mostra_sede,
                            collocazione_in_fonte=row.get("Collocazione_In_Fonte") or "",
                            numero_catalogo=row.get("Numero_Catalogo") or "",
                            titolo_alternativo=row.get("Titolo_Opera_Alternativo") or "",
                            da_verificare=parse_bool(row.get("Da_Verificare")),
                            note=row.get("Note_OperaMostre") or "",
                            eliminata=parse_bool(row.get("Eliminata")),
                            data_eliminazione=parse_access_date(row.get("Data_Eliminazione")),
                            motivo_eliminazione=row.get("Motivo_Eliminazione") or "",
                        ),
                    )
            except IntegrityError as exc:
                stats.warn(f"OpereMostre ID_OperaMostra={row['ID_OperaMostra']}: {exc}")
                stats.bump("OpereMostre", "skipped")
                continue
            stats.bump("OpereMostre", "created" if created else "updated")

    # ------------------------------------------------------------------
    def import_riferimenti(self, accdb_path, stats):
        for row in mdb_export(accdb_path, "RiferimentiBibliografici"):
            opera = Opera.objects.filter(legacy_id=parse_int(row.get("ID_Opera"))).first()
            fonte = FonteBibliografica.objects.filter(legacy_id=parse_int(row.get("ID_Fonte"))).first()
            if opera is None or fonte is None:
                stats.warn(f"RiferimentiBibliografici ID_Bibliografia={row['ID_Bibliografia']}: Opera o Fonte non trovata, riga saltata")
                stats.bump("RiferimentiBibliografici", "skipped")
                continue

            try:
                with transaction.atomic():
                    _, created = RiferimentoBibliografico.objects.update_or_create(
                        legacy_id=parse_int(row["ID_Bibliografia"]),
                        defaults=dict(
                            opera=opera,
                            fonte=fonte,
                            nome_opera_citata=row.get("Nome_Opera_Citata") or "",
                            pagina=row.get("Pagina") or "",
                            tavola=row.get("Tavola") or "",
                            numero_riproduzione=row.get("Numero_riproduzione") or "",
                            sala=row.get("Sala") or "",
                            note=row.get("Nota_Bibliografica") or "",
                            da_verificare=parse_bool(row.get("Da_Verificare")),
                            eliminata=parse_bool(row.get("Eliminata")),
                            data_eliminazione=parse_access_date(row.get("Data_Eliminazione")),
                            motivo_eliminazione=row.get("Motivo_Eliminazione") or "",
                        ),
                    )
            except IntegrityError as exc:
                stats.warn(f"RiferimentiBibliografici ID_Bibliografia={row['ID_Bibliografia']}: {exc}")
                stats.bump("RiferimentiBibliografici", "skipped")
                continue
            stats.bump("RiferimentiBibliografici", "created" if created else "updated")
