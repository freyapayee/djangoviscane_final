# VISCANE UI/UX Improvement Report

## Scope

This redesign modernizes the VISCANE presentation layer while preserving the existing routes, template variables, forms, authentication flow, database models, APIs, and prediction behavior. The interface now follows a reusable agricultural design system that maps cleanly to Android Material 3 and Jetpack Compose.

## Design system

| Token | Use |
|---|---|
| Agriculture green `#256B3F` | Primary actions and positive agricultural context |
| Deep green `#174C2D` | App bars, sidebars, and strong contrast surfaces |
| Earth brown `#80613E` | Natural secondary emphasis |
| AI blue `#2563A9` | Analytics, administrative actions, and technology context |
| Soft background `#F5F8F3` | Low-glare application background |
| Surface white `#FFFFFF` | Cards, forms, and data containers |
| Main text `#17231B` | High-contrast headings and body copy |
| Muted text `#5D6B61` | Supporting information |

The system uses a 4px spacing rhythm, 12–20px corner radii, 44px minimum interaction targets, visible keyboard focus, reduced-motion support, responsive grids, and restrained shadows.

## Before and after

### Landing page

**Before — Problem:** Portal selection appeared inside a small dark card. Role choices depended on whole-card click handlers, the product purpose was understated, and secondary controls lacked clear destinations.

**After — Improvement:** The page now presents a full-width product hero, one-sentence explanation, accessible farmer and administrator role cards, explicit links, language selection, system overview, and a direct registration path.

**Reason — UX benefit:** A first-time farmer can understand the product and identify the main action within ten seconds. Explicit links also improve keyboard and assistive-technology navigation.

### Authentication

**Before — Problem:** Inputs depended on placeholder text, passwords could not be revealed, submission progress was not visible, and the layout did not explain the value of signing in.

**After — Improvement:** Authentication uses a responsive split layout, persistent field labels, autocomplete hints, password visibility controls, native validation, phone guidance, loading feedback, and a concise benefit summary.

**Reason — UX benefit:** Persistent labels and familiar mobile controls reduce entry mistakes and make registration easier for users with limited technical experience.

### Farmer dashboard

**Before — Problem:** Important actions and data were present but the initial action hierarchy was weak, and quick-action space was unused.

**After — Improvement:** The welcome area now exposes Scan Sugarcane, View History, and Recommendations immediately. A summary row shows today's scans, seven-day maturity average, and latest grade before detailed assessment controls.

**Reason — UX benefit:** Scanning is reachable in one click from the dashboard, history in one click, and the three most useful indicators are visible without searching through the page.

### Image scanning

**Before — Problem:** The workflow was camera-led and displayed AI output as status text. Users without camera access lacked an obvious alternative, and classification, maturity, and confidence had no stable visual hierarchy.

**After — Improvement:** The scanner now supports camera capture and local image upload through the same existing prediction endpoint. It shows a preview and a structured result card with classification, maturity, and confidence. The manual scan-entry form remains unchanged.

**Reason — UX benefit:** Farmers can complete analysis despite camera permission or device limitations, and results are easier to read and compare.

### Administrator experience

**Before — Problem:** Administrative navigation was distributed across dashboard cards and header actions. Desktop pages lacked a persistent navigation model, and mobile navigation varied between sections.

**After — Improvement:** Administrator pages share a persistent desktop sidebar and a four-destination mobile bottom bar. The dashboard adds scan-processing and farmer-activity summaries using live template values.

**Reason — UX benefit:** Common management destinations remain visible, navigation is consistent across pages, and operational volume is easier to assess.

### Superadministrator experience

**Before — Problem:** Governance tools, user management, model metrics, and records were presented as one continuous page without persistent system-level navigation or an infrastructure summary.

**After — Improvement:** Superadministrator pages use their own system-control sidebar and mobile navigation. A health panel summarizes database availability, configured prediction models, and access-control records using existing server-rendered data.

**Reason — UX benefit:** System-level concerns are separated from routine administration and can be reviewed quickly on desktop or mobile.

### Responsive behavior and accessibility

**Before — Problem:** Responsive rules existed but were distributed across a large shared stylesheet and page-level CSS. Some pages used placeholder-only inputs, inaccessible click containers, and inconsistent focus treatment.

**After — Improvement:** A dedicated presentation layer standardizes responsive breakpoints, focus rings, touch sizes, navigation changes, card layouts, reduced motion, semantic links, labels, live result regions, and skip links.

**Reason — UX benefit:** The same content hierarchy works on desktop, tablet, and Android-sized screens, and the component model can be translated to `Scaffold`, `TopAppBar`, `NavigationBar`, `Card`, `TextField`, and `LazyColumn`.

## Reusable components

- `components/brand.html` provides one logo and product-name treatment.
- `components/admin_navigation.html` provides administrator desktop and mobile navigation.
- `components/superadmin_navigation.html` provides superadministrator desktop and mobile navigation.
- `viscane-ui.css` contains presentation tokens and responsive component styles.
- `viscane-ui.js` provides password visibility, form loading feedback, and active navigation state.

## UX evaluation

| Check | Result |
|---|---|
| Can a farmer understand the system within 10 seconds? | Pass — the landing hero states the purpose and presents two clear roles. |
| Can a farmer upload an image within 3 clicks? | Pass — Farmer Portal → sign in → Scan/Upload, or one click from an authenticated dashboard. |
| Are important actions obvious? | Pass — primary actions use filled buttons and appear before detailed inputs. |
| Are errors understandable? | Pass — existing backend errors remain visible, native validation is retained, and scan failures use a live status region. |
| Is navigation consistent? | Pass — farmer bottom navigation is retained, with shared administrator and superadministrator navigation added. |

## Verification

- Public landing, farmer login, farmer registration, and administrator access return HTTP 200.
- Authenticated farmer dashboard, recommendations, agronomic logs, settings, and scanning routes return HTTP 200.
- Authenticated administrator and superadministrator dashboard, management, reporting, audit, monitoring, model, communication, and settings routes return HTTP 200.
- The shared CSS and JavaScript assets return HTTP 200.
- Desktop landing and mobile authentication screenshots were captured for visual review under `.local/`.

## Agricultural identity refinement

The final refinement restores `background.png` as the full-screen visual foundation on landing, authentication, role-selection, and application screens. Dark green overlays preserve text contrast while keeping the sugarcane imagery visible. Landing, authentication, administrator access, dashboard, and scanner cards now use translucent white or green-tinted surfaces with blur, soft borders, and restrained shadows.

Authentication fields use identical 52px wrappers, consistent padding, dark input text, and high-contrast placeholders. Login and Register use a green segmented control with a 300ms transition. Administrator access now presents Admin and Superadmin as full role cards with an icon, explanation, and explicit action.

Page fade-in, card slide-up, and button hover transitions were added with a reduced-motion fallback. Desktop and 500px mobile-breakpoint screenshots confirm readable layouts while authenticated farmer, Admin, and Superadmin workflow checks continue to return HTTP 200.
