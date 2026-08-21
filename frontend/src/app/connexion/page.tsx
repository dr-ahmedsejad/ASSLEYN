import Image from "next/image";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/api";
import { FormulaireConnexion } from "./FormulaireConnexion";

export const metadata = { title: "تسجيل الدخول — معهد الأصلين" };

export default async function PageConnexion() {
  const utilisateur = await getCurrentUser();
  if (utilisateur) redirect("/");

  return (
    <main
      className="flex flex-1 items-center justify-center px-4 py-12"
      style={{
        background:
          "radial-gradient(1200px 600px at 50% -10%, rgba(0,102,51,0.10), transparent 60%), #f8fafc",
      }}
    >
      <div className="w-full max-w-sm">
        <header className="mb-8 flex flex-col items-center text-center">
          <Image
            src="/logo-institut.png"
            alt="شعار معهد الأصلين"
            width={132}
            height={119}
            priority
            className="mb-3 h-auto w-28 object-contain"
          />
          <h1 className="text-2xl font-bold text-primary">معهد الأصلين</h1>
          <div
            className="my-2 h-0.5 w-14 rounded-full"
            style={{
              background:
                "linear-gradient(90deg, rgba(229,192,24,0.3), #E5C018, rgba(229,192,24,0.3))",
            }}
          />
          <p className="text-sm text-gris">نظام إدارة النتائج الدراسية</p>
        </header>

        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-card">
          <FormulaireConnexion />
        </div>

        <div className="mt-6 flex items-center justify-center gap-1.5">
          <span
            className="h-1 w-5 rounded-full"
            style={{ background: "#006633" }}
          />
          <span
            className="h-1 w-5 rounded-full"
            style={{ background: "#E5C018" }}
          />
          <span
            className="h-1 w-5 rounded-full"
            style={{ background: "#C82020" }}
          />
        </div>

        <p className="mt-4 text-center text-xs leading-relaxed text-gris">
          اسم المستخدم للطالبة هو رقمها.
          <br />
          عند تعذر الدخول، راجعي مصلحة الامتحانات.
        </p>
      </div>
    </main>
  );
}
