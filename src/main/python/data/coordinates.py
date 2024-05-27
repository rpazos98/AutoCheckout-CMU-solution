class Coordinates:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def translate_by(self, delta_x, delta_y, delta_z):
        self.x += delta_x
        self.y += delta_y
        self.z += delta_z

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Coordinates(%f, %f, %f)" % (self.x, self.y, self.z)
