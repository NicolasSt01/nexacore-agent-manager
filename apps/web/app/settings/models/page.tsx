"use client";

import { FormEvent, useEffect, useState } from "react";
import { Activity, CircleAlert, DownloadCloud, LoaderCircle, Plus, RefreshCw, Save, TriangleAlert } from "lucide-react";
import { Alert, PageHead } from "@/components/ui";
import { useToast } from "@/components/toast";
import { api, messageFrom } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatTokens, isSuperadmin } from "@/lib/roles";
import { PROVIDERS } from "@/lib/providers";
import type { AgencySettings, ModelPrice, ModelSyncReport, PoolStatus, User } from "@/types";

/** USD per 1k tokens is unreadable as a plain number; show per-million too. */
function price(value: number): string {
  return `$${value.toFixed(5)} · $${(value * 1000).toFixed(2)}/1M`;
}

export default function ModelSettingsPage() {
  const t = useT();
  const toast = useToast();
  const [me, setMe] = useState<User | null>(null);
  const [prices, setPrices] = useState<ModelPrice[]>([]);
  const [report, setReport] = useState<ModelSyncReport | null>(null);
  const [pools, setPools] = useState<PoolStatus[]>([]);
  const [settings, setSettings] = useState<AgencySettings | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => Promise.all([
    api<ModelPrice[]>("/admin/model-prices").then(setPrices),
    api<PoolStatus[]>("/admin/pool").then(setPools),
    api<AgencySettings>("/admin/settings").then(setSettings),
  ]);

  useEffect(() => {
    api<User>("/auth/me")
      .then(async (user) => { setMe(user); if (isSuperadmin(user)) await load(); })
      .catch((err) => toast.error(messageFrom(err)));
  }, [toast]);

  async function addPrice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    try {
      await api("/admin/model-prices", {
        method: "POST",
        body: JSON.stringify({
          provider: data.get("provider"),
          model: data.get("model"),
          input_price_per_1k_usd: Number(data.get("input_price_per_1k_usd")),
          output_price_per_1k_usd: Number(data.get("output_price_per_1k_usd")),
          note: data.get("note"),
        }),
      });
      toast.success(t("finance.prices.added"));
      form.reset();
      await load();
    } catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  async function seed() {
    setBusy(true);
    try {
      const result = await api<{ added: number }>("/admin/model-prices/seed", { method: "POST" });
      toast.success(t("finance.prices.seeded", { count: result.added }));
      await load();
    } catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  async function refreshPool() {
    setBusy(true);
    try { setPools(await api<PoolStatus[]>("/admin/pool/refresh", { method: "POST" })); }
    catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  async function saveThresholds(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      setSettings(await api<AgencySettings>("/admin/settings", {
        method: "PATCH",
        body: JSON.stringify({
          pool_alert_percent: Number(data.get("pool_alert_percent")),
          pool_degrade_percent: Number(data.get("pool_degrade_percent")),
          pool_block_percent: Number(data.get("pool_block_percent")),
          pool_fallback_model: data.get("pool_fallback_model"),
        }),
      }));
      toast.success(t("finance.email.saved"));
      setPools(await api<PoolStatus[]>("/admin/pool"));
    } catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  async function runSync() {
    setBusy(true);
    try { setReport(await api<ModelSyncReport>("/admin/model-sync/run", { method: "POST" })); }
    catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  if (!me) return <div className="page-loading"><LoaderCircle className="spin" /> {t("common.loading")}</div>;
  if (!isSuperadmin(me)) {
    return <div className="page">
      <PageHead eyebrow={t("nav.settings")} title={t("finance.prices.heading")} description={t("finance.prices.copy")} />
      <Alert type="info">{t("finance.team.restricted")}</Alert>
    </div>;
  }

  // Only the newest version per model is in force; the rest is history.
  const seen = new Set<string>();
  const rows = prices.map((row) => {
    const key = `${row.provider}/${row.model}`;
    const current = !seen.has(key);
    seen.add(key);
    return { row, current };
  });

  return (
    <div className="page">
      <PageHead eyebrow={t("nav.settings")} title={t("finance.prices.heading")} description={t("finance.prices.copy")} />

      <section className="section-block">
        <div className="section-heading">
          <div><h2><Activity size={17} /> {t("finance.pool.heading")}</h2><p>{t("finance.pool.copy")}</p></div>
          <button className="button secondary" onClick={refreshPool} disabled={busy}>
            <RefreshCw size={16} /> {t("finance.pool.refresh")}
          </button>
        </div>
        {pools.map((pool) => (
          <div key={pool.provider} className={`sync-block ${pool.blocked ? "danger" : pool.degraded ? "warning" : ""}`}>
            <h3>
              {pool.blocked ? <TriangleAlert size={17} /> : pool.degraded ? <CircleAlert size={17} /> : null}
              {pool.label} — {pool.configured ? `${pool.percent.toFixed(0)}%` : t("finance.pool.notConfigured")}
            </h3>
            {pool.configured && (
              <>
                <p>{pool.blocked ? t("finance.pool.blocked") : pool.degraded ? t("finance.pool.degraded") : t("finance.pool.ok")}</p>
                <div className="usage-track"><div className="usage-fill" style={{ width: `${Math.min(100, pool.percent)}%` }} /></div>
                <ul>
                  {pool.windows.map((w) => (
                    <li key={w.name}>
                      <strong>{w.name}</strong>: {w.percent.toFixed(1)}% · {t("finance.pool.colResets")} {w.resets_at ? new Date(w.resets_at).toLocaleString() : "—"}
                    </li>
                  ))}
                </ul>
                <small className="muted-block">
                  {pool.tokens_per_percent
                    ? t("finance.pool.capacity", { tokens: formatTokens(pool.tokens_per_percent) })
                    : t("finance.pool.capacityUnknown")}
                </small>
                {pool.captured_at && (
                  <small className="muted-block">{t("finance.pool.lastRead", { when: new Date(pool.captured_at).toLocaleString() })}</small>
                )}
              </>
            )}
          </div>
        ))}
      </section>

      {settings && (
        <form className="page-form" onSubmit={saveThresholds}>
          <section className="form-section">
            <div className="section-copy"><h2>{t("finance.pool.thresholdsHeading")}</h2><p>{t("finance.pool.thresholdsCopy")}</p></div>
            <div className="form-fields">
              <div className="form-grid">
                <label>{t("finance.pool.alertPercent")}<input name="pool_alert_percent" type="number" min={1} max={100} defaultValue={settings.pool_alert_percent} /></label>
                <label>{t("finance.pool.degradePercent")}<input name="pool_degrade_percent" type="number" min={1} max={100} defaultValue={settings.pool_degrade_percent} /></label>
              </div>
              <div className="form-grid">
                <label>{t("finance.pool.blockPercent")}<input name="pool_block_percent" type="number" min={1} max={100} defaultValue={settings.pool_block_percent} /></label>
                <label>{t("finance.pool.fallbackModel")}<input name="pool_fallback_model" defaultValue={settings.pool_fallback_model} placeholder="ox-alpha-free" /><small>{t("finance.pool.fallbackModelHint")}</small></label>
              </div>
              <button className="button primary align-start" disabled={busy}>
                {busy ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />} {t("common.saveChanges")}
              </button>
            </div>
          </section>
        </form>
      )}

      <section className="section-block">
        <div className="section-heading">
          <div><h2>{t("finance.sync.heading")}</h2><p>{t("finance.sync.copy")}</p></div>
          <button className="button secondary" onClick={runSync} disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}
            {busy ? t("finance.sync.running") : t("finance.sync.run")}
          </button>
        </div>

        {report && !report.has_changes && <Alert type="success">{t("finance.sync.noChanges")}</Alert>}
        {report?.agents_at_risk.length ? (
          <div className="sync-block danger">
            <h3><TriangleAlert size={17} /> {t("finance.sync.atRisk")}</h3>
            <p>{t("finance.sync.atRiskCopy")}</p>
            <ul>
              {report.agents_at_risk.map((row) => (
                <li key={`${row.client_name}-${row.agent_name}`}>
                  <strong>{row.client_name}</strong> — {row.agent_name} · <code>{row.model}</code>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {report?.retired.length ? (
          <div className="sync-block warning">
            <h3><CircleAlert size={17} /> {t("finance.sync.retired")}</h3>
            <ul>{report.retired.map((row) => <li key={`${row.provider}-${row.model}`}>{row.provider}: <code>{row.model}</code></li>)}</ul>
          </div>
        ) : null}
        {report?.new_models.length ? (
          <div className="sync-block">
            <h3>{t("finance.sync.newModels")}</h3>
            <ul>{report.new_models.map((row) => <li key={`${row.provider}-${row.model}`}>{row.provider}: <code>{row.model}</code></li>)}</ul>
          </div>
        ) : null}
        {report?.unreachable.length ? (
          <div className="sync-block warning">
            <h3>{t("finance.sync.unreachable")}</h3>
            <ul>{report.unreachable.map((row) => <li key={row.provider}>{row.provider} — <code>{row.base_url}</code></li>)}</ul>
          </div>
        ) : null}
        {report && <small className="muted-block">{t("finance.sync.checked", { list: report.checked_providers.join(", ") || "—" })}</small>}
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div><h2>{t("finance.prices.heading")}</h2></div>
          <button className="button secondary" onClick={seed} disabled={busy}>
            <DownloadCloud size={16} /> {t("finance.prices.seed")}
          </button>
        </div>

        {rows.length === 0 ? (
          <Alert type="info">{t("finance.prices.empty")}</Alert>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("finance.prices.colModel")}</th>
                  <th>{t("finance.prices.colInput")}</th>
                  <th>{t("finance.prices.colOutput")}</th>
                  <th>{t("finance.prices.colFrom")}</th>
                  <th>{t("finance.prices.colOrigin")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ row, current }) => (
                  <tr key={row.id} className={current ? "" : "row-muted"}>
                    <td>
                      <strong>{row.model}</strong>
                      <small className="muted-block">{row.provider}</small>
                    </td>
                    <td>{price(row.input_price_per_1k_usd)}</td>
                    <td>{price(row.output_price_per_1k_usd)}</td>
                    <td>
                      {new Date(row.effective_from).toLocaleDateString()}
                      <small className="muted-block">
                        {current ? t("finance.prices.current") : t("finance.prices.historical")}
                      </small>
                    </td>
                    <td>{row.origin}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <form className="page-form" onSubmit={addPrice}>
        <section className="form-section">
          <div className="section-copy"><h2>{t("finance.prices.addHeading")}</h2><p>{t("finance.prices.copy")}</p></div>
          <div className="form-fields">
            <div className="form-grid">
              <label>
                {t("finance.prices.provider")}
                <select name="provider" required defaultValue={PROVIDERS[0].id}>
                  {PROVIDERS.map((provider) => <option key={provider.id} value={provider.id}>{provider.label}</option>)}
                </select>
              </label>
              <label>{t("finance.prices.model")}<input name="model" required placeholder="gpt-4.1-mini" /></label>
            </div>
            <div className="form-grid">
              <label>{t("finance.prices.inputPrice")}<input name="input_price_per_1k_usd" type="number" step="0.00000001" min={0} required /></label>
              <label>{t("finance.prices.outputPrice")}<input name="output_price_per_1k_usd" type="number" step="0.00000001" min={0} required /></label>
            </div>
            <label>{t("finance.prices.note")}<input name="note" maxLength={500} /></label>
            <button className="button primary align-start" disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />} {t("finance.prices.submit")}
            </button>
          </div>
        </section>
      </form>
    </div>
  );
}
