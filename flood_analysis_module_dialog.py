# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtWidgets import (
    QDialog,
    QLabel,
    QDateEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QSizePolicy,
    QFrame,
    QGroupBox
)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import QDate, Qt


class flood_analysisDialog(QDialog):
    """
    Diálogo para el módulo de Análisis de Inundaciones:
     - Imagen de portada (flood.png).
     - Grupo de parámetros (fecha, antes/después, polarización, órbita).
     - Captura de AOI:
          * Botón “Point” (un clic) y
          * Botón “Rectángulo” (arrastrar en el canvas).
     - Campo “Tamaño (km)” (solo cuando se usa Point).
     - Botón “Ejecutar”.
     - Label “Área inundada”.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Ventana siempre arriba (mismo comportamiento que tenías)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowStaysOnTopHint
        )

        self.setWindowTitle("FloodAnalysis")
        self.resize(640, 540)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # Cabecera
        header_frame = QFrame(self)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        icon_label = QLabel(header_frame)
        icon_path = os.path.join(os.path.dirname(__file__), "img/icon.png")
        if os.path.exists(icon_path):
            icon_pix = QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(icon_pix)
        icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        title_label = QLabel("Análisis de Inundaciones", header_frame)
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        # Cuerpo
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # Imagen lateral
        image_label = QLabel(self)
        image_path = os.path.join(os.path.dirname(__file__), "img/flood.png")
        if os.path.exists(image_path):
            img_pixmap = QPixmap(image_path).scaledToWidth(300, Qt.SmoothTransformation)
            image_label.setPixmap(img_pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # Panel derecho
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        group = QGroupBox("Parámetros de Análisis", self)
        group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 2px 0px;
            }
        """)
        form = QFormLayout(group)
        form.setContentsMargins(12, 8, 12, 8)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)

        # Fecha
        lbl_date = QLabel("Fecha del evento:", self)
        lbl_date.setStyleSheet("font-size: 12px;")
        self.date_event = QDateEdit(self)
        self.date_event.setDisplayFormat("yyyy-MM-dd")
        self.date_event.setCalendarPopup(True)
        self.date_event.setDate(QDate.currentDate())
        self.date_event.setFixedWidth(120)

        # Días antes/después
        lbl_before = QLabel("Días antes:", self)
        self.spin_before = QSpinBox(self); self.spin_before.setRange(1, 180); self.spin_before.setValue(30); self.spin_before.setFixedWidth(80)

        lbl_after = QLabel("Días después:", self)
        self.spin_after = QSpinBox(self); self.spin_after.setRange(1, 180); self.spin_after.setValue(10); self.spin_after.setFixedWidth(80)

        # Polarización
        lbl_pol = QLabel("Polarización:", self)
        self.cmb_pol = QComboBox(self); self.cmb_pol.addItems(["VH", "VV"]); self.cmb_pol.setCurrentText("VH"); self.cmb_pol.setFixedWidth(100)

        # Órbita
        lbl_orbit = QLabel("Dirección órbita:", self)
        self.cmb_orbit = QComboBox(self); self.cmb_orbit.addItems(["DESCENDING", "ASCENDING"]); self.cmb_orbit.setCurrentText("DESCENDING"); self.cmb_orbit.setFixedWidth(120)

        form.addRow(lbl_date, self.date_event)
        form.addRow(lbl_before, self.spin_before)
        form.addRow(lbl_after, self.spin_after)
        form.addRow(lbl_pol, self.cmb_pol)
        form.addRow(lbl_orbit, self.cmb_orbit)

        # Geometría
        geom_layout = QHBoxLayout()
        geom_layout.setContentsMargins(0, 0, 0, 0)
        geom_layout.setSpacing(8)

        lbl_geom = QLabel("Geometría (clic/arrastre):", self)
        self.btn_point = QPushButton("Point", self)
        self.btn_point.setFixedWidth(100)
        self.btn_point.setStyleSheet("background-color:#E67E22;color:white;font-weight:bold;padding:6px;border-radius:4px;")

        self.btn_rect = QPushButton("Rectángulo", self)
        self.btn_rect.setFixedWidth(100)
        self.btn_rect.setStyleSheet("background-color:#16A085;color:white;font-weight:bold;padding:6px;border-radius:4px;")

        geom_layout.addWidget(lbl_geom)
        geom_layout.addWidget(self.btn_point)
        geom_layout.addWidget(self.btn_rect)
        geom_layout.addStretch(1)

        self.lbl_coords = QLabel("AOI: (sin definir)", self)
        self.lbl_coords.setStyleSheet("font-size: 11px; color: #555555;")
        self.lbl_coords.setWordWrap(True)

        form.addRow(geom_layout)
        form.addRow(self.lbl_coords)

        # Tamaño (solo para Point)
        lbl_size = QLabel("Tamaño (km):", self)
        self.spin_size = QSpinBox(self); self.spin_size.setRange(1, 500); self.spin_size.setValue(20); self.spin_size.setFixedWidth(70)
        form.addRow(lbl_size, self.spin_size)

        # Ejecutar
        self.btn_run = QPushButton("Ejecutar", self)
        self.btn_run.setFixedHeight(36)
        self.btn_run.setStyleSheet("background-color:#2980B9;color:white;font-weight:bold;padding-left:16px;padding-right:16px;border-radius:5px;")
        form.addRow("", self.btn_run)

        # Área
        self.lbl_area = QLabel("Área inundada: -- ha", self)
        self.lbl_area.setStyleSheet("font-size: 12px; color: #222222;")
        self.lbl_area.setWordWrap(True)
        form.addRow("", self.lbl_area)

        right_layout.addWidget(group)
        right_layout.addStretch(1)

        content_layout.addWidget(image_label)
        content_layout.addLayout(right_layout, 1)

        main_layout.addWidget(header_frame)
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)
