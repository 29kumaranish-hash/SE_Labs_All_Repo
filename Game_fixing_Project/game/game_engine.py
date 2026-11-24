import math
import pygame
from .marble import Marble
from .wall import Wall
from .sounds import SoundManager

# Game Engine

WHITE = (255, 255, 255)
DARK = (40, 40, 50)
WALL_COLOR = (90, 90, 110)
GOAL_COLOR = (60, 200, 120)

# Difficulty presets: tilt strength (max pull per frame), friction, time limit
DIFFICULTY_ORDER = ["Easy", "Medium", "Hard"]
DIFFICULTIES = {
    "Easy":   {"tilt_strength": 0.7, "friction": 0.07, "time_limit_ms": 60000},
    "Medium": {"tilt_strength": 0.6, "friction": 0.05, "time_limit_ms": 45000},
    "Hard":   {"tilt_strength": 0.5, "friction": 0.03, "time_limit_ms": 30000},
}

class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        # "cursor": marble is pulled toward the mouse pointer (follows it)
        # "tilt":   original behaviour, direction of cursor from screen centre
        self.control_mode = "cursor"
        self.max_speed = 8
        self.full_pull_dist = 120     # cursor distance (px) giving full pull
        self.deadzone = 6             # no pull when marble is on the cursor

        self.walls = self._build_maze()
        self.goal_x, self.goal_y, self.goal_radius = width - 60, height - 60, 22

        self.font = pygame.font.SysFont("Arial", 26)
        self.title_font = pygame.font.SysFont("Arial", 54, bold=True)
        self.body_font = pygame.font.SysFont("Arial", 28)
        self.hint_font = pygame.font.SysFont("Arial", 20)
        self.small_font = pygame.font.SysFont("Arial", 16)
        self.input_delay_ms = 700     # ignore input briefly so the click/key
                                      # you were playing with can't pick an option

        self.sounds = SoundManager()
        self._impact = 0.0            # hardest wall hit this frame (for sound)

        self.difficulty = "Medium"
        self._build_menu_buttons()
        self.reset(self.difficulty)

    def reset(self, difficulty=None):
        """Start a fresh round, optionally at a new difficulty."""
        if difficulty is not None:
            self.difficulty = difficulty
        settings = DIFFICULTIES[self.difficulty]
        self.tilt_strength = settings["tilt_strength"]   # max acceleration per frame
        self.friction = settings["friction"]
        self.time_limit_ms = settings["time_limit_ms"]

        self.marble = Marble(50, 50)
        self.game_over = False
        self.result = None  # "solved" or "timeout"
        self.finish_time_ms = None
        self.elapsed_ms = 0
        self.game_over_ticks = None   # when the round ended

        # start the clock last so setup time is not counted
        self.start_ticks = pygame.time.get_ticks()

    def _build_menu_buttons(self):
        """Rectangles for the end-screen buttons (difficulty row + exit)."""
        panel = pygame.Rect(0, 0, 500, 300)
        panel.center = (self.width // 2, self.height // 2)
        self.panel_rect = panel

        bw, bh, gap = 140, 56, 15
        total = 3 * bw + 2 * gap
        x0 = panel.centerx - total // 2
        y = panel.top + 145
        self.difficulty_buttons = {}
        for i, name in enumerate(DIFFICULTY_ORDER):
            self.difficulty_buttons[name] = pygame.Rect(x0 + i * (bw + gap), y, bw, bh)

        self.exit_button = pygame.Rect(0, 0, 200, 38)
        self.exit_button.midtop = (panel.centerx, y + bh + 18)

    def _build_maze(self):
        walls = []
        t = 16  # wall thickness

        # outer boundary
        walls.append(Wall(0, 0, self.width, t))
        walls.append(Wall(0, self.height - t, self.width, t))
        walls.append(Wall(0, 0, t, self.height))
        walls.append(Wall(self.width - t, 0, t, self.height))

        # a few internal walls forming a simple winding path
        walls.append(Wall(0, 140, self.width - 140, t))
        walls.append(Wall(140, 260, self.width - 140, t))
        walls.append(Wall(0, 380, self.width - 140, t))

        return walls

    def handle_event(self, event):
        # During play the game is driven by the continuous mouse position
        # (see handle_input). Once the round is over, the end screen offers:
        #   1 / 2 / 3 (or click) -> play again on Easy / Medium / Hard
        #   Esc / Q (or click Exit) -> quit
        if not self.game_over or self.game_over_ticks is None:
            return
        if pygame.time.get_ticks() - self.game_over_ticks < self.input_delay_ms:
            return

        if event.type == pygame.KEYDOWN:
            keys = {pygame.K_1: "Easy", pygame.K_2: "Medium", pygame.K_3: "Hard"}
            if event.key in keys:
                self.reset(keys[event.key])
            elif event.key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_4):
                self._request_exit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.difficulty_buttons.items():
                if rect.collidepoint(event.pos):
                    self.reset(name)
                    return
            if self.exit_button.collidepoint(event.pos):
                self._request_exit()

    def _request_exit(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _end_round(self, result, finish_ms=None):
        self.game_over = True
        self.result = result
        self.finish_time_ms = finish_ms
        self.game_over_ticks = pygame.time.get_ticks()
        if result == "solved":
            self.sounds.play_win()
        else:
            self.sounds.play_timeout()

    def handle_input(self):
        if self.game_over:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()

        if self.control_mode == "cursor":
            # vector from the marble to the cursor
            dx = mouse_x - self.marble.x
            dy = mouse_y - self.marble.y
        else:
            # vector from screen centre to the cursor (simulated tilt)
            dx = mouse_x - self.width / 2
            dy = mouse_y - self.height / 2

        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist < self.deadzone:
            return

        # pull grows with distance, so a nearby cursor gives a gentle push
        # and a far cursor gives full strength
        strength = self.tilt_strength * min(1.0, dist / self.full_pull_dist)
        self.marble.vx += (dx / dist) * strength
        self.marble.vy += (dy / dist) * strength

    def update(self):
        if self.game_over:
            return

        elapsed = pygame.time.get_ticks() - self.start_ticks
        self.elapsed_ms = min(elapsed, self.time_limit_ms)
        if elapsed >= self.time_limit_ms:
            self._end_round("timeout")
            return

        self.marble.vx *= (1 - self.friction)
        self.marble.vy *= (1 - self.friction)

        speed = (self.marble.vx ** 2 + self.marble.vy ** 2) ** 0.5
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.marble.vx *= scale
            self.marble.vy *= scale

        self.marble.x += self.marble.vx
        self.marble.y += self.marble.vy

        self._impact = 0.0
        self._resolve_wall_collisions()
        self.sounds.play_bounce(self._impact)

        gx = self.goal_x - self.marble.x
        gy = self.goal_y - self.marble.y
        if (gx ** 2 + gy ** 2) ** 0.5 <= self.goal_radius:
            self.elapsed_ms = elapsed
            self._end_round("solved", finish_ms=elapsed)

    def _resolve_wall_collisions(self):
        """True circle-vs-rectangle collision.

        For each wall, find the point on the rectangle closest to the
        marble's centre. The marble touches the wall only if that point is
        closer than the marble's radius. Near a corner the closest point is
        the corner itself, so the marble bounces off the round shape it
        actually has, not off its square bounding box.
        """
        m = self.marble
        r = m.radius
        restitution = 0.3  # same bounciness as before (velocity * -0.3)

        for wall in self.walls:
            rect = wall.rect()

            # closest point on the wall rectangle to the marble centre
            closest_x = max(rect.left, min(m.x, rect.right))
            closest_y = max(rect.top, min(m.y, rect.bottom))

            dx = m.x - closest_x
            dy = m.y - closest_y
            dist_sq = dx * dx + dy * dy

            if dist_sq >= r * r:
                continue  # circle does not touch this wall

            if dist_sq > 0:
                # centre is outside the wall: push out along the contact normal
                dist = dist_sq ** 0.5
                nx, ny = dx / dist, dy / dist
                penetration = r - dist
            else:
                # centre is inside the wall (should be rare): escape through
                # the nearest edge
                left = m.x - rect.left
                right = rect.right - m.x
                top = m.y - rect.top
                bottom = rect.bottom - m.y
                nearest = min(left, right, top, bottom)
                if nearest == left:
                    nx, ny = -1.0, 0.0
                elif nearest == right:
                    nx, ny = 1.0, 0.0
                elif nearest == top:
                    nx, ny = 0.0, -1.0
                else:
                    nx, ny = 0.0, 1.0
                penetration = nearest + r

            m.x += nx * penetration
            m.y += ny * penetration

            # bounce only if the marble is moving into the wall
            vn = m.vx * nx + m.vy * ny
            if vn < 0:
                self._impact = max(self._impact, -vn)   # for the bounce sound
                m.vx -= (1 + restitution) * vn * nx
                m.vy -= (1 + restitution) * vn * ny

    def render(self, screen):
        screen.fill(DARK)

        for wall in self.walls:
            pygame.draw.rect(screen, WALL_COLOR, wall.rect())

        pygame.draw.circle(screen, GOAL_COLOR, (self.goal_x, self.goal_y), self.goal_radius)
        pygame.draw.circle(screen, WHITE, (int(self.marble.x), int(self.marble.y)), self.marble.radius)

        # uses the frozen value, so the clock stops when the round ends
        remaining_ms = max(0, self.time_limit_ms - self.elapsed_ms)
        seconds_left = math.ceil(remaining_ms / 1000)
        timer_text = self.font.render(f"Time: {seconds_left}s", True, WHITE)
        screen.blit(timer_text, (10, 10))
        level_text = self.hint_font.render(self.difficulty, True, (170, 170, 185))
        screen.blit(level_text, level_text.get_rect(topright=(self.width - 24, 22)))

        if self.game_over:
            self._draw_end_screen(screen)

    def _draw_end_screen(self, screen):
        # dim the maze behind the message
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))

        if self.result == "solved":
            title, color = "MAZE SOLVED!", GOAL_COLOR
            detail = f"Finished in {self.finish_time_ms / 1000:.1f}s on {self.difficulty}"
        else:
            title, color = "TIME'S UP!", (220, 70, 70)
            detail = "The timer ran out - maze not solved"

        # solid panel so maze walls never run through the text
        panel = self.panel_rect
        pygame.draw.rect(screen, DARK, panel, border_radius=14)
        pygame.draw.rect(screen, color, panel, width=3, border_radius=14)

        cx = panel.centerx
        title_surf = self.title_font.render(title, True, color)
        screen.blit(title_surf, title_surf.get_rect(center=(cx, panel.top + 45)))
        detail_surf = self.body_font.render(detail, True, WHITE)
        screen.blit(detail_surf, detail_surf.get_rect(center=(cx, panel.top + 95)))

        # menu appears once input is being accepted
        if pygame.time.get_ticks() - self.game_over_ticks < self.input_delay_ms:
            return

        label = self.hint_font.render("Play again - choose difficulty:", True, (190, 190, 200))
        screen.blit(label, label.get_rect(center=(cx, panel.top + 130)))

        mouse = pygame.mouse.get_pos()
        for i, name in enumerate(DIFFICULTY_ORDER):
            rect = self.difficulty_buttons[name]
            hovered = rect.collidepoint(mouse)
            self._draw_button(screen, rect, f"{i + 1}  {name}",
                              f"{DIFFICULTIES[name]['time_limit_ms'] // 1000}s limit",
                              hovered, highlight=(name == self.difficulty))

        self._draw_button(screen, self.exit_button, "Esc  Exit", None,
                          self.exit_button.collidepoint(mouse))

    def _draw_button(self, screen, rect, text, subtext, hovered, highlight=False):
        fill = (85, 85, 110) if hovered else (60, 60, 78)
        border = GOAL_COLOR if highlight else (130, 130, 150)
        pygame.draw.rect(screen, fill, rect, border_radius=8)
        pygame.draw.rect(screen, border, rect, width=2, border_radius=8)
        if subtext:
            t = self.hint_font.render(text, True, WHITE)
            screen.blit(t, t.get_rect(center=(rect.centerx, rect.centery - 9)))
            st = self.small_font.render(subtext, True, (170, 170, 185))
            screen.blit(st, st.get_rect(center=(rect.centerx, rect.centery + 14)))
        else:
            t = self.hint_font.render(text, True, WHITE)
            screen.blit(t, t.get_rect(center=rect.center))