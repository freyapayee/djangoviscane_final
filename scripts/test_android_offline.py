"""Export safety and executable parity checks for the offline numeric port."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from scripts.export_android_offline import JAVA, PROJECT, generate_rules, package, read_rules


class AndroidOfflineTests(unittest.TestCase):
    def test_exported_numeric_contract_matches_backend(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viscane.settings")
        if importlib.util.find_spec("django") is None:
            self.skipTest("Install project requirements for backend parity")
        import django
        django.setup()
        from core.services import predict_variety_metrics
        rules = read_rules()
        constants = rules["constants"]
        for variety in constants["SRA_BASELINE_LKG_TC"]:
            for stage in (1, 2, 3):
                for infection in (0, 1):
                    for maturity in (None, "NOT_MATURE", "MATURE", "OVER_MATURE"):
                        for hectares in (0.5, 1.0, 2.5):
                            inputs = {"rssi": infection, "weeding": 2, "fertilizer": 3,
                                      "ratoon": stage, "plowing": 1}
                            expected = predict_variety_metrics(variety, hectares, [0.9], inputs,
                                custom_weights=rules["calculator_weights"], cv_maturity_status=maturity)
                            penalty = sum(min(0, inputs[k] * rules["calculator_weights"][k])
                                          for k in constants["AGRONOMIC_KEYS"])
                            adjustment = constants["CV_MATURITY_BASELINE_WEIGHTS"][variety].get(maturity, 0)
                            multiplier = max(0, 1 + penalty + adjustment)
                            lkg = constants["SRA_BASELINE_LKG_TC"][variety][stage] * multiplier
                            tons = constants["SRA_BASELINE_TC_HA"][variety][stage] * hectares * multiplier
                            self.assertAlmostEqual(lkg, expected["predicted_lkg_tc"])
                            self.assertAlmostEqual(tons, expected["predicted_tc_ha"])
                            self.assertAlmostEqual(lkg * tons, expected["predicted_lkg"])

    def test_export_contains_only_public_source(self):
        with tempfile.TemporaryDirectory() as directory:
            output = package(Path(directory) / "android.zip")
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertIn("viscane-offline/app/src/main/AndroidManifest.xml", names)
                self.assertIn("viscane-offline/app/src/main/java/com/viscane/offline/OfflineRules.java", names)
                for name in names:
                    self.assertFalse(any(token in name for token in (
                        ".env", ".sqlite", ".private", "local.properties", "uploads", ".jks", ".pem")))
                bundle = json.loads(archive.read("viscane-offline/app/src/main/assets/offline-rules.json"))
                self.assertEqual(bundle["image_inference_available"], read_rules()["image_inference_available"])
                self.assertEqual(bundle, json.loads(json.dumps(read_rules())))

    def test_generated_rules_are_current(self):
        before = (JAVA / "OfflineRules.java").read_bytes()
        generate_rules()
        self.assertEqual(before, (JAVA / "OfflineRules.java").read_bytes())

    def test_java_matches_backend(self):
        java_home = Path(os.environ.get("JAVA_HOME", "/nonexistent"))
        java = str(java_home / "bin/java") if (java_home / "bin/java").exists() else shutil.which("java")
        if not java:
            self.skipTest("Java runtime not installed; parity requires a full JDK")
        compiler = subprocess.run([java, "--list-modules"], capture_output=True, text=True)
        if compiler.returncode or "jdk.compiler@" not in compiler.stdout:
            self.skipTest("JDK compiler unavailable; set JAVA_HOME to a full JDK")
        # Import the real Django service, but never connect to the database.
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viscane.settings")
        if importlib.util.find_spec("django") is None:
            self.skipTest("Install project requirements to compare against Django")
        import django
        django.setup()
        from core.services import predict_variety_metrics
        rules = generate_rules()
        cases = []
        for v, variety in enumerate(rules["constants"]["SRA_BASELINE_LKG_TC"]):
            for stage in (1, 2, 3):
                for infection in (0, 1):
                    for maturity, label in enumerate((None, "NOT_MATURE", "MATURE", "OVER_MATURE")):
                        for hectares in (0.5, 1.0, 2.5):
                            for count in (1, 2, 3):
                                result = predict_variety_metrics(variety, hectares, [0.9],
                                    {"rssi": infection, "weeding": count, "fertilizer": count,
                                     "ratoon": stage, "plowing": count},
                                    custom_weights=rules["calculator_weights"], cv_maturity_status=label)
                                cases.append("check(%d, %s, %d, %d, %s, %d, %s, %s, %s);" % (
                                    v, hectares, count, stage, str(bool(infection)).lower(), maturity,
                                    result["predicted_lkg_tc"], result["predicted_tc_ha"], result["predicted_lkg"]))
        source = '''package com.viscane.offline;
public class ParityCheck {
  static void equal(double actual, double expected) {
    if (Math.abs(actual - expected) > 1e-8 * Math.max(1, Math.abs(expected)))
      throw new AssertionError(actual + " != " + expected);
  }
  static void check(int v, double ha, int count, int stage, boolean infected,
      int maturity, double lkg, double tons, double total) {
    OfflineCalculator.Result r = OfflineCalculator.calculate(v, ha, count, count, count, stage, infected, maturity);
    equal(r.lkgPerTon, lkg); equal(r.totalTons, tons); equal(r.totalLkg, total);
  }
  static void invalid(int v, double ha, int count, int stage, int maturity) {
    try { OfflineCalculator.calculate(v, ha, count, count, count, stage, false, maturity); }
    catch (IllegalArgumentException expected) { return; }
    throw new AssertionError("Invalid input accepted");
  }
  public static void main(String[] args) {
    CASES
    invalid(-1, 1, 1, 1, 0); invalid(3, 1, 1, 1, 0);
    invalid(0, 0, 1, 1, 0); invalid(0, -1, 1, 1, 0);
    invalid(0, Double.NaN, 1, 1, 0); invalid(0, Double.POSITIVE_INFINITY, 1, 1, 0);
    invalid(0, Double.MAX_VALUE, 1, 1, 0);
    invalid(0, 1, 0, 1, 0); invalid(0, 1, 4, 1, 0);
    invalid(0, 1, 1, 0, 0); invalid(0, 1, 1, 4, 0);
    invalid(0, 1, 1, 1, -1); invalid(0, 1, 1, 1, 4);
  }
}'''.replace("CASES", "\n".join(cases))
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "ParityCheck.java"
            harness.write_text(source)
            subprocess.run([java, "com.sun.tools.javac.Main", "-d", directory,
                            str(JAVA / "OfflineCalculator.java"), str(JAVA / "OfflineRules.java"),
                            str(harness)], check=True, capture_output=True, text=True)
            subprocess.run([java, "-cp", directory, "com.viscane.offline.ParityCheck"],
                           check=True, capture_output=True, text=True)
        print(f"Verified {len(cases)} Java predictions against Django, plus invalid inputs")


if __name__ == "__main__":
    unittest.main()
