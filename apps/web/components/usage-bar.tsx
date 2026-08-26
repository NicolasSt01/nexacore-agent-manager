"use client";

import { useT } from "@/lib/i18n";
import { formatTokens } from "@/lib/roles";
import type { Client } from "@/types";

/** Amber once the client is close to the limit, red once the package is gone. */
const WARNING_THRESHOLD = 80;

export function UsageBar({ client }: { client: Client }) {
  const t = useT();
  const unlimited = !client.monthly_token_limit;
  const pct = unlimited ? 0 : Math.min(100, client.percentage_tokens_used);
  const level = client.is_blocked ? "danger" : pct >= WARNING_THRESHOLD ? "warning" : "ok";

  return (
    <div className={`usage-bar usage-${level}`}>
      <div className="usage-bar-head">
        <strong>{t("finance.billing.usageHeading")}</strong>
        <span>
          {unlimited
            ? t("finance.billing.usageUnlimited", { used: formatTokens(client.used_tokens_current_cycle) })
            : t("finance.billing.usageOf", {
                used: formatTokens(client.used_tokens_current_cycle),
                limit: formatTokens(client.monthly_token_limit),
              })}
        </span>
      </div>
      {!unlimited && (
        <div className="usage-track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="usage-fill" style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="usage-bar-foot">
        <span>
          {client.is_blocked
            ? t("finance.billing.usageBlocked")
            : pct >= WARNING_THRESHOLD
              ? t("finance.billing.usageWarning")
              : t("finance.billing.usageOk")}
        </span>
        {client.cycle_start && client.cycle_end && (
          <small>
            {t("finance.billing.usageCycle", {
              start: new Date(client.cycle_start).toLocaleDateString(),
              end: new Date(client.cycle_end).toLocaleDateString(),
            })}
          </small>
        )}
      </div>
    </div>
  );
}
