.PHONY: setup install test clean run help

help:
	@echo "AI Model Scanner - Makefile Commands"
	@echo ""
	@echo "  make setup    - Create virtual environment and install dependencies"
	@echo "  make install  - Install the package (assumes venv is active)"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Remove virtual environment and build artifacts"
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
	@. venv/bin/activate && pip install -e . --quiet
	@echo "✅ Setup complete! Activate with: source venv/bin/activate"

install:
	pip install -e .

test:
	pytest tests/ -v

clean:
	rm -rf venv/
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

run:
	ai-model-scanner scan
