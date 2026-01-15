"""
Unified SMAPI Client - Complete access to all game data.

Session 120: Created to provide single point of access to ALL SMAPI endpoints.
The agent should use this client for ALL game data instead of scattered httpx calls.

Usage:
    from smapi_client import SMAPIClient

    client = SMAPIClient()  # Uses default localhost:8790

    # Get everything at once
    world = client.get_world_state()

    # Or get specific data
    crops = client.get_farm().crops
    npcs = client.get_npcs()
    machines = client.get_machines()
"""

import httpx
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from functools import cached_property
import time


# ============================================
# DATA CLASSES - Mirror SMAPI models
# ============================================

@dataclass
class TilePosition:
    x: int
    y: int

@dataclass
class PlayerState:
    name: str
    tile_x: int
    tile_y: int
    pixel_x: int
    pixel_y: int
    facing_direction: int
    facing: str
    energy: int
    max_energy: int
    health: int
    max_health: int
    money: int
    current_tool: Optional[str]
    current_tool_index: int
    is_moving: bool
    can_move: bool
    watering_can_water: int
    watering_can_max: int

@dataclass
class TimeState:
    hour: int
    minute: int
    time_string: str
    season: str
    day: int
    year: int
    day_of_week: str
    weather: str

@dataclass
class InventoryItem:
    slot: int
    name: str
    type: str
    stack: int
    quality: int

@dataclass
class CropInfo:
    x: int
    y: int
    crop_name: str
    days_until_harvest: int
    is_watered: bool
    is_ready_for_harvest: bool

@dataclass
class TileObject:
    x: int
    y: int
    name: str
    type: str
    is_passable: bool
    is_forageable: bool
    can_interact: bool
    interaction_type: Optional[str]

@dataclass
class NpcInfo:
    name: str
    display_name: str
    location: str
    tile_x: int
    tile_y: int
    is_villager: bool
    can_socialize: bool
    friendship_points: int
    friendship_hearts: int
    can_date: bool
    is_dating: bool
    is_married: bool
    birthday_season: str
    birthday_day: int
    is_birthday_today: bool
    gifted_today: bool
    gifts_this_week: int

@dataclass
class AnimalInfo:
    id: int
    name: str
    type: str
    building_name: str
    tile_x: int
    tile_y: int
    is_outside: bool
    happiness: int
    friendship: int
    was_pet_today: bool
    produced_today: bool
    current_product: Optional[str]
    age: int

@dataclass
class BuildingInfo:
    type: str
    name: str
    tile_x: int
    tile_y: int
    animal_count: int
    max_animals: int
    door_open: bool

@dataclass
class MachineInfo:
    name: str
    location: str
    tile_x: int
    tile_y: int
    is_processing: bool
    input_item: Optional[str]
    output_item: Optional[str]
    minutes_until_ready: int
    ready_for_harvest: bool
    needs_input: bool

@dataclass
class CalendarEvent:
    day: int
    season: str
    name: str
    location: Optional[str]
    type: str

@dataclass
class SkillInfo:
    level: int
    xp: int
    xp_to_next_level: int
    profession5: Optional[str]
    profession10: Optional[str]

@dataclass
class FishInfo:
    name: str
    difficulty: int
    behavior: str
    min_size: int
    max_size: int
    base_price: int
    time_range: str
    weather_required: str

@dataclass
class MineRock:
    tile_x: int
    tile_y: int
    type: str
    health: int

@dataclass
class MineMonster:
    name: str
    tile_x: int
    tile_y: int
    health: int
    max_health: int
    damage: int

@dataclass
class ChestInfo:
    location: str
    tile_x: int
    tile_y: int
    color: str
    items: List[InventoryItem] = field(default_factory=list)

@dataclass
class ResourceClump:
    x: int
    y: int
    width: int
    height: int
    type: str
    required_tool: str
    health: int

@dataclass
class DirectionInfo:
    clear: bool
    tiles_until_blocked: int
    blocker: Optional[str]
    adjacent_tile: Optional[Dict[str, Any]]

