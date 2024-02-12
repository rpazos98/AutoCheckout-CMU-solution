# from cpsdriver.codec import DocObjectCodec
from pymongo import MongoClient

# import moviepy
# from moviepy.editor import *
# from moviepy.video.fx.crop import crop

from score_calculate import *
from weight_trigger import WeightTrigger
from cpsdriver.codec import Targets, DocObjectCodec
from constants import (
    VERBOSE,
    VIZ,
    ASSOCIATION_TYPE,
    CE_ASSOCIATION,
    CLOSEST_ASSOCIATION,
)
from utils import *

# 0.75 might be better but its results jitter betweeen either 82.4 or 83.2???
from video.viz_utils import VizUtils

# import cv2
# import mediapipe as mp

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
    events.sort(key=lambda pickUpEvent: pickUpEvent.triggerBegin)

    viz = VizUtils(
        events, timestamps, db_name, weight_shelf_mean, weight_shelf_std, bookkeeper
    )

    if SHOULD_GRAPH:
        graph_weight_shelf_data(
            events, weight_shelf_mean, timestamps, db_name, "Weight Shelf Mean"
        )
        graph_weight_shelf_data(
            events, weight_shelf_std, timestamps, db_name, "Weight Shelf Standard"
        )
        # graph_weight_plate_data(events, weight_plate_mean, timestamps, dbName, "Weight Plate Mean")
        # graph_weight_plate_data(events, weight_plate_std, timestamps, dbName, "Weight Plate Standard")

    # dictionary recording all receipts
    # KEY: customer ID, VALUE: CustomerReceipt
    receipts = {}
    print("Capture {} events in the database {}".format(len(events), db_name))
    print("==============================================================")
    for event in events:
        if VERBOSE:
            print("----------------")
            print("Event: ", event)

        ################################ Naive Association ################################

        absolute_pos = event.get_event_coordinates()
        targets = bookkeeper.get_targets_for_event(event)
        if VIZ:
            viz.addEventPosition(event, absolute_pos)
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

        ################################ Calculate score ################################

        # TODO: omg this is weird. might need to concatenate adjacent events
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
            if DEBUG:
                customer_receipt.purchase(
                    product_extendend, pred_quantity
                )  # In the evaluation code, putback is still an event, so we accumulate for debug purpose
            else:
                customer_receipt.putback(product_extendend, pred_quantity)
        else:
            # Predict quantity from delta weight
            pred_quantity = max(
                int(round(abs(event.deltaWeight / product_extendend.product.weight))),
                1,
            )
            customer_receipt.purchase(product_extendend.product, pred_quantity)
        if VIZ:
            viz.addEventProduct(
                event,
                {
                    "name": product_extendend.name,
                    "quantity": pred_quantity,
                    "weight": product_extendend.weight,
                },
            )

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
        if VIZ:
            viz.graph()
    return receipts


class VideoCashier:
    def __init__(self, db_name):
        self.db_name = db_name
        self.myBK = BK.BookKeeper(db_name)
        self.db = self.myBK.db
        self.crop_dict = {
            "192.168.1.100_": {"x1": 1200, "y1": 0, "x2": 1740, "y2": 500},
            "192.168.1.101_": {"x1": 500, "y1": 0, "x2": 1140, "y2": 460},
            "192.168.1.102_": {"x1": 1390, "y1": 0, "x2": 2150, "y2": 926},
            "192.168.1.103_": {"x1": 630, "y1": 0, "x2": 1366, "y2": 1062},
            "192.168.1.107_": {"x1": 1096, "y1": 600, "x2": 2362, "y2": 1516},
            "192.168.1.109_": {"x1": 670, "y1": 626, "x2": 1530, "y2": 1518},
            "192.168.1.110_": {"x1": 68, "y1": 740, "x2": 1142, "y2": 1514},
        }

    def process(self):
        target_id_to_store_exit_time = self.get_store_exit_time()
        # target_id_to_relative_store_exit_time = self.transform_to_video_relative_time(target_id_to_store_exit_time)
        # target_to_clips_dir = self.create_clips(target_id_to_relative_store_exit_time)

    def get_store_exit_time(self):
        result = {}
        targets = self.db["full_targets"]
        for item in targets.find():
            if item["document"]["targets"]:
                in_memory_targets = Targets.from_dict(item)
                for target in in_memory_targets.targets:
                    result[target.target_id] = in_memory_targets.timestamp
        return result

    # def transform_to_video_relative_time(self, target_id_to_store_exit_time):
    #     result = {}
    #     start_time = datetime.datetime.fromtimestamp(self.myBK.getCleanStartTime())
    #     for key in target_id_to_store_exit_time.keys():
    #         timestamp = target_id_to_store_exit_time[key]
    #         datetimed_timestamp = datetime.datetime.fromtimestamp(timestamp)
    #         seconds = datetimed_timestamp - start_time
    #         result[key] = seconds
    #     return result

    # def create_clips(self, target_id_to_relative_store_exit_time):
    #     path = './videos/{}'.format(self.db_name)
    #     read_path = Path(path).resolve()
    #     videos = os.listdir(str(read_path))
    #     result = {}
    #     for target in target_id_to_relative_store_exit_time.keys():
    #         save_path = os.path.join(str(read_path), "targets/{}".format(target))
    #         Path(save_path).mkdir(parents=True, exist_ok=True)
    #         exit_time = target_id_to_relative_store_exit_time[target]
    #         result[target] = save_path
    #         for video in videos:
    #             if self.should_generate_video(video):
    #                 video_path = os.path.join(str(read_path), video)
    #                 start = exit_time - datetime.timedelta(seconds=1)
    #                 end = exit_time
    #                 clip = VideoFileClip(video_path).subclip(str(start), str(end))
    #                 # Missing video trimming
    #                 crop_limits = self.get_crop_limits(video)
    #                 clip = crop(clip, x1=crop_limits["x1"], y1=crop_limits["y1"], x2=crop_limits["x2"],
    #                             y2=crop_limits["y2"])
    #                 save_clip_path = os.path.join(save_path, video)
    #                 clip.write_videofile(save_clip_path)
    #                 # self.add_pose(save_clip_path)
    #     return result

    def get_crop_limits(self, video):
        for key in self.crop_dict.keys():
            if key in video:
                return self.crop_dict[key]

    def should_generate_video(self, video):
        for key in self.crop_dict.keys():
            if key in video:
                return True
        return False

    # def add_pose(self, save_clip_path):
    #     mp_drawing = mp.solutions.drawing_utils
    #     mp_pose = mp.solutions.pose
    #     cap = cv2.VideoCapture(save_clip_path)
    #     pose = mp_pose.Pose()
    #
    #     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    #     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    #
    #     writer = cv2.VideoWriter("{}-pose.mp4".format(save_clip_path), cv2.VideoWriter_fourcc(*'DIVX'), 20,
    #                              (width, height))
    #     while True:
    #         ret, frame = cap.read()
    #         if not ret:
    #             break
    #         frame = cv2.flip(frame, 1)
    #         height, width, _ = frame.shape
    #         frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    #         results = pose.process(frame_rgb)
    #         if results.pose_landmarks is not None:
    #             mp_drawing.draw_landmarks(
    #                 frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
    #                 mp_drawing.DrawingSpec(color=(128, 0, 250), thickness=2, circle_radius=3),
    #                 mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2))
    #         cv2.imshow("Frame", frame)
    #         writer.write(frame)
    #         if cv2.waitKey(1) & 0xFF == 27:
    #             break
    #     cap.release()
    #     writer.release()
    #     cv2.destroyAllWindows()
