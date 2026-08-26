"use client";

import { useEffect, useState } from "react";
import { Building2, Coins, Info, LoaderCircle, Wallet } from "lucide-react";
import { Alert, PageHead } from "@/components/ui";
import { useToast } from "@/components/toast";
import { api, messageFrom } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatMxn, formatTokens, isSuperadmin } from "@/lib/roles";
import type { FinanceDashboard, User } from "@/types";

export default function FinancePage() {
  const t = useT();
  const toast = useToast();
  const [me, setMe] = useState<User | null>(null);
  const [data, setData] = useState<FinanceDashboard | null>(null);

  useEffect(() => {
    api<User>("/auth/me")
      .then(async (user) => {
        setMe(user);
        if (isSuperadmin(user)) setData(await api<FinanceDashboard>("/dashboard/finance"));
      })
      .catch((err) => toast.error(messageFrom(err)));
  }, [toast]);

  if (!me) return <div className="page-loading"><LoaderCircle className="spin" /> {t("finance.dashboard.loading")}</div>;
  if (!isSuperadmin(me)) {
    return <div className="page">
      <PageHead eyebrow={t("finance.dashboard.eyebrow")} title={t("finance.dashboard.title")} description={t("finance.dashboard.description")} />
      <Alert type="info">{t("finance.dashboard.restricted")}</Alert>
    </div>;
  }
  if (!data) return <div className="page-loading"><LoaderCircle className="spin" /> {t("finance.dashboard.loading")}</div>;

  return (
    <div className="page">
      <PageHead eyebrow={t("finance.dashboard.eyebrow")} title={t("finance.dashboard.title")} description={t("finance.dashboard.description")} />

      {/* Stated plainly: accounting owns invoicing, so nothing here is a
          collected amount and the UI must not imply otherwise. */}
      <div className="security-note"><Info size={20} /><span>{t("finance.dashboard.projectionNotice")}</span></div>

      <section className="metrics-grid">
        <article className="metric-card">
          <span className="metric-icon blue"><Building2 size={20} /></span>
          <div><small>{t("finance.dashboard.totalClients")}</small><strong>{data.total_clients}</strong></div>
        </article>
        <article className="metric-card">
          <span className="metric-icon green"><Wallet size={20} /></span>
          <div><small>{t("finance.dashboard.projectedRevenue")}</small><strong>{formatMxn(data.total_monthly_revenue_mxn)}</strong></div>
        </article>
        <article className="metric-card">
          <span className="metric-icon amber"><Coins size={20} /></span>
          <div><small>{t("finance.dashboard.tokensConsumed")}</small><strong>{formatTokens(data.total_tokens_consumed)}</strong></div>
        </article>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <h2>{t("finance.dashboard.perSellerHeading")}</h2>
            <p>{t("finance.dashboard.perSellerCopy")}</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("finance.dashboard.colSeller")}</th>
                <th>{t("finance.dashboard.colClients")}</th>
                <th>{t("finance.dashboard.colRevenue")}</th>
                <th>{t("finance.dashboard.colTokens")}</th>
              </tr>
            </thead>
            <tbody>
              {data.workers_metrics.length === 0 && (
                <tr><td colSpan={4}>{t("finance.dashboard.noSellers")}</td></tr>
              )}
              {data.workers_metrics.map((seller) => (
                <tr key={seller.worker_id}>
                  <td>
                    <strong>{seller.worker_name}</strong>
                    <small className="muted-block">{seller.worker_email}</small>
                  </td>
                  <td>{seller.clients_count}</td>
                  <td>{formatMxn(seller.monthly_revenue_mxn)}</td>
                  <td>{formatTokens(seller.tokens_consumed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
