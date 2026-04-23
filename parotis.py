#!/usr/bin/env python3
"""
PAROTIS v3 – Isometrische Habbo-Style Welt
Inspiriert von Black Mirror S07E04 – Plaything

Start: python3 parotis.py
Maus:  python3 parotis.py --mouse
"""

import pygame
import sqlite3
import math
import random
import time
import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from pathlib import Path

# ─── Pfade ────────────────────────────────────────────────────────────────────
HOME      = Path.home()
DATA_DIR  = HOME / ".parotis"
DB_PATH   = DATA_DIR / "world.db"
INBOX_DIR = HOME / "parotis-inbox"

GOD_IMAGE_PATH: Optional[str] = None
for _ext in ("jpg", "jpeg", "png", "bmp", "webp"):
    _p = INBOX_DIR / f"god.{_ext}"
    if _p.exists():
        GOD_IMAGE_PATH = str(_p)
        break

# ─── Konstanten ───────────────────────────────────────────────────────────────
GRID_W   = 30
GRID_H   = 20
FPS      = 60
SAVE_EVERY = 30
MAX_POP  = 80
INIT_POP = 18
MAX_FOOD = 90
FOOD_RATE = 0.032
LIFESPAN = 60 * 60 * 7

# Iso-Parameter (nach Screen-Init gesetzt)
TILE_W = 64
TILE_H = 32
ISO_OX = 0
ISO_OY = 0

# Farben
C_BG       = (8, 18, 10)
C_WHITE    = (255, 255, 255)
C_HUD      = (160, 210, 160)
C_HUD_DIM  = (90, 130, 90)
C_MAIL_GLW = (255, 220, 80)
C_SHRINE   = (255, 240, 180)

# Kachel-Typen
T_GRASS = 0
T_DARK  = 1
T_STONE = 2
T_WATER = 3
T_SAND  = 4

TILE_COLORS = {
    # typ: (top, left, right)
    T_GRASS: ((55, 125, 55),  (42, 100, 42),  (68, 148, 68)),
    T_DARK:  ((32, 80, 32),   (22, 60, 22),   (42, 95, 42)),
    T_STONE: ((130, 130, 120),(110, 110, 100),(150, 150, 140)),
    T_WATER: ((45, 90, 170),  (35, 70, 140),  (55, 110, 195)),
    T_SAND:  ((195, 175, 105),(165, 148, 82), (215, 198, 125)),
}

SKIN_TONES = [
    (245, 208, 168), (225, 180, 135), (185, 138, 95),
    (155, 105, 65),  (95, 65, 45),
]

GLYPHS = ["◆", "○", "✦", "◇", "★", "△", "▽", "⬡"]


