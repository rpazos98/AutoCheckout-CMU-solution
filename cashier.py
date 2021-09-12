# from cpsdriver.codec import DocObjectCodec
import datetime
import os.path
from pathlib import Path

# import moviepy
# from moviepy.editor import *
# from moviepy.video.fx.crop import crop

from ScoreCalculate import *
from WeightTrigger import WeightTrigger as WT
from config import *
from cpsdriver.codec import Targets
from utils import *
# 0.75 might be better but its results jitter betweeen either 82.4 or 83.2???
from viz_utils import VizUtils
# import cv2
# import mediapipe as mp

PUTBACK_JITTER_RATE = 0.75
GRAB_FROM_SHELF_JITTER_RATE = 0.4


class CustomerReceipt():
    """
    checkIn/Out (datetime): time when customer enters/leaves the store
    customerID (String): identify of each customer
    purchaseList (Dict):
        KEY: product ID
        Value: (product, quantities)
    target (BK.Target): Target object for this customer
    """

    def __init__(self, customerID):
        self.customerID = customerID
        # productID -> (product, num_product)
        self.purchaseList = {}

    def purchase(self, product, num_product):
        productID = product.barcode
        if productID in self.purchaseList:
            product, quantity = self.purchaseList[productID]
            self.purchaseList[productID] = (product, quantity + num_product)
        else:
            self.purchaseList[productID] = (product, num_product)

    def putback(self, product, num_product):
        productID = product.barcode
        if productID in self.purchaseList:
            product, quantity = self.purchaseList[productID]
            if quantity > num_product:
                self.purchaseList[productID] = (product, quantity - num_product)
            else:
                del self.purchaseList[productID]


"""
Cashier class to generate receipts
"""


