"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Facebook, Globe2, Instagram, MessageCircle, QrCode, Radio, type LucideIcon } from "lucide-react";
import { PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Client } from "@/types";

// Channels that belong to a single client: the card links to the client-scoped
// configuration page once a client is selected.
const clientChannels: { key: "whatsappCloud" | "whatsapp" | "messenger" | "instagram"; icon: LucideIcon; className: string; path: string }[] = [
  { key: "whatsappCloud", icon: MessageCircle, className: "whatsapp", path: "whatsapp-cloud" },
  { key: "whatsapp", icon: QrCode, className: "whatsapp", path: "whatsapp" },
  { key: "messenger", icon: Facebook, className: "facebook", path: "messenger" },
  { key: "instagram", icon: Instagram, className: "instagram", path: "instagram" },
];

export default function ChannelsPage() {
  const t = useT();
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  useEffect(() => { api<Client[]>("/clients").then(setClients); }, []);
  const selected = clients.find((item) => item.id === clientId);
  return <div className="page"><PageHead eyebrow={t("channels.head.eyebrow")} title={t("channels.head.title")} description={t("channels.head.description")} />
    <div className="channels-toolbar"><label htmlFor="channel-client">{t("channels.toolbar.clientLabel")}</label><select id="channel-client" value={clientId} onChange={(e) => setClientId(e.target.value)}><option value="">{t("channels.toolbar.allClients")}</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select>{selected && <Link href={`/clients/${selected.id}`} className="button secondary">{t("channels.toolbar.openClient")}</Link>}</div>
    <section className="channel-grid">{clientChannels.map((channel) => <article className="channel-card channel-card-live" key={channel.key}><div className={`channel-icon ${channel.className}`}><channel.icon size={24} /></div><span className="coming live">{t(`channels.${channel.key}.status`)}</span><h3>{t(`channels.${channel.key}.title`)}</h3><p>{t(`channels.${channel.key}.description`)}</p><small className="channel-owner">{selected?.name || t(`channels.${channel.key}.ownerPlaceholder`)}</small>{selected ? <Link className="button primary" href={`/clients/${selected.id}/channels/${channel.path}`}>{t(`channels.${channel.key}.configure`)} <ArrowRight size={16} /></Link> : <button className="button disabled" disabled>{t(`channels.${channel.key}.selectClient`)}</button>}</article>)}
      <article className="channel-card channel-card-live"><div className="channel-icon webchat"><Globe2 size={24} /></div><span className="coming live">{t("channels.webchat.status")}</span><h3>{t("channels.webchat.title")}</h3><p>{t("channels.webchat.description")}</p><small className="channel-owner">{selected?.name || t("channels.webchat.ownerPlaceholder")}</small><Link className="button primary" href={selected ? `/agents?client=${selected.id}` : "/agents"}>{t("channels.webchat.configure")} <ArrowRight size={16} /></Link></article></section>
    <div className="channels-note"><Radio size={18} /><p><strong>{t("channels.note.strong")}</strong> {t("channels.note.rest")}</p></div>
  </div>;
}
