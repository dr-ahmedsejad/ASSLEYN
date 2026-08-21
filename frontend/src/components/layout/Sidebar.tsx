"use client";

import Image from "next/image";
import { X } from "lucide-react";

import type { NavGroup } from "@/lib/nav-config";

import NavTree from "./NavTree";

interface Props {
  mobile?: boolean;
  groups: NavGroup[];
  pathname: string;
  openKey: string | null;
  setOpenKey: (k: string | null) => void;
  setSidebarOpen: (v: boolean) => void;
  isCollapsed: boolean;
  setIsCollapsed: (v: boolean) => void;
}

/**
 * Barre laterale.
 *
 * En RTL elle occupe le bord droit de l'ecran ; `border-e` (border-inline-end)
 * pose donc automatiquement la separation du bon cote, sans condition.
 */
export default function Sidebar({
  mobile = false,
  groups,
  pathname,
  openKey,
  setOpenKey,
  setSidebarOpen,
  isCollapsed,
  setIsCollapsed,
}: Props) {
  const hideText = isCollapsed && !mobile;

  return (
    <aside
      className={`z-50 shrink-0 transition-all duration-300 ease-in-out ${
        mobile
          ? "flex h-full w-72 flex-col overflow-y-auto bg-white shadow-drawer"
          : `sticky top-0 hidden h-screen min-h-screen flex-col overflow-y-auto overflow-x-hidden border-e border-gray-100 bg-white lg:flex ${
              hideText ? "w-[80px]" : "w-64"
            }`
      }`}
    >
      {/* Identite */}
      <div
        className={`flex shrink-0 items-center border-b border-gray-100 py-4 transition-all ${
          hideText ? "justify-center px-0" : "gap-3 px-5"
        }`}
      >
        <Image
          src="/logo-institut-carre.png"
          alt="شعار معهد الأصلين"
          width={40}
          height={40}
          priority
          className="h-10 w-10 shrink-0 object-contain"
        />

        {hideText ? null : (
          <div className="overflow-hidden">
            <p className="truncate text-xs font-bold tracking-widest text-primary">
              معهد الأصلين
            </p>
            <div
              className="my-0.5 h-0.5 w-8 rounded-full"
              style={{
                background:
                  "linear-gradient(90deg, #E5C018, rgba(229,192,24,0.3))",
              }}
            />
            <p className="truncate text-[10px] leading-tight text-gris">
              نظام إدارة النتائج
            </p>
          </div>
        )}

        {mobile ? (
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="إغلاق القائمة"
            className="ms-auto text-gris hover:text-dark"
          >
            <X size={18} />
          </button>
        ) : null}
      </div>

      {/* Navigation */}
      <nav
        aria-label="التنقل الرئيسي"
        className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-2"
      >
        <NavTree
          groups={groups}
          pathname={pathname}
          openKey={openKey}
          setOpenKey={setOpenKey}
          onLinkClick={() => setSidebarOpen(false)}
          hideText={hideText}
          setIsCollapsed={setIsCollapsed}
        />
      </nav>

      {/* Pied */}
      <div className="shrink-0 border-t border-gray-100 px-2 pb-4 pt-3">
        <div className="mb-1 flex items-center justify-center gap-1.5">
          <span
            className="h-1 w-4 shrink-0 rounded-full"
            style={{ background: "#006633" }}
          />
          <span
            className="h-1 w-4 shrink-0 rounded-full"
            style={{ background: "#E5C018" }}
          />
          <span
            className="h-1 w-4 shrink-0 rounded-full"
            style={{ background: "#C82020" }}
          />
        </div>
        {hideText ? null : (
          <p className="truncate text-center text-[10px] text-gris/50">
            معهد الأصلين — مصلحة الامتحانات
          </p>
        )}
      </div>
    </aside>
  );
}