class Cashier():
    def __init__(self):
        pass

    def process(self, dbName):
        myBK = BK.BookKeeper(dbName)
        weightTrigger = WT(myBK)

        weight_shelf_mean, weight_shelf_std, weight_plate_mean, weight_plate_std = weightTrigger.get_moving_weight()

        number_gondolas = len(weight_shelf_mean)
        # reduce timestamp 
        timestamps = weightTrigger.get_agg_timestamps()
        for i in range(number_gondolas):
            timestamps[i] = timestamps[i][30:-29]

        # sanity check
        for i in range(number_gondolas):
            timestamps_count = len(timestamps[i])
            assert (timestamps_count == weight_shelf_mean[i].shape[1])
            assert (timestamps_count == weight_shelf_std[i].shape[1])
            assert (timestamps_count == weight_plate_mean[i].shape[2])
            assert (timestamps_count == weight_plate_std[i].shape[2])


        events = weightTrigger.detect_weight_events(weight_shelf_mean, weight_shelf_std, weight_plate_mean,
                                                    weight_plate_std, timestamps)
        events = weightTrigger.splitEvents(events)
        events.sort(key=lambda pickUpEvent: pickUpEvent.triggerBegin)

        viz = VizUtils(events, timestamps, dbName, weight_shelf_mean, weight_shelf_std, myBK)

        # dictionary recording all receipts
        # KEY: customer ID, VALUE: CustomerReceipt
        receipts = {}
        print("Capture {} events in the database {}".format(len(events), dbName))
        print("==============================================================")
        for event in events:
            if VERBOSE:
                print("----------------")
                print('Event: ', event)

            ################################ Naive Association ################################

            # absolutePos = myBK.getProductCoordinates(productID)
            absolutePos = event.getEventCoordinates(myBK)
            targets = myBK.getTargetsForEvent(event)
            if VIZ:
                viz.addEventPosition(event, absolutePos)
            # Initliaze a customer receipt for all new targets
            for target_id in targets.keys():
                if target_id not in receipts:
                    customer_receipt = CustomerReceipt(target_id)
                    receipts[target_id] = customer_receipt

            # No target for the event found at all
            if (len(targets) == 0):
                continue

            if ASSOCIATION_TYPE == CE_ASSOCIATION:
                target_id, _ = associate_product_ce(absolutePos, targets)
            elif ASSOCIATION_TYPE == CLOSEST_ASSOCIATION:
                target_id, _ = associate_product_closest(absolutePos, targets)
            else:
                target_id, _ = associate_product_naive(absolutePos, targets)

            ################################ Calculate score ################################

            # TODO: omg this is weird. might need to concatenate adjacent events
            isPutbackEvent = False
            if event.deltaWeight > 0:
                isPutbackEvent = True
                # get all products pickedup by this target
                if target_id not in receipts:
                    continue
                customer_receipt = receipts[target_id]
                purchase_list = customer_receipt.purchaseList  # productID -> (product, num_product)

                # find most possible putback product whose weight is closest to the event weight
                candidate_products = []
                for item in purchase_list.values():
                    product, num_product = item
                    for count in range(1, num_product + 1):
                        candidate_products.append((product, count))

                if (len(candidate_products) == 0):
                    continue
                # item = (product, count)
                candidate_products.sort(key=lambda item: abs(item[0].weight * item[1] - event.deltaWeight))
                product, putback_count = candidate_products[0]

                # If weight difference is too large, ignore this event
                if (abs(event.deltaWeight) < PUTBACK_JITTER_RATE * product.weight):
                    continue

                # Put the product on the shelf will affect planogram
                myBK.addProduct(event.getEventAllPositions(myBK), product)
            else:
                scoreCalculator = ScoreCalculator(myBK, event)
                topProductScore = scoreCalculator.getTopK(1)[0]
                if VERBOSE:
                    print("top 5 predicted products:")
                    for productScore in scoreCalculator.getTopK(5):
                        print(productScore)

                topProductExtended = myBK.getProductByID(topProductScore.barcode)

                product = topProductExtended

                # If deltaWeight is too small compared to the predicted product, ignore this event
                if (abs(event.deltaWeight) < GRAB_FROM_SHELF_JITTER_RATE * product.weight):
                    continue
            productID = product.barcode

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
                    customer_receipt.purchase(product,
                                              pred_quantity)  # In the evaluation code, putback is still an event, so we accumulate for debug purpose
                else:
                    customer_receipt.putback(product, pred_quantity)
            else:
                # Predict quantity from delta weight
                pred_quantity = max(int(round(abs(event.deltaWeight / product.weight))), 1)
                customer_receipt.purchase(product, pred_quantity)
            if VIZ:
                viz.addEventProduct(event, {"name": product.name, "quantity": pred_quantity, "weight": product.weight})

            if VERBOSE:
                print("Predicted: [%s][putback=%d] %s, weight=%dg, count=%d, thumbnail=%s" % (
                product.barcode, isPutbackEvent, product.name, product.weight, pred_quantity, product.thumbnail))
            else:
                print("Predicted: [%s][putback=%d] %s, weight=%dg, count=%d" % (
                product.barcode, isPutbackEvent, product.name, product.weight, pred_quantity))

        ################ Display all receipts ################
        if VERBOSE:
            num_receipt = 0
            if (len(receipts) == 0):
                print("No receipts!")
                return {}

            for id, customer_receipt in receipts.items():
                print("============== Receipt {} ==============".format(num_receipt))
                print("Customer ID: " + id)
                print("Purchase List: ")
                for _, entry in customer_receipt.purchaseList.items():
                    product, quantity = entry
                    print("*Name: " + product.name + ", Quantities: " + str(quantity), product.thumbnail,
                          product.barcode)
                num_receipt += 1
if VIZ:
            viz.graph()
        return receipts


class VideoCashier:

    def __init__(self, db_name):
        self.db_name = db_name
        self.myBK = BK.BookKeeper(db_name)
        self.db = self.myBK.db
        self.crop_dict = {"192.168.1.100_": {"x1": 1200, "y1": 0, "x2": 1740, "y2": 500},
                          "192.168.1.101_": {"x1": 500, "y1": 0, "x2": 1140, "y2": 460},
                          "192.168.1.102_": {"x1": 1390, "y1": 0, "x2": 2150, "y2": 926},
                          "192.168.1.103_": {"x1": 630, "y1": 0, "x2": 1366, "y2": 1062},
                          "192.168.1.107_": {"x1": 1096, "y1": 600, "x2": 2362, "y2": 1516},
                          "192.168.1.109_": {"x1": 670, "y1": 626, "x2": 1530, "y2": 1518},
                          "192.168.1.110_": {"x1": 68, "y1": 740, "x2": 1142, "y2": 1514}}

    def process(self):
        target_id_to_store_exit_time = self.get_store_exit_time()
        # target_id_to_relative_store_exit_time = self.transform_to_video_relative_time(target_id_to_store_exit_time)
        # target_to_clips_dir = self.create_clips(target_id_to_relative_store_exit_time)

    def get_store_exit_time(self):
        result = {}
        targets = self.db['full_targets']
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