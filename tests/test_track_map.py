from acc_telemetry.track_map import lap_colors_and_sizes, sample_color, sample_size


def test_full_throttle_is_green():
    r, g, b = sample_color(gas=1.0, brake=0.0)
    assert g == 255
    assert r < 100 and b < 100


def test_full_brake_is_red():
    r, g, b = sample_color(gas=0.0, brake=1.0)
    assert r == 255
    assert g < 100


def test_coasting_is_gray():
    assert sample_color(gas=0.0, brake=0.0) == (190, 190, 190)


def test_size_grows_with_pedal_intensity():
    small = sample_size(gas=0.0, brake=0.0)
    big = sample_size(gas=1.0, brake=0.0)
    assert big > small


def test_brake_wins_when_both_pedals_pressed():
    # sample_color checks brake first -- coherent with "braking while still
    # a bit on throttle" reading as braking on the map, not as gas.
    color_both = sample_color(gas=0.5, brake=0.5)
    color_brake_only = sample_color(gas=0.0, brake=0.5)
    assert color_both == color_brake_only


def test_lap_colors_and_sizes_matches_input_length():
    gas = [0.0, 0.5, 1.0, 0.2]
    brake = [0.0, 0.0, 0.0, 0.8]
    colors, sizes = lap_colors_and_sizes(gas, brake)
    assert len(colors) == len(gas)
    assert len(sizes) == len(gas)
    assert colors.shape[1] == 3
