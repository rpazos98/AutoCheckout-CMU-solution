from BookKeeper import BookKeeper
from WeightTrigger import PickUpEvent
import math_utils
from ProductScore import ProductScore
from utils import (
    get_product_ids_from_position_2d,
    get_product_positions,
    get_product_by_id,
)

sigmaForEventWeight = 10.0  # gram
sigmaForProductWeight = 10.0  # gram


class ScoreCalculator:

    # [ProductScore]
    productScoreRank: list

    # productID -> ProductScore
    productScoreDict: dict

    event: PickUpEvent

    def __init__(
        self, event, planogram, products_cache, product_ids_from_products_table
    ):
        self.productScoreRank = []
        self.productScoreDict = {}
        self.event = event
        self.planogram = planogram
        self.products_cache = products_cache

        for product_id in product_ids_from_products_table:
            product = get_product_by_id(product_id, self.products_cache)
            product_score = ProductScore(product)
            self.productScoreRank.append(product_score)
            self.productScoreDict[product_id] = product_score

        self.__calculate_arrangement_score()
        self.__calculate_weight_score()
        self.productScoreRank.sort(key=lambda x: x.get_total_score(), reverse=True)

    def get_top_k(self, k):
        return self.productScoreRank[:k]

    def get_score_by_product_id(self, product_id):
        return self.productScoreDict[product_id]

    # arrangement probability (with different weight sensed on different plate)
    def __calculate_arrangement_score(self):
        delta_weights = self.event.deltaWeights
        prob_per_plate = []
        overall_delta = sum(delta_weights)

        # a potential bug: what if there are both negatives and positives and their sum is zero?
        if overall_delta == 0:
            plate_prob = 1 / len(delta_weights)
            for i in range(0, len(delta_weights)):
                prob_per_plate.append(plate_prob)
        else:
            for delta_weight in delta_weights:
                prob_per_plate.append(delta_weight / overall_delta)

        product_ids_on_the_shelf = get_product_ids_from_position_2d(
            self.event.gondolaID, self.event.shelfID, self.planogram
        )
        for productID in product_ids_on_the_shelf:
            positions = get_product_positions(productID, self.products_cache)
            for position in positions:
                if (
                    position.gondola != self.event.gondolaID
                    or position.shelf != self.event.shelfID
                ):
                    continue
                self.productScoreDict[productID].arrangementScore += prob_per_plate[
                    position.plate - 1
                ]

    def __calculate_weight_score(self):
        delta_weight_for_event = abs(self.event.deltaWeight)
        for productScore in self.productScoreRank:
            product_weight = get_product_by_id(
                productScore.product.get_barcode(), self.products_cache
            ).product.weight
            productScore.weightScore = math_utils.areaUnderTwoGaussians(
                delta_weight_for_event,
                sigmaForEventWeight,
                product_weight,
                sigmaForProductWeight,
            )
