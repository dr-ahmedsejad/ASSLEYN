import Link from "next/link";
import { ExternalLink, Play, Trophy } from "lucide-react";

import { NouvelleCompetition } from "@/components/NouvelleCompetition";
import { Refus } from "@/components/Refus";
import { Carte, Vide } from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type { Competition, Paginated } from "@/lib/types";

export const metadata = { title: "المسابقات — معهد الأصلين" };

const TON_ETAT: Record<string, string> = {
  DRAFT: "border-gray-200 bg-gray-50 text-gris",
  RUNNING: "border-green-200 bg-green-50 text-green-700",
  FINISHED: "border-amber-200 bg-amber-50 text-amber-700",
};

export default async function PageCompetitions() {
  if (!(await utilisateurAvec(PERMISSIONS.COMPETITION_ANIMER))) {
    return <Refus titre="المسابقات" />;
  }

  const liste = await apiRequest<Paginated<Competition>>("/competitions/");

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">المسابقات</h1>

      <NouvelleCompetition />

      <Carte titre={`${liste.count} مسابقة`} sansPadding>
        {liste.results.length === 0 ? (
          <div className="p-4 sm:p-5">
            <Vide>لا توجد مسابقة بعد.</Vide>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {liste.results.map((competition) => (
              <li
                key={competition.id}
                className="flex flex-col gap-3 px-4 py-3.5 sm:px-5 md:flex-row md:items-center md:justify-between"
              >
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 font-semibold text-dark">
                    <Trophy size={15} className="text-gris" />
                    {competition.name}
                    <span
                      className={`rounded-lg border px-2 py-0.5 text-[11px] font-medium ${TON_ETAT[competition.state]}`}
                    >
                      {competition.state_display}
                    </span>
                  </p>
                  <p className="chiffres mt-1 text-xs text-gris">
                    {competition.nombre_groupes} مجموعات ·{" "}
                    {competition.nombre_questions} سؤالا ·{" "}
                    {competition.turn_seconds} ثانية للدور
                  </p>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  {competition.state === "DRAFT" ? (
                    <Link
                      href={`/competitions/${competition.id}`}
                      className="rounded-xl border border-gray-200 px-3.5 py-2 text-sm font-medium text-dark-soft transition-colors hover:bg-gray-50"
                    >
                      التحضير
                    </Link>
                  ) : (
                    <>
                      <Link
                        href={`/competitions/${competition.id}/animer`}
                        className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                        style={{
                          background: "linear-gradient(135deg,#006633,#008844)",
                        }}
                      >
                        <Play size={14} />
                        {competition.state === "RUNNING" ? "إدارة" : "النتيجة"}
                      </Link>
                      <Link
                        href={`/direct/${competition.code}`}
                        target="_blank"
                        className="flex items-center gap-1.5 rounded-xl border border-gray-200 px-3.5 py-2 text-sm font-medium text-gris transition-colors hover:bg-gray-50"
                      >
                        <ExternalLink size={14} />
                        <span className="chiffres">{competition.code}</span>
                      </Link>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Carte>
    </div>
  );
}
