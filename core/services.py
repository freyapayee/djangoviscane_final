from __future__ import annotations

import csv
import json
import os
import secrets
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

from .models import Admin, AgronomicLog, AuditLog, CvScanUpload, Notification, SystemConfig, User


DEFAULT_VARIETY_WEIGHTS = {
    "VMC 84-524": {"rssi": -0.45, "weeding": 0.35, "fertilizer": 0.25, "ratoon": -0.12, "plowing": 0.08},
    "VMC 84-947": {"rssi": -0.45, "weeding": 0.28, "fertilizer": 0.18, "ratoon": -0.05, "plowing": 0.05},
    "MAURITIO RC888": {"rssi": -0.55, "weeding": 0.28, "fertilizer": 0.18, "ratoon": -0.12, "plowing": 0.08},
}

CV_MATURITY_BASELINE_WEIGHTS = {
    "VMC 84-524": {"NOT_MATURE": -0.20, "MATURE": 0.00, "OVER_MATURE": -0.15},
    "VMC 84-947": {"NOT_MATURE": -0.18, "MATURE": 0.00, "OVER_MATURE": -0.22},
    "MAURITIO RC888": {"NOT_MATURE": -0.22, "MATURE": 0.00, "OVER_MATURE": -0.18},
}

SRA_BASELINE_LKG_TC = {
    "VMC 84-524": {1: 2.04, 2: 1.94, 3: 2.40},
    "VMC 84-947": {1: 1.86, 2: 2.14, 3: 2.21},
    "MAURITIO RC888": {1: 2.22, 2: 2.26, 3: 1.99},
}

SRA_BASELINE_TC_HA = {
    "VMC 84-524": {1: 239.0, 2: 165.0, 3: 134.0},
    "VMC 84-947": {1: 285.0, 2: 256.0, 3: 179.0},
    "MAURITIO RC888": {1: 273.06, 2: 250.86, 3: 143.28},
}

CROP_STAGE_LABELS = {
    1: "New Plant (1)",
    2: "1st ratoon (2nd)",
    3: "2nd ratoon (3rd)",
}

AGRONOMIC_KEYS = ["rssi", "weeding", "fertilizer", "ratoon", "plowing"]

VARIETY_ALIASES = {
    "Mauritius RC888": "MAURITIO RC888",
    "MAURITIO RC888": "MAURITIO RC888",
}

CV_VARIETY_ALIASES = {
    "524": "VMC 84-524",
    "VMC 84-524": "VMC 84-524",
    "847": "VMC 84-947",
    "VMC 84-947": "VMC 84-947",
    "MAURITIO": "MAURITIO RC888",
    "MAURITIO RC888": "MAURITIO RC888",
}

FERTILIZER_TIMING_GUIDE = {
    "VMC 84-524": {
        1: "1-Time: Apply all fertilizer at planting or 1 month after planting.",
        2: "2-Time: Half at ~45 days, half at ~3 months before canopy closure. Alternative: first dose 3-4 days after planting, second at 3 months.",
        3: "3-Time: First at planting, second after 1-2 months, third at 3-4 months.",
    },
    "VMC 84-947": {
        1: "1-Time: Apply full fertilizer at planting or right after ratoon starts based on soil test.",
        2: "2-Time: Split into two doses at ~1.5 months and ~3 months before canopy closure.",
        3: "3-Time: Split N and K into 3 equal doses at 30, 60, and 90 days after planting.",
    },
    "MAURITIO RC888": {
        1: "1-Time: Apply full N-P-K at planting.",
        2: "2-Time: Basal dose at planting, then top dress around 3 months.",
        3: "3-Time: Split nitrogen into 3 doses within first 3-4 months, or at 30, 60, and 90 days after planting.",
    },
}

WEEDING_GUIDE = {
    "VMC 84-524": {
        1: "1-Time: Not recommended. Weed pressure can become too high, and glyphosate should be avoided during germination and tillering due to crop sensitivity.",
        2: "2-Time: Acceptable when combined with chemical weeding. Use 2,4-D or Diuron early for safe control.",
        3: "3-Time: Best practice. Combine manual weeding with selective herbicides (2,4-D or Diuron) to keep the field clean and reduce lodging risk.",
    },
    "VMC 84-947": {
        1: "1-Time: Not recommended. A single weeding is not enough for this fast-growing variety.",
        2: "2-Time: Better, but still limited. Weed competition may reduce internode elongation and ratoon strength.",
        3: "3-Time: Strongly recommended. Use pre-emergence spraying plus three manual weedings at 25, 45, and 65 days after planting.",
    },
    "MAURITIO RC888": {
        1: "1-Time: Risky. Weed stress can weaken plant defense and increase leaf scald vulnerability.",
        2: "2-Time: Possible, but reduced weeding can increase disease risk.",
        3: "3-Time: Best practice. Perform manual weeding at 25, 45, and 65 days after planting to reduce stress and disease outbreaks.",
    },
}

