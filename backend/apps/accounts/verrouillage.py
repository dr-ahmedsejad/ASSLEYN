"""
Protection contre les tentatives repetees.

Politique, telle que l'etablissement l'a fixee :

    5 echecs  -> 5 minutes de blocage
    5 de plus -> 15 minutes
    5 de plus -> 30 minutes

Les paliers montent tant que les blocages se succedent dans une meme journee.
Passe ce delai sans nouvel incident, le compteur repart de zero : une etudiante
qui s'est trompee un mardi ne doit pas commencer le mercredi au palier trois.

Pourquoi une mecanique maison plutot que django-axes
------------------------------------------------------------------
Axes verrouille tres bien, mais a duree fixe. L'escalade demanderait de lui
greffer un compteur externe, et l'ecran de deblocage comme le minuteur
devraient alors lire ses tables internes. Deux comptabilites paralleles pour
un seul phenomene finissent toujours par diverger.

Ici, une seule source : le journal des tentatives. Le blocage courant, le
nombre d'essais restants, le temps restant et l'historique en decoulent, et ne
peuvent pas se contredire.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import Lockout, LoginAttempt, LoginOutcome, User

#: Nombre d'echecs consecutifs tolere avant blocage.
LIMITE_TENTATIVES = 5

#: Duree du blocage, par palier. Le dernier palier se repete indefiniment :
#: au-dela d'une demi-heure, allonger encore ne protege plus mieux, cela ne
#: fait qu'aggraver la gene pour une personne qui a simplement oublie son mot
#: de passe.
PALIERS: tuple[timedelta, ...] = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
)

#: Fenetre au-dela de laquelle l'escalade est oubliee.
FENETRE_ESCALADE = timedelta(hours=24)

ECHECS = (
    LoginOutcome.BAD_PASSWORD,
    LoginOutcome.UNKNOWN_USER,
    LoginOutcome.INACTIVE,
)


@dataclass(frozen=True)
class EtatVerrou:
    """Ce que l'interface a besoin de savoir, et rien de plus."""

    verrouille: bool
    #: Secondes restantes avant reouverture. 0 si le compte est ouvert.
    secondes_restantes: int = 0
    #: Palier atteint (1, 2, 3...), pour expliquer la duree a l'utilisateur.
    niveau: int = 0
    #: Essais encore possibles avant blocage. `None` quand le compte est bloque.
    tentatives_restantes: int | None = None
    verrou: Lockout | None = None


def duree_du_palier(niveau: int) -> timedelta:
    """Duree associee a un palier, le dernier valant pour tous les suivants."""
    return PALIERS[min(niveau, len(PALIERS)) - 1]


def verrou_actif(username: str, *, maintenant=None) -> Lockout | None:
    """Blocage en cours pour ce nom d'utilisateur, s'il y en a un."""
    maintenant = maintenant or timezone.now()
    return (
        Lockout.objects.filter(
            username=username, released_at__isnull=True, until__gt=maintenant
        )
        .order_by("-started_at")
        .first()
    )


def _debut_du_compteur(username: str) -> object:
    """
    Instant a partir duquel les echecs comptent.

    Tout ce qui precede une reussite ou la fin d'un blocage est solde : apres
    un blocage purge, l'etablissement veut cinq nouvelles chances, pas une.
    """
    derniere_reussite = LoginAttempt.objects.filter(
        username=username, outcome=LoginOutcome.SUCCESS
    ).aggregate(dernier=Max("at"))["dernier"]

    # Fin *effective* du dernier blocage : l'heure de reouverture manuelle
    # quand l'administration a debloque, sinon l'expiration prevue. Prendre
    # `until` dans les deux cas laisserait une fenetre ou plus rien ne
    # verrouille — celui qui insiste apres un deblocage doit etre rebloque.
    dernier_verrou = (
        Lockout.objects.filter(username=username).order_by("-started_at").first()
    )
    fin_verrou = None
    if dernier_verrou is not None:
        fin_verrou = dernier_verrou.released_at or dernier_verrou.until

    connus = [r for r in (derniere_reussite, fin_verrou) if r is not None]
    return max(connus) if connus else None


