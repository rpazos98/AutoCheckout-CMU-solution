# from cpsdriver.codec import DocObjectCodec
import datetime
import json
import os
from pathlib import Path

from PIL.ImageOps import crop
from pymongo import MongoClient

from computations.book_keeper import BookKeeper
from computations.score_calculator import *
from computations.weight_trigger import WeightTrigger
from constants import (
    VERBOSE,
    ASSOCIATION_TYPE,
    CE_ASSOCIATION,
    CLOSEST_ASSOCIATION,
)
from cpsdriver.codec import Targets, DocObjectCodec
from utils.coordinate_utils import get_3d_coordinates_for_plate
from utils.planogram_utils import load_planogram
from utils.product_utils import (
    build_all_products_cache,
    get_product_ids_from_position_3d,
    get_product_ids_from_position_2d,
    get_product_by_id,
)
from utils.store_meta_utils import build_dicts_from_store_meta
from utils.target_association_utils import (
    associate_product_ce,
    associate_product_closest,
    associate_product_naive,
)
from utils.time_utils import get_test_start_time

PUTBACK_JITTER_RATE = 0.75
GRAB_FROM_SHELF_JITTER_RATE = 0.4


class CustomerReceipt:
    """
    checkIn/Out (datetime): time when customer enters/leaves the store
    customerID (String): identify of each customer
    purchaseList (Dict):
        KEY: product ID
        Value: (product, quantities)
    target (BK.Target): Target object for this customer
    """

    def __init__(self, customer_id):
        self.customerID = customer_id
        # productID -> (product, num_product)
        self.purchaseList = {}

    def purchase(self, product, num_product):
        product_id = product.product_id.barcode
        if product_id in self.purchaseList:
            product, quantity = self.purchaseList[product_id]
            self.purchaseList[product_id] = (product, quantity + num_product)
        else:
            self.purchaseList[product_id] = (product, num_product)

    def putback(self, product, num_product):
        product_id = product.product
        if product_id in self.purchaseList:
            product, quantity = self.purchaseList[product_id]
            if quantity > num_product:
                self.purchaseList[product_id] = (product, quantity - num_product)
            else:
                del self.purchaseList[product_id]


"""
Cashier class to generate receipts
"""

SHOULD_GRAPH = False


