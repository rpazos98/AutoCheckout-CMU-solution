class Target:
    def __init__(self, id, head, left_hand=None, right_hand=None, valid_entrance=True):
        self.head = head
        self.id = id
        self.valid_entrance = valid_entrance

        self.left_hand = None
        self.right_hand = None
        if left_hand:
            self.left_hand = left_hand
        if right_hand:
            self.right_hand = right_hand

    def update(self, id, head, left_hand=None, right_hand=None, valid_entrance=True):
        self.head = head
        self.id = id
        self.valid_entrance = valid_entrance

        self.left_hand = None
        self.right_hand = None
        if left_hand:
            self.left_hand = left_hand
        if right_hand:
            self.right_hand = right_hand

    def __str__(self):
        return "Target(ID: {})".format(str(self.id))
