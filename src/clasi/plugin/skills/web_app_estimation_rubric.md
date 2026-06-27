# Web Application Development Estimation Rubric

## Purpose

This rubric provides hour-range estimates for common web application features and tasks, based on industry data, developer forum anecdotes, and agency estimation guides. It is intended for use in bottom-up estimation: classify each ticket/feature against the appropriate category, apply the hour range, then sum for a total "traditional development" estimate.

All estimates assume **a single mid-level full-stack developer** working in a modern framework (React, Django, Laravel, Rails, Next.js, etc.) with standard tooling. Adjust upward for junior developers or unfamiliar stacks; adjust downward for senior developers reusing code from prior projects.

---

## Estimation Ground Rules

### Productivity Assumptions
- **Effective coding hours per 8-hour day:** 5–6 hours (meetings, context-switching, breaks consume the rest)
- **Effective coding hours per 40-hour week:** 32 hours (per Stack Overflow / Intersog data)
- **Standard overhead multiplier:** 1.2–1.5x on raw coding estimates (to account for planning, communication, PR review, minor rework)
- **QA/testing multiplier:** Add 25–40% of development time for testing (manual + automated)
- **Risk/uncertainty buffer:** 15–25% on top of total (more for novel integrations, less for well-understood CRUD)

### What "Hours" Mean
Each estimate below is **developer-hours of effort**, not calendar time. A 16-hour task might take 2–3 calendar days depending on interruptions, feedback loops, and context-switching overhead.

---

## 1. Project Setup & Infrastructure

| Task | Hours (Low) | Hours (High) | Notes |
|------|:-----------:|:------------:|-------|
| Repository setup (Git, README, .gitignore, basic CI) | 1 | 4 | Higher if CI/CD pipeline includes staging/prod |
| Dev environment setup (Docker, env files, local DB) | 2 | 8 | Higher for Docker Compose multi-service setups |
| Framework scaffolding (create-react-app, django-admin startproject, etc.) | 1 | 3 | Minimal if using CLI generators |
| Database schema design (initial) | 4 | 16 | Depends on number of entities and relationships |
| CI/CD pipeline (GitHub Actions / similar) | 4 | 16 | Basic = 4h; with staging, secrets management, automated testing = 16h |
| Production deployment setup (first deploy to hosting) | 4 | 16 | VPS/bare metal higher; PaaS like Heroku/Vercel lower |
| Domain, SSL, DNS configuration | 1 | 4 | Trivial with managed services; harder with custom setups |
| Monitoring & logging setup | 2 | 8 | Sentry, application logging, basic alerting |

**Subtotal range for a typical project:** 19–75 hours

---

## 2. Authentication & Authorization

| Task | Hours (Low) | Hours (High) | Notes |
|------|:-----------:|:------------:|-------|
| Email/password registration + login (using framework auth) | 4 | 12 | Low end: Laravel Auth, Django auth, NextAuth scaffolding. High end: custom implementation |
| Password reset flow (with email) | 2 | 8 | Includes email sending, token generation, reset form |
| Google OAuth / Social login (single provider) | 2 | 8 | Low: using Passport.js/Socialite/NextAuth with a library. High: manual OAuth flow. Indie Hackers survey suggests 1–12 hours depending on stack familiarity |
| Additional OAuth provider (each) | 1 | 4 | Incremental after the first one is working |
| Role-based access control (RBAC) | 4 | 16 | Simple (admin/user) = 4h; multi-role with permissions matrix = 16h |
| Session management & security hardening | 2 | 8 | CSRF, secure cookies, rate limiting, account lockout |
| Email verification flow | 2 | 6 | Confirmation emails, verification tokens |
| Two-factor authentication (2FA) | 4 | 12 | TOTP integration, backup codes, recovery flow |

**Typical auth system (email + Google OAuth + password reset + basic RBAC):** 14–44 hours

**Key anecdotal data points:**
- Indie Hackers forum: developers report 1 hour (using framework scaffolding) to 1 week (from scratch with full security), with most landing around 10–12 hours for a complete system
- Existek estimates: standard authentication page = ~$1,760 at $80/hr North American rate ≈ 22 hours
- Firebase/Auth0 approach: 30 min to 2 hours for basic auth, but integration and customization add time

---

## 3. CRUD Features (Per Entity/Resource)

A "CRUD entity" means one data type with create, read (list + detail), update, and delete operations, including both API endpoint and UI.

| Complexity | Hours (Low) | Hours (High) | Characteristics |
|------------|:-----------:|:------------:|-----------------|
| Simple CRUD | 4 | 10 | Single table, few fields, no complex validation, no relationships. E.g., "work types" (part-time, full-time) |
| Medium CRUD | 8 | 20 | Multi-field form, 1–2 relationships, dropdown selections from related tables, basic validation rules. E.g., "job postings" with category/qualification |
| Complex CRUD | 16 | 40 | Multiple relationships, complex business rules, file uploads, conditional logic, multi-step forms. E.g., "inventory items" with images, categories, status workflows |