PLOWING_GUIDE = {
    "VMC 84-524": {
        1: "1-Time: Only suitable for shallow soils with hardpan underneath; excess plowing may bring up infertile soil.",
        2: "2-Time: Acceptable when spaced 1-2 weeks apart; first pass encourages weed seed sprouting, second pass suppresses weeds.",
        3: "3-Time: Highly recommended with deep passes (8-12 inches or ~50-60 cm with heavy tractors) to improve rooting and lodging resistance.",
    },
    "VMC 84-947": {
        1: "1-Time (Plant Crop): Not recommended due to poor soil preparation and reduced ratooning lifespan.",
        2: "2-Time (Plant Crop): Recommended for new planting to prepare soil thoroughly for multiple ratoon cycles.",
        3: "3-Time (Plant Crop): Best practice for deep soil preparation and stronger long-term ratoon performance.",
    },
    "MAURITIO RC888": {
        1: "1-Time: Risky; can leave stubble and weeds near the surface, increasing disease pressure and weakening crop vigor.",
        2: "2-Time: Acceptable if followed by thorough harrowing to clean and condition the soil.",
        3: "3-Time: Strongly recommended to bury residues/weeds and improve drainage against waterlogging stress.",
    },
}

DEFAULT_RECOMMENDATIONS = [
    {
        "icon": "calendar-outline",
        "title": "Schedule harvest for ready plot",
        "meta": "Prioritize fields with high maturity this week.",
        "tag": "Priority",
        "tag_class": "success",
        "category": "General",
    },
    {
        "icon": "color-wand-outline",
        "title": "Apply nutrient mix",
        "meta": "Support sucrose build-up before harvest.",
        "tag": "Soon",
        "tag_class": "warning",
        "category": "General",
    },
    {
        "icon": "trail-sign-outline",
        "title": "Prepare transport route",
        "meta": "Finalize hauling logistics before cutting day.",
        "tag": "Plan",
        "tag_class": "",
        "category": "General",
    },
]

DEFAULT_SCAN_PREDICT_ENDPOINT = "http://34.81.143.245:8000/predict"
DEFAULT_SCAN_PREDICT_TOP_K = 3
DEFAULT_SCAN_PREDICT_TIMEOUT_SECONDS = 30
CV_UPLOAD_RELATIVE_DIR = os.path.join("uploads", "cv_scans")


def get_static_root():
    return Path(settings.BASE_DIR) / "static"


def get_model_updates_root():
    return Path(settings.BASE_DIR) / "model_updates"


def log_audit(action, user_id=None):
    try:
        AuditLog.objects.create(user_id=user_id, action=action)
    except Exception:
        pass


def get_system_config():
    config, _ = SystemConfig.objects.get_or_create(
        pk=1,
        defaults={"system_name": "VISCANE", "maintenance_mode": False},
    )
    return config


