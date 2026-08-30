from .models import TipoOpera


def sezioni_nav(request):
    """Makes the section list available in the header nav on every page."""
    return {"sezioni_nav": TipoOpera.objects.filter(attivo=True)}
