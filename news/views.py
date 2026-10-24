from datetime import timedelta
from django import forms
from django.conf import settings
from django.contrib.syndication.views import Feed
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from .models import Source, Story, Tip


def index(request):
    stories = Story.objects.filter(published=True)
    category = request.GET.get("kategorie", "")
    query = request.GET.get("q", "")[:100]
    if category:
        stories = stories.filter(category=category)
    if query:
        stories = stories.filter(Q(title__icontains=query) | Q(evidence__icontains=query))
    return render(request, "news/index.html", {"stories": stories[:100], "categories": Story.CATEGORIES, "category": category, "query": query, "total": Story.objects.filter(published=True).count(), "source_count": Source.objects.filter(enabled=True).count()})


def detail(request, pk):
    story = get_object_or_404(Story, pk=pk, published=True)
    return render(request, "news/detail.html", {"story": story})


def sources(request):
    return render(request, "news/sources.html", {"sources": Source.objects.all(), "stale_before": timezone.now() - timedelta(hours=3)})


class TipForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Tip
        fields = ["text", "url", "contact"]
        labels = {"text": "Was gibt es Neues?", "url": "Link zur Quelle (optional)", "contact": "E-Mail für Rückfragen (optional)"}
        widgets = {"text": forms.Textarea(attrs={"rows": 6, "placeholder": "Was, wo und wann?"})}


def tip(request):
    form = TipForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        last = request.session.get("last_tip", 0)
        if timezone.now().timestamp() - last < 120:
            form.add_error(None, "Bitte warte zwei Minuten bis zum nächsten Hinweis.")
        else:
            if not form.cleaned_data["website"]:
                form.save()
            request.session["last_tip"] = timezone.now().timestamp()
            return HttpResponseRedirect(reverse("tip") + "?gesendet=1")
    return render(request, "news/tip.html", {"form": form, "sent": request.GET.get("gesendet") == "1"})


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


class NewsFeed(Feed):
    title = "Brieselang News"
    link = "/"
    description = "Lokale Meldungen mit Quellen aus Brieselang, Bredow und Zeestow"

    def items(self):
        return Story.objects.filter(published=True)[:40]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return "Quelle: " + item.source.name + ". " + item.date_label

    def item_pubdate(self, item):
        return item.updated_at

    def item_link(self, item):
        return settings.SITE_URL + item.get_absolute_url()
