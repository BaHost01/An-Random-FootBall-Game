import pygame
import json
import random
import math
import os
import time
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union

pygame.init()

SCREEN_W, SCREEN_H = 800, 600
AI_MAX_FLOW = 100
GAME_DURATION = 300
MENU_FONT = pygame.font.Font(None, 48)
HUD_FONT = pygame.font.Font(None, 24)
SKILL_FONT = pygame.font.Font(None, 20)
GOAL_FONT = pygame.font.Font(None, 72)

class SkillType(Enum):
    FLOW = "flow"
    STAMINA = "stamina"
    ULTIMATE = "ultimate"

class PlayerType(Enum):
    STRIKER = "striker"
    MIDFIELDER = "midfielder"
    DEFENDER = "defender"
    GOALKEEPER = "goalkeeper"

class ControlType(Enum):
    KEYBOARD = "keyboard"
    AI = "ai"

class GameState(Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GOAL = "goal"
    GAME_OVER = "gameover"

@dataclass
class Skill:
    name: str
    type: SkillType
    flow_cost: int
    stamina_cost: int
    cooldown: float
    effect: Dict[str, Union[int, float, bool]]

class SaveSystem:
    FILE = "game_save.json"

    @staticmethod
    def save(state: Dict):
        with open(SaveSystem.FILE, "w") as f:
            json.dump(state, f)

    @staticmethod
    def load() -> Optional[Dict]:
        if not os.path.exists(SaveSystem.FILE):
            return None
        with open(SaveSystem.FILE, "r") as f:
            return json.load(f)

class Ball:
    def __init__(self, x: float, y: float):
        self.pos = [x, y]
        self.vel = [0.0, 0.0]
        self.radius = 8
        self.friction = 0.95

    def update(self, dt: float, bounds: Tuple[int, int]) -> Optional[str]:
        self.pos[0] += self.vel[0] * dt * 60
        self.pos[1] += self.vel[1] * dt * 60
        self.vel[0] *= self.friction
        self.vel[1] *= self.friction
        if self.pos[0] < 0:
            return "B"
        if self.pos[0] > bounds[0]:
            return "A"
        self.pos[1] = max(self.radius, min(bounds[1] - self.radius, self.pos[1]))
        return None

    def render(self, s):
        pygame.draw.circle(s, (255, 255, 255), (int(self.pos[0]), int(self.pos[1])), self.radius)

class SkillSystem:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.register(Skill("Power Shot", SkillType.FLOW, 30, 10, 5, {"mult": 2}))
        self.register(Skill("Iron Tackle", SkillType.STAMINA, 0, 40, 8, {"boost": True}))
        self.register(Skill("Field Vision", SkillType.FLOW, 40, 20, 10, {"buff": True}))
        self.register(Skill("Awaken", SkillType.ULTIMATE, AI_MAX_FLOW, 0, 0, {"awaken": True}))

    def register(self, skill: Skill):
        self.skills[skill.name] = skill

    def can_use(self, p: "Player", name: str) -> bool:
        sk = self.skills.get(name)
        if not sk:
            return False
        if p.flow < sk.flow_cost:
            return False
        if p.stamina < sk.stamina_cost:
            return False
        if p.skill_cd.get(name, 0) > 0:
            return False
        return True

    def use(self, p: "Player", name: str) -> bool:
        if not self.can_use(p, name):
            return False
        sk = self.skills[name]
        p.flow -= sk.flow_cost
        p.stamina -= sk.stamina_cost
        p.skill_cd[name] = sk.cooldown
        if sk.effect.get("awaken"):
            p.awaken()
        return True

class Player:
    def __init__(self, name: str, team: str, ptype: PlayerType, ai_lvl: int, pos: Tuple[float, float], control: ControlType = ControlType.AI):
        self.name = name
        self.team = team
        self.ptype = ptype
        self.ai_lvl = ai_lvl
        self.control = control
        self.pos = [float(pos[0]), float(pos[1])]
        self.size = 24
        self.level = 1
        self.exp = 0
        self.score = 0
        self.max_stamina = 100
        self.max_flow = AI_MAX_FLOW
        self.stamina = self.max_stamina
        self.flow = 0
        self.skill_cd: Dict[str, float] = {}
        self.awakened_until = 0.0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "team": self.team,
            "ptype": self.ptype.value,
            "ai_lvl": self.ai_lvl,
            "pos": self.pos,
            "control": self.control.value,
            "level": self.level,
            "exp": self.exp,
            "score": self.score,
            "max_stamina": self.max_stamina,
            "max_flow": self.max_flow,
            "stamina": self.stamina,
            "flow": self.flow,
            "skill_cd": self.skill_cd,
            "awakened_until": self.awakened_until
        }

    @staticmethod
    def from_dict(d: Dict) -> "Player":
        p = Player(
            d["name"],
            d["team"],
            PlayerType(d.get("ptype", PlayerType.STRIKER.value)),
            d.get("ai_lvl", 1),
            tuple(d.get("pos", (0, 0))),
            ControlType(d.get("control", ControlType.AI.value))
        )
        p.level = d.get("level", 1)
        p.exp = d.get("exp", 0)
        p.score = d.get("score", 0)
        p.max_stamina = d.get("max_stamina", 100)
        p.max_flow = d.get("max_flow", AI_MAX_FLOW)
        p.stamina = d.get("stamina", p.max_stamina)
        p.flow = d.get("flow", 0)
        p.skill_cd = d.get("skill_cd", {})
        p.awakened_until = d.get("awakened_until", 0.0)
        return p

    def update(self, dt: float, ball: Ball, players: List["Player"]):
        for k in list(self.skill_cd.keys()):
            self.skill_cd[k] = max(0.0, self.skill_cd[k] - dt)
        self.flow = min(self.max_flow, self.flow + dt * 5)
        if self.control == ControlType.AI:
            self._ai(dt, ball, players)

    def _ai(self, dt: float, ball: Ball, players: List["Player"]):
        d = math.hypot(self.pos[0] - ball.pos[0], self.pos[1] - ball.pos[1])
        if self.ptype == PlayerType.STRIKER and d < 50:
            direction_x = 1 if self.team == "A" else -1
            ball.vel = [direction_x * 10, 0]
        elif self.ptype == PlayerType.DEFENDER:
            if (self.team == "A" and ball.pos[0] < SCREEN_W / 2) or (self.team == "B" and ball.pos[0] > SCREEN_W / 2):
                self._move(ball.pos)
            else:
                self._move([SCREEN_W / 2, SCREEN_H / 2])
        else:
            if d < 30:
                ball.vel = [(self.pos[0] - ball.pos[0]) * 0.12, (self.pos[1] - ball.pos[1]) * 0.12]
            else:
                target = [SCREEN_W / 2, SCREEN_H / 2] if random.random() < 0.2 else ball.pos
                self._move(target)

    def _move(self, target: List[float]):
        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        m = math.hypot(dx, dy) or 1.0
        spd = 2.0 + self.ai_lvl * 0.3 + (2.0 if time.time() < self.awakened_until else 0.0)
        self.pos[0] += dx / m * spd
        self.pos[1] += dy / m * spd

    def render(self, s):
        col = (0, 0, 180) if self.team == "A" else (180, 0, 0)
        if time.time() < self.awakened_until:
            col = (255, 215, 0)
        pygame.draw.circle(s, col, (int(self.pos[0]), int(self.pos[1])), self.size // 2)
        self._draw_bars(s)
        name_surf = pygame.font.Font(None, 16).render(self.name, True, (255, 255, 255))
        s.blit(name_surf, (self.pos[0] - self.size, self.pos[1] - self.size - 10))

    def _draw_bars(self, s):
        x = self.pos[0] - self.size / 2
        y = self.pos[1] + self.size / 2
        pygame.draw.rect(s, (50, 50, 50), (x, y, self.size, 4))
        pygame.draw.rect(s, (0, 255, 0), (x, y, self.size * (self.stamina / self.max_stamina), 4))
        pygame.draw.rect(s, (50, 50, 50), (x, y + 5, self.size, 4))
        pygame.draw.rect(s, (0, 255, 255), (x, y + 5, self.size * (self.flow / self.max_flow), 4))

    def awaken(self):
        self.awakened_until = time.time() + 10
        self.flow = 0
        self.stamina = self.max_stamina

class CharacterFactory:
    TEMPLATES = [
        {"name": "Alex", "ptype": "striker", "ai": 6},
        {"name": "Sam", "ptype": "midfielder", "ai": 5},
        {"name": "Lee", "ptype": "defender", "ai": 7},
        {"name": "Jin", "ptype": "goalkeeper", "ai": 4}
    ]

    @staticmethod
    def create_all() -> List[Player]:
        players: List[Player] = []
        for t in CharacterFactory.TEMPLATES:
            players.append(
                Player(
                    t["name"],
                    random.choice(["A", "B"]),
                    PlayerType(t["ptype"]),
                    t["ai"],
                    (random.randint(100, 700), random.randint(100, 500))
                )
            )
        return players

class GUIManager:
    def __init__(self):
        self.options = ["Start", "Quit"]
        self.sel = 0

    def menu(self, s):
        s.fill((0, 100, 0))
        for i, o in enumerate(self.options):
            color = (255, 255, 0) if i == self.sel else (255, 255, 255)
            s.blit(MENU_FONT.render(o, True, color), (SCREEN_W / 2 - 100, 150 + i * 60))
        pygame.display.flip()

    def nav(self, e) -> str:
        if e.key == pygame.K_UP:
            self.sel = (self.sel - 1) % len(self.options)
        if e.key == pygame.K_DOWN:
            self.sel = (self.sel + 1) % len(self.options)
        return self.options[self.sel]

class GameEngine:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("AI Football")
        self.clock = pygame.time.Clock()
        self.state = GameState.MENU
        self.menu = GUIManager()
        self.skill_sys = SkillSystem()
        self.ball = Ball(400, 300)
        self.teams = {"A": 0, "B": 0}
        self.players: List[Player] = []
        self.start = 0.0
        self.goal_time = 0.0

    def run(self):
        while True:
            dt = self.clock.tick(60) / 1000
            if self.state == GameState.MENU:
                self._menu_loop()
            elif self.state == GameState.PLAYING:
                self._play_loop(dt)
            elif self.state == GameState.GOAL:
                self._goal_loop()
            elif self.state == GameState.PAUSED:
                self._pause_loop()
            else:
                break

    def _menu_loop(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.state = GameState.GAME_OVER
            if e.type == pygame.KEYDOWN:
                sel = self.menu.nav(e)
                if sel == "Start":
                    self._start_game()
                    self.state = GameState.PLAYING
                if sel == "Quit":
                    self.state = GameState.GAME_OVER
        self.menu.menu(self.screen)

    def _start_game(self):
        self.players = CharacterFactory.create_all()
        self.players.append(Player("You", "B", PlayerType.STRIKER, 1, (400, 500), ControlType.KEYBOARD))
        self.start = time.time()
        self.teams = {"A": 0, "B": 0}

    def _play_loop(self, dt: float):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.state = GameState.GAME_OVER
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.state = GameState.PAUSED
                if e.key in (pygame.K_g, pygame.K_1, pygame.K_2):
                    self._handle_skill_key(e.key)
        self._handle_movement()
        goal = self.ball.update(dt, (SCREEN_W, SCREEN_H))
        if goal:
            self.teams[goal] += 1
            self.goal_time = time.time()
            self.state = GameState.GOAL
        for p in self.players:
            p.update(dt, self.ball, self.players)
        self._render_play()

    def _goal_loop(self):
        if time.time() - self.goal_time > 2:
            self.ball = Ball(400, 300)
            self.state = GameState.PLAYING
        self.screen.fill((0, 0, 0))
        self.screen.blit(GOAL_FONT.render("GOAL!", True, (255, 255, 0)), (SCREEN_W / 2 - 100, SCREEN_H / 2 - 50))
        pygame.display.flip()

    def _pause_loop(self):
        for e in pygame.event.get():
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
        self.screen.fill((0, 0, 0))
        self.screen.blit(MENU_FONT.render("Paused", True, (255, 255, 255)), (SCREEN_W / 2 - 80, SCREEN_H / 2 - 24))
        pygame.display.flip()

    def _handle_skill_key(self, key):
        mapping = {pygame.K_g: "Awaken", pygame.K_1: "Power Shot", pygame.K_2: "Field Vision"}
        name = mapping[key]
        hp = next((p for p in self.players if p.control == ControlType.KEYBOARD), None)
        if hp:
            self.skill_sys.use(hp, name)

    def _handle_movement(self):
        hp = next((p for p in self.players if p.control == ControlType.KEYBOARD), None)
        if not hp:
            return
        keys = pygame.key.get_pressed()
        spd = 4
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            hp.pos[1] -= spd
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            hp.pos[1] += spd
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            hp.pos[0] -= spd
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            hp.pos[0] += spd
        hp.pos[0] = max(hp.size / 2, min(SCREEN_W - hp.size / 2, hp.pos[0]))
        hp.pos[1] = max(hp.size / 2, min(SCREEN_H - hp.size / 2, hp.pos[1]))

    def _render_play(self):
        s = self.screen
        s.fill((34, 139, 34))
        self.ball.render(s)
        for p in self.players:
            p.render(s)
        s.blit(HUD_FONT.render(f"Score A {self.teams['A']} - B {self.teams['B']}", True, (255, 255, 255)), (10, 10))
        t = int(max(0, GAME_DURATION - (time.time() - self.start)))
        s.blit(HUD_FONT.render(f"Time {t}s", True, (255, 255, 255)), (SCREEN_W - 120, 10))
        for i, sk in enumerate(["Power Shot", "Field Vision", "Awaken"]):
            s.blit(SKILL_FONT.render(f"{i + 1}: {sk}", True, (255, 255, 255)), (10, SCREEN_H - 30 - i * 20))
        pygame.display.flip()

if __name__ == "__main__":
    GameEngine().run()
