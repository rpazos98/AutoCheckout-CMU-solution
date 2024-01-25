from datetime import datetime

import numpy as np

from BookKeeper import Position


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
        triggerBegin,
        triggerEnd,
        peakTime,
        nBegin,
        nEnd,
        deltaWeight,
        gondolaID,
        shelfID,
        deltaWeights,
    ):
        self.triggerBegin = triggerBegin
        self.triggerEnd = triggerEnd
        self.peakTime = peakTime
        self.nBegin = nBegin
        self.nEnd = nEnd
        self.deltaWeight = deltaWeight
        self.gondolaID = gondolaID
        self.shelfID = shelfID
        self.deltaWeights = deltaWeights

    # for one event, return its most possible gondola/shelf/plate
    def getEventMostPossiblePosition(self, bk):
        greatestDelta = 0
        plateIDWithGreatestDelta = 1
        for i in range(len(self.deltaWeights)):
            deltaWeightAbs = abs(self.deltaWeights[i])
            if deltaWeightAbs > greatestDelta:
                greatestDelta = deltaWeightAbs
                plateIDWithGreatestDelta = i + 1
        return Position(self.gondolaID, self.shelfID, plateIDWithGreatestDelta)

    # for one event, return its all possible (gondola/shelf/plate) above threshold
    def getEventAllPositions(self, bk):
        possiblePositions = []
        # Magic number: A plate take into account only when plate's deltaWeight is more than 20% of shelf's deltaWeight
        threshold = 0.2
        thresholdWeight = threshold * abs(self.deltaWeight)
        for i in range(len(self.deltaWeights)):
            deltaWeightAbs = abs(self.deltaWeights[i])
            if deltaWeightAbs >= thresholdWeight:
                plateID = i + 1
                possiblePositions.append(
                    Position(self.gondolaID, self.shelfID, plateID)
                )
        return possiblePositions

    def getEventCoordinates(self, bk):
        position = self.getEventMostPossiblePosition(bk)
        coordinates = bk.get3DCoordinatesForPlate(
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