@dataclass
class WaterSource:
    x: int
    y: int
    distance: int
    direction: str

# ============================================
# COMPOSITE STATE OBJECTS
# ============================================

@dataclass
class LocationState:
    name: str
    display_name: str
    is_outdoors: bool
    is_farm: bool
    map_width: int
    map_height: int
    shipping_bin: Optional[TilePosition]
    objects: List[TileObject] = field(default_factory=list)
    npcs: List[NpcInfo] = field(default_factory=list)
    crops: List[CropInfo] = field(default_factory=list)

@dataclass
class GameState:
    tick: int
    player: PlayerState
    time: TimeState
    location: LocationState
    inventory: List[InventoryItem]
    menu: Optional[str]
    event: Optional[str]
    dialogue_up: bool
    paused: bool

@dataclass
class SurroundingsState:
    position: TilePosition
    current_tile: Dict[str, Any]
    directions: Dict[str, DirectionInfo]
    nearest_water: Optional[WaterSource]

@dataclass
class FarmState:
    name: str
    map_width: int
    map_height: int
    shipping_bin: Optional[TilePosition]
    crops: List[CropInfo]
    objects: List[TileObject]
    tilled_tiles: List[TilePosition]
    grass_positions: List[TilePosition]
    resource_clumps: List[ResourceClump]
    chests: List[ChestInfo]

@dataclass
class SkillsState:
    farming: SkillInfo
    fishing: SkillInfo
    mining: SkillInfo
    combat: SkillInfo
    foraging: SkillInfo
    luck: SkillInfo

@dataclass
class AnimalsState:
    animals: List[AnimalInfo]
    buildings: List[BuildingInfo]

@dataclass
class MachinesState:
    machines: List[MachineInfo]

@dataclass
class CalendarState:
    season: str
    day: int
    year: int
    day_of_week: str
    days_until_season_end: int
    today_event: Optional[str]
    upcoming_events: List[CalendarEvent]
    upcoming_birthdays: List[CalendarEvent]

@dataclass
class FishingState:
    location: str
    weather: str
    season: str
    time_of_day: int
    available_fish: List[FishInfo]

@dataclass
class MiningState:
    location: str
    floor: int
    floor_type: Optional[str]
    ladder_found: bool
    shaft_found: bool
    rocks: List[MineRock]
    monsters: List[MineMonster]

@dataclass
class StorageState:
    chests: List[ChestInfo]
    fridge: List[InventoryItem]
    silo_hay: int
    silo_capacity: int

@dataclass
class NpcsState:
    npcs: List[NpcInfo]

# ============================================
# COMPLETE WORLD STATE
# ============================================

@dataclass
class WorldState:
    """Complete snapshot of ALL game data."""
    game: GameState
    surroundings: SurroundingsState
    farm: FarmState
    skills: SkillsState
    npcs: NpcsState
    animals: AnimalsState
    machines: MachinesState
    calendar: CalendarState
    fishing: FishingState
    mining: MiningState
    storage: StorageState
    timestamp: float = field(default_factory=time.time)


# ============================================
# SMAPI CLIENT
# ============================================

