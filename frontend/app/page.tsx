"use client";

import { useEffect, useMemo, useState } from "react";

type ConnectionStatus = "connected" | "disconnected";
type Provider = "tableau" | "google";

type ConnectedAccount = {
  provider: Provider;
  status: ConnectionStatus;
  display_name: string | null;
  connected_at: string | null;
};

type ConnectionsResponse = {
  tableau: ConnectedAccount;
  google: ConnectedAccount;
};

type TableauView = {
  id: string;
  workbook_id: string;
  name: string;
  description: string;
};

type TableauWorkbook = {
  id: string;
  name: string;
  views: TableauView[];
};

type GeneratedDeck = {
  id: string;
  title: string;
  url: string;
  slide_count: number;
};

type DeckGenerationJob = {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  requested_view_ids: string[];
  message: string;
  generated_deck: GeneratedDeck | null;
  created_at: string;
  completed_at: string | null;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const initialConnections: ConnectionsResponse = {
  tableau: {
    provider: "tableau",
    status: "disconnected",
    display_name: null,
    connected_at: null,
  },
  google: {
    provider: "google",
    status: "disconnected",
    display_name: null,
    connected_at: null,
  },
};

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let message = errorBody || `Request failed with status ${response.status}`;
    try {
      const parsed = JSON.parse(errorBody) as { detail?: string };
      message = parsed.detail || message;
    } catch {
      // Keep the plain response body when the backend did not return JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export default function Home() {
  const [connections, setConnections] = useState<ConnectionsResponse>(initialConnections);
  const [workbooks, setWorkbooks] = useState<TableauWorkbook[]>([]);
  const [selectedViewIds, setSelectedViewIds] = useState<string[]>([]);
  const [job, setJob] = useState<DeckGenerationJob | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedCount = selectedViewIds.length;
  const canGenerate =
    connections.tableau.status === "connected" &&
    connections.google.status === "connected" &&
    selectedCount > 0 &&
    !isGenerating;

  const generationSummary = useMemo(() => {
    if (!job) {
      return "No deck generated yet.";
    }

    if (job.status === "completed" && job.generated_deck) {
      return `${job.generated_deck.slide_count} slide deck generated from ${job.requested_view_ids.length} Tableau view${job.requested_view_ids.length === 1 ? "" : "s"}.`;
    }

    return job.message;
  }, [job]);

  useEffect(() => {
    async function loadConnections() {
      try {
        const connectionData = await apiRequest<ConnectionsResponse>("/api/connections");
        setConnections(connectionData);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Could not load Briefly connection state.");
      }
    }

    void loadConnections();
  }, []);

  function connect(provider: Provider) {
    setErrorMessage(null);
    window.location.href = `${apiBaseUrl}/auth/${provider}`;
  }

  useEffect(() => {
    async function loadTableauViews() {
      if (connections.tableau.status !== "connected") {
        setWorkbooks([]);
        setSelectedViewIds([]);
        return;
      }

      try {
        const workbookData = await apiRequest<TableauWorkbook[]>("/api/tableau/views");
        setWorkbooks(workbookData);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Could not load Tableau views.");
      }
    }

    void loadTableauViews();
  }, [connections.tableau.status]);

  function toggleView(viewId: string) {
    setSelectedViewIds((current) =>
      current.includes(viewId) ? current.filter((id) => id !== viewId) : [...current, viewId],
    );
  }

  async function generateDeck() {
    setIsGenerating(true);
    setErrorMessage(null);
    setJob(null);

    try {
      const generationJob = await apiRequest<DeckGenerationJob>("/api/decks/generate", {
        method: "POST",
        body: JSON.stringify({ view_ids: selectedViewIds }),
      });
      setJob(generationJob);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not generate a deck.");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Phase 0 MVP</p>
        <h1>Generate an executive-ready deck from Tableau views.</h1>
        <p>
          Connect Tableau, connect Google Slides, select the views you need, and let Briefly create the first draft of your meeting deck.
        </p>
      </section>

      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}

      <section className="steps-grid" aria-label="Briefly setup steps">
        <article className="card step-card">
          <div className="step-label">Steps 1 & 2</div>
          <h2>Connect</h2>
          <p>Connect Tableau and Google Slides with OAuth. Tokens stay on the server.</p>
          <div className="connection-list">
            <ConnectionRow
              account={connections.tableau}
              label="Tableau"
              onConnect={() => connect("tableau")}
            />
            <ConnectionRow
              account={connections.google}
              label="Google Slides"
              onConnect={() => connect("google")}
            />
          </div>
        </article>

        <article className="card step-card select-card">
          <div className="step-label">Step 3</div>
          <h2>Select</h2>
          <p>Choose the Tableau views that should become slides in the generated deck.</p>
          <div className="workbook-list">
            {connections.tableau.status !== "connected" ? (
              <p className="empty-state">Connect Tableau to load workbooks and views.</p>
            ) : workbooks.length === 0 ? (
              <p className="empty-state">No Tableau views found.</p>
            ) : null}
            {workbooks.map((workbook) => (
              <fieldset className="workbook" key={workbook.id}>
                <legend>{workbook.name}</legend>
                {workbook.views.map((view) => (
                  <label className="view-option" key={view.id}>
                    <input
                      checked={selectedViewIds.includes(view.id)}
                      onChange={() => toggleView(view.id)}
                      type="checkbox"
                    />
                    <span>
                      <strong>{view.name}</strong>
                      <small>{view.description}</small>
                    </span>
                  </label>
                ))}
              </fieldset>
            ))}
          </div>
        </article>

        <article className="card step-card">
          <div className="step-label">Step 4</div>
          <h2>Generate</h2>
          <p>Create a brand-new Google Slides deck with one selected Tableau view per slide.</p>
          <button className="primary-button" disabled={!canGenerate} onClick={() => void generateDeck()}>
            {isGenerating ? "Generating deck..." : "Generate Deck"}
          </button>
          <div className="status-box">
            <span className="status-label">Generation status</span>
            <strong>{job?.status ?? "Not started"}</strong>
            <p>{generationSummary}</p>
            {job?.generated_deck ? (
              <a href={job.generated_deck.url} rel="noreferrer" target="_blank">
                Open generated Google Slides deck
              </a>
            ) : (
              <span className="placeholder-url">Generated Google Slides URL will appear here.</span>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

function ConnectionRow({
  account,
  label,
  onConnect,
}: {
  account: ConnectedAccount;
  label: string;
  onConnect: () => void;
}) {
  const isConnected = account.status === "connected";

  return (
    <div className="connection-row">
      <div>
        <strong>{label}</strong>
        <span className={isConnected ? "connected" : "disconnected"}>
          {isConnected ? account.display_name ?? "Connected" : "Not connected"}
        </span>
      </div>
      <button className="secondary-button" onClick={onConnect} type="button">
        {isConnected ? "Reconnect" : `Connect ${label}`}
      </button>
    </div>
  );
}
