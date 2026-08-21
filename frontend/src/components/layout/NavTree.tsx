"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { isGroupActive, type NavGroup } from "@/lib/nav-config";

interface Props {
  groups: NavGroup[];
  pathname: string;
  openKey: string | null;
  setOpenKey: (k: string | null) => void;
  onLinkClick: () => void;
  hideText: boolean;
  setIsCollapsed: (v: boolean) => void;
}

/**
 * Arbre de navigation de la barre laterale.
 *
 * En RTL le chevron pointe vers la gauche au repos et pivote vers le bas a
 * l'ouverture ; le liseré doré d'un groupe actif est place en `start`, donc a
 * droite. Aucun `left`/`right` en dur.
 */
export default function NavTree({
  groups,
  pathname,
  openKey,
  setOpenKey,
  onLinkClick,
  hideText,
  setIsCollapsed,
}: Props) {
  return (
    <>
      {groups.map((group) => {
        const isOpen = openKey === group.key;
        const isActive = isGroupActive(group, pathname);
        const Icon = group.icon;

        return (
          <div key={group.key}>
            {group.section ? (
              <div
                className={`flex items-center gap-2 pt-4 pb-1 ${
                  hideText ? "justify-center px-0" : "px-3"
                }`}
              >
                {hideText ? (
                  <span className="h-px w-6 bg-gray-300" />
                ) : (
                  <>
                    <span className="whitespace-nowrap text-[11px] font-bold tracking-widest text-gris">
                      {group.section}
                    </span>
                    <span className="h-px flex-1 bg-gray-200" />
                  </>
                )}
              </div>
            ) : null}

            <button
              type="button"
              onClick={() => {
                if (hideText) {
                  setIsCollapsed(false);
                  setOpenKey(group.key);
                } else {
                  setOpenKey(isOpen ? null : group.key);
                }
              }}
              title={hideText ? group.label : undefined}
              aria-expanded={isOpen}
              aria-current={isActive ? "page" : undefined}
              className={`group relative mb-0.5 flex w-full items-center rounded-xl py-2 font-medium transition-all ${
                hideText ? "justify-center px-0" : "gap-2.5 px-3"
              } ${
                isOpen
                  ? "text-white"
                  : isActive
                    ? "bg-gray-50 text-primary"
                    : "text-dark-soft hover:bg-gray-50 hover:text-primary"
              }`}
              style={
                isOpen
                  ? {
                      background:
                        "linear-gradient(135deg, #006633, #008844)",
                    }
                  : undefined
              }
            >
              {isOpen ? (
                <span
                  className="absolute inset-inline-start-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-s-full"
                  style={{ background: "#E5C018", insetInlineStart: 0 }}
                />
              ) : null}

              <Icon
                size={17}
                className={
                  isOpen
                    ? "shrink-0 text-white"
                    : "shrink-0 text-gris group-hover:text-primary"
                }
              />

              {hideText ? null : (
                <>
                  <span className="flex-1 truncate text-start text-[15px]">
                    {group.label}
                  </span>
                  <ChevronLeft
                    size={14}
                    className="shrink-0 transition-transform duration-200"
                    style={{
                      color: isOpen ? "#E5C018" : "#94a3b8",
                      transform: isOpen ? "rotate(-90deg)" : "none",
                    }}
                  />
                </>
              )}
            </button>

            {isOpen && !hideText ? (
              <div className="mb-1 ps-4">
                {group.items.map((item) => {
                  const activeSub =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname === item.href ||
                        pathname.startsWith(`${item.href}/`);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onLinkClick}
                      className={`mb-0.5 flex items-center gap-2 rounded-lg px-3 py-1.5 text-[13px] transition-all ${
                        activeSub
                          ? "font-semibold text-primary"
                          : "text-gris hover:bg-gray-50 hover:text-primary"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors ${
                          activeSub ? "bg-primary" : "bg-gray-300"
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </>
  );
}
