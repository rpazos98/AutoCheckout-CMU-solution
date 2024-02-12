import math

import numpy as np
from scipy.stats import norm

from constants import BODY_THRESH
from cpsdriver.codec import Product
from data.product_extended import ProductExtended


def area_under_two_gaussians(m1, std1, m2, std2):
    if m1 > m2:
        (m1, std1, m2, std2) = (m2, std2, m1, std1)
    a = 1 / (2 * std1**2) - 1 / (2 * std2**2)
    b = m2 / (std2**2) - m1 / (std1**2)
    c = m1**2 / (2 * std1**2) - m2**2 / (2 * std2**2) - np.log(std2 / std1)
    point_of_intersect = np.roots([a, b, c])[0]
    area = norm.cdf(point_of_intersect, m2, std2) + (
        1.0 - norm.cdf(point_of_intersect, m1, std1)
    )

    return area


"""
Function to calculate distance of two 3D coordinates
"""


def calculate_distance3D(loc_a, loc_b):
    return math.sqrt(
        (loc_a.x - loc_b.x) ** 2 + (loc_a.y - loc_b.y) ** 2 + (loc_a.z - loc_b.z) ** 2
    )
