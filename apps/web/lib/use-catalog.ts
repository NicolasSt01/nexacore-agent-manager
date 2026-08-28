"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CatalogModel } from "@/types";

/**
 * The AI model catalog, from the backend.
 *
 * The backend is the single source of truth: it is what prices usage and what
 * the daily sync checks against providers. A second hard-coded list in the
 * frontend is how the model picker silently went empty for OpenCode.
 *
 * Cached per page load — the catalog only changes on deploy.
 */
let cache: CatalogModel[] | null = null;

export function useCatalog(): CatalogModel[] {
  const [models, setModels] = useState<CatalogModel[]>(cache ?? []);

  useEffect(() => {
    if (cache) return;
    api<CatalogModel[]>("/catalog/models")
      .then((rows) => { cache = rows; setModels(rows); })
      .catch(() => setModels([]));
  }, []);

  return models;
}

/** Model ids for one provider, cheapest first, so the affordable option leads. */
export function modelsForProvider(models: CatalogModel[], provider: string): string[] {
  return models
    .filter((model) => model.provider === provider)
    .sort((a, b) => a.input_price_per_1k - b.input_price_per_1k)
    .map((model) => model.id);
}

export function findModel(models: CatalogModel[], provider: string, id: string): CatalogModel | undefined {
  return models.find((model) => model.provider === provider && model.id === id);
}
