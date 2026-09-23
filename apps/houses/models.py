from django.conf import settings
from django.db import models
from django.utils import timezone


class House(models.Model):
    """School house for the house system (spec §17)."""

    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=20, blank=True)
    motto = models.CharField(max_length=200, blank=True)
    captain = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="captained_houses",
    )
    vice_captain = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vice_captained_houses",
    )
    staff_coordinator = models.ForeignKey(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coordinated_houses",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class HousePoint(models.Model):
    """A single awarded house point (spec §17)."""

    house = models.ForeignKey(
        House, on_delete=models.CASCADE, related_name="points"
    )
    student = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="house_points",
    )
    date = models.DateField(default=timezone.localdate)
    points = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=200, blank=True)
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="awarded_house_points",
    )

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.points} pt → {self.house.name}"


class HouseActivity(models.Model):
    """Event, competition or practice attached to the house system."""

    class ActivityKind(models.TextChoices):
        EVENT = "event", "Event"
        COMPETITION = "competition", "Competition"
        PRACTICE = "practice", "Practice"

    house = models.ForeignKey(
        House,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
    )
    name = models.CharField(max_length=150)
    date = models.DateField(default=timezone.localdate)
    kind = models.CharField(
        max_length=15, choices=ActivityKind.choices, default=ActivityKind.EVENT
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.name


class HouseResult(models.Model):
    """Rank and points gained by a house in an activity."""

    activity = models.ForeignKey(
        HouseActivity, on_delete=models.CASCADE, related_name="results"
    )
    house = models.ForeignKey(
        House, on_delete=models.CASCADE, related_name="results"
    )
    rank = models.PositiveIntegerField(default=1)
    points_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["activity", "rank"]
        constraints = [
            models.UniqueConstraint(fields=["activity", "house"], name="unique_activity_house"),
            models.UniqueConstraint(fields=["activity", "rank"], name="unique_activity_rank"),
        ]

    def __str__(self):
        return f"{self.house.name} (#{self.rank}) in {self.activity.name}"