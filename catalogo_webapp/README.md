# Catalogo Ragionato — Francesco Di Cocco

Django project for the "Catalogo Ragionato" section: browsable/filterable work records
with exhibition and bibliography subforms, modeled on the structure of
fondazionepaolini.it/ita/catalogo-ragionato.

Scope: the catalog module only (works, exhibitions, bibliography, images) — not a full
site with biography/news pages. See the app's `catalogo/models.py` docstring for why the
schema deliberately diverges from the source Access database (Di_Cocco_Archivio.accdb):
staging/parsing/audit tables that existed to work around Access's weak relational
data-entry UX aren't ported, since Django admin's inline forms solve that directly.

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

## Not done yet (next steps)

1. **Data import** — a one-time script to migrate cleaned data out of
   `Di_Cocco_Archivio.accdb` into these models (per the earlier redundancy-cleanup
   checklist: don't port `Z_TMP_GalleriaImmagini`, the duplicate `Dimensioni_Originale`
   column, or the superseded `Z_TMP_Esposizioni_Parse*` tables).
2. **Production settings** — `SECRET_KEY` from an environment variable, `DEBUG=False`,
   real `ALLOWED_HOSTS`, Postgres instead of SQLite, `gunicorn`/`whitenoise` added to
   requirements.
3. **Deployment** — Dockerfile + docker-compose (Nginx + Gunicorn + Postgres) for the
   Aruba Cloud VPS (or equivalent), plus Certbot for HTTPS.
