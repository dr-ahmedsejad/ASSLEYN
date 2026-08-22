import { KeyRound, LockKeyhole, ShieldAlert, UserCheck } from "lucide-react";

import { LigneCompte } from "@/components/LigneCompte";
import { Pagination } from "@/components/Pagination";
import { Refus } from "@/components/Refus";
import { Carte, OngletLien, Onglets, Vide } from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type { Compte, Paginated } from "@/lib/types";

export const metadata = { title: "الحسابات — معهد الأصلين" };

const TAILLE_PAGE = 25;

const ROLES = [
  { cle: "", libelle: "الكل" },
  { cle: "ADMIN", libelle: "مدير" },
  { cle: "ASSISTANT", libelle: "مساعد الإدارة" },
  { cle: "TEACHER", libelle: "أستاذ" },
  { cle: "STUDENT", libelle: "طالبة" },
];

const ETATS = [
  { cle: "", libelle: "كل الحسابات" },
  { cle: "verrouilles", libelle: "المقفلة" },
  { cle: "mdp_provisoire", libelle: "بكلمة سر مؤقتة" },
];

/**
 * Les comptes, tous roles confondus.
 *
 * A distinguer de `/droits`, qui ne montre que le personnel : cet ecran-la
 * sert a deleguer une capacite, et les droits d'une etudiante tiennent a son
 * statut. C'est pour cela que le compte d'une etudiante n'y figurait pas — et
 * qu'il n'existait aucun moyen de lui rendre son mot de passe.
 *
 * C'est ce que fait cette page : retrouver n'importe quel compte, corriger son
 * nom, lui rendre l'acces.
 */
export default async function PageComptes({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    role?: string;
    etat?: string;
    page?: string;
  }>;
}) {
  if (!(await utilisateurAvec(PERMISSIONS.COMPTES_GERER))) {
    return <Refus titre="الحسابات" />;
  }

  const parametres = await searchParams;
  const recherche = (parametres.q ?? "").trim();
  const role = ROLES.some((r) => r.cle === parametres.role)
    ? (parametres.role ?? "")
    : "";
  const etat = ETATS.some((e) => e.cle === parametres.etat)
    ? (parametres.etat ?? "")
    : "";
  const page = Math.max(1, Number(parametres.page ?? "1") || 1);

  const requete = new URLSearchParams({
    page: String(page),
    page_size: String(TAILLE_PAGE),
  });
  if (recherche) requete.set("search", recherche);
  if (role) requete.set("role", role);
  if (etat) requete.set(etat, "1");

  const comptes = await apiRequest<Paginated<Compte>>(
    `/rbac/comptes/?${requete.toString()}`,
  );

  const lien = (
    modifications: Partial<{
      q: string;
      role: string;
      etat: string;
      page: number;
    }>,
  ) => {
    const params = new URLSearchParams();
    const q = modifications.q ?? recherche;
    if (q) params.set("q", q);
    const r = modifications.role ?? role;
    if (r) params.set("role", r);
    const e = modifications.etat ?? etat;
    if (e) params.set("etat", e);
    params.set("page", String(modifications.page ?? 1));
    return `/comptes?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">الحسابات</h1>

      <Carte titre="البحث">
        <form method="get" className="mb-4 flex flex-wrap items-center gap-2">
          {role ? <input type="hidden" name="role" value={role} /> : null}
          {etat ? <input type="hidden" name="etat" value={etat} /> : null}
          <input
            type="search"
            name="q"
            defaultValue={recherche}
            placeholder="الاسم أو رقم الطالبة أو اسم المستخدم"
            aria-label="بحث"
            className="champ max-w-sm"
          />
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
          >
            بحث
          </button>
        </form>

        <div className="space-y-3">
          <Onglets
            libelle="الدور"
            enfants={ROLES.map((r) => (
              <OngletLien
                key={r.cle || "tous"}
                href={lien({ role: r.cle })}
                actif={r.cle === role}
              >
                {r.libelle}
              </OngletLien>
            ))}
          />
          <Onglets
            libelle="الحالة"
            enfants={ETATS.map((e) => (
              <OngletLien
                key={e.cle || "tous"}
                href={lien({ etat: e.cle })}
                actif={e.cle === etat}
              >
                {e.libelle}
              </OngletLien>
            ))}
          />
        </div>
      </Carte>

      <Carte titre={`${comptes.count} حسابا`} sansPadding>
        {comptes.results.length === 0 ? (
          <div className="p-4 sm:p-5">
            <Vide>لا يوجد حساب مطابق.</Vide>
          </div>
        ) : (
          <>
            <ul className="divide-y divide-gray-100">
              {comptes.results.map((compte) => (
                <LigneCompte key={compte.id} compte={compte} />
              ))}
            </ul>

            <div className="px-4 pb-4 pt-4 sm:px-5 sm:pb-5">
              <Pagination
                page={page}
                count={comptes.count}
                pageSize={TAILLE_PAGE}
                href={(p) => lien({ page: p })}
                unite="حساب"
              />
            </div>
          </>
        )}
      </Carte>

      <Carte titre="ما تعنيه العلامات">
        <ul className="space-y-2 text-sm text-dark-soft">
          <li className="flex items-center gap-2">
            <KeyRound size={14} className="text-gris" />
            <span>
              <strong>كلمة سر مؤقتة</strong> — لم تُغيَّر بعد أول دخول.
            </span>
          </li>
          <li className="flex items-center gap-2">
            <LockKeyhole size={14} className="text-red-600" />
            <span>
              <strong>مقفل</strong> — بعد محاولات خاطئة متكررة. يُفتح من صفحة
              الزيارات وسجل الدخول، أو بتعيين كلمة سر جديدة من هنا.
            </span>
          </li>
          <li className="flex items-center gap-2">
            <ShieldAlert size={14} className="text-gris" />
            <span>
              <strong>معطل</strong> — الحساب موجود لكنه لا يسمح بالدخول.
            </span>
          </li>
          <li className="flex items-center gap-2">
            <UserCheck size={14} className="text-gris" />
            <span>
              تعيين كلمة سر جديدة لا يحتاج معرفة القديمة، ويفتح الحساب إن كان
              مقفلا.
            </span>
          </li>
        </ul>
      </Carte>
    </div>
  );
}
