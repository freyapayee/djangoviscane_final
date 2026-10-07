# VISCANE User Manual

**Application:** VISCANE Sugarcane Variety, Maturity, and Agronomic Assessment System  
**Audience:** Farmers, administrators, and superadministrators  
**Version:** October 2026  
**Primary farmer device:** Android mobile phone  
**Languages:** English and Hiligaynon, where translations are available

## 1. About VISCANE

VISCANE helps farmers record sugarcane field information, scan a sugarcane image, review AI-based variety and maturity results, estimate production, and read agronomic recommendations. Administrators use the web console to manage farmer accounts, review submissions, monitor predictions, publish announcements, and produce reports.

The system has two operating areas:

| Area | Main users | Recommended device |
|---|---|---|
| Farmer application | Farmers and field staff | Android phone |
| Administration console | Admins and superadmins | Desktop or laptop browser |

### Important limitation about offline use

The current Android application is a farmer-only WebView client. It requires access to the VISCANE server for login, image prediction, saving records, announcements, and feedback. It does **not** currently run the prediction model fully offline or provide guaranteed offline queue-and-sync behavior.

When the final offline-capable mobile release is enabled, the recommended behavior is:

1. The farmer records field details and captures photos without signal.
2. The phone stores the draft securely in an offline queue.
3. When connectivity returns, the farmer opens the app and selects **Sync**.
4. The app uploads queued records and images, receives prediction results, and marks each item **Synced**.
5. The farmer checks for conflicts or failed uploads before deleting local copies.

Until that offline queue is implemented and tested on a physical device, treat a record as saved only after the server confirms it.

## 2. Getting started

### For farmers

You need an active farmer account, the VISCANE Android application, and—when using the current release—an internet connection to the configured HTTPS server.

1. Open VISCANE.
2. Sign in with your registered email and password.
3. If you do not have an account, select **Register** and provide your name, email, phone number, and location.
4. Allow camera or gallery access when prompted if you plan to scan a crop.
5. Select **Hiligaynon** from the language selector if preferred.

### For administrators

Administrators use the protected web console, not the farmer APK. Open the supplied HTTPS administration URL and select the appropriate administrator login. Never share administrator credentials with farmers.

## 3. Farmer manual

### 3.1 Farmer dashboard

The dashboard provides access to:

- **Home:** current farmer overview and quick actions.
- **New Scan:** capture or choose a sugarcane image.
- **Calculate / Assessment:** enter agronomic details and view estimates.
- **Recommendations:** view actions related to fertilizer, weeding, plowing, ratoon stage, and harvest planning.
- **Input Logs:** review saved agronomic assessments.
- **Profile:** update account details, language, and profile photo.
- **Feedback:** send a support message to the administration team.

Use the bottom navigation on a phone. Return to the dashboard before closing the app if a form is still being completed.

### 3.2 Create a sugarcane scan

1. Open **New Scan**.
2. Select **Use camera** to take a new photo, or **Choose photo** to select an existing image.
3. Photograph a clear sugarcane stalk or leaf in good lighting. Keep the subject in focus and avoid a busy background.
4. Review the image. Select **Change photo** if the crop is blurred, too dark, blocked, or too far away.
5. Review the AI result, including:
   - classification or variety;
   - maturity status or percentage; and
   - confidence score.
6. Select **Use this result** only when the photo and result are reasonable.
7. Enter the **Plot name** so the scan can be identified later.
8. Submit the assessment and wait for the completion message.

The displayed confidence is the model's confidence for that image. It is not the same as the overall measured accuracy of the model.

### 3.3 Enter agronomic information

Complete the assessment using the conditions of the same plot used for the scan:

- sugarcane variety;
- area in hectares;
- crop stage, such as new plant or ratoon stage;
- number of plowing activities;
- number of weeding activities;
- number of fertilizer applications; and
- RSSI or infected-stalk information when available.

Check units and values before submitting. If the AI variety is uncertain, select the variety that is supported by field records or local verification rather than blindly accepting the result.

### 3.4 Read calculation results

The result page can show:

- variety;
- hectares;
- maturity;
- crop stage;
- estimated LKG/TC;
- estimated TC/HA; and
- estimated total LKG.

These are estimates generated from the latest scan and manual inputs. They are not laboratory measurements and do not replace field inspection, laboratory testing, or actual harvest weighing.

Select **Recalculate** to correct the inputs or **See Recommendations** to continue.

### 3.5 Read recommendations

Recommendations are grouped around farm actions such as nutrient application, weed control, plowing, ratoon management, maturity, and harvest preparation. Read the recommendation together with the variety and crop stage shown on the page.

Use professional agronomic judgment and local guidance before applying chemicals or changing field practices. Do not treat an AI suggestion as a pesticide label, laboratory diagnosis, or guaranteed yield.

### 3.6 Review input logs

Open **Input Logs** to review previous agronomic assessments and their associated scan results. Use the plot name and date to distinguish fields. Keep the phone connected when opening recently created records if the current release has not synchronized them locally.

