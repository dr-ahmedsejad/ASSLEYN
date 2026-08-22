import { KeyRound, LockKeyhole, ShieldAlert } from "lucide-react";

import { CorrectionNom } from "@/components/CorrectionNom";
import { ReinitialisationMotDePasse } from "@/components/ReinitialisationMotDePasse";
import type { Compte } from "@/lib/types";

const TON_ROLE: Record<string, string> = {
  ADMIN: "border-green-200 bg-green-50 text-green-700",
  ASSISTANT: "border-amber-200 bg-amber-50 text-amber-700",
  TEACHER: "border-blue-200 bg-blue-50 text-blue-700",
  STUDENT: "border-gray-200 bg-gray-50 text-gris",
};

function Marque({
  icone,
  texte,
  ton,
}: {
  icone: React.ReactNode;
  texte: string;
  ton: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[11px] font-medium ${ton}`}
    >
      {icone}
      {texte}
    </span>
  );
}

/**
 * Une ligne de la liste des comptes.
 *
 * Composant serveur : il ne porte aucun etat. Les deux gestes qu'il propose —
 * corriger le nom, rendre le mot de passe — sont des composants clients
 * autonomes, chacun avec son action. La liste peut ainsi compter cent lignes
 * sans qu'aucune n'envoie de JavaScript tant qu'on ne la touche pas.
 *
 * En pile sur telephone, en ligne des que la largeur le permet.
 */
export function LigneCompte({ compte }: { compte: Compte }) {
  return (
    <li className="flex flex-col gap-3 px-4 py-3.5 sm:px-5 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="font-semibold text-dark">{compte.full_name_ar}</p>
          <CorrectionNom
            key={compte.id}
            utilisateur={compte.id}
            nom={compte.full_name_ar}
          />
          <span
            className={`rounded-lg border px-2 py-0.5 text-[11px] font-medium ${TON_ROLE[compte.role]}`}
          >
            {compte.role_display}
          </span>
        </div>

        <p className="chiffres mt-1 text-xs text-gris" dir="ltr">
          {compte.username}
          {compte.matricule && compte.matricule !== compte.username
            ? ` · ${compte.matricule}`
            : ""}
          {compte.last_login
            ? ` · ${new Date(compte.last_login).toLocaleString("fr-FR", {
                dateStyle: "short",
                timeStyle: "short",
              })}`
            : " · —"}
        </p>

        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {compte.verrouille ? (
            <Marque
              icone={<LockKeyhole size={11} />}
              texte="مقفل"
              ton="border-red-200 bg-red-50 text-red-700"
            />
          ) : null}
          {compte.must_change_password ? (
            <Marque
              icone={<KeyRound size={11} />}
              texte="كلمة سر مؤقتة"
              ton="border-amber-200 bg-amber-50 text-amber-700"
            />
          ) : null}
          {!compte.is_active ? (
            <Marque
              icone={<ShieldAlert size={11} />}
              texte="معطل"
              ton="border-gray-200 bg-gray-50 text-gris"
            />
          ) : null}
        </div>
      </div>

      <div className="shrink-0">
        <ReinitialisationMotDePasse
          key={compte.id}
          utilisateur={compte.id}
          nom={compte.full_name_ar}
          suggestion={
            compte.matricule ? `${compte.matricule}${compte.matricule}` : undefined
          }
        />
      </div>
    </li>
  );
}
