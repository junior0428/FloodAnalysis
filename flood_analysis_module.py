# -*- coding: utf-8 -*-
import os
import ee

from qgis.PyQt.QtCore    import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui     import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
)
from qgis.gui import QgsMapTool

from .resources import *
from .flood_analysis_module_dialog import flood_analysisDialog


class PointMapTool(QgsMapTool):
    """
    Un QgsMapTool que captura un clic en el canvas, reproyecta
    esa coordenada a EPSG:4326 y la muestra en el label del diálogo.
    """
    def __init__(self, canvas, parent_plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.parent_plugin = parent_plugin

        # Preparamos el transformador: de CRS del proyecto a EPSG:4326
        proyecto_crs = QgsProject.instance().crs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.transform_to_wgs84 = QgsCoordinateTransform(
            proyecto_crs,
            wgs84_crs,
            QgsProject.instance()
        )

    def canvasPressEvent(self, event):
        # Obtenemos el punto en coordenadas del CRS actual del canvas
        p_map = self.toMapCoordinates(event.pos())

        # Reproyectamos a EPSG:4326
        try:
            punto_wgs84 = self.transform_to_wgs84.transform(p_map)
            lon = punto_wgs84.x()
            lat = punto_wgs84.y()
        except Exception as e:
            QMessageBox.critical(
                None,
                "Error de Proyección",
                f"No se pudo convertir las coordenadas a EPSG:4326:\n{e}"
            )
            # Desactivamos la herramienta para no colgar el cursor
            self.canvas.unsetMapTool(self)
            return

        # Guardamos en el plugin principal (en lon/lat correctos)
        self.parent_plugin.click_lon = lon
        self.parent_plugin.click_lat = lat

        # En lugar de un QMessageBox, actualizamos el label en el diálogo:
        if hasattr(self.parent_plugin, "dlg") and hasattr(self.parent_plugin.dlg, "lbl_coords"):
            self.parent_plugin.dlg.lbl_coords.setText(
                f"Lon: {lon:.6f}, Lat: {lat:.6f} (EPSG:4326)"
            )

        # Volver al MapTool por defecto
        self.canvas.unsetMapTool(self)


class flood_analysis:
    """
    Plugin flood_analysis_module para QGIS 3.x:
     1) Abre un diálogo para que el usuario seleccione la fecha, 
        días_before, días_after, polarización, dirección de órbita,
        un punto en el mapa y un tamaño (km).
     2) Con las coordenadas del clic y el tamaño, crea un cuadrado en EE.
     3) Calcula “difference > 1.1” a partir de Sentinel-1.
     4) Obtiene directamente la URL de teselas y carga la capa como QgsRasterLayer.
     5) Calcula el área inundada dentro de esa geometría y actualiza el diálogo.
    """

    def __init__(self, iface):
        self.iface       = iface
        self.canvas      = iface.mapCanvas()
        self.plugin_dir  = os.path.dirname(__file__)

        # Para internacionalización (i18n)
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

        # Atributos para la geometría dinámica
        self.click_lon = None
        self.click_lat = None
        self.map_tool = None  # instancia de PointMapTool

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
        Muestra (o crea, si es la primera vez) el diálogo que pide:
         - Fecha del evento
         - Días antes
         - Días después
         - Polarización
         - Dirección de órbita
         - Botón para capturar punto
         - Tamaño en km
        Conecta el botón btn_run al método run_analysis().
        Conecta el botón btn_point a activate_point_tool().
        """
        if self.first_start or not hasattr(self, 'dlg'):
            self.first_start = False
            self.dlg = flood_analysisDialog()

            # Conectar “Ejecutar”
            self.dlg.btn_run.clicked.connect(self.run_analysis)
            # Conectar “Point”
            self.dlg.btn_point.clicked.connect(self.activate_point_tool)

        # Limpiamos el label de coordenadas y de área cada vez que abrimos el diálogo
        self.dlg.lbl_coords.setText("Lon: --, Lat: --")
        self.dlg.lbl_area.setText("Área inundada: -- ha")

        # Mostrar el diálogo de forma NO bloqueante (modeless)
        self.dlg.show()

    def activate_point_tool(self):
        """
        Instancia y activa el QgsMapTool para capturar un solo clic
        en el canvas. Una vez capturado, el propio MapTool se desactiva.
        """
        if self.map_tool is None:
            self.map_tool = PointMapTool(self.canvas, self)
        self.canvas.setMapTool(self.map_tool)

    def run_analysis(self):
        """
        Slot que se llama cuando el usuario pulsa “Ejecutar”:
         1) Lee los valores del diálogo: fecha, días antes, días después,
            polarización, órbita, tamaño y verifica las coordenadas capturadas.
         2) Comprueba que haya fecha y coordenada; genera un polígono dinámico.
         3) Llama a _run_analysis() pasándole esos parámetros.
         4) Actualiza el label del área inundada.
        """
        # 1) Leer fecha
        qdate = self.dlg.date_event.date()
        self.event_date_str = qdate.toString('yyyy-MM-dd')

        if not self.event_date_str:
            QMessageBox.warning(
                self.dlg,
                self.tr('Falta fecha'),
                self.tr('Seleccione primero la fecha del evento antes de ejecutar.')
            )
            return

        # 1b) Leer días antes / días después / polarización / órbita
        days_before  = int(self.dlg.spin_before.value())
        days_after   = int(self.dlg.spin_after.value())
        polarization = str(self.dlg.cmb_pol.currentText())
        orbit_dir    = str(self.dlg.cmb_orbit.currentText())

        # 2) Verificar que se haya capturado un punto
        if self.click_lon is None or self.click_lat is None:
            QMessageBox.warning(
                self.dlg,
                self.tr('Falta punto'),
                self.tr('Debe pulsar “Point” y hacer clic en el mapa para capturar coordenadas.')
            )
            return

        # 2b) Leer tamaño en km
        tamaño_km = int(self.dlg.spin_size.value())

        # 3) Generar geometría dinámica (un rectángulo cuadrado) en EE
        try:
            # Convertimos tamaño en km a metros, y luego hacemos buffer/2 para cuadrado
            mitad_lado_m = (tamaño_km * 1000) / 2.0
            center_point = ee.Geometry.Point([self.click_lon, self.click_lat])
            ee_geometry = center_point.buffer(mitad_lado_m).bounds()
        except Exception as geoz:
            QMessageBox.critical(
                self.dlg,
                self.tr('Error en geometría'),
                f"No se pudo generar la geometría dinámica:\n{geoz}"
            )
            return

        # 4) Llamar a _run_analysis con los parámetros elegidos y capturar el área resultante
        try:
            area_ha = self._run_analysis(
                self.event_date_str,
                days_before, days_after,
                polarization, orbit_dir,
                ee_geometry
            )
            # Mostrar mensaje de éxito
            QMessageBox.information(
                self.dlg,
                self.tr('Éxito'),
                self.tr('El análisis ha terminado. Se añadió la capa de inundación.')
            )
            # Actualizar el label de área inundada (en ha)
            self.dlg.lbl_area.setText(f"Área inundada: {area_ha:.2f} ha")
        except Exception as e:
            QMessageBox.critical(
                self.dlg,
                self.tr('Error durante el análisis'),
                str(e)
            )
        finally:
            # Limpiar la fecha y la geometría para la próxima vez
            self.event_date_str = None
            self.click_lon = None
            self.click_lat = None

    def _run_analysis(self, date_str, days_before, days_after,
                      polarization, orbit_dir, ee_geometry):
        """
        1) Inicializa Earth Engine con tu ID de proyecto GCP.
        2) Filtra Sentinel-1 y calcula “difference” según los parámetros:
             - Días antes y después
             - Polarización
             - Dirección de órbita
        3) Aplica tus funciones difusas y genera la imagen “flooded”.
        4) Calcula el área inundada (en hectáreas) y devuelve ese valor.
        5) Obtiene la URL de teselas y carga la capa como QgsRasterLayer(uri, "Áreas Inundadas", "wms").
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

        # —— Verificar que existan imágenes “before” / “after” ————
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

        # —— 3) Funciones difusas y resto del procesamiento ————
        def fuzzyZ(img, z1, z2):
            z1_img = ee.Image.constant(z1)
            z2_img = ee.Image.constant(z2)
            mask = img.gte(z1_img).And(img.lte(z2_img))
            transition = mask.multiply(
                ee.Image(1).subtract(
                    img.subtract(z1_img).divide(z2_img.subtract(z1_img))
                )
            )
            return img.lt(z1_img).multiply(1) \
                      .add(img.gt(z2_img).multiply(0)) \
                      .add(transition)

        def fuzzyS(img, s1, s2):
            s1_img = ee.Image.constant(s1)
            s2_img = ee.Image.constant(s2)
            mask = img.gte(s1_img).And(img.lte(s2_img))
            transition = mask.multiply(
                img.subtract(s1_img).divide(s2_img.subtract(s1_img))
            )
            return img.lt(s1_img).multiply(0) \
                      .add(img.gt(s2_img).multiply(1)) \
                      .add(transition)

        s1 = 1.05
        s2 = 1.20
        FM_FV = fuzzyS(difference, s1, s2).rename('FM_FV')
        FM_FV = FM_FV.updateMask(FM_FV)

        # 1. Calcular NDBI (Sentinel-2) y mascarar zonas urbanas
        def mask_s2_clouds(image):
            qa = image.select('QA60')
            cloud_bit_mask = 1 << 10
            cirrus_bit_mask = 1 << 11
            mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
                qa.bitwiseAnd(cirrus_bit_mask).eq(0)
            )
            return image.updateMask(mask).divide(10000)

        sen2 = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterDate('2024-08-10', '2024-09-20')
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
            .filterBounds(ee_geometry)
            .map(mask_s2_clouds)
            .median()
            .clip(ee_geometry)
        )
        ndbi = sen2.normalizedDifference(['B11', 'B8']).rename('NDBI')
        urban_mask = ndbi.gt(0.2)
        FM_FV_mod = FM_FV.updateMask(urban_mask.Not())

        # 9. Cálculo de FM-OW (Agua Abierta) usando JRC/GSW1_0
        swater = ee.Image('JRC/GSW1_0/GlobalSurfaceWater').select('seasonality')
        water_mask = swater.gte(10)
        water_stats = swater.updateMask(water_mask).reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True
            ),
            geometry=ee_geometry,
            scale=30,
            bestEffort=True
        )
        mu    = ee.Number(water_stats.get('seasonality_mean'))
        sigma = ee.Number(water_stats.get('seasonality_stdDev'))
        z1_OW = mu
        z2_OW = mu.add(sigma.multiply(2))
        FM_OW = fuzzyZ(swater, z1_OW, z2_OW).rename('FM_OW')
        FM_OW = FM_OW.clip(ee_geometry)

        # 10. Unión difusa de FM-FV y FM-OW → FM1
        FM1 = FM_FV.max(FM_OW).rename('FM1')

        # Cargar DEM y calcular pendiente
        DEM = ee.Image('WWF/HydroSHEDS/03VFDEM')
        terrain = ee.Algorithms.Terrain(DEM)
        slope = terrain.select('slope')
        z1_slope = 1
        z2_slope = 5

        FM_HD = fuzzyZ(slope, z1_slope, z2_slope).clip(ee_geometry).rename('FM_HD')

        # 12. Fusión de información morfológica y de conectividad (FM2)
        weight1 = 3
        weight2 = 1

        FM2 = (
            FM1.updateMask(FM1.gt(0.8))
            .multiply(weight1)
            .add(FM_HD.multiply(weight2))
            .divide(weight1 + weight2)
            .rename('FM2')
        )

        # 13. Incorporar contexto espacial (FM3)
        kernel_context = ee.Kernel.square(radius=5)
        mean_context = FM2.reduceNeighborhood(
            reducer=ee.Reducer.mean(),
            kernel=kernel_context
        )

        D = FM2.subtract(mean_context).rename('D')
        z1_C = -0.2
        z2_C = 0.2

        FM3 = fuzzyZ(D, ee.Number(z1_C), ee.Number(z2_C)).multiply(FM2).rename('FM3')

        # Umbral final (por ejemplo, > 0.5)
        final_threshold = 0.5
        flooded = FM3.gt(final_threshold).rename('Flooded')

        # —— 4) Cálculo del área inundada ——————————————
        # 4.1) Crear un raster donde cada píxel “inundado” tenga su área en m²
        floodedAreaImage = flooded.multiply(ee.Image.pixelArea())

        # 4.2) Reducir esa imagen sumando todos los píxeles dentro de ee_geometry
        floodedAreaDict = floodedAreaImage.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=ee_geometry,
            scale=10,              # resolución de Sentinel-1 (10 m)
            maxPixels=1e13
        )

        # 4.3) Obtener el valor (en m²) y convertir a hectáreas (1 ha = 10.000 m²)
        floodedAreaM2 = floodedAreaDict.get('Flooded')
        areaHectareas = ee.Number(floodedAreaM2).divide(10000)

        # Usamos getInfo() para traer el valor al lado de Python
        try:
            area_ha_value = float(areaHectareas.getInfo())
        except Exception as ex_area:
            raise RuntimeError(f"No se pudo calcular el área inundada:\n{ex_area}")

        # —— 5) Obtener URL de teselas directamente ——————————
        viz_params = {
            'min':     0,
            'max':     1,
            'palette': ['blue']
        }

        try:
            tile_fetcher = flooded.getMapId(viz_params)["tile_fetcher"]
            xyz_url = tile_fetcher.url_format
        except Exception as e:
            raise RuntimeError(
                "No se pudo extraer la URL de teselas de Earth Engine.\n"
                "Asegúrate de haber autenticado EE (ee.Authenticate()) y de usar la versión correcta de la librería.\n"
                f"Error interno: {e}"
            )

        # —— 6) Crear URI tipo XYZ y cargar QgsRasterLayer ————
        uri = f"type=xyz&url={xyz_url}&zmin=0&zmax=22"
        layer_name = "Áreas Inundadas"
        layer = QgsRasterLayer(uri, layer_name, "wms")
        if not layer.isValid():
            raise RuntimeError("No se pudo crear la capa XYZ desde Earth Engine.")
        QgsProject.instance().addMapLayer(layer)

        # Finalmente devolvemos el valor de área en hectáreas para mostrar en la interfaz
        return area_ha_value
