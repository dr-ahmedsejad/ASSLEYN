import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight } from "lucide-react";

import { PreparationConcours } from "@/components/PreparationConcours";
import { Refus } from "@/components/Refus";
import { apiRequestOuIntrouvable } from "@/lib/api";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type { Competition } from "@/lib/types";

export const metadata = { title: "تحضير المسابقة — معهد الأصلين" };

export default async function PagePreparation({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  if (!(await utilisateurAvec(PERMISSIONS.COMPETITION_ANIMER))) {
    return <Refus titre="تحضير المسابقة" />;
  }

  const { id } = await params;
  const competition = await apiRequestOuIntrouvable<Competition>(`/competitions/${id}/`);

  // Une competition lancee n'a plus rien a preparer : sa console l'attend.
  if (competition.state !== "DRAFT") {
    redirect(`/competitions/${id}/animer`);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-dark">{competition.name}</h1>
        <Link
          href="/competitions"
          className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          <ArrowRight size={15} />
          كل المسابقات
        </Link>
      </div>

      <PreparationConcours competition={competition} />
    </div>
  );
}
