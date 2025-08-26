# features/dicom_import/gui/doctor_selection_dialog.py
"""
Enhanced Doctor Selection Dialog with dynamic tag management and ALL User functionality
"""
import json
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, 
    QLineEdit, QMessageBox, QFrame, QGroupBox, QCheckBox, QTextEdit,
    QScrollArea, QWidget, QGridLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtGui import QFont, QPixmap, QPainter, QIcon

# Import UI constants
from core.gui.ui_constants import (
    DIALOG_TITLE_STYLE, DIALOG_SUBTITLE_STYLE, DIALOG_FRAME_STYLE,
    PRIMARY_BUTTON_STYLE, SUCCESS_BUTTON_STYLE, GRAY_BUTTON_STYLE,
    DIALOG_CANCEL_BUTTON_STYLE, GROUP_BOX_STYLE, INFO_LABEL_STYLE,
    VIEW_SELECTOR_TITLE_STYLE, ENHANCED_WORKFLOW_BADGE_STYLE,
    Colors
)

# Import session config
from core.config.sessions import get_session_manager

class DoctorTagManager:
    """Manages dynamic doctor tags stored in JSON"""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("config/doctor_tags.json")
        self.default_tags = [
            {"code": "NSY", "name": "Nasywa Kamila", "color": "#4e73ff"},
            {"code": "ATL", "name": "Athila Ramdani Saputra", "color": "#28a745"},
            {"code": "NBL", "name": "Nabila Putri Azhari", "color": "#dc3545"},
            {"code": "ALL", "name": "Shared Access (All Users)", "color": "#ffc107", "shared": True}
        ]
        self._load_tags()
    
    def _load_tags(self):
        """Load doctor tags from JSON file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tags = data.get('doctor_tags', self.default_tags)
            else:
                self.tags = self.default_tags.copy()
                self._save_tags()
        except Exception as e:
            print(f"[WARNING] Failed to load doctor tags: {e}")
            self.tags = self.default_tags.copy()
    
    def _save_tags(self):
        """Save doctor tags to JSON file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "doctor_tags": self.tags,
                "last_updated": QTimer().remainingTime()
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARNING] Failed to save doctor tags: {e}")
    
    def get_tags(self):
        """Get all doctor tags"""
        return self.tags.copy()
    
    def get_tag_codes(self):
        """Get list of tag codes"""
        return [tag['code'] for tag in self.tags]
    
    def get_tag_by_code(self, code: str):
        """Get tag by code"""
        for tag in self.tags:
            if tag['code'] == code:
                return tag
        return None
    
    def add_tag(self, code: str, name: str, color: str = "#6c757d", shared: bool = False):
        """Add new doctor tag"""
        if any(tag['code'] == code for tag in self.tags):
            raise ValueError(f"Tag with code '{code}' already exists")
        
        new_tag = {
            "code": code,
            "name": name,
            "color": color,
            "shared": shared
        }
        self.tags.append(new_tag)
        self._save_tags()
        return new_tag
    
    def remove_tag(self, code: str):
        """Remove doctor tag"""
        if code == "ALL":
            raise ValueError("Cannot remove ALL user tag")
        
        self.tags = [tag for tag in self.tags if tag['code'] != code]
        self._save_tags()
    
    def update_tag(self, code: str, name: str = None, color: str = None):
        """Update existing tag"""
        for tag in self.tags:
            if tag['code'] == code:
                if name is not None:
                    tag['name'] = name
                if color is not None:
                    tag['color'] = color
                break
        self._save_tags()