def process(db_name):
    with open("src/main/resources/store_meta/Gondolas.json") as f:
        gondolas_meta = json.load(f)["gondolas"]
    with open("src/main/resources/store_meta/Shelves.json") as f:
        shelves_meta = json.load(f)["shelves"]
    with open("src/main/resources/store_meta/Plates.json") as f:
        plates_meta = json.load(f)["plates"]

    # Access instance DB
    _mongoClient = MongoClient("mongodb://localhost:27017")
    db = _mongoClient[db_name]

    # Reference to DB collections
    planogram_cursor = db["planogram"].find()
    products_cursor = db["products"]
    plate_cursor = db["plate_data"]
    targets_cursor = db["full_targets"]
    if targets_cursor.count() == 0:
        targets_cursor = db["targets"]
    frame_cursor = db["frame_message"]

    products_cache, product_ids_from_products_table = build_all_products_cache(
        products_cursor
    )
    planogram = load_planogram(planogram_cursor, products_cursor, products_cache)
    gondolas_dict, shelves_dict, plates_dict = build_dicts_from_store_meta(
        gondolas_meta, shelves_meta, plates_meta
    )

    bookkeeper = BookKeeper(
        planogram,
        lambda x: targets_cursor.find(x),
        lambda x: frame_cursor.find(x),
        product_ids_from_products_table,
        gondolas_dict,
        shelves_dict,
        plates_dict,
    )

    weight_trigger = WeightTrigger(
        get_test_start_time(plate_cursor, db_name),
        list(
            map(
                lambda x: DocObjectCodec.decode(doc=x, collection="plate_data"),
                plate_cursor.find(),
            )
        ),
        (lambda x, y: get_product_ids_from_position_2d(x, y, planogram)),
        (lambda x, y, z: get_product_ids_from_position_3d(x, y, z, planogram)),
        lambda x: get_product_by_id(x, products_cache),
        (
            lambda x, y, z: get_3d_coordinates_for_plate(
                x, y, z, gondolas_dict, shelves_dict, plates_dict
            )
        ),
    )

    (
        weight_shelf_mean,
        weight_shelf_std,
        weight_plate_mean,
        weight_plate_std,
    ) = weight_trigger.get_moving_weight()

    number_gondolas = len(weight_shelf_mean)
    # reduce timestamp
    timestamps = weight_trigger.get_agg_timestamps()
    for i in range(number_gondolas):
        timestamps[i] = timestamps[i][30:-29]

    # sanity check
    for i in range(number_gondolas):
        timestamps_count = len(timestamps[i])
        assert timestamps_count == weight_shelf_mean[i].shape[1]
        assert timestamps_count == weight_shelf_std[i].shape[1]
        assert timestamps_count == weight_plate_mean[i].shape[2]
        assert timestamps_count == weight_plate_std[i].shape[2]

    events = weight_trigger.detect_weight_events(
        weight_shelf_mean,
        weight_shelf_std,
        weight_plate_mean,
        timestamps,
    )
    events = weight_trigger.splitEvents(events)
    events.sort(key=lambda pick_up_event: pick_up_event.triggerBegin)

    # dictionary recording all receipts
    # KEY: customer ID, VALUE: CustomerReceipt
    receipts = {}
    print("Capture {} events in the database {}".format(len(events), db_name))
    print("==============================================================")
    for event in events:
        if VERBOSE:
            print("----------------")
            print("Event: ", event)

        absolute_pos = event.get_event_coordinates()
        targets = bookkeeper.get_targets_for_event(event)
        # Initliaze a customer receipt for all new targets
        for target_id in targets.keys():
            if target_id not in receipts:
                customer_receipt = CustomerReceipt(target_id)
                receipts[target_id] = customer_receipt

        # No target for the event found at all
        if len(targets) == 0:
            continue

        if ASSOCIATION_TYPE == CE_ASSOCIATION:
            target_id, _ = associate_product_ce(absolute_pos, targets)
        elif ASSOCIATION_TYPE == CLOSEST_ASSOCIATION:
            target_id, _ = associate_product_closest(absolute_pos, targets)
        else:
            target_id, _ = associate_product_naive(absolute_pos, targets)

        isPutbackEvent = False
        if event.deltaWeight > 0:
            isPutbackEvent = True
            # get all products pickedup by this target
            if target_id not in receipts:
                continue
            customer_receipt = receipts[target_id]
            purchase_list = (
                customer_receipt.purchaseList
            )  # productID -> (product_extendend, num_product)

            # find most possible putback product_extendend whose weight is closest to the event weight
            candidate_products = []
            for item in purchase_list.values():
                product_extendend, num_product = item
                for count in range(1, num_product + 1):
                    candidate_products.append((product_extendend, count))

            if len(candidate_products) == 0:
                continue
            # item = (product_extendend, count)
            candidate_products.sort(
                key=lambda item: abs(item[0].weight * item[1] - event.deltaWeight)
            )
            product_extendend, putback_count = candidate_products[0]

            # If weight difference is too large, ignore this event
            if abs(event.deltaWeight) < PUTBACK_JITTER_RATE * product_extendend.weight:
                continue

            # Put the product_extendend on the shelf will affect planogram
            bookkeeper.add_product(
                event.get_event_all_positions(bookkeeper), product_extendend
            )
        else:
            score_calculator = ScoreCalculator(
                event, planogram, products_cache, product_ids_from_products_table
            )
            top_product_score = score_calculator.get_top_k(1)[0]
            if VERBOSE:
                print("top 5 predicted products:")
                for productScore in score_calculator.get_top_k(5):
                    print(productScore)

            top_product_extended = get_product_by_id(
                top_product_score.product.product.product_id.barcode, products_cache
            )

            product_extendend = top_product_extended

            # If deltaWeight is too small compared to the predicted product_extendend, ignore this event
            if (
                abs(event.deltaWeight)
                < GRAB_FROM_SHELF_JITTER_RATE * product_extendend.product.weight
            ):
                continue
        productID = product_extendend.product

        ################################ Update receipt records ################################
        # New customer, create a new receipt
        if target_id not in receipts:
            customer_receipt = CustomerReceipt(target_id)
            receipts[target_id] = customer_receipt
        # Existing customer, update receipt
        else:
            customer_receipt = receipts[target_id]

        if isPutbackEvent:
            # Putback count from previous step
            pred_quantity = putback_count
        else:
            # Predict quantity from delta weight
            pred_quantity = max(
                int(round(abs(event.deltaWeight / product_extendend.product.weight))),
                1,
            )
            customer_receipt.purchase(product_extendend.product, pred_quantity)

        if VERBOSE:
            print(
                "Predicted: [%s][putback=%d] %s, weight=%dg, count=%d, thumbnail=%s"
                % (
                    product_extendend.product,
                    isPutbackEvent,
                    product_extendend.name,
                    product_extendend.weight,
                    pred_quantity,
                    product_extendend.thumbnail,
                )
            )
        else:
            print(
                "Predicted: [%s][putback=%d] %s, weight=%dg, count=%d"
                % (
                    product_extendend.product,
                    isPutbackEvent,
                    product_extendend.product.name,
                    product_extendend.product.weight,
                    pred_quantity,
                )
            )

    ################ Display all receipts ################
    if VERBOSE:
        num_receipt = 0
        if len(receipts) == 0:
            print("No receipts!")
            return {}

        for id, customer_receipt in receipts.items():
            print("============== Receipt {} ==============".format(num_receipt))
            print("Customer ID: " + id)
            print("Purchase List: ")
            for _, entry in customer_receipt.purchaseList.items():
                product_extendend, quantity = entry
                print(
                    "*Name: "
                    + product_extendend.name
                    + ", Quantities: "
                    + str(quantity),
                    product_extendend.thumbnail,
                    product_extendend.product,
                )
            num_receipt += 1
    return receipts
