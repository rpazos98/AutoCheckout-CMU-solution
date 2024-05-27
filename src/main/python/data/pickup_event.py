from datetime import datetime

import numpy as np
from constants import THRESHOLD
from data.position import Position


class PickUpEvent:
    triggerBegin: float  # timestamp
    triggerEnd: float  # timestamp
    peakTime: float  # timestamp for the time with highest weight variance
    nBegin: int
    nEnd: int
    deltaWeight: np.float
    gondolaID: int
    shelfID: int
    deltaWeights: list

    def __init__(
        self,
        trigger_begin,
        trigger_end,
        peak_time,
        n_begin,
        n_end,
        delta_weight,
        gondola_id,
        shelf_id,
        delta_weights,
        get_3d_coordinates_for_plate,
    ):
        self.triggerBegin = trigger_begin
        self.triggerEnd = trigger_end
        self.peakTime = peak_time
        self.nBegin = n_begin
        self.nEnd = n_end
        self.deltaWeight = delta_weight
        self.gondolaID = gondola_id
        self.shelfID = shelf_id
        self.deltaWeights = delta_weights
        self.get_3d_coordinates_for_plate = get_3d_coordinates_for_plate

    # for one event, return its most possible gondola/shelf/plate
    def get_event_most_possible_position(self):
        greatest_delta = 0
        plate_id_with_greatest_delta = 1
        for i in range(len(self.deltaWeights)):
            delta_weight_abs = abs(self.deltaWeights[i])
            if delta_weight_abs > greatest_delta:
                greatest_delta = delta_weight_abs
                plate_id_with_greatest_delta = i + 1
        return Position(self.gondolaID, self.shelfID, plate_id_with_greatest_delta)

    # for one event, return its all possible (gondola/shelf/plate) above threshold
    def get_event_all_positions(self):
        possible_positions = []
        threshold_weight = THRESHOLD * abs(self.deltaWeight)
        for i in range(len(self.deltaWeights)):
            delta_weight_abs = abs(self.deltaWeights[i])
            if delta_weight_abs >= threshold_weight:
                plate_id = i + 1
                possible_positions.append(
                    Position(self.gondolaID, self.shelfID, plate_id)
                )
        return possible_positions

    def get_event_coordinates(self):
        position = self.get_event_most_possible_position()
        coordinates = self.get_3d_coordinates_for_plate(
            position.gondola, position.shelf, position.plate
        )
        return coordinates

    def __repr__(self):
        return str(self)

    def __str__(self):
        res = "[{},{}] deltaWeight: {}, peakTime: {}, gondola {}, shelf {}, deltaWeights: [".format(
            datetime.fromtimestamp(self.triggerBegin),
            datetime.fromtimestamp(self.triggerEnd),
            self.deltaWeight,
            datetime.fromtimestamp(self.peakTime),
            self.gondolaID,
            self.shelfID,
        )
        for deltaWeight in self.deltaWeights:
            res += "%.2f, " % deltaWeight
        res += "]"
        return res
