"use client";

import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, AtSign, Bot, CheckCircle2, CircleAlert, ClipboardCopy, Facebook, Instagram, KeyRound, LoaderCircle, Plug, Power, RefreshCw, ShieldCheck, Webhook } from "lucide-react";
import { Alert } from "@/components/ui";
import { api, ApiError, messageFrom } from "@/lib/api";
import { useT, type I18nKey } from "@/lib/i18n";
import type { Client, MetaChannel, MetaPlatform } from "@/types";

const stateKeys: Record<MetaChannel["status"], { label: I18nKey }> = {
  disconnected: { label: "channels.meta.statusDisconnected" },
  connected: { label: "channels.meta.statusConnected" },
  error: { label: "channels.meta.statusError" },
};

// Everything that differs between Messenger and Instagram, in one place: the
// flow, the API and the webhook are identical for both.
const platformConfig: Record<MetaPlatform, { icon: typeof Facebook; title: I18nKey; copy: I18nKey; accountLabel: I18nKey; accountHint: I18nKey }> = {
  messenger: {
    icon: Facebook,
    title: "channels.meta.messengerTitle",
    copy: "channels.meta.messengerCopy",
    accountLabel: "channels.meta.pageIdLabel",
    accountHint: "channels.meta.pageIdHint",
  },
  instagram: {
    icon: Instagram,
    title: "channels.meta.instagramTitle",
    copy: "channels.meta.instagramCopy",
    accountLabel: "channels.meta.igIdLabel",
    accountHint: "channels.meta.igIdHint",
  },
};

function isPlatform(value: string): value is MetaPlatform {
  return value === "messenger" || value === "instagram";
}

