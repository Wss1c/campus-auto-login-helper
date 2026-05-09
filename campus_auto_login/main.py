from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime

import requests

from .adapters import get_adapter
from .config_store import ConfigStore
from .diagnostic_bundle import export_diagnostic_bundle
from .detector import DetectionEngine, DetectionOutcome
from .diagnostics import diagnostic_to_text
from .lock import SingleInstanceLock
from .logger import get_logger
from .models import Credentials, DetectionResult, LoginResult, Profile, normalize_check_urls
from .paths import data_dir, logs_dir
from .service import AutoLoginService
from .startup import is_startup_enabled, set_startup
from .startup_log import log_startup_event, log_startup_exception, show_native_error
from .update_check import check_latest_release
from .utils import USER_AGENT


try:
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QColor, QCloseEvent, QIcon, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMenu,
        QMessageBox,
        QInputDialog,
        QPushButton,
        QSpinBox,
        QStackedWidget,
        QStyle,
        QSystemTrayIcon,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - exercised only without GUI deps
    QApplication = None
    QMainWindow = object
    QObject = object

    def Signal():
        return None


OPERATORS = [
    ("电信", "telecom"),
    ("移动", "cmcc"),
    ("联通", "unicom"),
    ("校园网/无后缀", ""),
    ("自定义", "__custom__"),
]


APP_STYLES = """
QMainWindow {
    background: #f5f7fb;
}
QWidget {
    color: #172033;
    font-size: 13px;
}
QLabel#pageTitle {
    font-size: 24px;
    font-weight: 700;
    color: #111827;
}
QLabel#pageSubtitle {
    color: #5b6475;
    font-size: 13px;
}
QLabel#sectionTitle {
    color: #283247;
    font-size: 14px;
    font-weight: 700;
}
QLabel#statusPill {
    background: #e8f7ef;
    color: #17623a;
    border: 1px solid #b8e4c9;
    border-radius: 8px;
    padding: 10px 12px;
    font-weight: 600;
}
QFrame#panel, QGroupBox {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 8px;
}
QGroupBox {
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #283247;
}
QLineEdit, QComboBox, QSpinBox {
    background: #ffffff;
    color: #111827;
    border: 1px solid #cfd8e6;
    border-radius: 6px;
    padding: 7px 9px;
    min-height: 22px;
}
QSpinBox::up-button, QSpinBox::down-button {
    background: #eef3fb;
    border-left: 1px solid #cfd8e6;
    width: 18px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: #dce8f8;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #2f80ed;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 6px;
    padding: 8px 14px;
    min-height: 24px;
}
QPushButton:hover {
    background: #f0f5ff;
    border-color: #9cbcf4;
}
QPushButton:pressed {
    background: #e3edff;
}
QPushButton#primaryButton {
    background: #2f80ed;
    border-color: #2f80ed;
    color: #ffffff;
    font-weight: 700;
}
QPushButton#primaryButton:hover {
    background: #1f6ed4;
}
QPushButton#successButton {
    background: #179b63;
    border-color: #179b63;
    color: #ffffff;
    font-weight: 700;
}
QPushButton#successButton:hover {
    background: #128553;
}
QPushButton#dangerButton {
    background: #ffffff;
    border-color: #f1b7b7;
    color: #b42318;
}
QPushButton#dangerButton:hover {
    background: #fff1f1;
}
QListWidget, QTextEdit {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 8px;
    padding: 8px;
}
QListWidget::item {
    padding: 9px 10px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #e8f1ff;
    color: #164a8d;
}
QTextEdit#logView {
    background: #111827;
    color: #dbeafe;
    border: 1px solid #273244;
    font-size: 12px;
}
QCheckBox {
    spacing: 8px;
}
QDialog, QMessageBox, QInputDialog {
    background: #ffffff;
    color: #111827;
}
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    color: #111827;
    background: transparent;
}
QDialog QTextEdit, QMessageBox QTextEdit, QInputDialog QTextEdit {
    background: #ffffff;
    color: #111827;
}
"""