class DoctorTagWidget(QFrame):
    """Individual doctor tag widget with selection capability"""
    
    tag_selected = Signal(dict)
    tag_updated = Signal()  # Signal for when tag is updated
    
    def __init__(self, tag_data: dict, parent=None):
        super().__init__(parent)
        self.tag_data = tag_data
        self.selected = False
        self.parent_dialog = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the tag widget UI - FIXED layout"""
        self.setFrameStyle(QFrame.Box)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Header with code and color indicator
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Color indicator
        color_indicator = QLabel()
        color_indicator.setFixedSize(12, 12)
        color_indicator.setStyleSheet(f"""
            QLabel {{
                background: {self.tag_data.get('color', Colors.SECONDARY)};
                border-radius: 6px;
                border: 1px solid #dee2e6;
            }}
        """)
        header_layout.addWidget(color_indicator)
        
        # Tag code
        code_label = QLabel(self.tag_data['code'])
        code_label.setFont(QFont("Arial", 14, QFont.Bold))
        code_label.setStyleSheet(f"""
            QLabel {{
                color: {self.tag_data.get('color', Colors.SECONDARY)};
                font-weight: bold;
            }}
        """)
        header_layout.addWidget(code_label)
        
        # Shared badge for ALL user
        if self.tag_data.get('shared', False):
            shared_badge = QLabel("SHARED")
            shared_badge.setStyleSheet("""
                QLabel {
                    background: #4e73ff;
                    color: white;
                    border-radius: 8px;
                    padding: 2px 8px;
                    font-size: 9px;
                    font-weight: bold;
                }
            """)
            header_layout.addWidget(shared_badge)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Doctor name
        name_label = QLabel(self.tag_data['name'])
        name_label.setWordWrap(True)
        name_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 11px;
                line-height: 1.3;
                margin: 4px 0px;
            }
        """)
        layout.addWidget(name_label)
        
        # Edit button for non-shared tags
        if not self.tag_data.get('shared', False):
            edit_btn = QPushButton("✏️ Edit")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10px;
                    color: #495057;
                }
                QPushButton:hover {
                    background: #e9ecef;
                    border-color: #adb5bd;
                }
            """)
            edit_btn.clicked.connect(self._edit_tag)
            layout.addWidget(edit_btn)
        
        # Set widget properties
        self.setMinimumSize(180, 120)
        self.setMaximumSize(220, 140)
        self.setCursor(Qt.PointingHandCursor)
        
        # Apply initial style
        self._apply_style(selected=False)
    
    def _apply_style(self, selected: bool):
        """Apply style based on selection state"""
        color = self.tag_data.get('color', Colors.SECONDARY)
        
        if selected:
            self.setStyleSheet(f"""
                QFrame {{
                    border: 3px solid {color};
                    border-radius: 8px;
                    background: {color}20;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px solid {color};
                    border-radius: 8px;
                    background: white;
                }}
                QFrame:hover {{
                    background: {color}15;
                    border-color: {color};
                }}
            """)
    
    def _edit_tag(self):
        """Edit tag name and color"""
        dialog = EditDoctorDialog(self.tag_data, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                # Update through tag manager
                tag_manager = DoctorTagManager()
                tag_manager.update_tag(
                    self.tag_data['code'], 
                    name=dialog.new_name, 
                    color=dialog.new_color
                )
                
                # Update local data
                old_name = self.tag_data['name']
                self.tag_data['name'] = dialog.new_name
                self.tag_data['color'] = dialog.new_color
                
                # Refresh parent dialog to reload all tags
                if hasattr(self.parent(), '_populate_doctor_tags'):
                    self.parent()._populate_doctor_tags()
                
                QMessageBox.information(self, "Success", 
                    f"Doctor updated successfully!\n\n"
                    f"Name: {old_name} → {dialog.new_name}\n"
                    f"Code '{self.tag_data['code']}' remains unchanged")
                    
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update doctor: {e}")
    
    def mousePressEvent(self, event):
        """Handle click to select tag"""
        if event.button() == Qt.LeftButton:
            self.set_selected(not self.selected)
            self.tag_selected.emit(self.tag_data)
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """Set selection state"""
        self.selected = selected
        self._apply_style(selected)

class AddDoctorDialog(QDialog):
    """Dialog for adding new doctor tags"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Doctor Tag")
        self.setModal(True)
        self.setFixedSize(380, 300)
        
        self.code = ""
        self.name = ""
        self.color = Colors.PRIMARY
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the add doctor dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Add New Doctor Tag")
        title.setStyleSheet(DIALOG_TITLE_STYLE)
        layout.addWidget(title)
        
        # Code input
        layout.addWidget(QLabel("Doctor Code (2-4 characters):"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("e.g., EMA, JDN")
        self.code_input.setMaxLength(4)
        layout.addWidget(self.code_input)
        
        # Name input
        layout.addWidget(QLabel("Doctor Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Emergency Medicine Associates")
        layout.addWidget(self.name_input)
        
        # Color selection
        layout.addWidget(QLabel("Color:"))
        color_layout = QHBoxLayout()
        
        self.color_buttons = []
        colors = [Colors.PRIMARY, Colors.SUCCESS, Colors.WARNING, Colors.DANGER, 
                 "#9C27B0", "#FF5722", "#607D8B", Colors.SECONDARY]
        
        for color in colors:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 2px solid #dee2e6;
                    border-radius: 14px;
                }}
                QPushButton:checked {{
                    border: 3px solid #000;
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=color: self._select_color(c))
            self.color_buttons.append(btn)
            color_layout.addWidget(btn)
        
        # Set default color
        self.color_buttons[0].setChecked(True)
        self.color = colors[0]
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(DIALOG_CANCEL_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        add_btn = QPushButton("Add Doctor")
        add_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        add_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(add_btn)
        
        layout.addLayout(button_layout)
    
    def _select_color(self, color: str):
        """Select color for the new tag"""
        self.color = color
        for btn in self.color_buttons:
            btn.setChecked(False)
        
        # Find and check the clicked button
        for btn in self.color_buttons:
            if btn.styleSheet().find(color) != -1:
                btn.setChecked(True)
                break
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        self.code = self.code_input.text().strip().upper()
        self.name = self.name_input.text().strip()
        
        if not self.code or len(self.code) < 2:
            QMessageBox.warning(self, "Invalid Input", "Doctor code must be at least 2 characters")
            return
        
        if not self.name:
            QMessageBox.warning(self, "Invalid Input", "Doctor name cannot be empty")
            return
        
        self.accept()

class EditDoctorDialog(QDialog):
    """Dialog for editing existing doctor tags"""
    
    def __init__(self, tag_data: dict, parent=None):
        super().__init__(parent)
        self.tag_data = tag_data
        self.new_name = tag_data['name']
        self.new_color = tag_data['color']
        
        self.setWindowTitle("Edit Doctor")
        self.setModal(True)
        self.setFixedSize(500, 400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the edit dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel(f"Edit Doctor: {self.tag_data['code']}")
        title.setStyleSheet(DIALOG_TITLE_STYLE)
        layout.addWidget(title)
        
        # Code info (read-only)
        layout.addWidget(QLabel("Doctor Code (cannot be changed):"))
        code_display = QLineEdit(self.tag_data['code'])
        code_display.setReadOnly(True)
        code_display.setStyleSheet("background: #f8f9fa; color: #6c757d;")
        layout.addWidget(code_display)
        
        # Name input
        layout.addWidget(QLabel("Doctor Name:"))
        self.name_input = QLineEdit(self.tag_data['name'])
        self.name_input.setPlaceholderText("Enter doctor name")
        layout.addWidget(self.name_input)
        
        # Color selection
        layout.addWidget(QLabel("Color:"))
        color_layout = QHBoxLayout()
        
        self.color_buttons = []
        colors = [Colors.PRIMARY, Colors.SUCCESS, Colors.WARNING, Colors.DANGER, 
                 "#9C27B0", "#FF5722", "#607D8B", Colors.SECONDARY]
        
        for color in colors:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 2px solid #dee2e6;
                    border-radius: 14px;
                }}
                QPushButton:checked {{
                    border: 3px solid #000;
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=color: self._select_color(c))
            self.color_buttons.append(btn)
            color_layout.addWidget(btn)
            
            # Check current color
            if color == self.tag_data['color']:
                btn.setChecked(True)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(DIALOG_CANCEL_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        save_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _select_color(self, color: str):
        """Select color for the tag"""
        self.new_color = color
        for btn in self.color_buttons:
            btn.setChecked(False)
        
        # Find and check the clicked button
        for btn in self.color_buttons:
            if btn.styleSheet().find(color) != -1:
                btn.setChecked(True)
                break
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        self.new_name = self.name_input.text().strip()
        
        if not self.new_name:
            QMessageBox.warning(self, "Invalid Input", "Doctor name cannot be empty")
            return
        
        self.accept()

class DoctorSelectionDialog(QDialog):
    """
    Enhanced dialog for doctor selection with dynamic tag management and ALL User functionality
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TELPLASTINA - Doctor Selection") 
        self.setModal(True)
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        self.setSizeGripEnabled(True)
        # Remove close button
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint)
        
        self.selected_doctor_id: str = None
        self.selected_modality: str = "Planar"
        self.selected_tag_data: dict = None
        
        self.session_manager = get_session_manager()
        self.tag_manager = DoctorTagManager()
        self.tag_widgets = []
        
        self._setup_ui()
        self._load_last_session()
    
    def _setup_ui(self):
        """Setup the main dialog UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_layout = QVBoxLayout()
        
        title = QLabel("TELPLASTINA")
        title.setStyleSheet(VIEW_SELECTOR_TITLE_STYLE)
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title)
        
        subtitle = QLabel("Telkom Enhanced Planar Scintigraphy Analysis")
        subtitle.setStyleSheet(DIALOG_SUBTITLE_STYLE + "font-style: italic; margin-bottom: 8px;")
        subtitle.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(subtitle)
        
        #   NEW: Add description
        description = QLabel("Advanced AI-powered bone scan metastasis detection and analysis platform")
        description.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 11px;
                font-style: italic;
                margin-bottom: 16px;
            }
        """)
        description.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(description)
        
        main_layout.addLayout(header_layout)
        
        # Main content in scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Doctor selection section
        doctor_group = QGroupBox("👨‍⚕️ Select Doctor Code")
        doctor_group.setStyleSheet(GROUP_BOX_STYLE)
        doctor_layout = QVBoxLayout(doctor_group)
        
        # Tags grid
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        self.tags_layout.setSpacing(12)
        self.tags_layout.setContentsMargins(10, 10, 10, 10)
        
        self._populate_doctor_tags()
        
        doctor_layout.addWidget(self.tags_widget)
        
        # Add doctor button
        add_doctor_layout = QHBoxLayout()
        add_doctor_btn = QPushButton("➕ Add New Doctor")
        add_doctor_btn.setStyleSheet(GRAY_BUTTON_STYLE)
        add_doctor_btn.clicked.connect(self._add_new_doctor)
        add_doctor_layout.addWidget(add_doctor_btn)
        add_doctor_layout.addStretch()
        
        doctor_layout.addLayout(add_doctor_layout)
        scroll_layout.addWidget(doctor_group)
        
        # Modality info (Planar only)
        modality_group = QGroupBox("🔬 Image Modality")
        modality_group.setStyleSheet(GROUP_BOX_STYLE)
        modality_layout = QVBoxLayout(modality_group)
        
        modality_group = QGroupBox("🔬 Analysis Modality")
        modality_group.setStyleSheet(GROUP_BOX_STYLE)
        modality_layout = QVBoxLayout(modality_group)

        planar_info = QLabel("🩻 Planar Bone Scintigraphy - Metastasis Detection")
        planar_info.setStyleSheet(f"""
            QLabel {{
                background: {Colors.SUCCESS}20;
                border: 2px solid {Colors.SUCCESS};
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                color: {Colors.SUCCESS};
            }}
        """)
        planar_info.setAlignment(Qt.AlignCenter)
        modality_layout.addWidget(planar_info)

        modality_desc = QLabel("AI-powered bone scan analysis for automated metastasis detection and BSI quantification")
        modality_desc.setStyleSheet(INFO_LABEL_STYLE)
        modality_layout.addWidget(modality_desc)
        
        scroll_layout.addWidget(modality_group)
        
        # Selected info
        self.info_group = QGroupBox("ℹ️ Selection Info")
        self.info_group.setStyleSheet(GROUP_BOX_STYLE)
        info_layout = QVBoxLayout(self.info_group)
        
        self.info_label = QLabel("Please select a doctor code to continue")
        self.info_label.setStyleSheet(INFO_LABEL_STYLE)
        info_layout.addWidget(self.info_label)
        
        scroll_layout.addWidget(self.info_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        # Exit button
        exit_btn = QPushButton("🚪 Exit Application")
        exit_btn.setStyleSheet(DIALOG_CANCEL_BUTTON_STYLE)
        exit_btn.clicked.connect(self.reject)
        button_layout.addWidget(exit_btn)
        
        button_layout.addStretch()
        
        # Start button
        self.start_btn = QPushButton("🚀 Start Analysis Session")
        self.start_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.start_btn)
        
        main_layout.addLayout(button_layout)
    
    def _populate_doctor_tags(self):
        """Populate doctor tags from the tag manager"""
        # Clear existing widgets
        for widget in self.tag_widgets:
            widget.deleteLater()
        self.tag_widgets.clear()
        
        # Clear layout
        while self.tags_layout.count():
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Sort tags: ALL first, then others
        all_tags = self.tag_manager.get_tags()
        shared_tags = [tag for tag in all_tags if tag.get('shared', False)]
        individual_tags = [tag for tag in all_tags if not tag.get('shared', False)]
        sorted_tags = shared_tags + individual_tags
        
        cols = 4  # 4 columns for better layout
        
        for i, tag_data in enumerate(sorted_tags):
            row = i // cols
            col = i % cols
            
            tag_widget = DoctorTagWidget(tag_data, self)
            tag_widget.tag_selected.connect(self._on_tag_selected)
            self.tag_widgets.append(tag_widget)
            
            self.tags_layout.addWidget(tag_widget, row, col)
    
    def _on_tag_selected(self, tag_data: dict):
        """Handle tag selection"""
        # Deselect all other tags
        for widget in self.tag_widgets:
            if widget.tag_data['code'] != tag_data['code']:
                widget.set_selected(False)
        
        self.selected_doctor_id = tag_data['code']
        self.selected_tag_data = tag_data
        
        # Update info
        if tag_data.get('shared', False):
            info_text = f"""
            <b>Selected:</b> {tag_data['code']} - {tag_data['name']}<br>
            <b>Mode:</b> Shared Access (All Users)<br>
            <b>Data Path:</b> data/PLANAR/ALL/<br>
            <b>Description:</b> This is a shared workspace where all users can access and edit patient data collaboratively.
            """
        else:
            info_text = f"""
            <b>Selected:</b> {tag_data['code']} - {tag_data['name']}<br>
            <b>Mode:</b> Individual User Access<br>
            <b>Data Path:</b> data/PLANAR/{tag_data['code']}/<br>
            <b>Description:</b> This is your personal workspace for patient data analysis.
            """
        
        self.info_label.setText(info_text)
        self.info_label.setStyleSheet(f"""
            QLabel {{
                background: {tag_data.get('color', Colors.SECONDARY)}15;
                border: 2px solid {tag_data.get('color', Colors.SECONDARY)};
                border-radius: 6px;
                padding: 12px;
                font-size: 12px;
                color: #495057;
            }}
        """)
        
        self.start_btn.setEnabled(True)
    
    def _add_new_doctor(self):
        """Open dialog to add new doctor tag"""
        dialog = AddDoctorDialog(self)
        if dialog.exec():
            try:
                new_tag = self.tag_manager.add_tag(
                    dialog.code, 
                    dialog.name, 
                    dialog.color
                )
                self._populate_doctor_tags()
                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Doctor tag '{new_tag['code']}' added successfully!"
                )
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
    
    def _load_last_session(self):
        """Load and select last used session if enabled"""
        if self.session_manager.get_session_config("remember_last_session", True):
            last_session = self.session_manager.get_last_session()
            if last_session:
                session_code = last_session.get("session_code")
                if session_code:
                    # Find and select the corresponding tag widget
                    for widget in self.tag_widgets:
                        if widget.tag_data['code'] == session_code:
                            widget.set_selected(True)
                            self._on_tag_selected(widget.tag_data)
                            break
    
    def accept(self):
        """Create session and accept dialog"""
        if not self.selected_doctor_id:
            QMessageBox.warning(self, "No Selection", "Please select a doctor code")
            return
        
        try:
            # Create session using session manager
            session = self.session_manager.create_session(
                self.selected_doctor_id,
                self.selected_modality,
                user_data=self.selected_tag_data
            )
            print(f"[SESSION] Created: {session['session_id']}")
            super().accept()
            
        except Exception as e:
            print(f"[ERROR] Failed to create session: {e}")
            QMessageBox.critical(self, "Session Error", f"Failed to create session: {e}")