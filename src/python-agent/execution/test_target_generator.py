from execution.target_generator import SortStrategy, TargetGenerator


def test_water_targets_row_by_row():
    """Crops sorted by y then x."""
    gen = TargetGenerator()
    state = {
        "data": {
            "crops": [
                {"x": 14, "y": 15, "isWatered": False, "cropName": "Parsnip"},
                {"x": 12, "y": 15, "isWatered": False, "cropName": "Parsnip"},
                {"x": 13, "y": 16, "isWatered": False, "cropName": "Parsnip"},
            ]
        }
    }
    targets = gen.generate("water_crops", state, (10, 10), SortStrategy.ROW_BY_ROW)

    # Should be sorted: (12,15), (14,15), (13,16)
    assert targets[0].x == 12 and targets[0].y == 15
    assert targets[1].x == 14 and targets[1].y == 15
    assert targets[2].x == 13 and targets[2].y == 16


def test_water_excludes_watered():
    """Already watered crops not included."""
    gen = TargetGenerator()
    state = {
        "data": {
            "crops": [
                {"x": 12, "y": 15, "isWatered": True, "cropName": "Parsnip"},
                {"x": 13, "y": 15, "isWatered": False, "cropName": "Parsnip"},
            ]
        }
    }
    targets = gen.generate("water_crops", state, (10, 10))

    assert len(targets) == 1
    assert targets[0].x == 13


def test_harvest_targets():
    """Only ready crops included."""
    gen = TargetGenerator()
    state = {
        "data": {
            "crops": [
                {"x": 12, "y": 15, "isReadyForHarvest": True, "cropName": "Parsnip"},
                {"x": 13, "y": 15, "isReadyForHarvest": False, "cropName": "Parsnip"},
            ]
        }
    }
    targets = gen.generate("harvest_crops", state, (10, 10))

    assert len(targets) == 1
    assert targets[0].x == 12 and targets[0].y == 15


def test_nearest_first_sorting():
    """Nearest to player comes first."""
    gen = TargetGenerator()
    state = {
        "data": {
            "crops": [
                {"x": 20, "y": 20, "isWatered": False, "cropName": "Parsnip"},
                {"x": 11, "y": 10, "isWatered": False, "cropName": "Parsnip"},
                {"x": 12, "y": 10, "isWatered": False, "cropName": "Parsnip"},
            ]
        }
    }
    targets = gen.generate("water_crops", state, (10, 10), SortStrategy.NEAREST_FIRST)

    assert targets[0].x == 11 and targets[0].y == 10
    assert targets[1].x == 12 and targets[1].y == 10
    assert targets[2].x == 20 and targets[2].y == 20
