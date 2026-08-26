"use client";

import { useT } from "@/lib/i18n";
import type { BillingMode } from "@/types";

export type BillingValues = {
  billing_mode: BillingMode;
  monthly_fee_mxn: string;
  monthly_token_limit: number;
};

export const DEFAULT_BILLING: BillingValues = {
  billing_mode: "plan",
  monthly_fee_mxn: "200.00",
  monthly_token_limit: 500000,
};

const PRESETS: { key: "presetBasic" | "presetPro" | "presetUnlimited"; fee: string; limit: number }[] = [
  { key: "presetBasic", fee: "200.00", limit: 500_000 },
  { key: "presetPro", fee: "500.00", limit: 1_500_000 },
  { key: "presetUnlimited", fee: "0.00", limit: 0 },
];

/** Billing controls shared by the client create and edit forms. */
export function BillingFields({
  value,
  onChange,
  anchorDay,
}: {
  value: BillingValues;
  onChange: (next: BillingValues) => void;
  anchorDay?: number;
}) {
  const t = useT();
  const set = (patch: Partial<BillingValues>) => onChange({ ...value, ...patch });

  const modeHint =
    value.billing_mode === "byok"
      ? t("finance.billing.modeByokHint")
      : value.billing_mode === "pay_as_you_go"
        ? t("finance.billing.modePaygHint")
        : t("finance.billing.modePlanHint");

  return (
    <section className="form-section">
      <div className="section-copy">
        <h2>{t("finance.billing.heading")}</h2>
        <p>{t("finance.billing.copy")}</p>
      </div>
      <div className="form-fields">
        <label>
          {t("finance.billing.mode")}
          <select value={value.billing_mode} onChange={(e) => set({ billing_mode: e.target.value as BillingMode })}>
            <option value="plan">{t("finance.billing.modePlan")}</option>
            <option value="pay_as_you_go">{t("finance.billing.modePayg")}</option>
            <option value="byok">{t("finance.billing.modeByok")}</option>
          </select>
          <small>{modeHint}</small>
        </label>

        <div className="preset-row">
          <span className="preset-label">{t("finance.billing.presetLabel")}</span>
          {PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              className="button ghost"
              onClick={() => set({ monthly_fee_mxn: preset.fee, monthly_token_limit: preset.limit })}
            >
              {t(`finance.billing.${preset.key}` as const)}
            </button>
          ))}
        </div>

        <div className="form-grid">
          <label>
            {t("finance.billing.fee")}
            <input
              type="number"
              min={0}
              step="0.01"
              value={value.monthly_fee_mxn}
              onChange={(e) => set({ monthly_fee_mxn: e.target.value })}
            />
          </label>
          <label>
            {t("finance.billing.tokenLimit")}
            <input
              type="number"
              min={0}
              step={1000}
              // Pay-as-you-go has no hard cap and BYOK spends the client's own
              // key, so a limit would be meaningless for both.
              disabled={value.billing_mode !== "plan"}
              value={value.monthly_token_limit}
              onChange={(e) => set({ monthly_token_limit: Number(e.target.value) })}
            />
            <small>{t("finance.billing.tokenLimitHint")}</small>
          </label>
        </div>

        {anchorDay ? <small className="muted-block">{t("finance.billing.cycleHint", { day: anchorDay })}</small> : null}
      </div>
    </section>
  );
}
