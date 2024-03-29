import numpy as np

from constants import NUM_GONDOLA, NUM_SHELF, NUM_PLATE
from cpsdriver.codec import Product
from data.position import Position

from utils.product_utils import get_product_by_id


def load_planogram(planogram_cursor, products_cursor, products_cache):
    planogram = np.empty((NUM_GONDOLA, NUM_SHELF, NUM_PLATE), dtype=object)
    product_ids_from_planogram_table = set()

    for item in planogram_cursor:

        if "id" not in item["planogram_product_id"]:
            continue
        product_id = item["planogram_product_id"]["id"]
        if product_id == "":
            continue
        product_item = products_cursor.find_one(
            {
                "product_id.id": product_id,
            }
        )
        product = Product.from_dict(product_item)
        if product.weight == 0.0:
            continue

        product_extended = get_product_by_id(product_id, products_cache)
        for plate in item["plate_ids"]:
            shelf = plate["shelf_id"]
            gondola = shelf["gondola_id"]
            gondola_id = gondola["id"]
            shelf_id = shelf["shelf_index"]
            plate_id = plate["plate_index"]

            if planogram[gondola_id - 1][shelf_id - 1][plate_id - 1] is None:
                planogram[gondola_id - 1][shelf_id - 1][plate_id - 1] = set()
            planogram[gondola_id - 1][shelf_id - 1][plate_id - 1].add(product_id)
            product_ids_from_planogram_table.add(product_id)

            product_extended.positions.add(Position(gondola_id, shelf_id, plate_id))

    return planogram
