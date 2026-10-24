from django.test import TestCase, Client
from .collect import parse, save_item
from .models import Source, Story, Revision, Tip


class CollectionTests(TestCase):
    def setUp(self):
        self.source = Source.objects.create(name="Gemeinde", url="https://www.gemeindebrieselang.de/sperrungen", parser="closures", category="verkehr")

    def test_multiple_closures_on_one_page_and_changed_deadline(self):
        html = '<div id="content_frame"><p>Zeestow gesperrt</p><p>Veröffentlicht am: 12.10.2026</p><p>Bis 30. Oktober.</p><p>---</p><p>Querstraße gesperrt</p><p>Veröffentlicht am: 12.10.2026</p><p>Am 27. November.</p></div>'
        items = list(parse(self.source, html))
        self.assertEqual(len(items), 2)
        self.assertNotEqual(items[0]["external_id"], items[1]["external_id"])
        self.assertNotIn("Querstraße", items[0]["evidence"])
        for data in items:
            save_item(self.source, data)
            save_item(self.source, data)
        self.assertEqual(Story.objects.count(), 2)
        self.assertEqual(Revision.objects.count(), 2)
        changed = list(parse(self.source, html.replace("30. Oktober", "30. November")))[0]
        save_item(self.source, changed)
        story = Story.objects.get(external_id=changed["external_id"])
        self.assertEqual(story.revision_count, 2)
        self.assertEqual(story.revisions.count(), 2)
        self.assertIn("30. Oktober", story.revisions.first().evidence)

    def test_missing_event_year_is_not_invented(self):
        self.source.parser = "events"
        html = '<div id="dwa_event_list_wrapper"><div class="event_wrapper"><a class="event_teaser_title_link" href="/fest">Fest</a><span class="event_date">Samstag 24. April</span><span class="event_teaser">Im Dorf</span></div></div>'
        data = list(parse(self.source, html))[0]
        self.assertIsNone(data["source_date"])
        self.assertEqual(data["date_label"], "Samstag 24. April")

    def test_closure_date_in_separate_html_element(self):
        html = '<div id="content_frame"><strong>Straße gesperrt</strong><p>Veröffentlicht am: <span>12.10.2026</span></p><p>Umleitung ausgeschildert.</p></div>'
        data = list(parse(self.source, html))[0]
        self.assertEqual(data["source_date"].isoformat(), "2026-10-12")
        self.assertEqual(data["evidence"], "Umleitung ausgeschildert.")

    def test_hidden_stories_and_private_tips(self):
        data = dict(external_id="1", title="Verborgene Meldung", url=self.source.url, evidence="Intern", date_label="", source_date=None)
        save_item(self.source, data)
        story = Story.objects.get()
        story.published = False
        story.save()
        self.assertNotContains(self.client.get("/"), story.title)
        self.assertEqual(self.client.get(story.get_absolute_url()).status_code, 404)
        response = self.client.post("/hinweis/", {"text": "Neues Karussell", "url": "https://example.org", "contact": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Tip.objects.count(), 1)
        self.assertNotContains(self.client.get("/"), "Neues Karussell")
        self.assertEqual(self.client.get("/redaktion/").status_code, 302)

    def test_csrf_is_required_for_tips(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post("/hinweis/", {"text": "Spam"}).status_code, 403)

    def test_public_pages_and_feed(self):
        for path in ["/", "/quellen/", "/hinweis/", "/healthz", "/feed.xml"]:
            self.assertEqual(self.client.get(path).status_code, 200)
