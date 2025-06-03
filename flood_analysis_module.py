# -*- coding: utf-8 -*-
import os
import ee

from qgis.PyQt.QtCore    import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui     import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from qgis.core import (
    QgsProject,
    QgsRasterLayer
)
from qgis.gui import QgsMapTool

from .resources import *
from .flood_analysis_module_dialog import flood_analysisDialog


class flood_analysis:
    """
    Plugin flood_analysis_module para QGIS 3.x:
     1) Abre un diálogo para que el usuario seleccione la fecha.
     2) Usa un polígono fijo (España) en Earth Engine.
     3) Calcula “difference > 1.1” a partir de Sentinel-1.
     4) Obtiene directamente la URL de teselas usando:
           url = flooded.getMapId(viz_params)["tile_fetcher"].url_format
        y carga la capa como QgsRasterLayer (proveedor WMS, aunque el URI sea XYZ).
    """

    def __init__(self, iface):
        self.iface       = iface
        self.canvas      = iface.mapCanvas()
        self.plugin_dir  = os.path.dirname(__file__)

        # Para internacionalización (i18n), si existieran .qm en i18n/
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'flood_analysis_{locale}.qm'
        )
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions        = []
        self.menu           = self.tr(u'&flood analysis')
        self.first_start    = None
        self.event_date_str = None  # guardaremos la fecha elegida

    def tr(self, message):
        return QCoreApplication.translate('flood_analysis', message)

    def add_action(self, icon_path, text, callback,
                   enabled_flag=True, add_to_menu=True,
                   add_to_toolbar=True, status_tip=None,
                   whats_this=None, parent=None):
        """
        Crea un QAction con icono y texto, conecta al callback
        y lo añade a la toolbar/menú del plugin.
        """
        icon   = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """
        Se ejecuta al activar el plugin en QGIS.
        Agrega el botón “Analizar Inundaciones” a toolbar/menú.
        """
        icon_run = ':/plugins/flood_analysis_module/icon.png'
        self.action_run = self.add_action(
            icon_path=icon_run,
            text=self.tr('Analizar Inundaciones'),
            callback=self.run_dialog,
            parent=self.iface.mainWindow()
        )
        self.first_start = True

    def unload(self):
        """
        Se ejecuta al desactivar el plugin:
        Quita las acciones del menú y toolbar.
        """
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

    def run_dialog(self):
        """
        Muestra (o crea, si es la primera vez) el diálogo que pide fecha.
        Conecta el botón btn_run al método run_analysis().
        """
        if self.first_start or not hasattr(self, 'dlg'):
            self.first_start = False
            self.dlg = flood_analysisDialog()
            self.dlg.btn_run.clicked.connect(self.run_analysis)

        # Mostrar el diálogo de forma NO bloqueante (modeless)
        self.dlg.show()

    def run_analysis(self):
        """
        Slot que se llama cuando el usuario pulsa “Ejecutar Análisis”:
         1) Lee la fecha del QDateEdit.
         2) Monta un polígono fijo (España) en Earth Engine.
         3) Llama a _run_analysis() para:
            - Filtrar Sentinel-1 antes/después de la fecha,
            - Calcular “difference > 1.1”,
            - Obtener directamente URL de teselas:
                  url = flooded.getMapId(viz_params)["tile_fetcher"].url_format
            - Montar URI XYZ y crear un QgsRasterLayer(uri, "Áreas Inundadas", "wms").
        """
        # 1) Leer la fecha del diálogo
        qdate = self.dlg.date_event.date()
        self.event_date_str = qdate.toString('yyyy-MM-dd')

        if not self.event_date_str:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr('Falta fecha'),
                self.tr('Seleccione primero la fecha del evento antes de ejecutar.')
            )
            return

        # 2) Definir geometría estática (rectángulo en España) en EE:
        coords = [
            [-0.6199335975154141, 39.09580067813199],
            [-0.17945050425369535, 39.09580067813199],
            [-0.17945050425369535, 39.575233667357125],
            [-0.6199335975154141, 39.575233667357125],
            [-0.6199335975154141, 39.09580067813199]
        ]
        ee_geometry = ee.Geometry.Polygon([coords])

        # 3) Parámetros fijos
        days_before  = 30
        days_after   = 10
        polarization = "VH"
        orbit_dir    = "DESCENDING"

        try:
            self._run_analysis(
                self.event_date_str,
                days_before, days_after,
                polarization, orbit_dir,
                ee_geometry
            )
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr('Éxito'),
                self.tr('El análisis ha terminado. Se añadió la capa de inundación.')
            )
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr('Error durante el análisis'),
                str(e)
            )
        finally:
            # Limpiar la fecha para la próxima vez
            self.event_date_str = None
            self.dlg.close()

    def _run_analysis(self, date_str, days_before, days_after,
                      polarization, orbit_dir, ee_geometry):
        """
        1) Inicializa Earth Engine con tu ID de proyecto GCP habilitado.
        2) Filtra Sentinel-1 y calcula “difference”.
        3) Umbral “difference > 1.1” → genera imagen binaria “flooded”.
        4) Llama a getMapId(viz_params) y extrae:
              url = flooded.getMapId(viz_params)["tile_fetcher"].url_format
        5) Monta URI XYZ y crea QgsRasterLayer(uri, "Áreas Inundadas", "wms").
        """

        # —— 1) Inicializar Earth Engine ——————————————
        try:
            # Reemplaza 'tidop-424613' con tu propio Project ID en GCP
            ee.Initialize(project='tidop-424613')
        except Exception as ee_err:
            raise RuntimeError(f"No se pudo inicializar Earth Engine:\n{ee_err}")

        # —— 2) Filtrar Sentinel-1 y calcular “difference” ————
        event_date   = ee.Date(date_str)
        before_start = event_date.advance(-days_before, 'day')
        before_end   = event_date
        after_start  = event_date
        after_end    = event_date.advance(days_after, 'day')

        col_s1 = (
            ee.ImageCollection('COPERNICUS/S1_GRD')
              .filter(ee.Filter.eq('instrumentMode', 'IW'))
              .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarization))
              .filter(ee.Filter.eq('orbitProperties_pass', orbit_dir))
              .filter(ee.Filter.eq('resolution_meters', 10))
              .filterBounds(ee_geometry)
              .select(polarization)
        )

        # —— 2a) Verificar que existan imágenes “before” / “after” ——
        size_before = col_s1.filterDate(before_start, before_end).size().getInfo()
        size_after  = col_s1.filterDate(after_start, after_end).size().getInfo()
        if size_before == 0:
            raise RuntimeError("No hay imágenes 'before' para esa fecha y área.")
        if size_after == 0:
            raise RuntimeError("No hay imágenes 'after' para esa fecha y área.")

        before_img = col_s1.filterDate(before_start, before_end).median().clip(ee_geometry)
        after_img  = col_s1.filterDate(after_start, after_end).median().clip(ee_geometry)

        smoothing_radius = 50
        before_filt = before_img.focal_mean(smoothing_radius, 'circle', 'meters')
        after_filt  = after_img.focal_mean(smoothing_radius, 'circle', 'meters')

        difference = after_filt.divide(before_filt).rename('difference')

        # —— 3) Umbral fijo “difference > 1.1” ——————————
        flooded = difference.gt(1.1).rename('Flooded')

        # —— 4) Obtener URL de teselas directamente ——————————
        viz_params = {
            'min':     0,
            'max':     1,
            'palette': ['ffffff', '0000ff']
        }

        # Extraemos la URL del objeto tile_fetcher:
        try:
            tile_fetcher = flooded.getMapId(viz_params)["tile_fetcher"]
            xyz_url = tile_fetcher.url_format
        except Exception as e:
            raise RuntimeError(
                "No se pudo extraer la URL de teselas de Earth Engine.\n"
                "Asegúrate de haber autenticado EE (ee.Authenticate()) y de usar la versión correcta de la librería.\n"
                f"Error interno: {e}"
            )

        # Para depurar, imprime en la Consola de Python de QGIS:
        print(">>> xyz_url completo: ", xyz_url)

        # —— 5) Crear URI tipo XYZ y cargar QgsRasterLayer (proveedor 'wms') ————
        uri = f"type=xyz&url={xyz_url}&zmin=0&zmax=22"
        print(">>> URI para QgsRasterLayer:", uri)

        layer_name = "Áreas Inundadas"
        layer = QgsRasterLayer(uri, layer_name, "wms")
        if not layer.isValid():
            raise RuntimeError("No se pudo crear la capa XYZ desde Earth Engine.")
        QgsProject.instance().addMapLayer(layer)

        return layer
