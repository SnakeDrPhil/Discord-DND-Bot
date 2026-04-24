"""Combat engine: state machine, damage calculation, turn processing."""

import json
import random
from typing import List, Optional, Tuple

from src.game.constants import (
    AGILITY_FLEE_BONUS,
    BASE_FLEE_CHANCE,
    BLEED_DAMAGE_PER_TURN,
    BURN_DAMAGE_PER_TURN,
    ENEMY_TYPES,
    LOOT_DROP_CHANCE,
    MAX_ATTACKS_PER_TURN,
    MAX_BUFFS_PER_TURN,
    MAX_ITEMS_PER_TURN,
    PERFECT_ENCOUNTER_XP_BONUS,
    POISON_DAMAGE_PER_TURN,
    THRUST_DAMAGE_MULTIPLIER,
    THRUST_STUN_CHANCE,
    UNARMED_DAMAGE_MAX,
    UNARMED_DAMAGE_MIN,
)
from src.game.formulas import (
    calc_bonus_physical_damage,
    calc_bonus_spell_damage,
    calc_dodge_chance,
    calc_double_strike_chance,
    calc_main_stat_duration,
    calc_song_bonus,
)
from src.utils.data_loader import get_class, get_enemies, get_loot_table


# ── Effect type classification ──────────────────────────────────────

PLAYER_BUFF_TYPES = {
    "defense_up", "damage_reduction", "strength_up", "damage_up",
    "dodge_up", "evasion", "absorb", "reflect", "untargetable",
    "melee_immune", "illusion", "next_attack_bonus", "crit_up",
    "conditional_damage_up", "armor_pierce", "heal_over_time",
    "summon_companion",
}
ENEMY_DEBUFF_TYPES = {
    "stun", "slow", "burn", "bleed", "freeze", "charm",
    "disarm", "accuracy_down", "strength_down", "attack_down",
    "armor_down", "skip_turn", "immobilize",
}
IMMEDIATE_SELF_TYPES = {"heal", "lifesteal", "cleanse", "flee"}

ATTACK_SLOT_TYPES = {
    "slash", "blunt", "stab", "weapon_based",
    "ice_spell", "fire_spell", "spell", "debuff",
}
BUFF_SLOT_TYPES = {"buff", "skill_buff", "parry"}


# ── Helpers ─────────────────────────────────────────────────────────

def _talent_ids(player: dict) -> list:
    return json.loads(player.get("selected_talents", "[]"))


def _has_talent(player: dict, tid: str) -> bool:
    return tid in _talent_ids(player)


def get_action_slot(skill: dict) -> str:
    if skill["type"] in ATTACK_SLOT_TYPES:
        return "attack"
    if skill["type"] in BUFF_SLOT_TYPES:
        return "buff"
    if skill.get("damage_multiplier") is not None and skill.get("target") not in ("self", "summon"):
        return "attack"
    return "buff"


def get_max_actions(player: dict) -> Tuple[int, int, int]:
    ma, mb, mi = MAX_ATTACKS_PER_TURN, MAX_BUFFS_PER_TURN, MAX_ITEMS_PER_TURN
    if _has_talent(player, "bard_quick_notes"):
        ma += 1
        mb += 1
    return ma, mb, mi


def should_auto_end_turn(player: dict, state: dict) -> bool:
    ma, mb, mi = get_max_actions(player)
    return state["attacks_used"] >= ma and state["buffs_used"] >= mb and state["items_used"] >= mi


def _living(enemies: list, max_n: Optional[int] = None) -> list:
    alive = [e for e in enemies if e["is_alive"]]
    return alive[:max_n] if max_n else alive


def _target(enemies: list, tid: Optional[int] = None) -> Optional[dict]:
    if tid is not None:
        for e in enemies:
            if e["id"] == tid and e["is_alive"]:
                return e
    for e in enemies:
        if e["is_alive"]:
            return e
    return None


def is_stunned(debuffs: list) -> bool:
    return any(d["type"] in ("stun", "freeze") for d in debuffs)


# ── Parse / Serialize ───────────────────────────────────────────────

def parse_state(session: dict) -> dict:
    return {
        "enemies": json.loads(session["enemies"]),
        "player_buffs": json.loads(session["player_buffs"]),
        "player_debuffs": json.loads(session["player_debuffs"]),
        "enemy_debuffs": json.loads(session["enemy_debuffs"]),
        "turn_number": session["turn_number"],
        "attacks_used": session["attacks_used"],
        "buffs_used": session["buffs_used"],
        "items_used": session["items_used"],
        "extra_turn": session["extra_turn"],
        "damage_taken": session["damage_taken"],
        "combat_log": json.loads(session["combat_log"]),
    }


