import { Pagination } from "@/components/Pagination";
import { Carte, OngletLien, Onglets, Pastille, Vide } from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { Refus } from "@/components/Refus";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type { Enrollment, Paginated, Section } from "@/lib/types";

export const metadata = { title: "الطالبات — معهد الأصلين" };

const TAILLE_PAGE = 25;

/**
 * Liste des etudiantes inscrites, filtrable par قسم et cherchable par nom ou
 * matricule. La recherche passe par un formulaire GET : l'URL reste
 * partageable et la page fonctionne sans JavaScript.
 */
export default async function PageEtudiantes({
  searchParams,
}: {
  searchParams: Promise<{ section?: string; q?: string; page?: string }>;
}) {
  // Le sidebar masque cette entree sans la permission ; l'URL, elle,
  // se tape a la main.
  if (!(await utilisateurAvec(PERMISSIONS.ETUDIANTES_GERER))) {
    return <Refus titre="الطالبات" />;
  }

  const parametres = await searchParams;
  const sectionChoisie = parametres.section ?? "";
  const recherche = (parametres.q ?? "").trim();
  const page = Math.max(1, Number(parametres.page ?? "1") || 1);

  const sections = await apiRequest<Paginated<Section>>(
    "/sections/?is_active=true",
  );

  const requete = new URLSearchParams({
    is_active: "true",
    page: String(page),
    page_size: String(TAILLE_PAGE),
    ordering: "student__matricule",
  });
  if (sectionChoisie) requete.set("section", sectionChoisie);
  if (recherche) requete.set("search", recherche);

  const inscriptions = await apiRequest<Paginated<Enrollment>>(
    `/enrollments/?${requete.toString()}`,
  );

  const lien = (
    modifications: Partial<{ section: string; q: string; page: number }>,
  ) => {
    const params = new URLSearchParams();
    const s = modifications.section ?? sectionChoisie;
    const q = modifications.q ?? recherche;
    if (s) params.set("section", s);
    if (q) params.set("q", q);
    params.set("page", String(modifications.page ?? 1));
    return `/etudiantes?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">الطالبات</h1>

      <Carte titre="البحث والتصفية">
        <form method="get" className="mb-4 flex flex-wrap items-center gap-2">
          {sectionChoisie ? (
            <input type="hidden" name="section" value={sectionChoisie} />
          ) : null}
          <input
            type="search"
            name="q"
            defaultValue={recherche}
            placeholder="الاسم أو رقم الطالبة"
            aria-label="بحث"
            className="champ max-w-xs"
          />
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
          >
            بحث
          </button>
          {recherche ? (
            <a
              href={lien({ q: "" })}
              className="rounded-xl border border-gray-200 px-3 py-2.5 text-sm text-gris hover:bg-gray-50"
            >
              إلغاء البحث
            </a>
          ) : null}
        </form>

        <Onglets
          libelle="القسم"
          enfants={[
            <OngletLien
              key="tous"
              href={lien({ section: "" })}
              actif={sectionChoisie === ""}
            >
              كل الأقسام
            </OngletLien>,
            ...sections.results.map((s) => (
              <OngletLien
                key={s.id}
                href={lien({ section: String(s.id) })}
                actif={String(s.id) === sectionChoisie}
              >
                {s.name_ar}
              </OngletLien>
            )),
          ]}
        />
      </Carte>

      <Carte titre="قائمة الطالبات" sansPadding>
        {inscriptions.results.length === 0 ? (
          <div className="p-4 sm:p-5">
            <Vide>لا توجد طالبة مطابقة.</Vide>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table min-w-[32rem]">
                <thead>
                  <tr>
                    <th>رقم الطالبة</th>
                    <th>الاسم الكامل</th>
                    <th>القسم</th>
                    <th className="fin">الحالة</th>
                  </tr>
                </thead>
                <tbody>
                  {inscriptions.results.map((inscription) => (
                    <tr key={inscription.id}>
                      <td>
                        <span className="chiffres text-gris">
                          {inscription.matricule}
                        </span>
                      </td>
                      <td className="font-medium">
                        {inscription.full_name_ar}
                      </td>
                      <td>{inscription.section_name}</td>
                      <td className="fin">
                        <Pastille
                          libelle={inscription.is_active ? "مسجلة" : "غير نشطة"}
                          variante={inscription.is_active ? "success" : "neutral"}
                          point
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-4 pb-4 sm:px-5 sm:pb-5">
              <Pagination
                page={page}
                count={inscriptions.count}
                pageSize={TAILLE_PAGE}
                href={(p) => lien({ page: p })}
                unite="طالبة"
              />
            </div>
          </>
        )}
      </Carte>
    </div>
  );
}
