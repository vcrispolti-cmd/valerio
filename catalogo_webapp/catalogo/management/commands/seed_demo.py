"""Seeds a handful of demo records so the site can be smoke-tested before real data is imported."""
from django.core.management.base import BaseCommand

from catalogo.models import (
    Bibliografia,
    FonteBibliografica,
    Mostra,
    MostraSede,
    Opera,
    OperaMostra,
    Sede,
    TipoMostra,
    TipoOpera,
)


class Command(BaseCommand):
    help = "Seeds minimal demo data for local smoke-testing."

    def handle(self, *args, **options):
        dipinti, _ = TipoOpera.objects.get_or_create(
            slug="dipinti", defaults={"nome": "Dipinti", "ordine": 1}
        )
        carta, _ = TipoOpera.objects.get_or_create(
            slug="opere-su-carta", defaults={"nome": "Opere su carta", "ordine": 2}
        )

        personale, _ = TipoMostra.objects.get_or_create(nome="Mostra personale")

        opera1, _ = Opera.objects.update_or_create(
            numero_archivio="FDC-0001",
            defaults=dict(
                titolo="Paesaggio con figure",
                tipo_opera=dipinti,
                anno_testo="1965 ca.",
                anno_inizio=1965,
                anno_fine=1965,
                tecnica="Olio su tela",
                dimensioni_testo="cm 60 x 80",
                altezza_cm=60,
                larghezza_cm=80,
                pubblicata=True,
            ),
        )
        Opera.objects.update_or_create(
            numero_archivio="FDC-0002",
            defaults=dict(
                titolo="Studio per ritratto",
                tipo_opera=carta,
                anno_testo="1972",
                anno_inizio=1972,
                anno_fine=1972,
                tecnica="Matita su carta",
                dimensioni_testo="cm 21 x 29",
                pubblicata=True,
            ),
        )

        sede, _ = Sede.objects.get_or_create(nome="Galleria Comunale", citta="Pescara")
        mostra, _ = Mostra.objects.get_or_create(
            titolo="Francesco Di Cocco — Antologica",
            defaults=dict(tipo_mostra=personale, anno_inizio=1980, anno_fine=1980),
        )
        MostraSede.objects.get_or_create(mostra=mostra, sede=sede)
        OperaMostra.objects.get_or_create(opera=opera1, mostra=mostra, defaults={"sala": "I"})

        fonte, _ = FonteBibliografica.objects.get_or_create(
            titolo="Francesco Di Cocco. Catalogo generale",
            defaults=dict(autore="M. Rossi", editore="Edizioni Arte", luogo="Roma", anno="1999"),
        )
        Bibliografia.objects.get_or_create(
            opera=opera1, fonte=fonte, defaults={"riferimento_pagine": "45", "riprodotto": True}
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
