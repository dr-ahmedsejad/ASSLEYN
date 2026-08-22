import CoquilleServeur from "@/components/layout/CoquilleServeur";

/**
 * Changement de mot de passe : meme coquille que le reste de l'application.
 *
 * `exigerMotDePasseChange` est a faux, et c'est toute la raison d'etre de
 * cette mise en page : le layout de `(app)` renvoie ici tant que le mot de
 * passe est provisoire, si bien que cette page ne peut pas vivre dans ce
 * groupe sans boucler.
 */
export default function LayoutMotDePasse({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <CoquilleServeur exigerMotDePasseChange={false}>{children}</CoquilleServeur>
  );
}