def serialize_state(state: dict) -> dict:
    return {
        "enemies": json.dumps(state["enemies"]),
        "player_buffs": json.dumps(state["player_buffs"]),
        "player_debuffs": json.dumps(state["player_debuffs"]),
        "enemy_debuffs": json.dumps(state["enemy_debuffs"]),
        "turn_number": state["turn_number"],
        "attacks_used": state["attacks_used"],
        "buffs_used": state["buffs_used"],
        "items_used": state["items_used"],
        "extra_turn": state["extra_turn"],
        "damage_taken": state["damage_taken"],
        "combat_log": json.dumps(state["combat_log"][-10:]),
    }


# ── Enemy Spawning ──────────────────────────────────────────────────

def spawn_enemies(player_level: int) -> list:
    roll = random.randint(1, 100)
    count = 1 if roll <= 60 else (2 if roll <= 90 else 3)
    level = min(player_level, 20)
    enemies = []
    for i in range(count):
        etype = random.choice(ENEMY_TYPES)
        data = get_enemies(enemy_type=etype, level=level)
        if not data:
            continue
        t = data[0]
        enemies.append({
            "id": i, "type": t["type"],
            "name": t["type"].replace("_", " ").title(),
            "level": t["level"], "hp": t["hp"], "max_hp": t["hp"],
            "damage_min": t["damage_min"], "damage_max": t["damage_max"],
            "xp_reward": t["xp_reward"], "is_alive": True,
        })
    return enemies


# ── Damage Calculation ──────────────────────────────────────────────

