from cpsdriver.codec import Product
from data.product_extended import ProductExtended


def get_product_by_id(product_id, products_cache):
    if product_id in products_cache:
        return products_cache[product_id]
    return None


def build_all_products_cache(products_cursor):
    products_cache = {}
    product_ids_from_products_table = set()

    for item in products_cursor.find():
        product = Product.from_dict(item)
        if product.weight == 0.0:
            continue

        product_extended = ProductExtended(product)

        # Workaround for database error: [JD] Good catch, the real weight is 538g,
        # Our store operator made a mistake when inputing the product in :scales:
        if product_extended.get_barcode() == "898999010007":
            product_extended.weight = 538.0

        # Workaround for database error: [JD] 1064g for the large one (ACQUA PANNA PET MINERAL DRINK), 800g for the small one
        if product_extended.get_barcode() == "041508922487":
            product_extended.weight = 1064.0

        products_cache[product_extended.get_barcode()] = product_extended
        product_ids_from_products_table.add(product_extended.get_barcode())

    return products_cache, product_ids_from_products_table


def get_product_ids_from_position_2d(gondola_idx, shelf_idx, planogram):
    # remove Nones
    product_ids = set()
    for productIDSetForPlate in planogram[gondola_idx - 1][shelf_idx - 1]:
        if productIDSetForPlate is None:
            continue
        product_ids = product_ids.union(productIDSetForPlate)
    return product_ids


def get_product_ids_from_position_3d(gondola_idx, shelf_idx, plate_idx, planogram):
    return planogram[gondola_idx - 1][shelf_idx - 1][plate_idx - 1]


def get_product_positions(product_id, products_cache):
    product = get_product_by_id(product_id, products_cache)
    return product.positions
