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
     - Barra de título estándar (minimizar, maximizar, cerrar).
     - Imagen de portada (flood.png).
     - Grupo de parámetros con QFormLayout.
     - Botón “Point” para capturar coordenadas y label para mostrarlas.
     - Campo “Tamaño (km)” para generar un cuadrado.
     - Botón “Ejecutar” debajo de “Tamaño (km)”.
     - Label “Área inundada” al final (parte inferior del grupo).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ─── WindowFlags: mostrar botones estándar + siempre encima ───
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowStaysOnTopHint
        )

        # ───── Propiedades básicas del diálogo ─────
        self.setWindowTitle("Análisis de Inundaciones")
        self.resize(600, 520)  # Ajustamos la altura para dejar espacio al label de área

        # ───── Layout principal ────────────────────
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # ───── Cabecera personalizada ──────────────
        header_frame = QFrame(self)
        header_frame.setFrameShape(QFrame.NoFrame)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        icon_label = QLabel(header_frame)
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            icon_pix = QPixmap(icon_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(icon_pix)
        icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        title_label = QLabel("Análisis de Inundaciones", header_frame)
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        # ───── Contenido central ───────────────────
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # 1) Imagen de portada a la izquierda (flood.png)
        image_label = QLabel(self)
        image_path = os.path.join(os.path.dirname(__file__), "flood.png")
        if os.path.exists(image_path):
            img_pixmap = QPixmap(image_path).scaledToWidth(260, Qt.SmoothTransformation)
            image_label.setPixmap(img_pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # 2) Panel derecho con todos los controles
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # ── Grupo de parámetros con QFormLayout ──
        group = QGroupBox("Parámetros de Análisis", self)
        # Estilo para que el título del grupo sea más grande y en negrita
        group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 2px 0px;
            }
        """)
        group_layout = QFormLayout(group)
        group_layout.setContentsMargins(12, 8, 12, 8)
        group_layout.setLabelAlignment(Qt.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        group_layout.setHorizontalSpacing(16)
        group_layout.setVerticalSpacing(8)

        # – Fecha del evento
        lbl_date = QLabel("Fecha del evento:", self)
        lbl_date.setStyleSheet("font-size: 12px;")
        self.date_event = QDateEdit(self)
        self.date_event.setDisplayFormat("yyyy-MM-dd")
        self.date_event.setCalendarPopup(True)
        self.date_event.setDate(QDate.currentDate())
        self.date_event.setFixedWidth(120)

        # – Días antes del evento
        lbl_before = QLabel("Días antes:", self)
        lbl_before.setStyleSheet("font-size: 12px;")
        self.spin_before = QSpinBox(self)
        self.spin_before.setRange(1, 180)
        self.spin_before.setValue(30)
        self.spin_before.setFixedWidth(80)

        # – Días después del evento
        lbl_after = QLabel("Días después:", self)
        lbl_after.setStyleSheet("font-size: 12px;")
        self.spin_after = QSpinBox(self)
        self.spin_after.setRange(1, 180)
        self.spin_after.setValue(10)
        self.spin_after.setFixedWidth(80)

        # – Polarización (QComboBox)
        lbl_pol = QLabel("Polarización:", self)
        lbl_pol.setStyleSheet("font-size: 12px;")
        self.cmb_pol = QComboBox(self)
        self.cmb_pol.addItems(["VH", "VV"])
        self.cmb_pol.setCurrentText("VH")
        self.cmb_pol.setFixedWidth(100)

        # – Dirección de órbita (QComboBox)
        lbl_orbit = QLabel("Dirección órbita:", self)
        lbl_orbit.setStyleSheet("font-size: 12px;")
        self.cmb_orbit = QComboBox(self)
        self.cmb_orbit.addItems(["DESCENDING", "ASCENDING"])
        self.cmb_orbit.setCurrentText("DESCENDING")
        self.cmb_orbit.setFixedWidth(110)

        # Añadimos cada par “etiqueta / widget” al formulario
        group_layout.addRow(lbl_date, self.date_event)
        group_layout.addRow(lbl_before, self.spin_before)
        group_layout.addRow(lbl_after, self.spin_after)
        group_layout.addRow(lbl_pol, self.cmb_pol)
        group_layout.addRow(lbl_orbit, self.cmb_orbit)

        # ── Sección “Geometría” ──
        # Botón “Point” + label de coordenadas
        h_point_layout = QHBoxLayout()
        h_point_layout.setContentsMargins(0, 0, 0, 0)
        h_point_layout.setSpacing(8)
        lbl_point = QLabel("Geometría (clic):", self)
        lbl_point.setStyleSheet("font-size: 12px;")
        self.btn_point = QPushButton("Point", self)
        self.btn_point.setFixedWidth(100)
        self.btn_point.setStyleSheet("""
            background-color: #E67E22;
            color: white;
            font-weight: bold;
            padding: 6px;
            border-radius: 4px;
        """)
        h_point_layout.addWidget(lbl_point)
        h_point_layout.addWidget(self.btn_point)
        h_point_layout.addStretch(1)

        # Label para las coordenadas
        self.lbl_coords = QLabel("Lon: --, Lat: --", self)
        self.lbl_coords.setStyleSheet("font-size: 11px; color: #555555;")
        self.lbl_coords.setWordWrap(True)

        # Añadimos ambos a una subfila del formulario
        group_layout.addRow(h_point_layout)
        group_layout.addRow(self.lbl_coords)

        # ── Sección “Tamaño (km)” ──
        lbl_size = QLabel("Tamaño (km):", self)
        lbl_size.setStyleSheet("font-size: 12px;")
        self.spin_size = QSpinBox(self)
        self.spin_size.setRange(1, 500)
        self.spin_size.setValue(20)
        self.spin_size.setFixedWidth(60)

        # Añadimos “Tamaño (km)” al formulario por sí solo
        group_layout.addRow(lbl_size, self.spin_size)

        # ── Botón “Ejecutar” (en su propia fila, centrado entre las dos columnas) ──
        self.btn_run = QPushButton("Ejecutar", self)
        self.btn_run.setFixedHeight(36)
        self.btn_run.setStyleSheet("""
            background-color: #2980B9;
            color: white;
            font-weight: bold;
            padding-left: 16px;
            padding-right: 16px;
            border-radius: 5px;
        """)
        # Para centrarlo, pasamos un QLabel vacío como etiqueta y el botón como widget
        group_layout.addRow("", self.btn_run)

        # ── Label para mostrar el área inundada (debajo del botón) ──
        self.lbl_area = QLabel("Área inundada: -- ha", self)
        self.lbl_area.setStyleSheet("font-size: 12px; color: #222222;")
        self.lbl_area.setWordWrap(True)
        group_layout.addRow("", self.lbl_area)

        # ───── Ensamblar panel derecho ──────
        right_layout.addWidget(group)
        right_layout.addStretch(1)

        # ── Añadir imagen y formulario al contenido central ──
        content_layout.addWidget(image_label)
        content_layout.setAlignment(image_label, Qt.AlignTop)

        content_layout.addLayout(right_layout, 1)
        content_layout.setAlignment(right_layout, Qt.AlignTop)

        # ───── Montaje final ───────────────────────
        main_layout.addWidget(header_frame)
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)
