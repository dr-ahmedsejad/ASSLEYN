/**
 * Relais public de l'ecran de salle.
 *
 * Distinct du relais BFF, et c'est voulu : celui-ci ne joint **aucun** cookie.
 * L'ecran projete dans la salle n'est personne, et la page qui l'interroge ne
 * doit pas pouvoir emprunter la session de l'ordinateur qui l'affiche.
 *
 * Il existe pour que le navigateur n'ait pas a connaitre l'adresse de Django —
 * la meme raison que le reste de l'application.
 */

import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, API_PREFIX } from "@/lib/config";

export async function GET(
  _requete: NextRequest,
  contexte: { params: Promise<{ code: string }> },
): Promise<NextResponse> {
  const { code } = await contexte.params;

  // Le code est un mot de six caracteres tires d'un alphabet connu : tout ce
  // qui n'y ressemble pas ne merite pas d'atteindre Django.
  if (!/^[A-Za-z0-9]{4,12}$/.test(code)) {
    return NextResponse.json({ detail: "رمز غير صالح." }, { status: 404 });
  }

  const reponse = await fetch(
    `${API_BASE_URL}${API_PREFIX}/direct/${code.toUpperCase()}/`,
    { cache: "no-store", headers: { Accept: "application/json" } },
  );

  const texte = await reponse.text();
  return new NextResponse(texte || null, {
    status: reponse.status,
    headers: { "Content-Type": "application/json" },
  });
}

export const dynamic = "force-dynamic";