# ─── Iso-Hilfsfunktionen ──────────────────────────────────────────────────────
def iso(gx: float, gy: float) -> Tuple[int, int]:
    sx = ISO_OX + int((gx - gy) * TILE_W // 2)
    sy = ISO_OY + int((gx + gy) * TILE_H // 2)
    return sx, sy


def screen_to_grid(sx: int, sy: int) -> Tuple[float, float]:
    dx = (sx - ISO_OX) / (TILE_W / 2)
    dy = (sy - ISO_OY) / (TILE_H / 2)
    return (dx + dy) / 2, (dy - dx) / 2


# ─── Tilemap ──────────────────────────────────────────────────────────────────
def make_tilemap() -> List[List[int]]:
    rng = random.Random(42)   # Seed für reproducible Map
    tm  = [[T_GRASS] * GRID_H for _ in range(GRID_W)]

    # Dunkle Gras-Flecken
    for _ in range(18):
        cx = rng.randint(2, GRID_W - 3)
        cy = rng.randint(2, GRID_H - 3)
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if rng.random() < 0.45 - abs(dx) * 0.05 - abs(dy) * 0.05:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        tm[nx][ny] = T_DARK

    # Zwei Steinpfade
    for start_y in [GRID_H // 3, GRID_H * 2 // 3]:
        y = start_y
        for x in range(0, GRID_W):
            y = max(1, min(GRID_H - 2, y + rng.randint(-1, 1)))
            for dy in range(-1, 2):
                ny = y + dy
                if 0 <= ny < GRID_H:
                    tm[x][ny] = T_STONE
            # Rand dunkler
            for dy in (-2, 2):
                ny = y + dy
                if 0 <= ny < GRID_H and tm[x][ny] != T_STONE:
                    tm[x][ny] = T_DARK

    # Sand-Oasen
    for _ in range(10):
        cx = rng.randint(2, GRID_W - 3)
        cy = rng.randint(2, GRID_H - 3)
        r  = rng.randint(1, 3)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        tm[nx][ny] = T_SAND

    # Wasser-Teiche (innen)
    for _ in range(3):
        cx = rng.randint(4, GRID_W - 5)
        cy = rng.randint(4, GRID_H - 5)
        for dx in range(-2, 3):
            for dy in range(-1, 2):
                if rng.random() < 0.7:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        tm[nx][ny] = T_WATER

    return tm


def _draw_tile_details(s, sx, sy, tw, th, tile_type, rng_seed):
    """Pixel-Art Details auf der Kachel-Oberfläche."""
    rng = random.Random(rng_seed)
    tc = TILE_COLORS[tile_type][0]

    if tile_type == T_GRASS:
        # Kleine Gras-Halme und Punkte
        for _ in range(3):
            gx2 = sx + rng.randint(-tw // 4, tw // 4)
            gy2 = sy + rng.randint(-th // 4, th // 4)
            pygame.draw.line(s, (45, 105, 45), (gx2, gy2), (gx2 + rng.randint(-2,2), gy2 - 3), 1)
        # Blümchen
        if rng.random() < 0.12:
            fx = sx + rng.randint(-tw // 5, tw // 5)
            fy = sy + rng.randint(-th // 5, th // 5)
            fcol = rng.choice([(255,220,80),(255,160,200),(180,220,255),(255,160,80)])
            pygame.draw.circle(s, fcol, (fx, fy), 2)
            pygame.draw.circle(s, (255,255,255), (fx, fy), 1)

    elif tile_type == T_DARK:
        # Moos-Muster
        for _ in range(2):
            mx = sx + rng.randint(-tw // 5, tw // 5)
            my = sy + rng.randint(-th // 5, th // 5)
            pygame.draw.circle(s, (25, 65, 25), (mx, my), rng.randint(1,2))

    elif tile_type == T_STONE:
        # Pflastersteine-Linien
        pygame.draw.line(s, (110, 110, 100), (sx - 4, sy - 1), (sx + 4, sy - 1), 1)
        pygame.draw.line(s, (110, 110, 100), (sx, sy - 4),     (sx, sy + 2),     1)
        # Moos in Ritzen
        if rng.random() < 0.25:
            pygame.draw.circle(s, (70, 110, 60), (sx + rng.randint(-3,3), sy), 1)

    elif tile_type == T_WATER:
        # Wellen-Linien
        for i in range(2):
            wx = sx + rng.randint(-tw // 4, tw // 4)
            wy = sy + rng.randint(-th // 5, th // 5)
            pygame.draw.line(s, (65, 110, 190), (wx - 3, wy), (wx + 3, wy), 1)
        # Glanz
        if rng.random() < 0.2:
            pygame.draw.circle(s, (120, 180, 255), (sx + rng.randint(-4,4), sy + rng.randint(-3,3)), 1)

    elif tile_type == T_SAND:
        # Sand-Körner
        for _ in range(4):
            pygame.draw.circle(s, (210, 195, 130),
                (sx + rng.randint(-tw//4, tw//4), sy + rng.randint(-th//5, th//5)), 1)
        # Kleine Steine
        if rng.random() < 0.15:
            pygame.draw.circle(s, (180, 170, 140),
                (sx + rng.randint(-5,5), sy + rng.randint(-3,3)), 2)


def render_floor(screen_w: int, screen_h: int, tilemap: List[List[int]]) -> pygame.Surface:
    s   = pygame.Surface((screen_w, screen_h))
    s.fill(C_BG)
    tw, th = TILE_W, TILE_H
    wall_h = th // 4

    # Alle Tiles von hinten nach vorne (Tiefensortierung)
    tiles = []
    for gx in range(-1, GRID_W + 1):
        for gy in range(-1, GRID_H + 1):
            tiles.append((gx + gy, gx, gy))
    tiles.sort(key=lambda x: x[0])

    for _, gx, gy in tiles:
        t = (T_WATER if (gx < 0 or gx >= GRID_W or gy < 0 or gy >= GRID_H)
             else tilemap[gx][gy])
        sx, sy = iso(gx, gy)
        tc, lc, rc = TILE_COLORS[t]

        # Top-Fläche (Diamant)
        top_pts = [(sx, sy - th // 2), (sx + tw // 2, sy),
                   (sx, sy + th // 2), (sx - tw // 2, sy)]
        pygame.draw.polygon(s, tc, top_pts)

        # Links-Wand (sichtbar)
        lft_pts = [(sx - tw // 2, sy), (sx, sy + th // 2),
                   (sx, sy + th // 2 + wall_h), (sx - tw // 2, sy + wall_h)]
        pygame.draw.polygon(s, lc, lft_pts)

        # Rechts-Wand (sichtbar)
        rgt_pts = [(sx, sy + th // 2), (sx + tw // 2, sy),
                   (sx + tw // 2, sy + wall_h), (sx, sy + th // 2 + wall_h)]
        pygame.draw.polygon(s, rc, rgt_pts)

        # Kanten-Linien für Pixeligkeit
        pygame.draw.polygon(s, (0, 0, 0), top_pts, 1)
        pygame.draw.line(s, (0, 0, 0), (sx - tw//2, sy), (sx - tw//2, sy + wall_h), 1)
        pygame.draw.line(s, (0, 0, 0), (sx + tw//2, sy), (sx + tw//2, sy + wall_h), 1)
        pygame.draw.line(s, (0, 0, 0),
            (sx - tw//2, sy + wall_h), (sx, sy + th//2 + wall_h), 1)
        pygame.draw.line(s, (0, 0, 0),
            (sx + tw//2, sy + wall_h), (sx, sy + th//2 + wall_h), 1)

        # Pixel-Details auf der Oberfläche
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
            _draw_tile_details(s, sx, sy - th // 4, tw, th, t, gx * 1000 + gy)

    return s


# ─── Genome ───────────────────────────────────────────────────────────────────
@dataclass
class Genome:
    col_r:     float = 0.5   # Shirt-Farbe R
    col_g:     float = 0.5   # Shirt-Farbe G
    col_b:     float = 0.5   # Shirt-Farbe B
    skin_tone: float = 0.5   # Hautton-Index
    hair_dark: float = 0.5   # Haar-Dunkelheit
    size:      float = 0.5   # Körpergrösse
    speed:     float = 0.5
    social:    float = 0.5
    intellect: float = 0.5
    hunger_r:  float = 0.5
    courage:   float = 0.5
    repro:     float = 0.5
    piety:     float = 0.5
    mut_rate:  float = 0.05

    def shirt(self):
        return (int(40 + self.col_r * 215),
                int(40 + self.col_g * 215),
                int(40 + self.col_b * 215))

    def shirt_dark(self):
        r, g, b = self.shirt()
        return (max(0, r - 60), max(0, g - 60), max(0, b - 60))

    def shirt_light(self):
        r, g, b = self.shirt()
        return (min(255, r + 50), min(255, g + 50), min(255, b + 50))

    def skin(self):
        idx = int(self.skin_tone * (len(SKIN_TONES) - 1))
        return SKIN_TONES[max(0, min(len(SKIN_TONES) - 1, idx))]

    def hair(self):
        r, g, b = self.skin()
        d = self.hair_dark
        return (max(0, int(r * 0.45 * (1 - d))),
                max(0, int(g * 0.30 * (1 - d))),
                max(0, int(b * 0.20 * (1 - d))))

    def grid_size(self):
        return 0.3 + self.size * 0.4

    def px_speed(self):
        return 0.025 + self.speed * 0.07

    def hunger_rate(self):
        return 0.00004 + self.hunger_r * 0.00018

    def char_h(self):
        return int(26 + self.size * 14)

    def crossover(self, other: 'Genome') -> 'Genome':
        genes = {}
        for name in self.__dataclass_fields__:
            val = getattr(self, name) if random.random() < 0.5 else getattr(other, name)
            if name != 'mut_rate':
                val = max(0.0, min(1.0, val + random.gauss(0, self.mut_rate)))
            genes[name] = val
        return Genome(**genes)

    @classmethod
    def rand(cls):
        return cls(**{n: random.random() if n != 'mut_rate'
                      else random.uniform(0.01, 0.08)
                      for n in cls.__dataclass_fields__})


# ─── Zustände ─────────────────────────────────────────────────────────────────
class S:
    WANDER   = "wander"
    FOOD     = "food"
    MATE     = "mate"
    SLEEP    = "sleep"
    SOCIAL   = "social"
    WORSHIP  = "worship"
    FLEE_GOD = "flee_god"
    CURIOUS  = "curious"
    MAILRUN  = "mailrun"


# ─── Glyph-Blase ──────────────────────────────────────────────────────────────
class GlyphBubble:
    def __init__(self, gx: float, gy: float, col: Tuple):
        self.gx, self.gy = gx, gy
        self.glyph = random.choice(GLYPHS)
        self.col   = col
        self.life  = random.randint(55, 90)
        self.maxl  = self.life
        self.rise  = 0.0

    def update(self):
        self.life -= 1
        self.rise -= 0.012

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        if self.life <= 0:
            return
        alpha = int(255 * self.life / self.maxl)
        sx, sy = iso(self.gx, self.gy + self.rise)
        lbl = font.render(self.glyph, True, self.col)
        lbl.set_alpha(alpha)
        surf.blit(lbl, (sx - lbl.get_width() // 2, sy - 22))


# ─── Paroti ───────────────────────────────────────────────────────────────────
class Paroti:
    _nxt_id = 1

    def __init__(self, gx: float, gy: float,
                 genome: Genome = None, generation: int = 0, pid: int = None):
        self.id  = pid or Paroti._nxt_id
        Paroti._nxt_id += 1
        self.gx  = float(gx)
        self.gy  = float(gy)
        self.g   = genome or Genome.rand()
        self.gen = generation

        self.hunger   = random.uniform(0.08, 0.28)
        self.energy   = random.uniform(0.6, 1.0)
        self.happy    = random.uniform(0.4, 0.8)
        self.trust    = 0.3 + random.random() * 0.2
        self.piety    = 0.0
        self.age      = 0
        self.alive    = True
        self.state    = S.WANDER
        self.petting  = 0
        self.mate_cd  = 0
        self.children = 0
        self.parents: List[int] = []
        self.is_historian = False
        self.is_runner    = False

        a = random.uniform(0, math.tau)
        spd = self.g.px_speed()
        self.vx = math.cos(a) * spd
        self.vy = math.sin(a) * spd
        self.t  = random.randint(0, 100)
        self.facing_right = True
        self._shrine_cd = 0
        self.bubbles: List[GlyphBubble] = []
        self.dream_t = 0

    @property
    def _sz(self):
        return self.g.grid_size()

    def depth_key(self):
        return self.gx + self.gy

    def update(self, world: 'World'):
        if not self.alive:
            return
        self.age += 1
        self.t   += 1
        self.hunger = min(1.0, self.hunger + self.g.hunger_rate())
        if self.state == S.SLEEP:
            self.energy  = min(1.0, self.energy + 0.004)
            self.dream_t += 1
        else:
            self.energy  = max(0.0, self.energy - 0.0004)
            self.dream_t = 0
        if self.petting > 0:
            self.petting -= 1
            self.happy = min(1.0, self.happy + 0.003)
        if self.hunger >= 1.0 or self.age > LIFESPAN:
            self.alive = False
            return
        if self.mate_cd > 0:
            self.mate_cd -= 1
        if self._shrine_cd > 0:
            self._shrine_cd -= 1

        for b in self.bubbles:
            b.update()
        self.bubbles = [b for b in self.bubbles if b.life > 0]
        if self.state == S.SOCIAL and random.random() < 0.02:
            self.bubbles.append(GlyphBubble(self.gx, self.gy, self.g.shirt()))

        self._decide(world)
        self._act(world)

        self.gx = max(0.5, min(GRID_W - 0.5, self.gx))
        self.gy = max(0.5, min(GRID_H - 0.5, self.gy))
        self.happy = max(0.0, min(1.0, self.happy - 0.0001))

    def _decide(self, world: 'World'):
        if self.is_runner and world.mailbox and world.mailbox.has_pending():
            self.state = S.MAILRUN
            return
        if self.hunger > 0.72:
            self.state = S.FOOD
            return
        if self.energy < 0.18:
            self.state = S.SLEEP
            return
        if self.state == S.SLEEP and self.energy > 0.85:
            self.state = S.WANDER
        if (self._shrine_cd == 0 and world.shrine
                and self.hunger < 0.6
                and self.state not in (S.FOOD, S.SLEEP)):
            dist = self._dist(world.shrine.gx, world.shrine.gy)
            if dist < 7 and random.random() < 0.003:
                if self.g.piety > 0.6:
                    self.state = S.WORSHIP
                elif self.g.courage < 0.35:
                    self.state = S.FLEE_GOD
                else:
                    self.state = S.CURIOUS
                self._shrine_cd = 60 * 8
                return
        if self.hunger > 0.42:
            self.state = S.FOOD
            return
        if (self.hunger < 0.28 and self.energy > 0.5
                and self.mate_cd == 0 and self.g.repro > 0.25
                and len(world.parotis) < MAX_POP):
            self.state = S.MATE
            return
        if self.state not in (S.SLEEP, S.FOOD, S.MATE, S.SOCIAL,
                               S.WORSHIP, S.FLEE_GOD, S.CURIOUS):
            if self.g.social > 0.55 and random.random() < 0.001:
                self.state = S.SOCIAL
            elif self.state != S.WANDER:
                self.state = S.WANDER

    def _act(self, world: 'World'):
        if self.state == S.WANDER:
            self._wander()
        elif self.state == S.FOOD:
            f = world.nearest_food(self.gx, self.gy)
            if f:
                self._toward(f.gx, f.gy)
                if self._dist(f.gx, f.gy) < self._sz + 0.5:
                    world.eat_food(f)
                    self.hunger = max(0.0, self.hunger - 0.65)
                    self.happy  = min(1.0, self.happy + 0.12)
                    self.state  = S.WANDER
            else:
                self._wander()
        elif self.state == S.MATE:
            mate = world.find_mate(self)
            if mate:
                self._toward(mate.gx, mate.gy)
                if self._dist(mate.gx, mate.gy) < self._sz + mate._sz + 0.3:
                    world.reproduce(self, mate)
                    self.mate_cd = 60 * 12
                    mate.mate_cd = 60 * 12
                    self.state   = S.WANDER
            else:
                self.state = S.WANDER
        elif self.state == S.SOCIAL:
            nb = world.nearest_paroti(self)
            if nb:
                if self._dist(nb.gx, nb.gy) > self._sz * 3.5:
                    self._toward(nb.gx, nb.gy)
                else:
                    self.happy = min(1.0, self.happy + 0.06)
                    self.state = S.WANDER
            else:
                self.state = S.WANDER
        elif self.state == S.SLEEP:
            self.vx *= 0.85
            self.vy *= 0.85
            self.gx += self.vx
            self.gy += self.vy
        elif self.state == S.WORSHIP and world.shrine:
            wx, wy = world.shrine.worship_spot(self.id)
            self._toward(wx, wy)
            if self._dist(wx, wy) < 0.4:
                self.vx *= 0.1
                self.vy *= 0.1
                self.piety = min(1.0, self.piety + 0.002)
                self.happy = min(1.0, self.happy + 0.001)
                if random.random() < 0.015:
                    self.bubbles.append(
                        GlyphBubble(self.gx, self.gy, (255, 230, 100)))
        elif self.state == S.FLEE_GOD and world.shrine:
            dx = self.gx - world.shrine.gx
            dy = self.gy - world.shrine.gy
            d  = math.hypot(dx, dy)
            if d < 5.0:
                self._move_dir(dx / max(d, 0.01), dy / max(d, 0.01))
            else:
                self.state = S.WANDER
        elif self.state == S.CURIOUS and world.shrine:
            if self._dist(world.shrine.gx, world.shrine.gy) > self._sz * 3:
                self._toward(world.shrine.gx, world.shrine.gy)
            else:
                if random.random() < 0.008:
                    self.bubbles.append(
                        GlyphBubble(self.gx, self.gy, (200, 200, 255)))
                if random.random() < 0.005:
                    self.state = S.WANDER
        elif self.state == S.MAILRUN and world.mailbox:
            self._toward(world.mailbox.gx, world.mailbox.gy)
            if self._dist(world.mailbox.gx, world.mailbox.gy) < self._sz + 0.8:
                world.mailbox.execute(world)
                self.happy = min(1.0, self.happy + 0.3)
                self.bubbles.append(
                    GlyphBubble(self.gx, self.gy, (255, 255, 100)))
                self.state = S.WANDER

    def _wander(self):
        if random.random() < 0.018:
            a   = random.uniform(0, math.tau)
            spd = self.g.px_speed()
            self.vx = math.cos(a) * spd
            self.vy = math.sin(a) * spd
        self.gx += self.vx
        self.gy += self.vy
        if self.vx != 0:
            self.facing_right = self.vx > 0

    def _toward(self, tx: float, ty: float):
        dx, dy = tx - self.gx, ty - self.gy
        d = math.hypot(dx, dy)
        if d > 0.01:
            spd = self.g.px_speed()
            self.vx = dx / d * spd
            self.vy = dy / d * spd
            self.gx += self.vx
            self.gy += self.vy
            self.facing_right = self.vx > 0

    def _move_dir(self, dx: float, dy: float):
        spd = self.g.px_speed()
        self.vx = dx * spd
        self.vy = dy * spd
        self.gx += self.vx
        self.gy += self.vy

    def _dist(self, tx: float, ty: float) -> float:
        return math.hypot(tx - self.gx, ty - self.gy)

    # ── Habbo-Style Zeichnen ──────────────────────────────────────────────────
    def draw(self, surf: pygame.Surface, font_g: pygame.font.Font,
             font_s: pygame.font.Font):
        if not self.alive:
            return
        for b in self.bubbles:
            b.draw(surf, font_g)

        sx, sy = iso(self.gx, self.gy)
        h  = self.g.char_h()
        t  = self.t
        fr = self.facing_right

        # Schlafen → flach liegend
        if self.state == S.SLEEP:
            self._draw_sleep(surf, sx, sy, h)
            return

        shirt = self.g.shirt()
        dark  = self.g.shirt_dark()
        light = self.g.shirt_light()
        skin  = self.g.skin()
        hair  = self.g.hair()

        # Schatten
        sh_surf = pygame.Surface((h + 4, h // 3), pygame.SRCALPHA)
        pygame.draw.ellipse(sh_surf, (0, 0, 0, 50), (0, 0, h + 4, h // 3))
        surf.blit(sh_surf, (sx - (h + 4) // 2, sy - h // 6))

        moving = self.state in (S.WANDER, S.FOOD, S.MATE, S.SOCIAL,
                                 S.MAILRUN, S.CURIOUS)
        walk   = int(math.sin(t * 0.28) * (h // 7)) if moving else 0

        # Beine & Schuhe
        lw = max(3, h // 7)
        lh = h // 3
        ly = sy - lh // 2
        shoe = (38, 28, 18)
        pygame.draw.rect(surf, dark, (sx - lw * 2, ly + walk, lw, lh))
        pygame.draw.rect(surf, dark, (sx + lw,     ly - walk, lw, lh))
        pygame.draw.rect(surf, shoe, (sx - lw * 2 - 1, ly + lh + walk,  lw + 2, lw), border_radius=1)
        pygame.draw.rect(surf, shoe, (sx + lw - 1,      ly + lh - walk, lw + 2, lw), border_radius=1)

        # Hüfte
        pygame.draw.rect(surf, dark,
            (sx - lw * 2, sy - lh - lw * 2, lw * 4, lw * 2), border_radius=1)

        # Shirt-Körper
        bh = h // 3
        bw = max(8, h // 2)
        by = sy - lh - lw * 2 - bh
        pygame.draw.rect(surf, shirt, (sx - bw // 2, by, bw, bh), border_radius=2)
        pygame.draw.line(surf, light, (sx, by + 2), (sx, by + bh - 4), 1)

        # Arme
        aw  = max(2, h // 10)
        swing = int(math.sin(t * 0.28 + 1.5) * (h // 9)) if moving else 0
        pygame.draw.rect(surf, shirt, (sx - bw // 2 - aw, by + swing,  aw, bh - 2))
        pygame.draw.circle(surf, skin, (sx - bw // 2 - aw // 2, by + bh - 2 + swing), aw)
        pygame.draw.rect(surf, shirt, (sx + bw // 2,       by - swing, aw, bh - 2))
        pygame.draw.circle(surf, skin, (sx + bw // 2 + aw // 2, by + bh - 2 - swing), aw)

        # Kopf
        hh = h // 3
        hw = max(6, int(hh * 0.88))
        hox = hw // 5 if fr else -(hw // 5)
        hy  = by - hh
        hx  = sx - hw // 2 + hox
        br  = max(2, hh // 4)
        pygame.draw.rect(surf, skin, (hx, hy, hw, hh), border_radius=br)

        # Haare
        pygame.draw.rect(surf, hair, (hx, hy, hw, hh // 3), border_radius=br)
        side_x = hx + hw - 2 if fr else hx
        pygame.draw.rect(surf, hair, (side_x, hy, 2, hh // 2))

        # Augen
        ew = max(2, hw // 5)
        ey = hy + hh // 3 + 1
        ex1 = hx + (hw // 2) if fr else hx + 2
        ex2 = hx + hw - ew - 2 if fr else hx + (hw // 2) - ew
        pygame.draw.rect(surf, (30, 20, 10), (ex1, ey, ew, ew))
        pygame.draw.rect(surf, (30, 20, 10), (ex2, ey, ew, ew))
        pygame.draw.rect(surf, (210, 230, 255), (ex1, ey, 1, 1))
        pygame.draw.rect(surf, (210, 230, 255), (ex2, ey, 1, 1))

        # Mund
        mx = hx + hw // 4
        mw = hw // 2
        my = ey + ew + 1
        if self.happy > 0.6:
            pygame.draw.arc(surf, (120, 60, 40),
                (mx, my, mw, ew), math.pi, 2 * math.pi, 1)
        elif self.happy < 0.3:
            pygame.draw.arc(surf, (120, 60, 40),
                (mx, my - ew // 2, mw, ew), 0, math.pi, 1)

        # Accessoires
        if self.g.intellect > 0.72:
            gc = (140, 170, 215)
            pygame.draw.rect(surf, gc, (ex1 - 1, ey - 1, ew + 2, ew + 2), 1)
            pygame.draw.rect(surf, gc, (ex2 - 1, ey - 1, ew + 2, ew + 2), 1)
            pygame.draw.line(surf, gc,
                (ex1 + ew, ey + ew // 2), (ex2, ey + ew // 2), 1)

        if self.g.piety > 0.72:
            pygame.draw.ellipse(surf, (255, 220, 50),
                (hx - 2, hy - 6, hw + 4, 5), 1)

        if self.is_historian:
            sx2 = sx + bw // 2 + aw + 3
            pygame.draw.line(surf, (160, 130, 80), (sx2, by), (sx2, by - bh), 2)
            pygame.draw.circle(surf, (220, 200, 100), (sx2, by - bh), 3)

        if self.is_runner:
            pygame.draw.rect(surf, (255, 220, 60), (sx - 4, hy - 11, 8, 6))
            pygame.draw.polygon(surf, (220, 180, 30),
                [(sx - 4, hy - 11), (sx, hy - 6), (sx + 4, hy - 11)])

        if self.petting > 0:
            alpha = int(155 * self.petting / 60)
            r     = h + 10
            gs    = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            lc    = self.g.shirt_light()
            pygame.draw.circle(gs, (*lc, alpha), (r, r), r)
            surf.blit(gs, (sx - r, sy - r))

        if self.gen >= 3:
            lbl = font_s.render(f"G{self.gen}", True, (200, 200, 200))
            lbl.set_alpha(175)
            surf.blit(lbl, (sx - lbl.get_width() // 2, hy - 14))

    def _draw_sleep(self, surf: pygame.Surface, sx: int, sy: int, h: int):
        shirt = self.g.shirt()
        skin  = self.g.skin()
        w = h + 8
        ph = max(4, h // 4)
        pygame.draw.ellipse(surf, shirt, (sx - w // 2, sy - ph, w, ph))
        pygame.draw.circle(surf, skin, (sx + w // 2 - ph, sy - ph // 2), ph)
        if self.dream_t > 30:
            dr    = h + 4
            ds    = pygame.Surface((dr * 3, dr * 3), pygame.SRCALPHA)
            pulse = int(math.sin(self.dream_t * 0.09) * 5)
            pygame.draw.circle(ds, (160, 140, 255, 28),
                (dr, dr), dr + pulse)
            surf.blit(ds, (sx - dr, sy - dr))

    def status_text(self) -> str:
        return {
            S.WANDER:   "wandert",
            S.FOOD:     "sucht Futter",
            S.MATE:     "sucht Partner",
            S.SLEEP:    "schläft",
            S.SOCIAL:   "sozialisiert",
            S.WORSHIP:  "betet an",
            S.FLEE_GOD: "flieht (Gott!)",
            S.CURIOUS:  "neugierig",
            S.MAILRUN:  "holt Post",
        }.get(self.state, self.state)


# ─── Futter – Pixel-Art Essen ────────────────────────────────────────────────
FOOD_TYPES = [
    "pizza", "kebab", "burger", "cake",
    "apple", "broccoli", "sushi", "taco",
    "watermelon", "donut",
]

FOOD_GLOW = {
    "pizza":      (240, 180, 40),
    "kebab":      (200, 120, 60),
    "burger":     (210, 150, 60),
    "cake":       (255, 150, 200),
    "apple":      (220, 50,  50),
    "broccoli":   (60,  200, 60),
    "sushi":      (255, 200, 180),
    "taco":       (240, 200, 80),
    "watermelon": (50,  200, 80),
    "donut":      (220, 140, 180),
}


class Food:
    def __init__(self, gx: float, gy: float):
        self.gx, self.gy = gx, gy
        self.typ = random.choice(FOOD_TYPES)
        self.sz  = random.uniform(0.75, 1.15)
        self.age = 0

    def update(self): self.age += 1
    def depth_key(self): return self.gx + self.gy

    def draw(self, surf: pygame.Surface):
        sx, sy = iso(self.gx, self.gy)
        t      = self.age
        bob    = int(math.sin(t * 0.09) * 1.8)
        sy    -= bob
        s      = max(6, int(11 * self.sz))
        gc     = FOOD_GLOW.get(self.typ, (200, 200, 100))

        # Glow unter dem Essen
        gw = s + 7
        gs = pygame.Surface((gw * 3, gw * 3), pygame.SRCALPHA)
        pygame.draw.ellipse(gs, (*gc, 35), (0, gw, gw * 3, gw))
        surf.blit(gs, (sx - gw - gw // 2, sy - gw // 2))

        if   self.typ == "pizza":      self._pizza(surf, sx, sy, s)
        elif self.typ == "kebab":      self._kebab(surf, sx, sy, s)
        elif self.typ == "burger":     self._burger(surf, sx, sy, s)
        elif self.typ == "cake":       self._cake(surf, sx, sy, s)
        elif self.typ == "apple":      self._apple(surf, sx, sy, s)
        elif self.typ == "broccoli":   self._broccoli(surf, sx, sy, s)
        elif self.typ == "sushi":      self._sushi(surf, sx, sy, s)
        elif self.typ == "taco":       self._taco(surf, sx, sy, s)
        elif self.typ == "watermelon": self._watermelon(surf, sx, sy, s)
        elif self.typ == "donut":      self._donut(surf, sx, sy, s)

    # ── Essen-Zeichnungen ────────────────────────────────────────────────────
    def _pizza(self, surf, sx, sy, s):
        # Dreieck-Slice
        pts = [(sx, sy - s * 2), (sx - s, sy), (sx + s, sy)]
        pygame.draw.polygon(surf, (210, 160, 80), pts)   # Teig
        inner = [(sx, sy - s * 2 + 3), (sx - s + 4, sy - 3), (sx + s - 4, sy - 3)]
        pygame.draw.polygon(surf, (200, 60, 40), inner)  # Sauce
        # Käse-Punkte
        for dx, dy in [(-2, -4), (2, -7), (0, -10), (-3, -11)]:
            pygame.draw.circle(surf, (240, 220, 60), (sx + dx, sy + dy), 2)
        # Pepperoni
        pygame.draw.circle(surf, (160, 40, 40), (sx - 1, sy - 6), 2)
        pygame.draw.circle(surf, (160, 40, 40), (sx + 2, sy - 12), 2)
        # Kruste
        pygame.draw.polygon(surf, (180, 130, 60), pts, 2)

    def _kebab(self, surf, sx, sy, s):
        # Spiess
        pygame.draw.line(surf, (180, 150, 80), (sx, sy), (sx, sy - s * 2 - 4), 2)
        # Fleisch & Gemüse abwechselnd
        chunks = [
            ((180, 100, 60), 3),   # Fleisch
            ((80, 180, 80),  2),   # Grün
            ((180, 100, 60), 3),
            ((220, 80, 60),  2),   # Rot (Tomate)
            ((180, 100, 60), 3),
        ]
        cy = sy - 3
        for col, h in chunks:
            pygame.draw.ellipse(surf, col, (sx - s // 2 - 1, cy - h * 2, s + 2, h * 2))
            cy -= h * 2 + 1
        # Griff
        pygame.draw.rect(surf, (210, 180, 100), (sx - 2, sy - 3, 4, 5), border_radius=1)

    def _burger(self, surf, sx, sy, s):
        bw = s + 4
        # Boden-Bun
        pygame.draw.ellipse(surf, (210, 160, 80),  (sx - bw // 2, sy - 4, bw, 6))
        # Patty
        pygame.draw.ellipse(surf, (120, 70, 30),   (sx - bw // 2 + 1, sy - 8, bw - 2, 5))
        # Salat
        pygame.draw.ellipse(surf, (60, 180, 60),   (sx - bw // 2 - 1, sy - 11, bw + 2, 4))
        # Käse
        pygame.draw.rect(surf,    (240, 210, 50),  (sx - bw // 2 + 1, sy - 14, bw - 2, 4))
        # Tomate
        pygame.draw.ellipse(surf, (220, 60, 50),   (sx - bw // 2 + 2, sy - 17, bw - 4, 3))
        # Oben-Bun
        pygame.draw.ellipse(surf, (210, 160, 80),  (sx - bw // 2, sy - 23, bw, 8))
        pygame.draw.ellipse(surf, (230, 185, 100), (sx - bw // 2 + 2, sy - 24, bw - 4, 4))
        # Sesam
        for dx in [-3, 0, 3]:
            pygame.draw.circle(surf, (240, 230, 160), (sx + dx, sy - 22), 1)

    def _cake(self, surf, sx, sy, s):
        cw = s + 3
        # Basis
        pygame.draw.rect(surf, (220, 160, 180), (sx - cw // 2, sy - s * 2, cw, s * 2), border_radius=2)
        # Schichten
        pygame.draw.line(surf, (255, 200, 210), (sx - cw // 2, sy - s), (sx + cw // 2, sy - s), 2)
        # Glasur oben
        pygame.draw.ellipse(surf, (255, 220, 230), (sx - cw // 2 - 1, sy - s * 2 - 3, cw + 2, 8))
        # Kerze
        pygame.draw.rect(surf, (255, 255, 180), (sx, sy - s * 2 - 10, 3, 8))
        # Flamme
        pygame.draw.circle(surf, (255, 180, 40), (sx + 1, sy - s * 2 - 11), 3)
        pygame.draw.circle(surf, (255, 240, 80), (sx + 1, sy - s * 2 - 11), 1)
        # Deko-Punkte
        for i, col in enumerate([(255,80,80),(80,80,255),(80,255,80)]):
            pygame.draw.circle(surf, col, (sx - cw // 2 + 3 + i * (cw // 3), sy - s - 4), 2)

    def _apple(self, surf, sx, sy, s):
        # Apfel-Körper
        pygame.draw.circle(surf, (210, 45, 45), (sx, sy - s), s)
        pygame.draw.circle(surf, (240, 80, 80), (sx - s // 3, sy - s - s // 3), s // 3)
        # Glanz
        pygame.draw.circle(surf, (255, 200, 200), (sx - s // 3, sy - s - s // 4), s // 4)
        # Stiel
        pygame.draw.line(surf, (100, 70, 30), (sx, sy - s * 2), (sx + 2, sy - s * 2 - 5), 2)
        # Blatt
        leaf_pts = [(sx + 2, sy - s * 2 - 4), (sx + 8, sy - s * 2 - 8),
                    (sx + 5, sy - s * 2 - 2)]
        pygame.draw.polygon(surf, (60, 160, 60), leaf_pts)

    def _broccoli(self, surf, sx, sy, s):
        # Stiel
        pygame.draw.rect(surf, (100, 150, 60), (sx - 2, sy - s, 4, s))
        # Baumkrone aus Kreisen
        crowns = [
            (0, -s * 2, s),
            (-s // 2 - 1, -s - s // 2, s // 2 + 2),
            (s // 2 + 1,  -s - s // 2, s // 2 + 2),
            (-s // 3, -s * 2 - s // 2, s // 2),
            (s // 3,  -s * 2 - s // 2, s // 2),
        ]
        for dx, dy, r in crowns:
            pygame.draw.circle(surf, (50, 160, 50),  (sx + dx, sy + dy), r)
            pygame.draw.circle(surf, (80, 200, 70),  (sx + dx - 1, sy + dy - 1), max(1, r - 2))
        # Textur-Punkte
        for dx, dy in [(-2,-s*2-2),(2,-s*2-2),(0,-s*2+2),(-3,-s-s//2),(3,-s-s//2)]:
            pygame.draw.circle(surf, (30, 120, 30), (sx+dx, sy+dy), 1)

    def _sushi(self, surf, sx, sy, s):
        sw = s + 3
        # Nori (schwarz)
        pygame.draw.rect(surf, (30, 30, 30), (sx - sw // 2, sy - s - 2, sw, s + 4), border_radius=2)
        # Reis
        pygame.draw.rect(surf, (250, 248, 240), (sx - sw // 2 + 1, sy - s, sw - 2, s), border_radius=1)
        # Fisch obenauf
        pygame.draw.ellipse(surf, (255, 160, 120), (sx - sw // 2 + 1, sy - s - 6, sw - 2, 7))
        pygame.draw.ellipse(surf, (255, 200, 180), (sx - sw // 2 + 3, sy - s - 5, sw - 6, 4))
        # Nori-Streifen seitlich
        pygame.draw.rect(surf, (20, 20, 20), (sx - sw // 2, sy - s - 2, 2, s + 4))
        pygame.draw.rect(surf, (20, 20, 20), (sx + sw // 2 - 2, sy - s - 2, 2, s + 4))

    def _taco(self, surf, sx, sy, s):
        # Taco-Shell (U-Form, schräg)
        shell_pts = [
            (sx - s, sy), (sx + s, sy),
            (sx + s - 2, sy - s), (sx - s + 2, sy - s),
        ]
        pygame.draw.polygon(surf, (220, 185, 80), shell_pts)
        pygame.draw.polygon(surf, (240, 210, 100), shell_pts, 2)
        # Füllung
        pygame.draw.rect(surf, (160, 80, 40),  (sx - s + 3, sy - s + 2, s * 2 - 6, 4))  # Fleisch
        pygame.draw.rect(surf, (60, 180, 60),  (sx - s + 3, sy - s + 5, s * 2 - 6, 2))  # Salat
        pygame.draw.rect(surf, (220, 60, 50),  (sx - s + 3, sy - s + 6, s * 2 - 6, 2))  # Salsa
        pygame.draw.rect(surf, (240, 230, 200),(sx - s + 3, sy - s + 7, s * 2 - 6, 3))  # Käse
        # Knuspriger Rand
        pygame.draw.arc(surf, (200, 160, 50),
            (sx - s - 1, sy - s - 1, s * 2 + 2, s * 2 + 2), math.pi, 2 * math.pi, 2)

    def _watermelon(self, surf, sx, sy, s):
        # Halbkreis (Scheibe)
        pygame.draw.circle(surf, (220, 50, 70),  (sx, sy - s // 2), s)
        pygame.draw.circle(surf, (255, 100, 100),(sx - s // 3, sy - s), s // 3)
        # Weisser Rand
        pygame.draw.circle(surf, (230, 230, 220),(sx, sy - s // 2), s, 3)
        # Schale
        pygame.draw.arc(surf, (50, 160, 60),
            (sx - s, sy - s * 2, s * 2, s * 2), math.pi, 2 * math.pi, 4)
        # Kerne
        for dx, dy in [(-3, -2), (2, -4), (-1, -7), (4, -1)]:
            pygame.draw.circle(surf, (30, 20, 20), (sx + dx, sy - s // 2 + dy), 2)

    def _donut(self, surf, sx, sy, s):
        # Donut-Ring
        pygame.draw.circle(surf, (210, 145, 85), (sx, sy - s), s)
        pygame.draw.circle(surf, (55, 125, 55),  (sx, sy - s), s // 3)  # Loch (Hintergrund)
        # Glasur
        pygame.draw.circle(surf, (240, 160, 190),(sx, sy - s), s - 2)
        pygame.draw.circle(surf, (55, 125, 55),  (sx, sy - s), s // 3)
        # Streusel
        sprinkle_cols = [(255,80,80),(80,80,255),(80,220,80),(255,220,80)]
        for i in range(6):
            a = i * math.pi / 3
            rx = sx + int(math.cos(a) * (s - 4))
            ry = (sy - s) + int(math.sin(a) * (s - 4))
            col = sprinkle_cols[i % len(sprinkle_cols)]
            pygame.draw.rect(surf, col, (rx - 1, ry - 2, 2, 4), border_radius=1)


# ─── Schrein ──────────────────────────────────────────────────────────────────
class Shrine:
    def __init__(self, gx: float, gy: float, image_path: Optional[str]):
        self.gx, self.gy = gx, gy
        self.t        = 0
        self.visitors = 0
        self.img      = self._load(image_path)

    def _load(self, path: Optional[str]) -> pygame.Surface:
        if path:
            try:
                img = pygame.image.load(path).convert_alpha()
                return pygame.transform.scale(img, (80, 80))
            except Exception:
                pass
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        for r2 in range(40, 0, -5):
            a = int(40 * r2 / 40)
            pygame.draw.circle(s, (255, 240, 180, a), (40, 40), r2)
        pygame.draw.circle(s, (255, 255, 220), (40, 40), 18)
        pygame.draw.circle(s, (30, 20, 0),     (40, 40), 10)
        pygame.draw.circle(s, (255, 220, 120), (40, 40), 4)
        return s

    def worship_spot(self, pid: int) -> Tuple[float, float]:
        a = (pid * 2.39996) % math.tau
        r = 2.2
        return (self.gx + math.cos(a) * r, self.gy + math.sin(a) * r)

    def depth_key(self):
        return self.gx + self.gy + 0.05

    def update(self):
        self.t += 1

    def draw(self, surf: pygame.Surface, font_s: pygame.font.Font):
        sx, sy = iso(self.gx, self.gy)
        t  = self.t
        tw = TILE_W
        th = TILE_H

        # Iso-Würfel Sockel
        top = [(sx, sy - th), (sx + tw // 2, sy - th // 2),
               (sx, sy), (sx - tw // 2, sy - th // 2)]
        lft = [(sx - tw // 2, sy - th // 2), (sx, sy),
               (sx, sy + th // 2), (sx - tw // 2, sy)]
        rgt = [(sx, sy), (sx + tw // 2, sy - th // 2),
               (sx + tw // 2, sy), (sx, sy + th // 2)]
        pygame.draw.polygon(surf, (160, 140, 100), top)
        pygame.draw.polygon(surf, (115, 98, 68),   lft)
        pygame.draw.polygon(surf, (135, 118, 82),  rgt)
        pygame.draw.polygon(surf, (180, 160, 120), top, 1)

        # Glow
        gr = 55 + int(math.sin(t * 0.04) * 8)
        gs = pygame.Surface((gr * 3, gr * 3), pygame.SRCALPHA)
        pygame.draw.circle(gs, (255, 240, 140, 22), (gr, gr), gr)
        surf.blit(gs, (sx - gr, sy - th - gr))

        # Bild
        surf.blit(self.img, (sx - 40, sy - th - 82))
        pygame.draw.rect(surf, C_SHRINE,
            (sx - 41, sy - th - 83, 82, 82), 2, border_radius=4)

        if self.visitors > 0:
            lbl = font_s.render(f"🙏 {self.visitors}", True, (255, 220, 80))
            surf.blit(lbl, (sx - 18, sy + th // 2 + 4))


# ─── Postfach ─────────────────────────────────────────────────────────────────
class Mailbox:
    def __init__(self, inbox_dir: Path, gx: float, gy: float,
                 screen_w: int, screen_h: int):
        self.dir      = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.gx, self.gy = gx, gy
        self.screen_w = screen_w
        self._pending : Optional[Path] = None
        self.t        = 0
        self.msg      = ""
        self.msg_timer = 0
        self._last_scan = 0.0

    def has_pending(self) -> bool:
        now = time.time()
        if now - self._last_scan > 2.0:
            self._last_scan = now
            self._scan()
        return self._pending is not None

    def _scan(self):
        if self._pending:
            return
        for f in sorted(self.dir.glob("*.txt")):
            self._pending = f
            return

    def execute(self, world: 'World'):
        if not self._pending:
            return
        p = self._pending
        try:
            for line in p.read_text(encoding="utf-8").strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(maxsplit=1)
                cmd   = parts[0].upper()
                arg   = parts[1] if len(parts) > 1 else ""
                self._run(cmd, arg, world)
            read_dir = self.dir / "gelesen"
            read_dir.mkdir(exist_ok=True)
            p.rename(read_dir / (p.stem + f"_{int(time.time())}.read"))
        except Exception as e:
            print(f"Postfach-Fehler: {e}")
        finally:
            self._pending = None

    def _run(self, cmd: str, arg: str, world: 'World'):
        print(f"📬 {cmd} {arg}")
        if   cmd == "REGEN":      world.rain();   self._show("🌧 Regen!")
        elif cmd == "FEST":       world.feast();  self._show("🎉 Grosses Fest!")
        elif cmd == "FRIEDEN":    world.peace();  self._show("☮ Friede!")
        elif cmd == "NEU":
            n = max(1, min(10, int(arg) if arg.isdigit() else 3))
            for _ in range(n): world.spawn_one()
            self._show(f"👶 {n} neue Parotis!")
        elif cmd == "ALLE_WECKEN": world.wakeall(); self._show("⚡ Alle wach!")
        elif cmd in ("NACHRICHT", "TIPP", "HILFE"):
            self._show(f"📜 {arg}")
        elif cmd == "BESTRAFT":
            vs = random.sample(world.parotis, min(3, len(world.parotis)))
            for v in vs: v.hunger = 0.95
            self._show("⚡ Gott ist zornig!")
        else:
            self._show(f"❓ Unbekannter Befehl: {cmd}")

    def _show(self, msg: str):
        self.msg       = msg
        self.msg_timer = 60 * 12

    def update(self):
        self.t += 1
        self.has_pending()
        if self.msg_timer > 0:
            self.msg_timer -= 1

    def depth_key(self):
        return self.gx + self.gy

    def draw(self, surf: pygame.Surface,
             font_s: pygame.font.Font, font_m: pygame.font.Font):
        sx, sy = iso(self.gx, self.gy)
        t   = self.t
        tw  = TILE_W // 2
        th  = TILE_H // 2
        glow = self.has_pending()
        pulse = math.sin(t * 0.15)

        if glow:
            top_col = (int(200 + pulse * 55), int(180 + pulse * 40), 50)
        else:
            top_col = (70, 115, 70)

        top = [(sx, sy - th), (sx + tw // 2, sy - th // 2),
               (sx, sy), (sx - tw // 2, sy - th // 2)]
        lft = [(sx - tw // 2, sy - th // 2), (sx, sy),
               (sx, sy + th // 2), (sx - tw // 2, sy)]
        rgt = [(sx, sy), (sx + tw // 2, sy - th // 2),
               (sx + tw // 2, sy), (sx, sy + th // 2)]
        pygame.draw.polygon(surf, top_col, top)
        pygame.draw.polygon(surf, (45, 75, 45), lft)
        pygame.draw.polygon(surf, (60, 100, 60), rgt)
        pygame.draw.polygon(surf, (180, 180, 180), top, 1)

        if glow:
            gr = 30
            gs = pygame.Surface((gr * 3, gr * 3), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, 220, 80, 50), (gr, gr), gr)
            surf.blit(gs, (sx - gr, sy - th - gr))
            pygame.draw.rect(surf, (255, 220, 80), (sx - 10, sy - th - 16, 20, 14))
            pygame.draw.polygon(surf, (200, 160, 30),
                [(sx - 10, sy - th - 16), (sx, sy - th - 8),
                 (sx + 10, sy - th - 16)])

        lbl = font_s.render("POST", True,
            (255, 240, 100) if glow else (160, 200, 160))
        surf.blit(lbl, (sx - lbl.get_width() // 2, sy + th // 2 + 2))

        if self.msg_timer > 0:
            alpha = min(255, self.msg_timer * 6)
            tw2   = font_m.size(self.msg)[0] + 28
            ts    = pygame.Surface((tw2, 44), pygame.SRCALPHA)
            ts.fill((0, 0, 0, 185))
            pygame.draw.rect(ts, (80, 160, 80, 120), (0, 0, tw2, 44), 1, border_radius=6)
            surf.blit(ts, (self.screen_w // 2 - tw2 // 2, 90))
            ml = font_m.render(self.msg, True, (255, 240, 150))
            ml.set_alpha(alpha)
            surf.blit(ml, (self.screen_w // 2 - ml.get_width() // 2, 97))


# ─── Touch-Menü ───────────────────────────────────────────────────────────────
class TouchMenu:
    ITEMS = [
        ("🌧", "Regen",        "rain"),
        ("🍎", "Grosses Fest", "feast"),
        ("☮",  "Frieden",      "peace"),
        ("👶", "Neues Leben",  "newlife"),
        ("📜", "Chronik",      "chronicle"),
        ("⚡", "Alle wecken",  "wakeall"),
        ("🔌", "Ausschalten",  "quit"),
    ]

    def __init__(self, W: int, H: int):
        self.W, self.H = W, H
        self.open  = False
        self.confirm_quit = False
        self.anim  = 0.0
        self._t    = 0
        self.tx    = 58
        self.ty    = H - 58
        self.bsz   = 76
        self.pad   = 10
        self._rects: List[pygame.Rect] = []
        self._build()

    def _build(self):
        self._rects.clear()
        cols = 3
        x0   = self.tx + 46
        y0   = self.ty
        for i in range(len(self.ITEMS)):
            col = i % cols
            row = i // cols
            rx  = x0 + col * (self.bsz + self.pad)
            ry  = y0 - row * (self.bsz + self.pad) - self.bsz
            self._rects.append(pygame.Rect(rx, ry, self.bsz, self.bsz))

    def update(self):
        self._t += 1
        if self.open:
            self.anim = min(1.0, self.anim + 0.12)
        else:
            self.anim = max(0.0, self.anim - 0.18)

    def toggle(self):
        self.open = not self.open
        self.confirm_quit = False

    def hit_toggle(self, x: int, y: int) -> bool:
        return math.hypot(x - self.tx, y - self.ty) < 44

    def hit_item(self, x: int, y: int) -> Optional[str]:
        if not self.open or self.anim < 0.3:
            return None
        for i, r in enumerate(self._rects):
            if r.collidepoint(x, y):
                return self.ITEMS[i][2]
        return None

    def draw(self, surf: pygame.Surface,
             font_s: pygame.font.Font, font_l: pygame.font.Font):
        t  = self._t
        tx, ty = self.tx, self.ty

        # Toggle-Button
        pulse = int(math.sin(t * 0.08) * 3) if not self.open else 0
        col   = (35, 95, 45) if not self.open else (115, 45, 28)
        brd   = (75, 175, 85) if not self.open else (195, 95, 55)
        r     = 34 + pulse
        gs = pygame.Surface((r * 3, r * 3), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*col, 55), (r, r), r)
        surf.blit(gs, (tx - r, ty - r))
        pygame.draw.circle(surf, col, (tx, ty), r)
        pygame.draw.circle(surf, brd, (tx, ty), r, 2)
        il = font_l.render("☰" if not self.open else "✕", True, C_WHITE)
        surf.blit(il, (tx - il.get_width() // 2, ty - il.get_height() // 2))

        if self.anim <= 0.01:
            return

        # Panel-Hintergrund
        if len(self._rects) > 0:
            rows = (len(self.ITEMS) + 2) // 3
            pw = 3 * (self.bsz + self.pad) + 16
            ph = rows * (self.bsz + self.pad) + 16
            px = tx + 38
            py = ty - ph + self.bsz + self.pad
            ps = pygame.Surface((pw, ph), pygame.SRCALPHA)
            ps.fill((8, 20, 10, 155))
            pygame.draw.rect(ps, (55, 115, 55, 100),
                (0, 0, pw, ph), 1, border_radius=10)
            surf.blit(ps, (px - 8, py - 8))

        for i, (emoji, label, _) in enumerate(self.ITEMS):
            if i >= len(self._rects):
                break
            rect  = self._rects[i]
            delay = i * 0.07
            prog  = max(0.0, (self.anim - delay) / (1 - delay + 0.01))
            if prog <= 0.0:
                continue
            alpha = int(255 * prog)
            oy    = int((1 - prog) * 20)

            bg = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            bg.fill((18, 42, 18, int(225 * prog)))
            pygame.draw.rect(bg,
                (55 + int(45 * prog), 130, 55 + int(45 * prog), alpha),
                (0, 0, rect.w, rect.h), 2, border_radius=10)
            surf.blit(bg, (rect.x, rect.y + oy))

            el = font_l.render(emoji, True, C_WHITE)
            el.set_alpha(alpha)
            ll = font_s.render(label,  True, C_HUD)
            ll.set_alpha(alpha)
            surf.blit(el, (rect.x + rect.w // 2 - el.get_width() // 2,
                           rect.y + oy + 8))
            surf.blit(ll, (rect.x + rect.w // 2 - ll.get_width() // 2,
                           rect.y + oy + rect.h - 18))

        if self.confirm_quit:
            cw, ch = 320, 100
            cx, cy = self.W // 2 - cw // 2, self.H // 2 - ch // 2
            cs = pygame.Surface((cw, ch), pygame.SRCALPHA)
            cs.fill((0, 0, 0, 215))
            pygame.draw.rect(cs, (195, 55, 55, 200),
                (0, 0, cw, ch), 2, border_radius=10)
            surf.blit(cs, (cx, cy))
            tl = font_s.render("Welt wirklich beenden?", True, (255, 100, 100))
            surf.blit(tl, (cx + cw // 2 - tl.get_width() // 2, cy + 14))
            for lbl, col2, rx in [
                    ("JA ✓",   (195, 55, 55), cx + 50),
                    ("NEIN ✕", (55, 155, 55), cx + 180)]:
                pygame.draw.rect(surf, col2,
                    (rx - 30, cy + 52, 90, 34), border_radius=8)
                tl2 = font_s.render(lbl, True, C_WHITE)
                surf.blit(tl2, (rx - tl2.get_width() // 2, cy + 62))

    def confirm_rects(self) -> Tuple[pygame.Rect, pygame.Rect]:
        cw, ch = 320, 100
        cx, cy = self.W // 2 - cw // 2, self.H // 2 - ch // 2
        return (pygame.Rect(cx + 20, cy + 52, 90, 34),
                pygame.Rect(cx + 150, cy + 52, 90, 34))


# ─── Welt ─────────────────────────────────────────────────────────────────────
class World:
    def __init__(self):
        self.parotis   : List[Paroti]            = []
        self.food      : List[Food]              = []
        self.shrine    : Optional[Shrine]        = None
        self.mailbox   : Optional[Mailbox]       = None
        self.tilemap   : List[List[int]]         = make_tilemap()
        self.t         = 0
        self.day       = 0
        self.max_gen   = 0
        self.total_born = 0
        self.total_died = 0
        self.chronicle : List[str]               = []

    def setup_shrine(self):
        self.shrine = Shrine(GRID_W * 0.72, GRID_H * 0.38, GOD_IMAGE_PATH)

    def setup_mailbox(self, screen_w: int, screen_h: int):
        self.mailbox = Mailbox(
            INBOX_DIR, GRID_W * 0.15, GRID_H * 0.75, screen_w, screen_h)

    def spawn_initial(self):
        for _ in range(INIT_POP):
            self.parotis.append(Paroti(
                random.uniform(1.0, GRID_W - 1.0),
                random.uniform(1.0, GRID_H - 1.0)))
        self.total_born = INIT_POP
        self._assign_roles()

    def spawn_one(self):
        if len(self.parotis) >= MAX_POP:
            return
        self.parotis.append(Paroti(
            random.uniform(1.0, GRID_W - 1.0),
            random.uniform(1.0, GRID_H - 1.0)))
        self.total_born += 1

    def _assign_roles(self):
        if not self.parotis:
            return
        for p in self.parotis:
            p.is_historian = False
            p.is_runner    = False
        max(self.parotis, key=lambda p: p.age).is_historian = True
        max(self.parotis, key=lambda p: p.g.intellect + p.g.courage).is_runner = True

    def update(self):
        self.t   += 1
        self.day  = self.t // (60 * 35)
        if len(self.food) < MAX_FOOD and random.random() < FOOD_RATE:
            self.food.append(Food(
                random.uniform(1.0, GRID_W - 1.0),
                random.uniform(1.0, GRID_H - 1.0)))
        for f in self.food:
            f.update()
        if self.shrine:
            self.shrine.update()
        if self.mailbox:
            self.mailbox.update()
        for p in self.parotis:
            p.update(self)
        dead = [p for p in self.parotis if not p.alive]
        if dead:
            self.total_died += len(dead)
            self.parotis = [p for p in self.parotis if p.alive]
            for p in dead:
                if p.gen >= 2:
                    self._log(
                        f"Tag {self.day}: #{p.id} (G{p.gen}) gestorben,"
                        f" {p.children} Kinder")
        if self.shrine:
            self.shrine.visitors = sum(
                1 for p in self.parotis if p.state == S.WORSHIP)
        if self.t % (60 * 60 * 5) == 0:
            self._assign_roles()
        if self.t % (60 * 60) == 0:
            self._log(
                f"Tag {self.day}: {len(self.parotis)} leben, "
                f"G{self.max_gen}, "
                f"Geb:{self.total_born}/Gest:{self.total_died}")

    def _log(self, msg: str):
        self.chronicle.append(msg)
        self.chronicle = self.chronicle[-80:]

    def draw(self, surf: pygame.Surface, floor: pygame.Surface,
             font_s: pygame.font.Font, font_m: pygame.font.Font,
             font_g: pygame.font.Font):
        surf.blit(floor, (0, 0))
        drawables = []
        for f in self.food:
            drawables.append((f.depth_key(), "food", f))
        for p in self.parotis:
            drawables.append((p.depth_key(), "paroti", p))
        if self.shrine:
            drawables.append((self.shrine.depth_key(), "shrine", self.shrine))
        if self.mailbox:
            drawables.append((self.mailbox.depth_key(), "mailbox", self.mailbox))
        drawables.sort(key=lambda x: x[0])
        for _, typ, obj in drawables:
            if   typ == "food":    obj.draw(surf)
            elif typ == "paroti":  obj.draw(surf, font_g, font_s)
            elif typ == "shrine":  obj.draw(surf, font_s)
            elif typ == "mailbox": obj.draw(surf, font_s, font_m)
        self._draw_hud(surf, font_s, font_m)

    def _draw_hud(self, surf: pygame.Surface,
                  font_s: pygame.font.Font, font_m: pygame.font.Font):
        lines = [
            (font_m, f"Parotis: {len(self.parotis)}", C_HUD),
            (font_s, f"Max. Generation: {self.max_gen}", C_HUD),
            (font_s, f"Geb: {self.total_born}  Gest: {self.total_died}", C_HUD_DIM),
            (font_s, f"Tag {self.day}", (200, 200, 140)),
        ]
        total_h = sum(f.get_height() for f, _, _ in lines) + 16
        bg = pygame.Surface((206, total_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 165))
        pygame.draw.rect(bg, (55, 115, 55, 100),
            (0, 0, 206, total_h), 1, border_radius=6)
        surf.blit(bg, (8, 8))
        y = 14
        for f, txt, col in lines:
            surf.blit(f.render(txt, True, col), (14, y))
            y += f.get_height()

    # Interaktionen
    def nearest_food(self, gx, gy):
        return min(self.food,
            key=lambda f: (f.gx - gx) ** 2 + (f.gy - gy) ** 2,
            default=None)

    def eat_food(self, f: Food):
        if f in self.food:
            self.food.remove(f)

    def find_mate(self, p: Paroti) -> Optional[Paroti]:
        c = [q for q in self.parotis
             if q.id != p.id and q.mate_cd == 0
             and q.hunger < 0.45 and q.state == S.MATE]
        return min(c, key=lambda q: (q.gx - p.gx) ** 2 + (q.gy - p.gy) ** 2,
                   default=None)

    def nearest_paroti(self, p: Paroti) -> Optional[Paroti]:
        o = [q for q in self.parotis if q.id != p.id]
        return min(o, key=lambda q: (q.gx - p.gx) ** 2 + (q.gy - p.gy) ** 2,
                   default=None)

    def reproduce(self, a: Paroti, b: Paroti):
        if len(self.parotis) >= MAX_POP:
            return
        child = Paroti(
            (a.gx + b.gx) / 2 + random.uniform(-1.0, 1.0),
            (a.gy + b.gy) / 2 + random.uniform(-1.0, 1.0),
            a.g.crossover(b.g),
            max(a.gen, b.gen) + 1)
        child.parents = [a.id, b.id]
        a.children += 1
        b.children += 1
        self.parotis.append(child)
        self.total_born += 1
        self.max_gen = max(self.max_gen, child.gen)
        self._log(f"Tag {self.day}: Geburt #{child.id} (G{child.gen})")

    def add_food(self, gx: float, gy: float, n: int = 3):
        for _ in range(n):
            self.food.append(Food(
                max(0.5, min(GRID_W - 0.5, gx + random.uniform(-1.0, 1.0))),
                max(0.5, min(GRID_H - 0.5, gy + random.uniform(-1.0, 1.0)))))

    def rain(self, n: int = 22):
        for _ in range(n):
            self.food.append(Food(
                random.uniform(1.0, GRID_W - 1.0),
                random.uniform(1.0, GRID_H - 1.0)))

    def peace(self):
        for p in self.parotis:
            p.happy = min(1.0, p.happy + 0.4)

    def wakeall(self):
        for p in self.parotis:
            if p.state == S.SLEEP:
                p.state  = S.WANDER
                p.energy = 0.6

    def feast(self):
        self.rain(50)
        self.peace()

    def pet_at(self, gx: float, gy: float) -> Optional[Paroti]:
        for p in self.parotis:
            if math.hypot(p.gx - gx, p.gy - gy) < p._sz + 0.8:
                p.petting = 70
                p.happy   = min(1.0, p.happy + 0.22)
                p.trust   = min(1.0, p.trust + 0.06)
                return p
        return None


# ─── Datenbank ────────────────────────────────────────────────────────────────
class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self._init()

    def _init(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS parotis(
                id INT, gx REAL, gy REAL, gen INT, age INT, genome TEXT,
                hunger REAL, energy REAL, happy REAL, trust REAL, piety REAL,
                children INT, parents TEXT, is_historian INT, is_runner INT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, val TEXT);
            CREATE TABLE IF NOT EXISTS chronicle(ts INT, event TEXT);
        """)
        self.conn.commit()

    def save(self, world: World):
        self.conn.execute("DELETE FROM parotis")
        for p in world.parotis:
            self.conn.execute(
                "INSERT INTO parotis VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.id, p.gx, p.gy, p.gen, p.age, json.dumps(asdict(p.g)),
                 p.hunger, p.energy, p.happy, p.trust, p.piety,
                 p.children, json.dumps(p.parents),
                 int(p.is_historian), int(p.is_runner)))
        m = dict(t=world.t, day=world.day, max_gen=world.max_gen,
                 born=world.total_born, died=world.total_died,
                 tilemap=json.dumps(world.tilemap))
        self.conn.execute("DELETE FROM meta")
        for k, v in m.items():
            self.conn.execute("INSERT INTO meta VALUES(?,?)", (k, str(v)))
        for ev in world.chronicle[-10:]:
            self.conn.execute(
                "INSERT INTO chronicle VALUES(?,?)", (world.t, ev))
        world.chronicle.clear()
        self.conn.commit()

    def load(self, world: World) -> bool:
        if self.conn.execute(
                "SELECT COUNT(*) FROM parotis").fetchone()[0] == 0:
            return False
        m = {k: v for k, v in self.conn.execute(
            "SELECT key, val FROM meta").fetchall()}
        world.t          = int(m.get("t", 0))
        world.day        = int(m.get("day", 0))
        world.max_gen    = int(m.get("max_gen", 0))
        world.total_born = int(m.get("born", 0))
        world.total_died = int(m.get("died", 0))
        if "tilemap" in m:
            world.tilemap = json.loads(m["tilemap"])
        # v2→v3 Feld-Migration: alte Gene entfernen, neue ergänzen
        V2_REMOVE = {"body_type", "eye_size", "limbs"}
        V3_FIELDS  = set(Genome.__dataclass_fields__.keys())
        for row in self.conn.execute("SELECT * FROM parotis"):
            (id_, gx, gy, gen, age, g_json, hunger, energy,
             happy, trust, piety, children, par, hist, runner) = row
            raw = json.loads(g_json)
            # Alte Felder entfernen
            for k in list(raw.keys()):
                if k not in V3_FIELDS:
                    del raw[k]
            # Fehlende neue Felder mit Default ergänzen
            defaults = Genome()
            for k in V3_FIELDS:
                if k not in raw:
                    raw[k] = getattr(defaults, k)
            p = Paroti(gx, gy, Genome(**raw), gen, pid=int(id_))
            p.age      = age
            p.hunger   = hunger
            p.energy   = energy
            p.happy    = happy
            p.trust    = trust
            p.piety    = piety
            p.children = children
            p.parents  = json.loads(par)
            p.is_historian = bool(hist)
            p.is_runner    = bool(runner)
            world.parotis.append(p)
        Paroti._nxt_id = max((p.id for p in world.parotis), default=0) + 1
        rows = self.conn.execute(
            "SELECT event FROM chronicle ORDER BY ts DESC LIMIT 40"
        ).fetchall()
        world.chronicle = [r[0] for r in reversed(rows)]
        return True

    def close(self):
        self.conn.close()


# ─── Game ─────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        self.mouse_mode = "--mouse" in sys.argv or "-m" in sys.argv
        pygame.mouse.set_visible(self.mouse_mode)

        info        = pygame.display.Info()
        self.W, self.H = info.current_w, info.current_h
        try:
            self.screen = pygame.display.set_mode(
                (self.W, self.H), pygame.FULLSCREEN | pygame.NOFRAME)
        except Exception:
            self.W, self.H = 1280, 720
            self.screen = pygame.display.set_mode((self.W, self.H))
            self.mouse_mode = True
            pygame.mouse.set_visible(True)
        pygame.display.set_caption("Parotis")
        self.clock = pygame.time.Clock()

        # Iso-Parameter
        global TILE_W, TILE_H, ISO_OX, ISO_OY
        TILE_W = max(40, min(72, self.W // (GRID_W + GRID_H) * 2))
        TILE_H = TILE_W // 2
        ISO_OX = self.W // 2
        ISO_OY = TILE_H * 3

        # Fonts
        self.fs = pygame.font.Font(None, 22)
        self.fm = pygame.font.Font(None, 30)
        self.fl = pygame.font.Font(None, 52)
        self.fg = pygame.font.Font(None, 20)

        # Welt
        self.world = World()
        self.world.setup_shrine()
        self.world.setup_mailbox(self.W, self.H)

        self.db = DB(DB_PATH)
        if not self.db.load(self.world):
            self.world.spawn_initial()
            print("🌱 Neue Welt erschaffen")
        else:
            print(f"🔄 Geladen: {len(self.world.parotis)} Parotis, "
                  f"Tag {self.world.day}")

        print("🗺  Kacheln werden gerendert ...")
        self.floor = render_floor(self.W, self.H, self.world.tilemap)
        print("✅ Kacheln fertig")

        self.menu       = TouchMenu(self.W, self.H)
        self.running    = True
        self.last_save  = time.time()
        self.selected   : Optional[Paroti] = None
        self.show_chron = False
        self.particles  : List[dict] = []
        self.press_pos  : Optional[Tuple] = None

        print(f"📬 Postfach: {INBOX_DIR}")
        print(f"🙏 Gott-Bild: {GOD_IMAGE_PATH or 'prozedurales Auge'}")

    def events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                self.press_pos = (*ev.pos, time.time())
                self._on_touch(*ev.pos)
            elif ev.type == pygame.MOUSEBUTTONUP:
                if self.press_pos:
                    if time.time() - self.press_pos[2] > 0.7:
                        self._long_press(*ev.pos)
                    self.press_pos = None
            elif ev.type == pygame.FINGERDOWN:
                tx, ty = int(ev.x * self.W), int(ev.y * self.H)
                self.press_pos = (tx, ty, time.time())
                self._on_touch(tx, ty)
            elif ev.type == pygame.FINGERUP:
                if self.press_pos:
                    if time.time() - self.press_pos[2] > 0.7:
                        self._long_press(
                            int(ev.x * self.W), int(ev.y * self.H))
                    self.press_pos = None

    def _on_touch(self, x: int, y: int):
        if self.menu.confirm_quit:
            yr, nr = self.menu.confirm_rects()
            if yr.collidepoint(x, y):
                self.running = False
                return
            if nr.collidepoint(x, y):
                self.menu.confirm_quit = False
                return
            return
        if self.menu.hit_toggle(x, y):
            self.menu.toggle()
            return
        if self.menu.open:
            a = self.menu.hit_item(x, y)
            if a:
                self._run_action(a)
                if a != "quit":
                    self.menu.open = False
            else:
                self.menu.open = False
            return
        self._particle(x, y)
        gx, gy = screen_to_grid(x, y)
        petted = self.world.pet_at(gx, gy)
        if petted:
            self.selected = petted
        else:
            self.world.add_food(gx, gy)
            self.selected = None

    def _long_press(self, x: int, y: int):
        self.world.rain()
        self._particle(x, y, rain=True)

    def _run_action(self, action: str):
        if   action == "rain":      self.world.rain()
        elif action == "feast":     self.world.feast()
        elif action == "peace":     self.world.peace()
        elif action == "newlife":   self.world.spawn_one()
        elif action == "chronicle": self.show_chron = not self.show_chron
        elif action == "wakeall":   self.world.wakeall()
        elif action == "quit":      self.menu.confirm_quit = True

    def _particle(self, x: int, y: int, rain: bool = False):
        self.particles.append(
            dict(x=x, y=y, life=40, maxl=40, rain=rain))

    def update(self):
        self.world.update()
        self.menu.update()
        if time.time() - self.last_save > SAVE_EVERY:
            self.db.save(self.world)
            self.last_save = time.time()
        self.particles = [p for p in self.particles if p["life"] > 0]
        for p in self.particles:
            p["life"] -= 1

    def draw(self):
        self.world.draw(
            self.screen, self.floor, self.fs, self.fm, self.fg)
        for p in self.particles:
            prog  = 1 - p["life"] / p["maxl"]
            r     = int(35 * prog)
            alpha = int(220 * (1 - prog))
            if r > 0:
                col = (100, 200, 255, alpha) if p["rain"] \
                      else (255, 240, 140, alpha)
                s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, col, (r + 1, r + 1), r)
                self.screen.blit(s, (p["x"] - r - 1, p["y"] - r - 1))
        if self.selected and self.selected.alive:
            self._draw_panel()
        if self.show_chron:
            self._draw_chronicle()
        self.menu.draw(self.screen, self.fs, self.fl)
        pygame.display.flip()

    def _draw_panel(self):
        p = self.selected
        pw, ph = 242, 212
        px, py = self.W - pw - 12, 12
        s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        s.fill((0, 0, 0, 170))
        pygame.draw.rect(s, (*p.g.shirt(), 100),
            (0, 0, pw, ph), 2, border_radius=8)
        self.screen.blit(s, (px, py))
        bw = pw - 46

        def bar(label, val, col, yo):
            self.screen.blit(
                self.fs.render(label, True, C_HUD_DIM), (px + 8, py + yo))
            pygame.draw.rect(self.screen, (40, 40, 40),
                (px + 84, py + yo + 2, bw, 10), border_radius=4)
            pygame.draw.rect(self.screen, col,
                (px + 84, py + yo + 2, max(0, int(bw * val)), 10),
                border_radius=4)

        self.screen.blit(
            self.fm.render(f"Paroti #{p.id}", True, p.g.shirt()),
            (px + 8, py + 8))
        self.screen.blit(
            self.fs.render(f"G{p.gen} · Alter {p.age // 60}s", True, C_HUD),
            (px + 8, py + 32))
        bar("Hunger",   p.hunger, (220, 80, 60),   55)
        bar("Energie",  p.energy, (80, 200, 120),   75)
        bar("Glück",    p.happy,  (220, 200, 60),   95)
        bar("Vertrau.", p.trust,  (100, 160, 255), 115)
        bar("Frömmig.", p.piety,  (255, 230, 80),  135)
        self.screen.blit(
            self.fs.render(f"Status: {p.status_text()}", True, C_HUD_DIM),
            (px + 8, py + 163))
        self.screen.blit(
            self.fs.render(f"Kinder: {p.children}", True, C_HUD_DIM),
            (px + 8, py + 181))

    def _draw_chronicle(self):
        lines = self.world.chronicle[-22:]
        w = min(500, self.W - 20)
        h = len(lines) * 18 + 20
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 182))
        self.screen.blit(s, (10, self.H - h - 32))
        for i, line in enumerate(lines):
            col = (180, 200, 160) if i == len(lines) - 1 else (110, 140, 110)
            self.screen.blit(
                self.fs.render(line, True, col),
                (18, self.H - h - 32 + 10 + i * 18))

    def run(self):
        print(f"🎮 Parotis v3 Iso-Modus  "
              f"{self.W}x{self.H}  TILE {TILE_W}x{TILE_H}")
        print(f"   Maus-Modus: {self.mouse_mode}")
        try:
            while self.running:
                self.events()
                self.update()
                self.draw()
                self.clock.tick(FPS)
        except Exception:
            import traceback
            print("Game-Loop Fehler:")
            print(traceback.format_exc())
        finally:
            print("💾 Speichert ...")
            self.db.save(self.world)
            self.db.close()
            pygame.quit()
            print(f"👋 {self.world.total_born} Parotis lebten, "
                  f"G{self.world.max_gen}")
            sys.exit(0)


if __name__ == "__main__":
    if ("DISPLAY" not in os.environ
            and "WAYLAND_DISPLAY" not in os.environ):
        os.environ.setdefault("SDL_VIDEODRIVER", "fbdev")
        os.environ.setdefault("SDL_FBDEV", "/dev/fb0")
    Game().run()
