from __future__ import annotations

import csv
import json
import math
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Max, Sum, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect as django_redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .language import translate_recommendations
from .models import Admin, AgronomicLog, AuditLog, CvScanUpload, Feedback, Notification, Scan, SystemConfig, User
from .services import (
    DEFAULT_RECOMMENDATIONS,
    DEFAULT_SCAN_PREDICT_TOP_K,
    DEFAULT_SCAN_PREDICT_ENDPOINT,
    _build_cv_upload_path,
    _extract_cv_context,
    _parse_choice_value,
    _parse_float,
    _parse_hectares_value,
    _parse_ratoon_value,
    api_predict_scan_payload,
    compute_agronomic_adjustment,
    derive_scan_assessment,
    generate_recommendations,
    get_current_admin,
    get_model_updates_root,
    get_static_root,
    get_system_config,
    group_recommendations_by_category,
    is_valid_admin_role,
    log_audit,
    normalize_cv_variety_name,
    normalize_cv_maturity_status,
    normalize_variety_name,
    predict_variety_metrics,
    request_prediction_service,
    save_prediction_context,
    summarize_prediction_service_error,
    verify_and_upgrade_password,
)


def render_template(request, template_name, context=None, status=200):
    payload = {"request": request, "session": request.session}
    if context:
        payload.update(context)
    return render(request, template_name, payload, status=status)


INVALID_CV_IMAGE_MESSAGE = "Invalid Image. This Image is not supported"
CV_CONFIDENCE_THRESHOLD = 0.50


def supported_cv_confidence(cv_context):
    try:
        confidence = float((cv_context or {}).get("confidence"))
    except (TypeError, ValueError):
        return False
    if confidence > 1:
        confidence /= 100
    return math.isfinite(confidence) and confidence >= CV_CONFIDENCE_THRESHOLD


_REDIRECT_PATH_PARAMS = {
    "admin_farmer_edit": {"user_id"},
    "delete_cv_upload": {"upload_id"},
    "superadmin_user_details": {"user_id"},
}


def redirect(viewname, *args, **kwargs):
    if not kwargs:
        return django_redirect(viewname, *args)
    path_param_names = _REDIRECT_PATH_PARAMS.get(viewname, set())
    path_kwargs = {key: kwargs.pop(key) for key in list(kwargs.keys()) if key in path_param_names}
    if path_kwargs:
        path = reverse(viewname, kwargs=path_kwargs)
    else:
        path = reverse(viewname, args=args if args else None)
    if kwargs:
        path = f"{path}?{urlencode(kwargs, doseq=True)}"
    return django_redirect(path)


def farmer_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user_id = request.session.get("user_id")
        user = User.objects.filter(pk=user_id, is_archived=False, is_active=True).first() if user_id else None
        if not user:
            request.session.pop("user_id", None)
            return redirect("auth")
        request.current_user = user
        return view(request, *args, **kwargs)

    return wrapped


def login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        admin_id = request.session.get("admin_id")
        admin = Admin.objects.filter(pk=admin_id, is_archived=False).first() if admin_id else None
        if not admin:
            request.session.pop("admin_id", None)
            return redirect("admin_login")
        request.current_admin = admin
        return view(request, *args, **kwargs)

    return wrapped


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            admin_id = request.session.get("admin_id")
            admin = Admin.objects.filter(pk=admin_id, is_archived=False).first() if admin_id else None
            if not admin:
                request.session.pop("admin_id", None)
                return redirect("superadmin_login" if required_role == "superadmin" else "admin_login")
            if admin.role != required_role:
                return redirect("admin_portal")
            request.current_admin = admin
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def current_user(request):
    user_id = request.session.get("user_id")
    return User.objects.filter(pk=user_id, is_archived=False, is_active=True).first() if user_id else None


def current_admin(request):
    return get_current_admin(request)


def portal(request):
    return render_template(request, "portal.html")


def admin_access(request):
    return render_template(request, "admin_access.html")


@farmer_login_required
def homepage(request):
    user = current_user(request)
    scan_section = request.GET.get("scan_section")
    sample_plot_names = ("Plot #1 Sample", "Plot #2 Sample", "Plot #4 Sample")
    scans_base_query = Scan.objects.filter(user_id=user.id).exclude(plot_name__in=sample_plot_names)
    recent_query = scans_base_query.filter(hidden_from_recent=False).select_related("cv_upload").order_by("-created_at", "-id")
    recent_page = Paginator(recent_query, 4).get_page(request.GET.get("recent_page"))
    recent_scans = list(recent_page.object_list) if scan_section != "scan-gallery" else []
    gallery_query = (
        scans_base_query.filter(hidden_from_recent=False, cv_upload__isnull=False)
        .select_related("cv_upload").order_by("-created_at", "-id")
    )
    gallery_page = Paginator(gallery_query, 4).get_page(request.GET.get("gallery_page"))
    gallery_scans = gallery_page.object_list
    recent_scan_cards = [{"scan": scan, "cv_upload": scan.cv_upload} for scan in recent_scans]
    if scan_section == "recent-scans":
        return render_template(request, "components/homepage_recent_scans.html", {
            "recent_scan_cards": recent_scan_cards,
            "recent_page": recent_page,
            "gallery_page": gallery_page,
        })
    if scan_section == "scan-gallery":
        return render_template(request, "components/homepage_scan_gallery.html", {
            "gallery_scans": gallery_scans,
            "gallery_page": gallery_page,
            "recent_page": recent_page,
        })
    scan_variety = request.session.pop("scan_result_variety", "")
    scan_maturity_status = (request.session.get("latest_cv_context") or {}).get("maturity_status", "") if scan_variety else ""
    today = timezone.now().date()
    seven_days_ago = timezone.now() - timedelta(days=7)
    scans_today = scans_base_query.filter(created_at__date=today).count()
    pending_scans = scans_base_query.filter(status="pending").count()
    scans_last7 = list(scans_base_query.filter(created_at__gte=seven_days_ago))
    agronomic_logs = list(AgronomicLog.objects.filter(user_id=user.id).order_by("-created_at")[:10])
    announcements = list(Notification.objects.order_by("-created_at")[:5])
    recommendations = request.session.get("farmer_recommendations") or DEFAULT_RECOMMENDATIONS
    grouped_recommendations = group_recommendations_by_category(recommendations)
    if scans_last7:
        grade_a = sum(1 for s in scans_last7 if (s.grade or "").upper() == "A")
        avg_grade_a = int((grade_a / len(scans_last7)) * 100)
        avg_maturity = int(sum(s.maturity_pct for s in scans_last7) / len(scans_last7))
    else:
        avg_grade_a = 0
        avg_maturity = 0
    if avg_maturity >= 85:
        yield_est = "High"
        harvest_window = "3-7 days"
    elif avg_maturity >= 75:
        yield_est = "Medium"
        harvest_window = "8-12 days"
    else:
        yield_est = "Low"
        harvest_window = "14-18 days"
    page_message = request.GET.get("message")
    picture_removed = request.GET.get("notice") == "picture_removed" or page_message in {
        "Picture removed from recent scans.",
        "Picture removed from recent scans. The saved assessment remains available.",
    }
    return render_template(
        request,
        "homepage.html",
        {
            "user": user,
            "scans_today": scans_today,
            "pending_scans": pending_scans,
            "avg_grade_a": avg_grade_a,
            "yield_est": yield_est,
            "harvest_window": harvest_window,
            "avg_maturity": avg_maturity,
            "recent_scans": recent_scans,
            "recent_scan_cards": recent_scan_cards,
            "recent_page": recent_page,
            "gallery_scans": gallery_scans,
            "gallery_page": gallery_page,
            "agronomic_logs": agronomic_logs,
            "announcements": announcements,
            "recommendations": recommendations,
            "grouped_recommendations": grouped_recommendations,
            "message": None if picture_removed else page_message,
            "error": request.GET.get("error"),
            "picture_removed": picture_removed,
            "scan_result_variety": scan_variety,
            "scan_result_maturity_status": scan_maturity_status,
        },
    )


@farmer_login_required
def farmer_recommendations(request):
    user = current_user(request)
    recommendations = translate_recommendations(request.session.get("farmer_recommendations") or DEFAULT_RECOMMENDATIONS)
    grouped_recommendations = group_recommendations_by_category(recommendations)
    area_styles = {
        "Missing Inputs": ("missing", "alert-circle-outline"),
        "Harvest Directives": ("harvest", "sunny-outline"),
        "Pest and Disease": ("pest", "shield-checkmark-outline"),
        "Fertilizer Guidance": ("fertilizer", "flask-outline"),
        "Weeding Guidance": ("weeding", "leaf-outline"),
        "Plowing Guidance": ("plowing", "construct-outline"),
        "Yield Improvement": ("yield", "trending-up-outline"),
        "General": ("general", "sparkles-outline"),
    }
    for group in grouped_recommendations:
        group["tone"], group["icon"] = area_styles.get(group["category"], area_styles["General"])
    return render_template(request, "farmer_recommendations.html", {"user": user, "recommendations": recommendations, "grouped_recommendations": grouped_recommendations})


