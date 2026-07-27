#!/usr/bin/env python3
"""Matrix OS V10: cinematic Pi scenes synchronized to the ESP32 sidecar."""
from __future__ import annotations

import json, math, os, random, socket, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, Tuple

import pygame
from live_data import LiveData
from main import (
    BLACK, BRIGHT_GREEN, DIM_GREEN, FPS, FULLSCREEN, HEAD_GREEN, HEIGHT,
    MATRIX_CHARS, WIDTH, CinematicRain, RainTextTransition, choose_font,
    choose_matrix_font, clamp, ease_in_out, mix, temp_color,
)

IDLE_MIN = float(os.getenv("MATRIX_IDLE_MIN_SECONDS", "12"))
IDLE_MAX = float(os.getenv("MATRIX_IDLE_MAX_SECONDS", "26"))
COLLECT_S, CUTSCENE_S, HOLD_S = 1.85, 2.05, 4.2
SIDECAR_PORT = int(os.getenv("MATRIX_SIDECAR_PORT", "4210"))
STATE_FILE = Path(os.getenv("MATRIX_SIDECAR_STATE_FILE", "/tmp/matrix_sidecar_state.json"))
Color = Tuple[int, int, int]


def fit_font(text: str, width: int, size: int) -> pygame.font.Font:
    while size > 42:
        font = choose_font(size, bold=True)
        if font.size(text)[0] <= width:
            return font
        size -= 2
    return choose_font(42, bold=True)


def back(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


class Sidecar:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.payload: Optional[dict] = None
        self.last = 0.0
        self.event_id = 0

    def send(self) -> None:
        if self.payload is None:
            return
        self.payload["sent_at"] = datetime.now(timezone.utc).isoformat()
        try:
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.payload), encoding="utf-8")
            tmp.replace(STATE_FILE)
        except OSError:
            pass
        try:
            raw = json.dumps(self.payload, separators=(",", ":")).encode()
            self.sock.sendto(raw, ("255.255.255.255", SIDECAR_PORT))
        except OSError as exc:
            print(f"Sidecar UDP: {exc}", file=sys.stderr)
        self.last = time.monotonic()

    def show(self, source: str, value: Optional[float]) -> None:
        self.event_id += 1
        self.payload = {
            "mode": "temperature", "source": source,
            "temperature_f": None if value is None else int(round(value)),
            "event_id": self.event_id, "ttl_ms": 9000,
        }
        self.send()

    def rain(self) -> None:
        self.event_id += 1
        self.payload = {
            "mode": "rain", "source": "none", "temperature_f": None,
            "event_id": self.event_id, "ttl_ms": 2500,
        }
        self.send(); self.send(); self.send()
        self.payload = None

    def tick(self) -> None:
        if self.payload and time.monotonic() - self.last > 0.45:
            self.send()


