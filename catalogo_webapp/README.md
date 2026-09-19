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

### Adding the images (portable setup)

This project (and the `db.sqlite3` it ships with, once populated by `import_access`) never
needs to carry the actual image files — they're excluded on purpose so the project stays
small and portable. To make images appear:

1. Inside `catalogo_webapp/`, create a folder at `media/immagini/` if it doesn't exist yet.
2. Copy all the artwork image files into it **flat** (no subfolders), keeping their
   **original filenames** exactly as they came from the source (e.g.
   `006_1919_pa11_recto.jpg`). The database already has every filename recorded — it just
   needs the bytes to show up at that path.
3. That's it — no re-import, no restart needed. Each work's page resolves its image(s) by
   matching filename under `media/immagini/`; whatever isn't there yet just shows the
   "Nessuna immagine" placeholder until you add it.

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

Real image files aren't inside the `.accdb` (Access only stores the original filename/path).
The import never needs them to be present: every `Immagine` row with a filename is pointed at
`media/immagini/<filename>` by reference only — nothing is read or copied at import time. This
is what makes the database portable: the whole project (code + `db.sqlite3`) can be copied to
any machine without the (large) image files, and the site works as soon as the real images are
dropped into that machine's `media/immagini/` folder — flat, using their original filenames
(e.g. `006_1919_pa11_recto.jpg`). No re-import needed.

`--images-dir /path/to/images` is only for the case where you already have the files locally
at import time and want Django to physically copy them into `media/opere/%Y/` instead.

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
