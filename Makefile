.PHONY: setup install dev test lint lint-fix typecheck clean run help

help:
	@echo "AI Model Scanner - Makefile Commands"
	@echo ""
	@echo "  make setup     - Create virtual environment and install dependencies"
	@echo "  make install   - Install the package in editable mode"
	@echo "  make dev       - Install package with all dev dependencies"
	@echo "  make test      - Run tests with coverage"
	@echo "  make lint      - Check code with ruff"
	@echo "  make lint-fix  - Auto-fix lint issues with ruff"
	@echo "  make typecheck - Run mypy type checker (if installed)"
	@echo "  make clean     - Remove build artifacts (prompts before deleting)"
	@echo "  make run       - Run a basic scan (assumes venv is active)"
	@echo ""

setup:
	@echo "🚀 Setting up AI Model Scanner..."
	@if [ ! -d "venv" ]; then \
		python3 -m venv venv; \
		echo "✓ Virtual environment created"; \
	else \
		echo "✓ Virtual environment already exists"; \
	fi
	@echo "🔌 Activating and installing..."
	@. venv/bin/activate && pip install --upgrade pip --quiet
	@. venv/bin/activate && pip install -e ".[dev]" --quiet
	@echo "✅ Setup complete! Activate with: source venv/bin/activate"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short --cov=ai_model_scanner --cov-report=term-missing

lint:
	ruff check ai_model_scanner/ tests/

lint-fix:
	ruff check --fix ai_model_scanner/ tests/
	ruff format ai_model_scanner/ tests/

typecheck:
	@if command -v mypy > /dev/null 2>&1; then \
		mypy ai_model_scanner/ --ignore-missing-imports; \
	else \
		echo "mypy not installed. Run: pip install mypy"; \
	fi

clean:
	@echo "This will remove: venv/, build/, dist/, *.egg-info, and __pycache__ dirs."
	@printf "Type 'YES' to confirm: "; \
	read confirm; \
	if [ "$$confirm" = "YES" ]; then \
		echo "🧹 Cleaning..."; \
		rm -rf build/ dist/ *.egg-info; \
		find . -type d -name __pycache__ -not -path './venv/*' -exec rm -rf {} + 2>/dev/null || true; \
		find . -type f -name "*.pyc" -not -path './venv/*' -delete 2>/dev/null || true; \
		echo "✅ Clean complete (venv preserved — remove manually if needed)"; \
	else \
		echo "❌ Aborted."; \
	fi

run:
	ai-model-scanner scan
