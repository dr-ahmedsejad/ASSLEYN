import { Pagination } from "@/components/Pagination";
import { Alerte, Carte, Nombre, OngletLien, Onglets, Vide } from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { Refus } from "@/components/Refus";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type {
  GradeHistoryEntry,
  GradeStatus,
  Paginated,
  Section,
} from "@/lib/types";

export const metadata = { title: "سجل تغييرات النقاط — معهد الأصلين" };

const TAILLE_PAGE = 25;

const LIBELLE_STATUT: Record<GradeStatus | string, string> = {
  ENTERED: "مسجلة",
  ABSENT: "غائبة",
  EXCUSED: "غياب مبرر",
  EXEMPT: "معفاة",
  MISSING: "غير مدخلة",
  "": "—",
};

/**
 * Journal d'audit des notes.
 *
 * C'est la piece qui repond a « qui a change cette note, quand, et pourquoi ».
 * Rien n'y est modifiable : la table est en ecriture seule cote base.
 */
export default async function PageJournal({
  searchParams,
}: {
  searchParams: Promise<{ section?: string; q?: string; page?: string }>;
}) {
  // Le sidebar masque cette entree sans la permission ; l'URL, elle,
  // se tape a la main.
  if (!(await utilisateurAvec(PERMISSIONS.JOURNAL_CONSULTER))) {
    return <Refus titre="سجل تغييرات النقاط" />;
  }

  const parametres = await searchParams;
  const sectionChoisie = parametres.section ?? "";
  const recherche = (parametres.q ?? "").trim();
  const page = Math.max(1, Number(parametres.page ?? "1") || 1);

  const sections = await apiRequest<Paginated<Section>>(
    "/sections/?is_active=true",
  );

  const requete = new URLSearchParams({
    ordering: "-changed_at",
    page: String(page),
    page_size: String(TAILLE_PAGE),
  });
  if (sectionChoisie) {
    requete.set("grade__curriculum__section", sectionChoisie);
  }
  if (recherche) requete.set("search", recherche);

  const journal = await apiRequest<Paginated<GradeHistoryEntry>>(
    `/grade-history/?${requete.toString()}`,
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
    return `/journal?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">سجل تغييرات النقاط</h1>

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

        <div className="mt-4">
          <Alerte ton="info">
            هذا السجل غير قابل للتعديل ولا للحذف. كل إدخال أو تصحيح لنقطة يترك
            أثرا دائما باسم صاحبه وتاريخه.
          </Alerte>
        </div>
      </Carte>

      <Carte titre="الحركات" sansPadding>
        {journal.results.length === 0 ? (
          <div className="p-4 sm:p-5">
            <Vide>لا توجد حركات مسجلة.</Vide>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table min-w-[52rem]">
                <thead>
                  <tr>
                    <th>التاريخ</th>
                    <th>الطالبة</th>
                    <th>المادة</th>
                    <th className="centre">من</th>
                    <th className="centre">إلى</th>
                    <th>السبب</th>
                    <th className="fin">بواسطة</th>
                  </tr>
                </thead>
                <tbody>
                  {journal.results.map((ligne) => (
                    <tr key={ligne.id}>
                      <td>
                        <span className="chiffres text-xs text-gris">
                          {new Date(ligne.changed_at).toLocaleString("fr-FR", {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </span>
                      </td>
                      <td>
                        <p className="font-medium">{ligne.full_name_ar}</p>
                        <span className="chiffres text-xs text-gris">
                          {ligne.matricule} · {ligne.section_name}
                        </span>
                      </td>
                      <td>{ligne.subject_name}</td>
                      <td className="centre">
                        <ValeurNote
                          valeur={ligne.old_value}
                          statut={ligne.old_status}
                        />
                      </td>
                      <td className="centre">
                        <span className="font-semibold">
                          <ValeurNote
                            valeur={ligne.new_value}
                            statut={ligne.new_status}
                          />
                        </span>
                      </td>
                      <td className="text-xs text-gris">
                        {ligne.reason || "—"}
                      </td>
                      <td className="fin text-xs">{ligne.changed_by_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-4 pb-4 sm:px-5 sm:pb-5">
              <Pagination
                page={page}
                count={journal.count}
                pageSize={TAILLE_PAGE}
                href={(p) => lien({ page: p })}
                unite="حركة"
              />
            </div>
          </>
        )}
      </Carte>
    </div>
  );
}

function ValeurNote({
  valeur,
  statut,
}: {
  valeur: string | null;
  statut: string;
}) {
  if (valeur !== null) return <Nombre>{valeur}</Nombre>;
  return (
    <span className="text-xs text-gris">
      {LIBELLE_STATUT[statut] ?? statut ?? "—"}
    </span>
  );
}