function CopyField({ label, value }: { label: string; value: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return <div className="wa-copy-field">
    <label>{label}<input readOnly value={value} onFocus={(event) => event.currentTarget.select()} /></label>
    <button type="button" className="button secondary" onClick={copy}><ClipboardCopy size={15} /> {copied ? t("clients.whatsappCloud.copied") : t("clients.whatsappCloud.copy")}</button>
  </div>;
}

export default function MetaChannelPage() {
  const t = useT();
  const { id, platform } = useParams<{ id: string; platform: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [channel, setChannel] = useState<MetaChannel | null>(null);
  const [agentId, setAgentId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const valid = isPlatform(platform);

  useEffect(() => {
    if (!valid) return;
    const loadChannel = api<MetaChannel>(`/meta/${platform}/channels/${id}`)
      .then((current) => {
        setChannel(current);
        setAgentId(current.agent_id);
        setAccountId(current.account_id);
      })
      .catch((err) => {
        // 404 just means the channel has not been configured yet.
        if (!(err instanceof ApiError && err.status === 404)) throw err;
        setChannel(null);
      });
    Promise.all([
      api<Client>(`/clients/${id}`).then((item) => { setClient(item); setAgentId((value) => value || item.agents[0]?.id || ""); }),
      loadChannel,
    ]).catch((err) => setError(messageFrom(err))).finally(() => setLoading(false));
  }, [id, platform, valid]);

  if (!valid) notFound();

  async function save(): Promise<MetaChannel | null> {
    if (!agentId) return null;
    const payload: Record<string, string> = { agent_id: agentId, account_id: accountId.trim() };
    if (accessToken.trim()) payload.access_token = accessToken.trim();
    if (appSecret.trim()) payload.app_secret = appSecret.trim();
    const saved = await api<MetaChannel>(`/meta/${platform}/channels/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    setChannel(saved);
    setAccessToken("");
    setAppSecret("");
    return saved;
  }

  async function saveOnly() {
    setBusy(true); setError("");
    try { await save(); } catch (err) { setError(messageFrom(err)); } finally { setBusy(false); }
  }

  async function saveAndConnect() {
    setBusy(true); setError("");
    try {
      if (await save()) setChannel(await api<MetaChannel>(`/meta/${platform}/channels/${id}/connect`, { method: "POST" }));
    } catch (err) { setError(messageFrom(err)); } finally { setBusy(false); }
  }

  async function disconnect() {
    if (!confirm(t("channels.meta.confirmDisconnect"))) return;
    setBusy(true); setError("");
    try { setChannel(await api<MetaChannel>(`/meta/${platform}/channels/${id}/disconnect`, { method: "POST" })); }
    catch (err) { setError(messageFrom(err)); } finally { setBusy(false); }
  }

  if (loading || !client) return <div className="page-loading"><LoaderCircle className="spin" /> {t("channels.meta.loading")}</div>;

  const config = platformConfig[platform as MetaPlatform];
  const Icon = config.icon;
  const state = stateKeys[channel?.status || "disconnected"];
  const canConnect = Boolean(agentId && accountId.trim() && !busy);

  return <div className="page wa-page">
    <Link href={`/clients/${client.id}`} className="back-link"><ArrowLeft size={17} /> {t("clients.whatsapp.back", { name: client.name })}</Link>
    <header className="wa-header">
      <div className="wa-mark"><Icon size={26} /></div>
      <div><span>{t("clients.whatsapp.channelOf", { name: client.name })}</span><h1>{t(config.title)}</h1><p>{t(config.copy)}</p></div>
      {channel && <div className={`wa-state ${channel.status}`}>{channel.status === "connected" ? <CheckCircle2 size={17} /> : channel.status === "error" ? <CircleAlert size={17} /> : <RefreshCw size={17} />} {t(state.label)}</div>}
    </header>
    {error && <Alert>{error}</Alert>}
    <div className="wa-layout"><main>
      <section className="wa-panel">
        <div className="wa-panel-head"><span><Bot size={19} /></span><div><h2>{t("clients.whatsapp.assignedAgent")}</h2><p>{t("clients.whatsapp.assignedAgentCopy")}</p></div></div>
        <div className="wa-agent-row"><label>{t("clients.whatsapp.agentToRespond")}<select value={agentId} onChange={(event) => setAgentId(event.target.value)} disabled={busy}><option value="">{t("clients.whatsapp.selectAgent")}</option>{client.agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}{agent.is_active ? "" : t("clients.whatsapp.inactiveSuffix")}</option>)}</select></label></div>
        {!client.agents.length && <Alert>{t("channels.meta.needsAgent")}</Alert>}
      </section>

      <section className="wa-panel">
        <div className="wa-panel-head"><span><KeyRound size={19} /></span><div><h2>{t("channels.meta.credentialsTitle")}</h2><p>{t("channels.meta.credentialsCopy")}</p></div></div>
        <div className="wa-cloud-form">
          <label>{t(config.accountLabel)}<input value={accountId} onChange={(event) => setAccountId(event.target.value)} disabled={busy} /><small>{t(config.accountHint)}</small></label>
          <label>{t("channels.meta.accessTokenLabel")}<input type="password" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} placeholder={channel?.has_access_token ? t("clients.whatsappCloud.secretSavedPlaceholder") : ""} disabled={busy} /></label>
          <label>{t("channels.meta.appSecretLabel")}<input type="password" value={appSecret} onChange={(event) => setAppSecret(event.target.value)} placeholder={channel?.has_app_secret ? t("clients.whatsappCloud.secretSavedPlaceholder") : ""} disabled={busy} /></label>
        </div>
        {channel?.status === "connected" && <div className="wa-connected"><div className="wa-phone"><AtSign size={24} /><span><small>{t("channels.meta.connectedAccount")}</small><strong>{channel.account_name || channel.account_id}</strong></span></div><div className="wa-ready"><CheckCircle2 size={18} /> {t("clients.whatsapp.readyForMessages")}</div></div>}
        {channel?.last_error && <Alert>{channel.last_error}</Alert>}
        <div className="wa-actions">
          <button className="button secondary" onClick={saveOnly} disabled={!agentId || busy}>{t("clients.whatsappCloud.save")}</button>
          <button className="button primary" onClick={saveAndConnect} disabled={!canConnect}>{busy ? <LoaderCircle className="spin" size={17} /> : <Plug size={17} />} {t("clients.whatsappCloud.connectVerify")}</button>
          {channel?.status === "connected" && <button className="button danger" onClick={disconnect} disabled={busy}><Power size={17} /> {t("clients.whatsappCloud.disconnect")}</button>}
        </div>
      </section>

      {channel && <section className="wa-panel">
        <div className="wa-panel-head"><span><Webhook size={19} /></span><div><h2>{t("clients.whatsappCloud.webhookTitle")}</h2><p>{t("channels.meta.webhookCopy")}</p></div></div>
        <CopyField label={t("clients.whatsappCloud.webhookUrlLabel")} value={channel.webhook_url} />
        <CopyField label={t("clients.whatsappCloud.verifyTokenLabel")} value={channel.webhook_verify_token} />
        <ol className="wa-webhook-steps"><li>{t("channels.meta.webhookStep1")}</li><li>{t("channels.meta.webhookStep2")}</li><li>{t("channels.meta.webhookStep3")}</li></ol>
      </section>}
    </main>
    <aside className="wa-side"><ShieldCheck size={22} /><h3>{t("clients.whatsapp.separationTitle")}</h3><p>{t("clients.whatsapp.separationCopy")}<strong>{client.name}</strong>.</p><hr /><h3>{t("clients.whatsapp.humanControlTitle")}</h3><p>{t("clients.whatsapp.humanControlCopy")}</p></aside></div>
  </div>;
}
