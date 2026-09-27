import re
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.template.loader import get_template
from django.test import RequestFactory
from django.utils.translation import override

from .language import (
    PROTECTED_TERMS,
    RECOMMENDATION_GUIDES,
    RECOMMENDATION_META,
    farmer_summary,
    farmer_text,
    translate_recommendations,
)


class FarmerLanguageTests(SimpleTestCase):
    def test_language_switch_and_agronomic_values(self):
        response = self.client.post("/i18n/setlang/", {"language": "hil", "next": "/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.cookies["django_language"].value, "hil")

        with override("hil"):
            self.assertEqual(farmer_text("Home"), "Balik sa Una")
            self.assertEqual(farmer_text("Number of Plowing"), "Pila ka beses nag-arado")
            self.assertEqual(farmer_text("Maturity"), "Maturity sang Tubo")
            self.assertEqual(farmer_text("Maturity:"), "Maturity sang Tubo:")
            self.assertEqual(farmer_text("Estimated LKG"), "Ginabanta nga LKG")
            for status in ("Mature", "Not Mature", "Over Mature"):
                self.assertEqual(farmer_text(status), status)
        with override("en"):
            self.assertEqual(farmer_text("Home"), "Home")

    def test_offline_recommendations_preserve_original_and_numbers(self):
        source = [{
            "title": "Consider 3-time fertilizer application for VMC 84-524",
            "meta": "3-Time: First at planting, second after 1-2 months, third at 3-4 months.",
            "tag": "Upgrade",
            "category": "Fertilizer Guidance",
        }]
        with override("hil"), patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""}):
            result = translate_recommendations(source)
            self.assertIn("pag-abono", result[0]["title"])
            self.assertIn("3 ka beses", result[0]["meta"])
            self.assertEqual(result[0]["original_title"], source[0]["title"])
            self.assertEqual(result[0]["original_meta"], source[0]["meta"])
            self.assertEqual(source[0]["title"], "Consider 3-time fertilizer application for VMC 84-524")
            self.assertIn("pag-abono", farmer_summary("Fertilizer Guidance: " + source[0]["title"]))

    def test_farmer_form_keeps_machine_values_with_hiligaynon_labels(self):
        request = RequestFactory().get("/homepage")
        request.session = {}
        context = {"request": request, "user": SimpleNamespace(fullname="Test Farmer")}
        with override("hil"):
            html = get_template("homepage.html").render(context, request)
        self.assertIn('data-value="1st Ratoon"', html)
        self.assertIn("Una nga ratoon", html)
        self.assertIn('value="Less than 1 Hectares"', html)
        self.assertIn("Kulang sa 1 ka ektarya", html)
        self.assertIn("Katukma:", html)
        self.assertIn("Balik sa Una", html)

    def test_farmer_results_show_estimate_note_in_selected_language(self):
        request = RequestFactory().get("/calculate-results")
        request.session = {}
        context = {"request": request, "user": SimpleNamespace(fullname="Test Farmer")}
        with override("en"):
            english = get_template("calculate_results.html").render(context, request)
        with override("hil"):
            hiligaynon = get_template("calculate_results.html").render(context, request)
        self.assertIn("Important Note:", english)
        self.assertIn("Exact sugar content and quality require laboratory testing.", english)
        self.assertIn("Actual yield is confirmed after harvest and weighing.", english)
        self.assertIn("Importante nga Pahibalo:", hiligaynon)
        self.assertIn("Mga ginabanta lamang ini nga resulta.", hiligaynon)
        self.assertIn("pag-usisa sa laboratoryo", hiligaynon)

    def test_farming_guide_translations_preserve_numbers_and_named_terms(self):
        for source, translation in {**RECOMMENDATION_GUIDES, **RECOMMENDATION_META}.items():
            with self.subTest(source=source):
                numbers = lambda value: sorted(re.findall(r"\d+(?:[.,]\d+)?", value))
                self.assertEqual(numbers(source), numbers(translation))
                for term in PROTECTED_TERMS:
                    if term.lower() in source.lower():
                        self.assertIn(term.lower(), translation.lower())

    def test_deepseek_only_fills_unknown_advice_and_rejects_changed_numbers(self):
        source = [{"title": "Check plot 18", "meta": "Return in 12 days.", "tag": "New tag"}]
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=(
            '{"items":[{"title":"Susiaha ang uma 19",'
            '"meta":"Balik sa 12 ka adlaw.","tag":"Bag-o"}]}'
        )))])
        with override("hil"), patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only"}):
            with patch("openai.OpenAI") as client:
                client.return_value.chat.completions.create.return_value = response
                result = translate_recommendations(source)
        self.assertEqual(result[0]["title"], source[0]["title"])
        self.assertEqual(result[0]["meta"], "Balik sa 12 ka adlaw.")
        self.assertEqual(result[0]["original_meta"], source[0]["meta"])
