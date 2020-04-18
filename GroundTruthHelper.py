import BookKeeper
import json

class Serializable:
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=2)

class Product(Serializable):
    def __init__(self, id, barcodeType, name, thumbnail, price, weight):
        self.id = id
        self.barcodeType = barcodeType
        self.name = name
        self.thumbnail = thumbnail
        self.price = price
        self.weight = weight

# print all products from a certain shelf
gondola_id = 4
shelf_id = 6
plate_id = None

bk = BookKeeper.BookKeeper(dbname='TEAM-PEI-JD-1')

if plate_id is not None:
    product_id = bk.getProductIDsFromPosition(gondola_id, shelf_id, plate_id)
    productExtended = bk.getProductByID(product_id)
    objProduct = Product(
                    productExtended.barcode,
                    productExtended.barcode_type,
                    productExtended.name,
                    productExtended.thumbnail,
                    productExtended.price,
                    productExtended.weight
                )
    print (objProduct.toJSON())
else:
    product_ids = bk.getProductIDsFromPosition(gondola_id, shelf_id)
    for product_id in product_ids:
        product = bk.getProductByID(product_id)
        print (product)