@farmer_login_required
def farmer_agronomic_logs(request):
    user = current_user(request)
    agronomic_logs = list(AgronomicLog.objects.filter(user_id=user.id).select_related("scan__cv_upload").order_by("-created_at"))
    history_rows = []
    for log in agronomic_logs:
        scan = log.scan if log.scan and log.scan.user_id == user.id else None
        scan_upload = scan.cv_upload if scan else None
        recommendation_items = log.recommendations_snapshot or []
        if not recommendation_items:
            recommendation_items = []
            for item in (log.recommendations_summary or "").split(" | "):
                if item.strip():
                    category, separator, title = item.partition(": ")
                    recommendation_items.append({
                        "category": category if separator else "General",
                        "title": title if separator else category,
                        "meta": "",
                        "icon": "sparkles-outline",
                        "tag": "",
                    })
        history_rows.append({
            "log": log,
            "scan": scan,
            "scan_upload": scan_upload,
            "scan_image_url": reverse("cv_upload_image", args=[scan_upload.pk]) if scan_upload else "",
            "calculated_at": timezone.localtime(log.created_at) if log.created_at else None,
            "scanned_at": timezone.localtime(scan.created_at) if scan and scan.created_at else None,
            "recommendation_items": recommendation_items,
        })
    return render_template(request, "farmer_agronomic_logs.html", {"user": user, "history_rows": history_rows})


@farmer_login_required
@require_POST
def delete_cv_upload(request, upload_id):
    def back_to_recent_scans(**message):
        for page_name in ("recent_page", "gallery_page"):
            page_number = request.GET.get(page_name, "")
            if page_number.isdigit():
                message[page_name] = page_number
        response = redirect("homepage", **message)
        response["Location"] += "#recent-scans"
        return response

    user_id = request.session.get("user_id")
    upload = CvScanUpload.objects.filter(pk=upload_id, user_id=user_id).first()
    if not upload:
        return back_to_recent_scans(error="Picture not found or already removed.")
    file_path = cv_image_path(upload.image_path)
    try:
        with transaction.atomic():
            Scan.objects.filter(user_id=user_id, cv_upload_id=upload_id).update(hidden_from_recent=True)
            upload.delete()
    except Exception:
        return back_to_recent_scans(error="Unable to remove picture right now.")
    try:
        if file_path.is_file():
            file_path.unlink()
    except OSError:
        pass
    return back_to_recent_scans(notice="picture_removed")


def cv_image_path(relative_path):
    root = settings.PRIVATE_UPLOAD_ROOT if relative_path.startswith("private/") else get_static_root()
    root = Path(root).resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise Http404("Image not found")
    return path


@require_GET
def cv_upload_image(request, upload_id):
    upload = CvScanUpload.objects.filter(pk=upload_id).first()
    farmer = current_user(request)
    admin = current_admin(request) if not request.farmer_only else None
    if not upload or not ((farmer and upload.user_id == farmer.id) or admin):
        raise Http404("Image not found")
    path = cv_image_path(upload.image_path)
    if not path.is_file():
        raise Http404("Image not found")
    response = FileResponse(path.open("rb"))
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@farmer_login_required
@require_POST
def api_scan_predict(request):
    uploaded_file = request.FILES.get("file") or request.FILES.get("image")
    if not uploaded_file or not uploaded_file.name:
        return JsonResponse({"error": "Missing image file. Use form field `file`."}, status=400)
    try:
        top_k = max(1, min(10, int(request.GET.get("top_k", DEFAULT_SCAN_PREDICT_TOP_K))))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid `top_k`. Provide an integer from 1 to 10."}, status=400)
    if uploaded_file.size > settings.SCAN_MAX_IMAGE_BYTES:
        return JsonResponse({"error": "Image must be 10 MB or smaller."}, status=413)
    file_bytes = uploaded_file.read()
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(BytesIO(file_bytes)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 40_000_000:
                return JsonResponse({"error": "Use a JPEG, PNG or WebP image under 40 megapixels."}, status=400)
            uploaded_file.content_type = Image.MIME[image.format]
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return JsonResponse({"error": "The uploaded file is not a valid image."}, status=400)
    response_payload, error_payload, error_status = request_prediction_service(
        uploaded_filename=uploaded_file.name,
        file_bytes=file_bytes,
        content_type=uploaded_file.content_type or "image/jpeg",
        top_k=top_k,
    )
    if error_payload:
        return JsonResponse(error_payload, status=error_status or 500)

    response_body, status_code = response_payload

    if 200 <= status_code < 300:
        try:
            decoded_payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "Prediction service did not return valid JSON."}, status=502)
        cv_context = _extract_cv_context(decoded_payload)
        if not cv_context:
            response_keys = list(decoded_payload) if isinstance(decoded_payload, dict) else []
            return JsonResponse({
                "error": "Prediction service returned no recognizable prediction.",
                "details": f"Response fields: {', '.join(response_keys) or 'none'}. Expected variety, maturity, and a prediction score.",
            }, status=502)
        if not supported_cv_confidence(cv_context):
            request.session.pop("latest_cv_context", None)
            return JsonResponse({"error": INVALID_CV_IMAGE_MESSAGE}, status=422)
        try:
            cv_context = save_prediction_context(request.session.get("user_id"), uploaded_file, file_bytes, decoded_payload)
        except Exception:
            return JsonResponse({"error": "The analyzed photo could not be saved. Please try again."}, status=500)
        if not cv_context.get("upload_id"):
            return JsonResponse({"error": "The analyzed photo could not be saved. Please try again."}, status=500)
        request.session["latest_cv_context"] = cv_context
        decoded_payload["prediction"] = {
            "variety": cv_context.get("normalized_variety") or cv_context.get("variety"),
            "maturity_status": cv_context.get("maturity_status"),
            "confidence": cv_context.get("confidence"),
            "class_name": cv_context.get("class_name"),
        }
        return JsonResponse(decoded_payload, status=status_code)
    return HttpResponse(response_body, status=status_code, content_type="application/json")


