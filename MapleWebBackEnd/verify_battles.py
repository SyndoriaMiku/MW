import os
import django
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MapleWebBackEnd.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.characters.models import Character
from apps.party.models import Party, PartyMember
from apps.world.models import EnemyTemplate
from apps.battles.services import BattleService
from apps.battles.models import CombatInstance

def run_verification():
    # Setup Data
    User = get_user_model()
    # Create a dummy user if not exists
    user, _ = User.objects.get_or_create(username='testuser_verify', email='test_verify@example.com')
    user.set_password('password')
    user.save()

    char, _ = Character.objects.get_or_create(name='TestCharVerify', owner=user, defaults={'base_hp': 100, 'base_att': 20})
    party, _ = Party.objects.get_or_create(name='TestPartyVerify', leader=char)
    PartyMember.objects.get_or_create(party=party, character=char, defaults={'position': 1})

    enemy, _ = EnemyTemplate.objects.get_or_create(name='TestSlimeVerify', defaults={'level': 1, 'base_hp': 50, 'base_mp': 0, 'base_att': 5, 'exp_reward': 10, 'lumis_reward_min': 1, 'lumis_reward_max': 2})

    print("Data setup complete.")

    # Test Service
    print("Creating Combat Instance...")
    combat = BattleService.create_combat_instance(party, [enemy])
    print(f"Combat Created: {combat}")
    print(f"Combatants: {combat.combatants.count()}")

    print("Starting Combat...")
    BattleService.start_combat(combat)
    print(f"Status: {combat.status}, Phase: {combat.turn_phase}, Current Player Pos: {combat.current_player_position}")

    player_combatant = combat.combatants.get(is_player=True)
    enemy_combatant = combat.combatants.get(is_player=False)

    print(f"Player HP: {player_combatant.current_hp}")
    print(f"Enemy HP: {enemy_combatant.current_hp}")

    print("Executing Attack (Player -> Enemy)...")
    BattleService.execute_action(player_combatant, 'ATTACK', enemy_combatant)
    enemy_combatant.refresh_from_db()
    print(f"Enemy HP after attack: {enemy_combatant.current_hp}")

    print("Ending Turn...")
    BattleService.end_turn(combat)
    print(f"Phase: {combat.turn_phase}")

    if combat.turn_phase == 'monster_phase':
        print("Switching back to Player Phase (simulating monster turn end)...")
        BattleService.end_turn(combat)
        print(f"Phase: {combat.turn_phase}, Turn Count: {combat.turn_count}")

    print("Verification Complete.")

if __name__ == '__main__':
    run_verification()
