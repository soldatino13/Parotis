#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   P A R O T I S  v2  –  Die lebende Welt            ║
║   Black Mirror S07E04 inspiriert                    ║
║                                                      ║
║   Postfach: ~/parotis-inbox/  (txt-Befehle)         ║
║   Gott-Bild: ~/parotis-inbox/god.jpg (oder .png)   ║
╚══════════════════════════════════════════════════════╝
"""

import pygame
import sqlite3
import math
import random
import time
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict
from pathlib import Path
import threading

# ─── Pfade ────────────────────────────────────────────────────────────────────
HOME        = Path.home()
DATA_DIR    = HOME / ".parotis"
DB_PATH     = DATA_DIR / "world.db"
INBOX_DIR   = HOME / "parotis-inbox"
GOD_IMAGE   = None   # Wird in Game.__init__ gesucht

for ext in ("jpg","jpeg","png","bmp","webp"):
    p = INBOX_DIR / f"god.{ext}"
    if p.exists():
        GOD_IMAGE = str(p)
        break

# ─── Konstanten ──────────────────────────────────────────────────────────────
FPS          = 60
SAVE_EVERY   = 30
MAX_POP      = 80
INIT_POP     = 18
MAX_FOOD     = 60
FOOD_RATE    = 0.018
LIFESPAN     = 60 * 60 * 7

# Farben
C_BG         = (12, 28, 14)
C_GRID       = (20, 42, 20)
C_FOOD       = (70, 210, 80)
C_FOOD_GLOW  = (40, 120, 40)
C_WHITE      = (255, 255, 255)
C_HUD        = (160, 210, 160)
C_HUD_DIM    = (90, 130, 90)
C_MENU_BG    = (10, 20, 10, 220)
C_MENU_BTN   = (30, 60, 30)
C_MENU_HOV   = (50, 100, 50)
C_MAIL_GLOW  = (255, 220, 80)
C_SHRINE     = (255, 240, 180)

# Postfach-Befehle
CMD_MAP = {
    "REGEN":       "rain",
    "FRIEDEN":     "peace",
    "FUTTER":      "food",
    "NEU":         "newlife",
    "ALLE_WECKEN": "wakeall",
    "NACHRICHT":   "message",
    "FEST":        "feast",
    "BESTRAFT":    "punish",
}

# Proto-Sprachen-Glyphen (einfache Pixel-Symbole per Unicode)
GLYPHS = ["◆","○","✦","◇","★","△","▽","⬡","⬟","◈"]

# ─── Genom ────────────────────────────────────────────────────────────────────
@dataclass
class Genome:
    col_r:      float = 0.5
    col_g:      float = 0.5
    col_b:      float = 0.5
    body_type:  float = 0.5
    size:       float = 0.5
    eye_size:   float = 0.5
    limbs:      float = 0.5
    speed:      float = 0.5
    social:     float = 0.5
    intellect:  float = 0.5
    hunger_r:   float = 0.5
    courage:    float = 0.5
    repro:      float = 0.5
    piety:      float = 0.5   # NEU: Religiösität / Reaktion auf Schrein
    mut_rate:   float = 0.05

    def color(self):
        return (int(40+self.col_r*215), int(40+self.col_g*215), int(40+self.col_b*215))
    def accent(self):
        r,g,b=self.color(); return (min(255,r+70),min(255,g+70),min(255,b+70))
    def dark(self):
        r,g,b=self.color(); return (max(0,r-50),max(0,g-50),max(0,b-50))
    def body_v(self):    return int(self.body_type*4.99)
    def n_limbs(self):   return 4 if self.limbs>0.5 else 2
    def px_size(self):   return 10+self.size*22
    def px_speed(self):  return 0.6+self.speed*2.8
    def hunger_rate(self): return 0.0008+self.hunger_r*0.0025

    def crossover(self, other:'Genome') -> 'Genome':
        genes={}
        for name in self.__dataclass_fields__:
            val = getattr(self,name) if random.random()<0.5 else getattr(other,name)
            if name!='mut_rate':
                val = max(0.0,min(1.0,val+random.gauss(0,self.mut_rate)))
            genes[name]=val
        return Genome(**genes)

    @classmethod
    def rand(cls):
        return cls(**{n:random.random() if n!='mut_rate'
                      else random.uniform(0.01,0.08)
                      for n in cls.__dataclass_fields__})


# ─── Zustände ─────────────────────────────────────────────────────────────────
class S:
    WANDER   = "wander"
    FOOD     = "food"
    MATE     = "mate"
    SLEEP    = "sleep"
    SOCIAL   = "social"
    WORSHIP  = "worship"   # NEU: zum Schrein
    FLEE_GOD = "flee_god"  # NEU: flieht vor Schrein
    CURIOUS  = "curious"   # NEU: untersucht Schrein
    MAILRUN  = "mailrun"   # NEU: läuft zum Postfach


# ─── Proto-Sprach-Blase ───────────────────────────────────────────────────────
class GlyphBubble:
    def __init__(self, x, y, col):
        self.x, self.y = x, y
        self.glyph = random.choice(GLYPHS)
        self.col   = col
        self.life  = random.randint(55, 90)
        self.maxl  = self.life
        self.oy    = 0.0

    def update(self):
        self.life -= 1
        self.oy   -= 0.5

    def draw(self, surf, font):
        if self.life <= 0: return
        alpha = int(255 * (self.life / self.maxl))
        label = font.render(self.glyph, True, (*self.col, 255))
        label.set_alpha(alpha)
        surf.blit(label, (int(self.x)-8, int(self.y+self.oy)-8))


# ─── Paroti ───────────────────────────────────────────────────────────────────
class Paroti:
    _nxt_id = 1

    def __init__(self, x, y, genome:Genome=None, generation:int=0, pid:int=None):
        self.id   = pid or Paroti._nxt_id; Paroti._nxt_id += 1
        self.x, self.y = float(x), float(y)
        self.g    = genome or Genome.rand()
        self.gen  = generation

        self.hunger  = random.uniform(0.2, 0.45)
        self.energy  = random.uniform(0.6, 1.0)
        self.happy   = random.uniform(0.4, 0.8)
        self.trust   = 0.3 + random.random()*0.2
        self.piety   = 0.0   # akkumuliert durch Schrein-Besuche
        self.age     = 0
        self.alive   = True
        self.state   = S.WANDER
        self.petting = 0
        self.mate_cd = 0
        self.children= 0
        self.parents : List[int] = []
        self.is_historian = False   # ältester Paroti
        self.is_runner    = False   # Postfach-Läufer

        a = random.uniform(0, math.tau)
        self.vx = math.cos(a); self.vy = math.sin(a)
        self.t  = random.randint(0, 100)

        self._col  = self.g.color()
        self._acc  = self.g.accent()
        self._dark = self.g.dark()
        self._sz   = self.g.px_size()
        self._spd  = self.g.px_speed()

        self.bubbles: List[GlyphBubble] = []
        self.dream_t = 0

        # Schrein-Reaktions-Timer
        self._shrine_cd = 0

    def update(self, world:'World'):
        if not self.alive: return
        self.age += 1
        self.t   += 1
        self.hunger = min(1.0, self.hunger + self.g.hunger_rate())

        if self.state == S.SLEEP:
            self.energy = min(1.0, self.energy + 0.004)
            self.dream_t += 1
        else:
            self.energy = max(0.0, self.energy - 0.0004)
            self.dream_t = 0

        if self.petting > 0:
            self.petting -= 1
            self.happy = min(1.0, self.happy + 0.003)

        if self.hunger >= 1.0 or self.age > LIFESPAN:
            self.alive = False; return

        if self.mate_cd > 0: self.mate_cd -= 1
        if self._shrine_cd > 0: self._shrine_cd -= 1

        # Glyph-Blasen
        for b in self.bubbles: b.update()
        self.bubbles = [b for b in self.bubbles if b.life > 0]
        if self.state == S.SOCIAL and random.random() < 0.02:
            self.bubbles.append(GlyphBubble(self.x, self.y - self._sz, self._col))

        self._decide(world)
        self._act(world)

        # Wand-Bounce
        if self.x < self._sz:           self.x=self._sz;           self.vx=abs(self.vx)
        if self.x > world.w-self._sz:   self.x=world.w-self._sz;   self.vx=-abs(self.vx)
        if self.y < self._sz:           self.y=self._sz;            self.vy=abs(self.vy)
        if self.y > world.h-self._sz:   self.y=world.h-self._sz;   self.vy=-abs(self.vy)

        self.happy = max(0, min(1, self.happy - 0.0001))

    def _decide(self, world:'World'):
        # Postfach-Läufer hat Vorrang
        if self.is_runner and world.mailbox.has_pending():
            self.state = S.MAILRUN; return

        if self.hunger > 0.72:
            self.state = S.FOOD; return
        if self.energy < 0.18:
            self.state = S.SLEEP; return
        if self.state == S.SLEEP and self.energy > 0.85:
            self.state = S.WANDER

        # Schrein-Reaktion (einmal pro Paroti, nicht zu oft)
        if (self._shrine_cd == 0 and world.shrine and
                self.hunger < 0.6 and self.state not in (S.FOOD, S.SLEEP)):
            sx, sy = world.shrine.x, world.shrine.y
            dist = math.hypot(self.x-sx, self.y-sy)
            if dist < 350 and random.random() < 0.003:
                if self.g.piety > 0.6:
                    self.state = S.WORSHIP
                elif self.g.courage < 0.35:
                    self.state = S.FLEE_GOD
                else:
                    self.state = S.CURIOUS
                self._shrine_cd = 60*8
                return

        if self.hunger > 0.42:
            self.state = S.FOOD; return
        if (self.hunger < 0.28 and self.energy > 0.5
                and self.mate_cd == 0 and self.g.repro > 0.25
                and len(world.parotis) < MAX_POP):
            self.state = S.MATE; return
        if self.state not in (S.SLEEP,S.FOOD,S.MATE,S.SOCIAL,S.WORSHIP,S.FLEE_GOD,S.CURIOUS):
            if self.g.social > 0.55 and random.random() < 0.001:
                self.state = S.SOCIAL
            elif self.state not in (S.WANDER,):
                self.state = S.WANDER

    def _act(self, world:'World'):
        if self.state == S.WANDER:
            self._wander()
        elif self.state == S.FOOD:
            f = world.nearest_food(self.x, self.y)
            if f:
                self._toward(f.x, f.y)
                if self._dist(f.x,f.y) < self._sz+8:
                    world.eat_food(f)
                    self.hunger = max(0, self.hunger-0.42)
                    self.happy  = min(1, self.happy+0.12)
                    self.state  = S.WANDER
            else: self._wander()
        elif self.state == S.MATE:
            mate = world.find_mate(self)
            if mate:
                self._toward(mate.x, mate.y)
                if self._dist(mate.x,mate.y) < self._sz+mate._sz+4:
                    world.reproduce(self, mate)
                    self.mate_cd=60*12; mate.mate_cd=60*12
                    self.state=S.WANDER
            else: self.state=S.WANDER
        elif self.state == S.SOCIAL:
            nb = world.nearest_paroti(self)
            if nb:
                if self._dist(nb.x,nb.y) > self._sz*3.5:
                    self._toward(nb.x,nb.y)
                else:
                    self.happy=min(1,self.happy+0.06)
                    self.state=S.WANDER
            else: self.state=S.WANDER
        elif self.state == S.SLEEP:
            self.vx*=0.88; self.vy*=0.88
            self.x+=self.vx; self.y+=self.vy
        elif self.state == S.WORSHIP and world.shrine:
            sx,sy = world.shrine.worship_spot(self.id)
            self._toward(sx, sy)
            if self._dist(sx,sy) < 20:
                self.vx*=0.1; self.vy*=0.1
                self.piety=min(1, self.piety+0.002)
                self.happy=min(1, self.happy+0.001)
                if random.random()<0.015:
                    self.bubbles.append(GlyphBubble(self.x, self.y-self._sz,
                                                    (255,230,100)))
        elif self.state == S.FLEE_GOD and world.shrine:
            sx,sy = world.shrine.x, world.shrine.y
            dx,dy = self.x-sx, self.y-sy
            d = math.hypot(dx,dy)
            if d < 250:
                self._move_dir(dx/max(d,1), dy/max(d,1))
            else:
                self.state = S.WANDER
        elif self.state == S.CURIOUS and world.shrine:
            sx,sy = world.shrine.x, world.shrine.y
            if self._dist(sx,sy) > self._sz*3:
                self._toward(sx, sy)
            else:
                if random.random()<0.008:
                    self.bubbles.append(GlyphBubble(self.x, self.y-self._sz,
                                                    (200,200,255)))
                if random.random()<0.005:
                    self.state=S.WANDER
        elif self.state == S.MAILRUN and world.mailbox:
            mx,my = world.mailbox.screen_x, world.mailbox.screen_y
            self._toward(mx, my)
            if self._dist(mx,my) < self._sz+22:
                world.mailbox.execute(world)
                self.happy=min(1,self.happy+0.3)
                self.bubbles.append(GlyphBubble(self.x, self.y-self._sz-10,
                                                (255,255,100)))
                self.state=S.WANDER

    def _wander(self):
        if random.random()<0.018:
            a=random.uniform(0,math.tau)
            self.vx=math.cos(a)*self._spd; self.vy=math.sin(a)*self._spd
        self.x+=self.vx; self.y+=self.vy

    def _toward(self, tx, ty):
        dx,dy=tx-self.x, ty-self.y
        d=math.hypot(dx,dy)
        if d>0.5:
            s=self._spd*(0.75+self.g.intellect*0.5)
            self.vx=dx/d*s; self.vy=dy/d*s
            self.x+=self.vx; self.y+=self.vy

    def _move_dir(self, dx, dy):
        self.vx=dx*self._spd; self.vy=dy*self._spd
        self.x+=self.vx; self.y+=self.vy

    def _dist(self, tx, ty): return math.hypot(tx-self.x, ty-self.y)

    # ── Zeichnen ──────────────────────────────────────────────────────────────
    def draw(self, surf:pygame.Surface, font_glyph):
        if not self.alive: return

        # Glyph-Blasen (hinter allem)
        for b in self.bubbles: b.draw(surf, font_glyph)

        sx, sy = int(self.x), int(self.y)
        sz     = int(self._sz)
        t      = self.t

        if self.state == S.SLEEP:
            self._draw_sleep(surf, sx, sy, sz); return

        bob = int(math.sin(t*0.14)*2.5)
        sy_b = sy+bob

        # Worship-Aura
        if self.state == S.WORSHIP:
            aura_r = sz+6+int(math.sin(t*0.1)*3)
            a_surf = pygame.Surface((aura_r*3,aura_r*3), pygame.SRCALPHA)
            pygame.draw.circle(a_surf,(255,230,80,55),(aura_r,aura_r+bob),aura_r)
            surf.blit(a_surf,(sx-aura_r,sy_b-aura_r))

        # Postfach-Runner Markierung
        if self.is_runner:
            pygame.draw.circle(surf,(255,220,60),(sx,sy_b-sz-7),4)

        # Historiker-Markierung
        if self.is_historian:
            pygame.draw.line(surf,(200,200,200),(sx,sy_b-sz-5),(sx,sy_b-sz-14),2)
            pygame.draw.circle(surf,(200,200,200),(sx,sy_b-sz-14),3)

        self._draw_limbs(surf,sx,sy_b,sz,t)
        self._draw_body(surf,sx,sy_b,sz)
        self._draw_face(surf,sx,sy_b,sz)

        if self.petting > 0:
            alpha=int(180*self.petting/60)
            acc=self._acc
            gs=pygame.Surface((sz*5,sz*5),pygame.SRCALPHA)
            pygame.draw.circle(gs,(*acc,alpha),(sz*2+sz//2,sz*2+sz//2),sz*2)
            surf.blit(gs,(sx-sz*2-sz//2,sy_b-sz*2-sz//2))

        if self.gen >= 3:
            lbl=pygame.font.Font(None,15).render(f"G{self.gen}",True,(180,180,180))
            surf.blit(lbl,(sx-sz,sy_b-sz-13))

    def _draw_body(self, surf, sx, sy, sz):
        col,acc = self._col, self._acc
        bv = self.g.body_v()
        if bv==0:
            pygame.draw.ellipse(surf,col,(sx-sz,sy-sz,sz*2,sz*2))
            pygame.draw.ellipse(surf,acc,(sx-sz+3,sy-sz+3,sz*2-6,sz*2-6),2)
        elif bv==1:
            pygame.draw.ellipse(surf,col,(sx-sz+sz//3,sy-int(sz*1.35),sz*2-sz//3*2,int(sz*2.7)))
        elif bv==2:
            pygame.draw.ellipse(surf,col,(sx-int(sz*1.35),sy-sz//2,int(sz*2.7),sz))
            pygame.draw.ellipse(surf,acc,(sx-int(sz*1.35)+2,sy-sz//2+2,int(sz*2.7)-4,sz-4),2)
        elif bv==3:
            pts=[(sx,sy-sz),(sx+sz,sy),(sx,sy+sz),(sx-sz,sy)]
            pygame.draw.polygon(surf,col,pts)
            pygame.draw.polygon(surf,acc,pts,2)
        else:
            pts=[(int(sx+sz*math.cos(math.pi/3*i)),int(sy+sz*math.sin(math.pi/3*i)))
                 for i in range(6)]
            pygame.draw.polygon(surf,col,pts)
            pygame.draw.polygon(surf,acc,pts,2)

    def _draw_face(self, surf, sx, sy, sz):
        es = max(2, int(2+self.g.eye_size*5))
        ex = sx+(sz//3 if self.vx>=0 else -sz//3)
        ey = sy-sz//3
        for dx in (-es, es):
            pygame.draw.circle(surf,C_WHITE,(ex+dx,ey),es)
            pd=1 if self.vx>=0 else -1
            pygame.draw.circle(surf,(15,15,15),(ex+dx+pd,ey),max(1,es-2))
        my=ey+es+2
        if self.happy>0.6:
            pygame.draw.arc(surf,(30,30,30),(ex-es,my,es*2,es),math.pi,2*math.pi,2)
        elif self.happy<0.3:
            pygame.draw.arc(surf,(30,30,30),(ex-es,my-es,es*2,es),0,math.pi,2)

    def _draw_limbs(self, surf, sx, sy, sz, t):
        n=self.g.n_limbs(); lc=self._dark; ll=sz*0.65
        for i in range(n):
            ba=math.pi+(math.pi/max(1,n-1))*i
            wag=math.sin(t*0.18+i*math.pi)*5
            ex=int(sx+math.cos(ba)*ll); ey=int(sy+math.sin(ba)*ll+wag)
            pygame.draw.line(surf,lc,(sx,sy),(ex,ey),2)
            pygame.draw.circle(surf,lc,(ex,ey),3)

    def _draw_sleep(self, surf, sx, sy, sz):
        pygame.draw.ellipse(surf,self._col,(sx-int(sz*.9),sy-int(sz*.5),int(sz*1.8),int(sz)))
        # Traum-Shimmer
        if self.dream_t > 30:
            dr = int(sz*1.6)+int(math.sin(self.dream_t*0.08)*4)
            ds = pygame.Surface((dr*3,dr*3),pygame.SRCALPHA)
            pygame.draw.circle(ds,(160,140,255,22),(dr,dr),dr)
            surf.blit(ds,(sx-dr,sy-dr))
        f=pygame.font.Font(None,18)
        for i,c in enumerate("ZZZ"):
            z=f.render(c,True,(180,180,255)); z.set_alpha(160-i*40)
            surf.blit(z,(sx+sz+i*7,sy-sz-i*7))

    def status_text(self):
        return {S.WANDER:"wandert",S.FOOD:"sucht Futter",S.MATE:"sucht Partner",
                S.SLEEP:"schläft",S.SOCIAL:"sozialisiert",
                S.WORSHIP:"betet an",S.FLEE_GOD:"flieht (Gott!)",
                S.CURIOUS:"neugierig",S.MAILRUN:"holt Post"}.get(self.state,self.state)


# ─── Futter ───────────────────────────────────────────────────────────────────
class Food:
    __slots__=('x','y','sz','age')
    def __init__(self,x,y):
        self.x,self.y=float(x),float(y); self.sz=random.uniform(4,9); self.age=0
    def update(self): self.age+=1
    def draw(self,surf):
        pulse=math.sin(self.age*0.06)*1.5; r=int(self.sz+pulse)
        gs=pygame.Surface((r*5,r*5),pygame.SRCALPHA)
        pygame.draw.circle(gs,(*C_FOOD_GLOW,45),(r*2+r,r*2+r),r*2)
        surf.blit(gs,(int(self.x)-r*2-r,int(self.y)-r*2-r))
        pygame.draw.circle(surf,C_FOOD,(int(self.x),int(self.y)),r)
        pygame.draw.circle(surf,(130,255,130),(int(self.x),int(self.y)),max(1,r-2))


# ─── Schrein (Gott-Bild) ──────────────────────────────────────────────────────
class Shrine:
    def __init__(self, x:float, y:float, image_path:Optional[str]):
        self.x, self.y  = x, y
        self.t          = 0
        self.visitors   = 0
        self.surf       = self._load(image_path)

    def _load(self, path:Optional[str]) -> pygame.Surface:
        if path:
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img,(96,96))
                return img
            except Exception:
                pass
        # Prozedurale Gottheit — strahlendes Auge
        s = pygame.Surface((96,96),pygame.SRCALPHA)
        for r2 in range(48,0,-6):
            a = int(40*(r2/48))
            pygame.draw.circle(s,(255,240,180,a),(48,48),r2)
        pygame.draw.circle(s,(255,255,220),  (48,48),22)
        pygame.draw.circle(s,(30,20,0),      (48,48),12)
        pygame.draw.circle(s,(255,220,120),  (48,48),5)
        return s

    def worship_spot(self, pid:int) -> Tuple[float,float]:
        """Gibt einen Platz im Kreis ums Schrein zurück (je Paroti eigener Winkel)"""
        a = (pid * 2.39996) % math.tau  # goldener Winkel
        r = 70
        return (self.x + math.cos(a)*r, self.y + math.sin(a)*r)

    def update(self):
        self.t += 1

    def draw(self, surf:pygame.Surface, font_s):
        glow_r = 55+int(math.sin(self.t*0.04)*8)
        gs = pygame.Surface((glow_r*3,glow_r*3),pygame.SRCALPHA)
        pygame.draw.circle(gs,(255,240,140,30),(glow_r,glow_r),glow_r)
        surf.blit(gs,(int(self.x)-glow_r,int(self.y)-glow_r))
        # Schrein-Basis (Sockel)
        pygame.draw.rect(surf,(60,50,30),
            (int(self.x)-52, int(self.y)+40, 104, 14), border_radius=4)
        pygame.draw.rect(surf,(90,80,50),
            (int(self.x)-50, int(self.y)+38, 100, 12), border_radius=4)
        # Bild
        surf.blit(self.surf,(int(self.x)-48,int(self.y)-48))
        # Rahmen
        pygame.draw.rect(surf,C_SHRINE,(int(self.x)-49,int(self.y)-49,98,98),2,border_radius=4)
        # Besucher-Label
        if self.visitors > 0:
            lbl = font_s.render(f"🙏 {self.visitors}",True,(255,220,80))
            surf.blit(lbl,(int(self.x)-20,int(self.y)+56))


# ─── Postfach ─────────────────────────────────────────────────────────────────
class Mailbox:
    def __init__(self, inbox_dir:Path, screen_x:int, screen_y:int):
        self.dir       = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.screen_x  = screen_x
        self.screen_y  = screen_y
        self._pending  : Optional[Path] = None
        self.t         = 0
        self.msg       = ""          # Aktive Nachricht für HUD
        self.msg_timer = 0
        self._last_scan= 0

    def has_pending(self) -> bool:
        now = time.time()
        if now - self._last_scan > 2:   # alle 2s scannen
            self._last_scan = now
            self._scan()
        return self._pending is not None

    def _scan(self):
        if self._pending: return
        for f in sorted(self.dir.glob("*.txt")):
            self._pending = f; return

    def execute(self, world:'World'):
        if not self._pending: return
        p = self._pending
        try:
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split(maxsplit=1)
                cmd   = parts[0].upper()
                arg   = parts[1] if len(parts)>1 else ""
                self._run(cmd, arg, world)
            # Als gelesen markieren
            read_dir = self.dir/"gelesen"
            read_dir.mkdir(exist_ok=True)
            dest = read_dir / (p.stem + f"_{int(time.time())}.read")
            p.rename(dest)
        except Exception as e:
            print(f"Postfach-Fehler: {e}")
        finally:
            self._pending = None

    def _run(self, cmd:str, arg:str, world:'World'):
        print(f"📬 Befehl: {cmd} {arg}")
        if cmd == "REGEN":
            world.rain(30)
            self._show("🌧 Regen auf Befehl!")
        elif cmd == "FEST":
            world.rain(50)
            for p in world.parotis: p.happy = min(1, p.happy+0.5)
            self._show("🎉 Grosses Fest! Alle jubeln!")
        elif cmd == "FRIEDEN":
            for p in world.parotis: p.happy = min(1, p.happy+0.4)
            self._show("☮ Friede sei mit allen Parotis")
        elif cmd == "NEU":
            n = max(1,min(10,int(arg) if arg.isdigit() else 3))
            for _ in range(n): world.spawn_one()
            self._show(f"👶 {n} neue Parotis erschaffen!")
        elif cmd == "ALLE_WECKEN":
            for p in world.parotis:
                if p.state==S.SLEEP: p.state=S.WANDER; p.energy=0.6
            self._show("⚡ Alle geweckt!")
        elif cmd == "NACHRICHT":
            self._show(f"📜 {arg}")
        elif cmd == "BESTRAFT":
            victims = random.sample(world.parotis, min(3,len(world.parotis)))
            for v in victims: v.hunger=0.95
            self._show("⚡ Gott ist zornig! Hunger kommt!")
        elif cmd == "TIPP":
            self._show(f"💡 Tipp: {arg}")
        elif cmd == "HILFE":
            self._show(f"ℹ {arg}")
        else:
            self._show(f"❓ Unbekannter Befehl: {cmd}")

    def _show(self, msg:str):
        self.msg       = msg
        self.msg_timer = 60 * 12   # 12 Sekunden

    def update(self):
        self.t += 1
        if self.msg_timer > 0: self.msg_timer -= 1

    def draw(self, surf:pygame.Surface, font_s, font_m):
        # Postfach-Icon unten rechts
        px, py = self.screen_x, self.screen_y
        glow = self.has_pending()
        if glow:
            pulse = int(30+math.sin(self.t*0.15)*20)
            gs = pygame.Surface((80,80),pygame.SRCALPHA)
            pygame.draw.circle(gs,(*C_MAIL_GLOW,pulse),(40,40),38)
            surf.blit(gs,(px-40,py-40))
        col = C_MAIL_GLOW if glow else (80,100,80)
        pygame.draw.rect(surf,col,(px-28,py-16,56,32),border_radius=5)
        pygame.draw.polygon(surf,col,[(px-28,py-16),(px,py+2),(px+28,py-16)])
        pygame.draw.rect(surf,(0,0,0),(px-28,py-16,56,32),2,border_radius=5)
        lbl=font_s.render("POST",True,(0,0,0))
        surf.blit(lbl,(px-18,py-8))
        if glow:
            nl=font_s.render("NEU!",True,(255,50,50))
            surf.blit(nl,(px-14,py+18))

        # Aktive Nachricht
        if self.msg_timer > 0:
            alpha=min(255,self.msg_timer*6)
            tw = font_m.size(self.msg)[0]+24
            ts = pygame.Surface((tw,44),pygame.SRCALPHA)
            ts.fill((0,0,0,180))
            surf.blit(ts,(surf.get_width()//2-tw//2, py-90))
            ml=font_m.render(self.msg,True,(255,240,150))
            ml.set_alpha(alpha)
            surf.blit(ml,(surf.get_width()//2-ml.get_width()//2, py-84))


# ─── Touch-Menü ───────────────────────────────────────────────────────────────
class TouchMenu:
    ITEMS = [
        ("🌧",  "Regen",       "rain"),
        ("🍎",  "Grosses Fest","feast"),
        ("☮",   "Frieden",     "peace"),
        ("👶",  "Neues Leben", "newlife"),
        ("📜",  "Chronik",     "chronicle"),
        ("⚡",  "Alle wecken", "wakeall"),
        ("🔌",  "Ausschalten", "quit"),
    ]

    def __init__(self, screen_w, screen_h):
        self.W, self.H = screen_w, screen_h
        self.open      = False
        self.confirm_quit = False
        self.btn_size  = 72
        self.pad       = 10
        self.toggle_r  = 34

        # Toggle-Button: unten links
        self.tx = 56
        self.ty = screen_h - 56

        # Items-Positionen (aufklappend nach oben-rechts)
        self._items_rect: List[pygame.Rect] = []
        self._build_rects()

        self.anim  = 0.0   # 0..1 für Aufklapp-Animation
        self._t    = 0

    def _build_rects(self):
        self._items_rect.clear()
        cols = 3
        x0   = self.tx + self.toggle_r + 12
        y0   = self.ty
        for i, _ in enumerate(self.ITEMS):
            col = i % cols
            row = i // cols
            rx  = x0 + col*(self.btn_size+self.pad)
            ry  = y0 - row*(self.btn_size+self.pad) - self.btn_size
            self._items_rect.append(pygame.Rect(rx, ry, self.btn_size, self.btn_size))

    def update(self):
        self._t += 1
        if self.open:
            self.anim = min(1.0, self.anim+0.12)
        else:
            self.anim = max(0.0, self.anim-0.18)

    def toggle(self):
        self.open = not self.open
        self.confirm_quit = False

    def hit_toggle(self, x, y) -> bool:
        return math.hypot(x-self.tx, y-self.ty) < self.toggle_r+8

    def hit_item(self, x, y) -> Optional[str]:
        if not self.open or self.anim < 0.3: return None
        for i, rect in enumerate(self._items_rect):
            if rect.collidepoint(x,y):
                return self.ITEMS[i][2]
        return None

    def draw(self, surf:pygame.Surface, font_s, font_l):
        # Toggle-Button
        pulse = int(math.sin(self._t*0.08)*4) if not self.open else 0
        col = (80,160,80) if not self.open else (160,80,40)
        pygame.draw.circle(surf,col,(self.tx,self.ty),self.toggle_r+pulse)
        pygame.draw.circle(surf,(200,255,200),(self.tx,self.ty),self.toggle_r+pulse,2)
        icon = "☰" if not self.open else "✕"
        il   = font_l.render(icon,True,C_WHITE)
        surf.blit(il,(self.tx-il.get_width()//2, self.ty-il.get_height()//2))

        if self.anim <= 0.01: return

        # Items
        for i,(emoji,label,cmd) in enumerate(self.ITEMS):
            if i >= len(self._items_rect): break
            r = self._items_rect[i]
            # gestaffelte Animation
            delay = i * 0.08
            prog  = max(0, (self.anim - delay) / (1-delay+0.01))
            if prog <= 0: continue

            alpha = int(255*prog)
            oy    = int((1-prog)*30)

            bg = pygame.Surface((r.w,r.h),pygame.SRCALPHA)
            bg.fill((*C_MENU_BTN,min(230,int(230*prog))))
            pygame.draw.rect(bg,(80,160,80,alpha),(0,0,r.w,r.h),2,border_radius=12)
            bg.set_alpha(alpha)
            surf.blit(bg,(r.x,r.y+oy))

            el = font_l.render(emoji,True,C_WHITE); el.set_alpha(alpha)
            ll = font_s.render(label, True,C_HUD);  ll.set_alpha(alpha)
            surf.blit(el,(r.x+r.w//2-el.get_width()//2, r.y+oy+8))
            surf.blit(ll,(r.x+r.w//2-ll.get_width()//2, r.y+oy+r.h-20))

        # Bestätigung für Quit
        if self.confirm_quit:
            cw, ch = 320, 100
            cx, cy = self.W//2-cw//2, self.H//2-ch//2
            cs = pygame.Surface((cw,ch),pygame.SRCALPHA)
            cs.fill((0,0,0,210))
            pygame.draw.rect(cs,(200,60,60,200),(0,0,cw,ch),2,border_radius=10)
            surf.blit(cs,(cx,cy))
            tl=font_s.render("Welt wirklich beenden?",True,(255,100,100))
            surf.blit(tl,(cx+cw//2-tl.get_width()//2, cy+14))
            for lbl,col,rx in [("JA ✓",(255,80,80),cx+50),("NEIN ✕",(80,200,80),cx+180)]:
                pygame.draw.rect(surf,col,(rx-30,cy+52,90,34),border_radius=8)
                tl2=font_s.render(lbl,True,C_WHITE)
                surf.blit(tl2,(rx-tl2.get_width()//2,cy+62))

    def confirm_rects(self) -> Tuple[pygame.Rect,pygame.Rect]:
        cw,ch=320,100; cx,cy=self.W//2-cw//2,self.H//2-ch//2
        return pygame.Rect(cx+20,cy+52,90,34), pygame.Rect(cx+150,cy+52,90,34)


# ─── Welt ─────────────────────────────────────────────────────────────────────
class World:
    def __init__(self, w:int, h:int):
        self.w, self.h   = w, h
        self.parotis     : List[Paroti] = []
        self.food        : List[Food]   = []
        self.shrine      : Optional[Shrine] = None
        self.mailbox     : Optional[Mailbox]= None
        self.t           = 0
        self.day         = 0
        self.max_gen     = 0
        self.total_born  = 0
        self.total_died  = 0
        self.chronicle   : List[str] = []
        self._historian  : Optional[int] = None  # ID

    def setup_shrine(self):
        self.shrine = Shrine(self.w*0.72, self.h*0.38, GOD_IMAGE)

    def setup_mailbox(self):
        self.mailbox = Mailbox(INBOX_DIR, self.w-70, self.h-55)

    def spawn_initial(self):
        for _ in range(INIT_POP):
            self.parotis.append(Paroti(
                random.uniform(80,self.w-80),
                random.uniform(80,self.h-80),
                Genome.rand()))
        self.total_born = INIT_POP
        self._assign_roles()

    def spawn_one(self):
        if len(self.parotis) >= MAX_POP: return
        p=Paroti(random.uniform(80,self.w-80),random.uniform(80,self.h-80),Genome.rand())
        self.parotis.append(p)
        self.total_born+=1

    def _assign_roles(self):
        if not self.parotis: return
        # Historiker: ältester
        oldest = max(self.parotis, key=lambda p:p.age)
        for p in self.parotis: p.is_historian=False
        oldest.is_historian=True
        self._historian=oldest.id
        # Postfach-Läufer: höchste intellect+courage
        for p in self.parotis: p.is_runner=False
        runner=max(self.parotis, key=lambda p:p.g.intellect+p.g.courage)
        runner.is_runner=True

    def update(self):
        self.t+=1
        self.day=self.t//(60*35)

        if len(self.food)<MAX_FOOD and random.random()<FOOD_RATE:
            self.food.append(Food(random.uniform(40,self.w-40),
                                  random.uniform(40,self.h-40)))
        for f in self.food:    f.update()
        if self.shrine:        self.shrine.update()
        if self.mailbox:       self.mailbox.update()
        for p in self.parotis: p.update(self)

        dead=[p for p in self.parotis if not p.alive]
        if dead:
            self.total_died+=len(dead)
            self.parotis=[p for p in self.parotis if p.alive]
            for p in dead:
                if p.gen>=2:
                    self._log(f"Tag {self.day}: #{p.id} (G{p.gen}) gestorben, {p.children} Kinder")

        # Schrein-Besucher zählen
        if self.shrine:
            self.shrine.visitors=sum(1 for p in self.parotis if p.state==S.WORSHIP)

        # Rollen alle 5min neu vergeben
        if self.t%(60*60*5)==0:
            self._assign_roles()

        if self.t%(60*60)==0:
            self._log(f"Tag {self.day}: {len(self.parotis)} leben, MaxGen {self.max_gen}, "
                      f"Geb:{self.total_born}/Gest:{self.total_died}")

    def _log(self, msg:str):
        self.chronicle.append(msg)
        if len(self.chronicle)>80: self.chronicle.pop(0)

    def nearest_food(self, x, y):
        return min(self.food,key=lambda f:(f.x-x)**2+(f.y-y)**2,default=None)
    def eat_food(self,f):
        if f in self.food: self.food.remove(f)
    def find_mate(self,p):
        c=[q for q in self.parotis if q.id!=p.id and q.mate_cd==0
           and q.hunger<0.45 and q.state==S.MATE]
        return min(c,key=lambda q:(q.x-p.x)**2+(q.y-p.y)**2,default=None)
    def nearest_paroti(self,p):
        o=[q for q in self.parotis if q.id!=p.id]
        return min(o,key=lambda q:(q.x-p.x)**2+(q.y-p.y)**2,default=None)

    def reproduce(self,a,b):
        if len(self.parotis)>=MAX_POP: return
        child=Paroti((a.x+b.x)/2+random.uniform(-25,25),
                     (a.y+b.y)/2+random.uniform(-25,25),
                     a.g.crossover(b.g),generation=max(a.gen,b.gen)+1)
        child.parents=[a.id,b.id]
        a.children+=1; b.children+=1
        self.parotis.append(child)
        self.total_born+=1
        self.max_gen=max(self.max_gen,child.gen)
        self._log(f"Tag {self.day}: Geburt #{child.id} (G{child.gen})")

    def add_food(self,x,y,n=3):
        for _ in range(n):
            self.food.append(Food(x+random.uniform(-25,25),y+random.uniform(-25,25)))
    def rain(self,n=22):
        for _ in range(n):
            self.food.append(Food(random.uniform(40,self.w-40),random.uniform(40,self.h-40)))
    def peace(self):
        for p in self.parotis: p.happy=min(1,p.happy+0.4)
    def wakeall(self):
        for p in self.parotis:
            if p.state==S.SLEEP: p.state=S.WANDER; p.energy=0.6
    def feast(self):
        self.rain(50)
        for p in self.parotis: p.happy=min(1,p.happy+0.5)
    def pet_at(self,x,y):
        for p in self.parotis:
            if math.hypot(p.x-x,p.y-y)<p._sz+18:
                p.petting=70; p.happy=min(1,p.happy+0.22)
                p.trust=min(1,p.trust+0.06); return p
        return None

    def draw(self,surf,font_s,font_m,font_l,font_g):
        for f in self.food:    f.draw(surf)
        if self.shrine:        self.shrine.draw(surf,font_s)
        if self.mailbox:       self.mailbox.draw(surf,font_s,font_m)
        for p in self.parotis: p.draw(surf,font_g)
        self._draw_hud(surf,font_s,font_m)

    def _draw_hud(self,surf,font_s,font_m):
        lines=[
            (font_m,f"Parotis: {len(self.parotis)}",C_HUD),
            (font_s,f"Max. Generation: {self.max_gen}",C_HUD),
            (font_s,f"Geb: {self.total_born}  Gest: {self.total_died}",C_HUD_DIM),
            (font_s,f"Tag {self.day}",  (200,200,140)),
        ]
        y=10
        for f,txt,col in lines:
            surf.blit(f.render(txt,True,col),(12,y)); y+=f.size-4


# ─── Datenbank ────────────────────────────────────────────────────────────────
class DB:
    def __init__(self,path:Path):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(str(path))
        self._init()

    def _init(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS parotis(
                id INT,x REAL,y REAL,gen INT,age INT,genome TEXT,
                hunger REAL,energy REAL,happy REAL,trust REAL,piety REAL,
                children INT,parents TEXT,is_historian INT,is_runner INT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,val TEXT);
            CREATE TABLE IF NOT EXISTS chronicle(ts INT,event TEXT);
        """); self.conn.commit()

    def save(self,world:World):
        self.conn.execute("DELETE FROM parotis")
        for p in world.parotis:
            self.conn.execute("INSERT INTO parotis VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.id,p.x,p.y,p.gen,p.age,json.dumps(asdict(p.g)),
                 p.hunger,p.energy,p.happy,p.trust,p.piety,
                 p.children,json.dumps(p.parents),
                 int(p.is_historian),int(p.is_runner)))
        m=dict(t=world.t,day=world.day,max_gen=world.max_gen,
               born=world.total_born,died=world.total_died)
        self.conn.execute("DELETE FROM meta")
        for k,v in m.items():
            self.conn.execute("INSERT INTO meta VALUES(?,?)",(k,str(v)))
        for ev in world.chronicle[-10:]:
            self.conn.execute("INSERT INTO chronicle VALUES(?,?)",(world.t,ev))
        world.chronicle.clear()
        self.conn.commit()

    def load(self,world:World)->bool:
        cur=self.conn.execute("SELECT COUNT(*) FROM parotis")
        if cur.fetchone()[0]==0: return False
        rows=self.conn.execute("SELECT key,val FROM meta").fetchall()
        m={k:v for k,v in rows}
        world.t=int(m.get('t',0)); world.day=int(m.get('day',0))
        world.max_gen=int(m.get('max_gen',0))
        world.total_born=int(m.get('born',0)); world.total_died=int(m.get('died',0))
        for row in self.conn.execute("SELECT * FROM parotis"):
            id_,x,y,gen,age,g_json,hunger,energy,happy,trust,piety,children,par,hist,runner=row
            p=Paroti(x,y,Genome(**json.loads(g_json)),gen,pid=int(id_))
            p.age=age; p.hunger=hunger; p.energy=energy; p.happy=happy
            p.trust=trust; p.piety=piety; p.children=children
            p.parents=json.loads(par); p.is_historian=bool(hist); p.is_runner=bool(runner)
            world.parotis.append(p)
        Paroti._nxt_id=max((p.id for p in world.parotis),default=0)+1
        rows=self.conn.execute("SELECT event FROM chronicle ORDER BY ts DESC LIMIT 40").fetchall()
        world.chronicle=[r[0] for r in reversed(rows)]
        return True

    def close(self): self.conn.close()