@farmer_login_required
def calculate_results(request):
    if request.method != "POST":
        return django_redirect("/homepage#calc-form")
    user = current_user(request)
    variety = request.POST.get("variety", "").strip()
    plowing_count = request.POST.get("plowing_count", "").strip()
    weeding_count = request.POST.get("weeding_count", "").strip()
    fertilizer_count = request.POST.get("fertilizer_count", "").strip()
    ratoon_stage = request.POST.get("ratoon_stage", "").strip()
    rssi_infected = request.POST.get("rssi_infected", "").strip()
    hectares = request.POST.get("hectares", "").strip()
    cv_maturity_status = request.POST.get("cv_maturity_status", "").strip()
    cv_variety_detected = request.POST.get("cv_variety_detected", "").strip()
    cv_prediction_applied = request.POST.get("cv_prediction_applied", "").strip() in {"1", "true", "True"}
    cv_context = (request.session.get("latest_cv_context") or {}) if cv_prediction_applied else {}
    if cv_prediction_applied and not supported_cv_confidence(cv_context):
        request.session.pop("latest_cv_context", None)
        return redirect("homepage", error=INVALID_CV_IMAGE_MESSAGE)
    cv_detected_variety = normalize_cv_variety_name(cv_variety_detected or cv_context.get("normalized_variety") or cv_context.get("variety"))
    if not cv_maturity_status:
        cv_maturity_status = (cv_context.get("maturity_status") or "").strip()
    latest_scan = Scan.objects.filter(user_id=user.id).order_by("-created_at", "-id").first()
    maturity_pct = latest_scan.maturity_pct if latest_scan else None
    visual_features = [0.21, 0.48, 0.63, 0.74, 0.59]
    cv_visual_features = cv_context.get("visual_features")
    if isinstance(cv_visual_features, list):
        cleaned_features = []
        for value in cv_visual_features:
            try:
                cleaned_features.append(float(value))
            except (TypeError, ValueError):
                continue
        if cleaned_features:
            visual_features = cleaned_features
    rssi_text = (rssi_infected or "").strip().lower()
    if rssi_text in {"yes", "y", "1", "true"}:
        rssi_value = 1.0
    elif rssi_text in {"no", "n", "0", "false"}:
        rssi_value = 0.0
    else:
        rssi_value = None
    hectares_value = _parse_hectares_value(hectares)
    normalized_variety = normalize_variety_name(variety)
    plowing_value = _parse_choice_value(plowing_count)
    weeding_value = _parse_choice_value(weeding_count)
    fertilizer_value = _parse_choice_value(fertilizer_count)
    ratoon_value = _parse_ratoon_value(ratoon_stage)
    payload = {
        "variety": normalized_variety,
        "hectares": hectares_value,
        "visual_features": visual_features,
        "agronomic_input": {"rssi": rssi_value, "weeding": weeding_value, "fertilizer": fertilizer_value, "ratoon": ratoon_value, "plowing": plowing_value},
        "custom_weights": {"rssi": -0.50, "weeding": 0.32, "fertilizer": 0.22, "ratoon": -0.10, "plowing": 0.09},
        "cv_maturity_status": cv_maturity_status,
    }
    has_complete_payload = bool(variety) and hectares_value is not None and len(visual_features) >= 1 and all(isinstance(value, (int, float)) for value in visual_features) and all(value is not None for value in payload["agronomic_input"].values())
    missing_fields = []
    api_error = None
    prediction_response = {}
    if has_complete_payload and cv_detected_variety and normalized_variety and cv_detected_variety != normalized_variety:
        has_complete_payload = False
        api_error = f"Variety mismatch: Computer vision detected {cv_detected_variety}, but agronomic input selected {normalized_variety}. Please select the matching variety."
        missing_fields.append("matching variety")
    if has_complete_payload:
        try:
            prediction_response = predict_variety_metrics(
                variety=payload["variety"],
                hectares=payload["hectares"],
                visual_features=payload["visual_features"],
                agronomic_input=payload["agronomic_input"],
                custom_weights=payload["custom_weights"],
                cv_maturity_status=payload["cv_maturity_status"],
            )
        except Exception as exc:
            api_error = str(exc)
    else:
        if not variety:
            missing_fields.append("variety")
        if hectares_value is None:
            missing_fields.append("hectares")
        if rssi_value is None:
            missing_fields.append("rssi")
        if weeding_value is None:
            missing_fields.append("weeding")
        if fertilizer_value is None:
            missing_fields.append("fertilizer")
        if ratoon_value is None:
            missing_fields.append("ratoon stage")
        if plowing_value is None:
            missing_fields.append("plowing")
        api_error = "Missing required fields for prediction: " + ", ".join(missing_fields) + "." if missing_fields else "Missing required fields for prediction."
    recommendation_input = {"rssi": rssi_value, "weeding": weeding_value, "fertilizer": fertilizer_value, "ratoon": ratoon_value, "plowing": plowing_value}
    generated_recommendations = generate_recommendations(prediction_response=prediction_response, agronomic_input=recommendation_input, missing_fields=missing_fields, variety=normalized_variety)
    request.session["farmer_recommendations"] = generated_recommendations
    recommendations_summary = " | ".join(f"{item.get('category', 'General')}: {item.get('title', '')}" for item in generated_recommendations)
    if has_complete_payload and prediction_response:
        try:
            AgronomicLog.objects.create(
                user_id=user.id,
                scan=latest_scan,
                variety=normalized_variety or variety or None,
                hectares=hectares or None,
                plowing_count=plowing_count or None,
                weeding_count=weeding_count or None,
                fertilizer_count=fertilizer_count or None,
                ratoon_stage=ratoon_stage or None,
                rssi_infected=rssi_infected or None,
                predicted_lkg_tc=prediction_response.get("predicted_lkg_tc"),
                predicted_tc_ha=prediction_response.get("predicted_tc_ha"),
                predicted_lkg=prediction_response.get("predicted_lkg"),
                recommendations_summary=recommendations_summary or "No recommendation generated.",
                recommendations_snapshot=generated_recommendations,
            )
        except Exception:
            pass
    def maturity_label(value):
        if value is None:
            return "Not provided"
        if value < 75:
            return "Not Mature"
        if value <= 90:
            return "Mature"
        return "Over Mature"
    variety_display = normalized_variety or "Not provided"
    normalized_cv_maturity = normalize_cv_maturity_status(prediction_response.get("cv_maturity_status") or cv_maturity_status)
    if normalized_cv_maturity == "NOT_MATURE":
        maturity_display = "Not Mature (Computer Vision)"
    elif normalized_cv_maturity == "OVER_MATURE":
        maturity_display = "Over Mature (Computer Vision)"
    elif normalized_cv_maturity == "MATURE":
        maturity_display = "Mature (Computer Vision)"
    else:
        maturity_display = maturity_label(maturity_pct)
    def format_decimal(value):
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "Pending"
    crop_stage_display = prediction_response.get("crop_stage") or {"1": "New Plant (1)", "2": "1st ratoon (2nd)", "3": "2nd ratoon (3rd)"}.get((ratoon_stage or "").strip(), "Unknown")
    try:
        cv_confidence_pct = f"{float(cv_context.get('confidence')) * 100:.1f}%"
    except (TypeError, ValueError, AttributeError):
        cv_confidence_pct = "Pending"
    return render_template(
        request,
        "calculate_results.html",
        {
            "user": user,
            "variety_display": variety_display,
            "maturity_display": maturity_display,
            "lkg_tc_display": "Pending",
            "hectares_display": hectares if hectares else "Not provided",
            "predicted_lkg_tc_display": format_decimal(prediction_response.get("predicted_lkg_tc")),
            "predicted_tc_ha_display": format_decimal(prediction_response.get("predicted_tc_ha")),
            "crop_stage_display": crop_stage_display,
            "visual_grade_display": format_decimal(prediction_response.get("visual_grade")),
            "agronomic_adjustment_display": format_decimal(prediction_response.get("agronomic_adjustment")),
            "agronomic_multiplier_display": format_decimal(prediction_response.get("agronomic_multiplier")),
            "predicted_quality_grade_display": format_decimal(prediction_response.get("predicted_quality_grade")),
            "baseline_lkg_tc_display": format_decimal(prediction_response.get("baseline_lkg_tc")),
            "baseline_tc_ha_per_hectare_display": format_decimal(prediction_response.get("baseline_tc_ha_per_hectare")),
            "adjusted_baseline_tc_ha_display": format_decimal(prediction_response.get("adjusted_baseline_tc_ha")),
            "predicted_lkg_display": format_decimal(prediction_response.get("predicted_lkg")),
            "cv_model_display": cv_context.get("model_name") if cv_context else None,
            "cv_class_display": cv_context.get("class_name") if cv_context else None,
            "cv_variety_display": cv_detected_variety if cv_detected_variety else None,
            "cv_maturity_display": (normalized_cv_maturity if normalized_cv_maturity else None),
            "cv_confidence_display": cv_confidence_pct,
            "weights_used": prediction_response.get("weights_used") or {},
            "api_visual_features": prediction_response.get("input", {}).get("visual_features") or visual_features,
            "api_agronomic_input": prediction_response.get("input", {}).get("agronomic_input") or payload["agronomic_input"],
            "api_hectares": prediction_response.get("input", {}).get("hectares", hectares_value),
            "api_error": api_error,
            "plowing_count": plowing_count,
            "weeding_count": weeding_count,
            "fertilizer_count": fertilizer_count,
            "ratoon_stage": ratoon_stage,
            "rssi_infected": rssi_infected,
        },
    )


@farmer_login_required
def farmer_settings(request):
    user = current_user(request)
    error = None
    success = None
    profile_updated = False
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_profile":
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("phone", "").strip()
            province = request.POST.get("province", "").strip()
            municipality = request.POST.get("municipality", "").strip()
            barangay = request.POST.get("barangay", "").strip()
            if not email or not phone or not province or not municipality or not barangay:
                error = "Please complete your profile details."
            elif len(phone) != 11 or not phone.isdigit():
                error = "Phone number must be exactly 11 digits."
            elif User.objects.filter(email=email).exclude(pk=user.id).exists():
                error = "Email already exists."
            else:
                profile_photo = request.FILES.get("profile_photo")
                photo_bytes = None
                if profile_photo:
                    photo_bytes, error = prepare_profile_photo(profile_photo)
                old_photo = user.profile_photo_path
                new_photo = None
                if not error and photo_bytes:
                    new_photo = f"farmer-{user.id}-{secrets.token_hex(8)}.jpg"
                    try:
                        photo_dir = Path(settings.PRIVATE_UPLOAD_ROOT) / "profile_photos"
                        photo_dir.mkdir(parents=True, exist_ok=True)
                        (photo_dir / new_photo).write_bytes(photo_bytes)
                    except OSError:
                        error = "Could not save the profile photo. Please try again."
                if not error:
                    user.email = email
                    user.phone = phone
                    user.province = province
                    user.municipality = municipality
                    user.barangay = barangay
                    update_fields = ["email", "phone", "province", "municipality", "barangay"]
                    if new_photo or request.POST.get("remove_profile_photo") == "1":
                        user.profile_photo_path = new_photo or ""
                        update_fields.append("profile_photo_path")
                    user.save(update_fields=update_fields)
                    if old_photo and old_photo != user.profile_photo_path:
                        try:
                            (Path(settings.PRIVATE_UPLOAD_ROOT) / "profile_photos" / Path(old_photo).name).unlink(missing_ok=True)
                        except OSError:
                            pass
                    log_audit(f"Farmer updated profile details: {user.fullname}", user_id=user.id)
                    success = "Profile updated successfully."
                    profile_updated = True
        else:
            current_password = request.POST.get("current_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")
            if not current_password or not new_password or not confirm_password:
                error = "Please complete all password fields."
            elif not verify_and_upgrade_password(user, current_password, "password"):
                error = "Current password is incorrect."
            elif new_password != confirm_password:
                error = "New passwords do not match."
            elif current_password == new_password:
                error = "New password must be different from the current password."
            else:
                from django.contrib.auth.hashers import make_password

                user.password = make_password(new_password)
                user.save(update_fields=["password"])
                log_audit(f"Farmer updated password: {user.fullname}", user_id=user.id)
                success = "Password updated successfully."
    photo_available = bool(user.profile_photo_path and (
        Path(settings.PRIVATE_UPLOAD_ROOT) / "profile_photos" / Path(user.profile_photo_path).name
    ).is_file())
    return render_template(request, "farmer_settings.html", {"user": user, "error": error, "success": success, "profile_updated": profile_updated, "photo_available": photo_available})


