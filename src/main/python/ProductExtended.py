# product_extended.barcode_type = product.product_id.barcode_type
# product_extended.barcode = product.product_id.product
# product_extended.name = product.name
# product_extended.thumbnail = product.thumbnail
# product_extended.price = product.price
# product_extended.weight = product.weight
# product_extended.positions = set()
from cpsdriver.codec import Product


class ProductExtended:
    positions: list
    product: Product

    def __init__(self, product):
        # barcode = product.product_id.product
        # barcode_type = product.product_id.barcode_type
        self.product = product
        self.positions = set()

    def __repr__(self):
        return str(self)

    def get_barcode(self):
        return self.product.product_id.barcode

    def get_barcode_type(self):
        return self.product.product_id.barcode_type

    def __str__(self):
        return (
            "Product(barcode_type=%s, barcode=%s, name=%s, thumbnail=%s, price=%f, weight=%f, positions=%s)"
            % (
                self.barcode_type,
                self.barcode,
                self.name,
                self.thumbnail,
                self.price,
                self.weight,
                str(self.positions),
            )
        )
