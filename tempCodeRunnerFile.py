"""
Rocket Launch Game - clean Python/Pygame build
Run: python space.py
Requirements: pip install pygame
"""

import math
import random
import sys
import json
from pathlib import Path
from array import array
from dataclasses import dataclass

import pygame
pygame.mixer.pre_init(22050, -16, 1, 512)


# ==================== CONFIG ====================
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60
GROUND_Y = 520

ROCKET_W = 32
ROCKET_H = 150
ROCKET_NOSE_H = 28
ROCKET_THRUSTER_H = 30

MAX_FUEL = 1500.0
# Full tank lasts ~3 minutes at 60 FPS during continuous burn.
FUEL_CONSUMPTION_RATE = MAX_FUEL / (3 * 60 * FPS)
FUEL_PER_PICKUP = 250.0
LOW_FUEL_THRESHOLD = MAX_FUEL * 0.25

ASTEROID_COUNT = 15
INITIAL_ACTIVE_ASTEROIDS = 5
MAX_ACTIVE_ASTEROIDS = 15
ASTEROID_MIN_SIZE = 12
ASTEROID_MAX_SIZE = 32
ASTEROID_MIN_SPEED = 0.45
ASTEROID_MAX_SPEED = 1.25
ASTEROIDS_DODGED_FOR_INCREASE = 8
ASTEROID_INCREASE_AMOUNT = 2

PICKUP_SPAWN_MIN_DODGES = 5
PICKUP_SPAWN_MAX_DODGES = 6
SHIELD_DURATION_FRAMES = 300
CLEAR_DURATION_FRAMES = 80

ROCKET_INITIAL_VELOCITY = 0.8
ROCKET_ACCELERATION = 0.05
ROCKET_MAX_VELOCITY = 12.0
ROCKET_HORIZONTAL_SPEED = 4.0
ROCKET_VERTICAL_CONTROL_ACCEL = 0.2
ROCKET_CONTROL_SPEED_X = 4.0
ROCKET_CONTROL_SPEED_Y = 3.0
GRAVITY_ACCELERATION = 0.03
COUNTDOWN_SECONDS = 3
CONTROL_LOCK_SECONDS = 0
ASTEROID_START_SECONDS = 20
ASTEROID_TARGET_ACTIVE = 1
ROCKET_DEFAULT_SCREEN_Y = SCREEN_HEIGHT - ROCKET_H - 25
COMBO_WINDOW_FRAMES = FPS * 3
COMBO_NEAR_MISS_BONUS = 25
BOSS_SCORE_STEP = 300
HIGHSCORE_FILE = "rocket_highscore.json"


# Colors
BLACK = (0, 0, 0)
WHITE = (245, 245, 245)
RED = (230, 60, 60)
GREEN = (80, 220, 110)
YELLOW = (250, 220, 90)
ORANGE = (245, 145, 40)
CYAN = (90, 220, 255)
GRAY = (140, 140, 150)
LIGHT_GRAY = (205, 210, 220)
DARK_GRAY = (55, 60, 70)
DARK_GREEN = (35, 100, 55)
BROWN = (122, 96, 66)
BLUE = (110, 170, 250)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    life: int
    max_life: int
    color: tuple
    ptype: str = "generic"
    drag: float = 1.0
    grow: float = 0.0

    def update(self) -> bool:
        self.x += self.vx
        self.y += self.vy
        self.vx *= self.drag
        self.vy *= self.drag
        if self.ptype == "smoke":
            self.size = max(0.5, self.size + self.grow)
            self.grow *= 0.985
            self.vx += random.uniform(-0.03, 0.03)
            self.vy += random.uniform(-0.02, 0.02)
        else:
            self.size *= 0.965
        self.life -= 1
        return self.life > 0 and self.size > 0.6

    def draw(self, screen: pygame.Surface, camera_y: float) -> None:
        sy = world_to_screen_y(self.y, camera_y)
        if sy < -50 or sy > SCREEN_HEIGHT + 50:
            return
        alpha = int(255 * (self.life / self.max_life))
        r = max(1, int(self.size))
        if self.ptype == "smoke":
            surf = pygame.Surface((r * 4 + 4, r * 4 + 4), pygame.SRCALPHA)
            cx = r * 2 + 2
            cy = r * 2 + 2
            a1 = max(6, int(alpha * 0.20))
            a2 = max(10, int(alpha * 0.36))
            a3 = max(12, int(alpha * 0.52))
            pygame.draw.circle(surf, (95, 95, 102, a1), (cx, cy), int(r * 1.8))
            pygame.draw.circle(surf, (128, 128, 136, a2), (cx, cy), int(r * 1.3))
            pygame.draw.circle(surf, (*self.color, a3), (cx, cy), r)
            screen.blit(surf, (int(self.x - cx), int(sy - cy)))
        else:
            surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*self.color, alpha), (r + 1, r + 1), r)
            screen.blit(surf, (int(self.x - r), int(sy - r)))


