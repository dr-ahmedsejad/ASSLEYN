import {
  Activity,
  CalendarCheck,
  LockKeyhole,
  ShieldAlert,
  Users,
} from "lucide-react";

import { BoutonDeblocage } from "@/components/BoutonDeblocage";
import { Pagination } from "@/components/Pagination";
import { Refus } from "@/components/Refus";
import {
  Alerte,
  Carte,
  Indicateur,
  OngletLien,
  Onglets,
  Vide,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type {
  IssueConnexion,
  Paginated,
  StatistiquesVisites,
  TentativeConnexion,
  Verrou,
} from "@/lib/types";

export const metadata = { title: "الزيارات وسجل الدخول — معهد الأصلين" };

const TAILLE_PAGE = 25;

const PERIODES: { cle: string; libelle: string }[] = [
  { cle: "7", libelle: "آخر 7 أيام" },
  { cle: "30", libelle: "آخر 30 يوما" },
  { cle: "90", libelle: "آخر 90 يوما" },
  { cle: "tout", libelle: "منذ البداية" },
];

const FILTRES: { cle: string; libelle: string }[] = [
  { cle: "", libelle: "كل المحاولات" },
  { cle: "1", libelle: "الدخول الناجح" },
  { cle: "0", libelle: "المحاولات الفاشلة" },
];

/** Teinte de la pastille d'issue : le vert rassure, le rouge appelle l'oeil. */
const TON_ISSUE: Record<IssueConnexion, string> = {
  SUCCESS: "border-green-200 bg-green-50 text-green-700",
  BAD_PASSWORD: "border-amber-200 bg-amber-50 text-amber-700",
  UNKNOWN_USER: "border-red-200 bg-red-50 text-red-700",
  INACTIVE: "border-gray-200 bg-gray-50 text-gris",
  LOCKED: "border-red-200 bg-red-50 text-red-700",
};

/**
 * Frequentation et securite des acces.
 *
 * Une page, trois lectures : combien de visites et par qui, ce que dit le
 * journal des tentatives, et quels comptes sont fermes en ce moment.
 *
 * Le deblocage est reserve a `comptes.gerer` : consulter le journal n'autorise
 * pas a rouvrir une porte.
 */
export default async function PageSecurite({
  searchParams,
}: {
  searchParams: Promise<{
    periode?: string;
    succes?: string;
    q?: string;
    page?: string;
    historique?: string;
  }>;
}) {
  if (!(await utilisateurAvec(PERMISSIONS.JOURNAL_CONSULTER))) {
    return <Refus titre="الزيارات وسجل الدخول" />;
  }
  const peutDebloquer = await utilisateurAvec(PERMISSIONS.COMPTES_GERER);

  const parametres = await searchParams;
  const periode = PERIODES.some((p) => p.cle === parametres.periode)
    ? parametres.periode!
    : "30";
  const succes = FILTRES.some((f) => f.cle === (parametres.succes ?? ""))
    ? (parametres.succes ?? "")
    : "";
  const recherche = (parametres.q ?? "").trim();
  const page = Math.max(1, Number(parametres.page ?? "1") || 1);
  const historique = parametres.historique === "1";

  const requete = new URLSearchParams({
    periode,
    page: String(page),
    page_size: String(TAILLE_PAGE),
  });
  if (succes) requete.set("succes", succes);
  if (recherche) requete.set("username", recherche);

  const [stats, journal, verrous] = await Promise.all([
    apiRequest<StatistiquesVisites>(`/securite/statistiques/?periode=${periode}`),
    apiRequest<Paginated<TentativeConnexion>>(
      `/securite/journal/?${requete.toString()}`,
    ),
    peutDebloquer
      ? apiRequest<Paginated<Verrou>>(
          `/securite/verrous/?page_size=50${historique ? "&historique=1" : ""}`,
        )
      : Promise.resolve({ count: 0, next: null, previous: null, results: [] }),
  ]);

  const lien = (
    modifications: Partial<{
      periode: string;
      succes: string;
      q: string;
      page: number;
      historique: string;
    }>,
  ) => {
    const params = new URLSearchParams();
    params.set("periode", modifications.periode ?? periode);
    const s = modifications.succes ?? succes;
    if (s) params.set("succes", s);
    const q = modifications.q ?? recherche;
    if (q) params.set("q", q);
    const h = modifications.historique ?? (historique ? "1" : "");
    if (h) params.set("historique", h);
    params.set("page", String(modifications.page ?? 1));
    return `/securite?${params.toString()}`;
  };

  const maximum = Math.max(...stats.top_etudiantes.map((e) => e.visites), 1);

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">الزيارات وسجل الدخول</h1>

      <Onglets
        libelle="الفترة"
        enfants={PERIODES.map((p) => (
          <OngletLien
            key={p.cle}
            href={lien({ periode: p.cle })}
            actif={p.cle === periode}
          >
            {p.libelle}
          </OngletLien>
        ))}
      />

      {/* ─── Chiffres de frequentation ─────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Indicateur
          libelle="عدد الزيارات"
          valeur={stats.visites}
          detail="كل دخول ناجح"
          icone={<Activity size={17} />}
        />
        <Indicateur
          libelle="الزائرات"
          valeur={stats.visiteurs}
          detail="حسابات مختلفة"
          icone={<Users size={17} />}
        />
        <Indicateur
          libelle="زيارات اليوم"
          valeur={stats.visites_aujourdhui}
          icone={<CalendarCheck size={17} />}
        />
        <Indicateur
          libelle="محاولات فاشلة"
          valeur={stats.echecs}
          detail={`${stats.blocages} إقفالا في الفترة`}
          icone={<ShieldAlert size={17} />}
        />
      </div>

      {/* ─── Comptes bloques ───────────────────────────────────────── */}
      {peutDebloquer ? (
        <Carte
          titre={historique ? "الإقفالات (مع السابقة)" : "الحسابات المقفلة الآن"}
        >
          <div className="mb-4">
            <Onglets
              libelle="العرض"
              enfants={[
                <OngletLien
                  key="actifs"
                  href={lien({ historique: "" })}
                  actif={!historique}
                >
                  المقفلة الآن
                </OngletLien>,
                <OngletLien
                  key="tout"
                  href={lien({ historique: "1" })}
                  actif={historique}
                >
                  كل الإقفالات
                </OngletLien>,
              ]}
            />
          </div>

          {verrous.results.length === 0 ? (
            <Vide>
              {historique
                ? "لا توجد إقفالات مسجلة."
                : "لا يوجد حساب مقفل حاليا."}
            </Vide>
          ) : (
            <ul className="space-y-2.5">
              {verrous.results.map((verrou) => (
                <li
                  key={verrou.id}
                  className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-3.5 py-3 ${
                    verrou.actif
                      ? "border-red-200 bg-red-50"
                      : "border-gray-100 bg-white"
                  }`}
                >
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 font-semibold text-dark">
                      <LockKeyhole
                        size={14}
                        className={verrou.actif ? "text-red-600" : "text-gris"}
                      />
                      {verrou.full_name_ar || verrou.username}
                    </p>
                    <p className="chiffres mt-0.5 text-xs text-gris">
                      {verrou.username} · المستوى {verrou.level} ·{" "}
                      {verrou.duree_minutes} دقيقة
                      {verrou.ip_address ? ` · ${verrou.ip_address}` : ""}
                    </p>
                    {!verrou.actif && verrou.released_at ? (
                      <p className="mt-0.5 text-xs text-gris">
                        فُتح بواسطة {verrou.released_by_name || "انتهاء المدة"}
                      </p>
                    ) : null}
                  </div>

                  {verrou.actif ? (
                    <BoutonDeblocage
                      verrou={verrou.id}
                      secondes={verrou.secondes_restantes}
                    />
                  ) : (
                    <span className="text-xs text-gris">انتهى</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4">
            <Alerte ton="info">
              بعد خمس محاولات خاطئة يُقفل الحساب خمس دقائق، ثم خمس عشرة، ثم
              ثلاثين. الفتح اليدوي يمنح صاحبة الحساب خمس محاولات جديدة، ويبقى
              الإقفال مسجلا في السجل.
            </Alerte>
          </div>
        </Carte>
      ) : null}

      {/* ─── Les dix plus assidues ─────────────────────────────────── */}
      <Carte titre="أكثر عشر طالبات زيارة">
        {stats.top_etudiantes.length === 0 ? (
          <Vide>لا توجد زيارات في هذه الفترة.</Vide>
        ) : (
          <ol className="space-y-2">
            {stats.top_etudiantes.map((etudiante, index) => (
              <li key={etudiante.username} className="flex items-center gap-3">
                <span
                  className={`chiffres flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${
                    index < 3
                      ? "text-white"
                      : "border border-gray-200 bg-white text-gris"
                  }`}
                  style={
                    index < 3
                      ? { background: "linear-gradient(135deg,#004d24,#006633)" }
                      : undefined
                  }
                >
                  {index + 1}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="truncate text-sm font-medium text-dark">
                      {etudiante.full_name_ar || etudiante.username}
                    </p>
                    <span className="chiffres shrink-0 text-sm font-bold text-primary">
                      {etudiante.visites}
                    </span>
                  </div>
                  {/* Barre proportionnelle : le rang seul ne dit pas l'ecart. */}
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(etudiante.visites / maximum) * 100}%`,
                        background: "linear-gradient(90deg,#006633,#008844)",
                      }}
                    />
                  </div>
                  <p className="chiffres mt-0.5 text-xs text-gris">
                    {etudiante.username} · آخر زيارة{" "}
                    {new Date(etudiante.derniere).toLocaleString("fr-FR", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Carte>

      {/* ─── Journal ───────────────────────────────────────────────── */}
      <Carte titre="سجل محاولات الدخول" sansPadding>
        <div className="p-4 sm:p-5">
          <form method="get" className="mb-4 flex flex-wrap items-center gap-2">
            <input type="hidden" name="periode" value={periode} />
            {succes ? <input type="hidden" name="succes" value={succes} /> : null}
            <input
              type="search"
              name="q"
              defaultValue={recherche}
              placeholder="اسم المستخدم"
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
            libelle="النوع"
            enfants={FILTRES.map((f) => (
              <OngletLien
                key={f.cle || "tous"}
                href={lien({ succes: f.cle })}
                actif={f.cle === succes}
              >
                {f.libelle}
              </OngletLien>
            ))}
          />
        </div>

        {journal.results.length === 0 ? (
          <div className="px-4 pb-4 sm:px-5 sm:pb-5">
            <Vide>لا توجد محاولات في هذه الفترة.</Vide>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table min-w-[44rem]">
                <thead>
                  <tr>
                    <th>التاريخ</th>
                    <th>الحساب</th>
                    <th className="centre">النتيجة</th>
                    <th>عنوان IP</th>
                    <th className="fin">المتصفح</th>
                  </tr>
                </thead>
                <tbody>
                  {journal.results.map((ligne) => (
                    <tr key={ligne.id}>
                      <td>
                        <span className="chiffres text-xs text-gris">
                          {new Date(ligne.at).toLocaleString("fr-FR", {
                            dateStyle: "short",
                            timeStyle: "medium",
                          })}
                        </span>
                      </td>
                      <td>
                        <p className="font-medium">
                          {ligne.full_name_ar || "—"}
                        </p>
                        <span className="chiffres text-xs text-gris">
                          {ligne.username}
                        </span>
                      </td>
                      <td className="centre">
                        <span
                          className={`inline-block rounded-lg border px-2 py-0.5 text-xs font-medium ${TON_ISSUE[ligne.outcome]}`}
                        >
                          {ligne.outcome_display}
                        </span>
                      </td>
                      <td>
                        <span className="chiffres text-xs">
                          {ligne.ip_address ?? "—"}
                        </span>
                      </td>
                      <td className="fin">
                        <span
                          className="block max-w-[16rem] truncate text-xs text-gris"
                          title={ligne.user_agent}
                        >
                          {ligne.user_agent || "—"}
                        </span>
                      </td>
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
                unite="محاولة"
              />
            </div>
          </>
        )}
      </Carte>
    </div>
  );
}