def get_current_admin(request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        return None
    admin = Admin.objects.filter(pk=admin_id, is_archived=False).first()
    if not admin:
        request.session.pop("admin_id", None)
    return admin


def is_valid_admin_role(role):
    return role in {"admin", "superadmin"}


def normalize_variety_name(variety):
    cleaned = (variety or "").strip()
    return VARIETY_ALIASES.get(cleaned, cleaned)


def normalize_cv_variety_name(variety):
    cleaned = (variety or "").strip()
    if not cleaned:
        return None
    cleaned_upper = cleaned.upper()
    mapped = CV_VARIETY_ALIASES.get(cleaned) or CV_VARIETY_ALIASES.get(cleaned_upper)
    if mapped:
        return mapped
    return normalize_variety_name(cleaned)


def normalize_cv_maturity_status(status):
    cleaned = (status or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not cleaned:
        return None
    if "OVER" in cleaned and "MATURE" in cleaned:
        return "OVER_MATURE"
    if "NOT" in cleaned and "MATURE" in cleaned:
        return "NOT_MATURE"
    if "MATURE" in cleaned:
        return "MATURE"
    return None


def get_cv_maturity_baseline_adjustment(variety, cv_maturity_status):
    normalized_variety = normalize_variety_name(variety)
    normalized_status = normalize_cv_maturity_status(cv_maturity_status)
    if not normalized_status:
        return 0.0, None
    weights = CV_MATURITY_BASELINE_WEIGHTS.get(normalized_variety) or {}
    return float(weights.get(normalized_status, 0.0)), normalized_status


def get_variety_weights(variety, custom_weights=None):
    weights = deepcopy(DEFAULT_VARIETY_WEIGHTS)
    if custom_weights is not None:
        weights[variety] = custom_weights
    return weights.get(variety, weights["VMC 84-524"])


def compute_visual_grade(visual_features):
    if not visual_features:
        raise ValueError("visual_features must not be empty.")
    return sum(visual_features) / len(visual_features)


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_choice_value(value):
    if value is None:
        return None
    numeric_value = _parse_float(value)
    if numeric_value is not None:
        return numeric_value
    cleaned = str(value).strip()
    stage_map = {"1-Time": 1.0, "2-Time": 2.0, "3-Time": 3.0, "1x": 1.0, "2x": 2.0, "3x": 3.0}
    return stage_map.get(cleaned)


def _parse_ratoon_value(value):
    if value is None:
        return None
    numeric_value = _parse_float(value)
    if numeric_value is not None:
        return numeric_value
    cleaned = str(value).strip()
    stage_map = {
        "Plant": 1.0,
        'Plant" (1st)': 1.0,
        "1st Ratoon": 2.0,
        "2nd Ratoon": 3.0,
        "New Plant (1)": 1.0,
        "1st ratoon (2nd)": 2.0,
        "2nd ratoon (3rd)": 3.0,
    }
    return stage_map.get(cleaned)


def _parse_hectares_value(value):
    if value is None:
        return None
    numeric_value = _parse_float(value)
    if numeric_value is not None:
        return numeric_value
    normalized = " ".join(str(value).strip().lower().replace("hectares", "hectare").split())
    hectares_map = {
        "less than 1 hectare": 0.5,
        "1 hectare": 1.0,
        "1-2": 1.5,
        "1-2 hectare": 1.5,
        "2": 2.0,
        "2 hectare": 2.0,
        "2-3": 2.5,
        "2-3 hectare": 2.5,
        "3": 3.0,
        "3 hectare": 3.0,
        "3-4": 3.5,
        "3-4 hectare": 3.5,
        "4": 4.0,
        "4 hectare": 4.0,
        "5": 5.0,
        "5 hectare": 5.0,
        "more than 5": 5.5,
        "more than 5 hectare": 5.5,
    }
    return hectares_map.get(normalized)


def _build_training_pipeline():
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline

    return Pipeline(steps=[("vectorizer", DictVectorizer(sparse=False)), ("regressor", LinearRegression())])


def get_agronomic_linear_model(weight_signature):
    from sklearn.linear_model import LinearRegression

    x_train = []
    y_train = []
    for index, coefficient in enumerate(weight_signature):
        row = [0.0] * len(AGRONOMIC_KEYS)
        row[index] = 1.0
        x_train.append(row)
        y_train.append(float(coefficient))
    model = LinearRegression(fit_intercept=False)
    model.fit(x_train, y_train)
    return model


def compute_agronomic_adjustment(agronomic_input, weights):
    weight_signature = tuple(float(weights[key]) for key in AGRONOMIC_KEYS)
    model = get_agronomic_linear_model(weight_signature)
    features = [[float(agronomic_input[key]) for key in AGRONOMIC_KEYS]]
    return float(model.predict(features)[0])


def compute_agronomic_penalty(agronomic_input, weights):
    contributions = [float(agronomic_input[key]) * weights[key] for key in AGRONOMIC_KEYS]
    return sum(min(0.0, value) for value in contributions)


def compute_agronomic_multiplier(agronomic_adjustment):
    return max(0.0, 1.0 + agronomic_adjustment)


def get_sra_baseline(variety, crop_stage):
    try:
        return SRA_BASELINE_LKG_TC[variety][crop_stage], SRA_BASELINE_TC_HA[variety][crop_stage]
    except KeyError as exc:
        raise ValueError("Missing SRA baseline for the selected variety or ratoon stage.") from exc


def predict_variety_metrics(variety, hectares, visual_features, agronomic_input, custom_weights=None, cv_maturity_status=None):
    normalized_variety = normalize_variety_name(variety)
    if normalized_variety not in DEFAULT_VARIETY_WEIGHTS and custom_weights is None:
        raise ValueError("Unknown variety. Provide a known variety or include custom_weights.")

    crop_stage = int(round(float(agronomic_input["ratoon"])))
    if crop_stage not in CROP_STAGE_LABELS:
        raise ValueError("ratoon stage must be 1, 2, or 3.")

    weights_used = get_variety_weights(normalized_variety, custom_weights)
    visual_grade = compute_visual_grade(visual_features)
    baseline_lkg_tc, baseline_tc_ha_per_hectare = get_sra_baseline(normalized_variety, crop_stage)
    adjusted_baseline_tc_ha = baseline_tc_ha_per_hectare * hectares
    agronomic_adjustment = compute_agronomic_adjustment(agronomic_input, weights_used)
    agronomic_penalty = compute_agronomic_penalty(agronomic_input, weights_used)
    cv_maturity_adjustment, normalized_cv_maturity_status = get_cv_maturity_baseline_adjustment(
        normalized_variety, cv_maturity_status
    )
    combined_penalty = agronomic_penalty + cv_maturity_adjustment
    agronomic_multiplier = compute_agronomic_multiplier(combined_penalty)
    raw_predicted_lkg_tc = baseline_lkg_tc * agronomic_multiplier
    predicted_lkg_tc = max(0.0, min(baseline_lkg_tc, raw_predicted_lkg_tc))
    raw_predicted_tc_ha = adjusted_baseline_tc_ha * agronomic_multiplier
    predicted_tc_ha = max(0.0, min(adjusted_baseline_tc_ha, raw_predicted_tc_ha))
    predicted_lkg = predicted_lkg_tc * predicted_tc_ha
    predicted_quality_grade = visual_grade + agronomic_adjustment + cv_maturity_adjustment

    return {
        "variety": normalized_variety,
        "crop_stage": CROP_STAGE_LABELS[crop_stage],
        "hectares": hectares,
        "visual_grade": visual_grade,
        "agronomic_adjustment": agronomic_adjustment,
        "agronomic_penalty": agronomic_penalty,
        "cv_maturity_status": normalized_cv_maturity_status,
        "cv_maturity_adjustment": cv_maturity_adjustment,
        "combined_penalty": combined_penalty,
        "agronomic_multiplier": agronomic_multiplier,
        "predicted_quality_grade": predicted_quality_grade,
        "baseline_lkg_tc": baseline_lkg_tc,
        "baseline_tc_ha_per_hectare": baseline_tc_ha_per_hectare,
        "adjusted_baseline_tc_ha": adjusted_baseline_tc_ha,
        "raw_predicted_lkg_tc": raw_predicted_lkg_tc,
        "predicted_lkg_tc": predicted_lkg_tc,
        "raw_predicted_tc_ha": raw_predicted_tc_ha,
        "predicted_tc_ha": predicted_tc_ha,
        "predicted_lkg": predicted_lkg,
        "weights_used": weights_used,
        "prediction_engine": "weighted_baseline_sklearn",
        "training_rows_used": 0,
        "input": {
            "hectares": hectares,
            "visual_features": visual_features,
            "agronomic_input": agronomic_input,
            "cv_maturity_status": normalized_cv_maturity_status,
        },
    }


def _format_factor_value(value):
    if value is None:
        return "missing"
    if float(value).is_integer():
        return str(int(float(value)))
    return f"{float(value):.2f}"


def generate_recommendations(prediction_response, agronomic_input, missing_fields=None, variety=None):
    recommendations = []
    missing_fields = missing_fields or []
    agronomic_input = agronomic_input or {}
    selected_variety = normalize_variety_name(variety or prediction_response.get("variety") or "VMC 84-524")
    fertilizer_guide = FERTILIZER_TIMING_GUIDE.get(selected_variety, FERTILIZER_TIMING_GUIDE["VMC 84-524"])
    weeding_guide = WEEDING_GUIDE.get(selected_variety, WEEDING_GUIDE["VMC 84-524"])
    plowing_guide = PLOWING_GUIDE.get(selected_variety, PLOWING_GUIDE["VMC 84-524"])
    normalized_cv_maturity = normalize_cv_maturity_status(
        prediction_response.get("cv_maturity_status") or prediction_response.get("maturity_status")
    )

    if normalized_cv_maturity == "NOT_MATURE":
        recommendations.append(
            {
                "icon": "pause-circle-outline",
                "title": "Delay cutting for sucrose accumulation",
                "meta": 'Real-time harvest directive: "Not Mature" classification indicates stalks should not be cut yet. Delay harvest to allow optimal sucrose accumulation before scheduling transport.',
                "tag": "Advisory",
                "tag_class": "warning",
                "category": "Harvest Directives",
            }
        )
    elif normalized_cv_maturity == "MATURE":
        recommendations.append(
            {
                "icon": "checkmark-done-circle-outline",
                "title": "Finalize immediate harvest logistics",
                "meta": 'Real-time harvest directive: "Mature" classification indicates harvest-ready stalks. Proceed with immediate cutting and finalize hauling/transport coordination.',
                "tag": "Ready",
                "tag_class": "success",
                "category": "Harvest Directives",
            }
        )
    elif normalized_cv_maturity == "OVER_MATURE":
        recommendations.append(
            {
                "icon": "alert-outline",
                "title": "Expedite harvest to prevent further yield loss",
                "meta": 'Real-time harvest directive: "Over Mature" classification requires urgent cutting. Expedite harvest to mitigate further yield degradation caused by sucrose inversion.',
                "tag": "Urgent",
                "tag_class": "warning",
                "category": "Harvest Directives",
            }
        )

    if missing_fields:
        recommendations.append(
            {
                "icon": "alert-circle-outline",
                "title": "Complete missing agronomic inputs",
                "meta": "Please fill: " + ", ".join(missing_fields) + ".",
                "tag": "Required",
                "tag_class": "warning",
                "category": "Missing Inputs",
            }
        )

    fertilizer_value = agronomic_input.get("fertilizer")
    fertilizer_missing = ("fertilizer" in missing_fields) or (fertilizer_value is None)
    if fertilizer_missing:
        recommendations.append(
            {
                "icon": "beaker-outline",
                "title": f"Choose fertilizer timing for {selected_variety}",
                "meta": f"{fertilizer_guide[1]} {fertilizer_guide[2]} {fertilizer_guide[3]}",
                "tag": "Required",
                "tag_class": "warning",
                "category": "Fertilizer Guidance",
            }
        )

    weeding_value = agronomic_input.get("weeding")
    weeding_missing = ("weeding" in missing_fields) or (weeding_value is None)
    if weeding_missing:
        recommendations.append(
            {
                "icon": "cut-outline",
                "title": f"Choose weeding schedule for {selected_variety}",
                "meta": f"{weeding_guide[1]} {weeding_guide[2]} {weeding_guide[3]}",
                "tag": "Required",
                "tag_class": "warning",
                "category": "Weeding Guidance",
            }
        )

    plowing_value = agronomic_input.get("plowing")
    plowing_missing = ("plowing" in missing_fields) or (plowing_value is None)
    if plowing_missing:
        recommendations.append(
            {
                "icon": "construct-outline",
                "title": f"Choose plowing schedule for {selected_variety}",
                "meta": f"{plowing_guide[1]} {plowing_guide[2]} {plowing_guide[3]}",
                "tag": "Required",
                "tag_class": "warning",
                "category": "Plowing Guidance",
            }
        )

    predicted_lkg = prediction_response.get("predicted_lkg")
    baseline_lkg_tc = prediction_response.get("baseline_lkg_tc")
    adjusted_baseline_tc_ha = prediction_response.get("adjusted_baseline_tc_ha")
    baseline_lkg = None
    if baseline_lkg_tc is not None and adjusted_baseline_tc_ha is not None:
        baseline_lkg = float(baseline_lkg_tc) * float(adjusted_baseline_tc_ha)

    low_lkg = False
    if predicted_lkg is not None and baseline_lkg and baseline_lkg > 0:
        low_lkg = (float(predicted_lkg) / baseline_lkg) < 0.85

    low_factor_rules = [("plowing", 2.0, "Increase plowing"), ("weeding", 2.0, "Increase weeding"), ("fertilizer", 2.0, "Increase fertilizer")]

    for key, threshold, label in low_factor_rules:
        value = agronomic_input.get(key)
        if value is None:
            continue
        if float(value) < threshold:
            category = "Yield Improvement"
            if key == "fertilizer":
                category = "Fertilizer Guidance"
            elif key == "weeding":
                category = "Weeding Guidance"
            elif key == "plowing":
                category = "Plowing Guidance"
            recommendations.append(
                {
                    "icon": "trending-up-outline",
                    "title": f"{label} from {_format_factor_value(value)} to at least {int(threshold)}",
                    "meta": "Low input level is pulling down predicted LKG.",
                    "tag": "Improve",
                    "tag_class": "warning",
                    "category": category,
                }
            )

    rssi_value = agronomic_input.get("rssi")
    if rssi_value is not None and float(rssi_value) >= 1.0:
        recommendations.append(
            {
                "icon": "medkit-outline",
                "title": "RSSI infected: apply PHILSURIN control protocol",
                "meta": "Conduct weekly monitoring, especially lower leaf areas, and immediately remove and burn infested leaves to prevent spread. Effective chemical options include Carbofuran, Phenthoate, Dinotefuran, Thiamethoxam, Pymetrozine, and Buprofezin. Report suspected infestations to PHILSURIN, DA, or SRA, and adopt integrated pest management using monitoring, physical removal, and chemical or biological interventions.",
                "tag": "Urgent",
                "tag_class": "warning",
                "category": "Pest and Disease",
            }
        )

    if not fertilizer_missing and low_lkg:
        fert_choice = int(round(float(fertilizer_value)))
        fert_choice = max(1, min(3, fert_choice))
        recommendations.append(
            {
                "icon": "leaf-outline",
                "title": f"Follow {fert_choice}-time fertilizer schedule for {selected_variety}",
                "meta": fertilizer_guide[fert_choice],
                "tag": "Guide",
                "tag_class": "",
                "category": "Fertilizer Guidance",
            }
        )

    if not fertilizer_missing:
        fert_choice = int(round(float(fertilizer_value)))
        fert_choice = max(1, min(3, fert_choice))
        if fert_choice == 1:
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 2-time fertilizer application for {selected_variety}", "meta": fertilizer_guide[2], "tag": "Upgrade", "tag_class": "warning", "category": "Fertilizer Guidance"})
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 3-time fertilizer application for {selected_variety}", "meta": fertilizer_guide[3], "tag": "Upgrade", "tag_class": "warning", "category": "Fertilizer Guidance"})
        elif fert_choice == 2:
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 3-time fertilizer application for {selected_variety}", "meta": fertilizer_guide[3], "tag": "Upgrade", "tag_class": "warning", "category": "Fertilizer Guidance"})

    if not weeding_missing and low_lkg:
        weed_choice = int(round(float(weeding_value)))
        weed_choice = max(1, min(3, weed_choice))
        recommendations.append({"icon": "leaf-outline", "title": f"Follow {weed_choice}-time weeding schedule for {selected_variety}", "meta": weeding_guide[weed_choice], "tag": "Guide", "tag_class": "", "category": "Weeding Guidance"})

    if not weeding_missing:
        weed_choice = int(round(float(weeding_value)))
        weed_choice = max(1, min(3, weed_choice))
        if weed_choice == 1:
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 2-time weeding for {selected_variety}", "meta": weeding_guide[2], "tag": "Upgrade", "tag_class": "warning", "category": "Weeding Guidance"})
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 3-time weeding for {selected_variety}", "meta": weeding_guide[3], "tag": "Upgrade", "tag_class": "warning", "category": "Weeding Guidance"})
        elif weed_choice == 2:
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 3-time weeding for {selected_variety}", "meta": weeding_guide[3], "tag": "Upgrade", "tag_class": "warning", "category": "Weeding Guidance"})

    if not plowing_missing and low_lkg:
        plow_choice = int(round(float(plowing_value)))
        plow_choice = max(1, min(3, plow_choice))
        recommendations.append({"icon": "leaf-outline", "title": f"Follow {plow_choice}-time plowing schedule for {selected_variety}", "meta": plowing_guide[plow_choice], "tag": "Guide", "tag_class": "", "category": "Plowing Guidance"})

    if not plowing_missing:
        plow_choice = int(round(float(plowing_value)))
        plow_choice = max(1, min(3, plow_choice))
        ratoon_value = agronomic_input.get("ratoon")
        ratoon_stage = int(round(float(ratoon_value))) if ratoon_value is not None else None
        is_vmc_947_ratoon = selected_variety == "VMC 84-947" and ratoon_stage in {2, 3}
        if is_vmc_947_ratoon:
            recommendations.append({"icon": "construct-outline", "title": "For VMC 84-947 ratoon, avoid plowing", "meta": "Use stubble shaving and inter-row cultivation (off-barring) to protect ratoon shoots.", "tag": "Important", "tag_class": "warning", "category": "Plowing Guidance"})
        elif plow_choice == 1:
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 2-time plowing for {selected_variety}", "meta": plowing_guide[2], "tag": "Upgrade", "tag_class": "warning", "category": "Plowing Guidance"})
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 3-time plowing for {selected_variety}", "meta": plowing_guide[3], "tag": "Upgrade", "tag_class": "warning", "category": "Plowing Guidance"})
        elif plow_choice == 2:
            recommendations.append({"icon": "trending-up-outline", "title": f"Consider 3-time plowing for {selected_variety}", "meta": plowing_guide[3], "tag": "Upgrade", "tag_class": "warning", "category": "Plowing Guidance"})

    if low_lkg and not recommendations:
        recommendations.append({"icon": "analytics-outline", "title": "Predicted LKG is below baseline", "meta": "Increase low agronomic inputs and re-calculate to recover yield.", "tag": "Attention", "tag_class": "warning", "category": "Yield Improvement"})

    if not low_lkg and not recommendations:
        recommendations.append({"icon": "checkmark-circle-outline", "title": "Maintain current agronomic practices", "meta": "Current inputs are supporting baseline-level yield.", "tag": "Stable", "tag_class": "success", "category": "General"})

    return recommendations


def group_recommendations_by_category(recommendations):
    grouped = {}
    for recommendation in recommendations or []:
        category = recommendation.get("category") or "General"
        grouped.setdefault(category, []).append(recommendation)
    category_order = ["Missing Inputs", "Harvest Directives", "Pest and Disease", "Fertilizer Guidance", "Weeding Guidance", "Plowing Guidance", "Yield Improvement", "General"]
    ordered_groups = []
    for category in category_order:
        if category in grouped:
            ordered_groups.append({"category": category, "items": grouped.pop(category)})
    for category, items in grouped.items():
        ordered_groups.append({"category": category, "items": items})
    return ordered_groups


def _build_multipart_form_data(fields, files):
    boundary = f"----ViscaneBoundary{secrets.token_hex(16)}"
    chunks = []
    for field_name, field_value in (fields or {}).items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(field_value).encode("utf-8"))
        chunks.append(b"\r\n")
    for file_item in (files or []):
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{file_item["field_name"]}"; filename="{file_item["filename"]}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {file_item['content_type']}\r\n\r\n".encode("utf-8"))
        chunks.append(file_item["content"])
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    return body, f"multipart/form-data; boundary={boundary}"


def verify_and_upgrade_password(instance, raw_password, field_name="password"):
    stored_value = getattr(instance, field_name, "") or ""
    if not raw_password:
        return False
    try:
        if check_password(raw_password, stored_value):
            return True
    except Exception:
        pass
    try:
        from werkzeug.security import check_password_hash

        if check_password_hash(stored_value, raw_password):
            setattr(instance, field_name, make_password(raw_password))
            return True
    except Exception:
        pass
    if stored_value == raw_password:
        setattr(instance, field_name, make_password(raw_password))
        return True
    return False


def _extract_cv_context(prediction_payload):
    if not isinstance(prediction_payload, dict):
        return {}
    models = prediction_payload.get("models")
    if not isinstance(models, dict) or not models:
        return {}
    best_entry = None
    best_confidence = float("-inf")
    for model_name, model_payload in models.items():
        if not isinstance(model_payload, dict):
            continue
        prediction = model_payload.get("prediction")
        if not isinstance(prediction, dict):
            continue
        try:
            confidence = float(prediction.get("confidence"))
        except (TypeError, ValueError):
            confidence = float("-inf")
        if confidence > best_confidence:
            best_confidence = confidence
            best_entry = {"model_name": model_name, "prediction": prediction, "top_k": model_payload.get("top_k") or []}
    if not best_entry:
        return {}
    prediction = best_entry["prediction"]
    maturity_status = normalize_cv_maturity_status(prediction.get("maturity_status"))
    normalized_variety = normalize_cv_variety_name(prediction.get("variety"))
    visual_features = []
    for item in best_entry.get("top_k") or []:
        if not isinstance(item, dict):
            continue
        try:
            visual_features.append(float(item.get("confidence")))
        except (TypeError, ValueError):
            continue
    if not visual_features:
        try:
            visual_features = [float(prediction.get("confidence"))]
        except (TypeError, ValueError):
            visual_features = []
    return {
        "model_name": best_entry["model_name"],
        "maturity_status": maturity_status,
        "class_name": prediction.get("class_name"),
        "variety": prediction.get("variety"),
        "normalized_variety": normalized_variety,
        "confidence": prediction.get("confidence"),
        "visual_features": visual_features,
        "models": models,
    }


def _build_cv_upload_path(filename):
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    generated_name = f"cv-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(8)}{ext}"
    relative_path = os.path.join(CV_UPLOAD_RELATIVE_DIR, generated_name)
    absolute_path = get_static_root() / Path(relative_path)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    return relative_path.replace("\\", "/"), absolute_path


def _persist_cv_upload(user_id, uploaded_filename, file_bytes, cv_context):
    if not user_id or not file_bytes:
        return
    relative_path, absolute_path = _build_cv_upload_path(uploaded_filename)
    try:
        absolute_path.write_bytes(file_bytes)
    except OSError:
        return
    try:
        confidence = _parse_float((cv_context or {}).get("confidence"))
        CvScanUpload.objects.create(
            user_id=user_id,
            image_path=relative_path,
            original_filename=os.path.basename(uploaded_filename or "upload.jpg"),
            variety=((cv_context or {}).get("normalized_variety") or (cv_context or {}).get("variety")),
            maturity_status=(cv_context or {}).get("maturity_status"),
            model_name=(cv_context or {}).get("model_name"),
            confidence=confidence,
        )
    except Exception:
        pass


def api_predict_scan_payload(uploaded_file, top_k):
    endpoint = (os.getenv("SCAN_PREDICT_ENDPOINT", DEFAULT_SCAN_PREDICT_ENDPOINT).strip() or DEFAULT_SCAN_PREDICT_ENDPOINT)
    timeout_raw = os.getenv("SCAN_PREDICT_TIMEOUT_SECONDS", str(DEFAULT_SCAN_PREDICT_TIMEOUT_SECONDS))
    try:
        timeout_seconds = max(5.0, float(timeout_raw))
    except (TypeError, ValueError):
        timeout_seconds = float(DEFAULT_SCAN_PREDICT_TIMEOUT_SECONDS)

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return None, {"error": "Uploaded image is empty."}, 400

    separator = "&" if "?" in endpoint else "?"
    target_url = f"{endpoint}{separator}{urlencode({'top_k': top_k})}"
    body, content_type = _build_multipart_form_data(
        fields={},
        files=[{
            "field_name": "file",
            "filename": os.path.basename(uploaded_file.name) or "capture.jpg",
            "content_type": getattr(uploaded_file, "content_type", None) or "image/jpeg",
            "content": file_bytes,
        }],
    )
    outbound = Request(target_url, data=body, method="POST")
    outbound.add_header("accept", "application/json")
    outbound.add_header("Content-Type", content_type)
    outbound.add_header("Content-Length", str(len(body)))
    try:
        with urlopen(outbound, timeout=timeout_seconds) as api_response:
            response_body = api_response.read()
            status_code = getattr(api_response, "status", 200)
    except HTTPError as exc:
        try:
            details = exc.read().decode("utf-8", errors="replace")
        except Exception:
            details = str(exc)
        return None, {"error": "Prediction service returned an error.", "status": exc.code, "details": details[:600]}, 502
    except URLError as exc:
        return None, {"error": "Prediction service is unreachable.", "details": str(exc.reason) if getattr(exc, "reason", None) else str(exc)}, 502
    except TimeoutError:
        return None, {"error": "Prediction service timed out.", "details": f"Request exceeded {timeout_seconds:.0f} seconds."}, 504
    except Exception as exc:
        return None, {"error": "Failed to request prediction service.", "details": str(exc)}, 500
    return (response_body, status_code), None, None


def save_prediction_context(user_id, uploaded_file, file_bytes, decoded_payload):
    cv_context = _extract_cv_context(decoded_payload)
    _persist_cv_upload(user_id=user_id, uploaded_filename=uploaded_file.name, file_bytes=file_bytes, cv_context=cv_context)
    return cv_context
