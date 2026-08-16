"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { Bot, Building2, Inbox, LayoutDashboard, LogOut, Menu, MessageSquareText, Radio, Settings, X } from "lucide-react";
import { api } from "@/lib/api";
import { useT, type I18nKey } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/language-switcher";
import type { User } from "@/types";

const navigation: { href: string; labelKey: I18nKey; icon: typeof LayoutDashboard }[] = [
  { href: "/", labelKey: "nav.home", icon: LayoutDashboard },
  { href: "/clients", labelKey: "nav.clients", icon: Building2 },
  { href: "/agents", labelKey: "nav.agents", icon: Bot },
  { href: "/inbox", labelKey: "nav.inbox", icon: Inbox },
  { href: "/playground", labelKey: "nav.playground", icon: MessageSquareText },
  { href: "/channels", labelKey: "nav.channels", icon: Radio },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
];

// Extra path prefixes served without a session (comma-separated, baked at
// build). Lets a deployment add public pages without patching the shell.
const EXTRA_PUBLIC_PATHS = (process.env.NEXT_PUBLIC_PUBLIC_PATHS || "")
  .split(",")
  .map((path) => path.trim())
  .filter(Boolean);

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useT();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(pathname !== "/login");
  const [mobileOpen, setMobileOpen] = useState(false);
  const isLogin = pathname === "/login";
  const isPortal = pathname.startsWith("/portal/");
  const isWidget = pathname.startsWith("/widget/");
  const isExtraPublic = EXTRA_PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
  const isBare = isLogin || isPortal || isWidget || isExtraPublic;

  useEffect(() => {
    if (isBare) { setLoading(false); return; }
    setLoading(true);
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [isBare, pathname, router]);

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  if (isBare) return <>{children}</>;
  if (loading || !user) return <div className="app-loader"><span className="openlivery-icon"><img src="/brand/openlivery-logo-original.png" alt="" /></span><span>{t("shell.loading")}</span></div>;

  return (
    <div className="app-layout">
      <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label={t("shell.openMenu")}><Menu /></button>
      {mobileOpen && <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <Link href="/" className="brand"><span className="openlivery-icon"><img src="/brand/openlivery-logo-original.png" alt="" /></span><span>OpenLivery</span></Link>
          <button className="sidebar-close" onClick={() => setMobileOpen(false)} aria-label={t("shell.closeMenu")}><X /></button>
        </div>
        <div className="sidebar-workspace"><Building2 size={14} /><span>{user.agency.name}</span></div>
        <nav>
          <span className="nav-label">{t("nav.section")}</span>
          {navigation.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return <Link key={item.href} href={item.href} className={active ? "active" : ""} onClick={() => setMobileOpen(false)}><item.icon size={18} /><span>{t(item.labelKey)}</span></Link>;
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="user-avatar">{user.name.slice(0, 1).toUpperCase()}</div>
          <div className="user-meta"><strong>{user.name}</strong><span>{user.email}</span></div>
          <button className="icon-button inverse" onClick={logout} title={t("shell.logout")}><LogOut size={17} /></button>
        </div>
        <LanguageSwitcher />
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