def make_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#1976d2"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QPen(QColor("white"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawArc(17, 21, 30, 30, 35 * 16, 110 * 16)
    painter.drawArc(22, 28, 20, 20, 40 * 16, 100 * 16)
    painter.setBrush(QColor("white"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(29, 43, 7, 7)
    painter.end()
    return QIcon(pixmap)


def panel_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("panel")
    return frame


def page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageTitle")
    return label


def page_subtitle(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageSubtitle")
    label.setWordWrap(True)
    return label


class IpcBridge(QObject):
    show_requested = Signal()


class UiBridge(QObject):
    status_requested = Signal(str)


class MainWindow(QMainWindow):  # type: ignore[misc]
    def __init__(self, minimized: bool = False, recovery_window: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("校园网自动登录")
        self.resize(1180, 760)
        self.setMinimumSize(1040, 680)
        self.setStyleSheet(APP_STYLES)
        self.store = ConfigStore(data_dir())
        self.logger = get_logger(logs_dir())
        self.detector = DetectionEngine()
        self.detected_outcome: DetectionOutcome | None = None
        self.service: AutoLoginService | None = None
        self.status_messages: list[str] = []
        self.recovery_window = recovery_window
        self.close_prompt_seen = False
        self._loading_profile_options = False
        self.ui_bridge = UiBridge()
        self.ui_bridge.status_requested.connect(self._set_status)
        self.app_icon = make_app_icon()
        self.setWindowIcon(self.app_icon)
        self._last_resume_tick = time.monotonic()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_detect_page()
        self._build_credentials_page()
        self._build_dashboard_page()
        self._build_tray()

        self._load_profiles()
        if self.profiles:
            self.stack.setCurrentWidget(self.dashboard_page)
            self._select_profile(0)
        else:
            self.stack.setCurrentWidget(self.detect_page)

        if self.recovery_window:
            self._set_status("检测到已有后台实例，本窗口作为恢复窗口打开。")

        if minimized and self.profiles and self.tray_available:
            QTimer.singleShot(100, self.hide)

        self.resume_timer = QTimer(self)
        self.resume_timer.timeout.connect(self._watch_resume)
        self.resume_timer.start(15000)

    def _make_button(self, text: str, kind: str = "", icon_name: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setMinimumWidth(88)
        if kind:
            button.setObjectName(f"{kind}Button")
        if icon_name:
            standard_pixmap = getattr(QStyle.StandardPixmap, icon_name, None)
            if standard_pixmap is not None:
                button.setIcon(self.style().standardIcon(standard_pixmap))
        return button

    def _build_detect_page(self) -> None:
        self.detect_page = QWidget()
        layout = QVBoxLayout(self.detect_page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        title = page_title("校园网协议识别")
        subtitle = page_subtitle("先输入登录页网址，识别成功后再配置账号。")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("例如：http://portal.example.edu/")
        self.detect_button = self._make_button("识别协议", "primary", "SP_BrowserReload")
        self.detect_button.clicked.connect(self._detect_protocol)
        self.detect_status = QLabel("")
        self.detect_status.setObjectName("pageSubtitle")
        self.detect_status.setWordWrap(True)
        self.detect_back_dashboard_button = self._make_button("返回主界面", icon_name="SP_ArrowBack")
        self.detect_back_dashboard_button.clicked.connect(self._back_to_dashboard)
        self.detect_back_dashboard_button.setVisible(False)
        self.diagnostic_box = QTextEdit()
        self.diagnostic_box.setReadOnly(True)
        self.diagnostic_box.setVisible(False)
        self.copy_diagnostic_button = self._make_button("复制诊断信息", icon_name="SP_FileDialogDetailedView")
        self.copy_diagnostic_button.setVisible(False)
        self.copy_diagnostic_button.clicked.connect(self._copy_diagnostic)

        input_panel = panel_frame()
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(22, 20, 22, 20)
        input_layout.setSpacing(12)
        input_title = QLabel("登录页网址")
        input_title.setObjectName("sectionTitle")
        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        input_row.addWidget(self.url_input, 1)
        input_row.addWidget(self.detect_button)
        input_layout.addWidget(input_title)
        input_layout.addLayout(input_row)
        input_layout.addWidget(self.detect_status)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(input_panel)
        layout.addWidget(self.diagnostic_box)
        bottom_buttons = QHBoxLayout()
        bottom_buttons.addWidget(self.detect_back_dashboard_button)
        bottom_buttons.addStretch(1)
        bottom_buttons.addWidget(self.copy_diagnostic_button)
        layout.addLayout(bottom_buttons)
        layout.addStretch(1)
        self.stack.addWidget(self.detect_page)

    def _build_credentials_page(self) -> None:
        self.credentials_page = QWidget()
        layout = QVBoxLayout(self.credentials_page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        title = page_title("保存登录配置")
        subtitle = page_subtitle("协议已识别，现在填写账号和运营商信息。")
        self.protocol_label = QLabel("")
        self.protocol_label.setObjectName("statusPill")
        self.protocol_label.setWordWrap(True)
        self.profile_name_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.operator_combo = QComboBox()
        for label, suffix in OPERATORS:
            self.operator_combo.addItem(label, suffix)
        self.custom_suffix_input = QLineEdit()
        self.custom_suffix_input.setPlaceholderText("例如：telecom")
        self.custom_suffix_input.setEnabled(False)
        self.operator_combo.currentIndexChanged.connect(self._operator_changed)
        form_group = QGroupBox("配置内容")
        form = QFormLayout(form_group)
        form.setContentsMargins(18, 18, 18, 16)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("已识别协议", self.protocol_label)
        form.addRow("配置名称", self.profile_name_input)
        form.addRow("账号", self.username_input)
        form.addRow("密码", self.password_input)
        form.addRow("运营商", self.operator_combo)
        form.addRow("自定义后缀", self.custom_suffix_input)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.back_button = self._make_button("返回重新识别", icon_name="SP_ArrowBack")
        self.back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.detect_page))
        self.cancel_profile_button = self._make_button("返回主界面")
        self.cancel_profile_button.clicked.connect(self._back_to_dashboard)
        self.cancel_profile_button.setVisible(False)
        self.save_profile_button = self._make_button("保存配置", "success", "SP_DialogSaveButton")
        self.save_profile_button.clicked.connect(self._save_detected_profile)
        buttons.addStretch(1)
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.cancel_profile_button)
        buttons.addWidget(self.save_profile_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(form_group)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.stack.addWidget(self.credentials_page)

    def _build_dashboard_page(self) -> None:
        self.dashboard_page = QWidget()
        layout = QVBoxLayout(self.dashboard_page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        title_block.addWidget(page_title("校园网自动登录"))
        title_block.addWidget(page_subtitle("管理配置、手动登录和后台常驻。"))
        self.new_profile_button = self._make_button("新增配置", icon_name="SP_FileDialogNewFolder")
        self.new_profile_button.clicked.connect(self._start_new_profile)
        header.addLayout(title_block, 1)
        header.addWidget(self.new_profile_button, 0, Qt.AlignmentFlag.AlignTop)

        content = QHBoxLayout()
        content.setSpacing(18)
        profile_group = QGroupBox("配置档案")
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setContentsMargins(14, 18, 14, 14)
        self.profile_list = QListWidget()
        self.profile_list.setMinimumWidth(240)
        self.profile_list.setWordWrap(True)
        self.profile_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.profile_list.currentRowChanged.connect(self._select_profile)
        self.status_label = QLabel("未启动")
        self.status_label.setObjectName("statusPill")
        self.status_label.setWordWrap(True)
        self.saved_name_input = QLineEdit()
        self.saved_name_input.setPlaceholderText("配置名称")
        self.saved_name_input.returnPressed.connect(self._rename_current_profile)
        self.rename_profile_button = self._make_button("保存名称", icon_name="SP_DialogSaveButton")
        self.rename_profile_button.clicked.connect(self._rename_current_profile)
        self.resident_checkbox = QCheckBox("启动常驻")
        self.resident_checkbox.stateChanged.connect(self._resident_changed)
        self.startup_checkbox = QCheckBox("开机自启")
        self.startup_checkbox.stateChanged.connect(self._startup_changed)
        self.prevent_sleep_checkbox = QCheckBox("常驻时防止睡眠/休眠")
        self.prevent_sleep_checkbox.stateChanged.connect(self._profile_options_changed)
        self.resume_reconnect_checkbox = QCheckBox("唤醒后立即检查")
        self.resume_reconnect_checkbox.stateChanged.connect(self._profile_options_changed)
        self.check_interval_spin = QSpinBox()
        self.check_interval_spin.setRange(10, 600)
        self.check_interval_spin.setSuffix(" 秒")
        self.check_interval_spin.setMinimumWidth(104)
        self.check_interval_spin.valueChanged.connect(self._profile_options_changed)
        self.login_interval_spin = QSpinBox()
        self.login_interval_spin.setRange(1, 72)
        self.login_interval_spin.setSuffix(" 小时")
        self.login_interval_spin.setMinimumWidth(104)
        self.login_interval_spin.valueChanged.connect(self._profile_options_changed)
        self.check_urls_input = QTextEdit()
        self.check_urls_input.setPlaceholderText("每行一个检测地址")
        self.check_urls_input.setMaximumHeight(72)
        self.check_urls_input.textChanged.connect(self._profile_options_changed)
        self.login_button = self._make_button("立即登录", "primary", "SP_MediaPlay")
        self.login_button.clicked.connect(self._login_now)
        self.logout_button = self._make_button("注销", "danger", "SP_DialogDiscardButton")
        self.logout_button.clicked.connect(self._logout_now)
        self.pause_button = self._make_button("暂停", icon_name="SP_MediaPause")
        self.pause_button.clicked.connect(self._toggle_pause)
        self.check_now_button = self._make_button("检测网络", icon_name="SP_BrowserReload")
        self.check_now_button.clicked.connect(self._check_network_now)
        self.export_diag_button = self._make_button("导出诊断包", icon_name="SP_DriveHDIcon")
        self.export_diag_button.clicked.connect(self._export_diagnostics)
        self.copy_log_button = self._make_button("复制日志")
        self.copy_log_button.clicked.connect(self._copy_ui_log)
        self.clear_log_button = self._make_button("清空显示")
        self.clear_log_button.clicked.connect(self._clear_ui_log)
        self.open_logs_button = self._make_button("打开日志目录", icon_name="SP_DirOpenIcon")
        self.open_logs_button.clicked.connect(self._open_logs_dir)
        self.update_button = self._make_button("检查更新", icon_name="SP_BrowserReload")
        self.update_button.clicked.connect(self._check_updates)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(250)

        profile_layout.addWidget(self.profile_list)

        controls_panel = panel_frame()
        controls = QVBoxLayout(controls_panel)
        controls.setContentsMargins(18, 16, 18, 16)
        controls.setSpacing(12)
        controls_title = QLabel("当前状态")
        controls_title.setObjectName("sectionTitle")
        switches = QHBoxLayout()
        switches.setSpacing(16)
        switches.addWidget(self.resident_checkbox)
        switches.addWidget(self.startup_checkbox)
        switches.addWidget(self.prevent_sleep_checkbox)
        switches.addWidget(self.resume_reconnect_checkbox)
        switches.addStretch(1)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.login_button)
        action_row.addWidget(self.check_now_button)
        action_row.addWidget(self.logout_button)
        action_row.addWidget(self.pause_button)
        rename_row = QHBoxLayout()
        rename_row.setSpacing(10)
        rename_row.addWidget(self.saved_name_input, 1)
        rename_row.addWidget(self.rename_profile_button)
        controls.addWidget(controls_title)
        controls.addWidget(self.status_label)
        controls.addWidget(QLabel("配置名称"))
        controls.addLayout(rename_row)
        controls.addLayout(switches)
        interval_row = QHBoxLayout()
        interval_row.setSpacing(10)
        interval_row.addWidget(QLabel("检测间隔"))
        interval_row.addWidget(self.check_interval_spin)
        interval_row.addWidget(QLabel("定期重登"))
        interval_row.addWidget(self.login_interval_spin)
        interval_row.addStretch(1)
        controls.addLayout(interval_row)
        controls.addWidget(QLabel("断网检测地址"))
        controls.addWidget(self.check_urls_input)
        controls.addLayout(action_row)
        controls.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(controls_panel)
        log_title = QLabel("运行日志")
        log_title.setObjectName("sectionTitle")
        log_buttons = QHBoxLayout()
        log_buttons.setSpacing(8)
        log_buttons.addWidget(log_title)
        log_buttons.addStretch(1)
        log_buttons.addWidget(self.copy_log_button)
        log_buttons.addWidget(self.clear_log_button)
        log_buttons.addWidget(self.open_logs_button)
        log_buttons.addWidget(self.export_diag_button)
        log_buttons.addWidget(self.update_button)
        right.addLayout(log_buttons)
        right.addWidget(self.log_view, 1)

        content.addWidget(profile_group, 1)
        content.addLayout(right, 2)
        layout.addLayout(header)
        layout.addLayout(content, 1)
        self.stack.addWidget(self.dashboard_page)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray.setIcon(self.app_icon)
        menu = QMenu()
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.reveal)
        login_action = QAction("立即登录", self)
        login_action.triggered.connect(self._login_now)
        check_action = QAction("检测网络", self)
        check_action.triggered.connect(self._check_network_now)
        pause_action = QAction("暂停/恢复", self)
        pause_action.triggered.connect(self._toggle_pause)
        logs_action = QAction("打开日志目录", self)
        logs_action.triggered.connect(self._open_logs_dir)
        diagnostics_action = QAction("导出诊断包", self)
        diagnostics_action.triggered.connect(self._export_diagnostics)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(show_action)
        menu.addAction(login_action)
        menu.addAction(check_action)
        menu.addAction(pause_action)
        menu.addSeparator()
        menu.addAction(logs_action)
        menu.addAction(diagnostics_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.reveal()
            if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger)
            else None
        )
        if self.tray_available:
            self.tray.show()
            self.tray.setVisible(True)

    def _load_profiles(self) -> None:
        self.profiles = self.store.load_profiles()
        self.profile_list.clear()
        for profile in self.profiles:
            self.profile_list.addItem(self._profile_list_text(profile))

    def _current_profile(self) -> Profile | None:
        row = self.profile_list.currentRow()
        if row < 0 or row >= len(self.profiles):
            return None
        return self.profiles[row]

    def _profile_list_text(self, profile: Profile) -> str:
        return f"{profile.name} - {profile.adapter_name}"

    def _start_new_profile(self) -> None:
        self.detected_outcome = None
        self.detect_status.setText("")
        self.diagnostic_box.clear()
        self.diagnostic_box.setVisible(False)
        self.copy_diagnostic_button.setVisible(False)
        self.protocol_label.setText("")
        self.profile_name_input.clear()
        self.username_input.clear()
        self.password_input.clear()
        self.custom_suffix_input.clear()
        self.operator_combo.setCurrentIndex(0)
        has_profiles = bool(self.profiles)
        self.detect_back_dashboard_button.setVisible(has_profiles)
        self.cancel_profile_button.setVisible(has_profiles)
        self.stack.setCurrentWidget(self.detect_page)

    def _back_to_dashboard(self) -> None:
        if self.profiles:
            self.stack.setCurrentWidget(self.dashboard_page)
            if self.profile_list.currentRow() < 0:
                self.profile_list.setCurrentRow(0)
            return
        self.stack.setCurrentWidget(self.detect_page)

    def _select_profile(self, row: int) -> None:
        profile = self._current_profile()
        if not profile:
            return
        option_widgets = [
            self.saved_name_input,
            self.resident_checkbox,
            self.startup_checkbox,
            self.prevent_sleep_checkbox,
            self.resume_reconnect_checkbox,
            self.check_interval_spin,
            self.login_interval_spin,
            self.check_urls_input,
        ]
        self._loading_profile_options = True
        for widget in option_widgets:
            widget.blockSignals(True)
        self.saved_name_input.setText(profile.name)
        self.resident_checkbox.setChecked(profile.resident_enabled)
        self.startup_checkbox.setChecked(profile.startup_enabled or is_startup_enabled())
        self.prevent_sleep_checkbox.setChecked(profile.prevent_sleep_enabled)
        self.resume_reconnect_checkbox.setChecked(profile.resume_reconnect_enabled)
        self.check_interval_spin.setValue(max(10, int(profile.check_interval_seconds)))
        self.login_interval_spin.setValue(max(1, int(profile.login_interval_seconds // 3600)))
        self.check_urls_input.setPlainText("\n".join(normalize_check_urls(profile.check_urls or profile.check_url)))
        for widget in option_widgets:
            widget.blockSignals(False)
        self._loading_profile_options = False
        self._stop_service()
        if profile.resident_enabled:
            if not self._start_service(profile):
                profile.resident_enabled = False
                self.store.upsert_profile(profile)
                self.resident_checkbox.blockSignals(True)
                self.resident_checkbox.setChecked(False)
                self.resident_checkbox.blockSignals(False)

    def _detect_protocol(self) -> None:
        self.detect_status.setText("正在访问并识别协议...")
        QApplication.processEvents()
        outcome = self.detector.detect(self.url_input.text())
        self.detected_outcome = outcome
        diagnostic = diagnostic_to_text(outcome.diagnostic)
        if outcome.supported and outcome.detected:
            detected = outcome.detected
            self.detect_status.setText(
                f"识别成功：{detected.adapter_name}，置信分 {detected.score}"
            )
            self.protocol_label.setText(f"{detected.adapter_name} ({detected.gateway})")
            self.profile_name_input.setText(detected.adapter_name)
            self.stack.setCurrentWidget(self.credentials_page)
            self.diagnostic_box.setVisible(False)
            self.copy_diagnostic_button.setVisible(False)
        else:
            best = outcome.candidates[0] if outcome.candidates else None
            suffix = f"；最高候选 {best.adapter_name} {best.score} 分" if best else ""
            self.detect_status.setText(f"暂未适配该网站{suffix}")
            self.diagnostic_box.setPlainText(diagnostic)
            self.diagnostic_box.setVisible(True)
            self.copy_diagnostic_button.setVisible(True)

    def _rename_current_profile(self) -> None:
        row = self.profile_list.currentRow()
        profile = self._current_profile()
        if not profile:
            return
        new_name = self.saved_name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "无法保存名称", "配置名称不能为空")
            self.saved_name_input.setText(profile.name)
            return
        if new_name == profile.name:
            self._set_status("配置名称未改变")
            return
        profile.name = new_name
        self.store.upsert_profile(profile)
        self.profiles[row] = profile
        item = self.profile_list.item(row)
        if item:
            item.setText(self._profile_list_text(profile))
        self._set_status(f"配置名称已更新为：{new_name}")

    def _copy_diagnostic(self) -> None:
        QApplication.clipboard().setText(self.diagnostic_box.toPlainText())
        self._set_status("诊断信息已复制")

    def _operator_changed(self) -> None:
        self.custom_suffix_input.setEnabled(self.operator_combo.currentData() == "__custom__")

    def _save_detected_profile(self) -> None:
        if not self.detected_outcome or not self.detected_outcome.detected:
            QMessageBox.warning(self, "无法保存", "请先识别协议")
            return
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "无法保存", "账号和密码不能为空")
            return
        operator_suffix = self.operator_combo.currentData()
        operator_label = self.operator_combo.currentText()
        if operator_suffix == "__custom__":
            operator_suffix = self.custom_suffix_input.text().strip().lstrip("@")
        detected = self.detected_outcome.detected
        profile = self.store.create_profile(
            name=self.profile_name_input.text().strip() or detected.adapter_name,
            login_url=self.detected_outcome.diagnostic.requested_url,
            adapter_id=detected.adapter_id,
            adapter_name=detected.adapter_name,
            gateway=detected.gateway,
            login_endpoint=detected.login_endpoint,
            logout_endpoint=detected.logout_endpoint,
            username=username,
            password=password,
            operator_label=operator_label,
            operator_suffix=str(operator_suffix or ""),
        )
        self.store.upsert_profile(profile)
        self._load_profiles()
        self.stack.setCurrentWidget(self.dashboard_page)
        self.profile_list.setCurrentRow(len(self.profiles) - 1)
        self._set_status("配置已保存")

    def _resident_changed(self) -> None:
        profile = self._current_profile()
        if not profile:
            return
        profile.resident_enabled = self.resident_checkbox.isChecked()
        self.store.upsert_profile(profile)
        if profile.resident_enabled:
            if not self._start_service(profile):
                profile.resident_enabled = False
                self.store.upsert_profile(profile)
                self.resident_checkbox.blockSignals(True)
                self.resident_checkbox.setChecked(False)
                self.resident_checkbox.blockSignals(False)
        else:
            self._stop_service()

    def _profile_options_changed(self) -> None:
        if self._loading_profile_options:
            return
        profile = self._current_profile()
        if not profile:
            return
        profile.prevent_sleep_enabled = self.prevent_sleep_checkbox.isChecked()
        profile.resume_reconnect_enabled = self.resume_reconnect_checkbox.isChecked()
        profile.check_interval_seconds = int(self.check_interval_spin.value())
        profile.login_interval_seconds = int(self.login_interval_spin.value()) * 60 * 60
        profile.check_urls = normalize_check_urls(self.check_urls_input.toPlainText())
        profile.check_url = profile.check_urls[0]
        self.store.upsert_profile(profile)
        if self.service and self.service.running:
            self.service.update_profile(profile)

    def _startup_changed(self) -> None:
        profile = self._current_profile()
        if not profile:
            return
        try:
            set_startup(self.startup_checkbox.isChecked())
            profile.startup_enabled = self.startup_checkbox.isChecked()
            self.store.upsert_profile(profile)
            self._set_status("开机自启已更新")
        except Exception as exc:
            QMessageBox.warning(self, "开机自启失败", str(exc))

    def _start_service(self, profile: Profile) -> bool:
        self._stop_service()
        password = self._get_password_or_prompt(profile)
        if password is None:
            self._set_status("需要重新输入密码后才能登录")
            return False
        self.service = AutoLoginService(
            profile,
            lambda _profile: password,
            self.logger,
            status_callback=self._post_status,
        )
        self.service.start()
        return True

    def _stop_service(self) -> None:
        if self.service:
            self.service.stop()
            self.service = None

    def _login_now(self) -> None:
        profile = self._current_profile()
        if not profile:
            return
        try:
            if self.service and self.service.running:
                result = self.service.login_now()
            else:
                result = self._login_once(profile)
                if result is None:
                    return
            self._set_status(result.message)
            if not result.success:
                QMessageBox.warning(
                    self,
                    "登录失败",
                    f"{result.message}\n\n{result.raw_summary[:300]}",
                )
        except Exception as exc:
            self._handle_runtime_error("立即登录失败", exc)

    def _logout_now(self) -> None:
        try:
            if not self.service:
                profile = self._current_profile()
                if not profile:
                    return
                result = self._logout_once(profile)
                if result is None:
                    return
                self._set_status(result.message)
                return
            result = self.service.logout_now()
            self._set_status(result.message)
        except Exception as exc:
            self._handle_runtime_error("注销失败", exc)

    def _toggle_pause(self) -> None:
        if not self.service:
            self._set_status("常驻未启动，无法暂停")
            return
        self.service.pause(not self.service.paused)
        self.pause_button.setText("恢复" if self.service.paused else "暂停")

    def _check_network_now(self) -> None:
        profile = self._current_profile()
        if not profile:
            return
        try:
            if self.service and self.service.running:
                self.service.request_check("手动触发网络检测")
                return
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            adapter = get_adapter(profile.adapter_id)
            online = adapter.check_status(
                session,
                self._profile_detection(profile),
                profile.check_urls or [profile.check_url],
            )
            if online:
                self._set_status("网络检测正常，无需重新登录")
                return
            self._set_status("检测到可能已断网，正在尝试登录")
            result = self._login_once(profile)
            if result is None:
                return
            self._set_status(result.message)
            if not result.success:
                QMessageBox.warning(
                    self,
                    "网络检测后登录失败",
                    f"{result.message}\n\n{result.raw_summary[:300]}",
                )
        except Exception as exc:
            self._handle_runtime_error("网络检测失败", exc)

    def _copy_ui_log(self) -> None:
        QApplication.clipboard().setText(self.log_view.toPlainText())
        self._set_status("运行日志已复制")

    def _clear_ui_log(self) -> None:
        self.status_messages.clear()
        self.log_view.clear()
        self._set_status("运行日志显示已清空")

    def _open_logs_dir(self) -> None:
        path = logs_dir()
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self._set_status(f"已打开日志目录：{path}")
        except Exception as exc:
            self._handle_runtime_error("打开日志目录失败", exc)

    def _export_diagnostics(self) -> None:
        try:
            output = export_diagnostic_bundle(
                output_dir=data_dir() / "diagnostics",
                profiles=self.profiles,
                log_dir=logs_dir(),
                ui_log=self.log_view.toPlainText(),
            )
            self._set_status(f"诊断包已导出：{output}")
            QMessageBox.information(self, "诊断包已导出", f"文件位置：\n{output}")
        except Exception as exc:
            self._handle_runtime_error("导出诊断包失败", exc)

    def _check_updates(self) -> None:
        self.update_button.setEnabled(False)
        self._set_status("正在检查更新...")
        QApplication.processEvents()
        try:
            result = check_latest_release()
            self._set_status(result.message)
            if result.has_update and result.url:
                QMessageBox.information(
                    self,
                    "发现新版本",
                    f"{result.message}\n\n下载页面：\n{result.url}",
                )
            else:
                QMessageBox.information(self, "检查更新", result.message)
        finally:
            self.update_button.setEnabled(True)

    def _watch_resume(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_resume_tick
        self._last_resume_tick = now
        if elapsed < 90:
            return
        profile = self._current_profile()
        if (
            profile
            and profile.resume_reconnect_enabled
            and self.service
            and self.service.running
            and not self.service.paused
        ):
            self.service.request_check("检测到电脑可能刚从睡眠/休眠恢复，立即检查网络")

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setToolTip(message)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status_messages.append(f"[{timestamp}] {message}")
        self.status_messages = self.status_messages[-100:]
        self.log_view.setPlainText("\n".join(self.status_messages))
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        if self.tray:
            self.tray.setToolTip(message)

    def _post_status(self, message: str) -> None:
        self.ui_bridge.status_requested.emit(message)

    def _profile_detection(self, profile: Profile) -> DetectionResult:
        return DetectionResult(
            supported=True,
            adapter_id=profile.adapter_id,
            adapter_name=profile.adapter_name,
            score=100,
            gateway=profile.gateway,
            login_endpoint=profile.login_endpoint,
            logout_endpoint=profile.logout_endpoint,
            reason="来自已保存配置",
        )

    def _credentials(self, profile: Profile, password: str) -> Credentials:
        return Credentials(
            username=profile.username,
            password=password,
            operator_suffix=profile.operator_suffix,
        )

    def _login_once(self, profile: Profile) -> LoginResult | None:
        password = self._get_password_or_prompt(profile)
        if password is None:
            self._set_status("需要重新输入密码后才能登录")
            return None
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        adapter = get_adapter(profile.adapter_id)
        result = adapter.login(
            session,
            self._profile_detection(profile),
            self._credentials(profile, password),
        )
        self.logger.info("Manual login: %s; summary=%s", result.message, result.raw_summary)
        return result

    def _logout_once(self, profile: Profile) -> LoginResult | None:
        password = self._get_password_or_prompt(profile)
        if password is None:
            self._set_status("需要重新输入密码后才能注销")
            return None
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        adapter = get_adapter(profile.adapter_id)
        result = adapter.logout(
            session,
            self._profile_detection(profile),
            self._credentials(profile, password),
        )
        self.logger.info("Manual logout: %s; summary=%s", result.message, result.raw_summary)
        return result

    def _get_password_or_prompt(self, profile: Profile) -> str | None:
        try:
            return self.store.decrypt_password(profile)
        except Exception as exc:
            log_startup_exception(exc)
            password, ok = QInputDialog.getText(
                self,
                "需要重新输入密码",
                "保存的密码无法在当前 Windows 状态下解密，请重新输入校园网密码：",
                QLineEdit.EchoMode.Password,
            )
            if not ok or not password:
                return None
            try:
                updated = self.store.update_password(profile.id, password)
                for index, item in enumerate(self.profiles):
                    if item.id == profile.id:
                        self.profiles[index] = updated
                        break
                self._set_status("密码已重新加密保存")
                return password
            except Exception as save_exc:
                self._handle_runtime_error("保存新密码失败", save_exc)
                return None

    def _handle_runtime_error(self, title: str, exc: Exception) -> None:
        path = log_startup_exception(exc)
        message = f"{title}：{exc}\n\n错误日志：{path}"
        self._set_status(title)
        QMessageBox.critical(self, title, message)

    def reveal(self) -> None:
        self.showNormal()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        profile = self._current_profile()
        if profile and self.tray_available and not self.close_prompt_seen:
            prompt = QMessageBox(self)
            prompt.setWindowTitle("关闭程序")
            prompt.setText("你想把程序缩小到托盘继续运行，还是直接退出？")
            minimize_button = prompt.addButton("缩小到托盘", QMessageBox.ButtonRole.AcceptRole)
            exit_button = prompt.addButton("直接退出", QMessageBox.ButtonRole.DestructiveRole)
            cancel_button = prompt.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            prompt.setDefaultButton(minimize_button)
            prompt.exec()
            clicked = prompt.clickedButton()
            if clicked == cancel_button:
                event.ignore()
                return
            if clicked == exit_button:
                self._quit_app()
                return
            self.close_prompt_seen = True
            event.ignore()
            self.hide()
            self.tray.showMessage("校园网自动登录", "程序已缩小到托盘。")
            return

        if profile and profile.resident_enabled:
            if self.tray_available:
                event.ignore()
                self.hide()
                self.tray.showMessage("校园网自动登录", "程序已隐藏到托盘，仍在常驻运行。")
                return
            event.ignore()
            self.reveal()
            QMessageBox.warning(
                self,
                "系统托盘不可用",
                "当前系统没有可用托盘区域，程序不会隐藏到后台。请先关闭常驻，或保持窗口打开。",
            )
            return

        self._quit_app()

    def _quit_app(self) -> None:
        self._stop_service()
        QApplication.quit()


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--safe-mode", action="store_true")
    parser.add_argument("--no-single-instance", action="store_true")
    args = parser.parse_args(argv)

    if QApplication is None:
        print("缺少 PySide6。请先运行：pip install -r requirements.txt")
        return 2

    lock = SingleInstanceLock()
    primary_instance = True
    show_request_succeeded = False
    if not args.no_single_instance:
        primary_instance = lock.acquire()
        if not primary_instance:
            show_request_succeeded = SingleInstanceLock.request_show()
            log_startup_event(
                f"single instance lock busy; show_request_succeeded={show_request_succeeded}; opening recovery window"
            )
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(make_app_icon())

    def qt_exception_hook(exc_type, exc, tb):
        path = log_startup_exception(exc)
        try:
            QMessageBox.critical(
                None,
                "CampusAutoLogin 运行错误",
                f"程序遇到错误，但窗口不会直接关闭。\n\n{exc}\n\n错误日志：{path}",
            )
        except Exception:
            show_native_error(
                "CampusAutoLogin 运行错误",
                f"{exc}\n\n错误日志：{path}",
            )

    sys.excepthook = qt_exception_hook

    bridge = IpcBridge()
    minimized = args.minimized and primary_instance and not args.safe_mode
    window = MainWindow(
        minimized=minimized,
        recovery_window=not primary_instance,
    )
    if primary_instance:
        bridge.show_requested.connect(window.reveal)
        lock.start_server(lambda command: bridge.show_requested.emit() if command == "show" else None)
    if not minimized:
        window.show()
    code = app.exec()
    if primary_instance:
        lock.release()
    return code


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except BaseException as exc:
        path = log_startup_exception(exc)
        show_native_error(
            "CampusAutoLogin 启动失败",
            f"程序启动失败，错误日志已写入：\n{path}",
        )
        return 1
