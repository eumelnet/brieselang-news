from django.contrib import admin
from django.urls import path
from news import views

urlpatterns = [path("", views.index, name="index"), path("meldung/<int:pk>/", views.detail, name="detail"), path("quellen/", views.sources, name="sources"), path("hinweis/", views.tip, name="tip"), path("feed.xml", views.NewsFeed()), path("healthz", views.health), path("redaktion/", admin.site.urls)]
