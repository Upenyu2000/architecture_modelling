from __future__ import annotations

import cv2
import numpy as np

from app.services.plan_boundary import detect_plan_boundary


def sample_kitchen_plan() -> np.ndarray:
    """Synthetic regression derived from the supplied L-shaped kitchen blueprint.

    It deliberately includes door/window gaps, cabinetry, an island and dining
    furniture so those symbols cannot be mistaken for the outside boundary.
    """
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    wall = 15
    outline = np.asarray(
        [(40, 60), (790, 60), (790, 430), (375, 430), (375, 545), (10, 545), (10, 300), (40, 300)],
        dtype=np.int32,
    )
    cv2.polylines(image, [outline], True, (0, 0, 0), wall, cv2.LINE_8)
    cv2.line(image, (450, 60), (530, 60), (255, 255, 255), wall + 3)
    cv2.line(image, (210, 545), (285, 545), (255, 255, 255), wall + 3)
    cv2.rectangle(image, (290, 75), (700, 120), (30, 30, 30), 2)
    cv2.rectangle(image, (455, 210), (645, 290), (30, 30, 30), 2)
    cv2.rectangle(image, (100, 390), (260, 485), (30, 30, 30), 2)
    for centre in ((90, 430), (280, 430), (140, 365), (220, 365), (140, 510), (220, 510)):
        cv2.circle(image, centre, 16, (30, 30, 30), 2)
    return image


def main() -> None:
    result = detect_plan_boundary(sample_kitchen_plan())
    assert result.confidence >= 0.70
    assert len(result.polygon_px) >= 6

    # Building membership remains true even when a furniture symbol occupies floor pixels.
    for x, y in ((400, 200), (350, 400), (650, 200), (700, 400)):
        assert result.building_mask[y, x] == 1, (x, y)
    for x, y in ((5, 5), (500, 580), (790, 520)):
        assert result.building_mask[y, x] == 0, (x, y)
        assert result.exterior_mask[y, x] == 1, (x, y)

    print("Plan-boundary smoke test passed: L-shaped envelope, openings and furniture are classified correctly")


if __name__ == "__main__":
    main()