### 3.7 Announcements, feedback, and profile

Read announcements for maintenance notices, model updates, and operational instructions. Use **Feedback** to report an incorrect result, upload problem, account problem, or recommendation concern. Include the plot name, date, and a short description; do not include another person's password.

In **Profile**, update only your own information. Sign out after using a shared device.

### 3.8 Offline and weak-signal procedure

For the current release:

- do not assume that a scan is saved just because the result page appeared;
- wait for the success or saved confirmation;
- if a request fails, keep the original photo and field notes and retry when connected;
- do not submit the same scan repeatedly unless the previous attempt clearly failed; and
- avoid clearing app data or browser storage until pending work is confirmed.

For the final offline release, look for an explicit status such as **Saved on device**, **Waiting to sync**, **Syncing**, **Synced**, or **Sync failed**. Only records marked **Synced** should be treated as uploaded to the server.

## 4. Administrator manual

### 4.1 Admin dashboard

The Admin Console summarizes scan activity, farmer activity, data health, and recent system logs. Use the module tiles to open the detailed pages.

### 4.2 Manage farmer accounts

Open **Farmers** to search by name, email, phone, or address. Available actions include:

- create a farmer account;
- edit farmer information;
- reset a farmer password;
- deactivate or reactivate access; and
- delete an account when authorized by local policy.

Confirm the farmer's identity before changing account information. Prefer deactivation when access should be suspended temporarily. Verify the correct account before using delete because account-related records may be affected by the configured retention rules.

### 4.3 Monitor predictions

Open **Prediction Monitoring** to review submitted prediction and agronomic records. Search or filter by farmer, variety, RSSI, and status. Check pending records after connectivity or prediction-service incidents and investigate repeated failures before asking a farmer to resubmit.

### 4.4 Review AI model status

Open **AI Models** to view the active model package, deployment status, last configuration update, and whether the current administrator has view-only or management access. Model replacement is restricted to superadmins. Record the reason, validation result, and deployment date for every production model change.

### 4.5 View reports and export data

Open **Performance Reports** to compare reporting farms, municipalities, total predictions, average LKG/TC, average LKG/HA, and total predicted LKG. Use the search and municipality filters, then select **Export CSV** when a file is required for analysis or reporting.

Use the report as an operational summary. Predicted values should not be presented as confirmed harvest results.

### 4.6 View yield analytics

Open **Yield Analytics** to compare results by variety and maturity. Select a year and, when needed, a month. Review both the charts and the comparison details because the table contains the exact averages and totals used in the display.

### 4.7 Publish announcements and review feedback

Open **Communications** to:

1. Enter a short announcement title.
2. Write a clear message with the affected date, action, and contact instruction.
3. Select **Review & publish**.
4. Check the preview and confirm publication.
5. Search the feedback inbox for farmer support messages.

Announcements are visible to active farmers immediately. Do not publish unverified model, harvest, safety, or maintenance information.

### 4.8 Language and access

Administrators can use the language selector where available. Hiligaynon translations cover the main farmer workflows, but some live or uncommon content may remain in English. Review translated operational messages before publishing them.

## 5. Superadministrator manual

Superadmins have elevated access and should use it only for governance tasks:

- create administrator accounts;
- change administrator roles;
- archive administrator accounts;
- archive, restore, or inspect farmer accounts;
- review the scan gallery;
- manage model and system settings;
- download superadmin reports; and
- inspect the audit log.

Use separate named accounts. Do not use a superadmin account for routine farmer support. Archive access promptly when a staff member leaves or changes role.

## 6. Security and privacy practices

- Use only the official HTTPS address.
- Never share passwords or leave an administrator session open on a shared computer.
- Confirm account ownership before changing or resetting credentials.
- Upload only crop images and information needed for the assessment.
- Do not expose scan image files through a public static directory.
- Keep backups and private uploads protected and test restoration periodically.
- Report suspected unauthorized access immediately to the system owner.

The application uses session authentication, role restrictions, CSRF protection, input validation, password hashing, protected image delivery, and audit logging. These controls reduce risk but do not remove the need for careful account and device handling.

## 7. Troubleshooting

| Problem | Recommended action |
|---|---|
| Cannot sign in | Check the account details, connection, and account status. Ask an admin to verify whether the account is active. |
| Camera does not open | Grant camera permission, close other camera apps, then retry. Use **Choose photo** as a fallback. |
| Image rejected | Use JPG, PNG, or WebP; take a clear, focused photo with good lighting. |
| Prediction remains pending | Check the connection and prediction-service status. Do not repeatedly resubmit the same image. |
| Result looks incorrect | Retake the photo, verify the selected variety and field inputs, and send feedback with the plot name and date. |
| Data appears missing | Confirm that the save completed. For an offline-capable release, check the sync status and retry failed items. |
| Admin page is blocked | Confirm that the correct administrator URL and account are being used. The farmer APK intentionally cannot open admin endpoints. |
| Hiligaynon text is incomplete | Continue with the English label and report the phrase to the system owner for translation review. |

