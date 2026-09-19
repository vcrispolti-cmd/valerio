from datetime import date

import django_filters
from django import forms
from django.db.models import Max, Min

from .models import Opera


class OperaFilter(django_filters.FilterSet):
    """Powers the combined-filter search on the browse page."""

    anno_da = django_filters.NumberFilter(
        field_name="anno_inizio", lookup_expr="gte", label="Anno da",
        widget=forms.NumberInput(attrs={"placeholder": "es. 1960"}),
    )
    anno_a = django_filters.NumberFilter(
        field_name="anno_fine", lookup_expr="lte", label="Anno a",
        widget=forms.NumberInput(attrs={"placeholder": "es. 1970"}),
    )
    tecnica = django_filters.CharFilter(
        field_name="tecnica", lookup_expr="icontains", label="Tecnica",
    )
    q = django_filters.CharFilter(method="filter_search", label="Cerca nel titolo")

    class Meta:
        model = Opera
        fields = ["tipo_opera", "anno_da", "anno_a", "tecnica", "q"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bound the year inputs to the years actually present, instead of letting the
        # browser's number-input spinner start from 0/1 — set on every request since the
        # real min/max shifts as new works get a year assigned.
        years = Opera.objects.aggregate(min_anno=Min("anno_inizio"), max_anno=Max("anno_fine"))
        year_min = years["min_anno"]
        year_max = years["max_anno"] or date.today().year
        if year_min is not None:
            self.form.fields["anno_da"].widget.attrs.update({
                "min": year_min, "max": year_max, "placeholder": f"es. {year_min}",
            })
            self.form.fields["anno_a"].widget.attrs.update({
                "min": year_min, "max": year_max, "placeholder": f"es. {year_max}",
            })

    def filter_search(self, queryset, name, value):
        return queryset.filter(titolo__icontains=value)