def prepare_profile_photo(upload):
    if upload.size > 5 * 1024 * 1024:
        return None, "Profile photo must be 5 MB or smaller."
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(upload) as photo:
            if photo.format not in {"JPEG", "PNG", "WEBP"} or photo.width * photo.height > 20_000_000:
                return None, "Choose a JPEG, PNG or WebP photo under 20 megapixels."
            photo = ImageOps.exif_transpose(photo)
            photo = ImageOps.fit(photo.convert("RGB"), (512, 512))
            output = BytesIO()
            photo.save(output, format="JPEG", quality=86, optimize=True)
            return output.getvalue(), None
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None, "Choose a valid JPEG, PNG or WebP profile photo."


@require_GET
def farmer_profile_photo(request, user_id):
    user = User.objects.filter(pk=user_id).first()
    farmer = current_user(request)
    admin = current_admin(request) if not request.farmer_only else None
    if not user or not user.profile_photo_path or not ((farmer and farmer.id == user.id) or admin):
        raise Http404("Profile photo not found")
    photo_dir = (Path(settings.PRIVATE_UPLOAD_ROOT) / "profile_photos").resolve()
    photo_path = (photo_dir / Path(user.profile_photo_path).name).resolve()
    if not photo_path.is_relative_to(photo_dir) or not photo_path.is_file():
        raise Http404("Profile photo not found")
    response = FileResponse(photo_path.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@farmer_login_required
@require_POST
def farmer_feedback(request):
    user = current_user(request)
    feedback_message = request.POST.get("feedback_message", "").strip()
    if not feedback_message:
        return redirect("homepage", error="Please enter your feedback before submitting.")
    Feedback.objects.create(user_id=user.id, message=feedback_message)
    log_audit(f"Farmer feedback submitted by {user.fullname}", user_id=user.id)
    return redirect("homepage", message="Thank you. Your feedback was submitted successfully.")


@login_required
def admin_portal(request):
    current = current_admin(request)
    user_search = request.GET.get("user_search", "").strip()[:100]
    user_status = request.GET.get("user_status", "all")
    if user_status not in {"all", "active", "inactive"}:
        user_status = "all"
    total_users = User.objects.filter(is_archived=False, is_active=True).count()
    total_scans = Scan.objects.count()
    seven_days_ago = timezone.now() - timedelta(days=7)
    active_user_ids = User.objects.filter(is_archived=False, is_active=True).values_list("id", flat=True)
    active_farmers = Scan.objects.filter(created_at__gte=seven_days_ago, user_id__in=active_user_ids).values("user_id").distinct().count()
    pending_scans = Scan.objects.filter(status="pending", user_id__in=active_user_ids).count()
    users_query = User.objects.filter(is_archived=False)
    if user_search:
        users_query = users_query.filter(Q(fullname__icontains=user_search) | Q(email__icontains=user_search))
    if user_status != "all":
        users_query = users_query.filter(is_active=user_status == "active")
    user_filter_active = bool(user_search or user_status != "all")
    users_query = users_query.annotate(last_scan_at=Max("scans__created_at")).order_by("-id")
    users = list(users_query if user_filter_active else users_query[:6])
    for user in users:
        user.last_scan_display = timezone.localtime(user.last_scan_at).strftime("%b %d, %Y") if user.last_scan_at else None
    now = timezone.now()
    logs = list(AuditLog.objects.order_by("-timestamp", "-id")[:5])
    storage_utilization = 68
    stats = {"active_users": total_users, "total_scans": total_scans, "active_farmers": active_farmers, "pending_scans": pending_scans, "storage_utilization": storage_utilization}
    metric_trends = {
        "active_users": "+12% from last week" if total_users else "Waiting for first users",
        "total_scans": "+18% from last week" if total_scans else "Waiting for first scan",
        "active_farmers": "Last 7 days",
        "pending_scans": "Needs review" if pending_scans else "All clear",
        "storage_utilization": "Steady vs last week" if storage_utilization < 70 else "+6% from last week",
    }
    for log in logs:
        elapsed = now - log.timestamp
        total_minutes = max(0, int(elapsed.total_seconds() // 60))
        if total_minutes < 1:
            relative = "Just now"
        elif total_minutes < 60:
            relative = f"{total_minutes}m ago"
        else:
            total_hours = total_minutes // 60
            relative = f"{total_hours}h ago" if total_hours < 24 else f"{total_hours // 24}d ago"
        log.relative_time = relative
        log.exact_time = timezone.localtime(log.timestamp).strftime("%b %d, %Y %I:%M %p %Z")
    return render_template(request, "admin.html", {"total_users": total_users, "users": users, "logs": logs, "current_admin": current, "stats": stats, "metric_trends": metric_trends, "user_search": user_search, "user_status": user_status, "user_filter_active": user_filter_active})


@login_required
def admin_farmers(request):
    message = request.GET.get("message")
    error = request.GET.get("error")
    search = request.GET.get("search", "").strip()
    if request.method == "POST":
        action = request.POST.get("action")
        current = current_admin(request)
        if action == "create":
            fullname = request.POST.get("fullname", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("phone", "").strip()
            province = request.POST.get("province", "").strip()
            municipality = request.POST.get("municipality", "").strip()
            barangay = request.POST.get("barangay", "").strip()
            password = request.POST.get("password", "").strip()
            if not fullname or not email or not phone or not password:
                return redirect("admin_farmers", error="Please complete all required fields.", open_create="1")
            if len(phone) != 11 or not phone.isdigit():
                return redirect("admin_farmers", error="Phone number must be exactly 11 digits.", open_create="1")
            if len(password) < 8:
                return redirect("admin_farmers", error="Password must be at least 8 characters.", open_create="1")
            if User.objects.filter(email=email).exists():
                return redirect("admin_farmers", error="Email already exists.", open_create="1")
            from django.contrib.auth.hashers import make_password

            User.objects.create(fullname=fullname, email=email, phone=phone, password=make_password(password), province=province, municipality=municipality, barangay=barangay, is_active=True, is_archived=False)
            log_audit(f"Admin created farmer account: {fullname}", user_id=current.id if current else None)
            return redirect("admin_farmers", message="Farmer account created successfully.")
        if action == "reset":
            user = User.objects.filter(pk=request.POST.get("user_id"), is_archived=False).first()
            if user:
                from django.contrib.auth.hashers import make_password

                temp_password = f"VISCANE-{secrets.token_urlsafe(6)}"
                user.password = make_password(temp_password)
                user.save(update_fields=["password"])
                log_audit(f"Farmer credentials reset: {user.fullname}", user_id=current.id if current else None)
                return redirect("admin_farmers", message=f"Temporary password for {user.fullname}: {temp_password}")
            return redirect("admin_farmers", error="Unable to reset credentials.")
        if action == "deactivate":
            user = User.objects.filter(pk=request.POST.get("user_id"), is_archived=False, is_active=True).first()
            if user:
                user.is_active = False
                user.save(update_fields=["is_active"])
                log_audit(f"Farmer account deactivated: {user.fullname}", user_id=current.id if current else None)
                return redirect("admin_farmers", message=f"{user.fullname} has been deactivated.")
            return redirect("admin_farmers", error="Unable to deactivate account.")
        if action == "activate":
            user = User.objects.filter(pk=request.POST.get("user_id"), is_archived=False, is_active=False).first()
            if user:
                user.is_active = True
                user.save(update_fields=["is_active"])
                log_audit(f"Farmer account activated: {user.fullname}", user_id=current.id if current else None)
                return redirect("admin_farmers", message=f"{user.fullname} has been reactivated.")
            return redirect("admin_farmers", error="Unable to activate account.")
        if action == "delete":
            user = User.objects.filter(pk=request.POST.get("user_id"), is_archived=False).first()
            if user:
                user.is_archived = True
                user.is_active = False
                user.save(update_fields=["is_archived", "is_active"])
                log_audit(f"Farmer account deleted: {user.fullname}", user_id=current.id if current else None)
                return redirect("admin_farmers", message=f"{user.fullname}'s account has been deleted.")
            return redirect("admin_farmers", error="Unable to delete account.")

    users_query = User.objects.filter(is_archived=False)
    total_farmers = users_query.count()
    active_count = users_query.filter(is_active=True).count()
    inactive_count = users_query.filter(is_active=False).count()
    if search:
        users_query = users_query.filter(Q(fullname__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search) | Q(province__icontains=search) | Q(municipality__icontains=search) | Q(barangay__icontains=search))
    paginator = Paginator(users_query.order_by("-id"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = [
        None if str(number) == str(Paginator.ELLIPSIS) else number
        for number in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    ]
    return render_template(request, "admin_farmers.html", {
        "users": list(page_obj.object_list),
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "total_farmers": total_farmers,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "message": message,
        "error": error,
        "open_create": request.GET.get("open_create") == "1",
        "search": search,
        "search_query": urlencode({"search": search}) if search else "",
        "current_admin": current_admin(request),
    })


@login_required
def admin_farmer_edit(request, user_id):
    user = User.objects.filter(pk=user_id).first()
    if not user or user.is_archived:
        return redirect("admin_farmers")
    if request.method == "POST":
        fullname = request.POST.get("fullname", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        province = request.POST.get("province", "").strip()
        municipality = request.POST.get("municipality", "").strip()
        barangay = request.POST.get("barangay", "").strip()
        if not fullname or not email or not phone:
            return redirect("admin_farmer_edit", user_id=user.id, error="Please complete all required fields.")
        if len(phone) != 11 or not phone.isdigit():
            return redirect("admin_farmer_edit", user_id=user.id, error="Phone number must be exactly 11 digits.")
        if User.objects.filter(email=email).exclude(pk=user.id).exists():
            return redirect("admin_farmer_edit", user_id=user.id, error="Email already exists.")
        user.fullname = fullname
        user.email = email
        user.phone = phone
        user.province = province
        user.municipality = municipality
        user.barangay = barangay
        user.save()
        log_audit(f"Farmer account updated: {user.fullname}", user_id=current_admin(request).id if current_admin(request) else None)
        return redirect("admin_farmers", message="Farmer account updated.")
    return render_template(request, "admin_farmer_edit.html", {"user": user, "error": request.GET.get("error"), "current_admin": current_admin(request)})


@login_required
def admin_monitoring(request):
    search = request.GET.get("search", "").strip()
    variety = request.GET.get("variety", "").strip()
    status = request.GET.get("status", "").strip()
    base_logs = AgronomicLog.objects.select_related("user").order_by("-created_at")
    total_predictions = base_logs.count()
    today_predictions = base_logs.filter(created_at__date=timezone.localdate()).count()
    completed_predictions = base_logs.filter(predicted_lkg__isnull=False).count()
    averages = base_logs.aggregate(avg_lkg_tc=Avg("predicted_lkg_tc"), avg_lkg_ha=Avg("predicted_tc_ha"))
    variety_options = list(
        base_logs.exclude(variety__isnull=True).exclude(variety="")
        .values_list("variety", flat=True).distinct().order_by("variety")
    )
    logs = base_logs
    if search:
        logs = logs.filter(
            Q(user__fullname__icontains=search)
            | Q(variety__icontains=search)
            | Q(rssi_infected__icontains=search)
        )
    if variety:
        logs = logs.filter(variety=variety)
    if status == "completed":
        logs = logs.filter(predicted_lkg__isnull=False)
    elif status == "pending":
        logs = logs.filter(predicted_lkg__isnull=True)
    paginator = Paginator(logs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    monitoring_rows = []
    for log in page_obj.object_list:
        monitoring_rows.append({"farmer_name": log.user.fullname if log.user else f"User #{log.user_id}", "variety": log.variety or "N/A", "hectares": log.hectares or "N/A", "predicted_lkg_tc": round(log.predicted_lkg_tc, 2) if log.predicted_lkg_tc is not None else None, "predicted_tc_ha": round(log.predicted_tc_ha, 2) if log.predicted_tc_ha is not None else None, "predicted_lkg": round(log.predicted_lkg, 2) if log.predicted_lkg is not None else None, "rssi_infected": log.rssi_infected or "N/A", "created_at": log.created_at})
    page_numbers = [None if str(number) == str(Paginator.ELLIPSIS) else number for number in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)]
    filter_values = {"search": search, "variety": variety, "status": status}
    query_string = urlencode({key: value for key, value in filter_values.items() if value})
    return render_template(request, "admin_monitoring.html", {
        "rows": monitoring_rows,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "query_string": query_string,
        "search": search,
        "selected_variety": variety,
        "selected_status": status,
        "variety_options": variety_options,
        "total_predictions": total_predictions,
        "today_predictions": today_predictions,
        "completed_predictions": completed_predictions,
        "avg_lkg_tc": round(averages["avg_lkg_tc"] or 0, 2),
        "avg_lkg_ha": round(averages["avg_lkg_ha"] or 0, 2),
        "current_admin": current_admin(request),
    })


@login_required
@require_GET
def admin_models(request):
    config = get_system_config()
    admin = current_admin(request)
    return render_template(
        request,
        "admin_models.html",
        {
            "config": config,
            "model_deployed": bool(config.model_filename),
            "can_manage_model": bool(admin and admin.role == "superadmin"),
            "current_admin": admin,
        },
    )


@login_required
def admin_reports(request):
    logs = AgronomicLog.objects.select_related("user").order_by("-created_at")
    farmer_summary = {}
    municipality_summary = {}
    total_predictions = 0
    total_lkg_tc = 0.0
    total_tc_ha = 0.0
    total_lkg = 0.0
    lkg_tc_count = 0
    tc_ha_count = 0
    latest_prediction_at = None
    for log in logs:
        if not log.user or log.user.is_archived:
            continue
        entry = farmer_summary.setdefault(log.user_id, {"user": log.user, "count": 0, "lkg_tc_count": 0, "tc_ha_count": 0, "total_lkg_tc": 0.0, "total_tc_ha": 0.0, "total_lkg": 0.0})
        entry["count"] += 1
        total_predictions += 1
        if latest_prediction_at is None:
            latest_prediction_at = log.created_at
        if log.predicted_lkg_tc is not None:
            entry["lkg_tc_count"] += 1
            entry["total_lkg_tc"] += float(log.predicted_lkg_tc)
            total_lkg_tc += float(log.predicted_lkg_tc)
            lkg_tc_count += 1
        if log.predicted_tc_ha is not None:
            entry["tc_ha_count"] += 1
            entry["total_tc_ha"] += float(log.predicted_tc_ha)
            total_tc_ha += float(log.predicted_tc_ha)
            tc_ha_count += 1
        if log.predicted_lkg is not None:
            entry["total_lkg"] += float(log.predicted_lkg)
            total_lkg += float(log.predicted_lkg)
        municipality = log.user.municipality or "Unspecified"
        location = municipality_summary.setdefault(municipality, {"name": municipality, "predictions": 0, "farmer_ids": set(), "total_lkg": 0.0})
        location["predictions"] += 1
        location["farmer_ids"].add(log.user_id)
        if log.predicted_lkg is not None:
            location["total_lkg"] += float(log.predicted_lkg)
    rows = []
    for user_id, summary in farmer_summary.items():
        user = summary["user"]
        rows.append({"name": user.fullname, "municipality": user.municipality or "N/A", "barangay": user.barangay or "N/A", "predictions": summary["count"], "avg_lkg_tc": round(summary["total_lkg_tc"] / summary["lkg_tc_count"], 2) if summary["lkg_tc_count"] else 0, "avg_lkg_ha": round(summary["total_tc_ha"] / summary["tc_ha_count"], 2) if summary["tc_ha_count"] else 0, "total_lkg": round(summary["total_lkg"], 2)})
    rows = sorted(rows, key=lambda item: item["predictions"], reverse=True)
    max_location_predictions = max((item["predictions"] for item in municipality_summary.values()), default=0)
    locations = []
    for item in sorted(municipality_summary.values(), key=lambda value: value["predictions"], reverse=True)[:5]:
        locations.append({
            "name": item["name"],
            "predictions": item["predictions"],
            "farmers": len(item["farmer_ids"]),
            "total_lkg": round(item["total_lkg"], 2),
            "share": round((item["predictions"] / max_location_predictions) * 100) if max_location_predictions else 0,
        })
    report = {
        "farms": len(rows),
        "municipalities": len(municipality_summary),
        "total_predictions": total_predictions,
        "avg_lkg_tc": round(total_lkg_tc / lkg_tc_count, 2) if lkg_tc_count else 0,
        "avg_lkg_ha": round(total_tc_ha / tc_ha_count, 2) if tc_ha_count else 0,
        "total_lkg": round(total_lkg, 2),
        "latest_prediction_at": latest_prediction_at,
        "top_farm": rows[0] if rows else None,
    }
    search = request.GET.get("search", "").strip()
    municipality_filter = request.GET.get("municipality", "").strip()
    municipality_options = sorted({row["municipality"] for row in rows if row["municipality"] != "N/A"})
    filtered_rows = rows
    if search:
        lowered_search = search.lower()
        filtered_rows = [
            row for row in filtered_rows
            if lowered_search in row["name"].lower()
            or lowered_search in row["municipality"].lower()
            or lowered_search in row["barangay"].lower()
        ]
    if municipality_filter:
        filtered_rows = [row for row in filtered_rows if row["municipality"] == municipality_filter]

    if request.GET.get("download") == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Farmer", "Municipality", "Barangay", "Predictions", "Average LKG/TC", "Average LKG/HA", "Total Predicted LKG"])
        for row in filtered_rows:
            writer.writerow([row["name"], row["municipality"], row["barangay"], row["predictions"], row["avg_lkg_tc"], row["avg_lkg_ha"], row["total_lkg"]])
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="viscane-farm-performance.csv"'
        return response

    paginator = Paginator(filtered_rows, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = [None if str(number) == str(Paginator.ELLIPSIS) else number for number in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)]
    filter_values = {"search": search, "municipality": municipality_filter}
    query_string = urlencode({key: value for key, value in filter_values.items() if value})
    report["filtered_farms"] = len(filtered_rows)
    return render_template(request, "admin_reports.html", {
        "rows": list(page_obj.object_list),
        "report": report,
        "locations": locations,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "query_string": query_string,
        "search": search,
        "selected_municipality": municipality_filter,
        "municipality_options": municipality_options,
        "current_admin": current_admin(request),
    })


@login_required
def admin_communications(request):
    message = request.GET.get("message")
    error = request.GET.get("error")
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        content = request.POST.get("message", "").strip()
        if title and content:
            current = current_admin(request)
            Notification.objects.create(title=title, message=content, created_by=current.id if current else None)
            log_audit(f"Announcement published: {title}", user_id=current.id if current else None)
            return redirect("admin_communications", message="Announcement published successfully.")
        return redirect("admin_communications", error="Add both a title and message before publishing.")

    search = request.GET.get("search", "").strip()
    notifications = list(Notification.objects.order_by("-created_at")[:8])
    feedback_query = Feedback.objects.order_by("-created_at")
    if search:
        matching_users = User.objects.filter(fullname__icontains=search).values_list("id", flat=True)
        feedback_query = feedback_query.filter(Q(message__icontains=search) | Q(user_id__in=matching_users))
    paginator = Paginator(feedback_query, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    feedback_entries = list(page_obj.object_list)
    feedback = []
    for entry in feedback_entries:
        farmer = User.objects.filter(pk=entry.user_id).first() if entry.user_id else None
        feedback.append({"farmer_label": farmer.fullname if farmer else (f"Farmer ID {entry.user_id}" if entry.user_id else "Unknown"), "message": entry.message, "created_at": entry.created_at})
    page_numbers = [None if str(number) == str(Paginator.ELLIPSIS) else number for number in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)]
    return render_template(request, "admin_communications.html", {
        "notifications": notifications,
        "feedback": feedback,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "search": search,
        "query_string": urlencode({"search": search}) if search else "",
        "total_announcements": Notification.objects.count(),
        "total_feedback": Feedback.objects.count(),
        "active_recipients": User.objects.filter(is_archived=False, is_active=True).count(),
        "message": message,
        "error": error,
        "current_admin": current_admin(request),
    })


def admin_login(request):
    if not Admin.objects.filter(is_archived=False).exists():
        return redirect("admin_setup")
    error = None
    success = request.GET.get("success")
    next_page = "admin_register" if (request.POST.get("next") or request.GET.get("next")) == "admin_register" else None
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip().lower()
        password = request.POST.get("password", "")
        admin = Admin.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier), is_archived=False).first()
        if admin and verify_and_upgrade_password(admin, password, "password_hash"):
            admin.save(update_fields=["password_hash"])
            request.session.cycle_key()
            request.session.pop("user_id", None)
            request.session["admin_id"] = admin.id
            return redirect(next_page or "admin_portal")
        error = "Invalid admin credentials. Please try again."
    return render_template(request, "admin_login.html", {"error": error, "success": success, "next_page": next_page})


def superadmin_login(request):
    if not Admin.objects.filter(is_archived=False).exists():
        return redirect("admin_setup")
    error = None
    success = request.GET.get("success")
    next_page = "superadmin_register" if (request.POST.get("next") or request.GET.get("next")) == "superadmin_register" else None
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip().lower()
        password = request.POST.get("password", "")
        admin = Admin.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier), is_archived=False).first()
        if admin and verify_and_upgrade_password(admin, password, "password_hash"):
            admin.save(update_fields=["password_hash"])
            if admin.role != "superadmin":
                error = "Your account is not authorized for superadmin access."
            else:
                request.session.cycle_key()
                request.session.pop("user_id", None)
                request.session["admin_id"] = admin.id
                return redirect(next_page or "superadmin_portal")
        else:
            error = "Invalid superadmin credentials. Please try again."
    return render_template(request, "superadmin_login.html", {"error": error, "success": success, "next_page": next_page})


def admin_setup(request):
    if Admin.objects.filter(is_archived=False).exists():
        return redirect("admin_login")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")
        if not username or not email or not password:
            error = "Please complete all fields."
        elif password != confirm:
            error = "Passwords do not match."
        elif Admin.objects.filter(Q(username__iexact=username) | Q(email__iexact=email)).exists():
            error = "An admin account with those details already exists."
        else:
            from django.contrib.auth.hashers import make_password

            admin = Admin.objects.create(username=username, email=email, password_hash=make_password(password), role="superadmin")
            request.session.cycle_key()
            request.session.pop("user_id", None)
            request.session["admin_id"] = admin.id
            log_audit(f"Superadmin account created: {admin.username}", user_id=admin.id)
            return redirect("admin_portal")
    return render_template(request, "admin_setup.html", {"error": error})


def _registration_authorizer(request, required_role=None):
    admin = current_admin(request)
    if admin and (required_role is None or admin.role == required_role):
        return admin
    if request.method != "POST":
        return None
    identifier = request.POST.get("authorizer_identifier", "").strip()
    password = request.POST.get("authorizer_password", "")
    authorizer = Admin.objects.filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier), is_archived=False
    ).first() if identifier and password else None
    if not authorizer or (required_role and authorizer.role != required_role):
        return None
    original_hash = authorizer.password_hash
    if not verify_and_upgrade_password(authorizer, password, "password_hash"):
        return None
    if authorizer.password_hash != original_hash:
        authorizer.save(update_fields=["password_hash"])
    request.session.cycle_key()
    request.session.pop("user_id", None)
    request.session["admin_id"] = authorizer.id
    return authorizer


def admin_register(request):
    authorizer = _registration_authorizer(request)
    error = None
    success = request.GET.get("success")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        full_name = request.POST.get("full_name", "").strip() or username
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if not authorizer:
            error = "Enter an existing Admin or Superadmin account to authorize registration."
        elif not username or not email or not password or not confirm_password:
            error = "Please complete all registration fields."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif Admin.objects.filter(username__iexact=username).exists():
            error = "Username is already taken."
        elif Admin.objects.filter(email__iexact=email).exists():
            error = "Email is already registered."
        else:
            from django.contrib.auth.hashers import make_password

            Admin.objects.create(username=username, full_name=full_name, email=email, password_hash=make_password(password), role="admin", is_archived=False)
            log_audit(f"Admin account registered: {username}", user_id=authorizer.id)
            return redirect("admin_register", success="Admin account created successfully.")
    return render_template(request, "admin_register.html", {
        "error": error, "success": success, "authorization_required": authorizer is None,
        "form_values": request.POST if request.method == "POST" else {},
    })


def superadmin_register(request):
    authorizer = _registration_authorizer(request, required_role="superadmin")
    error = None
    success = request.GET.get("success")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        full_name = request.POST.get("full_name", "").strip() or username
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if not authorizer:
            error = "Enter an existing Superadmin account to authorize registration."
        elif not username or not email or not password or not confirm_password:
            error = "Please complete all registration fields."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif Admin.objects.filter(username__iexact=username).exists():
            error = "Username is already taken."
        elif Admin.objects.filter(email__iexact=email).exists():
            error = "Email is already registered."
        else:
            from django.contrib.auth.hashers import make_password

            Admin.objects.create(username=username, full_name=full_name, email=email, password_hash=make_password(password), role="superadmin", is_archived=False)
            log_audit(f"Superadmin account registered: {username}", user_id=authorizer.id)
            return redirect("superadmin_register", success="Superadmin account created successfully.")
    return render_template(request, "superadmin_register.html", {
        "error": error, "success": success, "authorization_required": authorizer is None,
        "form_values": request.POST if request.method == "POST" else {},
    })


@role_required("superadmin")
def admin_reset(request):
    error = None
    success = request.GET.get("success")
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip().lower()
        email = request.POST.get("email", "").strip().lower()
        new_password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")
        if len(new_password) < 8:
            error = "Password must be at least 8 characters."
        elif new_password != confirm:
            error = "Passwords do not match."
        else:
            admin = Admin.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()
            if not admin or admin.email.lower() != email:
                error = "Admin account not found with those details."
            else:
                from django.contrib.auth.hashers import make_password

                admin.password_hash = make_password(new_password)
                admin.save(update_fields=["password_hash"])
                success = "Password updated. You can sign in now."
    return render_template(request, "admin_reset.html", {"error": error, "success": success})


@role_required("superadmin")
def superadmin_portal(request):
    create_error = request.GET.get("create_error")
    create_success = request.GET.get("create_success")
    total_users = User.objects.filter(is_archived=False, is_active=True).count()
    total_admins = Admin.objects.filter(is_archived=False).count()
    seven_days_ago = timezone.now() - timedelta(days=7)
    active_user_ids = User.objects.filter(is_archived=False, is_active=True).values_list("id", flat=True)
    active_farmers = Scan.objects.filter(created_at__gte=seven_days_ago, user_id__in=active_user_ids).values("user_id").distinct().count()
    total_scans = Scan.objects.count()
    total_prediction_logs = AgronomicLog.objects.count()
    total_estimated_lkg_value = AgronomicLog.objects.aggregate(total=Sum("predicted_lkg"))["total"] or 0.0
    total_estimated_lkg = f"{float(total_estimated_lkg_value):,.2f}"
    pending_scans = Scan.objects.filter(status="pending", user_id__in=active_user_ids).count()
    admins = list(Admin.objects.filter(is_archived=False).order_by("-id"))
    recent_scans = list(Scan.objects.filter(user_id__in=active_user_ids).order_by("-created_at")[:6])
    recent_predictions = list(AgronomicLog.objects.order_by("-created_at")[:6])
    combined_cv_accuracy = None
    report_path = Path(settings.BASE_DIR) / "reports" / "cv_training_results_latest.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        accuracy = report.get("combined_accuracy_pct")
        if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool) and math.isfinite(accuracy) and 0 <= accuracy <= 100:
            combined_cv_accuracy = f"{accuracy:.2f}%"
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return render_template(request, "superadmin.html", {"total_users": total_users, "total_admins": total_admins, "active_farmers": active_farmers, "total_scans": total_scans, "total_prediction_logs": total_prediction_logs, "total_estimated_lkg": total_estimated_lkg, "pending_scans": pending_scans, "admins": admins, "recent_scans": recent_scans, "recent_predictions": recent_predictions, "create_error": create_error, "create_success": create_success, "current_admin": current_admin(request), "combined_cv_accuracy": combined_cv_accuracy})