class Asteroid:
    def __init__(self) -> None:
        self.active = False
        self.is_boss = False
        self.x = 0.0
        self.y = 0.0
        self.size = 0.0
        self.angle = 0.0
        self.spin = 0.0
        self.close_call = False
        self.points = []

    def spawn(self, camera_y: float, rocket_x: float, boss: bool = False) -> None:
        self.active = True
        self.is_boss = boss
        self.close_call = False
        self.size = random.uniform(48, 72) if boss else random.uniform(ASTEROID_MIN_SIZE, ASTEROID_MAX_SIZE)
        spread = 110 if boss else 170
        target_x = rocket_x + ROCKET_W / 2 + random.uniform(-spread, spread)
        self.x = max(50, min(SCREEN_WIDTH - 50, target_x))
        # Static world obstacle placed ahead of the rocket path.
        self.y = camera_y - random.uniform(SCREEN_HEIGHT * 1.0, SCREEN_HEIGHT * 1.6 if boss else SCREEN_HEIGHT * 1.35)
        self.angle = random.uniform(0, math.tau)
        self.spin = random.uniform(-0.018, 0.018) if boss else random.uniform(-0.03, 0.03)
        n = random.randint(9, 12) if boss else random.randint(5, 8)
        self.points = []
        for i in range(n):
            a = (i / n) * math.tau
            wobble = 0.45 if boss else 0.3
            r = random.uniform(self.size * (1.0 - wobble), self.size * (1.0 + wobble))
            self.points.append((math.cos(a) * r, math.sin(a) * r))

    def update(self) -> None:
        # Keep position fixed; only rotate for visual liveliness.
        self.angle += self.spin

    def draw(self, screen: pygame.Surface, camera_y: float) -> None:
        if not self.active:
            return
        sy = world_to_screen_y(self.y, camera_y)
        if sy < -80 or sy > SCREEN_HEIGHT + 80:
            return
        c, s = math.cos(self.angle), math.sin(self.angle)
        pts = []
        for px, py in self.points:
            rx = px * c - py * s
            ry = px * s + py * c
            pts.append((int(self.x + rx), int(sy + ry)))
        if len(pts) > 2:
            shadow = [(x + 3, y + 3) for x, y in pts]
            if self.is_boss:
                pygame.draw.polygon(screen, (62, 24, 24), shadow)
                pygame.draw.polygon(screen, (128, 42, 42), pts)
                pygame.draw.polygon(screen, (190, 95, 70), pts, 2)
            else:
                pygame.draw.polygon(screen, (70, 54, 38), shadow)
                pygame.draw.polygon(screen, (124, 98, 70), pts)
                pygame.draw.polygon(screen, (150, 128, 98), pts, 2)

            for i in range(3):
                a = self.angle + i * 2.1
                cx = int(self.x + math.cos(a) * self.size * 0.35)
                cy = int(sy + math.sin(a) * self.size * 0.35)
                rr = max(2, int(self.size * (0.16 - i * 0.03)))
                if self.is_boss:
                    pygame.draw.circle(screen, (95, 42, 36), (cx, cy), rr)
                    pygame.draw.circle(screen, (188, 116, 82), (cx, cy), rr, 1)
                else:
                    pygame.draw.circle(screen, (82, 65, 50), (cx, cy), rr)
                    pygame.draw.circle(screen, (132, 112, 86), (cx, cy), rr, 1)

            hx1 = int(self.x - self.size * 0.25)
            hy1 = int(sy - self.size * 0.25)
            hx2 = int(self.x + self.size * 0.15)
            hy2 = int(sy - self.size * 0.10)
            pygame.draw.line(screen, (188, 165, 132), (hx1, hy1), (hx2, hy2), 2)


