# Di Cocco — Access database build kit

This folder builds a full Microsoft Access application for the
"Di_Cocco_Database_Schede_1913-1934" catalog: 129 works, one record each,
plus a data-entry form, an advanced boolean search form, and two reports
(a tabular one with thumbnails and a one-page-per-record "word-like" catalog
card report).

## Why a build kit instead of a finished .accdb file

This was generated from a Linux cloud session with no Windows and no
Microsoft Access installed, so there is no way to author a real `.accdb`
binary directly. Instead, this kit gives you everything Access itself needs
to build the real thing on your own PC in one pass: your actual data
(already extracted from the spreadsheet) plus VBA code that creates the
tables, imports the data, and builds the forms/reports using Access's own
object model. Every button and event on the generated forms/reports calls a
plain public VBA function (`=RunSearch()`, `=RefreshFormImages()`, etc.) —
nothing is written into a form's own class module, so you do **not** need to
enable "Trust access to the VBA project object model".

## What's in here

```
data/
  DiCocco_Data.dat            <- the actual data (129 records), used by ImportData
  DiCocco_Data_preview.csv    <- same data, human-readable, for your reference only
vba/
  01_modSchema.bas             creates tables Opere + Config, and qryOpereOrdinate
  02_modImportData.bas         imports data/DiCocco_Data.dat into Opere
  03_modImageHelpers.bas       shared image-handling logic used by forms/reports
  04_modBuildForm_Edit.bas     builds frmOpereEdit (data entry, all fields incl. images)
  05_modBuildReport_Tabella.bas builds rptTabella (landscape grid + thumbnails)
  06_modBuildReport_Schede.bas builds rptSchede (one catalog "scheda" per page)
  07_modBuildForm_Search.bas   builds frmRicercaAvanzata (boolean multi-field search)
  08_modMain.bas               RunAll orchestrator + frmMenu switchboard
```

The data came from your Google Drive copy of the spreadsheet (both its
sheets: "Database opere" and "Testo grezzo schede", merged one row per work).
The `Immagine recto/verso/laterale` and `Illustrazione 1-3` columns were
empty in the source file (headers only, no filenames), so images are **not**
pre-linked — you attach them per record after the build, see step 5 below.
Neither the `DiCoccoImmagini_Schede` folder nor the reference PDF were
reachable from this session, so the "Schede" report layout is my own design
inspired by a typical museum catalog card rather than a copy of your PDF —
easy to adjust once you can show me the PDF or describe changes.

## Build steps (on your Windows PC, in Access)

1. **Copy this whole `DiCoccoAccessDB` folder** to your PC, anywhere you like
   (e.g. `Documents\DiCoccoAccessDB`). Keep `data/` next to where you'll save
   the `.accdb` — `ImportData` looks for `data\DiCocco_Data.dat` relative to
   the database file's own folder.

2. Open Access and create a **new blank desktop database**. Save it directly
   inside `DiCoccoAccessDB` (next to the `data` folder), e.g. as
   `DiCocco.accdb`.

3. Open the VBA editor (**Alt+F11**). For each of the 8 files in `vba/`, use
   **File > Import File...** and import them in order (01 through 08). You
   should end up with 8 standard modules in the Project Explorer.

4. If your `.accdb` isn't saved directly inside `DiCoccoAccessDB` (next to
   `data/`), `ImportData` will pop up a file picker so you can browse
   straight to `DiCocco_Data.dat` wherever you put it — you don't have to
   match the folder layout exactly.

5. Open the Immediate window (**Ctrl+G**), type:
   ```
   RunAll
   ```
   and press Enter. This creates the tables, imports all 129 records,
   builds both forms and both reports, and opens a menu. A message box
   confirms completion — if something goes wrong partway through, it tells
   you which step failed with the exact Access error, so you can fix that
   one piece (or send me the exact message).

   You can re-run any single step from the Immediate window too, e.g.
   `BuildEditForm` or `BuildSchedeReport`, if you only need to rebuild one
   piece after a tweak.

6. **Link the images.** On the menu, click **"Imposta cartella immagini..."**
   and point it at your `DiCoccoImmagini_Schede` folder. Then open
   **"Inserisci / modifica schede"**, navigate to each record (arrows at the
   bottom of the form), and click the **"Sfoglia..."** button under each
   image slot (Recto, Verso, Laterale, Illustrazione 1-3) to pick that
   record's image file. If the file lives inside the folder you configured,
   only the relative filename is stored, so the database stays portable.

## The four deliverables

- **frmOpereEdit** — every field is editable, including all six image slots
  with a live preview and a "Sfoglia..." (Browse) button each. Standard
  Access navigation buttons at the bottom let you add/delete records.
- **rptTabella** — landscape, one row per record, columns in the same order
  as the original Excel plus a recto thumbnail on the left.
- **rptSchede** — one page per work: title, images (recto/verso/laterale,
  auto-centered based on which exist), technical metadata in two columns,
  then Provenienza / Esposizioni personali / Esposizioni collettive /
  Bibliografia / Note as clearly labeled sections that only appear when
  they have content, and grow to fit however much text each record has.
- **frmRicercaAvanzata** — up to 5 search rows, each picking a field, an
  operator (Contiene / Uguale a / Inizia con / Vuoto / Non vuoto), and a
  value; each row after the first has an E/O (AND/OR) selector combining it
  with everything above it. Results appear in a list; you can open the
  selected record for editing, or print either report limited to just the
  matching set.

## Design choices worth knowing about

- **One flat table**, not a normalized schema. Bibliografia, Esposizioni
  personali/collettive, Note etc. are memo fields holding the same
  multi-line text blocks the Excel had, rather than separate one-row-per-
  citation tables. This keeps the tabular report a faithful mirror of the
  Excel and keeps the search form simple. If you'd rather search/browse
  individual exhibitions or bibliography entries one at a time, that's a
  reasonable follow-up (child tables + a subform) — just ask.
- The advanced search evaluates rows strictly left to right (no
  parentheses/precedence beyond that), which covers "boolean search across
  all fields" for the vast majority of real queries without a much more
  complex UI.
- `NumeroScheda` (the original `N.` column) is shown read-only on the edit
  form since it's the record's identity from the source spreadsheet.

## If something breaks on first run

I couldn't test any of this against real Access (no Windows/Access in this
build environment), so treat the first `RunAll` as a first draft. The code
traps errors at each step and reports the exact Access error number/message
and which `Build...`/`Create...`/`Import...` sub it happened in — send me
that and I can fix it quickly, since these are near-mechanical adjustments
(a typo'd control name, a property that needs a slightly different value
in your Access version, etc.).
