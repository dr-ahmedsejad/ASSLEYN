"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";

import { isGroupActive, resolveGroups } from "@/lib/nav-config";
import type { CurrentUser, Semester } from "@/lib/types";

import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

/**
 * Coquille de l'application : barre laterale + barre du haut + contenu.
 *
 * Composant client parce qu'il porte l'etat d'ouverture de la navigation.
 * L'utilisateur lui est transmis par le layout serveur : aucune identite
 * n'est reconstruite cote navigateur.
 */
export default function Shell({
  user,
  fusul,
  faslCourant,
  children,
}: {
  user: CurrentUser;
  fusul: Semester[];
  faslCourant: Semester | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const groups = resolveGroups(user.permissions, user.role);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  /*
   * Le groupe ouvert se deduit du chemin courant : c'est une donnee derivee,
   * pas un etat a synchroniser. Un clic de l'utilisateur le remplace, mais
   * seulement tant qu'il reste sur la meme page — a la navigation suivante,
   * le groupe correspondant a la nouvelle page reprend la main.
   */
  const cleActive =
    groups.find((groupe) => isGroupActive(groupe, pathname))?.key ??
    groups[0]?.key ??
    null;

  const [choix, setChoix] = useState<{
    chemin: string;
    cle: string | null;
  } | null>(null);

  const openKey = choix?.chemin === pathname ? choix.cle : cleActive;
  const setOpenKey = (cle: string | null) => setChoix({ chemin: pathname, cle });

  const proprietesSidebar = {
    groups,
    pathname,
    openKey,
    setOpenKey,
    setSidebarOpen,
    isCollapsed,
    setIsCollapsed,
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar {...proprietesSidebar} />

      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <div className="relative z-50 ms-auto">
            <Sidebar mobile {...proprietesSidebar} />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          user={user}
          fusul={fusul}
          faslCourant={faslCourant}
          onOpenMobile={() => setSidebarOpen(true)}
          onToggleCollapsed={() => setIsCollapsed(!isCollapsed)}
        />
        <main className="flex-1 p-3 sm:p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
