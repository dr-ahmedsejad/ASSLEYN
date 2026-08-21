import Link from "next/link";
import { ShieldAlert } from "lucide-react";

import { Carte } from "./ui";

/**
 * Page refusee faute de droit.
 *
 * Le sidebar masque deja ce qui n'est pas accessible ; ceci couvre l'URL
 * tapee a la main ou le vieux favori. On dit clairement ce qui manque et on
 * propose une sortie, plutot que de laisser une page casser sur le 403 de
 * l'API.
 */
export function Refus({
  titre,
  retour = "/",
}: {
  titre: string;
  retour?: string;
}) {
  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">{titre}</h1>
      <Carte>
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <ShieldAlert size={30} className="text-gray-300" />
          <p className="font-medium text-dark">
            لا تملك الصلاحية اللازمة لهذه الصفحة.
          </p>
          <p className="max-w-sm text-sm text-gris">
            إن كنت بحاجة إليها، اطلب من الإدارة منحك الصلاحية من صفحة
            «الأدوار والصلاحيات».
          </p>
          <Link
            href={retour}
            className="mt-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
          >
            العودة
          </Link>
        </div>
      </Carte>
    </div>
  );
}