def _player_damage(player: dict, state: dict, skill: Optional[dict] = None,
                   attack_type: str = "slash", tgt: Optional[dict] = None) -> int:
    # Use equipped weapon damage if available
    weapon = player.get("_equipped_weapon")
    is_spell = skill and skill.get("type") in ("ice_spell", "fire_spell", "spell")

    if weapon and not (is_spell and not weapon.get("casting", False)):
        base = random.randint(weapon["damage_min"], weapon["damage_max"])
    else:
        base = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX)

    if skill is None and attack_type == "thrust":
        base = int(base * THRUST_DAMAGE_MULTIPLIER)
    if skill and skill.get("damage_multiplier"):
        base = int(base * skill["damage_multiplier"])

    if is_spell and player["class"] == "bard":
        bonus = calc_song_bonus(player["charisma"])
    elif is_spell:
        bonus = calc_bonus_spell_damage(player["intelligence"])
    else:
        bonus = calc_bonus_physical_damage(player["strength"])
    dmg = base + bonus

    # Buff modifiers
    consumed = []
    for i, b in enumerate(state["player_buffs"]):
        if b["type"] in ("strength_up", "damage_up"):
            dmg *= (1 + b.get("value", 0) / 100)
        elif b["type"] == "next_attack_bonus":
            dmg *= (1 + b.get("value", 0) / 100)
            consumed.append(i)
    for i in reversed(consumed):
        state["player_buffs"].pop(i)

    # Talent bonuses
    tids = _talent_ids(player)
    if "warrior_berserker_fury" in tids and player["max_hp"] > 0:
        lost = ((player["max_hp"] - player["hp"]) * 100) // player["max_hp"]
        dmg *= (1 + 5 * (lost // 10) / 100)
    if "rogue_thrust_mastery" in tids and attack_type in ("stab", "thrust"):
        dmg *= 1.25
    if "cleric_holy_guidance" in tids and attack_type == "blunt":
        dmg *= 1.10
    if "mage_arcane_knowledge" in tids and is_spell:
        dmg *= (1 + 5 * (player["intelligence"] // 10) / 100)

    # Enemy armor_down
    if tgt:
        for d in state["enemy_debuffs"]:
            if d.get("enemy_id") == tgt["id"] and d["type"] == "armor_down":
                dmg *= (1 + d.get("value", 0) / 100)

    return max(1, int(dmg))


def _enemy_damage(enemy: dict, player: dict, state: dict) -> Tuple[int, str]:
    # Absorb / untargetable / melee_immune checks
    for b in state["player_buffs"]:
        if b["type"] in ("absorb", "untargetable", "illusion", "melee_immune"):
            return 0, b["type"]

    raw = random.randint(enemy["damage_min"], enemy["damage_max"])

    # Enemy debuffs (disarm, strength_down, attack_down, accuracy_down)
    edbs = [d for d in state["enemy_debuffs"] if d.get("enemy_id") == enemy["id"]]
    if any(d["type"] == "disarm" for d in edbs):
        raw = int(raw * 0.5)
    for d in edbs:
        if d["type"] in ("strength_down", "attack_down"):
            raw = int(raw * (1 - d.get("value", 0) / 100))

    # Accuracy check
    miss_chance = 0
    for d in edbs:
        if d["type"] == "accuracy_down":
            miss_chance += d.get("value", 0)
    if miss_chance > 0 and random.randint(1, 100) <= miss_chance:
        return 0, "missed"

    # Dodge
    dodge = calc_dodge_chance(player["agility"])
    tids = _talent_ids(player)
    if "rogue_evasion" in tids:
        dodge += 15
    if "ranger_keen_reflexes" in tids:
        dodge += 10
    for b in state["player_buffs"]:
        if b["type"] == "dodge_up":
            dodge += b.get("value", 0)
        elif b["type"] == "evasion":
            dodge += b.get("chance", b.get("value", 0))
    if random.random() * 100 < dodge:
        return 0, "dodged"

    # Armor damage reduction
    total_ar = player.get("_total_ar", 0)
    if total_ar > 0:
        from src.game.formulas import calc_armor_reduction
        ar_pct = calc_armor_reduction(total_ar)
        raw = max(1, int(raw * (1 - ar_pct / 100)))

    # Damage reduction
    dmg = float(raw)
    for b in state["player_buffs"]:
        if b["type"] in ("damage_reduction", "defense_up"):
            dmg *= (1 - b.get("value", 0) / 100)
    if "warrior_toughened_skin" in tids:
        dmg *= 0.90
    if "cleric_sacred_resilience" in tids:
        dmg *= 0.80

    final = max(1, int(dmg))

    # Reflect (Counterattack)
    for b in state["player_buffs"]:
        if b["type"] == "reflect" and enemy["is_alive"]:
            reflect = int(raw * b.get("value", 0) / 100)
            enemy["hp"] = max(0, enemy["hp"] - reflect)
            if enemy["hp"] <= 0:
                enemy["is_alive"] = False

    return final, "hit"


# ── Status Effects ──────────────────────────────────────────────────

def _make_effect(edef: dict, skill: dict, player: dict, enemy_id: Optional[int] = None) -> Optional[dict]:
    chance = edef.get("chance", 100)
    if edef["type"] in ("stun", "slow") and _has_talent(player, "warrior_iron_will"):
        if random.randint(1, 100) <= 25:
            return None
    if random.randint(1, 100) > chance:
        return None

    dur = edef.get("duration")
    if dur is None and skill.get("duration_rule") == "main_stat":
        cd = get_class(player["class"])
        dur = calc_main_stat_duration(player[cd["main_stat"]])
    if dur is None:
        dur = 1
    if _has_talent(player, "bard_fascinating_tunes") and player["class"] == "bard":
        dur += 1

    entry = {"type": edef["type"], "remaining_turns": dur, "source": skill.get("id", "unknown")}
    if "value" in edef:
        entry["value"] = edef["value"]
        if _has_talent(player, "bard_inspiring_presence") and enemy_id is None:
            entry["value"] = int(entry["value"] * 1.5)
    if "unit" in edef:
        entry["unit"] = edef["unit"]
    if enemy_id is not None:
        entry["enemy_id"] = enemy_id
    if edef["type"] == "burn":
        entry["damage_per_turn"] = BURN_DAMAGE_PER_TURN
    elif edef["type"] == "bleed":
        entry["damage_per_turn"] = BLEED_DAMAGE_PER_TURN
    elif edef["type"] == "poison":
        entry["damage_per_turn"] = POISON_DAMAGE_PER_TURN
    return entry


def _apply_skill_effects(skill: dict, player: dict, state: dict,
                         targets: list, updates: dict, msgs: list):
    """Route status_effects to player buffs or enemy debuffs."""
    for edef in skill.get("status_effects", []):
        etype = edef["type"]

        # Immediate self effects
        if etype == "heal":
            amt = int(player["max_hp"] * edef.get("value", 10) / 100)
            hp = min(updates.get("hp", player["hp"]) + amt, player["max_hp"])
            updates["hp"] = hp
            msgs.append(f"Healed for {amt} HP!")
        elif etype == "cleanse":
            n = edef.get("count", 1)
            removed = state["player_debuffs"][:n]
            state["player_debuffs"] = state["player_debuffs"][n:]
            for r in removed:
                msgs.append(f"Cleansed {r['type']}!")
        elif etype == "flee":
            if random.randint(1, 100) <= edef.get("chance", 30):
                msgs.append("Quick Escape! You fled from combat!")
                state["_fled"] = True
            else:
                msgs.append("Quick Escape failed!")
        elif etype == "skip_turn" and edef.get("affects") == "all":
            # Smoke Bomb style
            for e in _living(state["enemies"]):
                eff = _make_effect(edef, skill, player, enemy_id=e["id"])
                if eff:
                    state["enemy_debuffs"].append(eff)
            peff = _make_effect(edef, skill, player)
            if peff:
                state["player_debuffs"].append(peff)
            msgs.append("Smoke bomb! Everyone is blinded!")
        elif etype == "random_element":
            pass  # Handled separately in process_skill
        elif etype == "lifesteal":
            pass  # Handled after damage calc
        elif etype in PLAYER_BUFF_TYPES:
            eff = _make_effect(edef, skill, player)
            if eff:
                state["player_buffs"].append(eff)
                msgs.append(f"Gained {eff['type']} for {eff['remaining_turns']}t!")
        elif etype in ENEMY_DEBUFF_TYPES:
            for t in targets:
                eff = _make_effect(edef, skill, player, enemy_id=t["id"])
                if eff:
                    state["enemy_debuffs"].append(eff)
                    msgs.append(f"{t['name']} is affected by {eff['type']}!")


def process_turn_start(player: dict, state: dict) -> Tuple[dict, list]:
    """Process start-of-turn effects. Returns (player_updates, messages)."""
    msgs = []
    updates = {}
    hp = player["hp"]

    # Talent: Battle Hardened +5 HP/turn
    if _has_talent(player, "warrior_battle_hardened"):
        heal = min(5, player["max_hp"] - hp)
        if heal > 0:
            hp += heal
            msgs.append(f"Battle Hardened: +{heal} HP")

    # DoTs on player
    for d in state["player_debuffs"]:
        if d["type"] in ("burn", "bleed", "poison"):
            dot = d.get("damage_per_turn", 3)
            hp -= dot
            msgs.append(f"Took {dot} {d['type']} damage!")

    # HoTs on player
    for b in state["player_buffs"]:
        if b["type"] == "heal_over_time":
            amt = int(player["max_hp"] * b.get("value", 10) / 100)
            hp = min(hp + amt, player["max_hp"])
            msgs.append(f"Healed for {amt} HP!")

    # Tick durations
    for e in state["player_buffs"]:
        e["remaining_turns"] -= 1
    for e in state["player_debuffs"]:
        e["remaining_turns"] -= 1
    for e in state["enemy_debuffs"]:
        e["remaining_turns"] -= 1

    state["player_buffs"] = [b for b in state["player_buffs"] if b["remaining_turns"] > 0]
    state["player_debuffs"] = [d for d in state["player_debuffs"] if d["remaining_turns"] > 0]
    state["enemy_debuffs"] = [d for d in state["enemy_debuffs"] if d["remaining_turns"] > 0]

    if hp != player["hp"]:
        updates["hp"] = max(0, hp)
    return updates, msgs


# ── Double Strike ───────────────────────────────────────────────────

def _check_double_strike(player: dict, state: dict, tid: Optional[int]) -> list:
    chance = calc_double_strike_chance(player["dexterity"])
    if random.random() * 100 >= chance:
        return []
    t = _target(state["enemies"], tid)
    if not t or not t["is_alive"]:
        return []
    dmg = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX) + calc_bonus_physical_damage(player["strength"])
    dmg = max(1, int(dmg))
    t["hp"] -= dmg
    msg = f"Double Strike! Extra slash for {dmg} damage!"
    if t["hp"] <= 0:
        t["hp"] = 0
        t["is_alive"] = False
        msg += f" **{t['name']} defeated!**"
    state["combat_log"].append({
        "turn": state["turn_number"], "actor": "player",
        "action": "double_strike", "target": t["name"],
        "damage": dmg, "message": msg,
    })
    return [msg]


# ── Action Processing ──────────────────────────────────────────────

def process_basic_attack(atype: str, player: dict, state: dict,
                         tid: Optional[int] = None) -> Tuple[dict, dict, list]:
    msgs = []
    updates = {}
    t = _target(state["enemies"], tid)
    if not t:
        return state, updates, ["No valid target!"]

    dmg = _player_damage(player, state, attack_type=atype, tgt=t)
    t["hp"] -= dmg
    verb = "slashed" if atype == "slash" else "thrust at"
    if t["hp"] <= 0:
        t["hp"] = 0
        t["is_alive"] = False
        msgs.append(f"You {verb} {t['name']} for {dmg} damage! **{t['name']} defeated!**")
    else:
        msgs.append(f"You {verb} {t['name']} for {dmg} damage!")

    if atype == "thrust" and t["is_alive"] and random.randint(1, 100) <= THRUST_STUN_CHANCE:
        state["enemy_debuffs"].append({
            "type": "stun", "remaining_turns": 1,
            "source": "basic_thrust", "enemy_id": t["id"],
        })
        msgs.append(f"{t['name']} is stunned!")

    state["attacks_used"] += 1
    state["combat_log"].append({
        "turn": state["turn_number"], "actor": "player",
        "action": atype, "target": t["name"], "damage": dmg,
        "message": msgs[0],
    })
    msgs.extend(_check_double_strike(player, state, t["id"]))
    return state, updates, msgs


def process_skill(skill: dict, player: dict, state: dict,
                  tid: Optional[int] = None) -> Tuple[dict, dict, list]:
    msgs = []
    updates = {}

    # Cost
    cost = skill["cost"]
    res = skill["resource"]
    if res == "mana" and _has_talent(player, "mage_mana_efficiency"):
        cost = max(1, int(cost * 0.9))
    if player[res] < cost:
        return state, updates, [f"Not enough {res.upper()}! Need {cost}, have {player[res]}."]
    updates[res] = player[res] - cost

    # Slot
    slot = get_action_slot(skill)
    if slot == "attack":
        state["attacks_used"] += 1
    else:
        state["buffs_used"] += 1

    # Melodic Health talent
    if slot == "buff" and _has_talent(player, "bard_melodic_health"):
        heal = min(5, player["max_hp"] - player["hp"])
        if heal > 0:
            updates["hp"] = updates.get("hp", player["hp"]) + heal
            msgs.append(f"Melodic Health: +{heal} HP")

    # Damage dealing
    dealt_total = 0
    targets_hit = []
    if skill.get("damage_multiplier") is not None:
        ttype = skill.get("target", "single_enemy")
        if ttype == "furthest_enemy":
            alive = _living(state["enemies"])
            hit_targets = [alive[-1]] if alive else []
        elif ttype == "enemies_3":
            hit_targets = _living(state["enemies"], 3)
        elif ttype == "all_enemies":
            hit_targets = _living(state["enemies"])
        else:
            t = _target(state["enemies"], tid)
            hit_targets = [t] if t else []

        hits = skill.get("hit_count", 1)
        for t in hit_targets:
            for _ in range(hits):
                if not t["is_alive"]:
                    break
                dmg = _player_damage(player, state, skill=skill,
                                     attack_type=skill["type"], tgt=t)
                t["hp"] -= dmg
                dealt_total += dmg
                if t["hp"] <= 0:
                    t["hp"] = 0
                    t["is_alive"] = False
                    msgs.append(f"{skill['name']} hit {t['name']} for {dmg}! **{t['name']} defeated!**")
                else:
                    msgs.append(f"{skill['name']} hit {t['name']} for {dmg} damage!")
            targets_hit.append(t)

        if slot == "attack":
            ds = _check_double_strike(player, state, hit_targets[0]["id"] if hit_targets else None)
            msgs.extend(ds)

    # Non-damage enemy-target skills (debuffs only)
    if skill.get("damage_multiplier") is None and skill.get("target") in ("single_enemy", "all_enemies", "enemies_3"):
        ttype = skill["target"]
        if ttype == "all_enemies":
            targets_hit = _living(state["enemies"])
        elif ttype == "enemies_3":
            targets_hit = _living(state["enemies"], 3)
        else:
            t = _target(state["enemies"], tid)
            targets_hit = [t] if t else []

    # Elemental Burst random element
    if skill.get("random_element") and targets_hit:
        elements = [("burn", "fire"), ("slow", "ice"), ("stun", "lightning")]
        etype, ename = random.choice(elements)
        cd = get_class(player["class"])
        dur = calc_main_stat_duration(player[cd["main_stat"]])
        eff = {"type": etype, "remaining_turns": dur, "source": skill["id"], "enemy_id": targets_hit[0]["id"]}
        if etype == "burn":
            eff["damage_per_turn"] = BURN_DAMAGE_PER_TURN
        state["enemy_debuffs"].append(eff)
        msgs.append(f"Elemental Burst ({ename})! {targets_hit[0]['name']} affected by {etype}!")

    # Apply status effects
    _apply_skill_effects(skill, player, state, targets_hit, updates, msgs)

    # Lifesteal
    for edef in skill.get("status_effects", []):
        if edef["type"] == "lifesteal" and dealt_total > 0:
            ls = max(1, int(dealt_total * edef.get("value", 10) / 100))
            hp = min(updates.get("hp", player["hp"]) + ls, player["max_hp"])
            updates["hp"] = hp
            msgs.append(f"Life steal: +{ls} HP!")

    # Log
    state["combat_log"].append({
        "turn": state["turn_number"], "actor": "player",
        "action": skill["name"], "target": "various",
        "damage": dealt_total, "message": msgs[0] if msgs else skill["name"],
        "skill_id": skill["id"],
    })
    return state, updates, msgs


def process_item(item_data: dict, player: dict, state: dict) -> Tuple[dict, dict, list]:
    msgs = []
    updates = {}
    res = item_data["resource"]
    val = item_data["value"]

    if res == "hp":
        new = min(player["hp"] + val, player["max_hp"])
        updates["hp"] = new
        msgs.append(f"Restored {val} HP!")
    elif res == "mana":
        new = min(player["mana"] + val, player["max_mana"])
        updates["mana"] = new
        msgs.append(f"Restored {val} Mana!")
    elif res == "sp":
        new = min(player["sp"] + val, player["max_sp"])
        updates["sp"] = new
        msgs.append(f"Restored {val} SP!")

    # Status effects from consumable
    se = item_data.get("status_effect")
    if se:
        if se.get("type") == "heal_over_time":
            state["player_buffs"].append({
                "type": "heal_over_time", "value": se["value"],
                "remaining_turns": se["duration"], "source": item_data["id"],
            })
            msgs.append(f"+{se['value']} HP/turn for {se['duration']} turns!")
        elif se.get("type") == "cleanse":
            removes = se.get("removes", [])
            state["player_debuffs"] = [
                d for d in state["player_debuffs"] if d["type"] not in removes
            ]
            msgs.append("Ailments cleansed!")
        elif se.get("type") == "skip_turn":
            state["player_debuffs"].append({
                "type": "stun", "remaining_turns": 1, "source": item_data["id"],
            })
            msgs.append("The meal was so filling you can't move!")

    state["items_used"] += 1
    state["combat_log"].append({
        "turn": state["turn_number"], "actor": "player",
        "action": "item", "target": "self", "damage": 0,
        "message": msgs[0] if msgs else "Used item",
    })
    return state, updates, msgs


# ── Enemy Turn ──────────────────────────────────────────────────────

def process_enemy_turns(player: dict, state: dict) -> Tuple[dict, dict, list]:
    msgs = []
    updates = {}
    hp = player["hp"]

    # Quick Reload talent: extra basic slash at end of player turn
    if _has_talent(player, "ranger_quick_reload"):
        t = _target(state["enemies"])
        if t:
            dmg = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX) + calc_bonus_physical_damage(player["strength"])
            dmg = max(1, int(dmg))
            t["hp"] -= dmg
            if t["hp"] <= 0:
                t["hp"] = 0
                t["is_alive"] = False
                msgs.append(f"Quick Reload! Extra shot for {dmg}! **{t['name']} defeated!**")
            else:
                msgs.append(f"Quick Reload! Extra shot at {t['name']} for {dmg}!")

    # Process DoTs on enemies
    for e in _living(state["enemies"]):
        edbs = [d for d in state["enemy_debuffs"] if d.get("enemy_id") == e["id"]]
        for d in edbs:
            if d["type"] in ("burn", "bleed", "poison"):
                dot = d.get("damage_per_turn", 3)
                e["hp"] -= dot
                msgs.append(f"{e['name']} took {dot} {d['type']} damage!")
                if e["hp"] <= 0:
                    e["hp"] = 0
                    e["is_alive"] = False
                    msgs.append(f"**{e['name']} defeated by {d['type']}!**")

    # Each enemy attacks
    for e in state["enemies"]:
        if not e["is_alive"]:
            continue
        edbs = [d for d in state["enemy_debuffs"] if d.get("enemy_id") == e["id"]]
        if any(d["type"] in ("stun", "freeze", "skip_turn", "immobilize") for d in edbs):
            msgs.append(f"{e['name']} is incapacitated and cannot act!")
            continue
        if any(d["type"] == "charm" for d in edbs):
            others = [o for o in _living(state["enemies"]) if o["id"] != e["id"]]
            if others:
                victim = random.choice(others)
                cdmg = random.randint(e["damage_min"], e["damage_max"])
                victim["hp"] -= cdmg
                if victim["hp"] <= 0:
                    victim["hp"] = 0
                    victim["is_alive"] = False
                    msgs.append(f"{e['name']} (charmed) attacked {victim['name']} for {cdmg}! **{victim['name']} defeated!**")
                else:
                    msgs.append(f"{e['name']} (charmed) attacked {victim['name']} for {cdmg}!")
            else:
                msgs.append(f"{e['name']} is charmed but has no allies to attack!")
            continue

        dmg, result = _enemy_damage(e, player, state)
        if result == "dodged":
            msgs.append(f"You dodged {e['name']}'s attack!")
        elif result == "missed":
            msgs.append(f"{e['name']}'s attack missed!")
        elif result in ("absorb", "untargetable", "illusion", "melee_immune"):
            msgs.append(f"{e['name']}'s attack was blocked by your {result}!")
        else:
            hp -= dmg
            state["damage_taken"] += dmg
            msgs.append(f"{e['name']} attacked you for {dmg} damage!")

    if hp != player["hp"]:
        updates["hp"] = max(0, hp)

    # Companion attacks (Nature's Companion talent)
    if _has_talent(player, "ranger_natures_companion"):
        t = _target(state["enemies"])
        if t:
            cd = get_class(player["class"])
            comp_dmg = max(1, calc_main_stat_duration(player[cd["main_stat"]]) * 3)
            t["hp"] -= comp_dmg
            if t["hp"] <= 0:
                t["hp"] = 0
                t["is_alive"] = False
                msgs.append(f"Your companion attacks {t['name']} for {comp_dmg}! **{t['name']} defeated!**")
            else:
                msgs.append(f"Your companion attacks {t['name']} for {comp_dmg} damage!")

    state["turn_number"] += 1
    state["attacks_used"] = 0
    state["buffs_used"] = 0
    state["items_used"] = 0
    return state, updates, msgs


# ── Flee ────────────────────────────────────────────────────────────

def process_flee(player: dict, state: dict) -> Tuple[dict, dict, list, bool]:
    msgs = []
    updates = {}
    chance = BASE_FLEE_CHANCE + player["agility"] * AGILITY_FLEE_BONUS

    if random.randint(1, 100) <= chance:
        msgs.append("You escaped from combat!")
        return state, updates, msgs, True

    msgs.append(f"Failed to flee! (had {chance}% chance)")
    hp = player["hp"]
    for e in _living(state["enemies"]):
        dmg = random.randint(e["damage_min"], e["damage_max"])
        hp -= dmg
        state["damage_taken"] += dmg
        msgs.append(f"{e['name']} strikes as you flee for {dmg} damage!")
    if hp != player["hp"]:
        updates["hp"] = max(0, hp)
    return state, updates, msgs, False


# ── Combat Resolution ──────────────────────────────────────────────

def check_combat_end(player_hp: int, enemies: list) -> str:
    if player_hp <= 0:
        return "defeat"
    if all(not e["is_alive"] for e in enemies):
        return "victory"
    return "ongoing"


def calculate_rewards(enemies: list, damage_taken: int,
                      floor: int = 1, player_class: str = "warrior") -> dict:
    xp = sum(e["xp_reward"] for e in enemies)
    perfect = damage_taken == 0
    if perfect:
        xp = int(xp * (1 + PERFECT_ENCOUNTER_XP_BONUS))

    from src.game.items import generate_loot
    gold, loot = generate_loot(enemies, floor, player_class)

    return {"xp": xp, "perfect": perfect, "gold": gold, "loot": loot}
