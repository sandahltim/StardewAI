"""
Inventory Manager - Intelligent item categorization and storage decisions.

Decides what to keep in inventory, what to store in chests, and what to sell.
Used by the agent when inventory gets full or during daily planning.

Usage:
    from planning.inventory_manager import InventoryManager
    
    manager = InventoryManager()
    decision = manager.categorize_item(item)  # 'keep', 'store', 'sell'
    
    # Check if inventory management needed
    if manager.needs_organization(inventory):
        action = manager.get_storage_action(inventory, chests)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class InventoryManager:
    """Decides what to keep, sell, or store."""
    
    # Tools we NEVER store or sell
    ESSENTIAL_TOOLS = frozenset([
        "Axe", "Pickaxe", "Hoe", "Watering Can", "Scythe",
        "Copper Axe", "Steel Axe", "Gold Axe", "Iridium Axe",
        "Copper Pickaxe", "Steel Pickaxe", "Gold Pickaxe", "Iridium Pickaxe",
        "Copper Hoe", "Steel Hoe", "Gold Hoe", "Iridium Hoe",
        "Copper Watering Can", "Steel Watering Can", "Gold Watering Can", "Iridium Watering Can",
    ])
    
    # Items to STORE, not sell (resources for crafting)
    STORE_ITEMS = {
        # Seeds - keep for next planting
        "seed": ["Parsnip Seeds", "Potato Seeds", "Cauliflower Seeds", "Bean Starter",
                 "Kale Seeds", "Garlic Seeds", "Jazz Seeds", "Tulip Bulb", "Rice Shoot",
                 "Melon Seeds", "Tomato Seeds", "Blueberry Seeds", "Pepper Seeds",
                 "Corn Seeds", "Pumpkin Seeds", "Cranberry Seeds", "Eggplant Seeds",
                 "Amaranth Seeds", "Artichoke Seeds", "Beet Seeds", "Bok Choy Seeds",
                 "Mixed Seeds", "Ancient Seeds", "Rare Seed", "Strawberry Seeds"],
        
        # Raw materials for crafting
        "material": ["Wood", "Stone", "Coal", "Fiber", "Sap", "Hardwood", "Clay"],
        
        # Ores and bars for crafting/upgrades
        "ore": ["Copper Ore", "Iron Ore", "Gold Ore", "Iridium Ore"],
        "bar": ["Copper Bar", "Iron Bar", "Gold Bar", "Iridium Bar", "Refined Quartz"],
        
        # Gems - high value, save for gifts/bundles
        "gem": ["Diamond", "Ruby", "Emerald", "Jade", "Amethyst", "Topaz", "Aquamarine",
                "Prismatic Shard", "Fire Quartz", "Frozen Tear", "Earth Crystal"],
        
        # Monster loot - for crafting/bundles
        "monster_loot": ["Slime", "Bug Meat", "Bat Wing", "Solar Essence", "Void Essence"],
        
        # Crafting components
        "crafting": ["Battery Pack", "Quartz", "Pine Tar", "Oak Resin", "Maple Syrup"],
    }
    
    # Categories to SELL by default (excess crops, fish, forage)
    SELL_CATEGORIES = frozenset(["crop", "fruit", "vegetable", "fish", "forage"])
    
    # Items to KEEP in inventory (always useful)
    KEEP_IN_INVENTORY = frozenset([
        # Food for energy
        "Salad", "Field Snack", "Energy Tonic",
        # Commonly used items
        "Torch", "Bomb", "Cherry Bomb", "Mega Bomb",
    ])
    
    # How many of each material to keep in inventory
    MATERIAL_KEEP_AMOUNTS = {
        "Wood": 20,
        "Stone": 20,
        "Coal": 10,
        "Fiber": 10,
        "Sap": 5,
    }
    
    def __init__(self, 
                 inventory_threshold: float = 0.8,
                 material_keep: Optional[Dict[str, int]] = None):
        """
        Args:
            inventory_threshold: When inventory is this % full, suggest organizing
            material_keep: Override for how many of each material to keep
        """
        self.inventory_threshold = inventory_threshold
        self.material_keep = material_keep or self.MATERIAL_KEEP_AMOUNTS.copy()
        
        # Build lookup sets for faster checking
        self._store_items_set = set()
        for items in self.STORE_ITEMS.values():
            self._store_items_set.update(items)
    
    def categorize_item(self, item: Dict[str, Any]) -> str:
        """
        Categorize an item for storage/selling decision.
        
        Args:
            item: Inventory item dict with 'name', 'type', 'stack', etc.
            
        Returns:
            'keep': Always keep in inventory (tools, food)
            'store': Store in chest (materials, seeds, ore)
            'sell': Ship/sell (crops, fish, forage)
        """
        if not item:
            return "skip"
        
        name = item.get("name", "")
        item_type = item.get("type", "")
        
        # Essential tools - always keep
        if name in self.ESSENTIAL_TOOLS or item_type == "tool":
            return "keep"
        
        # Food items - keep for energy
        if name in self.KEEP_IN_INVENTORY:
            return "keep"
        
        # Check if it's a storable item
        if name in self._store_items_set:
            return "store"
        
        # Check by category
        category = self._get_item_category(item)
        
        if category in ("seed", "ore", "bar", "gem", "monster_loot", "crafting"):
            return "store"
        
        if category in ("material",):
            # Materials: store excess, keep some
            return "store"
        
        if category in self.SELL_CATEGORIES:
            return "sell"
        
        # Default: sell misc items
        return "sell"
    
    def _get_item_category(self, item: Dict[str, Any]) -> str:
        """Get category for an item based on type or name patterns."""
        item_type = item.get("type", "").lower()
        name = item.get("name", "").lower()
        
        if item_type in ("seed", "seeds"):
            return "seed"
        if item_type == "tool":
            return "tool"
        if "seed" in name:
            return "seed"
        if "ore" in name:
            return "ore"
        if "bar" in name:
            return "bar"
        if item_type == "crop":
            return "crop"
        if item_type == "fruit":
            return "fruit"
        if item_type == "fish":
            return "fish"
        
        return item_type or "misc"
    
    def needs_organization(self, inventory: List[Dict[str, Any]]) -> bool:
        """
        Check if inventory needs organizing (too full with storable items).
        
        Args:
            inventory: List of inventory items
            
        Returns:
            True if inventory management is recommended
        """
        if not inventory:
            return False
        
        # Count non-empty slots
        filled_slots = sum(1 for item in inventory if item)
        total_slots = len(inventory)
        
        if total_slots == 0:
            return False
        
        fill_ratio = filled_slots / total_slots
        
        if fill_ratio < self.inventory_threshold:
            return False
        
        # Check how many items are storable
        storable_count = sum(
            1 for item in inventory 
            if item and self.categorize_item(item) == "store"
        )
        
        # Worth organizing if we have 5+ storable items
        return storable_count >= 5
    
    def get_items_to_store(self, inventory: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Get list of (slot, item) pairs that should be stored.
        
        Returns items sorted by priority (materials first, then ores, etc.)
        """
        to_store = []
        
        for slot, item in enumerate(inventory):
            if not item:
                continue
            
            decision = self.categorize_item(item)
            if decision == "store":
                # Check if we should keep some in inventory
                name = item.get("name", "")
                keep_amount = self.material_keep.get(name, 0)
                stack = item.get("stack", 1)
                
                if stack > keep_amount:
                    to_store.append((slot, item))
        
        return to_store
    
    def get_items_to_sell(self, inventory: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Get list of (slot, item) pairs that should be sold.
        """
        to_sell = []
        
        for slot, item in enumerate(inventory):
            if not item:
                continue
            
            decision = self.categorize_item(item)
            if decision == "sell":
                to_sell.append((slot, item))
        
        return to_sell
    
    def find_chest_for_item(self, 
                            item: Dict[str, Any], 
                            chests: List[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
        """
        Find the best chest to store an item in.
        
        Strategy:
        1. Prefer chest that already has same item type
        2. Then prefer chest with matching category
        3. Then any chest with space
        
        Args:
            item: Item to store
            chests: List of chest info dicts with 'x', 'y', 'contents', 'slots_free'
            
        Returns:
            (x, y) position of best chest, or None if all full
        """
        if not chests:
            return None
        
        item_name = item.get("name", "")
        item_category = self._get_item_category(item)
        
        best_match = None
        category_match = None
        any_space = None
        
        for chest in chests:
            slots_free = chest.get("slots_free", 0)
            if slots_free <= 0:
                continue
            
            contents = chest.get("contents", [])
            
            # Check if this chest already has the same item
            for stored_item in contents:
                if stored_item.get("item_name") == item_name:
                    best_match = (chest.get("x"), chest.get("y"))
                    break
                
                # Check category match
                if stored_item.get("category") == item_category:
                    category_match = (chest.get("x"), chest.get("y"))
            
            if best_match:
                break
            
            # Track any chest with space
            if any_space is None:
                any_space = (chest.get("x"), chest.get("y"))
        
        return best_match or category_match or any_space
    
    def get_storage_summary(self, inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a summary of what should be stored/sold.
        
        Returns:
            Dict with 'store_count', 'sell_count', 'recommendations'
        """
        to_store = self.get_items_to_store(inventory)
        to_sell = self.get_items_to_sell(inventory)
        
        store_names = [item.get("name") for _, item in to_store]
        sell_names = [item.get("name") for _, item in to_sell]
        
        recommendations = []
        
        if len(to_store) >= 5:
            recommendations.append(f"Store {len(to_store)} items: {', '.join(store_names[:3])}...")
        
        if len(to_sell) >= 3:
            recommendations.append(f"Sell {len(to_sell)} items: {', '.join(sell_names[:3])}...")
        
        return {
            "store_count": len(to_store),
            "sell_count": len(to_sell),
            "store_items": store_names,
            "sell_items": sell_names,
            "recommendations": recommendations,
            "needs_action": len(to_store) >= 5 or len(to_sell) >= 10,
        }


# Global instance for easy access
_inventory_manager: Optional[InventoryManager] = None


def get_inventory_manager() -> InventoryManager:
    """Get or create the global inventory manager."""
    global _inventory_manager
    if _inventory_manager is None:
        _inventory_manager = InventoryManager()
    return _inventory_manager


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    # Test with mock inventory
    test_inventory = [
        {"name": "Axe", "type": "tool", "stack": 1},
        {"name": "Wood", "type": "material", "stack": 150},
        {"name": "Stone", "type": "material", "stack": 80},
        {"name": "Parsnip", "type": "crop", "stack": 15},
        {"name": "Parsnip Seeds", "type": "seed", "stack": 10},
        {"name": "Copper Ore", "type": "ore", "stack": 25},
        {"name": "Fiber", "type": "material", "stack": 40},
        None,  # Empty slot
        {"name": "Diamond", "type": "gem", "stack": 1},
        {"name": "Coal", "type": "material", "stack": 30},
    ]
    
    manager = InventoryManager()
    
    print("Testing Inventory Manager\\n")
    print("=" * 50)
    
    for item in test_inventory:
        if item:
            decision = manager.categorize_item(item)
            print(f"{item['name']:20} -> {decision}")
    
    print("\\n" + "=" * 50)
    print("\\nStorage Summary:")
    
    summary = manager.get_storage_summary(test_inventory)
    print(f"  Store: {summary['store_count']} items")
    print(f"  Sell:  {summary['sell_count']} items")
    print(f"  Recommendations: {summary['recommendations']}")
