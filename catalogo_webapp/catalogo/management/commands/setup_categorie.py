"""
Set up the catalog's real section taxonomy: Pittura, Disegno, Scultura, Arti applicate,
Cinema — replacing the placeholder "Dipinti"/"Opere su carta" categories that seed_demo.py
created early on, before the real classification scheme was settled.

Usage:
    python manage.py setup_categorie

Safe to re-run: every category is get_or_create'd by slug. Existing works keep whatever
tipo_opera they're already assigned — this command only makes sure the five real categories
exist and are visible in the public nav, and makes sure "Da classificare" (the import's
default holding bucket for anything not yet reviewed) stays out of the public nav without
deleting it, since works may still be pointing at it.

Re-assigning the 129 imported works into these categories is a curatorial decision, not
something this command guesses at — do that from /admin/ (or ask for a proposed mapping
based on the Tecnica field, reviewed before applying).
"""
from django.core.management.base import BaseCommand

from catalogo.models import TipoOpera

CATEGORIE = [
    ("pittura", "Pittura", 1),
    ("disegno", "Disegno", 2),
    ("scultura", "Scultura", 3),
    ("arti-applicate", "Arti applicate", 4),
    ("cinema", "Cinema", 5),
]


class Command(BaseCommand):
    help = "Creates/updates the real TipoOpera section taxonomy and hides 'Da classificare' from the public nav."

    def handle(self, *args, **options):
        for slug, nome, ordine in CATEGORIE:
            obj, created = TipoOpera.objects.update_or_create(
                slug=slug, defaults={"nome": nome, "ordine": ordine, "attivo": True},
            )
            self.stdout.write(f"{'creata' if created else 'aggiornata'}: {obj.nome} ({obj.slug})")

        da_classificare, _ = TipoOpera.objects.get_or_create(
            slug="da-classificare", defaults={"nome": "Da classificare", "ordine": 999},
        )
        if da_classificare.attivo:
            da_classificare.attivo = False
            da_classificare.save(update_fields=["attivo"])
            self.stdout.write("'Da classificare' nascosta dalla navigazione pubblica (resta visibile/assegnabile in admin).")

        for old_slug in ("dipinti", "opere-su-carta"):
            old = TipoOpera.objects.filter(slug=old_slug).first()
            if old and old.opere.exists():
                self.stdout.write(self.style.WARNING(
                    f"Attenzione: '{old.nome}' ({old_slug}) ha ancora {old.opere.count()} opere assegnate — "
                    f"riassegnale a una delle nuove categorie da /admin/, poi puoi disattivarla o eliminarla."
                ))
