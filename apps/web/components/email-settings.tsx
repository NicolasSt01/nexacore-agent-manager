"use client";

import { FormEvent, useEffect, useState } from "react";
import { LoaderCircle, Mail, Save, Send, ShieldAlert, ShieldCheck } from "lucide-react";
import { api, messageFrom } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Alert } from "@/components/ui";
import type { ClientEmailSettings } from "@/types";

/** Copy for one surface. The agency panel and the client portal word this
 *  differently ("the client" vs "you"), so the strings come from the caller's
 *  own dictionary while the form itself stays in one place. */
export type EmailLabels = {
  heading: string;
  copy: string;
  notificationLabel: string;
  notificationHint: string;
  senderHeading: string;
  senderCopy: string;
  useOwn: string;
  useOwnHint: string;
  host: string;
  port: string;
  user: string;
  password: string;
  passwordSaved: string;
  useTls: string;
  fromEmail: string;
  fromName: string;
  statusOwn: string;
  statusFallback: string;
  statusPending: string;
  statusNone: string;
  testHeading: string;
  testLabel: string;
  testSubmit: string;
  testSent: string;
  saved: string;
  save: string;
};

/** `basePath` is the client's own API prefix: /clients/{id} from the agency
 *  panel, /portal/{slug} from the portal. Both expose the same three routes. */
export function EmailSettings({ basePath, labels }: { basePath: string; labels: EmailLabels }) {
  const toast = useToast();
  const [settings, setSettings] = useState<ClientEmailSettings | null>(null);
  const [useOwn, setUseOwn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<ClientEmailSettings>(`${basePath}/email`)
      .then((row) => { setSettings(row); setUseOwn(row.smtp_enabled); })
      .catch((err) => toast.error(messageFrom(err)));
  }, [basePath, toast]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const payload: Record<string, unknown> = {
        notification_email: String(data.get("notification_email") || "") || null,
        smtp_enabled: useOwn,
        smtp_host: data.get("smtp_host") ?? "",
        smtp_port: Number(data.get("smtp_port") || 587),
        smtp_user: data.get("smtp_user") ?? "",
        smtp_use_tls: data.get("smtp_use_tls") === "on",
        smtp_from_email: String(data.get("smtp_from_email") || "") || null,
        smtp_from_name: data.get("smtp_from_name") ?? "",
      };
      // Blank keeps the stored password: the API never returns it, so an empty
      // field must not be read as "clear it".
      const password = String(data.get("smtp_password") || "").trim();
      if (password) payload.smtp_password = password;
      setSettings(await api<ClientEmailSettings>(`${basePath}/email`, { method: "PATCH", body: JSON.stringify(payload) }));
      toast.success(labels.saved);
    } catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  async function sendTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      setSettings(await api<ClientEmailSettings>(`${basePath}/email/test`, { method: "POST", body: JSON.stringify({ to: data.get("to") }) }));
      toast.success(labels.testSent);
    } catch (err) { toast.error(messageFrom(err)); } finally { setBusy(false); }
  }

  if (!settings) return <div className="page-loading"><LoaderCircle className="spin" /></div>;

  const status = settings.using_own_smtp
    ? { type: "success" as const, icon: <ShieldCheck size={15} />, text: labels.statusOwn }
    : settings.smtp_enabled
      ? { type: "info" as const, icon: <ShieldAlert size={15} />, text: labels.statusPending }
      : settings.delivery_ready
        ? { type: "info" as const, icon: <Mail size={15} />, text: labels.statusFallback }
        : { type: "error" as const, icon: <ShieldAlert size={15} />, text: labels.statusNone };

  return <>
    <form className="page-form" onSubmit={save}>
      <section className="form-section">
        <div className="section-copy"><h2><Mail size={17} /> {labels.heading}</h2><p>{labels.copy}</p></div>
        <div className="form-fields">
          <Alert type={status.type}>{status.icon} {status.text}</Alert>
          <label>
            {labels.notificationLabel}
            <input name="notification_email" type="email" defaultValue={settings.notification_email || ""} />
            <small>{labels.notificationHint}</small>
          </label>
        </div>
      </section>

      <section className="form-section">
        <div className="section-copy"><h2>{labels.senderHeading}</h2><p>{labels.senderCopy}</p></div>
        <div className="form-fields">
          <label className="switch-row">
            <span><strong>{labels.useOwn}</strong><small>{labels.useOwnHint}</small></span>
            <input type="checkbox" checked={useOwn} onChange={(event) => setUseOwn(event.target.checked)} />
          </label>
          {useOwn && <>
            <div className="form-grid">
              <label>{labels.host}<input name="smtp_host" defaultValue={settings.smtp_host} placeholder="smtp.example.com" /></label>
              <label>{labels.port}<input name="smtp_port" type="number" min={1} max={65535} defaultValue={settings.smtp_port} /></label>
            </div>
            <div className="form-grid">
              <label>{labels.user}<input name="smtp_user" defaultValue={settings.smtp_user} autoComplete="off" /></label>
              <label>
                {labels.password}
                <input name="smtp_password" type="password" autoComplete="new-password" placeholder={settings.has_smtp_password ? labels.passwordSaved : ""} />
              </label>
            </div>
            <div className="form-grid">
              <label>{labels.fromEmail}<input name="smtp_from_email" type="email" defaultValue={settings.smtp_from_email} /></label>
              <label>{labels.fromName}<input name="smtp_from_name" defaultValue={settings.smtp_from_name} /></label>
            </div>
            <label className="switch-row">
              <span><strong>{labels.useTls}</strong></span>
              <input name="smtp_use_tls" type="checkbox" defaultChecked={settings.smtp_use_tls} />
            </label>
          </>}
        </div>
      </section>

      <div className="form-footer">
        <button className="button primary" disabled={busy}>
          {busy ? <LoaderCircle className="spin" size={17} /> : <Save size={17} />} {labels.save}
        </button>
      </div>
    </form>

    <form className="page-form" onSubmit={sendTest}>
      <section className="form-section">
        <div className="section-copy"><h2>{labels.testHeading}</h2></div>
        <div className="form-fields">
          <label>{labels.testLabel}<input name="to" type="email" required defaultValue={settings.alert_email || ""} /></label>
          <button className="button secondary align-start" disabled={busy}><Send size={16} /> {labels.testSubmit}</button>
        </div>
      </section>
    </form>
  </>;
}
