import ee
# CONSTANTES GLOBALES
geoemtry_gsw = [
    [-9.997846154141579, 36.126099901780215],
    [3.1637749396084214, 36.126099901780215],
    [3.1637749396084214, 43.79229580945271],
    [-9.997846154141579, 43.79229580945271],
    [-9.997846154141579, 36.126099901780215],
]

# Geometria para precipitaciones
geometry_coords = [
    [-2.3428081194314876,38.963040572874135],
    [-0.11258351005648759,38.963040572874135],
    [-0.11258351005648759,40.67584834410753],
    [-2.3428081194314876,40.67584834410753],
    [-2.3428081194314876,38.963040572874135]
]

geometry_pp = ee.Geometry.Polygon(geometry_coords)

# Geometria para analisis de inundaciones
geometry_admin= (
    ee.FeatureCollection('FAO/GAUL/2015/level2')
    .filter(ee.Filter.eq('ADM0_NAME', 'Spain'))
    .filter(ee.Filter.eq('ADM2_NAME', 'Valencia/València'))
)