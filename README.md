# Briefly

Briefly turns Tableau dashboards into Google Slides decks for overworked managers and directors.

The product is intentionally narrow: **Tableau -> Google Slides**. Users should not feel like they are learning another reporting tool. They should connect their accounts, select the views they need, and generate a usable deck.

## Product Vision

Managers and directors repeatedly spend hours on low-value reporting work:

- Opening Tableau dashboards
- Taking screenshots of charts
- Pasting them into Google Slides
- Resizing visuals
- Updating numbers and commentary
- Repeating the same workflow every week or month

The dashboard already contains the trusted information. The deck is the communication layer.

Briefly removes the manual work between those systems.

## V1 Validation Goal

V1 is not primarily about proving that Tableau and Google Slides can be integrated. That is implementation work.

The real validation goal is proving that managers and directors will replace their manual **Tableau screenshot -> Google Slides** workflow with Briefly.

Success should be measured by:

- Repeat usage across weekly or monthly reporting cycles
- Decks used in real meetings
- Time saved versus the manual screenshot workflow
- Users returning without training or support

Success is not measured by number of integrations, enterprise feature coverage, or technical completeness.

## Product Principles

### 1. Connect, Select, Generate

The core workflow is:

1. Connect Tableau.
2. Connect Google.
3. Select Tableau views.
4. Generate a Google Slides deck.

Nothing else should be required for the first useful version.

### 2. Do Not Build Another BI Tool

Users already have Tableau. Briefly does not replace it.

Briefly is not a dashboard builder, reporting platform, analytics layer, or charting system. It is the bridge from trusted dashboard views to executive communication.

### 3. Respect Existing Workflows

Users already know Tableau and Google Slides. Briefly should fit around those tools instead of introducing a new place to create reports.

The product should feel less like software and more like a shortcut.

## Phase 0 MVP

The smallest useful version is:

1. User connects Tableau with OAuth.
2. User connects Google with OAuth.
3. User selects Tableau views.
4. User clicks **Generate**.
5. Briefly creates a brand-new Google Slides deck.
6. Each selected Tableau view becomes one slide.

Phase 0 should explicitly avoid:

- Template mapping
- Slide refresh
- Placeholder binding
- Scheduling
- AI commentary
- Existing deck updates
- Slide layout editing

Phase 0 proves whether the generated deck is useful enough to replace manual screenshots, even before advanced template support exists.

## V1 Product Hypotheses

- Users are willing to connect Tableau and Google if OAuth is simple.
- Users will accept rendered Tableau images if they are current, clean, and inserted reliably.
- Users care more about saving reporting time than perfect deck design in the first version.
- Users will tolerate a brand-new generated deck if it saves enough manual work.
- Users may ultimately care more about refreshing existing decks than generating new ones.
- The strongest early signal is repeat use for real recurring meetings.

## V1 User Experience

### Step 1: Connect Tableau

The user clicks **Connect Tableau** and completes OAuth. Briefly stores the refresh token securely. API keys are never exposed.

### Step 2: Connect Google

The user clicks **Connect Google** and grants access to create Google Slides presentations.

### Step 3: Select Tableau Views

The user sees available Tableau workbooks and views, then selects the views to include.

Example workbooks:

- Revenue Dashboard
- Customer Health
- Support Operations
- Security Metrics

Example views:

- Revenue Growth
- ARR Trend
- Customer Count
- Retention
- Pipeline

### Step 4: Generate

The user clicks **Generate**. Briefly starts an async job, exports the selected Tableau views as rendered images, creates a new Google Slides deck, inserts one image per slide, and returns the presentation URL.

## UX Constraints

V1 must stay simple enough for a non-technical manager or director.

Do not require:

- API keys exposed to users
- Service account setup for non-technical users
- SQL
- Dashboard configuration
- Dashboard editing
- Slide designing
- Workflow building
- Training

If users need documentation to complete the basic flow, the product is too complicated.

## V1 Architecture

Keep the architecture lightweight and implementation-ready.

### Frontend: Next.js

Responsibilities:

- Authentication entry points
- Tableau workbook and view selection
- Generate action
- Async job status
- Presentation URL display

No reporting logic or Tableau processing should run in the browser.

### Backend API: FastAPI

Responsibilities:

- Tableau OAuth flow and token refresh
- Google OAuth flow and token refresh
- Workbook and view discovery
- Generation job creation
- Deck generation orchestration

