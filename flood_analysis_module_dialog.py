# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QDialog,
    QLabel,
    QDateEdit,
    QVBoxLayout,
    QPushButton
)
from qgis.PyQt.QtCore import QDate

class flood_analysisDialog(QDialog):
    """
    Diálogo que solo pide la fecha del evento y tiene un botón "Ejecutar Análisis".
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análisis de Inundaciones")

        # ───── Widgets ───────────
        lbl_date = QLabel("Fecha del evento:")
        self.date_event = QDateEdit()
        self.date_event.setDisplayFormat("yyyy-MM-dd")
        self.date_event.setCalendarPopup(True)
        # Por defecto: fecha actual
        self.date_event.setDate(QDate.currentDate())

        self.btn_run = QPushButton("Ejecutar Análisis")
        self.btn_run.setEnabled(True)

        # ───── Layout ────────────
        layout = QVBoxLayout()
        layout.addWidget(lbl_date)
        layout.addWidget(self.date_event)
        layout.addWidget(self.btn_run)
        self.setLayout(layout)
