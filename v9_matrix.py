#!/usr/bin/env python3
import os, random, time, subprocess, sys
from datetime import datetime
import pygame
try:
    import requests
except Exception:
    requests = None

WIDTH, HEIGHT, FPS = 480, 320, 60
FULLSCREEN = os.getenv('MATRIX_FULLSCREEN','1') != '0'
MATRIX = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+=<>?/\\|ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ'
GREEN=(0,255,70); DIM=(0,70,25); WHITE=(190,255,205); BLACK=(0,0,0)
XRP_URL='https://min-api.cryptocompare.com/data/price?fsym=XRP&tsyms=USD'

class Drop:
    def __init__(self,x,h):
        self.x=x; self.h=h; self.reset(True)
    def reset(self, first=False):
        self.y=random.uniform(-HEIGHT, HEIGHT if first else -20)
        r=random.random()
        self.speed=random.uniform(10,17) if r<.10 else random.uniform(6,11) if r<.35 else random.uniform(3.5,7.5)
        self.length=random.randint(8,22)
        self.chars=[random.choice(MATRIX) for _ in range(self.length)]
        self.burst=1.0
    def update(self):
        if random.random()<.003: self.burst=random.uniform(1.8,3.2)
        self.burst += (1-self.burst)*.05
        self.y += self.speed*self.burst
        if random.random()<.09: self.chars[random.randrange(len(self.chars))]=random.choice(MATRIX)
        if self.y-self.length*self.h>HEIGHT: self.reset()

class Rain:
    def __init__(self,font):
        self.font=font; self.w=max(10,font.size('W')[0]); self.h=max(14,font.get_linesize())
        self.drops=[Drop(x,self.h) for x in range(0,WIDTH+self.w,self.w)]
    def draw(self,surface):
        for d in self.drops:
            d.update()
            for i,ch in enumerate(d.chars):
                y=int(d.y-i*self.h)
                if y<0 or y>HEIGHT: continue
                b=max(.10,1-i/max(1,d.length))
                c=WHITE if i==0 else tuple(int(DIM[j]+(GREEN[j]-DIM[j])*b) for j in range(3))
                surface.blit(self.font.render(ch,True,c),(d.x,y))

class Live:
    def __init__(self):
        self.xrp=None; self.last=0
    def refresh(self):
        if time.monotonic()-self.last<20: return
        self.last=time.monotonic()
        if not requests: return
        try:
            r=requests.get(XRP_URL,timeout=5); r.raise_for_status(); data=r.json()
            if isinstance(data.get('USD'),(int,float)): self.xrp=float(data['USD'])
        except Exception:
            pass

class App:
    def __init__(self):
        pygame.init(); flags=pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen=pygame.display.set_mode((WIDTH,HEIGHT),flags)
        pygame.mouse.set_visible(False); pygame.display.set_caption('Matrix OS V9')
        self.clock=pygame.time.Clock()
        self.rain_font=pygame.font.SysFont('DejaVu Sans Mono',16,bold=False)
        self.time_font=pygame.font.SysFont('DejaVu Sans Mono',34,bold=False)
        self.label_font=pygame.font.SysFont('DejaVu Sans Mono',18,bold=False)
        self.value_font=pygame.font.SysFont('DejaVu Sans Mono',48,bold=False)
        self.rain=Rain(self.rain_font); self.live=Live(); self.mode=0; self.next_switch=time.monotonic()+8
    def glow(self,font,text,center,color=GREEN):
        img=font.render(text,True,color); rect=img.get_rect(center=center)
        for dx,dy in ((2,0),(-2,0),(0,2),(0,-2)):
            ghost=font.render(text,True,(0,80,25)); self.screen.blit(ghost,rect.move(dx,dy))
        self.screen.blit(img,rect)
    def draw_overlay(self):
        now=datetime.now()
        self.glow(self.time_font,now.strftime('%I:%M:%S %p').lstrip('0'),(WIDTH//2,34))
        self.glow(self.label_font,now.strftime('%A, %B %d, %Y').upper(),(WIDTH//2,64))
        if time.monotonic()>self.next_switch:
            self.mode=(self.mode+1)%2; self.next_switch=time.monotonic()+8
        if self.mode==0:
            self.glow(self.label_font,'XRP PRICE',(WIDTH//2,170))
            val='CONNECTING...' if self.live.xrp is None else f'${self.live.xrp:,.3f}'
            self.glow(self.value_font,val,(WIDTH//2,220),WHITE if self.live.xrp is None else GREEN)
        else:
            self.glow(self.label_font,'MATRIX OS V9',(WIDTH//2,185))
            self.glow(self.value_font,'ONLINE',(WIDTH//2,230))
    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type==pygame.QUIT: return
                if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: return
            self.live.refresh(); self.screen.fill(BLACK); self.rain.draw(self.screen); self.draw_overlay()
            pygame.display.flip(); self.clock.tick(FPS)

def main():
    try: App().run(); return 0
    finally: pygame.quit()
if __name__=='__main__': raise SystemExit(main())
