# Farmer dashboard visual refinement

## Account Settings spacing refinement

Following approval of the layout suggestions, Profile Details occupies the left column, with Password Update and Account stacked on the right. Mobile reading order is Profile Details, Password Update, Account. Submit buttons now appear after each form's fields and use full available width on phones. Decorative field icons are hidden, Location Details is left-aligned, and the read-only name has a muted surface and explanatory text.

All three password fields have associated labels, appropriate autocomplete values and Show/Hide controls using the existing delegated handler. Password guidance matches the current backend checks (different from the existing password, matching confirmation); no new length requirement was imposed. Existing success/error messages render inside the submitted form with status/alert semantics.

The existing profile/password action values, input names, location choices and required constraints remain unchanged. Tests passed at 1366, 768 and 390px: no overflow, submit buttons follow fields, all visibility toggles work, and Sign Out can scroll clear of the bottom navigation. A deliberately incorrect current password was rejected by the backend and its error appeared in Password Update only; no account change was saved. Screenshots: `artifacts/ui/account-settings-refined-*.png`.

## Companion pages

Recommendations, Agronomic Input Logs and Account Settings now load the dashboard stylesheet plus scoped `farmer-pages.css`. They share the light canvas, compact header (including the existing language control), white cards, green actions and bottom navigation. Recommendation rows have clearer category/content/tag hierarchy, input logs use readable separated content rows, and Profile uses consistent labeled controls with a single-column layout on smaller screens. No fields, labels, options, form actions, workflow scripts or navigation destinations were changed.

All three pages passed browser checks at 1366, 768 and 390px (nine page/viewport combinations), with no document overflow or page JavaScript errors. Active navigation and language-control visibility were checked. Original form markup, translation labels and script blocks compare unchanged against pre-edit snapshots. Both Profile forms were filled and intercepted at submission to verify their existing action values without saving changes. The existing test account has no agronomic logs, so its empty state was exercised; a populated history was not generated. Screenshots are in `artifacts/ui/farmer_recommendations-*.png`, `farmer_agronomic_logs-*.png` and `farmer_settings-*.png`.

The supplied reference guides the light canvas, scan banner, summary cards, assessment layout, result placement and bottom navigation. Styling is scoped to the homepage through `static/css/farmer-dashboard.css`.

## Visual changes

- Replaced the full-screen photo and glass dashboard surfaces with a pale agricultural background, white cards, restrained shadows and green actions.
- Consolidated the greeting, date, language selector and Settings into one compact header.
- Added a decorative phone/scan illustration using the existing image asset. Open Camera and Upload Photo retain their behavior.
- Improved summary hierarchy with local SVG icons and subtle green, blue and amber accents.
- Removed nested assessment-card surfaces. The existing controls sit in a two-column grid on larger screens and one column on phones; Hectares and Calculate span the available width.
- Placed Recent Scans and Scan Gallery immediately after assessment, ahead of Farmer Pages and News & Announcements. Feedback remains available.
- Refined existing bottom navigation and touch targets, with content padding so the final controls can scroll clear of the fixed navigation.

## Preserved system behavior

The entire assessment form markup and all existing workflow script blocks compare byte-for-byte with the pre-refinement template snapshot. Input names, values, available options, hidden CV fields, labels and form action are unchanged. Camera, upload, feedback, image removal, language selection and navigation destinations remain intact.

The reference's sample statistics, assessment labels, news and navigation names were not substituted for system data. For example, VISCANE still uses Scans Today, Number of Plowing, Infected by RSSI? and Hectares. No decorative notification indicator, new Reset behavior, fictional trend or fabricated result was added.

## Verification

Browser checks cover 1366px desktop, 768px tablet and 390px phone widths. Each check exercises Variety, Plowing, Weedings, Fertilizer, Ratoon, RSSI and Hectares and verifies the resulting values. Calculate is intercepted at submission to confirm its payload without creating an assessment. Upload Photo is clicked and reaches `/scan/new`. Tests also assert no document overflow or page JavaScript errors. Existing account sign-in is used; no new accounts are created.

Visual previews: `artifacts/ui/farmer-dashboard-1366.png`, `farmer-dashboard-768.png` and `farmer-dashboard-390.png`. These display the local test account's real data. No camera hardware or live prediction was exercised; those scripts are unchanged. External news images still depend on their original source.