@role_required("superadmin")
def superadmin_governance(request):
    active_queryset = User.objects.filter(is_archived=False, is_active=True)
    active_search = request.GET.get("search", "").strip()
    active_municipality = request.GET.get("municipality", "").strip()
    if active_search:
        active_queryset = active_queryset.filter(
            Q(fullname__icontains=active_search)
            | Q(email__icontains=active_search)
            | Q(phone__icontains=active_search)
        )
    if active_municipality:
        active_queryset = active_queryset.filter(municipality=active_municipality)
    users = list(active_queryset.order_by("-id"))
    all_active_users = User.objects.filter(is_archived=False, is_active=True)
    archived_users = list(User.objects.filter(is_archived=True).order_by("-id"))
    deactivated_users = list(User.objects.filter(is_archived=False, is_active=False).order_by("-id"))
    return render_template(request, "superadmin_governance.html", {
        "total_users": all_active_users.count(),
        "active_user_count": all_active_users.count(),
        "active_result_count": len(users),
        "active_search": active_search,
        "active_municipality": active_municipality,
        "municipalities": list(all_active_users.exclude(municipality="").values_list("municipality", flat=True).distinct().order_by("municipality")),
        "archived_user_count": len(archived_users),
        "deactivated_user_count": len(deactivated_users),
        "users": users,
        "archived_users": archived_users,
        "deactivated_users": deactivated_users,
        "current_admin": current_admin(request),
    })


