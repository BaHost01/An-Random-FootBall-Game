
import pytest
import os
import json
from FootGame.py import Ball, SkillSystem, Player, PlayerType, ControlType, SaveSystem

# Test Ball boundary and goal detection
def test_ball_goals_and_bounce(tmp_path):
    ball = Ball(5, 100)
    # simulate moving left past 0
    ball.vel = [-10.0, 0.0]
    result = ball.update(1/60, (800, 600))
    assert result == 'B'
    # simulate moving right past 800
    ball = Ball(795, 100)
    ball.vel = [10.0, 0.0]
    result = ball.update(1/60, (800, 600))
    assert result == 'A'
    # test vertical bounce
    ball = Ball(400, 5)
    ball.vel = [0.0, -5.0]
    result = ball.update(1/60, (800, 600))
    assert result is None
    assert ball.pos[1] == ball.radius

# Test SkillSystem usage and cooldowns
def test_skill_system():
    ss = SkillSystem()
    player = Player('Test', 'A', PlayerType.STRIKER, 1, (100,100), ControlType.KEYBOARD)
    # initial resource
    player.flow = 50
    player.stamina = 50
    # cannot use Flow Vision without enough flow
    assert not ss.can_use(player, 'Field Vision')
    # top up flow
    player.flow = 40
    assert ss.can_use(player, 'Field Vision')
    assert ss.use(player, 'Field Vision')
    # cooldown applied
    assert player.skill_cd['Field Vision'] == ss.skills['Field Vision'].cooldown
    # cannot re-use immediately
    assert not ss.can_use(player, 'Field Vision')

# Test Player awaken resets flow and stamina
def test_player_awaken():
    player = Player('P', 'A', PlayerType.MIDFIELDER, 1, (0,0), ControlType.AI)
    player.flow = 100
    player.stamina = 10
    player.awaken()
    assert player.flow == 0
    assert player.stamina == player.max_stamina
    assert player.awakened_until > 0

# Test SaveSystem saving and loading

def test_save_and_load(tmp_path, monkeypatch):
    # redirect file
    test_file = tmp_path / 'save.json'
    monkeypatch.setattr(SaveSystem, 'FILE', str(test_file))
    data = {'foo': 'bar'}
    SaveSystem.save(data)
    loaded = SaveSystem.load()
    assert loaded == data
