dev:
	uvicorn server.main:app --reload

test:
	pytest

e2e:
	pytest tests/test_e2e_playwright.py

docs:
	python tools/docs/build_docs.py

docs-refresh:
	python tools/docs/build_docs.py --refresh-facts

docs-check:
	python tools/docs/check_docs.py
