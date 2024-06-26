import numpy as np

from data.pickup_event import PickUpEvent

from utils.coordinate_utils import init_nd_array, rolling_window


class WeightTrigger:

    # full event trigger: to get all event triggers from the current database
    # results: a list of events including their information of:
    # event start and end time,
    # event start and end index,
    # weight changes in gram,
    # gondola where event happens,
    # shelf where event happens,
    # a list plates where event happens.

    def __init__(
        self,
        test_start_time,
        plate_data,
        get_product_id_from_position_2d,
        get_product_id_from_position_3d,
        get_product_by_id,
        get_3d_coordinates_for_plate,
    ):
        self.plate_data = plate_data
        self.test_start_time = test_start_time
        self.get_product_id_from_position_2d = get_product_id_from_position_2d
        self.get_product_id_from_position_3d = get_product_id_from_position_3d
        self.get_product_by_id = get_product_by_id
        self.get_3d_coordinates_for_plate = get_3d_coordinates_for_plate
        (
            self.agg_plate_data,
            self.agg_shelf_data,
            self.timestamps,
        ) = self.get_agg_weight()

    # sliding window detect events
    # concatenate the data set , and use sliding window (60 data points per window)
    # moving average weight, can remove noise and reduce the false trigger caused by shake or unstable during an event

    def get_agg_weight(self, number_gondolas=5):
        agg_plate_data = [None] * number_gondolas
        agg_shelf_data = [None] * number_gondolas
        timestamps = init_nd_array(number_gondolas)

        for item in self.plate_data:
            gondola_id = item.plate_id.gondola_id
            # seconds since epoch
            if item.timestamp < self.test_start_time:
                continue
            np_shelf = (
                self.adapt_np_plate(gondola_id, item.data).sum(axis=2).transpose()
            )  # [shelf, time]
            np_plate = self.adapt_np_plate(gondola_id, item.data).transpose(
                1, 2, 0
            )  # [shelf,plate,time]
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

            timestamps[gondola_id - 1].append(item.timestamp)

        return agg_plate_data, agg_shelf_data, timestamps

    def adapt_np_plate(self, gondola_id, item):
        # replace all NaN elements to 0
        # remove first line, which is always NaN elements
        if gondola_id == 2 or gondola_id == 4 or gondola_id == 5:
            np.nan_to_num(item, copy=True, nan=0)[:, 1:13, 1:13][:, :, 9:12] = 0
        return np.nan_to_num(item, copy=True, nan=0)[:, 1:13, 1:13]

    def rolling_window(self, a, window):
        shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
        strides = a.strides + (a.strides[-1],)
        return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)

    def get_agg_timestamps(self, number_gondolas=5):
        agg_timestamps = init_nd_array(number_gondolas)
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
        timestamps,  # timestamps: [gondola, timestamp]
        num_plate=12,
        thresholds=None,
    ):
        # the lightest product is: {'_id': ObjectId('5e30c1c0e3a947a97b665757'), 'product_id': {'barcode_type':
        # 'UPC', 'id': '041420027161'}, 'metadata': {'name': 'TROLLI SBC ALL STAR MIX', 'thumbnail':
        # 'https://cdn.shopify.com/s/files/1/0083/0704/8545/products/41420027161_cce873d6-f143-408c-864e-eb351a730114
        # .jpg?v=1565210393', 'price': 1, 'weight': 24}}

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
                            self.get_3d_coordinates_for_plate,
                        )

                        events.append(event)
        return events

    # events
    def splitEvents(self, pick_up_events):
        splitted_events = []
        for pickUpEvent in pick_up_events:
            # print ('----------------------')
            # print ('event', pickUpEvent)
            if pickUpEvent.deltaWeight > 0:
                splitted_events.append(pickUpEvent)
                continue

            trigger_begin = pickUpEvent.triggerBegin
            trigger_end = pickUpEvent.triggerEnd
            peak_time = pickUpEvent.peakTime
            n_begin = pickUpEvent.nBegin
            n_end = pickUpEvent.nEnd
            gondola_id = pickUpEvent.gondolaID
            shelf_id = pickUpEvent.shelfID

            # calculate the threshold for contributing plates
            potential_active_plate_ids = []
            number_of_plates = 12
            abs_delta_weights = []
            for i in range(number_of_plates):
                abs_delta_weights.append(abs(pickUpEvent.deltaWeights[i]))

            product_ids_on_this_shelf = self.get_product_id_from_position_2d(
                gondola_id, shelf_id
            )
            min_weight_on_this_shelf = float("inf")
            for productID in product_ids_on_this_shelf:
                product_extended = self.get_product_by_id(productID)
                if product_extended.product.weight < min_weight_on_this_shelf:
                    min_weight_on_this_shelf = product_extended.product.weight

            plate_active_threshold = min_weight_on_this_shelf / 3.0
            # print (min_weight_on_this_shelf)
            # print (plate_active_threshold)
            for i in range(number_of_plates):
                if abs_delta_weights[i] >= plate_active_threshold:
                    potential_active_plate_ids.append(i + 1)

            # use planogram to split events into groups
            # shelf planogram [1,2],[1,2,3],[3,4,5], [6,7,8,9]
            # => poetential event [1-5], [6-9]
            groups = []  # [subEvent=[3,4,5], subEvent=[7,8]]
            products_in_last_plate = set()
            for i in range(len(potential_active_plate_ids)):
                # for i in range(number_of_plates): # [0, 11] or [0, 8]
                plate_id = potential_active_plate_ids[i]
                products_in_plate_i = self.get_product_id_from_position_3d(
                    gondola_id, shelf_id, plate_id
                )  # [1, 12] or [1, 9]
                if i == 0:
                    for productID in products_in_plate_i:
                        products_in_last_plate.add(productID)
                    groups.append([plate_id])
                else:
                    connected = False
                    for productID in products_in_plate_i:
                        if productID in products_in_last_plate:
                            connected = True
                            break
                    if connected:
                        for productID in products_in_plate_i:
                            products_in_last_plate.add(productID)
                        groups[-1].append(plate_id)
                    else:
                        groups.append([plate_id])
                        products_in_last_plate = set()
                        for productID in products_in_plate_i:
                            products_in_last_plate.add(productID)

            # generate subEvent for each group
            for group in groups:
                delta_weights = np.zeros(number_of_plates)
                delta_weight = 0
                for plate_id in group:
                    weight_on_this_plate = pickUpEvent.deltaWeights[plate_id - 1]
                    delta_weights[plate_id - 1] = weight_on_this_plate
                    delta_weight += weight_on_this_plate

                splitted_event = PickUpEvent(
                    trigger_begin,
                    trigger_end,
                    peak_time,
                    n_begin,
                    n_end,
                    delta_weight,
                    gondola_id,
                    shelf_id,
                    delta_weights,
                    self.get_3d_coordinates_for_plate,
                )
                splitted_events.append(splitted_event)
        return splitted_events
