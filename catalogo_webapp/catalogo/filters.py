import django_filters
from django import forms

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

    def filter_search(self, queryset, name, value):
        return queryset.filter(titolo__icontains=value)
