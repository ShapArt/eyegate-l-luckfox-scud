import numpy as np

from vision.people_count import PeopleCounter, PeopleCounterConfig


def test_people_counter_counts_two_blobs():
    cfg = PeopleCounterConfig(
        bg_history=5,
        bg_var_threshold=16.0,
        people_min_area=50,
        dilate_kernel=3,
        erode_kernel=3,
        use_morphology=True,
    )
    counter = PeopleCounter(cfg)

    # Warm up background model
    blank = np.zeros((200, 200, 3), dtype=np.uint8)
    for _ in range(3):
        counter.count(blank)

    frame = blank.copy()
    frame[20:60, 20:60] = 255
    frame[120:170, 120:180] = 255

    count = counter.count(frame)
    assert count == 2


def test_people_counter_rejects_tiny_noise_and_aspect():
    cfg = PeopleCounterConfig(
        bg_history=3,
        bg_var_threshold=10.0,
        people_min_area=30,
        min_aspect_ratio=0.5,
        max_aspect_ratio=2.0,
    )
    counter = PeopleCounter(cfg)
    blank = np.zeros((100, 100, 3), dtype=np.uint8)
    for _ in range(2):
        counter.count(blank)

    frame = blank.copy()
    # Tiny noise blob (below area)
    frame[10:14, 10:14] = 255
    # Extremely thin vertical line (bad aspect ratio)
    frame[20:70, 90:92] = 255
    # Valid person-like blob
    frame[40:75, 40:70] = 255

    count = counter.count(frame)
    assert count == 1


def test_people_counter_filters_confetti_on_large_frames():
    # Many small-ish blobs on a large frame should not explode the count.
    # This simulates camera noise / background subtraction "confetti".
    cfg = PeopleCounterConfig(
        bg_history=5,
        bg_var_threshold=16.0,
        people_min_area=50,
        dilate_kernel=3,
        erode_kernel=3,
        use_morphology=True,
        min_area_ratio=0.01,
        min_width_ratio=0.04,
        min_height_ratio=0.12,
    )
    counter = PeopleCounter(cfg)
    blank = np.zeros((720, 960, 3), dtype=np.uint8)
    for _ in range(3):
        counter.count(blank)

    frame = blank.copy()
    # Sprinkle many 50x50 blobs across the frame (area 2500 each).
    for row in range(5):
        for col in range(4):
            y = 10 + row * 140
            x = 10 + col * 220
            frame[y : y + 50, x : x + 50] = 255

    count = counter.count(frame)
    assert count == 0


def test_people_counter_filters_border_blobs():
    cfg = PeopleCounterConfig(
        bg_history=5,
        bg_var_threshold=16.0,
        people_min_area=50,
        dilate_kernel=3,
        erode_kernel=3,
        use_morphology=True,
        min_area_ratio=0.0,
        min_width_ratio=0.0,
        min_height_ratio=0.0,
        border_margin_ratio=0.1,
        min_extent=0.0,
    )
    counter = PeopleCounter(cfg)
    blank = np.zeros((200, 200, 3), dtype=np.uint8)
    for _ in range(3):
        counter.count(blank)

    frame = blank.copy()
    # Edge blob should be ignored by border filtering.
    frame[10:60, 0:30] = 255
    # Center blob should count.
    frame[80:150, 80:120] = 255

    count = counter.count(frame)
    assert count == 1


def test_people_counter_merges_close_blobs():
    cfg = PeopleCounterConfig(
        bg_history=5,
        bg_var_threshold=16.0,
        people_min_area=50,
        use_morphology=False,
        min_area_ratio=0.0,
        min_width_ratio=0.0,
        min_height_ratio=0.0,
        border_margin_ratio=0.0,
        min_extent=0.0,
        merge_margin_ratio=0.1,
    )
    counter = PeopleCounter(cfg)
    blank = np.zeros((200, 200, 3), dtype=np.uint8)
    for _ in range(3):
        counter.count(blank)

    frame = blank.copy()
    frame[50:140, 50:80] = 255
    frame[50:140, 86:116] = 255  # small gap between blobs

    count = counter.count(frame)
    assert count == 1