**Per Existek's detailed breakdown:**
- Simple CRUD (single entity, minimal rules): ~$780 at $80/hr ≈ **10 hours** (front-end + back-end + testing)
- Medium CRUD (with business rules): ~$1,760 at $80/hr ≈ **22 hours**

**Per Quora developer estimates:**
- Basic CRUD in MVC framework with corresponding DB: 2 hours for data access layer, plus controller + views = roughly 4–8 hours total for a single entity (happy path only)

**Rule of thumb:** Count your entities, classify each, and sum. A typical small web app has 5–15 entities.

---

## 4. UI/UX & Frontend

| Task | Hours (Low) | Hours (High) | Notes |
|------|:-----------:|:------------:|-------|
| UI framework installation + base layout (Bootstrap/Tailwind) | 2 | 6 | CDN = minutes; custom Sass compilation + theme = 6h |
| Responsive navigation (header, sidebar, mobile menu) | 3 | 10 | Simple top nav = 3h; complex sidebar + hamburger + breadcrumbs = 10h |
| Dashboard/home page (with data widgets) | 8 | 24 | Static layout = 8h; dynamic charts, real-time data = 24h |
| Form design & validation (per complex form) | 2 | 8 | Simple contact form = 2h; multi-step form with conditional fields = 8h |
| Data table with search/sort/pagination | 4 | 12 | Using a library (DataTables, AG Grid) = 4h; custom implementation = 12h |
| Custom page/view (informational, about, settings) | 2 | 6 | Per page, depending on content and interactivity |
| Error handling & user feedback (toast notifications, loading states) | 2 | 6 | Global error handling, loading spinners, success/error messages |
| Responsive design QA & fixes | 4 | 16 | Cross-browser testing, mobile breakpoints |
| Print-friendly views / PDF export | 2 | 8 | CSS print styles = 2h; server-side PDF generation = 8h |
| Dark mode / theme switching | 2 | 8 | CSS variables approach = 2h; comprehensive theming = 8h |

**Overall "fit and finish" pass** (taking an app from functional to presentable): 16–40 hours, depending on page count and design ambition.

**Per Orange Hill Development's bottom-up example:**
- A single homepage with 6 background sections, custom fonts, buttons: ~205 minutes (3.4 hours) for HTML/CSS only, plus 20% contingency

---

## 5. Common Feature Modules

| Feature | Hours (Low) | Hours (High) | Notes |
|---------|:-----------:|:------------:|-------|
| Email sending (transactional) | 2 | 8 | SMTP/SendGrid setup + templates; higher if multiple email types |
| File upload (single) | 2 | 8 | Local storage = 2h; S3 with signed URLs + progress bar = 8h |
| File upload (multiple/drag-drop) | 4 | 12 | With preview, progress, error handling |
| Image handling (resize, thumbnails, gallery) | 4 | 12 | Server-side processing, responsive images |
| Search functionality (basic) | 4 | 12 | SQL LIKE queries = 4h; full-text search / Elasticsearch = 12h+ |
| Notifications (in-app) | 4 | 12 | Read/unread, real-time via WebSocket = 12h |
| CSV/Excel import | 4 | 12 | Simple format = 4h; complex validation, preview, error handling = 12h |
| CSV/Excel export | 2 | 8 | Basic data dump = 2h; formatted Excel with styling = 8h |
| Reporting / analytics page | 8 | 32 | Static charts = 8h; interactive dashboards with date filters, drill-down = 32h |
| PDF generation (invoices, reports) | 4 | 16 | Template-based = 4h; complex multi-page with headers/footers = 16h |
| Real-time updates (WebSockets) | 8 | 24 | Chat-like features, live dashboards |
| Calendar / scheduling view | 8 | 24 | Using library (FullCalendar) = 8h; custom = 24h |
| Payment integration (Stripe basic) | 8 | 24 | One-time payments = 8h; subscriptions with webhooks = 24h |
| QR code generation/scanning | 2 | 8 | Generation = 2h; scanning with mobile camera integration = 8h |
| Audit logging / activity history | 4 | 12 | Basic event recording = 4h; detailed user action tracking with UI = 12h |
| Multi-tenancy / organization accounts | 16 | 40 | Data isolation, org management, member invitations |
| API (REST, for external consumers) | 8 | 32 | Simple read-only = 8h; full CRUD with auth, rate limiting, docs = 32h |

---

## 6. Third-Party Integrations

| Integration | Hours (Low) | Hours (High) | Notes |
|-------------|:-----------:|:------------:|-------|
| Google Maps / geolocation | 4 | 12 | Display only = 4h; geocoding, custom markers, directions = 12h |
| Slack notifications | 2 | 8 | Webhook posting = 2h; interactive messages = 8h |
| External API consumption (per API) | 4 | 16 | Well-documented REST API = 4h; poorly documented or requiring complex auth = 16h |
| SSO (SAML/OIDC enterprise) | 16 | 40 | Highly variable based on IdP documentation quality |
| Google Drive/Sheets integration | 8 | 24 | Read-only = 8h; full sync = 24h |

