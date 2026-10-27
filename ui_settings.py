"""THEOLOGICUS-AI Settings Modal - comprehensive settings dialog."""
from pathlib import Path
import json
import os
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QGroupBox, QFormLayout, QSpinBox, QComboBox, QFrame,
    QFileDialog, QColorDialog, QApplication, QWidget
)

# Import color constants from ui module
sys.path.insert(0, str(Path(__file__).parent))
try:
    from ui import C, DEFAULT_UI_COLOR, _read_full_config, API_FILE
except ImportError:
    # Fallback if ui not available
    class C:
        PRI = "#00d4ff"
        PRI_DIM = "#0088aa"
        PRI_GHO = "#00d4ff22"
        TEXT = "#e0f0ff"
        TEXT_MED = "#88aacc"
        TEXT_DIM = "#557799"
        BORDER = "#1a3a4a"
        BORDER_B = "#2a5a6a"
        BG = "#00060a"
    DEFAULT_UI_COLOR = "#00d4ff"
    def _read_full_config(): return {}
    API_FILE = Path("/tmp/api_keys.json")


class SettingsModal(QDialog):
    """Centralized settings dialog for THEOLOGICUS-AI."""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {C.BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
            QGroupBox {{
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: bold;
                color: {C.PRI};
                font-family: 'Courier New';
                font-size: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLineEdit, QComboBox {{
                background: #000d12;
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 4px 8px;
                font-family: 'Courier New';
                font-size: 10px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {C.PRI};
            }}
            QLabel {{
                color: {C.TEXT_DIM};
                font-family: 'Courier New';
                font-size: 9px;
            }}
        """)
        self.setWindowTitle("⚙  SETTINGS — THEOLOGICUS-AI")
        self.setFixedSize(680, 620)

        self._cfg = _read_full_config()
        self._build_ui()
        self._load_config()

    def _line_edit_style(self) -> str:
        return (f"QLineEdit {{ background: #000d12; color: {C.TEXT}; "
                f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
                f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

    def _btn_style(self, primary: bool = False) -> str:
        if primary:
            return (f"QPushButton {{ background: transparent; color: {C.PRI}; "
                    f"border: 1px solid {C.PRI_DIM}; border-radius: 4px; "
                    f"padding: 6px 16px; font-family: 'Courier New'; font-size: 10px; }}"
                    f"QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}")
        return (f"QPushButton {{ background: transparent; color: {C.TEXT_MED}; "
                f"border: 1px solid {C.BORDER}; border-radius: 4px; "
                f"padding: 6px 16px; font-family: 'Courier New'; font-size: 10px; }}"
                f"QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}")

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(16, 12, 16, 12)
        main_lay.setSpacing(8)

        # Header
        hdr = QLabel("⚙  SETTINGS")
        hdr.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        main_lay.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        main_lay.addWidget(sep)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        form = QVBoxLayout(content)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(10)

        # ── API Keys ────────────────────────────────────────────────────────
        api_grp = QGroupBox("🔑  API KEYS")
        api_lay = QFormLayout(api_grp)
        api_lay.setSpacing(6)
        api_lay.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._gemini_key = QLineEdit()
        self._gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key.setFixedHeight(26)
        api_lay.addRow("GEMINI API KEY:", self._gemini_key)

        self._mistral_key = QLineEdit()
        self._mistral_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._mistral_key.setFixedHeight(26)
        api_lay.addRow("MISTRAL API KEY:", self._mistral_key)

        self._mem0_key = QLineEdit()
        self._mem0_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._mem0_key.setFixedHeight(26)
        api_lay.addRow("MEM0 API KEY:", self._mem0_key)

        form.addWidget(api_grp)

        # ── Assistant Config ────────────────────────────────────────────────
        asst_grp = QGroupBox("🤖  ASSISTANT")
        asst_lay = QFormLayout(asst_grp)
        asst_lay.setSpacing(6)

        self._asst_name = QLineEdit()
        self._asst_name.setFixedHeight(26)
        asst_lay.addRow("ASSISTANT NAME:", self._asst_name)

        self._user_name = QLineEdit()
        self._user_name.setPlaceholderText("e.g. Ambassadeur")
        self._user_name.setFixedHeight(26)
        asst_lay.addRow("YOUR NAME:", self._user_name)

        self._llm_provider = QComboBox()
        self._llm_provider.addItems(["auto", "gemini", "mistral"])
        self._llm_provider.setFixedHeight(26)
        asst_lay.addRow("LLM PROVIDER:", self._llm_provider)

        form.addWidget(asst_grp)

        # ── UI Settings ─────────────────────────────────────────────────────
        ui_grp = QGroupBox("🎨  INTERFACE")
        ui_lay = QFormLayout(ui_grp)
        ui_lay.setSpacing(6)

        color_lay = QHBoxLayout()
        self._ui_color = QLineEdit("#00d4ff")
        self._ui_color.setFixedWidth(90)
        self._ui_color.setFixedHeight(26)
        color_lay.addWidget(self._ui_color)
        btn_clr = QPushButton("BROWSE")
        btn_clr.setFixedHeight(26)
        btn_clr.clicked.connect(self._pick_color)
        color_lay.addWidget(btn_clr)
        color_lay.addStretch()
        ui_lay.addRow("UI COLOR:", color_lay)

        self._hud_style = QComboBox()
        self._hud_style.addItems(["core", "minimal", "full"])
        self._hud_style.setFixedHeight(26)
        ui_lay.addRow("HUD STYLE:", self._hud_style)

        form.addWidget(ui_grp)

        # ── Theology Brain ──────────────────────────────────────────────────
        theo_grp = QGroupBox("📖  THEOLOGY BRAIN")
        theo_lay = QFormLayout(theo_grp)
        theo_lay.setSpacing(6)

        vault_lay = QHBoxLayout()
        self._vault_path = QLineEdit()
        self._vault_path.setFixedHeight(26)
        vault_lay.addWidget(self._vault_path)
        btn_vault = QPushButton("BROWSE")
        btn_vault.setFixedHeight(26)
        btn_vault.clicked.connect(self._pick_vault)
        vault_lay.addWidget(btn_vault)
        theo_lay.addRow("VAULT PATH:", vault_lay)

        self._auto_research = QComboBox()
        self._auto_research.addItems(["Enabled", "Disabled"])
        self._auto_research.setFixedHeight(26)
        theo_lay.addRow("AUTO RESEARCH:", self._auto_research)

        self._max_per_day = QSpinBox()
        self._max_per_day.setRange(1, 50)
        self._max_per_day.setFixedHeight(26)
        theo_lay.addRow("MAX/DAY:", self._max_per_day)

        self._cooldown = QSpinBox()
        self._cooldown.setRange(60, 7200)
        self._cooldown.setSingleStep(300)
        self._cooldown.setFixedHeight(26)
        theo_lay.addRow("COOLDOWN (s):", self._cooldown)

        self._research_depth = QComboBox()
        self._research_depth.addItems(["Quick", "Standard", "Deep"])
        self._research_depth.setFixedHeight(26)
        theo_lay.addRow("DEPTH:", self._research_depth)

        self._research_lang = QComboBox()
        self._research_lang.addItems(["Auto", "French", "English", "Arabic"])
        self._research_lang.setFixedHeight(26)
        theo_lay.addRow("LANGUAGE:", self._research_lang)

        form.addWidget(theo_grp)

        # ── Memory ──────────────────────────────────────────────────────────
        mem_grp = QGroupBox("💾  MEMORY / MEM0")
        mem_lay = QFormLayout(mem_grp)
        mem_lay.setSpacing(6)

        self._mem0_user = QLineEdit()
        self._mem0_user.setFixedHeight(26)
        mem_lay.addRow("USER ID:", self._mem0_user)

        self._mem0_host = QLineEdit("https://api.mem0.ai")
        self._mem0_host.setFixedHeight(26)
        mem_lay.addRow("HOST:", self._mem0_host)

        form.addWidget(mem_grp)

        # ── Elasticsearch ───────────────────────────────────────────────────
        es_grp = QGroupBox("🔍  ELASTICSEARCH / XERJ")
        es_lay = QFormLayout(es_grp)
        es_lay.setSpacing(6)

        self._xerj_url = QLineEdit("http://localhost:9200")
        self._xerj_url.setFixedHeight(26)
        es_lay.addRow("URL:", self._xerj_url)

        self._xerj_ns = QLineEdit()
        self._xerj_ns.setFixedHeight(26)
        es_lay.addRow("NAMESPACE:", self._xerj_ns)

        form.addWidget(es_grp)

        form.addStretch()
        scroll.setWidget(content)
        main_lay.addWidget(scroll)

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(12)

        save_btn = QPushButton("💾  SAVE")
        save_btn.setFixedHeight(30)
        save_btn.setStyleSheet(self._btn_style(True))
        save_btn.clicked.connect(self._save_settings)
        btn_lay.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(30)
        cancel_btn.setStyleSheet(self._btn_style(False))
        cancel_btn.clicked.connect(self.close)
        btn_lay.addWidget(cancel_btn)

        btn_lay.addStretch()
        main_lay.addLayout(btn_lay)

    def _pick_color(self):
        c = QColorDialog.getColor(Qt.GlobalColor.blue, self, "Select UI Color")
        if c.isValid():
            self._ui_color.setText(f"#{c.red():02x}{c.green():02x}{c.blue():02x}")

    def _pick_vault(self):
        path = QFileDialog.getExistingDirectory(self, "Select Theology Vault")
        if path:
            self._vault_path.setText(path)

    def _load_config(self):
        cfg = self._cfg
        self._gemini_key.setText(cfg.get("gemini_api_key", ""))
        self._mistral_key.setText(cfg.get("mistral_api_key", ""))
        self._mem0_key.setText(cfg.get("mem0_api_key", ""))

        self._asst_name.setText(cfg.get("assistant_name", "Theologicus"))
        self._user_name.setText(cfg.get("user_name", ""))
        self._llm_provider.setCurrentText(cfg.get("llm_provider", "auto"))

        self._ui_color.setText(cfg.get("ui_color", "#00d4ff"))
        self._hud_style.setCurrentText(cfg.get("hud_style", "core"))

        theo = cfg.get("plugin_config", {}).get("theology_brain", {})
        self._vault_path.setText(theo.get("theology_vault_path", ""))
        self._auto_research.setCurrentText(
            "Enabled" if theo.get("theology_auto_research", True) else "Disabled"
        )
        self._max_per_day.setValue(int(theo.get("theology_auto_research_max_per_day", 3)))
        self._cooldown.setValue(int(theo.get("theology_auto_research_cooldown", 1800)))
        self._research_depth.setCurrentText(theo.get("theology_auto_research_depth", "Standard"))
        self._research_lang.setCurrentText(theo.get("theology_auto_research_language", "Auto").capitalize())

        mem0 = cfg.get("plugin_config", {}).get("mem0", {})
        self._mem0_user.setText(mem0.get("user_id", "markliv"))
        self._mem0_host.setText(mem0.get("host", "https://api.mem0.ai"))

        self._xerj_url.setText(cfg.get("xerj_url", "http://localhost:9200"))
        self._xerj_ns.setText(cfg.get("xerj_memory_namespace", "markliv"))

    def _save_settings(self):
        try:
            data = _read_full_config()

            # API Keys
            data["gemini_api_key"] = self._gemini_key.text().strip()
            data["mistral_api_key"] = self._mistral_key.text().strip()
            data["mem0_api_key"] = self._mem0_key.text().strip()

            # Assistant
            data["assistant_name"] = self._asst_name.text().strip() or "Theologicus"
            data["user_name"] = self._user_name.text().strip()
            data["llm_provider"] = self._llm_provider.currentText()

            # UI
            data["ui_color"] = self._ui_color.text().strip() or DEFAULT_UI_COLOR
            data["hud_style"] = self._hud_style.currentText()

            # Theology
            if "plugin_config" not in data:
                data["plugin_config"] = {}
            if "theology_brain" not in data["plugin_config"]:
                data["plugin_config"]["theology_brain"] = {}
            theo = data["plugin_config"]["theology_brain"]
            theo["theology_vault_path"] = self._vault_path.text().strip()
            theo["theology_auto_research"] = self._auto_research.currentText() == "Enabled"
            theo["theology_auto_research_max_per_day"] = str(self._max_per_day.value())
            theo["theology_auto_research_cooldown"] = str(self._cooldown.value())
            theo["theology_auto_research_depth"] = self._research_depth.currentText().lower()
            theo["theology_auto_research_language"] = self._research_lang.currentText().lower()

            # Mem0
            if "mem0" not in data["plugin_config"]:
                data["plugin_config"]["mem0"] = {}
            mem0 = data["plugin_config"]["mem0"]
            mem0["api_key"] = self._mem0_key.text().strip()
            mem0["user_id"] = self._mem0_user.text().strip()
            mem0["host"] = self._mem0_host.text().strip() or "https://api.mem0.ai"

            # Xerj
            data["xerj_url"] = self._xerj_url.text().strip()
            data["xerj_memory_namespace"] = self._xerj_ns.text().strip()

            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            # Restrict permissions: only owner can read/write (prevents credential leakage)
            os.chmod(API_FILE, 0o600)
            self.settings_changed.emit()
            self.close()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
