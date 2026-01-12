from execution.inventory_manager import InventoryManager


def test_find_seeds_multiple_types():
    """Seeds in different slots should all be found."""
    inv = [
        {"name": "Parsnip Seeds", "stack": 5},
        None,
        {"name": "Potato Seeds", "stack": 3},
    ]
    mgr = InventoryManager(inv)
    seeds = mgr.find_seeds()
    assert len(seeds) == 2
    assert mgr.total_seeds() == 8


def test_tool_in_unexpected_slot():
    """Tools can shift from default positions."""
    inv = [
        {"name": "Parsnip Seeds", "stack": 5},
        {"name": "Hoe", "stack": 1},
        {"name": "Axe", "stack": 1},
    ]
    mgr = InventoryManager(inv)
    assert mgr.find_tool("Axe") == 2
    assert mgr.find_tool("Hoe") == 1


def test_seed_priority():
    """Parsnip should outrank potato and cauliflower."""
    inv = [
        {"name": "Potato Seeds", "stack": 6},
        {"name": "Cauliflower Seeds", "stack": 9},
        {"name": "Parsnip Seeds", "stack": 2},
    ]
    mgr = InventoryManager(inv)
    slot, name = mgr.get_seed_priority()
    assert slot == 2
    assert "Parsnip" in name