@role_required("superadmin")
def superadmin_scan_gallery(request):
    uploads = list(CvScanUpload.objects.select_related("user").order_by("-created_at", "-id"))
    return render_template(request, "superadmin_scan_gallery.html", {"superadmin_cv_uploads": uploads, "current_admin": current_admin(request)})


@role_required("superadmin")
def superadmin_create_admin(request):
    current = current_admin(request)
    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip().lower()
    role = request.POST.get("role", "admin").strip().lower()
    password = request.POST.get("password", "")
    confirm_password = request.POST.get("confirm_password", "")
    if not username or not email or not password or not confirm_password:
        return redirect("superadmin_portal", create_error="Please complete all registration fields.")
    if not is_valid_admin_role(role):
        return redirect("superadmin_portal", create_error="Invalid role selected.")
    if password != confirm_password:
        return redirect("superadmin_portal", create_error="Passwords do not match.")
    if len(password) < 8:
        return redirect("superadmin_portal", create_error="Password must be at least 8 characters.")
    if Admin.objects.filter(username__iexact=username).exists():
        return redirect("superadmin_portal", create_error="Username is already taken.")
    if Admin.objects.filter(email__iexact=email).exists():
        return redirect("superadmin_portal", create_error="Email is already registered.")
    from django.contrib.auth.hashers import make_password

    new_admin = Admin.objects.create(username=username, email=email, password_hash=make_password(password), role=role, is_archived=False)
    if current:
        log_audit(f"{role.title()} account created: {username}", user_id=current.id)
    return redirect("superadmin_portal", create_success=f"{role.title()} account created successfully.")


