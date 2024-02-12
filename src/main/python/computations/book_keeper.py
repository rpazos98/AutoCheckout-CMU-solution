from constants import INCH_TO_METER, CE_ASSOCIATION, VERBOSE
from data.coordinates import Coordinates
from data.target import Target


class BookKeeper:
    def __init__(
        self,
        planogram,
        targets_find,
        frame_find,
        products_id_from_products_table,
        gondolas_dict,
        shelves_dict,
        plates_dict,
    ):
        # Reference to DB collections
        self.targets_find = targets_find
        self.frame_find = frame_find

        self.planogram = planogram

        # store meta
        self._gondolasDict = gondolas_dict
        self._shelvesDict = shelves_dict
        self._platesDict = plates_dict

        self.productIDsFromProductsTable = products_id_from_products_table

    def add_product(self, positions, product_extended):
        for position in positions:
            gondola_id, shelf_id, plate_id = (
                position.gondola,
                position.shelf,
                position.plate,
            )
            self.planogram[gondola_id - 1][shelf_id - 1][plate_id - 1].add(
                product_extended.product
            )
            # Update product position
            if position not in product_extended.positions:
                product_extended.positions.add(position)

    """
    Function to get lastest targets for an event
    Input:
        event
    Output:
        List[target]: all the in-store target during this event period
    """

    def get_targets_for_event(self, event):
        time_begin = event.triggerBegin
        time_end = event.triggerEnd
        targets_cursor = self.targets_find(
            {"timestamp": {"$gte": time_begin, "$lt": time_end}}
        )
        # print("Duration: ", time_begin, time_end)
        # Sort the all targets entry in a timely order
        targets_cursor.sort([("timestamp", 1)])
        targets = {}
        num_timestamps = targets_cursor.count()
        for i, targetDoc in enumerate(targets_cursor):
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
                # print("Trigger duration ", datetime.fromtimestamp(time_begin), datetime.fromtimestamp(time_end))
                # print("Peak time ", datetime.fromtimestamp(event.peakTime))
                # print(time_begin, event.peakTime, time_end)
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
