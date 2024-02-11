from Position import Position
from cpsdriver.codec import Product
from math_utils import *
from Constants import NUM_GONDOLA, NUM_SHELF, NUM_PLATE
from ProductExtended import ProductExtended

BODY_THRESH = 0.8

"""
Helper functions to associate targets to a product with head ONLY
Input:
    product_loc: Coordinates of product location (global coordinate)
    targets: Dictionary of target IDs and Target object
Returns:
    id (String): result target id
    target (Target object): result Target object
"""


def associate_product_naive(product_loc, targets):
    result_id = None
    result_target = None
    min_dist = float("inf")
    for id, target in targets.items():
        distance = calculate_distance3D(target.head["position"], product_loc)
        # print("Distance for target: ", id, "is: ", str(distance))
        if distance < min_dist:
            result_id = id
            result_target = target
            min_dist = distance
    # print("Result ID: ", result_id)
    return result_id, result_target


"""
Helper functions to associate targets to a product with head and hands
Input:
    product_loc: Coordinates of product location (global coordinate)
    targets: Dictionary of target IDs and Target object
Returns:
    id (String): result target id
    target (Target object): result Target object
"""


def associate_product_ce(product_loc, targets):
    result_id = None
    result_target = None
    min_dist = float("inf")
    for id, target in targets.items():
        ce_distance = 0
        total_score = 0
        if target.head is not None:
            head, hscore = target.head["position"], target.head["score"]
            ce_distance += calculate_distance3D(head, product_loc) * hscore
            total_score += hscore
        if target.left_hand is not None:
            left_hand, lscore = target.left_hand["position"], target.left_hand["score"]
            ce_distance += calculate_distance3D(left_hand, product_loc) * lscore
            total_score += lscore
        if target.right_hand is not None:
            right_hand, rscore = (
                target.right_hand["position"],
                target.right_hand["score"],
            )
            ce_distance += calculate_distance3D(right_hand, product_loc) * rscore
            total_score += rscore
        if total_score == 0:
            ce_distance = float("inf")
        else:
            ce_distance /= total_score

        # print("Distance for target: ", id, "is: ", str(ce_distance))
        if ce_distance <= min_dist:
            result_id = id
            result_target = target
            min_dist = ce_distance
    # print("Result ID: ", result_id)
    return result_id, result_target


"""
Helper functions to associate targets to a product with the possible closest body part
Input:
    product_loc: Coordinates of product location (global coordinate)
    targets: Dictionary of target IDs and Target object
Returns:
    id (String): result target id
    target (Target object): result Target object
"""


def associate_product_closest(product_loc, targets):
    result_id = None
    result_target = None
    min_dist = float("inf")
    for id, target in targets.items():
        closest_dist = float("inf")
        if target.head is not None:
            head, score = target.head["position"], target.head["score"]
            # print("head dist", calculate_distance3D(head, product_loc), "score", score)
            if score > BODY_THRESH:
                closest_dist = min(
                    calculate_distance3D(head, product_loc), closest_dist
                )
        if target.left_hand is not None:
            left_hand, score = target.left_hand["position"], target.left_hand["score"]
            # print("left_hand dist", calculate_distance3D(left_hand, product_loc), "score", score)
            if score > BODY_THRESH:
                closest_dist = min(
                    calculate_distance3D(left_hand, product_loc), closest_dist
                )
        if target.right_hand is not None:
            right_hand, score = (
                target.right_hand["position"],
                target.right_hand["score"],
            )
            # print("right_hand dist", calculate_distance3D(right_hand, product_loc), "score", score)
            if score > BODY_THRESH:
                closest_dist = min(
                    calculate_distance3D(right_hand, product_loc), closest_dist
                )

        # print("Closest distance for target: ", id, "is: ", str(closest_dist))
        if closest_dist <= min_dist:
            result_id = id
            result_target = target
            min_dist = closest_dist
    # print("Result ID: ", result_id)
    if not result_id or not result_target:
        result_id, result_target = targets.items[0]
    return result_id, result_target


def init_1D_array(dim):
    array = np.array([None for i in range(dim)], dtype=object)
    for i in range(dim):
        array[i] = []
    return array


# [gondola, shelf, ts]
def init_2D_array(dim1, dim2):
    array = np.array([[None for j in range(dim2)] for i in range(dim1)], dtype=object)
    for i in range(dim1):
        for j in range(dim2):
            array[i][j] = []
    return array


# [gondola, shelf, plate_id, ts]
def init_3D_array(dim1, dim2, dim3):
    array = np.array(
        [[[None for k in range(dim3)] for j in range(dim2)] for i in range(dim1)],
        dtype=object,
    )
    for i in range(dim1):
        for j in range(dim2):
            for k in range(dim3):
                array[i][j][k] = []
    return array


def rolling_window(a, window):
    shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
    strides = a.strides + (a.strides[-1],)
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)


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