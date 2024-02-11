import io
import json
import os

from PIL import Image

import GroundTruth as GT
from Constants import INCH_TO_METER
from Coordinates import Coordinates
from Target import Target
from config import *
from cpsdriver import codec
from cpsdriver.codec import DocObjectCodec


class BookKeeper:
    def __init__(
        self,
        dbname,
        planogram,
        products_cursor,
        plate_cursor,
        targets_cursor,
        frame_cursor,
        products_id_from_products_table,
    ):
        # Access instance DB
        self.__dbname = dbname

        # Reference to DB collections
        self.products_cursor = products_cursor  # find one y find
        self.plate_cursor = plate_cursor  # find one
        self.targets_cursor = targets_cursor  # find con filtro
        self.frame_cursor = frame_cursor  # find con filtro

        ## puedo meter un find con parametros opcionales y

        self._planogram = planogram
        self._productsCache = {}

        # store meta
        self._gondolasDict = {}
        self._shelvesDict = {}
        self._platesDict = {}

        self.productIDsFromPlanogramTable = set()
        self.productIDsFromProductsTable = products_id_from_products_table

        self._buildDictsFromStoreMeta()

    def addProduct(self, positions, productExtended):
        for position in positions:
            gondolaID, shelfID, plateID = (
                position.gondola,
                position.shelf,
                position.plate,
            )
            self._planogram[gondolaID - 1][shelfID - 1][plateID - 1].add(
                productExtended.product
            )
            # Update product position
            if position not in productExtended.positions:
                productExtended.positions.add(position)

    def getFramesForEvent(self, event):
        timeBegin = event.triggerBegin
        timeEnd = event.triggerEnd
        frames = {}
        # TODO: date_time different format in test 2
        framesCursor = self.frame_cursor.find(
            {"timestamp": {"$gte": timeBegin, "$lt": timeEnd}}
        )

        for frameDoc in framesCursor:
            cameraID = frameDoc["camera_id"]
            if cameraID not in frames:
                frames[cameraID] = frameDoc
            else:
                if frames[cameraID]["date_time"] <= frameDoc["date_time"]:
                    # pick an earlier frame for this camera
                    frames[cameraID] = frameDoc

        for frameKey in frames:
            # print("Frame Key (camera ID) is: ", frameKey)
            rgbFrame = DocObjectCodec.decode(frames[frameKey], "frame_message")
            imageStream = io.BytesIO(rgbFrame.frame)
            im = Image.open(imageStream)
            frames[frameKey] = im
        if VERBOSE:
            print("Capture {} camera frames in this event".format(len(frames)))
        return frames

    """
    Function to get a frame Image from the database
    Input:
        timestamp: double/string
        camera_id: int/string, if camera id is not specified, returns all the image with camera IDs
    Output:
        (with camera ID) PIL Image: Image object RGB format
        (without camera ID): dictionary {camera_id: PIL Image}
    """

    def getFrameImage(self, timestamp, camera_id=None):
        if camera_id is not None:
            framesCursor = self.frame_cursor.find(
                {"timestamp": float(timestamp), "camera_id": int(camera_id)}
            )
            # One timestamp should corresponds to only one frame
            if framesCursor.count() == 0:
                return None
            item = framesCursor[0]
            rgb = DocObjectCodec.decode(doc=item, collection="frame_message")
            imageStream = io.BytesIO(rgb.frame)
            im = Image.open(imageStream)
            return im
        else:
            image_dict = {}
            framesCursor = self.frame_cursor.find(
                {
                    "timestamp": float(timestamp),
                }
            )
            if framesCursor.count() == 0:
                return None
            for item in framesCursor:
                # print("Found image with camera id: ", item['camera_id'])
                camera_id = item["camera_id"]
                rgb = codec.DocObjectCodec.decode(doc=item, collection="frame_message")
                imageStream = io.BytesIO(rgb.frame)
                im = Image.open(imageStream)
                image_dict[camera_id] = im
            return image_dict

    """
    Function to get lastest targets for an event
    Input:
        event
    Output:
        List[target]: all the in-store target during this event period
    """

    def getTargetsForEvent(self, event):
        timeBegin = event.triggerBegin
        timeEnd = event.triggerEnd
        targetsCursor = self.targets_cursor.find(
            {"timestamp": {"$gte": timeBegin, "$lt": timeEnd}}
        )
        # print("Duration: ", timeBegin, timeEnd)
        # Sort the all targets entry in a timely order
        targetsCursor.sort([("timestamp", 1)])
        targets = {}
        num_timestamps = targetsCursor.count()
        for i, targetDoc in enumerate(targetsCursor):
            if "targets" not in targetDoc["document"]["targets"]:
                continue
            target_list = targetDoc["document"]["targets"]["targets"]
            for target in target_list:
                target_id = target["target_id"]["id"]
                valid_entrance = target["target_state"] == "TARGETSTATE_VALID_ENTRANCE"
                # Head
                head = None
                if "head" in target:
                    if len(target["head"]["point"]) != 0:
                        x, y, z = (
                            target["head"]["point"]["x"],
                            target["head"]["point"]["y"],
                            target["head"]["point"]["z"],
                        )
                        score = target["head"]["score"]
                        coordinate = Coordinates(
                            x * INCH_TO_METER, y * INCH_TO_METER, z * INCH_TO_METER
                        )
                        head = {"position": coordinate, "score": score}
                left_hand, right_hand = None, None
                if CE_ASSOCIATION and "l_wrist" in target and "r_wrist" in target:
                    # Left hand
                    if len(target["l_wrist"]["point"]) != 0:
                        lh_x, lh_y, lh_z = (
                            target["l_wrist"]["point"]["x"],
                            target["l_wrist"]["point"]["y"],
                            target["l_wrist"]["point"]["z"],
                        )
                        lh_score = target["l_wrist"]["score"]
                        lh_coordinate = Coordinates(
                            lh_x * INCH_TO_METER,
                            lh_y * INCH_TO_METER,
                            lh_z * INCH_TO_METER,
                        )
                        left_hand = {"position": lh_coordinate, "score": lh_score}
                    else:
                        left_hand = None
                    # Right
                    if len(target["r_wrist"]["point"]) != 0:
                        rh_x, rh_y, rh_z = (
                            target["r_wrist"]["point"]["x"],
                            target["r_wrist"]["point"]["y"],
                            target["r_wrist"]["point"]["z"],
                        )
                        rh_score = target["r_wrist"]["score"]
                        rh_coordinate = Coordinates(
                            rh_x * INCH_TO_METER,
                            rh_y * INCH_TO_METER,
                            rh_z * INCH_TO_METER,
                        )
                        right_hand = {"position": rh_coordinate, "score": rh_score}
                    else:
                        right_hand = None

                if target_id not in targets:
                    # Create new target during this period
                    targets[target_id] = Target(
                        target_id, head, left_hand, right_hand, valid_entrance
                    )
                else:
                    # Update existing target
                    targets[target_id].update(
                        target_id, head, left_hand, right_hand, valid_entrance
                    )
            # print(i, num_timestamps, targetDoc['timestamp'])
            # print(targets.items())
            if i > num_timestamps / 2:
                # print("Trigger duration ", datetime.fromtimestamp(timeBegin), datetime.fromtimestamp(timeEnd))
                # print("Peak time ", datetime.fromtimestamp(event.peakTime))
                # print(timeBegin, event.peakTime, timeEnd)
                # print("Break at date time: ", targetDoc['date_time'])
                break
            if targetDoc["timestamp"] > event.peakTime:
                break
        # print("Event timestamp: ", targetDoc['timestamp'], head)
        if VERBOSE:
            print(
                "Targets: Capture {} targets in this event".format(len(targets)),
                targets.keys(),
            )
        return targets

    def _findOptimalPlateForEvent(self, event):
        return 1

    def get3DCoordinatesForPlate(self, gondola, shelf, plate):
        gondolaMetaKey = str(gondola)
        shelfMetaKey = str(gondola) + "_" + str(shelf)
        plateMetaKey = str(gondola) + "_" + str(shelf) + "_" + str(plate)

        # TODO: rotation values for one special gondola
        absolute3D = Coordinates(0, 0, 0)
        gondolaTranslation = self._getTranslation(self._gondolasDict[gondolaMetaKey])
        absolute3D.translateBy(
            gondolaTranslation["x"], gondolaTranslation["y"], gondolaTranslation["z"]
        )

        if gondola == 5:
            # rotate by 90 degrees
            shelfTranslation = self._getTranslation(self._shelvesDict[shelfMetaKey])
            absolute3D.translateBy(
                -shelfTranslation["y"], shelfTranslation["x"], shelfTranslation["z"]
            )

            plateTranslation = self._getTranslation(self._platesDict[plateMetaKey])
            absolute3D.translateBy(
                -plateTranslation["y"], plateTranslation["x"], plateTranslation["z"]
            )

        else:
            shelfTranslation = self._getTranslation(self._shelvesDict[shelfMetaKey])
            absolute3D.translateBy(
                shelfTranslation["x"], shelfTranslation["y"], shelfTranslation["z"]
            )

            key_ = self._platesDict.get(plateMetaKey)
            if key_ is None:
                return absolute3D
            plateTranslation = self._getTranslation(key_)
            absolute3D.translateBy(
                plateTranslation["x"], plateTranslation["y"], plateTranslation["z"]
            )

        return absolute3D

    def _getTranslation(self, meta):
        return meta["coordinates"]["transform"]["translation"]

    def _buildDictsFromStoreMeta(self):
        for gondolaMeta in GT.gondolasMeta:
            self._gondolasDict[str(gondolaMeta["id"]["id"])] = gondolaMeta

        for shelfMeta in GT.shelvesMeta:
            IDs = shelfMeta["id"]
            gondolaID = IDs["gondola_id"]["id"]
            shelfID = IDs["shelf_index"]
            shelfMetaIndexKey = str(gondolaID) + "_" + str(shelfID)
            self._shelvesDict[shelfMetaIndexKey] = shelfMeta

        for plateMeta in GT.platesMeta:
            IDs = plateMeta["id"]
            gondolaID = IDs["shelf_id"]["gondola_id"]["id"]
            shelfID = IDs["shelf_id"]["shelf_index"]
            plateID = IDs["plate_index"]
            plateMetaIndexKey = str(gondolaID) + "_" + str(shelfID) + "_" + str(plateID)
            self._platesDict[plateMetaIndexKey] = plateMeta

    def getCleanStartTime(self):
        testCaseStartTimeJSONFilePath = "src/main/resources/TestCaseStartTime.json"
        if os.path.exists(testCaseStartTimeJSONFilePath):
            with open(testCaseStartTimeJSONFilePath, "r") as f:
                testStartTime = json.load(f)
            if self.__dbname not in testStartTime:
                return 0
            return testStartTime[self.__dbname]
        else:
            print(
                "!!!WARNING: Didn't find competition/TestCaseStartTime.json, results might not be accurate. Please run TimeTravel.py to get the json file"
            )
            return 0

    def getTestStartTime(self):
        videoStartTime = self.getCleanStartTime()
        dbStartTime = self.plate_cursor.find_one(sort=[("timestamp", 1)])["timestamp"]
        if videoStartTime - dbStartTime >= 10:
            return videoStartTime
        else:
            return 0


# class Frame:

"""
Class for customer target
Attributes:
    self.head: Coordinates. global coordinate of head position. Usage: Coordinates.x, Coordinates.y, Coordinates.z
    self.id: STRING. Identify of the target.
    self.score: FLOAT. Confidence score of the target existence.
    self.valid_entrance: BOOL. Whether this target is a valid entrance at the store.
"""
