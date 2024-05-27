class Position:
    gondola: int
    shelf: int
    plate: int

    def __init__(self, gondola, shelf, plate):
        self.gondola = gondola
        self.shelf = shelf
        self.plate = plate

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Position(gondola=%d, shelf=%d, plate=%d)" % (
            self.gondola,
            self.shelf,
            self.plate,
        )

    def __eq__(self, other):
        if isinstance(other, Position):
            return (
                self.gondola == other.gondola
                and self.shelf == other.shelf
                and self.plate == other.plate
            )
        else:
            return False

    def __hash__(self):
        return hash((self.gondola, self.shelf, self.plate))