# ─── Game ─────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False)

        info=pygame.display.Info()
        self.W,self.H=info.current_w,info.current_h
        try:
            self.screen=pygame.display.set_mode(
                (self.W,self.H),pygame.FULLSCREEN|pygame.NOFRAME)
        except Exception:
            self.W,self.H=1280,720
            self.screen=pygame.display.set_mode((self.W,self.H))
            pygame.mouse.set_visible(True)

        pygame.display.set_caption("Parotis")
        self.clock=pygame.time.Clock()

        self.fs = pygame.font.Font(None,22)
        self.fm = pygame.font.Font(None,30)
        self.fl = pygame.font.Font(None,52)
        self.fg = pygame.font.Font(None,20)   # Glyph-Font

        self.world=World(self.W,self.H)
        self.world.setup_shrine()
        self.world.setup_mailbox()

        self.db=DB(DB_PATH)
        if not self.db.load(self.world):
            self.world.spawn_initial()
            print("🌱 Neue Welt erschaffen")
        else:
            print(f"🔄 Geladen: {len(self.world.parotis)} Parotis, Tag {self.world.day}")

        self.menu      = TouchMenu(self.W,self.H)
        self.running   = True
        self.last_save = time.time()
        self.selected  : Optional[Paroti]=None
        self.show_chron= False
        self.particles : List[dict]=[]
        self.press_pos : Optional[Tuple[int,int,float]]=None
        self.bg        = self._make_bg()

        print(f"📬 Postfach: {INBOX_DIR}")
        print(f"🙏 Gott-Bild: {GOD_IMAGE or 'Prozedurale Gottheit (kein Bild gefunden)'}")

    def _make_bg(self):
        bg=pygame.Surface((self.W,self.H)); bg.fill(C_BG)
        for _ in range(300):
            x,y=random.randint(0,self.W),random.randint(0,self.H)
            r=random.randint(2,10); s=random.randint(18,55)
            pygame.draw.circle(bg,(s//2,s,s//2),(x,y),r)
        for x in range(0,self.W,80): pygame.draw.line(bg,C_GRID,(x,0),(x,self.H),1)
        for y in range(0,self.H,80): pygame.draw.line(bg,C_GRID,(0,y),(self.W,y),1)
        return bg

    def events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: self.running=False

            elif ev.type==pygame.MOUSEBUTTONDOWN:
                self.press_pos=(*ev.pos,time.time())
                self._on_touch(*ev.pos)
            elif ev.type==pygame.MOUSEBUTTONUP:
                if self.press_pos:
                    if time.time()-self.press_pos[2]>0.7:
                        self._long_press(*ev.pos)
                    self.press_pos=None

            elif ev.type==pygame.FINGERDOWN:
                tx,ty=int(ev.x*self.W),int(ev.y*self.H)
                self.press_pos=(tx,ty,time.time())
                self._on_touch(tx,ty)
            elif ev.type==pygame.FINGERUP:
                if self.press_pos:
                    if time.time()-self.press_pos[2]>0.7:
                        self._long_press(int(ev.x*self.W),int(ev.y*self.H))
                    self.press_pos=None

    def _on_touch(self,x,y):
        # Quit-Bestätigung?
        if self.menu.confirm_quit:
            yes_r,no_r=self.menu.confirm_rects()
            if yes_r.collidepoint(x,y):  self.running=False; return
            if no_r.collidepoint(x,y):   self.menu.confirm_quit=False; return
            return

        # Menü-Toggle?
        if self.menu.hit_toggle(x,y):
            self.menu.toggle(); return

        # Menü-Item?
        if self.menu.open:
            action=self.menu.hit_item(x,y)
            if action:
                self._run_action(action)
                if action!="quit": self.menu.open=False
                return
            self.menu.open=False; return

        # Welt-Touch
        self._particle(x,y)
        petted=self.world.pet_at(x,y)
        if petted: self.selected=petted
        else:
            self.world.add_food(x,y)
            self.selected=None

    def _long_press(self,x,y):
        self.world.rain()
        self._particle(x,y,rain=True)

    def _run_action(self,action:str):
        if action=="rain":      self.world.rain()
        elif action=="feast":   self.world.feast()
        elif action=="peace":   self.world.peace()
        elif action=="newlife": self.world.spawn_one()
        elif action=="chronicle": self.show_chron=not self.show_chron
        elif action=="wakeall": self.world.wakeall()
        elif action=="quit":    self.menu.confirm_quit=True

    def _particle(self,x,y,rain=False):
        self.particles.append(dict(x=x,y=y,life=40,maxl=40,rain=rain))

    def update(self):
        self.world.update()
        self.menu.update()
        if time.time()-self.last_save>SAVE_EVERY:
            self.db.save(self.world); self.last_save=time.time()
        self.particles=[p for p in self.particles if p['life']>0]
        for p in self.particles: p['life']-=1

    def draw(self):
        self.screen.blit(self.bg,(0,0))
        self.world.draw(self.screen,self.fs,self.fm,self.fl,self.fg)

        # Touch-Partikel
        for p in self.particles:
            prog=1-p['life']/p['maxl']; r=int(35*prog); alpha=int(220*(1-prog))
            if r>0:
                col=(100,200,255,alpha) if p['rain'] else (255,240,140,alpha)
                s=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
                pygame.draw.circle(s,col,(r+1,r+1),r); self.screen.blit(s,(p['x']-r-1,p['y']-r-1))

        if self.selected and self.selected.alive: self._draw_panel()
        if self.show_chron: self._draw_chronicle()
        self.menu.draw(self.screen,self.fs,self.fl)
        pygame.display.flip()

    def _draw_panel(self):
        p=self.selected; pw,ph=240,200; px,py=self.W-pw-12,12
        s=pygame.Surface((pw,ph),pygame.SRCALPHA); s.fill((0,0,0,165))
        pygame.draw.rect(s,(*p._col,100),(0,0,pw,ph),2,border_radius=6)
        self.screen.blit(s,(px,py))
        bw=pw-40
        def bar(label,val,col,yo):
            self.screen.blit(self.fs.render(label,True,C_HUD_DIM),(px+8,py+yo))
            pygame.draw.rect(self.screen,(40,40,40),(px+80,py+yo+2,bw,10),border_radius=4)
            pygame.draw.rect(self.screen,col,(px+80,py+yo+2,int(bw*val),10),border_radius=4)
        self.screen.blit(self.fm.render(f"Paroti #{p.id}",True,p._col),(px+8,py+8))
        self.screen.blit(self.fs.render(f"G{p.gen} · Alter {p.age//60}s",True,C_HUD),(px+8,py+32))
        bar("Hunger",  p.hunger, (220,80,60),  55)
        bar("Energie", p.energy, (80,200,120), 75)
        bar("Glück",   p.happy,  (220,200,60), 95)
        bar("Vertrau.",p.trust,  (100,160,255),115)
        bar("Frömmig.",p.piety,  (255,230,80), 135)
        self.screen.blit(self.fs.render(f"Status: {p.status_text()}",True,C_HUD_DIM),(px+8,py+160))
        self.screen.blit(self.fs.render(f"Kinder: {p.children}",True,C_HUD_DIM),(px+8,py+178))

    def _draw_chronicle(self):
        w=min(500,self.W-20); lines=self.world.chronicle[-22:]
        h=len(lines)*18+20
        s=pygame.Surface((w,h),pygame.SRCALPHA); s.fill((0,0,0,180))
        self.screen.blit(s,(10,self.H-h-30))
        for i,line in enumerate(lines):
            col=(180,200,160) if i==len(lines)-1 else (110,140,110)
            self.screen.blit(self.fs.render(line,True,col),(18,self.H-h-30+10+i*18))

    def run(self):
        print("🎮 Parotis v2 startet ...")
        try:
            while self.running:
                self.events(); self.update(); self.draw()
                self.clock.tick(FPS)
        finally:
            print("💾 Speichert ...")
            self.db.save(self.world); self.db.close()
            pygame.quit()
            print(f"👋 Tschüss! {self.world.total_born} Parotis lebten.")
            sys.exit(0)


if __name__=="__main__":
    Game().run()
