.PHONY: install run test seed eval lint

install:
	pip install -r requirements.txt

run:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v

seed:
	python -m scripts.seed_kb

eval:
	python -m eval.harness

lint:
	python -m py_compile core/context.py
	python -m py_compile core/budget.py
	python -m py_compile core/tools.py
	python -m py_compile db/session.py
	python -m py_compile db/models.py
