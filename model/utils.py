import ee

# 2. FUNCIONES DE ENTRADA
# Enmascarar Nubes
def mask_s2_clouds(image):
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)


# Funciones difusas Z(Inversa) y S(Directa)
def fuzzyZ(img, z1, z2):
    z1 = ee.Image.constant(z1)
    z2 = ee.Image.constant(z2)

    mask = img.gte(z1).And(img.lte(z2))
    transition = mask.multiply(
        ee.Image(1).subtract(img.subtract(z1).divide(z2.subtract(z1)))
    )

    result = img.lt(z1).multiply(1).add(img.gt(z2).multiply(0)).add(transition)

    return result

def fuzzyS(img, s1, s2):
    s1 = ee.Image.constant(s1)
    s2 = ee.Image.constant(s2)

    mask = img.gte(s1).And(img.lte(s2))
    transition = mask.multiply(img.subtract(s1).divide(s2.subtract(s1)))

    result = img.lt(s1).multiply(0).add(img.gt(s2).multiply(1)).add(transition)

    return result

def mask_edge(image):
  edge = image.lt(-30.0)
  masked_image = image.mask().And(edge.Not())
  return image.updateMask(masked_image)