**Per DreamFactory's API development guide:**
- Database design: 2–3 days
- Research phase: 2–3 days
- Prototyping: 2–3 days
- Security: 1–5 days
- Documentation: 2–3 days
- Monitoring/dashboard: 2–3 days
- **Total for a full API project: 20–30 working days**

---

## 7. Testing & QA

| Task | Hours (Low) | Hours (High) | Notes |
|------|:-----------:|:------------:|-------|
| Unit tests (per major module) | 2 | 8 | Per module; multiply by module count |
| Integration tests | 4 | 16 | API endpoint testing, DB interaction tests |
| End-to-end tests (Cypress/Playwright) | 8 | 24 | Critical path coverage for key user flows |
| Cross-browser testing & fixes | 4 | 16 | Chrome, Firefox, Safari, Edge; mobile |
| Manual QA pass (per round) | 4 | 16 | Per full regression test; plan for 3–5 rounds |
| Bug fixing (per round of QA) | 8 | 24 | Highly variable; plan for 50–100% of QA time |

**Per industry data:**
- Testing typically consumes 15–40 hours for moderately complex web apps
- Dynamic applications with auth and real-time features: 60+ hours for testing
- Plan for 8–10 rounds of QA on a website launch (per PJ Srivastava), which is the "other 50%" of project time

---

## 8. Documentation & Project Management

| Task | Hours (Low) | Hours (High) | Notes |
|------|:-----------:|:------------:|-------|
| Technical documentation | 4 | 16 | Setup guides, API docs, architecture decisions |
| User documentation / help text | 4 | 16 | In-app help, user guide |
| Project management overhead | 10% | 20% | Of total development time; planning, standups, coordination |
| Code review time | 10% | 15% | Of development time |

---

## 9. Complexity Tiers (Aggregate Estimates)

These aggregate ranges come from synthesizing the industry sources above. Use them as a sanity check against your bottom-up total.

| App Complexity | Total Hours | Calendar Time (1 dev) | Characteristics |
|---------------|:-----------:|:---------------------:|-----------------|
| Simple | 200–500 | 2–3 months | 3–5 CRUD entities, basic auth, minimal UI, no real-time, few integrations |
| Medium | 500–1,200 | 3–6 months | 8–15 entities, OAuth + RBAC, dashboard, reports, 2–3 integrations, responsive design |
| Complex | 1,200–2,500+ | 6–12+ months | 15+ entities, complex workflows, real-time features, payment processing, multi-tenancy, extensive testing |

**Industry data points for calibration:**
- Cleveroad: Simple app = 500–800 hours, medium = 800–1,200 hours, complex = 1,200+ hours
- Typical MVP delivery: 3–4 months with a team of 3–5 people = roughly 1,500–2,500 person-hours including design and PM
- Lunka.tech real-world MVP: 1,768 person-hours with 8 specialists
- One-developer MVPs using modern frameworks: commonly 400–800 hours

---

## 10. How to Use This Rubric

### Step-by-step process:

1. **Inventory your tickets/features.** Export your ticket list from your project management tool.

2. **Classify each ticket.** Map each ticket to one or more categories in this rubric (setup, auth, CRUD entity, UI task, feature module, integration, testing, etc.).

3. **Assign hour ranges.** For each ticket, determine if it falls at the low, mid, or high end of the range based on actual complexity observed in your documentation.

4. **Sum the estimates.** Add up all individual estimates to get a raw development total.

5. **Apply multipliers:**
   - **PM/communication overhead:** +15% of raw total
   - **Code review:** +10%
   - **Testing/QA:** +30% (unless testing is already itemized in tickets)
   - **Risk/uncertainty buffer:** +20%

6. **Convert to calendar time.** Divide total hours by 32 effective hours/week for a single developer, or by (32 × team_size × 0.8) for a team (the 0.8 accounts for coordination overhead).

7. **Compare to actual.** Your "traditional estimate" is this total. Compare against the actual hours/timeline you achieved.

### Adjustments for AI-assisted development:
If you are comparing traditional vs. AI-assisted timelines, note that AI coding tools typically show the largest speedups on:
- Boilerplate/scaffolding (setup, CRUD generation)
- UI component creation and styling
- Test writing
- Documentation

And the smallest speedups on:
- Complex business logic
- Debugging integration issues
- Architecture decisions
- Security hardening

---

## Sources & Methodology

Estimates synthesized from:
- Existek: Detailed CRUD and auth cost breakdowns at $80/hr North American rate
- Cleveroad: Complexity-tier hour ranges (500/800/1200+)
- Indie Hackers forum: Developer self-reports on auth implementation time
- DreamFactory: API development phase-by-phase time estimates
- Orange Hill Development: Bottom-up per-component estimation methodology
- Netguru, Pragmatic Coders, Purrweb: MVP timeline case studies
- Intersog: Man-hour estimation best practices
- Stack Overflow developer survey: Effective working hours data
- PJ Srivastava: QA round estimation and "the other 50%"
- Multiple Quora developer discussions on CRUD and API implementation times

All hour ranges represent the middle of the distribution — extreme outliers (brand-new developer on unfamiliar stack, or senior developer copy-pasting from identical prior project) are excluded.
