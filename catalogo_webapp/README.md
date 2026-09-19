# Catalogo Ragionato — Francesco Di Cocco

Django project for the "Catalogo Ragionato" section: browsable/filterable work records
with exhibition and bibliography subforms, modeled on the structure of
fondazionepaolini.it/ita/catalogo-ragionato.

Scope: the catalog module only (works, exhibitions, bibliography, images) — not a full
site with biography/news pages. See the app's `catalogo/models.py` docstring for the
current mapping to the source Access database (Di_Cocco_Archivio.accdb) and which fields
are website-only additions (`TipoOpera`, `Collezione`/`TipoCollezione`, `Opera.anno_inizio`/
`anno_fine`) not yet present in Access. The source database was substantially restructured
in September 2026 (Bibliografia → RiferimentiBibliografici with duplicated fields removed,
OpereMostre now keys off a specific exhibition venue-stop via MostraSede, soft-delete
tracking added) — these models reflect that current structure, not the original one.

## Running locally

```bash
cd catalogo_webapp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for the public catalog, `/admin/` to add works,
exhibitions, and bibliography (the replacement for the Access forms).

Optional: `python manage.py seed_demo` populates a couple of demo records so the
pages aren't empty before real data is imported.

## Project layout

- `catalogo/models.py` — the data model (Opera, Mostra, Sede, FonteBibliografica,
  Bibliografia, Immagine, Collezione, plus lookup tables for controlled vocabularies)
- `catalogo/admin.py` — admin config with inline subforms (this is the day-to-day
  data-entry tool)
- `catalogo/views.py` + `catalogo/filters.py` — public site: category landing,
  filterable browse grid, work detail page
- `catalogo/templates/catalogo/` — templates (minimal gallery-style layout)

## Importing data from Access

```bash
python manage.py import_access /path/to/Di_Cocco_Archivio.accdb --dry-run   # preview, nothing saved
python manage.py import_access /path/to/Di_Cocco_Archivio.accdb            # commit
```

Requires `mdb-export` on PATH (`apt-get install mdbtools` / `brew install mdbtools`) — that's
the only thing that talks to the `.accdb` file directly.

Safe to re-run as often as you like as Access data keeps changing: every row carries the
original Access ID (`legacy_id`) and gets upserted, not re-inserted. Two exceptions on
purpose — `Opera.tipo_opera` (category) and `Opera.pubblicata` are only set the first time a
work is created, so re-importing never undoes categorization or publishing done from the
website admin. Newly-imported works default to a "Da classificare" category and
`pubblicata=False` until reviewed.

Real image files aren't inside the `.accdb` (Access only stores the original filename/path)
— pass `--images-dir /path/to/images` to attach files found there, matched against the
recorded path/filename; otherwise `Immagine` rows are created without a file and picked up
by a later pass.

Full details and the field-by-field mapping are in
`catalogo/management/commands/import_access.py`.

## Not done yet (next steps)

1. **Curatorial review** — every imported work starts as "Da classificare" and unpublished;
   assigning real categories and flipping `pubblicata` is a manual pass in the admin (or a
   follow-up script if there's a reliable rule to derive category from existing fields).
2. **Attaching real image files** — via `--images-dir` once the image folder is available.
3. **Production settings** — `SECRET_KEY` from an environment variable, `DEBUG=False`,
   real `ALLOWED_HOSTS`, Postgres instead of SQLite, `gunicorn`/`whitenoise` added to
   requirements.
4. **Deployment** — Dockerfile + docker-compose (Nginx + Gunicorn + Postgres) for the
   Aruba Cloud VPS (or equivalent), plus Certbot for HTTPS.
