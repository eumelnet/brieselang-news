from django.contrib import admin
from .models import Source, Story, Revision, Tip

admin.site.site_header = "Brieselang News · Redaktion"
admin.site.site_title = "Brieselang News"


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "last_success", "item_count", "last_error"]


class RevisionInline(admin.TabularInline):
    model = Revision
    extra = 0
    can_delete = False
    readonly_fields = ["captured_at", "title", "evidence", "fingerprint"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "source_date", "published", "revision_count"]
    list_filter = ["category", "published", "source"]
    search_fields = ["title", "evidence"]
    readonly_fields = ["first_seen", "last_seen", "updated_at", "fingerprint", "revision_count"]
    inlines = [RevisionInline]


@admin.register(Tip)
class TipAdmin(admin.ModelAdmin):
    list_display = ["__str__", "created_at", "status"]
    list_filter = ["status"]