class SMAPIClient:
    """
    Unified client for ALL SMAPI endpoints.

    Use this for ALL game data access instead of scattered httpx calls.
    """

    def __init__(self, base_url: str = "http://localhost:8790", timeout: float = 5.0):
        self.base_url = base_url
        self.timeout = timeout
        self._cache: Dict[str, tuple] = {}  # endpoint -> (data, timestamp)
        self._cache_ttl = 0.1  # 100ms cache to avoid hammering

    def _get(self, endpoint: str, use_cache: bool = True) -> Optional[Dict]:
        """GET request with optional caching."""
        cache_key = endpoint
        now = time.time()

        # Check cache
        if use_cache and cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return data

        try:
            resp = httpx.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    data = result.get("data", {})
                    self._cache[cache_key] = (data, now)
                    return data
                else:
                    logging.warning(f"SMAPI {endpoint} failed: {result.get('error')}")
            else:
                logging.warning(f"SMAPI {endpoint} HTTP {resp.status_code}")
        except Exception as e:
            logging.debug(f"SMAPI {endpoint} error: {e}")
        return None

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()

    # ============================================
    # INDIVIDUAL ENDPOINT ACCESSORS
    # ============================================

    def get_state(self, use_cache: bool = True) -> Optional[GameState]:
        """Get core game state (player, time, location, inventory)."""
        data = self._get("/state", use_cache)
        if not data:
            return None

        try:
            player_data = data.get("player", {})
            player = PlayerState(
                name=player_data.get("name", ""),
                tile_x=player_data.get("tileX", 0),
                tile_y=player_data.get("tileY", 0),
                pixel_x=player_data.get("pixelX", 0),
                pixel_y=player_data.get("pixelY", 0),
                facing_direction=player_data.get("facingDirection", 2),
                facing=player_data.get("facing", "south"),
                energy=player_data.get("energy", 0),
                max_energy=player_data.get("maxEnergy", 270),
                health=player_data.get("health", 100),
                max_health=player_data.get("maxHealth", 100),
                money=player_data.get("money", 0),
                current_tool=player_data.get("currentTool"),
                current_tool_index=player_data.get("currentToolIndex", 0),
                is_moving=player_data.get("isMoving", False),
                can_move=player_data.get("canMove", True),
                watering_can_water=player_data.get("wateringCanWater", 0),
                watering_can_max=player_data.get("wateringCanMax", 40),
            )

            time_data = data.get("time", {})
            time_state = TimeState(
                hour=time_data.get("hour", 6),
                minute=time_data.get("minute", 0),
                time_string=time_data.get("timeString", "6:00 AM"),
                season=time_data.get("season", "spring"),
                day=time_data.get("day", 1),
                year=time_data.get("year", 1),
                day_of_week=time_data.get("dayOfWeek", "Mon"),
                weather=time_data.get("weather", "sunny"),
            )

            loc_data = data.get("location", {})
            location = LocationState(
                name=loc_data.get("name", ""),
                display_name=loc_data.get("displayName", ""),
                is_outdoors=loc_data.get("isOutdoors", True),
                is_farm=loc_data.get("isFarm", False),
                map_width=loc_data.get("mapWidth", 0),
                map_height=loc_data.get("mapHeight", 0),
                shipping_bin=TilePosition(
                    x=loc_data.get("shippingBin", {}).get("x", 0),
                    y=loc_data.get("shippingBin", {}).get("y", 0)
                ) if loc_data.get("shippingBin") else None,
                objects=[self._parse_tile_object(o) for o in loc_data.get("objects", [])],
                crops=[self._parse_crop(c) for c in loc_data.get("crops", [])],
            )

            inventory = [self._parse_inventory_item(i) for i in data.get("inventory", []) if i]

            return GameState(
                tick=data.get("tick", 0),
                player=player,
                time=time_state,
                location=location,
                inventory=inventory,
                menu=data.get("menu"),
                event=data.get("event"),
                dialogue_up=data.get("dialogueUp", False),
                paused=data.get("paused", False),
            )
        except Exception as e:
            logging.error(f"Error parsing game state: {e}")
            return None

    def get_surroundings(self, use_cache: bool = False) -> Optional[SurroundingsState]:
        """Get directional surroundings (what's in each direction)."""
        data = self._get("/surroundings", use_cache)
        if not data:
            return None

        try:
            pos_data = data.get("position", {})
            position = TilePosition(x=pos_data.get("x", 0), y=pos_data.get("y", 0))

            directions = {}
            for dir_name, dir_data in data.get("directions", {}).items():
                directions[dir_name] = DirectionInfo(
                    clear=dir_data.get("clear", False),
                    tiles_until_blocked=dir_data.get("tilesUntilBlocked", 0),
                    blocker=dir_data.get("blocker"),
                    adjacent_tile=dir_data.get("adjacentTile"),
                )

            water_data = data.get("nearestWater")
            nearest_water = WaterSource(
                x=water_data.get("x", 0),
                y=water_data.get("y", 0),
                distance=water_data.get("distance", 99),
                direction=water_data.get("direction", ""),
            ) if water_data else None

            return SurroundingsState(
                position=position,
                current_tile=data.get("currentTile", {}),
                directions=directions,
                nearest_water=nearest_water,
            )
        except Exception as e:
            logging.error(f"Error parsing surroundings: {e}")
            return None

    def get_farm(self, use_cache: bool = True) -> Optional[FarmState]:
        """Get complete farm state (ALL crops, debris, etc.)."""
        data = self._get("/farm", use_cache)
        if not data:
            return None

        try:
            return FarmState(
                name=data.get("name", "Farm"),
                map_width=data.get("mapWidth", 0),
                map_height=data.get("mapHeight", 0),
                shipping_bin=TilePosition(
                    x=data.get("shippingBin", {}).get("x", 0),
                    y=data.get("shippingBin", {}).get("y", 0)
                ) if data.get("shippingBin") else None,
                crops=[self._parse_crop(c) for c in data.get("crops", [])],
                objects=[self._parse_tile_object(o) for o in data.get("objects", [])],
                tilled_tiles=[TilePosition(x=t.get("x", 0), y=t.get("y", 0)) for t in data.get("tilledTiles", [])],
                grass_positions=[TilePosition(x=t.get("x", 0), y=t.get("y", 0)) for t in data.get("grassPositions", [])],
                resource_clumps=[self._parse_resource_clump(r) for r in data.get("resourceClumps", [])],
                chests=[],  # Simplified
            )
        except Exception as e:
            logging.error(f"Error parsing farm: {e}")
            return None

    def get_skills(self, use_cache: bool = True) -> Optional[SkillsState]:
        """Get player skill levels and professions."""
        data = self._get("/skills", use_cache)
        if not data:
            return None

        try:
            return SkillsState(
                farming=self._parse_skill(data.get("farming", {})),
                fishing=self._parse_skill(data.get("fishing", {})),
                mining=self._parse_skill(data.get("mining", {})),
                combat=self._parse_skill(data.get("combat", {})),
                foraging=self._parse_skill(data.get("foraging", {})),
                luck=self._parse_skill(data.get("luck", {})),
            )
        except Exception as e:
            logging.error(f"Error parsing skills: {e}")
            return None

    def get_npcs(self, use_cache: bool = True) -> Optional[NpcsState]:
        """Get all NPCs with location, friendship, birthday info."""
        data = self._get("/npcs", use_cache)
        if not data:
            return None

        try:
            npcs = []
            for npc_data in data.get("npcs", []):
                npcs.append(NpcInfo(
                    name=npc_data.get("name", ""),
                    display_name=npc_data.get("displayName", ""),
                    location=npc_data.get("location", ""),
                    tile_x=npc_data.get("tileX", 0),
                    tile_y=npc_data.get("tileY", 0),
                    is_villager=npc_data.get("isVillager", False),
                    can_socialize=npc_data.get("canSocialize", False),
                    friendship_points=npc_data.get("friendshipPoints", 0),
                    friendship_hearts=npc_data.get("friendshipHearts", 0),
                    can_date=npc_data.get("canDate", False),
                    is_dating=npc_data.get("isDating", False),
                    is_married=npc_data.get("isMarried", False),
                    birthday_season=npc_data.get("birthdaySeason", ""),
                    birthday_day=npc_data.get("birthdayDay", 0),
                    is_birthday_today=npc_data.get("isBirthdayToday", False),
                    gifted_today=npc_data.get("giftedToday", False),
                    gifts_this_week=npc_data.get("giftsThisWeek", 0),
                ))
            return NpcsState(npcs=npcs)
        except Exception as e:
            logging.error(f"Error parsing NPCs: {e}")
            return None

    def get_animals(self, use_cache: bool = True) -> Optional[AnimalsState]:
        """Get farm animals and buildings."""
        data = self._get("/animals", use_cache)
        if not data:
            return None

        try:
            animals = []
            for a in data.get("animals", []):
                animals.append(AnimalInfo(
                    id=a.get("id", 0),
                    name=a.get("name", ""),
                    type=a.get("type", ""),
                    building_name=a.get("buildingName", ""),
                    tile_x=a.get("tileX", 0),
                    tile_y=a.get("tileY", 0),
                    is_outside=a.get("isOutside", False),
                    happiness=a.get("happiness", 0),
                    friendship=a.get("friendship", 0),
                    was_pet_today=a.get("wasPetToday", False),
                    produced_today=a.get("producedToday", False),
                    current_product=a.get("currentProduct"),
                    age=a.get("age", 0),
                ))

            buildings = []
            for b in data.get("buildings", []):
                buildings.append(BuildingInfo(
                    type=b.get("type", ""),
                    name=b.get("name", ""),
                    tile_x=b.get("tileX", 0),
                    tile_y=b.get("tileY", 0),
                    animal_count=b.get("animalCount", 0),
                    max_animals=b.get("maxAnimals", 0),
                    door_open=b.get("doorOpen", False),
                ))

            return AnimalsState(animals=animals, buildings=buildings)
        except Exception as e:
            logging.error(f"Error parsing animals: {e}")
            return None

    def get_machines(self, use_cache: bool = True) -> Optional[MachinesState]:
        """Get all processing machines."""
        data = self._get("/machines", use_cache)
        if not data:
            return None

        try:
            machines = []
            for m in data.get("machines", []):
                machines.append(MachineInfo(
                    name=m.get("name", ""),
                    location=m.get("location", ""),
                    tile_x=m.get("tileX", 0),
                    tile_y=m.get("tileY", 0),
                    is_processing=m.get("isProcessing", False),
                    input_item=m.get("inputItem"),
                    output_item=m.get("outputItem"),
                    minutes_until_ready=m.get("minutesUntilReady", 0),
                    ready_for_harvest=m.get("readyForHarvest", False),
                    needs_input=m.get("needsInput", True),
                ))
            return MachinesState(machines=machines)
        except Exception as e:
            logging.error(f"Error parsing machines: {e}")
            return None

    def get_calendar(self, use_cache: bool = True) -> Optional[CalendarState]:
        """Get calendar with events and birthdays."""
        data = self._get("/calendar", use_cache)
        if not data:
            return None

        try:
            events = [CalendarEvent(
                day=e.get("day", 0),
                season=e.get("season", ""),
                name=e.get("name", ""),
                location=e.get("location"),
                type=e.get("type", ""),
            ) for e in data.get("upcomingEvents", [])]

            birthdays = [CalendarEvent(
                day=b.get("day", 0),
                season=b.get("season", ""),
                name=b.get("name", ""),
                location=b.get("location"),
                type="birthday",
            ) for b in data.get("upcomingBirthdays", [])]

            return CalendarState(
                season=data.get("season", ""),
                day=data.get("day", 1),
                year=data.get("year", 1),
                day_of_week=data.get("dayOfWeek", ""),
                days_until_season_end=data.get("daysUntilSeasonEnd", 0),
                today_event=data.get("todayEvent"),
                upcoming_events=events,
                upcoming_birthdays=birthdays,
            )
        except Exception as e:
            logging.error(f"Error parsing calendar: {e}")
            return None

    def get_fishing(self, use_cache: bool = True) -> Optional[FishingState]:
        """Get fishing info for current location."""
        data = self._get("/fishing", use_cache)
        if not data:
            return None

        try:
            fish = []
            for f in data.get("availableFish", []):
                fish.append(FishInfo(
                    name=f.get("name", ""),
                    difficulty=f.get("difficulty", 0),
                    behavior=f.get("behavior", ""),
                    min_size=f.get("minSize", 0),
                    max_size=f.get("maxSize", 0),
                    base_price=f.get("basePrice", 0),
                    time_range=f.get("timeRange", ""),
                    weather_required=f.get("weatherRequired", "Any"),
                ))

            return FishingState(
                location=data.get("location", ""),
                weather=data.get("weather", ""),
                season=data.get("season", ""),
                time_of_day=data.get("timeOfDay", 0),
                available_fish=fish,
            )
        except Exception as e:
            logging.error(f"Error parsing fishing: {e}")
            return None

    def get_mining(self, use_cache: bool = True) -> Optional[MiningState]:
        """Get mine floor info."""
        data = self._get("/mining", use_cache)
        if not data:
            return None

        try:
            rocks = [MineRock(
                tile_x=r.get("tileX", 0),
                tile_y=r.get("tileY", 0),
                type=r.get("type", ""),
                health=r.get("health", 0),
            ) for r in data.get("rocks", [])]

            monsters = [MineMonster(
                name=m.get("name", ""),
                tile_x=m.get("tileX", 0),
                tile_y=m.get("tileY", 0),
                health=m.get("health", 0),
                max_health=m.get("maxHealth", 0),
                damage=m.get("damage", 0),
            ) for m in data.get("monsters", [])]

            return MiningState(
                location=data.get("location", ""),
                floor=data.get("floor", 0),
                floor_type=data.get("floorType"),
                ladder_found=data.get("ladderFound", False),
                shaft_found=data.get("shaftFound", False),
                rocks=rocks,
                monsters=monsters,
            )
        except Exception as e:
            logging.error(f"Error parsing mining: {e}")
            return None

    def get_storage(self, use_cache: bool = True) -> Optional[StorageState]:
        """Get all storage containers."""
        data = self._get("/storage", use_cache)
        if not data:
            return None

        try:
            chests = []
            for c in data.get("chests", []):
                items = [self._parse_inventory_item(i) for i in c.get("items", []) if i]
                chests.append(ChestInfo(
                    location=c.get("location", ""),
                    tile_x=c.get("tileX", 0),
                    tile_y=c.get("tileY", 0),
                    color=c.get("color", ""),
                    items=items,
                ))

            fridge = [self._parse_inventory_item(i) for i in data.get("fridge", []) if i]

            return StorageState(
                chests=chests,
                fridge=fridge,
                silo_hay=data.get("siloHay", 0),
                silo_capacity=data.get("siloCapacity", 0),
            )
        except Exception as e:
            logging.error(f"Error parsing storage: {e}")
            return None

    # ============================================
    # PATHFINDING & TILE CHECKS
    # ============================================

    def check_path(self, start_x: int, start_y: int, end_x: int, end_y: int) -> Optional[Dict]:
        """Check if path exists between two points."""
        try:
            resp = httpx.get(
                f"{self.base_url}/check-path",
                params={"startX": start_x, "startY": start_y, "endX": end_x, "endY": end_y},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    return result.get("data")
        except Exception as e:
            logging.debug(f"Path check error: {e}")
        return None

    def check_passable(self, x: int, y: int) -> Optional[Dict]:
        """Check if a single tile is passable."""
        try:
            resp = httpx.get(
                f"{self.base_url}/passable",
                params={"x": x, "y": y},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    return result.get("data")
        except Exception as e:
            logging.debug(f"Passable check error: {e}")
        return None

    def check_tillable_area(self, center_x: int, center_y: int, radius: int = 10) -> Optional[Dict]:
        """Get tillable tiles in an area."""
        try:
            resp = httpx.get(
                f"{self.base_url}/tillable-area",
                params={"centerX": center_x, "centerY": center_y, "radius": min(radius, 25)},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    return result.get("data")
        except Exception as e:
            logging.debug(f"Tillable area error: {e}")
        return None

    # ============================================
    # COMPLETE WORLD STATE
    # ============================================

    def get_world_state(self) -> Optional[WorldState]:
        """
        Get COMPLETE world state - ALL endpoints combined.

        Use this when you need full game context for planning.
        """
        game = self.get_state(use_cache=False)
        if not game:
            return None

        return WorldState(
            game=game,
            surroundings=self.get_surroundings(use_cache=False),
            farm=self.get_farm(use_cache=False),
            skills=self.get_skills(),
            npcs=self.get_npcs(),
            animals=self.get_animals(),
            machines=self.get_machines(),
            calendar=self.get_calendar(),
            fishing=self.get_fishing(),
            mining=self.get_mining(),
            storage=self.get_storage(),
        )

    # ============================================
    # HELPER PARSERS
    # ============================================

    def _parse_crop(self, data: Dict) -> CropInfo:
        return CropInfo(
            x=data.get("x", 0),
            y=data.get("y", 0),
            crop_name=data.get("cropName", ""),
            days_until_harvest=data.get("daysUntilHarvest", 0),
            is_watered=data.get("isWatered", False),
            is_ready_for_harvest=data.get("isReadyForHarvest", False),
        )

    def _parse_tile_object(self, data: Dict) -> TileObject:
        return TileObject(
            x=data.get("x", 0),
            y=data.get("y", 0),
            name=data.get("name", ""),
            type=data.get("type", ""),
            is_passable=data.get("isPassable", True),
            is_forageable=data.get("isForageable", False),
            can_interact=data.get("canInteract", False),
            interaction_type=data.get("interactionType"),
        )

    def _parse_inventory_item(self, data: Dict) -> InventoryItem:
        return InventoryItem(
            slot=data.get("slot", 0),
            name=data.get("name", ""),
            type=data.get("type", ""),
            stack=data.get("stack", 1),
            quality=data.get("quality", 0),
        )

    def _parse_skill(self, data: Dict) -> SkillInfo:
        return SkillInfo(
            level=data.get("level", 0),
            xp=data.get("xp", 0),
            xp_to_next_level=data.get("xpToNextLevel", 100),
            profession5=data.get("profession5"),
            profession10=data.get("profession10"),
        )

    def _parse_resource_clump(self, data: Dict) -> ResourceClump:
        return ResourceClump(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 2),
            height=data.get("height", 2),
            type=data.get("type", ""),
            required_tool=data.get("requiredTool", ""),
            health=data.get("health", 0),
        )


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

# Global client instance for easy access
_client: Optional[SMAPIClient] = None

def get_client() -> SMAPIClient:
    """Get or create global SMAPI client."""
    global _client
    if _client is None:
        _client = SMAPIClient()
    return _client

def get_world() -> Optional[WorldState]:
    """Quick access to complete world state."""
    return get_client().get_world_state()

def get_player() -> Optional[PlayerState]:
    """Quick access to player state."""
    state = get_client().get_state()
    return state.player if state else None

def get_farm() -> Optional[FarmState]:
    """Quick access to farm state."""
    return get_client().get_farm()

def get_crops() -> List[CropInfo]:
    """Quick access to ALL farm crops."""
    farm = get_client().get_farm()
    return farm.crops if farm else []

def get_npcs() -> List[NpcInfo]:
    """Quick access to all NPCs."""
    npcs = get_client().get_npcs()
    return npcs.npcs if npcs else []


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    client = SMAPIClient()

    print("Testing SMAPI Client...")

    world = client.get_world_state()
    if world:
        print(f"Player: {world.game.player.name} at ({world.game.player.tile_x}, {world.game.player.tile_y})")
        print(f"Time: {world.game.time.time_string}, {world.game.time.season} {world.game.time.day}")
        print(f"Money: {world.game.player.money}g")
        print(f"Energy: {world.game.player.energy}/{world.game.player.max_energy}")
        print(f"Farm crops: {len(world.farm.crops) if world.farm else 0}")
        print(f"NPCs: {len(world.npcs.npcs) if world.npcs else 0}")
        print(f"Machines: {len(world.machines.machines) if world.machines else 0}")
        print(f"Calendar: {world.calendar.day_of_week}, {world.calendar.days_until_season_end} days left")
    else:
        print("Failed to get world state (game not running?)")
