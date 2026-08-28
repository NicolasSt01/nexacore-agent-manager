"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, LibraryBig, LoaderCircle } from "lucide-react";
import { EmptyState, Modal, PageHead } from "@/components/ui";
import { useToast } from "@/components/toast";
import { api, messageFrom } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Agent, AgentTemplate, Client } from "@/types";

export default function TemplatesPage() {
  const t = useT();
  const toast = useToast();
  const router = useRouter();
  const [templates, setTemplates] = useState<AgentTemplate[] | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [cloning, setCloning] = useState<AgentTemplate | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api<AgentTemplate[]>("/agents/templates"), api<Client[]>("/clients")])
      .then(([rows, clientRows]) => { setTemplates(rows); setClients(clientRows); })
      .catch((err) => { setTemplates([]); toast.error(messageFrom(err)); });
  }, [toast]);

  async function clone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cloning) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const created = await api<Agent>(`/agents/${cloning.id}/clone`, {
        method: "POST",
        body: JSON.stringify({
          client_id: data.get("client_id"),
          name: data.get("name"),
          copy_documents: data.get("copy_documents") === "on",
        }),
      });
      toast.success(t("finance.templates.cloneDone"));
      setCloning(null);
      // Straight into the new agent: the seller's next step is adjusting the
      // details that differ for this client.
      router.push(`/agents/${created.id}`);
    } catch (err) {
      toast.error(messageFrom(err));
    } finally {
      setBusy(false);
    }
  }

  if (!templates) return <div className="page-loading"><LoaderCircle className="spin" /> {t("finance.templates.loading")}</div>;

  return (
    <div className="page">
      <PageHead
        eyebrow={t("finance.templates.eyebrow")}
        title={t("finance.templates.title")}
        description={t("finance.templates.description")}
      />

      {templates.length === 0 ? (
        <EmptyState
          icon={<LibraryBig size={24} />}
          title={t("finance.templates.title")}
          description={t("finance.templates.empty")}
        />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("finance.templates.colTemplate")}</th>
                <th>{t("finance.templates.colIndustry")}</th>
                <th>{t("finance.templates.colContent")}</th>
                <th>{t("finance.templates.colModel")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {templates.map((template) => (
                <tr key={template.id}>
                  <td>
                    <strong>{template.template_label || template.name}</strong>
                    <small className="muted-block">
                      {t("finance.templates.sourceClient", { name: template.source_client_name })}
                    </small>
                  </td>
                  <td>{template.industry || "—"}</td>
                  <td>
                    {t("finance.templates.contentSummary", {
                      qa: template.qa_count,
                      docs: template.document_count,
                      tools: template.tool_count,
                    })}
                  </td>
                  <td><code>{template.model}</code></td>
                  <td>
                    <button className="button secondary" onClick={() => setCloning(template)}>
                      <Copy size={15} /> {t("finance.templates.clone")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={Boolean(cloning)}
        title={t("finance.templates.cloneTitle", { name: cloning?.template_label || cloning?.name || "" })}
        description={t("finance.templates.cloneCopy")}
        onClose={() => setCloning(null)}
      >
        <form className="page-form" onSubmit={clone}>
          <div className="form-fields">
            <label>
              {t("finance.templates.cloneClient")}
              <select name="client_id" required defaultValue="">
                <option value="" disabled>{t("finance.templates.cloneSelectClient")}</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{client.name}</option>
                ))}
              </select>
            </label>
            <label>
              {t("finance.templates.cloneName")}
              <input name="name" required defaultValue={cloning?.name ?? ""} />
            </label>
            <label className="switch-row">
              <span>
                <strong>{t("finance.templates.cloneDocuments")}</strong>
                <small>{t("finance.templates.cloneDocumentsHint")}</small>
              </span>
              <input name="copy_documents" type="checkbox" defaultChecked />
            </label>
            <div className="form-footer">
              <button type="button" className="button secondary" onClick={() => setCloning(null)}>
                {t("common.cancel")}
              </button>
              <button className="button primary" disabled={busy}>
                {busy ? <LoaderCircle className="spin" size={16} /> : <Copy size={16} />} {t("finance.templates.cloneSubmit")}
              </button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  );
}
