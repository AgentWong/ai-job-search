PYTHON := .venv/bin/python

.PHONY: curate curate-dry ats-search rebuild-companion

curate:
	$(PYTHON) -m scripts.curation_appender.cli --verbose

curate-dry:
	$(PYTHON) -m scripts.curation_appender.cli --verbose --dry-run

ats-search:
	$(PYTHON) -m scripts.ats_scraper.cli --verbose --posted-within past_week

ats-search-today:
	$(PYTHON) -m scripts.ats_scraper.cli --verbose --posted-within past_day

rebuild-companion:
	$(PYTHON) -m scripts.curation_appender.rebuild_companion --verbose