## 8. Data and prediction notes

VISCANE stores farmer accounts, scan uploads, scan results, agronomic logs, recommendations, notifications, feedback, system configuration, and audit events. Prediction results depend on image quality, model availability, selected variety, crop stage, and the accuracy of manual inputs.

The application supports the sugarcane varieties configured for the deployed model, including VMC 84-524, VMC 84-947, and MAURITIO RC888. The available varieties and model behavior may change after an authorized model update.

## 9. Support checklist

When escalating an issue, provide:

- user role and account email, without the password;
- phone or browser and operating-system version;
- date and approximate time of the issue;
- plot name or record identifier;
- whether the device was online, offline, or on weak signal;
- a screenshot or exact error message when safe to share; and
- whether the issue happened once or repeatedly.

This information helps administrators distinguish account problems, connectivity problems, image-quality problems, prediction-service failures, and synchronization failures.

## 3.10.5 Integration Architecture

Integration Architecture describes how VISCANE connects and communicates with its mobile client, web administration console, internal application modules, database, file storage, and external prediction services. The architecture is designed to keep farmer workflows simple while allowing administrators to monitor and manage the information produced by the system.

### 3.10.5.1 Integration components

| Component | Purpose | Integration method |
|---|---|---|
| Farmer Android application | Provides mobile access for login, image capture, scans, agronomic inputs, recommendations, history, announcements, and feedback. | HTTPS connection to the farmer-enabled Django application through the Android WebView client. |
| Administration web console | Allows administrators to manage farmer accounts, monitor predictions, review reports, publish announcements, and manage support feedback. | Browser-based HTTPS access to protected Django routes. |
| Django application server | Coordinates authentication, validation, business rules, recommendations, reporting, and access control. | Server-rendered web pages, authenticated sessions, CSRF-protected forms, and controlled HTTP requests. |
| Prediction service | Classifies sugarcane images and returns variety, maturity, and confidence information. | HTTP request to the configured `/predict` endpoint; production deployment should use private networking or TLS. |
| Database | Stores accounts, administrator records, scans, uploaded-image metadata, agronomic logs, recommendations, notifications, feedback, configuration, and audit events. | Django ORM and relational database connection, using PostgreSQL in production or SQLite for local fallback. |
| Private image storage | Stores uploaded crop images used by the computer-vision workflow. | Authenticated, ownership-checked image delivery through Django; direct public static access is restricted. |
| Translation and language support | Provides English and Hiligaynon interface text and optional translation of recommendation explanations. | Django language selection and local translation catalog; optional server-side DeepSeek API integration. |
| Hosting and operations services | Provides deployment, HTTPS, DNS protection, container execution, monitoring, and backup/recovery support. | Protected network and deployment configuration, with administrator access restricted separately from the farmer application. |

### 3.10.5.2 Main data flow

The normal online integration flow is:

1. The farmer signs in through the Android application.
2. The application sends an authenticated request over HTTPS to the Django server.
3. The farmer captures or selects a crop image and submits it with the plot and agronomic information.
4. Django validates the request, stores the upload metadata, and sends the image to the configured prediction service.
5. The prediction service returns the detected variety, maturity result, and confidence score.
6. Django combines the prediction with validated agronomic inputs to calculate estimates and generate recommendations.
7. The scan, assessment, prediction, and recommendation snapshot are stored in the database.
8. The result is returned to the farmer application, while authorized administrators can view the corresponding monitoring and reporting data.

### 3.10.5.3 Administrative and communication integration

The administration console reads authorized records from the same Django application and database. This allows administrators to search farmer accounts, filter prediction logs, compare yield analytics, export reports, publish announcements, and review feedback without directly exposing database credentials to the client devices.

Announcements are created by an authorized administrator and stored as notifications. Active farmer accounts retrieve the announcements through the farmer interface. Feedback follows the reverse direction: a farmer submits a message through the application, Django stores it, and administrators review it through the Communications module.

### 3.10.5.4 Security controls for integration

All client-to-server communication should use HTTPS/TLS. Django session authentication, role-based authorization, CSRF protection, input validation, password hashing, and ownership checks protect requests and records. The farmer application is restricted to farmer routes, while administration routes remain on the protected web console. Audit records provide accountability for important administrative actions and model or system changes.

### 3.10.5.5 Offline integration consideration

The current farmer Android client depends on the Django server for login, prediction, and record saving. It does not yet execute the prediction model locally or provide a guaranteed offline queue and synchronization service. Therefore, a result should be considered successfully integrated only after the server returns a save or completion confirmation.

For the planned offline-capable mobile release, the integration layer should add a secure local queue containing the image, farmer inputs, timestamp, and a unique record identifier. When connectivity returns, the client should upload queued records to a versioned synchronization endpoint, receive an acknowledgement, handle duplicate submissions idempotently, report conflicts, and mark each record as **Synced** only after server confirmation. This approach allows field work without signal while preserving data integrity when the device reconnects.
