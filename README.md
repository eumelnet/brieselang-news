# Brieselang News

Self-hosted local news radar for Brieselang, Bredow and Zeestow.

Pilot: **https://brieselang-news.e.mcsps.de** · Kubernetes namespace `brieselang-news`.

## Implemented

- Django website, search/category filters, individual source links, RSS `/feed.xml`.
- Four real source adapters: municipal news, events, closures and Café Naschkatze's opening listing.
- Hourly collection, robots.txt checks, source health at `/quellen/`, database advisory lock.
- Per-item change detection, immutable extracted text revisions, idempotent imports.
- Private tip form with CSRF, honeypot and session-based throttling; Django editorial UI at `/redaktion/`.
- PostgreSQL with persistent storage and daily validated dumps (14 days retention).
- Tests and container build in GitHub Actions; images tagged with full Git commit SHA.

The pilot publishes **headlines and source links**, preserving extracted source text internally for comparison. It does not generate facts or republish full articles. Dates without a year remain as stated by the source. Initial imports retain original publication dates. Discovery/search API, LLM summaries, PDF/OCR and a curated birthday calendar are not yet configured. The four-source pilot is a working baseline for evaluating collection quality before expanding coverage.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collect_news
DEBUG=true .venv/bin/python manage.py runserver
.venv/bin/python manage.py test
```

SQLite is used only for local development. Production selects PostgreSQL via `DB_HOST`.

## Container build

Push to `main` runs tests and publishes `ghcr.io/eumelnet/brieselang-news:<full-sha>` and `:main`. No local Docker is needed. The GHCR package must be publicly pullable or an imagePullSecret must be configured. Builds do not have cluster credentials.

## Deployment

Prerequisites: ingress class `nginx`, ClusterIssuer `letsencrypt`, StorageClass `local-path`, DNS pointing to ingress.

Create namespace and a `news-secrets` Secret containing `SECRET_KEY`, `POSTGRES_DB=news`, `POSTGRES_USER=news`, `POSTGRES_PASSWORD`. Generate random values; do not commit them. Keep a secure external recovery copy.

Set `k8s/kustomization.yaml`'s image tag to the built full commit SHA, then:

```sh
kubectl apply -k k8s
kubectl -n brieselang-news rollout status deployment/web
kubectl -n brieselang-news create job --from=cronjob/collector collector-initial
kubectl -n brieselang-news logs job/collector-initial
kubectl -n brieselang-news exec -it deployment/web -- python manage.py createsuperuser
```

Editorial credentials are created interactively, not included in images or manifests. Add/disable sources in the editorial UI; each new source format needs a matching adapter and an allowed hostname in `news/collect.py`.

## Operation and recovery

```sh
kubectl -n brieselang-news get pods,cronjobs,jobs,ingress,certificate
kubectl -n brieselang-news logs deployment/web --since=30m
kubectl -n brieselang-news create job --from=cronjob/database-backup backup-manual
```

Source health is public at `/quellen/`; HTTP readiness at `/healthz` verifies the database. Collector errors fail the Job and remain visible per source. A missing source item does not imply cancellation or reopening. A closure's source publication date plus same-day ordinal is its pilot identity; reordering same-day entries can need editorial correction. Cross-source semantic merging is deferred.

Backups are custom-format `pg_dump` files on the `backups` PVC. Restore into an empty database with `pg_restore -U news -d news <file>`. Verify restore separately before replacing data. Local-path database and backup volumes share the node failure domain; copy dumps to your existing off-node backup system for disaster recovery. No HA is implied by this single-node pilot.

Before opening as a regular public service, fill in the operator's actual imprint/contact details and retention policy. The pilot currently identifies itself as such and links to this project for contact.
