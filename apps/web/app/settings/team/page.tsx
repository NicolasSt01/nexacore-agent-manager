"use client";

import { FormEvent, useEffect, useState } from "react";
import { LoaderCircle, ShieldCheck, UserPlus } from "lucide-react";
import { Alert, PageHead } from "@/components/ui";
import { useToast } from "@/components/toast";
import { api, messageFrom } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { isSuperadmin, ROLE_SELLER, ROLE_SUPERADMIN } from "@/lib/roles";
import type { AgencyUser, User } from "@/types";

export default function TeamPage() {
  const t = useT();
  const toast = useToast();
  const [me, setMe] = useState<User | null>(null);
  const [members, setMembers] = useState<AgencyUser[] | null>(null);
  const [role, setRole] = useState<string>(ROLE_SELLER);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<User>("/auth/me")
      .then(async (user) => {
        setMe(user);
        // Sellers get a clear message instead of a failed request; the endpoint
        // rejects them regardless of what the UI does.
        if (isSuperadmin(user)) setMembers(await api<AgencyUser[]>("/agency/users"));
      })
      .catch((err) => toast.error(messageFrom(err)));
  }, [toast]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    try {
      await api<AgencyUser>("/agency/users", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          email: data.get("email"),
          password: data.get("password"),
          role: data.get("role"),
        }),
      });
      toast.success(t("finance.team.created"));
      form.reset();
      setRole(ROLE_SELLER);
      setMembers(await api<AgencyUser[]>("/agency/users"));
    } catch (err) {
      toast.error(messageFrom(err));
    } finally {
      setBusy(false);
    }
  }

  if (!me) return <div className="page-loading"><LoaderCircle className="spin" /> {t("finance.team.loading")}</div>;
  if (!isSuperadmin(me)) {
    return <div className="page">
      <PageHead eyebrow={t("finance.team.eyebrow")} title={t("finance.team.title")} description={t("finance.team.description")} />
      <Alert type="info">{t("finance.team.restricted")}</Alert>
    </div>;
  }

  return (
    <div className="page">
      <PageHead eyebrow={t("finance.team.eyebrow")} title={t("finance.team.title")} description={t("finance.team.description")} />

      <form className="page-form" onSubmit={createUser}>
        <section className="form-section">
          <div className="section-copy">
            <h2>{t("finance.team.addHeading")}</h2>
            <p>{t("finance.team.addCopy")}</p>
          </div>
          <div className="form-fields">
            <div className="form-grid">
              <label>{t("finance.team.name")}<input name="name" required placeholder={t("finance.team.namePlaceholder")} /></label>
              <label>{t("finance.team.email")}<input name="email" type="email" required placeholder={t("finance.team.emailPlaceholder")} /></label>
            </div>
            <div className="form-grid">
              <label>{t("finance.team.password")}<input name="password" type="password" required minLength={8} autoComplete="new-password" placeholder={t("finance.team.passwordPlaceholder")} /></label>
              <label>{t("finance.team.role")}
                <select name="role" value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value={ROLE_SELLER}>{t("finance.team.roleSeller")}</option>
                  <option value={ROLE_SUPERADMIN}>{t("finance.team.roleSuperadmin")}</option>
                </select>
              </label>
            </div>
            <div className="security-note">
              <ShieldCheck size={20} />
              <span>{role === ROLE_SUPERADMIN ? t("finance.team.roleSuperadminHint") : t("finance.team.roleSellerHint")}</span>
            </div>
            <button className="button primary align-start" disabled={busy}>
              {busy ? <LoaderCircle size={17} className="spin" /> : <UserPlus size={17} />} {t("finance.team.submit")}
            </button>
          </div>
        </section>
      </form>

      <section className="section-block">
        <div className="section-heading"><div><h2>{t("finance.team.membersHeading")}</h2></div></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("finance.team.colName")}</th>
                <th>{t("finance.team.colEmail")}</th>
                <th>{t("finance.team.colRole")}</th>
                <th>{t("finance.team.colCreated")}</th>
              </tr>
            </thead>
            <tbody>
              {(members ?? []).map((member) => (
                <tr key={member.id}>
                  <td><strong>{member.name}</strong></td>
                  <td>{member.email}</td>
                  <td>{isSuperadmin(member) ? t("finance.team.roleSuperadmin") : t("finance.team.roleSeller")}</td>
                  <td>{new Date(member.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