Initial API surface:

- `/auth/tableau`
- `/auth/google`
- `/workbooks`
- `/views`
- `/generate`
- `/jobs/{job_id}`

### Data Store: Postgres

Store only what V1 needs:

- Users
- Connected accounts
- Selected views
- Generation jobs
- Generated presentation history

### Tableau Integration

Responsibilities:

- Refresh Tableau OAuth tokens
- List workbooks
- List views
- Export selected views as rendered images

V1 consumes rendered Tableau views, not raw data.

### Google Slides Integration

Responsibilities:

- Refresh Google OAuth tokens
- Create a new Google Slides presentation
- Add one slide per selected Tableau view
- Insert rendered Tableau images
- Return the presentation URL

### Async Generation Jobs

Deck generation should run asynchronously:

1. Create generation job.
2. Export selected Tableau views.
3. Create Google Slides deck.
4. Insert each rendered view as a slide.
5. Mark job complete with the presentation URL.

## Technical Strategy

### Generate Images, Not Charts

Do not rebuild Tableau charts, translate Tableau visualizations, or recreate chart logic in code.

Request rendered chart images from Tableau and insert them into Google Slides.

This keeps V1 fast, reliable, and visually consistent with the source dashboard.

## Non-Goals

V1 should not support:

- PowerPoint
- Power BI
- Looker
- Superset
- AI-generated commentary
- Dashboard creation
- Template designers
- Live embedded charts
- Board reporting workflows
- Complex workflow builders

## Future Enhancements

These may matter after Phase 0 validates repeat usage:

- Using existing Google Slides templates
- Refreshing existing decks
- Placeholder binding
- Scheduled updates
- AI speaker notes
- Additional BI sources
- PowerPoint or PDF export

## Success Criteria

A director can:

1. Connect Tableau.
2. Connect Google.
3. Select Tableau views.
4. Click **Generate**.
5. Use the resulting deck in a real meeting.

The first milestone succeeds when users come back for the next reporting cycle because Briefly saved meaningful time.

## Running the Phase 0 Scaffold

The repository now contains a minimal monorepo scaffold:

- `frontend/`: Next.js + TypeScript app for the Connect -> Select -> Generate flow
- `backend/`: FastAPI app with mocked connections, Tableau views, and deck generation jobs

### Backend

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000` by default.

Useful endpoints:

- `GET /health`
- `GET /api/connections`
- `POST /api/connections/tableau/mock-connect`
- `POST /api/connections/google/mock-connect`
- `GET /api/tableau/views`
- `POST /api/decks/generate`
- `GET /api/jobs/{job_id}`

### Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` by default and calls the backend at `http://localhost:8000`. To use a different backend URL, set `NEXT_PUBLIC_API_BASE_URL`.

## Current Mocked Behavior

The scaffold intentionally uses in-memory mock data:

- Tableau and Google connections are mocked button clicks.
- Tableau workbooks and views are static sample records.
- Deck generation completes immediately.
- The generated Google Slides URL is a placeholder.
- Jobs are stored in memory and reset when the backend restarts.

## Intentionally Not Implemented Yet

Phase 0 does not include:

- Real Tableau OAuth
- Real Google OAuth
- Production authentication
- External Tableau API calls
- External Google Slides API calls
- Database persistence or migrations
- Template mapping
- Existing deck refresh
- Scheduling
- AI commentary
- Slide designer or dashboard editor

---

# Phase 0 Vertical Slice Implementation

The current implementation replaces mock deck generation with the first end-to-end Tableau-to-Google-Slides vertical slice while keeping the product workflow intentionally small:

1. Connect Tableau.
2. Connect Google Slides.
3. Select Tableau views.
4. Generate a deck.

Briefly exports rendered Tableau visualization images and inserts them into Google Slides. It does not rebuild charts or extract raw data.

## Current Capabilities

- FastAPI backend.
- Next.js frontend.
- Tableau OAuth entry point and callback.
- Google OAuth entry point and callback.
- Server-side development token storage.
- Tableau workbook and view discovery through Tableau REST API.
- Tableau rendered view image retrieval.
- Google Slides presentation creation.
- One generated slide per selected Tableau view plus a title slide.
- Human-readable errors for common OAuth and generation failures.

## Current Limitations

This is development-grade only.

