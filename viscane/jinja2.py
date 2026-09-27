"""Jinja2 environment helpers for Django."""

from urllib.parse import urlencode

from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment
from core.language import HILIGAYNON_LABELS, farmer_summary, farmer_text, is_hiligaynon


def url_for(endpoint, **values):
    if endpoint == "static":
        filename = values.pop("filename", "")
        path = static(filename)
        if values:
            return f"{path}?{urlencode(values, doseq=True)}"
        return path

    try:
        return reverse(endpoint, kwargs=values or None)
    except Exception:
        path = reverse(endpoint)
        if values:
            return f"{path}?{urlencode(values, doseq=True)}"
        return path


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        url_for=url_for,
        farmer_text=farmer_text,
        farmer_summary=farmer_summary,
        is_hiligaynon=is_hiligaynon,
        farmer_catalog=lambda: HILIGAYNON_LABELS if is_hiligaynon() else {},
    )
    return env
