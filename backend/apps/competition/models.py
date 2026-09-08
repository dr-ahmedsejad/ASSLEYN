"""
Concours entre groupes d'etudiantes.

Le deroule est **entierement determine a l'avance**. Les groupes et les
questions sont ordonnes ; le tour d'indice i revient au groupe i modulo le
nombre de groupes, et porte la question i. Tous les tours sont donc crees au
demarrage, d'un coup.

Ce choix n'est pas une commodite : c'est ce qui permet au jury de mener la
competition **sans reseau**. Sa tablette telecharge le deroule complet une
fois, puis chaque geste — lancer un tour, trancher — devient une modification
qu'on peut differer et rejouer, au lieu d'une demande au serveur dont depend
la suite. La salle ou se tient ce concours n'a pas de connexion fiable.

Deux consequences de forme, assumees :

- le nombre de tours est un multiple du nombre de groupes ; les questions en
  trop restent inutilisees, pour que personne ne reponde a une question de
  plus que sa voisine ;
- l'heure d'un geste est celle que le navigateur annonce, bornee par le
  serveur. Un geste rejoue cinq minutes apres coup garde ainsi son heure
  reelle, et le retard ne se transforme pas en depassement de temps.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CompetitionKind(models.TextChoices):
    """
    Les deux formes que prend une session.

    La **مسابقة ثقافية** repose sur des enonces : chaque tour porte une
    question, et le nombre de tours decoule du nombre de questions saisies.

    La **ندوة شعرية** n'a pas d'enonce du tout. Le tour de parole revient a un
    groupe, le chronometre tourne, et le jury constate seulement si le groupe
    a recite dans le temps. Rien n'est donc a preparer avant la seance, et le
    nombre de tours ne peut venir que d'un nombre de جولات fixe a la creation.
    """

    CULTURELLE = "CULTURELLE", _("مسابقة ثقافية")
    POETIQUE = "POETIQUE", _("ندوة شعرية")


class CompetitionState(models.TextChoices):
    DRAFT = "DRAFT", _("قيد التحضير")
    RUNNING = "RUNNING", _("جارية")
    FINISHED = "FINISHED", _("منتهية")


class TurnOutcome(models.TextChoices):
    PENDING = "PENDING", _("في انتظار القرار")
    CORRECT = "CORRECT", _("إجابة صحيحة")
    NO_ANSWER = "NO_ANSWER", _("لم يجب")


class Competition(models.Model):
    """Une session de concours, de sa preparation a son classement final."""

    name = models.CharField(_("اسم المسابقة"), max_length=150)

    kind = models.CharField(
        _("نوع المسابقة"),
        max_length=12,
        choices=CompetitionKind.choices,
        default=CompetitionKind.CULTURELLE,
    )

    #: Adresse de l'ecran public. Tiree au hasard, assez longue pour ne pas se
    #: deviner, assez courte pour se recopier depuis une projection.
    code = models.CharField(_("رمز العرض العام"), max_length=12, unique=True)

    state = models.CharField(
        _("الحالة"),
        max_length=10,
        choices=CompetitionState.choices,
        default=CompetitionState.DRAFT,
    )

    turn_seconds = models.PositiveSmallIntegerField(
        _("مدة الدور بالثواني"),
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(600)],
    )

    #: Nombre d'enonces gardes hors du deroule, pour les departages.
    #:
    #: Sans ce reglage, la reserve vaut le reste de la division des questions
    #: par les groupes : elle est donc toujours plus petite que le nombre de
    #: groupes, et n'alimente jamais une manche complete. Ajouter des questions
    #: n'y change rien — elles forment simplement une جولة de plus.
    #:
    #: Un nombre plutot qu'un oui-non : une manche de departage consomme un
    #: enonce par groupe encore a egalite, et il en faut parfois plusieurs
    #: d'affilee. Cinq groupes et vingt enonces reserves, ce sont quatre
    #: manches possibles.
    #:
    #: Ce qui est reserve ne se joue pas : le deroule ordinaire se calcule sur
    #: ce qui reste.
    questions_reservees = models.PositiveSmallIntegerField(
        _("عدد أسئلة الحسم"),
        default=0,
        validators=[MaxValueValidator(500)],
    )

    #: L'ecran public montre l'enonce du tour en cours — jamais les suivants.
    show_question = models.BooleanField(_("عرض السؤال للجمهور"), default=True)

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="competitions_creees",
        verbose_name=_("أنشأها"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(_("بداية المسابقة"), null=True, blank=True)
    finished_at = models.DateTimeField(_("نهاية المسابقة"), null=True, blank=True)

    class Meta:
        verbose_name = _("مسابقة")
        verbose_name_plural = _("المسابقات")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def en_cours(self) -> bool:
        return self.state == CompetitionState.RUNNING

    @property
    def avec_questions(self) -> bool:
        """Une ندوة شعرية n'a pas d'enonces — ni a saisir, ni a projeter."""
        return self.kind == CompetitionKind.CULTURELLE

    def tours_prevus(self) -> int:
        """
        Nombre de tours que la session comportera, ou zero s'il est inconnu.

        Une مسابقة ثقافية tient dans ses questions : quatre groupes et trente
        questions donnent vingt-huit tours, deux questions restant en reserve,
        sans quoi deux groupes auraient une occasion de plus que les autres et
        le classement se discuterait.

        Une ندوة شعرية n'a pas de fin ecrite d'avance : elle tourne jusqu'a ce
        que le jury l'arrete. Zero dit ici « on ne sait pas », et non « aucun »
        — les ecrans doivent alors annoncer le tour sans pretendre connaitre
        le dernier.
        """
        groupes = self.groups.count()
        if groupes == 0:
            return 0
        if not self.avec_questions:
            return 0
        questions = self.questions.count()
        if questions == 0:
            return 0
        gardees = self.questions_reservees
        return (max(questions - gardees, 0) // groupes) * groupes


class Group(models.Model):
    """Un groupe concurrent. Porte un nom, et une couleur qui le suit partout."""

    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="groups",
        verbose_name=_("المسابقة"),
    )
    name = models.CharField(_("اسم المجموعة"), max_length=100)
    display_order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    #: Teinte du groupe sur les deux ecrans. Un groupe se reconnait de loin a
    #: sa couleur avant de se lire.
    color = models.CharField(_("اللون"), max_length=7, default="#006633")

    class Meta:
        verbose_name = _("مجموعة")
        verbose_name_plural = _("المجموعات")
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "name"],
                name="un_nom_de_groupe_par_competition",
            )
        ]

    def __str__(self) -> str:
        return self.name


class GroupMember(models.Model):
    """
    Une participante d'un groupe : un nom, rien de plus.

    Aucun lien vers le fichier des etudiantes, et c'est voulu. Ces listes
    disent qui compose une equipe le temps d'une seance ; les participantes ne
    se connectent pas, et rien dans l'application ne leur est rattache. Un
    lien vers une fiche n'apporterait donc rien — mais il ferait apparaitre
    comme une anomalie chaque nom sans correspondance, alors que la plupart
    n'en auront jamais.

    Le nom reste donc du texte, tel qu'il a ete depose. C'est aussi ce qui
    rend le compte rendu d'une seance passee insensible aux changements du
    fichier des etudiantes.
    """

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name=_("المجموعة"),
    )
    name = models.CharField(_("الاسم"), max_length=150)
    display_order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("عضوة")
        verbose_name_plural = _("الأعضاء")
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "name"],
                name="un_nom_par_groupe",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Question(models.Model):
    """
    Une question posee a voix haute.

    La reponse est **facultative**, et elle ne juge rien : le point est
    toujours accorde par la commission, jamais par une comparaison de texte.
    Elle sert d'aide-memoire a qui anime — quand les questions arrivent d'un
    classeur prepare par quelqu'un d'autre, personne ne connait par coeur les
    vingt reponses.

    Elle ne sort donc que par les routes du jury. L'ecran de la salle
    construit sa reponse a la main, champ par champ : la reponse n'y figure
    pas, et ne peut pas s'y glisser par inadvertance.
    """

    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("المسابقة"),
    )
    text = models.TextField(_("نص السؤال"))

    #: Vide tant que personne ne l'a saisie — la saisie collee n'en fournit pas.
    answer = models.TextField(_("الإجابة"), blank=True)

    display_order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("سؤال")
        verbose_name_plural = _("الأسئلة")
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return self.text[:60]


class Turn(models.Model):
    """
    Un tour : un groupe, une question, un chronometre, une decision.

    `awarded_late` n'est pas un aveu mais une trace. Le jury peut toujours
    accorder le point apres l'expiration — une equipe a pu repondre a temps
    pendant que le reseau flanchait. Ce qui compte est que la decision soit
    lisible apres coup, avec son heure et son motif : dans un concours, la
    premiere chose contestee est l'equite.
    """

    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="turns",
        verbose_name=_("المسابقة"),
    )
    index = models.PositiveSmallIntegerField(_("رقم الدور"))
    round_number = models.PositiveSmallIntegerField(_("الجولة"))

    #: Numero de la manche de departage, ou zero pour un tour ordinaire.
    #:
    #: Les tours de barrage ne rapportent aucun point au classement : ils
    #: **ordonnent** des groupes deja a egalite, sans jamais les faire passer
    #: devant quelqu'un qu'ils n'avaient pas rattrape. Un groupe a cinq points
    #: qui gagne le barrage reste a cinq points ; il passe seulement devant
    #: celles qui en avaient cinq aussi.
    tiebreak_round = models.PositiveSmallIntegerField(_("جولة الحسم"), default=0)

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="turns",
        verbose_name=_("المجموعة"),
    )
    #: Vide pour une ندوة شعرية : le tour de parole s'y ouvre sans enonce.
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="turns",
        null=True,
        blank=True,
        verbose_name=_("السؤال"),
    )

    started_at = models.DateTimeField(_("بداية الدور"), null=True, blank=True)
    outcome = models.CharField(
        _("النتيجة"),
        max_length=10,
        choices=TurnOutcome.choices,
        default=TurnOutcome.PENDING,
    )
    decided_at = models.DateTimeField(_("وقت القرار"), null=True, blank=True)
    decided_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tours_decides",
        verbose_name=_("قرر"),
    )

    awarded_late = models.BooleanField(_("مُنح بعد انتهاء الوقت"), default=False)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("دور")
        verbose_name_plural = _("الأدوار")
        ordering = ["index"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "index"], name="un_tour_par_indice"
            )
        ]

    def __str__(self) -> str:
        return f"{self.competition.name} — دور {self.index + 1} — {self.group.name}"

    @property
    def tranche(self) -> bool:
        return self.outcome != TurnOutcome.PENDING

    def secondes_restantes(self, maintenant=None) -> int:
        """Temps restant, jamais negatif. Zero tant que le tour n'a pas demarre."""
        if self.started_at is None:
            return self.competition.turn_seconds
        maintenant = maintenant or timezone.now()
        ecoule = (maintenant - self.started_at).total_seconds()
        return max(int(self.competition.turn_seconds - ecoule), 0)


class TurnAction(models.Model):
    """
    Geste du jury, identifie par le navigateur qui l'a produit.

    Hors ligne, la tablette accumule ses gestes et les rejoue a la reconnexion
    — parfois plusieurs fois, si la reponse du serveur s'est perdue en chemin.
    Cette table retient les identifiants deja vus : rejouer un geste devient
    sans effet, et le jury n'a pas a se demander si son clic est passe.
    """

    class Kind(models.TextChoices):
        START = "START", _("انطلاق الدور")
        DECIDE = "DECIDE", _("قرار")

    client_uuid = models.UUIDField(_("معرف العملية"), unique=True)
    turn = models.ForeignKey(
        Turn,
        on_delete=models.CASCADE,
        related_name="actions",
        verbose_name=_("الدور"),
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("عملية")
        verbose_name_plural = _("العمليات")
        ordering = ["received_at"]

    def __str__(self) -> str:
        return f"{self.kind} {self.client_uuid}"
