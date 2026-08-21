import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/api";
import { FormulaireMotDePasse } from "./FormulaireMotDePasse";

export const metadata = { title: "تغيير كلمة السر — معهد الأصلين" };

export default async function PageMotDePasse() {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) redirect("/connexion");

  const premiereConnexion = utilisateur.must_change_password;

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="mb-2 text-center text-xl font-bold text-dark">
          تغيير كلمة السر
        </h1>

        {premiereConnexion ? (
          <p className="mb-6 rounded-xl border border-yellow-200 bg-yellow-50 px-3.5 py-2.5 text-center text-sm text-yellow-700">
            كلمة السر الحالية مؤقتة. يجب تغييرها قبل متابعة الاستخدام.
          </p>
        ) : (
          <p className="mb-6 text-center text-sm text-gris">
            اختاري كلمة سر لا تقل عن اثني عشر حرفا.
          </p>
        )}

        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-card">
          <FormulaireMotDePasse />
        </div>
      </div>
    </main>
  );
}