- Tokens are stored in a local JSON file, not a production secret store.
- There are no user accounts, sessions, teams, or multi-tenancy.
- Generation is synchronous and runs in the request path.
- Temporary Tableau images are stored in backend memory so Google Slides can fetch them during deck creation.
- The backend must be reachable by Google while generating a deck. For local testing, expose the backend with a tunnel and set `APP_BASE_URL` to the public HTTPS URL.
- Tableau OAuth endpoints vary by connected app / authorization server setup. Configure the Tableau authorization and token URLs for your Tableau Cloud OAuth setup.
- No template mapping, refresh, scheduling, AI commentary, editing, PowerPoint export, or additional BI platforms are included.

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs on `http://localhost:8000` by default.

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:3000` by default.

## Required Environment Variables

Create a backend `.env` file or export these values before starting FastAPI.

| Variable | Required | Description |
| --- | --- | --- |
| `APP_BASE_URL` | Yes | Public backend URL used for OAuth callbacks and temporary image URLs. Use `http://localhost:8000` only when the provider can call localhost; otherwise use a tunnel URL. |
| `FRONTEND_BASE_URL` | Yes | Frontend URL for CORS and post-OAuth redirects. Defaults to `http://localhost:3000`. |
| `TOKEN_STORE_PATH` | No | Local development token file path. Defaults to `.briefly_tokens.json`. |
| `TABLEAU_SERVER_URL` | Yes | Tableau Cloud site server URL, for example `https://prod-useast-a.online.tableau.com`. |
| `TABLEAU_SITE_CONTENT_URL` | Yes | Tableau site content URL. Use an empty string for the default site. |
| `TABLEAU_API_VERSION` | No | Tableau REST API version. Defaults to `3.25`. |
| `TABLEAU_CLIENT_ID` | Yes | Tableau OAuth client id. |
| `TABLEAU_CLIENT_SECRET` | Yes | Tableau OAuth client secret. |
| `TABLEAU_AUTHORIZATION_URL` | Yes | Tableau OAuth authorization endpoint for your connected app / authorization server. |
| `TABLEAU_TOKEN_URL` | Yes | Tableau OAuth token endpoint for your connected app / authorization server. |
| `TABLEAU_SCOPES` | Yes | Space-delimited Tableau scopes. Defaults to `tableau:content:read tableau:views:download`. |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth web client id. |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth web client secret. |
| `GOOGLE_SCOPES` | No | Google scopes. Defaults to `https://www.googleapis.com/auth/presentations`. |

Frontend environment:

| Variable | Required | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | No | Backend URL used by the browser. Defaults to `http://localhost:8000`. |

## Tableau OAuth Setup

1. Create or configure a Tableau Cloud OAuth-capable connected app / authorization server for your site.
2. Add this redirect URI:

   ```text
   {APP_BASE_URL}/auth/tableau/callback
   ```

3. Grant the minimum scopes needed to list content and download rendered view images:

   ```text
   tableau:content:read tableau:views:download
   ```

4. Set the Tableau environment variables listed above.
5. Start the backend and click **Connect Tableau** in the UI.

After OAuth completes, Briefly stores the returned token data in the local development token file. Tokens are never sent to the frontend.

## Google OAuth Setup

1. In Google Cloud Console, create an OAuth client of type **Web application**.
2. Enable the Google Slides API.
3. Add this redirect URI:

   ```text
   {APP_BASE_URL}/auth/google/callback
   ```

4. Use the minimal Slides scope:

   ```text
   https://www.googleapis.com/auth/presentations
   ```

5. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
6. Start the backend and click **Connect Google Slides** in the UI.

## Local End-to-End Development Notes

Google Slides `createImage` requests fetch images by URL. Briefly temporarily serves Tableau-rendered images from the backend at `/api/images/{image_id}` during deck creation.

For a real local E2E test:

1. Run FastAPI locally.
2. Expose FastAPI with a public HTTPS tunnel.
3. Set `APP_BASE_URL` and `NEXT_PUBLIC_API_BASE_URL` to that public backend URL.
4. Configure Tableau and Google OAuth redirect URIs with the same public backend URL.
5. Connect Tableau.
6. Connect Google Slides.
7. Select Tableau views.
8. Generate the deck and open the returned Google Slides URL.

## Validation

Unit tests cover:

- Health endpoint.
- Tableau service initialization.
- Google Slides service initialization.
- Deck generation orchestration.

Run backend tests:

```bash
cd backend
pytest
```

Run frontend type checks:

```bash
cd frontend
npm run typecheck
```
