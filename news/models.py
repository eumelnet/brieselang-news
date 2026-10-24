from django.db import models
from django.urls import reverse


class Source(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField(unique=True, max_length=1000)
    parser = models.CharField(max_length=40, choices=[(x, x) for x in ["municipal", "events", "closures", "opening"]])
    category = models.CharField(max_length=40)
    enabled = models.BooleanField(default=True)
    last_attempt = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    item_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class Story(models.Model):
    CATEGORIES = [("dorfleben", "Dorfleben"), ("verkehr", "Verkehr"), ("veranstaltungen", "Veranstaltungen"), ("neueroeffnungen", "Neueröffnungen")]
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    external_id = models.CharField(max_length=200)
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    category = models.CharField(max_length=40, choices=CATEGORIES)
    summary = models.TextField(blank=True)
    evidence = models.TextField()
    date_label = models.CharField(max_length=200, blank=True)
    source_date = models.DateField(null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now_add=True)
    fingerprint = models.CharField(max_length=64)
    published = models.BooleanField(default=True)
    revision_count = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "external_id"], name="unique_source_item")]
        ordering = ["-source_date", "-updated_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("detail", args=[self.pk])


class Revision(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="revisions")
    captured_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=500)
    evidence = models.TextField()
    fingerprint = models.CharField(max_length=64)


class Tip(models.Model):
    text = models.TextField(max_length=4000)
    url = models.URLField(blank=True, max_length=1000)
    contact = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="neu", choices=[("neu", "Neu"), ("recherche", "In Recherche"), ("erledigt", "Erledigt")])

    class Meta:
        verbose_name = "Hinweis"
        verbose_name_plural = "Hinweise"

    def __str__(self):
        return self.text[:80]
