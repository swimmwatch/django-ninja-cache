SRC_DIR=ninja_cache
TESTS_DIR=tests
PACKAGE_DIR=ninja_cache
REFERENCES_DIR=docs/references
RUNNER=uv run

mypy:
	$(RUNNER) mypy --config formatters-cfg.toml $(SRC_DIR)

flake:
	$(RUNNER) flake8 --toml-config formatters-cfg.toml $(SRC_DIR)

black:
	$(RUNNER) black --config formatters-cfg.toml $(SRC_DIR)

black-lint:
	$(RUNNER) black --check --config formatters-cfg.toml $(SRC_DIR)

isort:
	$(RUNNER) isort --settings-path formatters-cfg.toml $(SRC_DIR)

doc-lint:
	$(RUNNER) lazydocs --validate --output-path $(REFERENCES_DIR) $(PACKAGE_DIR)

format: black isort doc-lint

lint: flake mypy black-lint

lock:
	uv lock --no-update

install:
	uv install --no-root

mkdocs-serve:
	$(RUNNER) mkdocs serve

mkdocs-deploy:
	$(RUNNER) mkdocs gh-deploy --force

test:
	$(RUNNER) pytest --cov=$(PACKAGE_DIR) --cov-branch --cov-report=xml --numprocesses logical $(TESTS_DIR)

actionlint:
	docker run --rm -v $(pwd):/repo --workdir /repo rhysd/actionlint:latest -color
