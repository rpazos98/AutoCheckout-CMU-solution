from Constants import ARRANGEMENT_CONTRIBUTION, WEIGHT_CONTRIBUTION


class ProductScore:
    arrangementScore: float
    weightScore: float
    product: str

    def __init__(self, product):
        self.product = product
        self.arrangementScore = 0.0
        self.weightScore = 0.0

    def get_total_score(self):
        return (
            ARRANGEMENT_CONTRIBUTION * self.arrangementScore
            + WEIGHT_CONTRIBUTION * self.weightScore
        )

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "[%s] arrangementScore=%f weightScore=%f totalScore=%f, weight=%f" % (
            self.product,
            self.arrangementScore,
            self.weightScore,
            self.get_total_score(),
            self.product.weight,
        )
