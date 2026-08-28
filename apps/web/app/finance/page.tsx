"use client";

import { useEffect, useState } from "react";
import { Building2, Coins, Info, LoaderCircle, TrendingUp, TriangleAlert, Wallet } from "lucide-react";
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
          <div><small>{t("finance.dashboard.aiCost")}</small><strong>{formatMxn(data.total_ai_cost_mxn)}</strong></div>
        </article>
        <article className="metric-card">
          <span className="metric-icon violet"><TrendingUp size={20} /></span>
          <div>
            <small>{t("finance.dashboard.margin")}</small>
            <strong>{formatMxn(data.total_margin_mxn)}</strong>
            <p>{t("finance.dashboard.marginPct", { pct: data.margin_pct })}</p>
          </div>
        </article>
      </section>

      <div className="security-note"><Info size={20} /><span>{t("finance.dashboard.costNotice")}</span></div>

      {data.unpriced_usage_records > 0 && (
        <div className="sync-block warning">
          <h3><TriangleAlert size={17} /> {t("finance.dashboard.unpricedWarning", { count: data.unpriced_usage_records })}</h3>
        </div>
      )}

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
                <th>{t("finance.dashboard.colCost")}</th>
                <th>{t("finance.dashboard.colMargin")}</th>
                <th>{t("finance.dashboard.colTokens")}</th>
              </tr>
            </thead>
            <tbody>
              {data.workers_metrics.length === 0 && (
                <tr><td colSpan={6}>{t("finance.dashboard.noSellers")}</td></tr>
              )}
              {data.workers_metrics.map((seller) => (
                <tr key={seller.worker_id}>
                  <td>
                    <strong>{seller.worker_name}</strong>
                    <small className="muted-block">{seller.worker_email}</small>
                  </td>
                  <td>{seller.clients_count}</td>
                  <td>{formatMxn(seller.monthly_revenue_mxn)}</td>
                  <td>{formatMxn(seller.ai_cost_mxn)}</td>
                  <td><strong>{formatMxn(seller.margin_mxn)}</strong></td>
                  <td>{formatTokens(seller.tokens_consumed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <h2>{t("finance.dashboard.perClientHeading")}</h2>
            <p>{t("finance.dashboard.perClientCopy")}</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("finance.dashboard.colClient")}</th>
                <th>{t("finance.dashboard.colPlan")}</th>
                <th>{t("finance.dashboard.colUsage")}</th>
                <th>{t("finance.dashboard.colCost")}</th>
                <th>{t("finance.dashboard.colMargin")}</th>
              </tr>
            </thead>
            <tbody>
              {data.clients_metrics.map((row) => (
                <tr key={row.client_id} className={row.is_blocked ? "row-blocked" : ""}>
                  <td>
                    <strong>{row.client_name}</strong>
                    <small className="muted-block">{row.seller_name || "—"}</small>
                  </td>
                  <td>{formatMxn(row.monthly_fee_mxn)}</td>
                  <td>
                    {formatTokens(row.tokens_used)}
                    <small className="muted-block">
                      {row.monthly_token_limit ? `${row.usage_pct}%` : t("finance.billing.unlimited")}
                    </small>
                  </td>
                  <td>{formatMxn(row.ai_cost_mxn)}</td>
                  <td><strong>{formatMxn(row.margin_mxn)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