class Pickup:
    def __init__(self) -> None:
        self.active = False
        self.kind = "fuel"
        self.size = 15
        self.x = 0.0
        self.y = 0.0
        self.pulse = 0.0

    def spawn(self, camera_y: float, rocket_x: float) -> None:
        self.active = True
        self.kind = random.choices(["fuel", "shield", "clear"], weights=[60, 25, 15])[0]
        self.size = 15 if self.kind == "fuel" else 20 if self.kind == "shield" else 18
        target_x = rocket_x + ROCKET_W / 2 + random.uniform(-180, 180)
        self.x = max(50, min(SCREEN_WIDTH - 50, target_x))
        # Spawn ahead in world space (same style as asteroid spawning).
        self.y = camera_y - random.uniform(SCREEN_HEIGHT * 0.70, SCREEN_HEIGHT * 1.40)
        self.pulse = 0.0

    def update(self) -> None:
        # Keep pickup fixed in world; only pulse animation changes.
        self.pulse += 0.11

    def draw(self, screen: pygame.Surface, camera_y: float, font: pygame.font.Font) -> None:
        if not self.active:
            return
        sy = world_to_screen_y(self.y, camera_y)
        if sy < -60 or sy > SCREEN_HEIGHT + 60:
            return
        color = GREEN if self.kind == "fuel" else CYAN if self.kind == "shield" else YELLOW
        pulsed = int(self.size + math.sin(self.pulse) * 3)
        glow = pygame.Surface((pulsed * 4, pulsed * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, 55), (pulsed * 2, pulsed * 2), pulsed * 2)
        screen.blit(glow, (int(self.x - pulsed * 2), int(sy - pulsed * 2)))
        pygame.draw.circle(screen, color, (int(self.x), int(sy)), pulsed)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(sy)), pulsed, 2)
        label = "F" if self.kind == "fuel" else "S" if self.kind == "shield" else "C"
        txt = font.render(label, True, BLACK)
        screen.blit(txt, (int(self.x - txt.get_width() // 2), int(sy - txt.get_height() // 2)))


def world_to_screen_y(world_y: float, camera_y: float) -> float:
    return SCREEN_HEIGHT / 2 + (world_y - camera_y)


def rects_overlap(a: pygame.Rect, b: pygame.Rect) -> bool:
    return a.colliderect(b)


class RocketGame:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Rocket Launch Game")
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.Font(None, 74)
        self.font_md = pygame.font.Font(None, 40)
        self.font_sm = pygame.font.Font(None, 26)
        self.audio_enabled = False
        self.sounds = {}
        self.engine_channel = None
        self.sfx_channel = None
        self.alert_channel = None
        self.sound_muted = False
        self._init_audio()
        self.high_score = self._load_high_score()

        self.stars = [
            {
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(0, SCREEN_HEIGHT),
                "depth": random.uniform(0.15, 1.0),
                "size": random.choice([1, 1, 1, 2]),
                "twinkle": random.uniform(0.6, 1.8),
                "phase": random.uniform(0.0, math.tau),
            }
            for _ in range(260)
        ]
        self.clouds = [
            {
                "x": random.uniform(-240, SCREEN_WIDTH + 240),
                "y": random.uniform(GROUND_Y - 1500, GROUND_Y - 200),
                "speed": random.uniform(0.4, 1.2),
                "w": random.randint(90, 160),
                "h": random.randint(26, 54),
            }
            for _ in range(8)
        ]

        self.reset()

    def _load_high_score(self) -> int:
        path = Path(HIGHSCORE_FILE)
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return int(data.get("high_score", 0))
        except Exception:
            return 0

    def _save_high_score(self) -> None:
        if self.score <= self.high_score:
            return
        self.high_score = self.score
        data = {"high_score": self.high_score}
        try:
            Path(HIGHSCORE_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _init_audio(self) -> None:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(22050, -16, 1, 512)
            self.engine_channel = pygame.mixer.Channel(0)
            self.sfx_channel = pygame.mixer.Channel(1)
            self.alert_channel = pygame.mixer.Channel(2)
            self._build_sounds()
            self.audio_enabled = True
        except pygame.error:
            self.audio_enabled = False

    def _tone(self, freq: float, duration: float, volume: float = 0.35, wave: str = "sine", sweep: float = 0.0) -> pygame.mixer.Sound:
        sample_rate = 22050
        total = max(1, int(sample_rate * duration))
        samples = array("h")
        phase = 0.0
        fade_count = max(1, int(total * 0.12))
        for i in range(total):
            frac = i / total
            cur_freq = max(1.0, freq + sweep * frac)
            phase += (2.0 * math.pi * cur_freq) / sample_rate
            if wave == "square":
                val = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "noise":
                val = random.uniform(-1.0, 1.0)
            else:
                val = math.sin(phase)
            env = 1.0
            if i < fade_count:
                env = i / fade_count
            elif i > total - fade_count:
                env = (total - i) / fade_count
            samples.append(int(32767 * volume * env * val))
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _build_sounds(self) -> None:
        self.sounds = {
            "click": self._tone(980, 0.04, 0.10, "sine"),
            "count_tick": self._tone(880, 0.06, 0.10, "sine"),
            "count_go": self._tone(1250, 0.16, 0.14, "sine", sweep=160),
            "launch": self._tone(160, 0.30, 0.12, "noise", sweep=-30),
            # Soft continuous hum for flight (no beep-like square wave).
            "engine": self._tone(72, 0.30, 0.04, "sine", sweep=2),
            "asteroid_spawn": self._tone(420, 0.05, 0.06, "sine"),
            "asteroid_dodge": self._tone(620, 0.06, 0.06, "sine"),
            "shield_hit": self._tone(1400, 0.08, 0.10, "sine"),
            "collision": self._tone(85, 0.45, 0.18, "noise", sweep=-25),
            "pickup_fuel": self._tone(520, 0.10, 0.12, "sine", sweep=100),
            "pickup_shield": self._tone(980, 0.12, 0.11, "sine"),
            "pickup_clear": self._tone(760, 0.14, 0.11, "sine", sweep=120),
            "low_fuel": self._tone(180, 0.08, 0.07, "sine"),
            "game_over": self._tone(150, 0.35, 0.16, "sine", sweep=-55),
        }

    def _play_sound(self, key: str, channel: str = "sfx") -> None:
        if not self.audio_enabled or self.sound_muted:
            return
        snd = self.sounds.get(key)
        if snd is None:
            return
        ch = self.sfx_channel
        if channel == "engine":
            ch = self.engine_channel
        elif channel == "alert":
            ch = self.alert_channel
        if ch is not None:
            ch.play(snd)

    def _set_engine_sound(self, active: bool) -> None:
        if not self.audio_enabled or self.sound_muted or self.engine_channel is None:
            return
        if active:
            if not self.engine_channel.get_busy():
                self.engine_channel.play(self.sounds["engine"], loops=-1)
        else:
            self.engine_channel.stop()

    def reset(self) -> None:
        self.phase = "menu"  # menu | countdown | playing | gameover
        self.countdown_val = COUNTDOWN_SECONDS
        self.countdown_timer = 0
        self.countdown_go_frames = 0
        self.frame = 0
        self.play_frame_count = 0

        self.score = 0
        self.rocket_x = SCREEN_WIDTH / 2 - ROCKET_W / 2
        # Start on launch pad (body bottom touching ground).
        self.rocket_y = GROUND_Y - ROCKET_H
        self.velocity = ROCKET_INITIAL_VELOCITY
        self.fuel = MAX_FUEL
        self.stage = 1

        self.camera_y = self.rocket_y + SCREEN_HEIGHT / 2 - ROCKET_DEFAULT_SCREEN_Y
        self.active_asteroids = 0
        self.max_asteroids = INITIAL_ACTIVE_ASTEROIDS
        self.asteroid_target_active = ASTEROID_TARGET_ACTIVE
        self.dodged_for_increase = 0
        self.obstacles_since_powerup = 0

        self.shield_active = False
        self.shield_timer = 0
        self.clear_active = False
        self.clear_timer = 0

        self.asteroids = [Asteroid() for _ in range(ASTEROID_COUNT)]
        self.pickups = [Pickup() for _ in range(3)]
        self.particles = []
        self.next_pickup_dodge_target = random.randint(PICKUP_SPAWN_MIN_DODGES, PICKUP_SPAWN_MAX_DODGES)
        self.last_low_fuel_sound_frame = -9999
        self.game_over_sound_played = False
        self.next_boss_score = BOSS_SCORE_STEP
        self.combo_count = 0
        self.combo_timer = 0
        self.rocket_tilt = 0.0
        self.rocket_tilt_target = 0.0
        self.shake_strength = 0.0
        self._set_engine_sound(False)

    def run(self) -> None:
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._save_high_score()
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    self._play_sound("click")
                    self.sound_muted = not self.sound_muted
                    if self.sound_muted:
                        self._set_engine_sound(False)
                        if self.sfx_channel is not None:
                            self.sfx_channel.stop()
                        if self.alert_channel is not None:
                            self.alert_channel.stop()
                    continue
                if self.phase == "menu":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._play_sound("click")
                        self.phase = "countdown"
                        self._play_sound("count_tick")
                elif self.phase == "playing":
                    if self.play_frame_count >= CONTROL_LOCK_SECONDS * FPS:
                        if event.key in (pygame.K_a, pygame.K_LEFT):
                            self.rocket_x -= ROCKET_HORIZONTAL_SPEED
                        elif event.key in (pygame.K_d, pygame.K_RIGHT):
                            self.rocket_x += ROCKET_HORIZONTAL_SPEED
                        elif event.key == pygame.K_UP:
                            self.velocity = min(ROCKET_MAX_VELOCITY, self.velocity + ROCKET_VERTICAL_CONTROL_ACCEL)
                        elif event.key == pygame.K_DOWN:
                            self.velocity = max(-ROCKET_MAX_VELOCITY, self.velocity - ROCKET_VERTICAL_CONTROL_ACCEL)
                elif self.phase == "gameover":
                    if event.key == pygame.K_r:
                        self._play_sound("click")
                        self.reset()
                    elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                        self._save_high_score()
                        pygame.quit()
                        sys.exit(0)

                if event.key == pygame.K_ESCAPE and self.phase != "gameover":
                    self._save_high_score()
                    pygame.quit()
                    sys.exit(0)

        self.rocket_x = max(10, min(SCREEN_WIDTH - ROCKET_W - 10, self.rocket_x))

    def update(self) -> None:
        self.frame += 1
        self.shake_strength = max(0.0, self.shake_strength * 0.88 - 0.08)
        self.rocket_tilt += (self.rocket_tilt_target - self.rocket_tilt) * 0.2
        if self.combo_timer > 0:
            self.combo_timer -= 1
        elif self.combo_count > 0:
            self.combo_count = 0
        if self.phase == "countdown":
            self.emit_countdown_smoke()
            if self.countdown_val > 0:
                self.countdown_timer += 1
                if self.countdown_timer >= FPS:
                    if self.countdown_val > 1:
                        self._play_sound("count_tick")
                    self.countdown_val -= 1
                    self.countdown_timer = 0
                    if self.countdown_val == 0:
                        self._play_sound("count_go")
                        self._play_sound("launch")
                        self.countdown_go_frames = int(FPS * 0.85)
            else:
                self.countdown_go_frames -= 1
                if self.countdown_go_frames <= 0:
                    self.phase = "playing"
            return

        if self.phase != "playing":
            return

        self.play_frame_count += 1
        self.apply_player_controls()
        self.update_rocket()
        self.update_clouds()
        self.update_asteroids()
        self.update_pickups()
        self.update_particles()

    def emit_countdown_smoke(self) -> None:
        tail_x = self.rocket_x + ROCKET_W / 2
        tail_y = self.rocket_y + ROCKET_H - 2
        progress = 1.0 - (self.countdown_val / max(1, COUNTDOWN_SECONDS))
        progress = max(0.0, min(1.0, progress))
        plume_bottom_y = GROUND_Y + 14
        plume_width = 14 + progress * 42
        density = int(10 + progress * 18)
        for _ in range(density):
            t = random.uniform(0.0, 1.0)
            sy = tail_y + (plume_bottom_y - tail_y) * t + random.uniform(-4, 4)
            sx = tail_x + random.uniform(-plume_width, plume_width) * (0.35 + t * 0.85)
            self.particles.append(
                Particle(
                    x=sx,
                    y=sy,
                    vx=random.uniform(-0.45, 0.45),
                    vy=random.uniform(0.35, 1.3),
                    size=random.uniform(5.5, 12.5) * (0.8 + t * 0.6),
                    life=random.randint(45, 85),
                    max_life=85,
                    color=random.choice([(112, 112, 122), (132, 132, 142), (162, 162, 172)]),
                    ptype="smoke",
                    drag=0.978,
                    grow=random.uniform(0.07, 0.16),
                )
            )

    def apply_player_controls(self) -> None:
        if self.play_frame_count < CONTROL_LOCK_SECONDS * FPS:
            return

        keys = pygame.key.get_pressed()
        self.rocket_tilt_target = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.rocket_x -= ROCKET_CONTROL_SPEED_X
            self.rocket_tilt_target = -8.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.rocket_x += ROCKET_CONTROL_SPEED_X
            self.rocket_tilt_target = 8.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.rocket_y -= ROCKET_CONTROL_SPEED_Y
            self.velocity = min(ROCKET_MAX_VELOCITY, self.velocity + ROCKET_VERTICAL_CONTROL_ACCEL * 0.7)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.rocket_y += ROCKET_CONTROL_SPEED_Y
            self.velocity = max(-ROCKET_MAX_VELOCITY, self.velocity - ROCKET_VERTICAL_CONTROL_ACCEL * 1.0)

        self.rocket_x = max(10, min(SCREEN_WIDTH - ROCKET_W - 10, self.rocket_x))
        self.rocket_y = min(GROUND_Y - ROCKET_H, self.rocket_y)

    def clamp_camera_to_rocket(self) -> None:
        min_sy = 80
        max_sy = SCREEN_HEIGHT - ROCKET_H - 30
        sy = world_to_screen_y(self.rocket_y, self.camera_y)
        if sy < min_sy:
            self.camera_y = self.rocket_y + SCREEN_HEIGHT / 2 - min_sy
        elif sy > max_sy:
            self.camera_y = self.rocket_y + SCREEN_HEIGHT / 2 - max_sy

    def update_rocket(self) -> None:
        if self.phase == "gameover":
            return

        keys = pygame.key.get_pressed()
        thrusting = (keys[pygame.K_w] or keys[pygame.K_UP]) and self.fuel > 0

        if thrusting:
            self._set_engine_sound(True)
            self.fuel = max(0.0, self.fuel - FUEL_CONSUMPTION_RATE)
            self.velocity = min(ROCKET_MAX_VELOCITY, self.velocity + ROCKET_ACCELERATION)
            thruster_y = self.rocket_y + ROCKET_H + 6
            for _ in range(6):
                self.particles.append(
                    Particle(
                        x=self.rocket_x + ROCKET_W / 2 + random.uniform(-8, 8),
                        y=thruster_y + random.uniform(-2, 5),
                        vx=random.uniform(-1.1, 1.1),
                        vy=random.uniform(1.5, 4.0),
                        size=random.uniform(2.5, 7.0),
                        life=random.randint(20, 35),
                        max_life=35,
                        color=random.choice([YELLOW, ORANGE, RED]),
                        ptype="fire",
                    )
                )
            for _ in range(3):
                self.particles.append(
                    Particle(
                        x=self.rocket_x + ROCKET_W / 2 + random.uniform(-10, 10),
                        y=thruster_y + random.uniform(-1, 7),
                        vx=random.uniform(-0.45, 0.45),
                        vy=random.uniform(1.0, 2.8),
                        size=random.uniform(3.8, 8.8),
                        life=random.randint(28, 55),
                        max_life=55,
                        color=random.choice([(120, 120, 128), (145, 145, 152)]),
                        ptype="smoke",
                        drag=0.975,
                        grow=random.uniform(0.05, 0.12),
                    )
                )
        else:
            self._set_engine_sound(False)
            self.velocity -= GRAVITY_ACCELERATION

        self.rocket_y -= self.velocity
        target_camera_y = self.rocket_y + SCREEN_HEIGHT / 2 - ROCKET_DEFAULT_SCREEN_Y
        delta = max(-6.0, min(6.0, (target_camera_y - self.camera_y) * 0.10))
        self.camera_y += delta
        self.clamp_camera_to_rocket()

        if self.stage == 1 and (GROUND_Y - self.rocket_y) > 300:
            self.stage = 2

        if self.shield_active:
            self.shield_timer -= 1
            if self.shield_timer <= 0:
                self.shield_active = False

        if self.clear_active:
            self.clear_timer -= 1
            if self.clear_timer <= 0:
                self.clear_active = False
            else:
                for ast in self.asteroids:
                    if ast.active:
                        ast.active = False
                        self.active_asteroids = max(0, self.active_asteroids - 1)

        if self.rocket_y >= GROUND_Y - ROCKET_H and self.velocity < 0:
            self.phase = "gameover"
            self._set_engine_sound(False)
            self.shake_strength = max(self.shake_strength, 10.0)
            self._save_high_score()
            if not self.game_over_sound_played:
                self._play_sound("game_over")
                self.game_over_sound_played = True

        if self.fuel <= LOW_FUEL_THRESHOLD and self.frame - self.last_low_fuel_sound_frame >= FPS * 4:
            self._play_sound("low_fuel", "alert")
            self.last_low_fuel_sound_frame = self.frame

    def update_clouds(self) -> None:
        for c in self.clouds:
            c["x"] += c["speed"]
            if c["x"] > SCREEN_WIDTH + 220:
                c["x"] = -220

    def update_asteroids(self) -> None:
        if self.phase == "gameover":
            return
        if self.play_frame_count < ASTEROID_START_SECONDS * FPS:
            return

        has_boss = any(a.active and a.is_boss for a in self.asteroids)
        if self.score >= self.next_boss_score and not has_boss:
            slot = next((a for a in self.asteroids if not a.active), None)
            if slot is not None:
                slot.spawn(self.camera_y, self.rocket_x, boss=True)
                self.active_asteroids += 1
                self.next_boss_score += BOSS_SCORE_STEP

        while self.active_asteroids < self.asteroid_target_active:
            slot = next((a for a in self.asteroids if not a.active), None)
            if slot is None:
                break
            slot.spawn(self.camera_y, self.rocket_x)
            self.active_asteroids += 1

        rocket_cx = self.rocket_x + ROCKET_W / 2
        rocket_cy = self.rocket_y + ROCKET_H / 2

        for a in self.asteroids:
            if not a.active:
                continue
            a.update()

            if a.y > self.camera_y + SCREEN_HEIGHT / 2 + a.size * 2:
                a.active = False
                self.active_asteroids = max(0, self.active_asteroids - 1)
                dodge_points = 60 if a.is_boss else 10
                self.score += dodge_points
                self.obstacles_since_powerup += 1
                self.dodged_for_increase += 1
                self.asteroid_target_active = min(MAX_ACTIVE_ASTEROIDS, 1 + self.score // 120)
                if a.close_call:
                    self.combo_count += 1
                    self.combo_timer = COMBO_WINDOW_FRAMES
                    self.score += COMBO_NEAR_MISS_BONUS * self.combo_count
                if self.dodged_for_increase >= ASTEROIDS_DODGED_FOR_INCREASE:
                    self.velocity = min(ROCKET_MAX_VELOCITY, self.velocity + 0.6)
                    self.dodged_for_increase = 0
                continue

            dist = math.hypot(rocket_cx - a.x, rocket_cy - a.y)
            collide_r = a.size + ROCKET_W * 0.45
            if not a.close_call and collide_r < dist < (collide_r + 18) and abs(rocket_cy - a.y) < (a.size + 24):
                a.close_call = True
            if dist < collide_r:
                if self.shield_active:
                    a.active = False
                    self.active_asteroids = max(0, self.active_asteroids - 1)
                    self.score += 5
                    self.shake_strength = max(self.shake_strength, 4.0)
                    self._play_sound("shield_hit")
                    for _ in range(14):
                        self.particles.append(
                            Particle(a.x, a.y, random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(3, 8), 18, 18, CYAN)
                        )
                else:
                    self.shake_strength = max(self.shake_strength, 12.0)
                    self._play_sound("collision")
                    for _ in range(32):
                        self.particles.append(
                            Particle(
                                self.rocket_x + ROCKET_W / 2,
                                self.rocket_y + ROCKET_H / 2,
                                random.uniform(-5, 5),
                                random.uniform(-5, 5),
                                random.uniform(4, 10),
                                20,
                                20,
                                random.choice([RED, ORANGE, YELLOW]),
                            )
                        )
                    self.phase = "gameover"
                    self._set_engine_sound(False)
                    self._save_high_score()
                    if not self.game_over_sound_played:
                        self._play_sound("game_over")
                        self.game_over_sound_played = True
                    return

    def update_pickups(self) -> None:
        if self.obstacles_since_powerup >= self.next_pickup_dodge_target:
            slot = next((p for p in self.pickups if not p.active), None)
            if slot:
                slot.spawn(self.camera_y, self.rocket_x)
                self.obstacles_since_powerup = 0
                self.next_pickup_dodge_target = random.randint(PICKUP_SPAWN_MIN_DODGES, PICKUP_SPAWN_MAX_DODGES)

        rocket_cx = self.rocket_x + ROCKET_W / 2
        rocket_cy = self.rocket_y + ROCKET_H / 2

        for p in self.pickups:
            if not p.active:
                continue
            p.update()
            if p.y > self.camera_y + SCREEN_HEIGHT / 2 + p.size * 2:
                p.active = False
                continue

            dist = math.hypot(rocket_cx - p.x, rocket_cy - p.y)
            if dist < (p.size + ROCKET_W / 2):
                if p.kind == "fuel":
                    self.fuel = min(MAX_FUEL, self.fuel + FUEL_PER_PICKUP)
                    self._play_sound("pickup_fuel")
                elif p.kind == "shield":
                    self.shield_active = True
                    self.shield_timer = SHIELD_DURATION_FRAMES
                    self._play_sound("pickup_shield")
                else:
                    self.clear_active = True
                    self.clear_timer = CLEAR_DURATION_FRAMES
                    self._play_sound("pickup_clear")
                p.active = False

    def update_particles(self) -> None:
        self.particles = [p for p in self.particles if p.update()]
        if len(self.particles) > 500:
            self.particles = self.particles[-500:]

    def draw(self) -> None:
        if self.phase == "menu":
            self.draw_menu()
            pygame.display.flip()
            return

        if self.shake_strength > 0:
            self.camera_y += random.uniform(-self.shake_strength, self.shake_strength)
        self.draw_background()
        self.draw_clouds()
        self.draw_ground()
        self.draw_particles()
        self.draw_asteroids()
        self.draw_pickups()

        if self.phase in ("playing", "gameover", "countdown"):
            self.draw_rocket()
        if self.shield_active:
            self.draw_shield()

        if self.phase == "countdown":
            self.draw_countdown()
        elif self.phase == "playing":
            self.draw_hud()
        elif self.phase == "gameover":
            self.draw_hud()
            self.draw_gameover()

        pygame.display.flip()

    def draw_menu(self) -> None:
        self.screen.fill((8, 8, 30))
        self.draw_starfield(1.0, use_camera=False)
        # Show rocket on menu so player can always see it.
        old_cam_y = self.camera_y
        self.camera_y = self.rocket_y + SCREEN_HEIGHT / 2 - ROCKET_DEFAULT_SCREEN_Y
        self.draw_rocket()
        self.camera_y = old_cam_y
        title = self.font_lg.render("ROCKET LAUNCH", True, ORANGE)
        self.screen.blit(title, (SCREEN_WIDTH / 2 - title.get_width() / 2, 180))
        hi = self.font_sm.render(f"BEST: {self.high_score}", True, CYAN)
        self.screen.blit(hi, (SCREEN_WIDTH / 2 - hi.get_width() / 2, 235))

        lines = [
            ("Press ENTER to Start", WHITE, self.font_md, 290),
            ("A/D or LEFT/RIGHT = Steer", LIGHT_GRAY, self.font_sm, 380),
            ("UP/DOWN = Throttle", LIGHT_GRAY, self.font_sm, 410),
            ("Collect F = Fuel, S = Shield, C = Clear", CYAN, self.font_sm, 440),
            ("M = Mute/Unmute Sound", LIGHT_GRAY, self.font_sm, 470),
            ("ESC = Quit", LIGHT_GRAY, self.font_sm, 500),
        ]
        for text, color, font, y in lines:
            r = font.render(text, True, color)
            self.screen.blit(r, (SCREEN_WIDTH / 2 - r.get_width() / 2, y))

    def draw_starfield(self, visibility: float, use_camera: bool) -> None:
        if visibility <= 0.01:
            return
        vis = max(0.0, min(1.0, visibility))
        t = self.frame / FPS
        for star in self.stars:
            sx = star["x"]
            sy = star["y"]
            if use_camera:
                sx = (sx - (self.rocket_x - SCREEN_WIDTH / 2) * star["depth"] * 0.10) % SCREEN_WIDTH
                sy = (sy - self.camera_y * star["depth"] * 0.08) % SCREEN_HEIGHT
            tw = 0.65 + 0.35 * math.sin(t * star["twinkle"] + star["phase"])
            bright = int(110 + 145 * vis * tw)
            col = (bright, bright, bright)
            if star["size"] <= 1:
                self.screen.set_at((int(sx), int(sy)), col)
            else:
                pygame.draw.circle(self.screen, col, (int(sx), int(sy)), int(star["size"]))

    def draw_background(self) -> None:
        altitude = max(0, GROUND_Y - self.rocket_y)
        sky_t = min(1.0, altitude / 5000)
        for y in range(SCREEN_HEIGHT):
            blend = y / SCREEN_HEIGHT
            r = int((12 + blend * 40) * (1 - sky_t))
            g = int((25 + blend * 90) * (1 - sky_t))
            b = int((80 + blend * 160) * (1 - sky_t) + 40 * sky_t)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SCREEN_WIDTH, y))

        star_visibility = min(1.0, max(0.15, altitude / 4200))
        self.draw_starfield(star_visibility, use_camera=True)

    def draw_clouds(self) -> None:
        altitude = max(0, GROUND_Y - self.rocket_y)
        alpha_mul = max(0.0, 1.0 - altitude / 5500)
        for c in self.clouds:
            sy = world_to_screen_y(c["y"], self.camera_y)
            if sy < -80 or sy > SCREEN_HEIGHT + 80:
                continue
            surf = pygame.Surface((c["w"], c["h"]), pygame.SRCALPHA)
            a = int(170 * alpha_mul)
            pygame.draw.ellipse(surf, (205, 210, 225, a), (0, 0, c["w"], c["h"]))
            pygame.draw.ellipse(surf, (225, 230, 240, a), (c["w"] // 4, 0, c["w"] // 2, c["h"] * 3 // 4))
            self.screen.blit(surf, (int(c["x"]), int(sy)))

    def draw_ground(self) -> None:
        gy = world_to_screen_y(GROUND_Y, self.camera_y)
        if gy < SCREEN_HEIGHT:
            pygame.draw.rect(self.screen, DARK_GREEN, (0, int(gy), SCREEN_WIDTH, SCREEN_HEIGHT - int(gy)))
            pygame.draw.rect(self.screen, DARK_GRAY, (SCREEN_WIDTH // 2 - 60, int(gy) - 20, 120, 20))

    def draw_rocket(self) -> None:
        sy = int(world_to_screen_y(self.rocket_y, self.camera_y))
        x = int(self.rocket_x)
        y = sy
        tilt = int(self.rocket_tilt)
        band_h = max(6, int(ROCKET_H * 0.05))
        win_r = max(5, int(ROCKET_W * 0.2))
        fin_w = max(12, int(ROCKET_W * 0.45))
        fin_h = max(16, int(ROCKET_H * 0.11))
        booster_w = max(16, int(ROCKET_W * 0.55))
        booster_y = int(y + ROCKET_H * 0.72)

        if self.stage == 1:
            pygame.draw.rect(self.screen, GRAY, (x - booster_w + tilt, booster_y, booster_w, ROCKET_THRUSTER_H))
            pygame.draw.rect(self.screen, GRAY, (x + ROCKET_W + tilt, booster_y, booster_w, ROCKET_THRUSTER_H))
            pygame.draw.rect(self.screen, RED, (x - booster_w + tilt, booster_y + ROCKET_THRUSTER_H // 2, booster_w, band_h))
            pygame.draw.rect(self.screen, RED, (x + ROCKET_W + tilt, booster_y + ROCKET_THRUSTER_H // 2, booster_w, band_h))

        body = [
            (x + tilt, y),
            (x + ROCKET_W + tilt, y),
            (x + ROCKET_W - tilt, y + ROCKET_H),
            (x - tilt, y + ROCKET_H),
        ]
        pygame.draw.polygon(self.screen, LIGHT_GRAY, body)
        pygame.draw.polygon(self.screen, GRAY, body, 1)
        pygame.draw.rect(self.screen, RED, (x + tilt, int(y + ROCKET_H * 0.25), ROCKET_W, band_h))
        pygame.draw.rect(self.screen, RED, (x + tilt, int(y + ROCKET_H * 0.55), ROCKET_W, band_h))

        window_cy = int(y + ROCKET_H * 0.40)
        pygame.draw.circle(self.screen, BLUE, (x + ROCKET_W // 2 + tilt, window_cy), win_r)
        pygame.draw.circle(self.screen, WHITE, (x + ROCKET_W // 2 + tilt, window_cy), win_r, 2)

        nose = [(x + tilt, y), (x + ROCKET_W // 2 + tilt, y - ROCKET_NOSE_H), (x + ROCKET_W + tilt, y)]
        pygame.draw.polygon(self.screen, WHITE, nose)
        pygame.draw.polygon(self.screen, GRAY, nose, 1)

        pygame.draw.polygon(self.screen, GRAY, [(x - tilt, y + ROCKET_H - fin_h), (x - fin_w - tilt, y + ROCKET_H), (x - tilt, y + ROCKET_H)])
        pygame.draw.polygon(
            self.screen,
            GRAY,
            [(x + ROCKET_W - tilt, y + ROCKET_H - fin_h), (x + ROCKET_W + fin_w - tilt, y + ROCKET_H), (x + ROCKET_W - tilt, y + ROCKET_H)],
        )

    def draw_shield(self) -> None:
        cx = int(self.rocket_x + ROCKET_W / 2)
        cy = int(world_to_screen_y(self.rocket_y, self.camera_y) + ROCKET_H / 2)
        radius = 90 + int(math.sin(self.frame * 0.25) * 14)
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*CYAN, 95), (radius, radius), radius, 4)
        pygame.draw.circle(s, (*CYAN, 40), (radius, radius), radius - 8)
        self.screen.blit(s, (cx - radius, cy - radius))

    def draw_asteroids(self) -> None:
        for a in self.asteroids:
            a.draw(self.screen, self.camera_y)

    def draw_pickups(self) -> None:
        for p in self.pickups:
            p.draw(self.screen, self.camera_y, self.font_sm)

    def draw_particles(self) -> None:
        for p in self.particles:
            p.draw(self.screen, self.camera_y)

    def draw_hud(self) -> None:
        pygame.draw.rect(self.screen, DARK_GRAY, (14, 14, 166, 24))
        fuel_pct = max(0.0, min(1.0, self.fuel / MAX_FUEL))
        color = GREEN if fuel_pct > 0.5 else YELLOW if fuel_pct > 0.25 else RED
        pygame.draw.rect(self.screen, color, (16, 16, int(162 * fuel_pct), 20))
        pygame.draw.rect(self.screen, WHITE, (14, 14, 166, 24), 1)

        self.screen.blit(self.font_sm.render(f"FUEL: {int(self.fuel)}", True, WHITE), (20, 18))
        self.screen.blit(self.font_md.render(f"Score: {self.score}", True, WHITE), (SCREEN_WIDTH - 220, 10))
        self.screen.blit(self.font_sm.render(f"Best: {self.high_score}", True, LIGHT_GRAY), (SCREEN_WIDTH - 190, 46))
        altitude = max(0, int(GROUND_Y - self.rocket_y))
        self.screen.blit(self.font_sm.render(f"Alt: {altitude}m", True, CYAN), (SCREEN_WIDTH - 140, 52))

        if self.fuel <= LOW_FUEL_THRESHOLD and self.phase == "playing":
            self.screen.blit(self.font_sm.render("LOW FUEL", True, RED), (20, 48))

        if self.play_frame_count < CONTROL_LOCK_SECONDS * FPS and self.phase == "playing":
            left = CONTROL_LOCK_SECONDS - int(self.play_frame_count / FPS)
            self.screen.blit(self.font_sm.render(f"Controls unlock in: {left}s", True, YELLOW), (20, 72))

        if self.play_frame_count < ASTEROID_START_SECONDS * FPS and self.phase == "playing":
            left = ASTEROID_START_SECONDS - int(self.play_frame_count / FPS)
            self.screen.blit(self.font_sm.render(f"Asteroids start in: {left}s", True, CYAN), (20, 96))

        y = 78
        if self.combo_count > 0 and self.combo_timer > 0:
            combo_txt = self.font_sm.render(f"COMBO x{self.combo_count}", True, ORANGE)
            self.screen.blit(combo_txt, (SCREEN_WIDTH // 2 - combo_txt.get_width() // 2, 14))
        if self.shield_active:
            pygame.draw.rect(self.screen, (35, 150, 210), (14, y, 96, 20))
            self.screen.blit(self.font_sm.render("SHIELD", True, WHITE), (20, y + 2))
            y += 24
        if self.clear_active:
            pygame.draw.rect(self.screen, (175, 165, 30), (14, y, 96, 20))
            self.screen.blit(self.font_sm.render("CLEAR", True, BLACK), (24, y + 2))

    def draw_countdown(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 92))
        self.screen.blit(overlay, (0, 0))
        pulse = 1.0 + 0.14 * math.sin(self.frame * 0.45)
        if self.countdown_val > 0:
            label = str(self.countdown_val)
            c = (255, 230, 120)
        else:
            label = "GO!"
            c = (255, 120, 70)
        text = self.font_lg.render(label, True, c)
        text = pygame.transform.smoothscale(
            text,
            (max(1, int(text.get_width() * pulse)), max(1, int(text.get_height() * pulse))),
        )
        self.screen.blit(text, (SCREEN_WIDTH / 2 - text.get_width() / 2, SCREEN_HEIGHT / 2 - text.get_height() / 2))

        line = self.font_sm.render("3  2  1  GO!  Ignite and climb!", True, (250, 245, 235))
        self.screen.blit(line, (SCREEN_WIDTH / 2 - line.get_width() / 2, SCREEN_HEIGHT / 2 + 78))

    def draw_gameover(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((80, 0, 0, 115))
        self.screen.blit(overlay, (0, 0))

        t = self.font_lg.render("GAME OVER", True, RED)
        s = self.font_md.render(f"Final Score: {self.score}", True, WHITE)
        b = self.font_sm.render(f"Best Score: {self.high_score}", True, CYAN)
        r = self.font_sm.render("R = Restart    Q / ESC = Quit", True, GREEN)
        self.screen.blit(t, (SCREEN_WIDTH / 2 - t.get_width() / 2, SCREEN_HEIGHT / 2 - 90))
        self.screen.blit(s, (SCREEN_WIDTH / 2 - s.get_width() / 2, SCREEN_HEIGHT / 2 - 8))
        self.screen.blit(b, (SCREEN_WIDTH / 2 - b.get_width() / 2, SCREEN_HEIGHT / 2 + 26))
        self.screen.blit(r, (SCREEN_WIDTH / 2 - r.get_width() / 2, SCREEN_HEIGHT / 2 + 48))


if __name__ == "__main__":
    RocketGame().run()