def echecs_consecutifs(username: str) -> int:
    """Nombre d'echecs depuis le dernier repere (reussite ou fin de blocage)."""
    requete = LoginAttempt.objects.filter(username=username, outcome__in=ECHECS)
    depuis = _debut_du_compteur(username)
    if depuis is not None:
        requete = requete.filter(at__gt=depuis)
    return requete.count()


def _niveau_suivant(username: str, *, maintenant=None) -> int:
    """Palier du prochain blocage, d'apres les blocages recents."""
    maintenant = maintenant or timezone.now()
    recents = Lockout.objects.filter(
        username=username, started_at__gt=maintenant - FENETRE_ESCALADE
    ).count()
    return recents + 1


def etat(username: str, *, maintenant=None) -> EtatVerrou:
    """Etat courant du compte, tel que l'interface doit le presenter."""
    maintenant = maintenant or timezone.now()
    verrou = verrou_actif(username, maintenant=maintenant)
    if verrou is not None:
        restant = int((verrou.until - maintenant).total_seconds())
        return EtatVerrou(
            verrouille=True,
            secondes_restantes=max(restant, 0),
            niveau=verrou.level,
            verrou=verrou,
        )
    return EtatVerrou(
        verrouille=False,
        tentatives_restantes=max(LIMITE_TENTATIVES - echecs_consecutifs(username), 0),
    )


def journaliser(
    username: str,
    outcome: str,
    *,
    user: User | None = None,
    ip: str | None = None,
    user_agent: str = "",
) -> LoginAttempt:
    """Inscrit une tentative au journal."""
    return LoginAttempt.objects.create(
        username=username,
        user=user,
        outcome=outcome,
        ip_address=ip,
        user_agent=user_agent[:255],
    )


def enregistrer_echec(
    username: str,
    outcome: str,
    *,
    user: User | None = None,
    ip: str | None = None,
    user_agent: str = "",
    maintenant=None,
) -> EtatVerrou:
    """
    Enregistre un echec et, si le seuil est atteint, pose le blocage.

    Renvoie l'etat resultant : soit le nombre d'essais qui restent, soit le
    blocage tout juste ouvert avec son minuteur.
    """
    maintenant = maintenant or timezone.now()
    journaliser(username, outcome, user=user, ip=ip, user_agent=user_agent)

    if echecs_consecutifs(username) < LIMITE_TENTATIVES:
        return etat(username, maintenant=maintenant)

    niveau = _niveau_suivant(username, maintenant=maintenant)
    duree = duree_du_palier(niveau)
    verrou = Lockout.objects.create(
        username=username,
        user=user,
        level=niveau,
        until=maintenant + duree,
        ip_address=ip,
    )
    return EtatVerrou(
        verrouille=True,
        secondes_restantes=int(duree.total_seconds()),
        niveau=niveau,
        verrou=verrou,
    )


def enregistrer_succes(
    user: User, *, ip: str | None = None, user_agent: str = ""
) -> LoginAttempt:
    """Enregistre une connexion reussie, ce qui remet le compteur a zero."""
    return journaliser(
        user.username,
        LoginOutcome.SUCCESS,
        user=user,
        ip=ip,
        user_agent=user_agent,
    )


def deverrouiller(verrou: Lockout, *, par: User) -> Lockout:
    """
    Rouvre un compte avant l'heure.

    Le blocage n'est pas supprime mais **clos** : il reste au dossier, avec la
    trace de qui l'a leve. Effacer l'incident retirerait a l'administration le
    seul indice d'une attaque en cours.
    """
    verrou.released_at = timezone.now()
    verrou.released_by = par
    verrou.save(update_fields=["released_at", "released_by"])
    return verrou