@role_required("superadmin")
def superadmin_update_role(request):
    admin = Admin.objects.filter(pk=request.POST.get("admin_id")).first()
    role = request.POST.get("role", "admin")
    current = current_admin(request)
    if admin and not admin.is_archived and current and admin.id != current.id and is_valid_admin_role(role):
        admin.role = role
        admin.save(update_fields=["role"])
        log_audit(f"Admin role updated for {admin.username} to {role}", user_id=current.id)
    return redirect("superadmin_portal")


@role_required("superadmin")
def superadmin_archive_admin(request):
    admin = Admin.objects.filter(pk=request.POST.get("admin_id")).first()
    current = current_admin(request)
    if admin and current and admin.id != current.id:
        admin.is_archived = True
        admin.save(update_fields=["is_archived"])
        log_audit(f"Admin account archived: {admin.username}", user_id=current.id)
    return redirect("superadmin_portal")


@role_required("superadmin")
def superadmin_archive_user(request):
    user = User.objects.filter(pk=request.POST.get("user_id")).first()
    current = current_admin(request)
    if user and not user.is_archived:
        user.is_archived = True
        user.save(update_fields=["is_archived"])
        log_audit(f"User account archived: {user.fullname}", user_id=current.id if current else None)
    return redirect("superadmin_governance")


@role_required("superadmin")
def superadmin_user_details(request, user_id):
    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise Http404("User not found")
    scans = list(Scan.objects.filter(user_id=user.id).order_by("-created_at"))
    agronomic_logs = list(AgronomicLog.objects.filter(user_id=user.id).order_by("-created_at"))
    feedback_entries = list(Feedback.objects.filter(user_id=user.id).order_by("-created_at"))
    audit_logs = list(AuditLog.objects.filter(action__icontains=user.fullname).order_by("-timestamp"))
    activity_items = []
    for scan in scans:
        activity_items.append({"kind": "Scan", "title": scan.plot_name, "meta": f"Grade {scan.grade} | Maturity {scan.maturity_pct}% | Status {scan.status.title()}", "timestamp": scan.created_at})
    for log in agronomic_logs:
        activity_items.append({"kind": "Agronomic Log", "title": log.variety or "Agronomic entry", "meta": f"Hectares {log.hectares or 'N/A'} | Predicted LKG {round(log.predicted_lkg, 2) if log.predicted_lkg is not None else 'N/A'}", "timestamp": log.created_at})
    for entry in feedback_entries:
        preview = entry.message[:90] + ("..." if len(entry.message) > 90 else "")
        activity_items.append({"kind": "Feedback", "title": "Farmer feedback submitted", "meta": preview, "timestamp": entry.created_at})
    for log in audit_logs:
        activity_items.append({"kind": "Audit", "title": log.action, "meta": f"Actor ID: {log.user_id if log.user_id is not None else 'System'}", "timestamp": log.timestamp})
    activity_items.sort(key=lambda item: item["timestamp"] or datetime.min, reverse=True)
    return render_template(request, "superadmin_user_details.html", {"user": user, "scans": scans, "agronomic_logs": agronomic_logs, "feedback_entries": feedback_entries, "audit_logs": audit_logs, "activity_items": activity_items[:25], "current_admin": current_admin(request)})


@role_required("superadmin")
def superadmin_restore_user(request):
    user = User.objects.filter(pk=request.POST.get("user_id")).first()
    current = current_admin(request)
    if user and user.is_archived:
        user.is_archived = False
        user.save(update_fields=["is_archived"])
        log_audit(f"User account restored: {user.fullname}", user_id=current.id if current else None)
    if user:
        return redirect("superadmin_user_details", user_id=user.id)
    return redirect("superadmin_portal")


def admin_logout(request):
    request.session.flush()
    return redirect("portal")


