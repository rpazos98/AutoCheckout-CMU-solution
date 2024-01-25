import numpy as np

from cpsdriver.codec import DocObjectCodec
from PickupEvents import PickUpEvent
from utils import init_1D_array, rolling_window


class WeightTrigger:

    # full event trigger: to get all event triggers from the current database
    # results: a list of events including their information of:
    # event start and end time,
    # event start and end index,
    # weight changes in gram,
    # gondola where event happens,
    # shelf where event happens,
    # a list plates where event happens.

    def __init__(self, BK):
        self.__bk = BK
        self.db = BK.db
        self.plate_data = BK.plateDB
        (
            self.agg_plate_data,
            self.agg_shelf_data,
            self.timestamps,
        ) = self.get_agg_weight()

    # sliding window detect events
    # concentacate the data set , and use sliding window (60 data points per window)
    # moving average weight, can remove noise and reduce the false trigger caused by shake or unstable during an event

    def get_agg_weight(self, number_gondolas=5):
        plate_data = self.db["plate_data"]
        agg_plate_data = [None] * number_gondolas
        agg_shelf_data = [None] * number_gondolas
        timestamps = init_1D_array(number_gondolas)

        test_start_time = self.__bk.getTestStartTime()
        for item in plate_data.find():
            gondola_id = item["gondola_id"]
            plate_data_item = DocObjectCodec.decode(doc=item, collection="plate_data")

            timestamp = plate_data_item.timestamp  # seconds since epoch
            if timestamp < test_start_time:
                continue
            np_plate = plate_data_item.data  # [time,shelf,plate]
            np_plate = np.nan_to_num(
                np_plate, copy=True, nan=0
            )  # replace all NaN elements to 0
            np_plate = np_plate[
                :, 1:13, 1:13
            ]  # remove first line, which is always NaN elements
            if gondola_id == 2 or gondola_id == 4 or gondola_id == 5:
                np_plate[:, :, 9:12] = 0
            np_shelf = np_plate.sum(axis=2)  # [time,shelf]
            np_shelf = np_shelf.transpose()  # [shelf, time]
            np_plate = np_plate.transpose(1, 2, 0)  # [shelf,plate,time]
            if agg_plate_data[gondola_id - 1] is not None:
                agg_plate_data[gondola_id - 1] = np.append(
                    agg_plate_data[gondola_id - 1], np_plate, axis=2
                )
                agg_shelf_data[gondola_id - 1] = np.append(
                    agg_shelf_data[gondola_id - 1], np_shelf, axis=1
                )
            else:
                agg_plate_data[gondola_id - 1] = np_plate
                agg_shelf_data[gondola_id - 1] = np_shelf

            timestamps[gondola_id - 1].append(timestamp)

        return agg_plate_data, agg_shelf_data, timestamps

    def rolling_window(self, a, window):
        shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
        strides = a.strides + (a.strides[-1],)
        return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)

    def get_agg_timestamps(self, number_gondolas=5):
        agg_timestamps = init_1D_array(number_gondolas)
        for gondola_id in range(number_gondolas):
            for i, date_time in enumerate(self.timestamps[gondola_id]):
                if i < len(self.timestamps[gondola_id]) - 1:
                    next_date_time = self.timestamps[gondola_id][i + 1]
                    time_delta = (next_date_time - date_time) / 12
                    agg_timestamps[gondola_id] += [
                        date_time + time_delta * j for j in range(0, 12)
                    ]
                else:
                    time_delta = 1 / 60
                    agg_timestamps[gondola_id] += [
                        date_time + time_delta * j for j in range(0, 12)
                    ]
        return agg_timestamps

    def get_moving_weight(self, num_gondola=5, window_size=60):
        moving_weight_plate_mean = []
        moving_weight_plate_std = []
        moving_weight_shelf_mean = []
        moving_weight_shelf_std = []
        for gondola_id in range(num_gondola):
            if self.agg_shelf_data[gondola_id] is None:
                continue
            moving_weight_shelf_mean.append(
                np.mean(
                    rolling_window(self.agg_shelf_data[gondola_id], window_size),
                    -1,
                )
            )
            moving_weight_shelf_std.append(
                np.std(
                    rolling_window(self.agg_shelf_data[gondola_id], window_size),
                    -1,
                )
            )
            moving_weight_plate_mean.append(
                np.mean(
                    rolling_window(self.agg_plate_data[gondola_id], window_size),
                    -1,
                )
            )
            moving_weight_plate_std.append(
                np.std(
                    rolling_window(self.agg_plate_data[gondola_id], window_size),
                    -1,
                )
            )
        return (
            moving_weight_shelf_mean,
            moving_weight_shelf_std,
            moving_weight_plate_mean,
            moving_weight_plate_std,
        )

    # detect events from weight trigger

    # return a list of events in the whole database, including the details of the events:
    # trigger_begin, trigger_end, n_begin, n_end, delta_weight, gondola, shelf, plates

    # active state: use variance, i.e. when variance is larger than the given threshold
    # valid active interval: based on how long the active state is, i.e. n(>threshold which is 1) continuous active time spots
    # event trigger based on valid active interval: find start index and end index (currently use 2 time spots for both thresholds)
    # of the n continuous active time spots, then find delta mean weight.
    # Trigger an event if the difference is large than a threshold

    def detect_weight_events(
        self,
        weight_shelf_mean,
        weight_shelf_std,  # TODO: matlab used var
        weight_plate_mean,
        weight_plate_std,
        timestamps,  # timestamps: [gondola, timestamp]
        num_plate=12,
        thresholds=None,
    ):
        # the lightest product is: {'_id': ObjectId('5e30c1c0e3a947a97b665757'), 'product_id': {'barcode_type': 'UPC', 'id': '041420027161'}, 'metadata': {'name': 'TROLLI SBC ALL STAR MIX', 'thumbnail': 'https://cdn.shopify.com/s/files/1/0083/0704/8545/products/41420027161_cce873d6-f143-408c-864e-eb351a730114.jpg?v=1565210393', 'price': 1, 'weight': 24}}

        if thresholds is None:
            thresholds = {
                "std_shelf": 20,
                "mean_shelf": 10,
                "mean_plate": 5,
                "min_event_length": 30,
            }
        events = []
        num_gondola = len(weight_shelf_mean)
        for gondola_idx in range(num_gondola):
            num_shelf = weight_shelf_mean[gondola_idx].shape[0]
            for shelf_idx in range(num_shelf):
                # find a continuous range that variance change is above threshold
                var_is_active = np.array(
                    weight_shelf_std[gondola_idx][shelf_idx]
                ) > thresholds.get("std_shelf")
                i = 0
                whole_length = len(var_is_active)
                while i < whole_length:
                    if not var_is_active[i]:
                        i += 1
                        continue
                    n_begin = i
                    n_end = i
                    n_peak = i
                    maxStd = weight_shelf_std[gondola_idx][shelf_idx][n_begin]
                    while n_end + 1 < whole_length and var_is_active[n_end + 1]:
                        n_end += 1
                        if weight_shelf_std[gondola_idx][shelf_idx][n_end] > maxStd:
                            maxStd = weight_shelf_std[gondola_idx][shelf_idx][n_end]
                            n_peak = n_end
                    i = n_end + 1

                    w_begin = weight_shelf_mean[gondola_idx][shelf_idx][n_begin]
                    w_end = weight_shelf_mean[gondola_idx][shelf_idx][n_end]
                    delta_w = w_end - w_begin
                    length = n_end - n_begin + 1

                    if length < thresholds.get("min_event_length"):
                        continue

                    if abs(delta_w) > thresholds.get("mean_shelf"):
                        trigger_begin = timestamps[gondola_idx][n_begin]
                        trigger_end = timestamps[gondola_idx][n_end]
                        peakTime = timestamps[gondola_idx][n_peak]
                        plates = [0] * num_plate
                        for plate_id in range(num_plate):
                            plates[plate_id] = (
                                weight_plate_mean[gondola_idx][shelf_idx][plate_id][
                                    n_end
                                ]
                                - weight_plate_mean[gondola_idx][shelf_idx][plate_id][
                                    n_begin
                                ]
                            )

                        event = PickUpEvent(
                            trigger_begin,
                            trigger_end,
                            peakTime,
                            n_begin,
                            n_end,
                            delta_w,
                            gondola_idx + 1,
                            shelf_idx + 1,
                            plates,
                        )

                        events.append(event)
        return events

    # events
    def splitEvents(self, pickUpEvents):
        splittedEvents = []
        for pickUpEvent in pickUpEvents:
            # print ('----------------------')
            # print ('event', pickUpEvent)
            if pickUpEvent.deltaWeight > 0:
                splittedEvents.append(pickUpEvent)
                continue

            triggerBegin = pickUpEvent.triggerBegin
            triggerEnd = pickUpEvent.triggerEnd
            peakTime = pickUpEvent.peakTime
            nBegin = pickUpEvent.nBegin
            nEnd = pickUpEvent.nEnd
            gondolaID = pickUpEvent.gondolaID
            shelfID = pickUpEvent.shelfID

            # calculate the threshold for contributing plates
            potentialActivePlateIDs = []
            numberOfPlates = 12
            if gondolaID == 2 or gondolaID == 4 or gondolaID == 5:
                numberOfPlates = 9
            absDeltaWeights = []
            for i in range(numberOfPlates):
                absDeltaWeights.append(abs(pickUpEvent.deltaWeights[i]))

            productIDsOnThisShelf = self.__bk.getProductIDsFromPosition(
                gondolaID, shelfID
            )
            minWeightOnThisShelf = float("inf")
            for productID in productIDsOnThisShelf:
                productExtended = self.__bk.getProductByID(productID)
                if productExtended.weight < minWeightOnThisShelf:
                    minWeightOnThisShelf = productExtended.weight

            plateActiveThreshold = minWeightOnThisShelf / 3.0
            # print (minWeightOnThisShelf)
            # print (plateActiveThreshold)
            for i in range(numberOfPlates):
                if absDeltaWeights[i] >= plateActiveThreshold:
                    potentialActivePlateIDs.append(i + 1)

            # use planogram to split events into groups
            # shelf planogram [1,2],[1,2,3],[3,4,5], [6,7,8,9]
            # => poetential event [1-5], [6-9]
            groups = []  # [subEvent=[3,4,5], subEvent=[7,8]]
            productsInLastPlate = set()
            for i in range(len(potentialActivePlateIDs)):
                # for i in range(numberOfPlates): # [0, 11] or [0, 8]
                plateID = potentialActivePlateIDs[i]
                productsInPlateI = self.__bk.getProductIDsFromPosition(
                    gondolaID, shelfID, plateID
                )  # [1, 12] or [1, 9]
                if i == 0:
                    for productID in productsInPlateI:
                        productsInLastPlate.add(productID)
                    groups.append([plateID])
                else:
                    connected = False
                    for productID in productsInPlateI:
                        if productID in productsInLastPlate:
                            connected = True
                            break
                    if connected:
                        for productID in productsInPlateI:
                            productsInLastPlate.add(productID)
                        groups[-1].append(plateID)
                    else:
                        groups.append([plateID])
                        productsInLastPlate = set()
                        for productID in productsInPlateI:
                            productsInLastPlate.add(productID)

            # generate subEvent for each group
            for group in groups:
                deltaWeights = np.zeros(numberOfPlates)
                deltaWeight = 0
                for plateID in group:
                    weightOnThisPlate = pickUpEvent.deltaWeights[plateID - 1]
                    deltaWeights[plateID - 1] = weightOnThisPlate
                    deltaWeight += weightOnThisPlate

                splittedEvent = PickUpEvent(
                    triggerBegin,
                    triggerEnd,
                    peakTime,
                    nBegin,
                    nEnd,
                    deltaWeight,
                    gondolaID,
                    shelfID,
                    deltaWeights,
                )
                splittedEvents.append(splittedEvent)
                # print ('splitted event:', splittedEvent)
        return splittedEvents
