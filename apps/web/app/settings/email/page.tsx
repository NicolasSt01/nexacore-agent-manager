"use client";

import { FormEvent, useEffect, useState } from "react";
import { LoaderCircle, Mail, Save, Send } from "lucide-react";
import { Alert, PageHead } from "@/components/ui";
import { useToast } from "@/components/toast";
import { api, messageFrom } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { isSuperadmin } from "@/lib/roles";
import type { AgencySettings, User } from "@/types";

export default function EmailSettingsPage() {
  const t = useT();
  const toast = useToast();
  const [me, setMe] = useState<User | null>(null);
  const [settings, setSettings] = useState<AgencySettings | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<User>("/auth/me")
      .then(async (user) => {
        setMe(user);
        if (isSuperadmin(user)) setSettings(await api<AgencySettings>("/admin/settings"));
      })
      .catch((err) => toast.error(messageFrom(err)));
  }, [toast]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const payload: Record<string, unknown> = {
        emails_enabled: data.get("emails_enabled") === "on",
        smtp_host: data.get("smtp_host"),
        smtp_port: Number(data.get("smtp_port")),
        smtp_user: data.get("smtp_user"),
        smtp_use_tls: data.get("smtp_use_tls") === "on",
        smtp_from_email: data.get("smtp_from_email"),
        smtp_from_name: data.get("smtp_from_name"),
        owner_alert_email: data.get("owner_alert_email"),
        notify_seller_on_quota: data.get("notify_seller_on_quota") === "on",
        notify_client_on_quota: data.get("notify_client_on_quota") === "on",
      };
      // Blank keeps the stored password: the API never returns it, so an empty
      // field must not be read as "clear it".
      const password = String(data.get("smtp_password") || "").trim();
      if (password) payload.smtp_password = password;

      setSettings(await api<AgencySettings>("/admin/settings", { method: "PATCH", body: JSON.stringify(payload) }));
      toast.success(t("finance.email.saved"));
    } catch (err) {
      toast.error(messageFrom(err));
    } finally {
      setBusy(false);
    }
  }

  async function sendTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api("/admin/settings/test-email", { method: "POST", body: JSON.stringify({ to: data.get("to") }) });
      toast.success(t("finance.email.testSent"));
    } catch (err) {
      toast.error(messageFrom(err));
    } finally {
      setBusy(false);
    }
  }

  if (!me) return <div className="page-loading"><LoaderCircle className="spin" /> {t("common.loading")}</div>;
  if (!isSuperadmin(me)) {
    return <div className="page">
      <PageHead eyebrow={t("finance.team.eyebrow")} title={t("finance.email.heading")} description={t("finance.email.copy")} />
      <Alert type="info">{t("finance.team.restricted")}</Alert>
    </div>;
  }
  if (!settings) return <div className="page-loading"><LoaderCircle className="spin" /> {t("common.loading")}</div>;

  return (
    <div className="page narrow-page">
      <PageHead eyebrow={t("nav.settings")} title={t("finance.email.heading")} description={t("finance.email.copy")} />

      <form className="page-form" onSubmit={save}>
        <section className="form-section">
          <div className="section-copy"><h2><Mail size={17} /> SMTP</h2><p>{t("finance.email.copy")}</p></div>
          <div className="form-fields">
            <label className="switch-row">
              <span><strong>{t("finance.email.enabled")}</strong><small>{t("finance.email.enabledHint")}</small></span>
              <input name="emails_enabled" type="checkbox" defaultChecked={settings.emails_enabled} />
            </label>
            <div className="form-grid">
              <label>{t("finance.email.host")}<input name="smtp_host" defaultValue={settings.smtp_host} placeholder="smtp.example.com" /></label>
              <label>{t("finance.email.port")}<input name="smtp_port" type="number" min={1} max={65535} defaultValue={settings.smtp_port} /></label>
            </div>
            <div className="form-grid">
              <label>{t("finance.email.user")}<input name="smtp_user" defaultValue={settings.smtp_user} autoComplete="off" /></label>
              <label>
                {t("finance.email.password")}
                <input
                  name="smtp_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder={settings.has_smtp_password ? t("finance.email.passwordSaved") : ""}
                />
              </label>
            </div>
            <label className="switch-row">
              <span><strong>{t("finance.email.useTls")}</strong></span>
              <input name="smtp_use_tls" type="checkbox" defaultChecked={settings.smtp_use_tls} />
            </label>
            <div className="form-grid">
              <label>{t("finance.email.fromEmail")}<input name="smtp_from_email" type="email" defaultValue={settings.smtp_from_email} /></label>
              <label>{t("finance.email.fromName")}<input name="smtp_from_name" defaultValue={settings.smtp_from_name} placeholder="NexaCore" /></label>
            </div>
            <label>
              {t("finance.email.ownerEmail")}
              <input name="owner_alert_email" type="email" defaultValue={settings.owner_alert_email} />
              <small>{t("finance.email.ownerEmailHint")}</small>
            </label>
          </div>
        </section>

        <section className="form-section">
          <div className="section-copy"><h2>{t("finance.dashboard.eyebrow")}</h2></div>
          <div className="form-fields">
            <label className="switch-row">
              <span><strong>{t("finance.email.notifySeller")}</strong><small>{t("finance.email.notifySellerHint")}</small></span>
              <input name="notify_seller_on_quota" type="checkbox" defaultChecked={settings.notify_seller_on_quota} />
            </label>
            <label className="switch-row">
              <span><strong>{t("finance.email.notifyClient")}</strong><small>{t("finance.email.notifyClientHint")}</small></span>
              <input name="notify_client_on_quota" type="checkbox" defaultChecked={settings.notify_client_on_quota} />
            </label>
          </div>
        </section>

        <div className="form-footer">
          <button className="button primary" disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={17} /> : <Save size={17} />} {t("common.saveChanges")}
          </button>
        </div>
      </form>

      <form className="page-form" onSubmit={sendTest}>
        <section className="form-section">
          <div className="section-copy"><h2>{t("finance.email.testHeading")}</h2></div>
          <div className="form-fields">
            <label>{t("finance.email.testEmail")}<input name="to" type="email" required defaultValue={settings.owner_alert_email} /></label>
            <button className="button secondary align-start" disabled={busy}>
              <Send size={16} /> {t("finance.email.testSubmit")}
            </button>
          </div>
        </section>
      </form>
    </div>
  );
}