class Director:
    EVENTS: Sequence[str] = ("outside", "inside")

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT), pygame.FULLSCREEN if FULLSCREEN else 0
        )
        pygame.display.set_caption("Matrix OS V10 - Cinematic Sidecar")
        pygame.mouse.set_visible(False)
        self.timer = pygame.time.Clock()
        self.clock_font = fit_font("12:59 PM", WIDTH - 22, 72)
        self.hero_fonts = {
            "OUTSIDE": fit_font("OUTSIDE", WIDTH - 20, 92),
            "INSIDE": fit_font("INSIDE", WIDTH - 20, 92),
        }
        self.blank_font = choose_font(10, bold=True)
        self.tiny_font = choose_matrix_font(9, bold=True)
        self.label_font = choose_font(14, bold=True)
        self.rain_fx = CinematicRain()
        self.data = LiveData(); self.data.refresh(force=True)
        self.sidecar = Sidecar()
        self.index, self.phase = 0, "idle"
        self.phase_start = time.monotonic()
        self.idle_wait = random.uniform(IDLE_MIN, IDLE_MAX)
        self.key, self.style = "outside", "lightning"
        self.value: Optional[float] = None
        self.transition: Optional[RainTextTransition] = None
        self.collect_points = []

    def elapsed(self) -> float:
        return time.monotonic() - self.phase_start

    def set_phase(self, phase: str) -> None:
        self.phase, self.phase_start = phase, time.monotonic()

    def begin(self) -> None:
        self.data.refresh(force=True)
        self.key = self.EVENTS[self.index]
        self.value = self.data.outside_f if self.key == "outside" else self.data.inside_f
        self.style = "lightning" if self.key == "outside" else random.choice(("robot", "agent"))
        self.collect_points = self.rain_fx.source_points(180)
        self.transition = None
        self.set_phase("collect")

    def form(self) -> None:
        title = self.key.upper()
        self.transition = RainTextTransition(
            self.rain_fx, title, "", temp_color(self.value),
            self.hero_fonts[title], self.blank_font, self.tiny_font,
        )
        self.sidecar.show(self.key, self.value)
        self.set_phase("form")

    def finish(self) -> None:
        self.sidecar.rain()
        self.index = (self.index + 1) % len(self.EVENTS)
        self.transition = None
        self.idle_wait = random.uniform(IDLE_MIN, IDLE_MAX)
        self.set_phase("idle")

    def update(self, dt: float) -> None:
        self.data.refresh(); self.sidecar.tick()
        self.rain_fx.update(dt, 0.0 if self.phase == "idle" else 0.34)
        e = self.elapsed()
        if self.phase == "idle" and e >= self.idle_wait:
            self.begin()
        elif self.phase == "collect" and e >= COLLECT_S:
            self.set_phase("cutscene")
        elif self.phase == "cutscene" and e >= CUTSCENE_S:
            self.form()
        elif self.phase == "form" and self.transition:
            self.transition.update(dt)
            if self.transition.form_done(): self.set_phase("hold")
        elif self.phase == "hold" and e >= HOLD_S and self.transition:
            self.transition.start_melt(); self.set_phase("melt")
        elif self.phase == "melt" and self.transition:
            self.transition.update(dt)
            if self.transition.melt_done(): self.finish()

    def draw_collect(self, p: float) -> None:
        p, target = clamp(p, 0, 1), (WIDTH // 2, HEIGHT - 40)
        q = ease_in_out(p)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); veil.fill((0, 0, 0, int(70*p)))
        self.screen.blit(veil, (0, 0))
        for i, (sx, sy) in enumerate(self.collect_points):
            swirl = math.sin(i * 1.7 + p * math.tau * 2) * (1-q) * 24
            x, y = sx + (target[0]-sx)*q + swirl, sy + (target[1]-sy)*q
            pygame.draw.circle(self.screen, mix((0,50,15), HEAD_GREEN, p), (int(x), int(y)), 1)
        w = int(30 + 340*q)
        for n in range(5):
            pygame.draw.ellipse(self.screen, (0, max(40,230-n*38), 60), (target[0]-w//2-n*3, target[1]-8-n, w+n*6, 16+n*2), 1)

    @staticmethod
    def bolt(seed: int = 713):
        r, pts, x, y = random.Random(seed), [], WIDTH//2, 45
        while y < HEIGHT-45:
            pts.append((x,y)); x += r.randint(-28,28); y += r.randint(18,32)
        pts.append((x, HEIGHT-45)); return pts

    def draw_lightning(self, p: float) -> None:
        flash = max(max(0, 1-abs(p-.35)*9), max(0, 1-abs(p-.78)*12)*.65)
        if flash:
            o = pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA); o.fill((140,255,175,int(130*flash))); self.screen.blit(o,(0,0))
        if p > .2:
            pts = self.bolt(); pygame.draw.lines(self.screen, (220,255,230), False, pts, 5); pygame.draw.lines(self.screen, BRIGHT_GREEN, False, pts, 2)

    def draw_robot(self, p: float) -> None:
        x, ground = int(-60+(WIDTH+120)*ease_in_out(p)), 244
        s, y = math.sin(p*math.tau*5), 168-int(abs(math.sin(p*math.tau*5))*6)
        c, f = (40,255,105), (0,15,5)
        pygame.draw.rect(self.screen,f,(x-17,y-27,34,26)); pygame.draw.rect(self.screen,c,(x-17,y-27,34,26),2)
        pygame.draw.circle(self.screen,HEAD_GREEN,(x-7,y-14),3); pygame.draw.circle(self.screen,HEAD_GREEN,(x+7,y-14),3)
        pygame.draw.rect(self.screen,f,(x-22,y,44,45)); pygame.draw.rect(self.screen,c,(x-22,y,44,45),2)
        pygame.draw.line(self.screen,c,(x-18,y+8),(x-40,y+28+int(s*22)),5); pygame.draw.line(self.screen,c,(x+18,y+8),(x+40,y+28-int(s*22)),5)
        pygame.draw.line(self.screen,c,(x-10,y+43),(x-25,ground-int(s*18)),6); pygame.draw.line(self.screen,c,(x+10,y+43),(x+25,ground+int(s*18)),6)
        self.screen.blit(self.label_font.render("UNAUTHORIZED PROCESS",True,(0,120,38)),(14,282))

    def draw_agent(self, p: float) -> None:
        a=clamp(p/.42,0,1); x=int(WIDTH+80+(WIDTH//2-(WIDTH+80))*back(a)); look=math.sin(max(0,p-.45)*math.tau*2); off=int(look*7)
        c,f=(0,190,55),(0,7,2)
        pygame.draw.polygon(self.screen,f,[(x-28,168),(x+28,168),(x+45,250),(x-45,250)]); pygame.draw.lines(self.screen,c,False,[(x-28,168),(x-45,250),(x+45,250),(x+28,168)],2)
        pygame.draw.circle(self.screen,f,(x,142),28); pygame.draw.circle(self.screen,c,(x,142),28,2)
        pygame.draw.line(self.screen,HEAD_GREEN,(x-22+off,139),(x-3+off,139),3); pygame.draw.line(self.screen,HEAD_GREEN,(x+3+off,139),(x+22+off,139),3)
        if p>.48:
            bx=int(x+off+look*150); o=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); pygame.draw.polygon(o,(0,255,75,24),[(x+off,142),(bx-45,80),(bx+45,280)]); self.screen.blit(o,(0,0))
        self.screen.blit(self.label_font.render("AGENT SCAN",True,(0,135,42)),(18,282))

    def draw_cutscene(self, p: float) -> None:
        o=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); o.fill((0,0,0,90)); self.screen.blit(o,(0,0))
        if self.style=="lightning": self.draw_lightning(p)
        elif self.style=="robot": self.draw_robot(p)
        else: self.draw_agent(p)
        y=int(clamp(p,0,1)*HEIGHT); pygame.draw.line(self.screen,(0,105,32),(0,y),(WIDTH,y),1)

    def draw_clock(self) -> None:
        text=datetime.now().strftime("%I:%M %p").lstrip("0"); color=HEAD_GREEN if self.phase=="idle" else (175,255,190)
        img=self.clock_font.render(text,True,color); rect=img.get_rect(center=(WIDTH//2,43)); shadow=self.clock_font.render(text,True,BLACK)
        for d in ((-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,2)): self.screen.blit(shadow,rect.move(*d))
        glow=self.clock_font.render(text,True,(0,78,25)); self.screen.blit(glow,rect.move(-2,0)); self.screen.blit(glow,rect.move(2,0)); self.screen.blit(img,rect)

    def draw(self) -> None:
        self.screen.fill(BLACK); self.rain_fx.draw(self.screen,0 if self.phase=="idle" else .28); e=self.elapsed()
        if self.phase=="collect": self.draw_collect(e/COLLECT_S)
        elif self.phase=="cutscene": self.draw_cutscene(e/CUTSCENE_S)
        elif self.phase in ("form","hold","melt") and self.transition: self.transition.draw(self.screen)
        self.draw_clock(); pygame.display.flip()

    def run(self) -> None:
        last=time.monotonic(); running=True
        while running:
            for event in pygame.event.get():
                if event.type==pygame.QUIT: running=False
                elif event.type==pygame.KEYDOWN:
                    if event.key==pygame.K_ESCAPE: running=False
                    elif event.key in (pygame.K_SPACE,pygame.K_RIGHT):
                        if self.phase=="idle": self.begin()
                        elif self.phase=="hold" and self.transition: self.transition.start_melt(); self.set_phase("melt")
            now=time.monotonic(); dt=min(.05,now-last); last=now; self.update(dt); self.draw(); self.timer.tick(FPS)
        self.sidecar.rain()


def main() -> int:
    try: Director().run(); return 0
    except KeyboardInterrupt: return 0
    except Exception as exc: print(f"Matrix OS V10 failed: {exc}",file=sys.stderr); return 1
    finally: pygame.quit()

if __name__=="__main__": raise SystemExit(main())
