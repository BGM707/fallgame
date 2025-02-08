import threading
import random
import sys
import os
import time
import pygame
import flet as ft
import asyncio
from io import BytesIO
from PIL import Image
import base64

# ========================
# Constantes Globales
# ========================
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
FPS = 60

GRAVITY = 9.81       # m/s^2
SCALE = 10           # píxeles por metro
G_PIXELS = GRAVITY * SCALE  # aceleración gravitatoria en píxeles/s^2

OBSTACLE_HEIGHT = 20
CONTROL_ACCEL_CONST = 500  # Afecta la aceleración lateral

HIGH_SCORE_FILE = "highscore.txt"

# Colores
COLOR_GOLD = (255, 215, 0)
COLOR_BROWN = (139, 69, 19)
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_SKY_BLUE = (135, 206, 235)

# ========================
# Funciones para High Score
# ========================
def load_high_score():
    if os.path.exists(HIGH_SCORE_FILE):
        try:
            with open(HIGH_SCORE_FILE, "r") as f:
                return int(f.read().strip())
        except Exception as e:
            print("Error al cargar el high score:", e)
            return 0
    else:
        return 0

def save_high_score(score):
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(score))
    except Exception as e:
        print("Error al guardar el high score:", e)

# ========================
# Clase Particle (efecto de explosión)
# ========================
class Particle:
    """
    Representa una partícula para simular el destello de átomos al colisionar.
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-150, 150)
        self.vy = random.uniform(-150, 150)
        self.lifetime = random.uniform(0.5, 1.5)  # Duración en segundos
        self.radius = random.randint(2, 4)
        self.color = COLOR_GOLD  # Color dorado

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.lifetime -= dt

    def draw(self, surface, camera_offset):
        if self.lifetime > 0:
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y - camera_offset)), self.radius)

# ========================
# Clase Obstacle
# ========================
class Obstacle:
    """
    Representa un obstáculo: una barra horizontal con un hueco aleatorio.
    """
    def __init__(self, y, screen_width, gap_width=80):
        self.y = y
        self.screen_width = screen_width
        self.height = OBSTACLE_HEIGHT
        self.gap_width = gap_width
        self.gap_x = random.randint(50, screen_width - 50 - gap_width)

    def draw(self, surface, camera_offset):
        obst_y_screen = self.y - camera_offset
        if -self.height < obst_y_screen < SCREEN_HEIGHT:
            # Parte izquierda
            left_rect = pygame.Rect(0, obst_y_screen, self.gap_x, self.height)
            pygame.draw.rect(surface, COLOR_BROWN, left_rect)
            # Parte derecha
            right_rect = pygame.Rect(self.gap_x + self.gap_width, obst_y_screen,
                                     self.screen_width - (self.gap_x + self.gap_width), self.height)
            pygame.draw.rect(surface, COLOR_BROWN, right_rect)
            # Líneas divisorias del hueco
            pygame.draw.line(surface, COLOR_BLACK, (self.gap_x, obst_y_screen),
                             (self.gap_x, obst_y_screen + self.height))
            pygame.draw.line(surface, COLOR_BLACK, (self.gap_x + self.gap_width, obst_y_screen),
                             (self.gap_x + self.gap_width, obst_y_screen + self.height))

    def get_collision_rects(self, camera_offset):
        obst_y_screen = self.y - camera_offset
        left_rect = pygame.Rect(0, obst_y_screen, self.gap_x, self.height)
        right_rect = pygame.Rect(self.gap_x + self.gap_width, obst_y_screen,
                                 SCREEN_WIDTH - (self.gap_x + self.gap_width), self.height)
        return left_rect, right_rect

# ========================
# Clase Player
# ========================
class Player:
    """
    Representa al jugador (la figura que cae).
    Parámetros:
      - shape: "Pelota", "Cuadrado" o "Triángulo"
      - size: define el tamaño (afecta la agilidad y la apariencia)
      - color: color de la figura (tupla RGB)
    """
    def __init__(self, x, y, shape, size, color):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.shape = shape
        self.size = size
        self.color = color
        self.hit_count = 0  # Contador de golpes
        self.bounce_count = 0  # Contador de rebotes

    def update(self, dt, lateral_input, g_pixels):
        # La agilidad se reduce a medida que la figura es más grande
        lateral_acc = CONTROL_ACCEL_CONST / self.size
        self.vx += lateral_input * lateral_acc * dt
        self.vy += g_pixels * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.995  # Fricción lateral reducida

        # Limitar el movimiento horizontal
        if self.x < 0:
            self.x = 0
            self.vx = 0
        elif self.x > SCREEN_WIDTH:
            self.x = SCREEN_WIDTH
            self.vx = 0

    def get_collision_rect(self, camera_offset):
        obj_y_screen = self.y - camera_offset
        if self.shape == "Pelota":
            radius = self.size
            return pygame.Rect(self.x - radius, obj_y_screen - radius, radius * 2, radius * 2)
        elif self.shape == "Cuadrado":
            side = self.size
            return pygame.Rect(self.x - side/2, obj_y_screen - side/2, side, side)
        elif self.shape == "Triángulo":
            side = self.size
            return pygame.Rect(self.x - side/2, obj_y_screen - side/2, side, side)

    def draw(self, surface, camera_offset):
        obj_y_screen = self.y - camera_offset
        if self.shape == "Pelota":
            radius = self.size
            pygame.draw.circle(surface, self.color, (int(self.x), int(obj_y_screen)), radius)
        elif self.shape == "Cuadrado":
            side = self.size
            rect = pygame.Rect(self.x - side/2, obj_y_screen - side/2, side, side)
            pygame.draw.rect(surface, self.color, rect)
        elif self.shape == "Triángulo":
            side = self.size
            half = side / 2
            points = [
                (self.x, obj_y_screen - half),
                (self.x - half, obj_y_screen + half),
                (self.x + half, obj_y_screen + half)
            ]
            pygame.draw.polygon(surface, self.color, points)

# ========================
# Clase Game
# ========================
class Game:
    """
    Encapsula la simulación del juego:
      - Ajusta obstáculos según la dificultad.
      - Controla la actualización de la física y la detección de colisiones.
      - Al colisionar se activa una animación de partículas (destello de átomos).
      - Al finalizar, muestra el puntaje y actualiza el high score.
    """
    def __init__(self, shape, size, color, difficulty, game_over_callback, is_mobile=False):
        pygame.init()
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.exploding = False
        self.explosion_particles = []
        self.player = Player(SCREEN_WIDTH/2, 50, shape, size, color)
        self.game_over_callback = game_over_callback
        self.is_mobile = is_mobile

        # Ajustar obstáculos según dificultad
        if difficulty == "Fácil":
            self.obstacle_gap = 150
            self.num_obstacles = 20
        elif difficulty == "Medio":
            self.obstacle_gap = 100
            self.num_obstacles = 30
        elif difficulty == "Difícil":
            self.obstacle_gap = 70
            self.num_obstacles = 40

        self.obstacles = [Obstacle(200 + i * self.obstacle_gap, SCREEN_WIDTH)
                          for i in range(self.num_obstacles)]
        self.camera_offset = 0
        self.font = pygame.font.SysFont(None, 24)

    def spawn_explosion(self, x, y):
        particles = []
        for _ in range(50):
            particles.append(Particle(x, y))
        return particles

    def handle_events(self):
        lateral_input = 0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    lateral_input = -1
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    lateral_input = 1
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_a) and lateral_input == -1:
                    lateral_input = 0
                elif event.key in (pygame.K_RIGHT, pygame.K_d) and lateral_input == 1:
                    lateral_input = 0

        # Manejo de controles táctiles para móviles
        if self.is_mobile:
            touch_input = self.handle_touch_input()
            if touch_input:
                lateral_input = touch_input

        return lateral_input

    def handle_touch_input(self):
        # Simula la entrada táctil para dispositivos móviles
        # Aquí puedes implementar la lógica para manejar toques en la pantalla
        # Por ahora, devolvemos 0 como marcador de posición
        return 0

    def update(self, dt, lateral_input):
        if not self.exploding:
            self.player.update(dt, lateral_input, G_PIXELS)
            self.camera_offset = self.player.y - 150
            player_rect = self.player.get_collision_rect(self.camera_offset)

            for obstacle in self.obstacles:
                left_rect, right_rect = obstacle.get_collision_rects(self.camera_offset)
                if player_rect.colliderect(left_rect) or player_rect.colliderect(right_rect):
                    self.player.hit_count += 1  # Incrementar contador de golpes
                    self.player.vy = -self.player.vy * 0.8  # Rebote
                    self.player.bounce_count += 1
                    if self.player.bounce_count >= 4:
                        # Inicia la animación de explosión
                        self.explosion_particles = self.spawn_explosion(self.player.x, self.player.y)
                        self.exploding = True
                        break
        else:
            for p in self.explosion_particles:
                p.update(dt)
            self.explosion_particles = [p for p in self.explosion_particles if p.lifetime > 0]
            if not self.explosion_particles:
                self.running = False

    def draw(self):
        self.screen.fill(COLOR_SKY_BLUE)  # Fondo azul cielo
        for obstacle in self.obstacles:
            obstacle.draw(self.screen, self.camera_offset)
        if not self.exploding:
            self.player.draw(self.screen, self.camera_offset)
        for particle in self.explosion_particles:
            particle.draw(self.screen, self.camera_offset)
        score = int(self.player.y)
        score_surf = self.font.render(f"Distancia: {score}", True, COLOR_BLACK)
        self.screen.blit(score_surf, (10, 10))

    def get_frame(self):
        # Convertir la superficie de Pygame a una imagen PIL
        frame = pygame.surfarray.array3d(self.screen)
        frame = frame.transpose([1, 0, 2])
        image = Image.fromarray(frame)
        return image

    async def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            lateral_input = self.handle_events()
            self.update(dt, lateral_input)
            self.draw()
            yield self.get_frame()
        # Al finalizar, actualiza el high score
        final_score = int(self.player.y)
        current_high = load_high_score()
        if final_score > current_high:
            save_high_score(final_score)
            current_high = final_score
        # Muestra mensaje de Game Over durante 2 segundos
        end_time = pygame.time.get_ticks()
        while pygame.time.get_ticks() - end_time < 2000:
            self.screen.fill(COLOR_BLACK)
            end_font = pygame.font.SysFont(None, 36)
            message = end_font.render(f"Game Over! Score: {final_score} | High Score: {current_high}", True, COLOR_WHITE)
            self.screen.blit(message, (20, SCREEN_HEIGHT // 2))
            yield self.get_frame()
        self.game_over_callback()
        pygame.quit()

async def run_game(shape, size, color, difficulty, game_over_callback, is_mobile=False):
    game = Game(shape, size, color, difficulty, game_over_callback, is_mobile)
    async for frame in game.run():
        yield frame

# ========================
# Interfaz Flet - Menú Principal
# ========================
async def main(page: ft.Page):
    page.title = "Juego de Caída - Menú Principal"
    page.vertical_alignment = "center"
    page.horizontal_alignment = "center"

    # Dropdown para seleccionar la figura
    shape_dropdown = ft.Dropdown(
        label="Selecciona la figura",
        options=[
            ft.dropdown.Option("Pelota"),
            ft.dropdown.Option("Cuadrado"),
            ft.dropdown.Option("Triángulo")
        ],
        value="Pelota"
    )

    # Slider para seleccionar el tamaño
    size_slider = ft.Slider(min=10, max=50, value=30, label="Tamaño", width=300)

    # Dropdown para seleccionar el color
    color_dropdown = ft.Dropdown(
        label="Selecciona el color",
        options=[
            ft.dropdown.Option("Rojo"),
            ft.dropdown.Option("Verde"),
            ft.dropdown.Option("Azul"),
            ft.dropdown.Option("Amarillo"),
            ft.dropdown.Option("Blanco")
        ],
        value="Rojo"
    )

    # Dropdown para seleccionar la dificultad
    difficulty_dropdown = ft.Dropdown(
        label="Dificultad",
        options=[
            ft.dropdown.Option("Fácil"),
            ft.dropdown.Option("Medio"),
            ft.dropdown.Option("Difícil")
        ],
        value="Medio"
    )

    # Dropdown para seleccionar el método de control en móvil
    control_dropdown = ft.Dropdown(
        label="Control en Móvil",
        options=[
            ft.dropdown.Option("Giroscopio"),
            ft.dropdown.Option("Touch"),
            ft.dropdown.Option("Teclas")
        ],
        value="Touch"
    )

    # Mostrar High Score actual
    high_score = load_high_score()
    high_score_text = ft.Text(f"High Score: {high_score}", size=20)

    # Mapeo de colores a valores RGB
    color_map = {
        "Rojo": (255, 0, 0),
        "Verde": (0, 255, 0),
        "Azul": (0, 0, 255),
        "Amarillo": (255, 255, 0),
        "Blanco": (255, 255, 255)
    }

    def update_high_score_text():
        hs = load_high_score()
        high_score_text.value = f"High Score: {hs}"
        page.update()

    async def start_game(e):
        shape = shape_dropdown.value
        size = size_slider.value
        color_choice = color_dropdown.value
        color = color_map.get(color_choice, (255, 0, 0))
        difficulty = difficulty_dropdown.value
        control_method = control_dropdown.value

        # Eliminar el menú principal y mostrar el juego
        page.controls.clear()
        game_image = ft.Image(width=SCREEN_WIDTH, height=SCREEN_HEIGHT)
        page.add(game_image)

        def game_over():
            # Volver al menú principal
            page.controls.clear()
            asyncio.create_task(main(page))

        async def update_game_frame():
            async for frame in run_game(shape, size, color, difficulty, game_over, is_mobile=(control_method != "Teclas")):
                buffer = BytesIO()
                frame.save(buffer, format="PNG")
                buffer.seek(0)
                img_str = base64.b64encode(buffer.read()).decode()
                game_image.src_base64 = img_str
                page.update()
                await asyncio.sleep(1/FPS)  # Esperar el tiempo adecuado para el próximo frame

        asyncio.ensure_future(update_game_frame())

    def reset_high_score(e):
        save_high_score(0)
        update_high_score_text()

    start_button = ft.ElevatedButton("Iniciar Juego", on_click=start_game)
    reset_button = ft.ElevatedButton("Reiniciar High Score", on_click=reset_high_score)

    page.add(
        ft.Column(
            [
                ft.Text("Menú Principal", size=30, weight="bold"),
                shape_dropdown,
                size_slider,
                color_dropdown,
                difficulty_dropdown,
                control_dropdown,
                high_score_text,
                start_button,
                reset_button
            ],
            horizontal_alignment="center",
            spacing=20
        )
    )

# ========================
# Arranque de la aplicación
# ========================
if __name__ == "__main__":
    ft.app(target=main)
