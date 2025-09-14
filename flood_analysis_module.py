# -*- coding: utf-8 -*-
import os
import ee

from qgis.PyQt.QtCore    import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui     import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QProgressDialog

from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsRectangle,
    QgsPointXY,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool, QgsRubberBand

from .resources import *
from .flood_analysis_module_dialog import flood_analysisDialog


# ------------------------ TOOLS ------------------------

class PointMapTool(QgsMapTool):
    """Captura un clic y lo guarda como punto en EPSG:4326."""
    def __init__(self, canvas, parent_plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.parent_plugin = parent_plugin

        proyecto_crs = QgsProject.instance().crs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.transform_to_wgs84 = QgsCoordinateTransform(
            proyecto_crs, wgs84_crs, QgsProject.instance()
        )

    def canvasPressEvent(self, event):
        p_map = self.toMapCoordinates(event.pos())
        try:
            p_wgs84 = self.transform_to_wgs84.transform(p_map)
            lon, lat = p_wgs84.x(), p_wgs84.y()
        except Exception as e:
            QMessageBox.critical(None, "Error de Proyección",
                                 f"No se pudo convertir a EPSG:4326:\n{e}")
            self.canvas.unsetMapTool(self)
            return

        # Guardar como modo "punto"
        self.parent_plugin.click_lon = lon
        self.parent_plugin.click_lat = lat
        self.parent_plugin.rect_bbox = None  # anula rectángulo si lo hubiera

        if hasattr(self.parent_plugin, "dlg"):
            self.parent_plugin.dlg.lbl_coords.setText(
                f"AOI (punto): Lon={lon:.6f}, Lat={lat:.6f} (EPSG:4326)"
            )

        self.canvas.unsetMapTool(self)


class RectMapTool(QgsMapTool):
    """Dibuja un rectángulo con rubber band y devuelve su bbox en EPSG:4326."""
    def __init__(self, canvas, parent_plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.parent_plugin = parent_plugin

        proyecto_crs = QgsProject.instance().crs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.transform_to_wgs84 = QgsCoordinateTransform(
            proyecto_crs, wgs84_crs, QgsProject.instance()
        )

        self.rb = None
        self.start_map_pt = None

    def canvasPressEvent(self, event):
        self.start_map_pt = self.toMapCoordinates(event.pos())
        if self.rb is None:
            self.rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rb.setWidth(2)
        self.rb.setStrokeColor(Qt.red)
        self.rb.setFillColor(Qt.transparent)

    def canvasMoveEvent(self, event):
        if self.start_map_pt is None or self.rb is None:
            return
        cur = self.toMapCoordinates(event.pos())
        rect = QgsRectangle(self.start_map_pt, cur)
        ring = [
            QgsPointXY(rect.xMinimum(), rect.yMinimum()),
            QgsPointXY(rect.xMinimum(), rect.yMaximum()),
            QgsPointXY(rect.xMaximum(), rect.yMaximum()),
            QgsPointXY(rect.xMaximum(), rect.yMinimum()),
            QgsPointXY(rect.xMinimum(), rect.yMinimum()),
        ]
        geom = QgsGeometry.fromPolygonXY([ring])
        self.rb.setToGeometry(geom, None)

    def canvasReleaseEvent(self, event):
        try:
            cur = self.toMapCoordinates(event.pos())
            rect = QgsRectangle(self.start_map_pt, cur)

            # Validación: debe tener área
            if abs(rect.width()) < 1e-9 or abs(rect.height()) < 1e-9:
                QMessageBox.warning(None, "Rectángulo inválido",
                                    "El rectángulo debe tener ancho y alto. Arrastra el ratón para definirlo.")
                self._cleanup()
                self.canvas.unsetMapTool(self)
                return

            # Transformar las 4 esquinas a WGS84 y construir bbox lon/lat
            corners = [
                QgsPointXY(rect.xMinimum(), rect.yMinimum()),
                QgsPointXY(rect.xMinimum(), rect.yMaximum()),
                QgsPointXY(rect.xMaximum(), rect.yMaximum()),
                QgsPointXY(rect.xMaximum(), rect.yMinimum()),
            ]
            lons, lats = [], []
            for p in corners:
                p_wgs84 = self.transform_to_wgs84.transform(p)
                lons.append(p_wgs84.x())
                lats.append(p_wgs84.y())

            lonmin, lonmax = min(lons), max(lons)
            latmin, latmax = min(lats), max(lats)

            # Guardar como modo "rectángulo"
            self.parent_plugin.rect_bbox = (lonmin, latmin, lonmax, latmax)
            self.parent_plugin.click_lon = None
            self.parent_plugin.click_lat = None

            if hasattr(self.parent_plugin, "dlg"):
                self.parent_plugin.dlg.lbl_coords.setText(
                    f"AOI (rectángulo): [xmin={lonmin:.6f}, ymin={latmin:.6f}, xmax={lonmax:.6f}, ymax={latmax:.6f}] (EPSG:4326)"
                )
        finally:
            self._cleanup()
            self.canvas.unsetMapTool(self)

    def _cleanup(self):
        try:
            if self.rb:
                self.rb.reset(QgsWkbTypes.PolygonGeometry)
        except Exception:
            pass
        self.rb = None
        self.start_map_pt = None


# ---------------------- PLUGIN ----------------------

class flood_analysis:
    """
    Plugin flood_analysis_module para QGIS 3.x:
     - AOI por Punto (con tamaño) o Rectángulo dibujado.
     - Progreso modal simple.
     - Parche null-safe para GSW y área.
    """

    def __init__(self, iface):
        self.iface       = iface
        self.canvas      = iface.mapCanvas()
        self.plugin_dir  = os.path.dirname(__file__)

        # i18n
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'flood_analysis_{locale}.qm')
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions        = []
        self.menu           = self.tr(u'&FloodAnalysis')
        self.first_start    = None

        # Estado de AOI
        self.click_lon = None
        self.click_lat = None
        self.rect_bbox = None  # (xmin, ymin, xmax, ymax) en EPSG:4326

        # Herramientas
        self.map_tool_point = None
        self.map_tool_rect  = None

    def tr(self, message):
        return QCoreApplication.translate('flood_analysis', message)

    def add_action(self, icon_path, text, callback,
                   enabled_flag=True, add_to_menu=True,
                   add_to_toolbar=True, status_tip=None,
                   whats_this=None, parent=None):
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
        icon_run = ':/plugins/flood_analysis_module/icon.png'
        self.action_run = self.add_action(
            icon_path=icon_run,
            text=self.tr('Analizar Inundaciones'),
            callback=self.run_dialog,
            parent=self.iface.mainWindow()
        )
        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

    # ----------------- Diálogo -----------------

    def run_dialog(self):
        if self.first_start or not hasattr(self, 'dlg'):
            self.first_start = False
            self.dlg = flood_analysisDialog()
            self.dlg.btn_run.clicked.connect(self.run_analysis)
            self.dlg.btn_point.clicked.connect(self.activate_point_tool)
            self.dlg.btn_rect.clicked.connect(self.activate_rect_tool)

        # Reset textos
        self.dlg.lbl_coords.setText("AOI: (sin definir)")
        self.dlg.lbl_area.setText("Área inundada: -- ha")
        self.dlg.show()

    def activate_point_tool(self):
        if self.map_tool_point is None:
            self.map_tool_point = PointMapTool(self.canvas, self)
        self.canvas.setMapTool(self.map_tool_point)
        if hasattr(self, "dlg"):
            self.dlg.lbl_coords.setText("AOI: haga un clic en el mapa…")

    def activate_rect_tool(self):
        if self.map_tool_rect is None:
            self.map_tool_rect = RectMapTool(self.canvas, self)
        self.canvas.setMapTool(self.map_tool_rect)
        if hasattr(self, "dlg"):
            self.dlg.lbl_coords.setText("AOI: arrastre para dibujar el rectángulo…")

    # --------------- Progreso helpers ---------------

    def _new_progress(self, text="Preparando…", maximum=100):
        parent = self.dlg if hasattr(self, "dlg") else self.iface.mainWindow()
        prog = QProgressDialog(text, "Abortar", 0, maximum, parent)
        prog.setWindowTitle("FloodAnalysis – Progreso")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog._cancelled = False
        prog.canceled.connect(lambda: setattr(prog, "_cancelled", True))
        return prog

    def _step(self, prog: QProgressDialog, value: int, text: str = None):
        if prog is None:
            return
        if getattr(prog, "_cancelled", False):
            raise RuntimeError("Operación cancelada por el usuario.")
        if text:
            prog.setLabelText(text)
        prog.setValue(value)
        QCoreApplication.processEvents()

    # ----------------- Ejecutar -----------------

    def run_analysis(self):
        # Parámetros
        qdate = self.dlg.date_event.date()
        event_date_str = qdate.toString('yyyy-MM-dd')
        if not event_date_str:
            QMessageBox.warning(self.dlg, self.tr('Falta fecha'),
                                self.tr('Seleccione la fecha del evento.'))
            return

        days_before  = int(self.dlg.spin_before.value())
        days_after   = int(self.dlg.spin_after.value())
        polarization = str(self.dlg.cmb_pol.currentText())
        orbit_dir    = str(self.dlg.cmb_orbit.currentText())

        # AOI: rectángulo preferente; si no, punto+size
        ee_geometry = None
        if self.rect_bbox is not None:
            xmin, ymin, xmax, ymax = self.rect_bbox
            # Validación por si acaso
            if abs(xmax - xmin) < 1e-12 or abs(ymax - ymin) < 1e-12:
                QMessageBox.warning(self.dlg, "Rectángulo inválido",
                                    "El rectángulo debe tener ancho y alto. Dibújalo nuevamente.")
                return
            ee_geometry = ee.Geometry.Rectangle([xmin, ymin, xmax, ymax], proj=None, geodesic=False)
        elif (self.click_lon is not None) and (self.click_lat is not None):
            size_km = int(self.dlg.spin_size.value())
            half_m  = (size_km * 1000) / 2.0
            center_point = ee.Geometry.Point([self.click_lon, self.click_lat])
            ee_geometry  = center_point.buffer(half_m).bounds()
        else:
            QMessageBox.warning(self.dlg, self.tr('Falta AOI'),
                                self.tr('Defina el AOI con Point o Rectángulo.'))
            return

        # Progreso
        prog = self._new_progress("Inicializando análisis…")
        self.dlg.btn_run.setEnabled(False)

        try:
            self._step(prog, 5, "Inicializando Earth Engine…")
            # Ejecutar algoritmo
            area_ha = self._run_analysis(
                event_date_str, days_before, days_after,
                polarization, orbit_dir, ee_geometry, prog
            )
            self._step(prog, 100, "Completado.")

            QMessageBox.information(self.dlg, "Éxito",
                                    "El análisis ha terminado y la capa ha sido añadida.")
            self.dlg.lbl_area.setText(f"Área inundada: {area_ha:.2f} ha")

        except Exception as e:
            QMessageBox.critical(self.dlg, self.tr('Error durante el análisis'), str(e))
        finally:
            try:
                prog.close()
            except Exception:
                pass
            self.dlg.btn_run.setEnabled(True)
            # limpiar estado del AOI
            self.click_lon = None
            self.click_lat = None
            self.rect_bbox = None

    # --------------- Núcleo del algoritmo ---------------

    def _run_analysis(self, date_str, days_before, days_after,
                      polarization, orbit_dir, ee_geometry, prog=None):

        # 1) EE init
        try:
            ee.Initialize(project='tidop-424613')
        except Exception as ee_err:
            raise RuntimeError(f"No se pudo inicializar Earth Engine:\n{ee_err}")
        self._step(prog, 20, "Filtrando colecciones…")

        # 2) Fechas
        event_date   = ee.Date(date_str)
        before_start = event_date.advance(-days_before, 'day')
        before_end   = event_date
        after_start  = event_date
        after_end    = event_date.advance(days_after, 'day')

        # 3) Colecciones
        col_s1 = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", polarization))
            .filter(ee.Filter.eq("orbitProperties_pass", orbit_dir))
            .filter(ee.Filter.eq("resolution_meters", 10))
            .filterBounds(ee_geometry)
            .select(polarization)
        )

        if col_s1.filterDate(before_start, before_end).size().getInfo() == 0:
            raise RuntimeError("No hay imágenes 'before' para esa fecha y área.")
        if col_s1.filterDate(after_start, after_end).size().getInfo() == 0:
            raise RuntimeError("No hay imágenes 'after' para esa fecha y área.")

        def _mask_s2_clouds(image):
            qa = image.select('QA60')
            cloud_bit = 1 << 10
            cirrus_bit = 1 << 11
            mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
            return image.updateMask(mask).divide(10000)

        s2_sr = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate('2024-08-10', '2024-09-20')
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .filterBounds(ee_geometry)
            .map(_mask_s2_clouds)
            .median()
            .clip(ee_geometry)
        )

        chirps = (
            ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
            .filterDate(event_date, event_date.advance(1, "day"))
            .filterBounds(ee_geometry)
            .select("precipitation")
        )

        gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        occ = gsw.select("occurrence")  # 0..100
        dem = ee.Image('WWF/HydroSHEDS/03VFDEM')

        # 4) Diferencia S1
        self._step(prog, 35, "Compuestas before/after y razón…")
        before_img = col_s1.filterDate(before_start, before_end).median().clip(ee_geometry)
        after_img  = col_s1.filterDate(after_start,  after_end ).median().clip(ee_geometry)

        smoothing_radius = 50  # m
        before_f = before_img.focal_mean(smoothing_radius, "circle", "meters")
        after_f  = after_img .focal_mean(smoothing_radius, "circle", "meters")
        difference = after_f.divide(before_f).rename("difference")

        # 5) Fuzzy
        self._step(prog, 50, "Variación SAR (FM_FV) y filtros…")
        def _fuzzyS(img, s1, s2):
            s1_img = ee.Image.constant(s1)
            s2_img = ee.Image.constant(s2)
            trans  = img.gte(s1_img).And(img.lte(s2_img)).multiply(
                        img.subtract(s1_img).divide(s2_img.subtract(s1_img))
                    )
            return img.lt(s1_img).multiply(0) \
                    .add(img.gt(s2_img).multiply(1)) \
                    .add(trans)

        def _fuzzyZ(img, z1, z2):
            z1_img = ee.Image.constant(z1)
            z2_img = ee.Image.constant(z2)
            trans  = img.gte(z1_img).And(img.lte(z2_img)).multiply(
                        ee.Image(1).subtract(
                            img.subtract(z1_img).divide(z2_img.subtract(z1_img))
                        )
                    )
            return img.lt(z1_img).multiply(1) \
                    .add(img.gt(z2_img).multiply(0)) \
                    .add(trans)

        s1_thr = 1.05
        s2_thr = 1.20
        FM_FV = _fuzzyS(difference, s1_thr, s2_thr).rename("FM_FV").updateMask(ee.Image(1))

        # Excluir urbano
        ndbi = s2_sr.normalizedDifference(["B11", "B8"]).rename("NDBI")
        FM_FV = FM_FV.updateMask(ndbi.gt(0.2).Not())

        # Lluvia mínima
        precip_accum = chirps.sum().clip(ee_geometry)
        FM_FV = FM_FV.updateMask(precip_accum.gt(5))

        # 6) FM_OW (null-safe)
        self._step(prog, 65, "Agua histórica (GSW)…")
        low_occ_mask = occ.lt(30)
        occ_norm = occ.divide(100)

        stats = occ_norm.updateMask(occ_norm.gt(0)).reduceRegion(
            reducer=ee.Reducer.mean().combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True),
            geometry=ee_geometry, scale=30, bestEffort=True
        )
        # Si no hay píxeles de GSW en el AOI, usa defaults
        mu = ee.Number(ee.Algorithms.If(stats.contains('occurrence_mean'),
                                        stats.get('occurrence_mean'), 0))
        sigma = ee.Number(ee.Algorithms.If(stats.contains('occurrence_stdDev'),
                                           stats.get('occurrence_stdDev'), 0))
        z1_default = ee.Number(0.05)
        z2_default = ee.Number(0.30)
        z1_ow = ee.Number(ee.Algorithms.If(mu.add(sigma).eq(0), z1_default, mu))
        z2_ow = ee.Number(ee.Algorithms.If(mu.add(sigma).eq(0),
                                           z2_default,
                                           mu.add(sigma.multiply(2))))
        z1_ow = z1_ow.max(0).min(1)
        z2_ow = z2_ow.max(0).min(1)

        FM_OW = _fuzzyZ(occ_norm, z1_ow, z2_ow).updateMask(low_occ_mask).rename("FM_OW").clip(ee_geometry)

        # Mezcla T=500 si aplica
        if date_str == '2024-10-29':
            q500_v = ee.FeatureCollection('projects/tidop-424613/assets/TIDOP/T500_v')
            q500_m = ee.FeatureCollection('projects/tidop-424613/assets/TIDOP/T500_m')
            q500_v_img = ee.Image().byte().paint(featureCollection=q500_v, color=1).rename('Q500_v').selfMask()
            q500_m_img = ee.Image().byte().paint(featureCollection=q500_m, color=1).rename('Q500_m').selfMask()
            FM_OW = FM_OW.blend(q500_v_img).blend(q500_m_img).clip(ee_geometry)

        # 7) Conectividad y fusión
        self._step(prog, 78, "Conectividad hidráulica y fusión…")
        FM1 = FM_FV.max(FM_OW).rename('FM1')

        terrain = ee.Algorithms.Terrain(dem)
        slope   = terrain.select('slope')
        FM_HD = _fuzzyZ(slope, 0, 5).clip(ee_geometry).rename('FM_HD').updateMask(ee.Image(1))

        w1, w2 = 6, 1
        FM2 = (FM1.updateMask(FM1.gt(0.8)).multiply(w1).add(FM_HD.multiply(w2))).divide(w1 + w2).rename('FM2')

        # 8) Contexto espacial
        self._step(prog, 85, "Contexto espacial…")
        kernel = ee.Kernel.square(radius=5)
        mean_context = FM2.reduceNeighborhood(reducer=ee.Reducer.mean(), kernel=kernel)
        D = FM2.subtract(mean_context).rename('D')
        FM3 = _fuzzyZ(D, -0.2, 0.2).multiply(FM2).rename('FM3')

        # 9) Binario final
        flooded     = FM3.multiply(FM_FV).rename('flooded')
        flooded_bin = flooded.gt(0).selfMask().rename('FloodedBin')

        # 10) Área (null-safe)
        self._step(prog, 92, "Calculando área…")
        flooded_area_img = flooded_bin.multiply(ee.Image.pixelArea())
        flooded_dict = flooded_area_img.reduceRegion(
            reducer=ee.Reducer.sum(), geometry=ee_geometry, scale=10, maxPixels=1e13
        )
        raw_area = flooded_dict.get('FloodedBin')
        area_ha  = ee.Algorithms.If(raw_area, ee.Number(raw_area).divide(10000), 0)
        area_ha_value = float(ee.Number(area_ha).getInfo())

        # 11) Publicación
        self._step(prog, 96, "Generando teselas…")
        viz_params = {'min': 0, 'max': 1, 'palette': ['blue']}
        tile_fetcher = flooded_bin.getMapId(viz_params)["tile_fetcher"]
        xyz_url = tile_fetcher.url_format

        uri = f"type=xyz&url={xyz_url}&zmin=0&zmax=22"
        layer_name = "Áreas Inundadas"
        layer = QgsRasterLayer(uri, layer_name, "wms")
        if not layer.isValid():
            raise RuntimeError("No se pudo crear la capa XYZ desde Earth Engine.")
        QgsProject.instance().addMapLayer(layer)

        return area_ha_value
