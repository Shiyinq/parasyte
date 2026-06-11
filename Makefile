.PHONY: install build clean venv

VENV = .venv
VENV_PYTHON = $(VENV)/bin/python
VENV_PIP = $(VENV)/bin/pip
VENV_NUITKA = $(VENV)/bin/nuitka

$(VENV)/bin/activate:
	python3 -m venv $(VENV)

venv: $(VENV)/bin/activate

install: venv
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install zstandard nuitka

build: clean install
	$(VENV_PYTHON) update_version.py
	$(VENV_NUITKA) --standalone --assume-yes-for-downloads --output-dir=dist parasyte.py
	@echo "====================================="
	@echo "✅ Build success! The application folder is located at: ./dist/parasyte.dist"
	@echo "   To install it system-wide so you can run 'parasyte' anywhere instantly, run:"
	@echo "   make install-parasyte"

install-parasyte:
	@echo "Installing Parasyte to /usr/local/lib and /usr/local/bin..."
	sudo rm -rf /usr/local/lib/parasyte
	sudo cp -r dist/parasyte.dist /usr/local/lib/parasyte
	sudo ln -sf /usr/local/lib/parasyte/parasyte.bin /usr/local/bin/parasyte
	@echo "✅ Installed successfully! You can now type 'parasyte' from anywhere."

clean:
	rm -rf build/ dist/ __pycache__/ parasyte.build/ parasyte.dist/ parasyte.onefile-build/
	@echo "🧹 Clean successfully!"
