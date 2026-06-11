.PHONY: install build clean venv

VENV = .venv
VENV_PYTHON = $(VENV)/bin/python
VENV_PIP = $(VENV)/bin/pip
VENV_PYINSTALLER = $(VENV)/bin/pyinstaller

$(VENV)/bin/activate:
	python3 -m venv $(VENV)

venv: $(VENV)/bin/activate

install: venv
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install pyinstaller

build: clean install
	$(VENV_PYTHON) update_version.py
	$(VENV_PYINSTALLER) --onefile --name parasyte parasyte.py
	@echo "====================================="
	@echo "✅ Build success! Binary is located at: ./dist/parasyte"
	@echo "   You can move it to /usr/local/bin/ to run it anywhere:"
	@echo "   sudo mv ./dist/parasyte /usr/local/bin/"

clean:
	rm -rf build/ dist/ __pycache__/
	@echo "🧹 Clean successfully!"