def auth(request):
    mode = request.GET.get("mode", "login")
    if request.method == "POST":
        if mode == "register":
            fullname = request.POST.get("fullname", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("phone", "").strip()
            password = request.POST.get("password", "")
            confirm = request.POST.get("confirm_password", "")
            province = request.POST.get("province", "").strip()
            municipality = request.POST.get("municipality", "").strip()
            barangay = request.POST.get("barangay", "").strip()
            if not fullname or not email or not phone or not password:
                return render_template(request, "auth.html", {"mode": mode, "error": "Please complete all required fields."})
            if len(phone) != 11 or not phone.isdigit():
                return render_template(request, "auth.html", {"mode": mode, "error": "Phone number must be exactly 11 digits."})
            if len(password) < 8:
                return render_template(request, "auth.html", {"mode": mode, "error": "Password must be at least 8 characters."})
            if password != confirm:
                return render_template(request, "auth.html", {"mode": mode, "error": "Passwords do not match."})
            if User.objects.filter(email=email).exists():
                return render_template(request, "auth.html", {"mode": mode, "error": "Email already registered."})
            from django.contrib.auth.hashers import make_password

            new_user = User.objects.create(fullname=fullname, email=email, phone=phone, password=make_password(password), province=province, municipality=municipality, barangay=barangay)
            request.session.cycle_key()
            request.session.pop("admin_id", None)
            request.session["user_id"] = new_user.id
            return redirect("auth_register_success")
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        user = User.objects.filter(email=email).first()
        if user and not user.is_archived and user.is_active and verify_and_upgrade_password(user, password, "password"):
            user.save(update_fields=["password"])
            request.session.cycle_key()
            request.session.pop("admin_id", None)
            request.session["user_id"] = user.id
            return redirect("homepage")
        if user and user.is_archived:
            return render_template(request, "auth.html", {"mode": mode, "error": "Account is archived. Please contact support."})
        if user and not user.is_active:
            return render_template(request, "auth.html", {"mode": mode, "error": "Account is deactivated. Please contact support."})
        return render_template(request, "auth.html", {"mode": mode, "error": "Invalid credentials. Please try again."})
    if request.headers.get("HX-Request"):
        return render_template(request, "auth_form.html", {"mode": mode})
    return render_template(request, "auth.html", {"mode": mode})


@farmer_login_required
def auth_register_success(request):
    user = current_user(request)
    if not user:
        return redirect("auth", mode="login")
    return render_template(request, "auth_register_success.html", {"user": user})


def logout(request):
    request.session.flush()
    return redirect("portal")


@farmer_login_required
def scan_new(request):
    error = None
    plot_name = ""
    ai_prediction_applied = False
    cv_context = {}
    if request.method == "GET" and request.GET.get("review") == "1":
        cv_context = request.session.get("latest_cv_context") or {}
        if cv_context and not supported_cv_confidence(cv_context):
            request.session.pop("latest_cv_context", None)
            cv_context = {}
    if request.method == "POST":
        plot_name = request.POST.get("plot_name", "").strip()
        ai_prediction_applied = request.POST.get("ai_prediction_applied", "") in {"1", "true", "True"}
        cv_context = request.session.get("latest_cv_context") or {}
        if not plot_name:
            error = "Please enter a plot name."
        elif not ai_prediction_applied:
            error = "Please scan an image before continuing."
        elif not supported_cv_confidence(cv_context):
            request.session.pop("latest_cv_context", None)
            error = INVALID_CV_IMAGE_MESSAGE
        else:
            derived_assessment = derive_scan_assessment(cv_context.get("maturity_status"), cv_context.get("confidence"))
            cv_upload = CvScanUpload.objects.filter(pk=cv_context.get("upload_id"), user_id=request.session.get("user_id")).first()
            if not derived_assessment or not cv_upload:
                error = "AI assessment is unavailable. Please scan the image again."
            else:
                Scan.objects.create(user_id=request.session.get("user_id"), cv_upload=cv_upload, plot_name=plot_name,
                    grade=derived_assessment["grade"], maturity_pct=derived_assessment["maturity_pct"], status=derived_assessment["status"])
                request.session["scan_result_variety"] = normalize_cv_variety_name(cv_context.get("normalized_variety") or cv_context.get("variety")) or ""
                log_audit(f"User {request.session.get('user_id')} uploaded a scan for {plot_name}", user_id=request.session.get("user_id"))
                return django_redirect("/homepage#calc-form")
    upload_id = cv_context.get("upload_id")
    cv_upload = CvScanUpload.objects.filter(pk=upload_id, user_id=request.session.get("user_id")).first() if upload_id else None
    review_prediction = {
        "variety": normalize_cv_variety_name(cv_context.get("normalized_variety") or cv_context.get("variety")),
        "maturity_status": cv_context.get("maturity_status"),
        "confidence": cv_context.get("confidence"),
    } if cv_upload else None
    confidence = cv_context.get("confidence") if review_prediction else None
    confidence_display = f"{float(confidence) * 100:.1f}%" if confidence is not None else ""
    return render_template(request, "scan_new.html", {
        "error": error,
        "plot_name": plot_name,
        "ai_prediction_applied": ai_prediction_applied and bool(review_prediction),
        "review_prediction": review_prediction,
        "review_preview_url": reverse("cv_upload_image", args=[cv_upload.pk]) if cv_upload else "",
        "confidence_display": confidence_display,
    })


@role_required("superadmin")
def superadmin_settings(request):
    config = get_system_config()
    if request.method == "POST":
        model_message = None
        model_file = request.FILES.get("model_file")
        if model_file and model_file.name:
            filename = os.path.basename(model_file.name)
            target_dir = get_model_updates_root()
            target_dir.mkdir(parents=True, exist_ok=True)
            file_path = target_dir / filename
            with file_path.open("wb") as target_file:
                for chunk in model_file.chunks():
                    target_file.write(chunk)
            config.model_filename = filename
            model_message = f"Model '{filename}' uploaded successfully."
        config.system_name = request.POST.get("system_name", "").strip() or config.system_name
        config.maintenance_mode = request.POST.get("maintenance_mode") == "on"
        config.save()
        current = current_admin(request)
        if current:
            log_audit("System settings updated", user_id=current.id)
            if model_message:
                log_audit(f"Model update received: {config.model_filename}", user_id=current.id)
        if model_message:
            return redirect("superadmin_settings", success=model_message)
        return redirect("superadmin_settings")
    return render_template(request, "superadmin_settings.html", {"config": config, "success": request.GET.get("success"), "current_admin": current_admin(request)})


@role_required("superadmin")
def superadmin_reports(request):
    logs = list(AgronomicLog.objects.select_related("user").order_by("-created_at"))
    total_predictions = len(logs)
    rows = []
    total_lkg_tc = 0.0
    total_tc_ha = 0.0
    total_lkg = 0.0
    lkg_tc_count = 0
    tc_ha_count = 0
    for log in logs:
        if log.predicted_lkg_tc is not None:
            total_lkg_tc += float(log.predicted_lkg_tc)
            lkg_tc_count += 1
        if log.predicted_tc_ha is not None:
            total_tc_ha += float(log.predicted_tc_ha)
            tc_ha_count += 1
        if log.predicted_lkg is not None:
            total_lkg += float(log.predicted_lkg)
        rows.append({"farmer_name": log.user.fullname if log.user else f"User #{log.user_id}", "variety": log.variety or "N/A", "hectares": log.hectares or "N/A", "predicted_lkg_tc": round(log.predicted_lkg_tc, 2) if log.predicted_lkg_tc is not None else None, "predicted_lkg_ha": round(log.predicted_tc_ha, 2) if log.predicted_tc_ha is not None else None, "predicted_lkg": round(log.predicted_lkg, 2) if log.predicted_lkg is not None else None, "created_at": log.created_at})
    report = {"avg_lkg_tc": round(total_lkg_tc / lkg_tc_count, 2) if lkg_tc_count else 0, "avg_lkg_ha": round(total_tc_ha / tc_ha_count, 2) if tc_ha_count else 0, "total_estimated_lkg": round(total_lkg, 2) if total_predictions else 0, "total_predictions": total_predictions}
    return render_template(request, "superadmin_reports.html", {"report": report, "rows": rows, "current_admin": current_admin(request)})


@role_required("superadmin")
def superadmin_reports_download(request):
    logs = list(AgronomicLog.objects.select_related("user").order_by("-created_at"))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Prediction ID", "Farmer Name", "Variety", "Hectares", "Predicted LKG/TC", "Predicted LKG/HA", "Predicted Total LKG", "RSSI Infected", "Created At"])
    for log in logs:
        farmer_name = log.user.fullname if log.user else f"User #{log.user_id}"
        writer.writerow([log.id, farmer_name, log.variety or "", log.hectares or "", round(log.predicted_lkg_tc, 2) if log.predicted_lkg_tc is not None else "", round(log.predicted_tc_ha, 2) if log.predicted_tc_ha is not None else "", round(log.predicted_lkg, 2) if log.predicted_lkg is not None else "", log.rssi_infected or "", log.created_at.strftime("%Y-%m-%d %H:%M:%S")])
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=superadmin_report.csv"
    return response


@role_required("superadmin")
def superadmin_audit(request):
    logs = list(AuditLog.objects.order_by("-timestamp")[:20])
    return render_template(request, "superadmin_audit.html", {"logs": logs, "current_admin": current_admin(request)})
