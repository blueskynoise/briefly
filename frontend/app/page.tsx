"use client";

import { useEffect, useMemo, useState } from "react";

type ConnectionStatus = "connected" | "disconnected";
type Provider = "tableau" | "google";

type ConnectedAccount = { provider: Provider; status: ConnectionStatus; display_name: string | null; connected_at: string | null };
type ConnectionsResponse = { tableau: ConnectedAccount; google: ConnectedAccount };
type TableauConnection = { id: string; display_name: string; server_url: string; site_content_url: string; auth_type: "pat"; pat_name: string; created_at: string; last_validated_at: string | null; validation_status: "unvalidated" | "valid" | "invalid" };
type TableauValidationResponse = { success: boolean; message: string; server_url: string | null; site_content_url: string | null; display_name: string | null };
type TableauView = { id: string; workbook_id: string; name: string; description: string };
type TableauWorkbook = { id: string; name: string; views: TableauView[] };
type GeneratedDeck = { id: string; title: string; url: string; slide_count: number };
type DeckGenerationJob = { id: string; status: "pending" | "running" | "completed" | "failed"; requested_view_ids: string[]; message: string; generated_deck: GeneratedDeck | null; created_at: string; completed_at: string | null };

type TableauForm = { tableauUrl: string; siteContentUrl: string; displayName: string; patName: string; patSecret: string };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const initialConnections: ConnectionsResponse = { tableau: { provider: "tableau", status: "disconnected", display_name: null, connected_at: null }, google: { provider: "google", status: "disconnected", display_name: null, connected_at: null } };
const initialTableauForm: TableauForm = { tableauUrl: "", siteContentUrl: "", displayName: "", patName: "", patSecret: "" };

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try { const parsed = JSON.parse(await response.text()) as { detail?: string }; message = parsed.detail || message; } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function parseTableauUrl(value: string): { serverUrl: string; siteContentUrl: string } | null {
  const raw = value.trim();
  if (!raw) return null;
  try {
    const url = new URL(raw.includes("://") ? raw : `https://${raw}`);
    const match = `${url.pathname}/${url.hash.replace(/^#/, "")}`.match(/\/site\/([^/?#]+)/);
    return { serverUrl: url.origin, siteContentUrl: match?.[1] ?? "" };
  } catch { return null; }
}

export default function Home() {
  const [connections, setConnections] = useState<ConnectionsResponse>(initialConnections);
  const [tableauConnections, setTableauConnections] = useState<TableauConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [tableauForm, setTableauForm] = useState<TableauForm>(initialTableauForm);
  const [validation, setValidation] = useState<TableauValidationResponse | null>(null);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [isSavingConnection, setIsSavingConnection] = useState(false);
  const [workbooks, setWorkbooks] = useState<TableauWorkbook[]>([]);
  const [selectedViewIds, setSelectedViewIds] = useState<string[]>([]);
  const [job, setJob] = useState<DeckGenerationJob | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedCount = selectedViewIds.length;
  const hasTableau = tableauConnections.length > 0 || connections.tableau.status === "connected";
  const canGenerate = hasTableau && connections.google.status === "connected" && selectedCount > 0 && !isGenerating;
  const canSaveTableau = validation?.success && !isSavingConnection;
  const generationSummary = useMemo(() => !job ? "No deck generated yet." : job.status === "completed" && job.generated_deck ? `${job.generated_deck.slide_count} slide deck generated from ${job.requested_view_ids.length} Tableau view${job.requested_view_ids.length === 1 ? "" : "s"}.` : job.message, [job]);

  async function refreshTableauConnections() {
    const saved = await apiRequest<TableauConnection[]>("/api/tableau/connections");
    setTableauConnections(saved);
    setSelectedConnectionId((current) => current || saved[0]?.id || "");
  }

  useEffect(() => { void (async () => {
    try { setConnections(await apiRequest<ConnectionsResponse>("/api/connections")); await refreshTableauConnections(); }
    catch (error) { setErrorMessage(error instanceof Error ? error.message : "Could not load Briefly connection state."); }
  })(); }, []);

  function connect(provider: Provider) { setErrorMessage(null); window.location.href = `${apiBaseUrl}/auth/${provider}`; }
  function updateTableauUrl(value: string) {
    const parsed = parseTableauUrl(value);
    setTableauForm((current) => ({ ...current, tableauUrl: parsed?.serverUrl ?? value, siteContentUrl: parsed?.siteContentUrl ?? current.siteContentUrl }));
    setValidation(null);
  }
  function tableauPayload() { return { server_url: tableauForm.tableauUrl, site_content_url: tableauForm.siteContentUrl, display_name: tableauForm.displayName || "Tableau", pat_name: tableauForm.patName, pat_secret: tableauForm.patSecret }; }
  async function testTableauConnection() {
    setIsTestingConnection(true); setErrorMessage(null); setValidation(null);
    try { setValidation(await apiRequest<TableauValidationResponse>("/api/tableau/connections/validate", { method: "POST", body: JSON.stringify(tableauPayload()) })); }
    catch (error) { setErrorMessage(error instanceof Error ? error.message : "Could not validate Tableau connection."); }
    finally { setIsTestingConnection(false); }
  }
  async function saveTableauConnection() {
    setIsSavingConnection(true); setErrorMessage(null);
    try { const saved = await apiRequest<TableauConnection>("/api/tableau/connections", { method: "POST", body: JSON.stringify(tableauPayload()) }); await refreshTableauConnections(); setSelectedConnectionId(saved.id); setTableauForm(initialTableauForm); setValidation(null); }
    catch (error) { setErrorMessage(error instanceof Error ? error.message : "Could not save Tableau connection."); }
    finally { setIsSavingConnection(false); }
  }

  useEffect(() => { void (async () => {
    if (!hasTableau) { setWorkbooks([]); setSelectedViewIds([]); return; }
    try { setWorkbooks(await apiRequest<TableauWorkbook[]>("/api/tableau/views")); }
    catch { setWorkbooks([]); }
  })(); }, [hasTableau, selectedConnectionId]);

  function toggleView(viewId: string) { setSelectedViewIds((current) => current.includes(viewId) ? current.filter((id) => id !== viewId) : [...current, viewId]); }
  async function generateDeck() {
    setIsGenerating(true); setErrorMessage(null); setJob(null);
    try { setJob(await apiRequest<DeckGenerationJob>("/api/decks/generate", { method: "POST", body: JSON.stringify({ view_ids: selectedViewIds }) })); }
    catch (error) { setErrorMessage(error instanceof Error ? error.message : "Could not generate a deck."); }
    finally { setIsGenerating(false); }
  }

  return <main className="page-shell">
    <section className="hero"><p className="eyebrow">Phase 0 MVP</p><h1>Generate an executive-ready deck from Tableau views.</h1><p>Connect your tools, select the views you need, and let Briefly create the first draft of your meeting deck.</p></section>
    {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
    <section className="steps-grid" aria-label="Briefly setup steps">
      <article className="card step-card"><div className="step-label">Step 1</div><h2>Connect</h2><p>For the MVP, connect with a Tableau Personal Access Token. This avoids sharing your password and avoids waiting on admin approval. Later this can be upgraded to Tableau Connected Apps.</p>
        <div className="onboarding-panel"><strong>How to find your site content URL</strong><p>In a Tableau URL like https://example.online.tableau.com/#/site/sales/views/Dashboard, the site content URL is sales.</p><p>Create a Personal Access Token in Tableau, paste it here once, and you can revoke it anytime. Do not paste your Tableau password.</p></div>
        <div className="tableau-form">
          <label>Tableau URL or dashboard URL<input value={tableauForm.tableauUrl} onChange={(e) => updateTableauUrl(e.target.value)} placeholder="https://prod-ca-a.online.tableau.com/#/site/sales/views/..." /></label>
          <label>Site content URL<input value={tableauForm.siteContentUrl} onChange={(e) => { setTableauForm({ ...tableauForm, siteContentUrl: e.target.value }); setValidation(null); }} placeholder="sales or blank for default site" /></label>
          <label>Connection name<input value={tableauForm.displayName} onChange={(e) => setTableauForm({ ...tableauForm, displayName: e.target.value })} placeholder="Sales Tableau" /></label>
          <label>Personal Access Token name<input value={tableauForm.patName} onChange={(e) => { setTableauForm({ ...tableauForm, patName: e.target.value }); setValidation(null); }} /></label>
          <label>Personal Access Token secret<input type="password" autoComplete="off" value={tableauForm.patSecret} onChange={(e) => { setTableauForm({ ...tableauForm, patSecret: e.target.value }); setValidation(null); }} /></label>
          <button className="secondary-button" onClick={() => void testTableauConnection()} type="button">{isTestingConnection ? "Testing..." : "Test connection"}</button>
          {validation ? <div className={validation.success ? "success-box" : "error-banner"}>{validation.message}</div> : null}
          <button className="primary-button" disabled={!canSaveTableau} onClick={() => void saveTableauConnection()} type="button">{isSavingConnection ? "Saving..." : "Save connection"}</button>
        </div>
        <div className="connection-list"><strong>Saved Tableau connections</strong>{tableauConnections.length === 0 ? <p className="empty-state">No saved Tableau connections yet.</p> : tableauConnections.map((connection) => <label className="connection-row" key={connection.id}><span><strong>{connection.display_name}</strong><span className="connected">{connection.server_url}{connection.site_content_url ? ` · site ${connection.site_content_url}` : " · default site"}</span></span><input checked={selectedConnectionId === connection.id} name="tableauConnection" onChange={() => setSelectedConnectionId(connection.id)} type="radio" /></label>)}</div>
        <ConnectionRow account={connections.google} label="Google Slides" onConnect={() => connect("google")} />
      </article>
      <article className="card step-card select-card"><div className="step-label">Step 2</div><h2>Select</h2><p>Choose the Tableau views that should become slides in the generated deck.</p><div className="workbook-list">{!hasTableau ? <p className="empty-state">Connect Tableau to load workbooks and views. Mock data remains available only in dev mode.</p> : workbooks.length === 0 ? <p className="empty-state">No Tableau views found.</p> : null}{workbooks.map((workbook) => <fieldset className="workbook" key={workbook.id}><legend>{workbook.name}</legend>{workbook.views.map((view) => <label className="view-option" key={view.id}><input checked={selectedViewIds.includes(view.id)} onChange={() => toggleView(view.id)} type="checkbox" /><span><strong>{view.name}</strong><small>{view.description}</small></span></label>)}</fieldset>)}</div></article>
      <article className="card step-card"><div className="step-label">Step 3</div><h2>Generate</h2><p>Create a brand-new Google Slides deck with one selected Tableau view per slide.</p><button className="primary-button" disabled={!canGenerate} onClick={() => void generateDeck()}>{isGenerating ? "Generating deck..." : "Generate Deck"}</button><div className="status-box"><span className="status-label">Generation status</span><strong>{job?.status ?? "Not started"}</strong><p>{generationSummary}</p>{job?.generated_deck ? <a href={job.generated_deck.url} rel="noreferrer" target="_blank">Open generated Google Slides deck</a> : <span className="placeholder-url">Generated Google Slides URL will appear here.</span>}</div></article>
    </section>
  </main>;
}

function ConnectionRow({ account, label, onConnect }: { account: ConnectedAccount; label: string; onConnect: () => void }) {
  const isConnected = account.status === "connected";
  return <div className="connection-row"><div><strong>{label}</strong><span className={isConnected ? "connected" : "disconnected"}>{isConnected ? account.display_name ?? "Connected" : "Not connected"}</span></div><button className="secondary-button" onClick={onConnect} type="button">{isConnected ? "Reconnect" : `Connect ${label}`}</button></div>;
}
