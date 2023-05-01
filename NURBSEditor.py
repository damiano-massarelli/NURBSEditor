import pygame

from pygame_gui import UIManager, UI_BUTTON_PRESSED, UI_TEXT_ENTRY_FINISHED
from pygame_gui.elements import UIButton, UITextEntryLine
from pygame_gui.windows.ui_message_window import UIMessageWindow
import pygame.gfxdraw
from functools import lru_cache

SIZE = [1280, 720]


@lru_cache(maxsize=None)
def N(i, j, t, knots):
    # Basis function
    if j == 0:
        if t >= knots[i] and t < knots[i+1]:
            return 1
        return 0
    term1 = 0
    if knots[i+j] != knots[i]:
        term1 = (t - knots[i]) / (knots[i+j] - knots[i])

    term2 = 0
    if knots[i + j + 1] != knots[i + 1]:
        term2 = (knots[i + j + 1] - t) / (knots[i + j + 1] - knots[i + 1])

    return term1 * N(i, j - 1, t, knots) + term2 * N(i + 1, j - 1, t, knots)


def S(t, degree, knots, ctrl_points):
    # Computes the NURBS at a given point
    res_x = 0
    res_y = 0
    total_weight = 0

    cached_values = []
    for i in range(len(ctrl_points)):
        # convert to tuple to make it hashable and compliant with @lru_cache
        v = N(i, degree, t, tuple(knots))
        total_weight += v * ctrl_points[i].weight
        cached_values.append(v)

    for i in range(len(ctrl_points)):
        v = cached_values[i]
        res_x += v * ctrl_points[i].x * ctrl_points[i].weight / total_weight
        res_y += v * ctrl_points[i].y * ctrl_points[i].weight / total_weight

    return (res_x, res_y)


class CtrlPoint:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.weight = 1
        self.radius = 5

    def __str__(self) -> str:
        return f"Ctrl({self.x}, {self.y}, {self.weight})"

    def __repr__(self) -> str:
        return self.__str__()


pygame.init()

pygame.display.set_caption('NURBS')
window_surface = pygame.display.set_mode(SIZE, pygame.RESIZABLE)
manager = UIManager(SIZE)

degree_entry_rect = pygame.Rect(0, 0, 75, 35)
degree_entry_rect.topright = (0, 0)
degree_entry = UITextEntryLine(degree_entry_rect, manager=manager,
                               placeholder_text="degree", anchors={"top": "top", "right": "right"})
degree_entry.set_allowed_characters("numbers")

ctrl_points_entry_rect = pygame.Rect(0, 0, 125, 35)
ctrl_points_entry_rect.topright = (0, 35)
ctrl_points_entry = UITextEntryLine(ctrl_points_entry_rect, manager=manager,
                                    placeholder_text="# ctrl points", anchors={"top": "top", "right": "right"})
ctrl_points_entry.set_allowed_characters("numbers")

knots_entry_rect = pygame.Rect(0, 0, 255, 35)
knots_entry_rect.topright = (-35, 70)
knots_entry = UITextEntryLine(knots_entry_rect, manager=manager,
                              placeholder_text="knots", anchors={"top": "top", "right": "right"})
knots_entry.set_allowed_characters([str(x) for x in range(10)] + [".", ","])

update_knots_button_rect = pygame.Rect(0, 0, 35, 30)
update_knots_button_rect.topright = (0, 72.5)
update_knots_button = UIButton(update_knots_button_rect, text=">", manager=manager, anchors={
                               "top": "top", "right": "right"})

start_button_rect = pygame.Rect(0, 0, 100, 30)
start_button_rect.topright = (0, 105)
start_button = UIButton(start_button_rect, text="Start",
                        manager=manager, anchors={"top": "top", "right": "right"})

ctrl_pt_x = UITextEntryLine(
    (0, 0, 100, 35), manager=manager, placeholder_text="x")
ctrl_pt_x.set_allowed_characters([str(x) for x in range(10)] + [".", "-"])

ctrl_pt_y = UITextEntryLine(
    (0, 35, 100, 35), manager=manager, placeholder_text="y")
ctrl_pt_y.set_allowed_characters([str(x) for x in range(10)] + [".", "-"])

ctrl_pt_w = UITextEntryLine(
    (0, 35, 100, 35), manager=manager, placeholder_text="weight")
ctrl_pt_w.set_allowed_characters([str(x) for x in range(10)] + [".", "-"])

g_knots = []
g_degree = 0
g_num_ctrl_points = 0
g_ctrl_points = []
g_camera_position = pygame.Vector2(0, 0)


def world_to_camera_space(position):
    return pygame.Vector2(position) - g_camera_position


def camera_to_world_space(position):
    return pygame.Vector2(position) + g_camera_position


g_msg_window = None


def show_invalid_input_msg(msg="invalid input entered"):
    global g_msg_window
    g_msg_window = UIMessageWindow(pygame.Rect(
        SIZE[0] / 2 - 150, 300, 300, 160), msg, manager, window_title="invalid input")


def show_ctrl_pt_data():
    ctrl_pt_x.show()
    ctrl_pt_y.show()
    ctrl_pt_w.show()


def hide_ctr_pt_data():
    ctrl_pt_x.hide()
    ctrl_pt_y.hide()
    ctrl_pt_w.hide()


def update_ctrl_pt_data(x, y, w):
    ctrl_pt_x.set_text(str(x))
    ctrl_pt_y.set_text(str(y))
    ctrl_pt_w.set_text(str(w))
    ctrl_pt_x.set_position(world_to_camera_space((x, y - 35 * 3)))
    ctrl_pt_y.set_position(world_to_camera_space((x, y - 35 * 2)))
    ctrl_pt_w.set_position(world_to_camera_space((x, y - 35)))


def set_ctrl_pt_data():
    try:
        g_ctrl_points[edited].x = float(ctrl_pt_x.get_text())
        g_ctrl_points[edited].y = float(ctrl_pt_y.get_text())
        g_ctrl_points[edited].weight = float(ctrl_pt_w.get_text())
    except:
        pass

    update_ctrl_pt_data(
        g_ctrl_points[edited].x, g_ctrl_points[edited].y, g_ctrl_points[edited].weight)


ctrl_pt_data_widgets = [ctrl_pt_x, ctrl_pt_y, ctrl_pt_w]


def has_any_ctrl_pt_data_focus():
    return ctrl_pt_x.is_focused or ctrl_pt_y.is_focused or ctrl_pt_w.is_focused


def set_default_knots():
    n_knots = g_degree + g_num_ctrl_points + 1
    knots_entry.set_text(",".join([str(x) for x in range(n_knots)]))


def start():
    global g_degree, g_num_ctrl_points, g_ctrl_points
    try:
        g_degree = int(degree_entry.get_text())
        g_num_ctrl_points = int(ctrl_points_entry.get_text())

        set_default_knots()

        g_ctrl_points = []
        for i in range(g_num_ctrl_points):
            p = CtrlPoint()
            p.x = 100 + i * 250
            p.y = 500
            g_ctrl_points.append(p)

        update_knots()
    except:
        show_invalid_input_msg()


def update_knots():
    global g_knots
    try:
        g_knots = [float(x) for x in knots_entry.get_text().split(",")]
        if len(g_knots) != g_degree + g_num_ctrl_points + 1:
            show_invalid_input_msg("invalid number of knots")
            set_default_knots()
            update_knots()
    except:
        show_invalid_input_msg("invalid knots")
        set_default_knots()
        update_knots()


def translate_camera(delta_x, delta_y):
    g_camera_position[0] -= delta_x
    g_camera_position[1] -= delta_y


def draw_grid(screen):
    base_line_color = pygame.Color(3, 3, 3)
    highlight_line_color = pygame.Color(8, 8, 8)
    bg_color = manager.ui_theme.get_colour('dark_bg')
    for x in range(-100, SIZE[0] + 100, 10):
        line_x = x - round(g_camera_position[0] % 100)
        line_color = base_line_color
        if x % 100 == 0:
            line_color = highlight_line_color
        pygame.gfxdraw.vline(screen, line_x, 0, SIZE[1], bg_color + line_color)
    for y in range(-100, SIZE[1] + 100, 10):
        line_y = y - round(g_camera_position[1] % 100)
        line_color = base_line_color
        if y % 100 == 0:
            line_color = highlight_line_color
        pygame.gfxdraw.hline(screen, 0, SIZE[0], line_y, bg_color + line_color)


def draw_spline(screen, steps=100):
    prev_ctrl_pos = None
    for p in g_ctrl_points:
        center = world_to_camera_space((p.x, p.y))
        fill_color = (0, 255, 0)
        if edited != -1 and p is g_ctrl_points[edited]:
            fill_color = (210, 255, 0)
        pygame.gfxdraw.aacircle(screen, round(
            center[0]), round(center[1]), p.radius, fill_color)
        pygame.gfxdraw.filled_circle(screen, round(
            center[0]), round(center[1]), p.radius, fill_color)
        if prev_ctrl_pos is not None:
            pygame.draw.aaline(screen, manager.ui_theme.get_colour(
                'dark_bg') + pygame.Color(20, 20, 20, 0), prev_ctrl_pos, center)
        prev_ctrl_pos = center

    if len(g_knots) < 2:
        return

    prev_spline_pos = world_to_camera_space(
        S(g_knots[g_degree], g_degree, g_knots, g_ctrl_points))
    for i in range(steps):
        # get as close as possible to 1 without reaching it
        percentage = i / (steps - 0.99999)
        t = g_knots[g_degree] * (1 - percentage) + \
            g_knots[-1 - g_degree] * percentage
        pos = world_to_camera_space(S(t, g_degree, g_knots, g_ctrl_points))
        pygame.draw.aaline(screen, (39, 213, 7), prev_spline_pos, pos)
        prev_spline_pos = pos


clock = pygame.time.Clock()
is_running = True
edited = -1
dragged = -1

hide_ctr_pt_data()

while is_running:
    time_delta = clock.tick(60)/1000.0
    pygame.display.set_caption(f"NURBS {round(1/time_delta, 2)}")
    for event in pygame.event.get():
        if event.type == pygame.QUIT or event.type == pygame.WINDOWCLOSE:
            is_running = False
        if event.type == pygame.VIDEORESIZE:
            window_surface = pygame.display.set_mode(
                (event.w, event.h), pygame.RESIZABLE)
            SIZE = [event.w, event.h]
            manager.set_window_resolution(SIZE)

        if g_msg_window is not None:
            if g_msg_window.process_event(event):
                g_msg_window = None
        if g_msg_window is not None and g_msg_window.alive():
            break

        manager.process_events(event)

        if event.type == UI_BUTTON_PRESSED:
            if event.ui_element == start_button:
                start()
            if event.ui_element == update_knots_button:
                update_knots()
        if event.type == UI_TEXT_ENTRY_FINISHED:
            if event.ui_element in ctrl_pt_data_widgets:
                set_ctrl_pt_data()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if not has_any_ctrl_pt_data_focus():
                hide_ctr_pt_data()
                edited = -1
            for (i, p) in enumerate(g_ctrl_points):
                if camera_to_world_space(pygame.Vector2(event.pos)).distance_to(pygame.Vector2(p.x, p.y)) < p.radius:
                    edited = i
                    dragged = i
                    show_ctrl_pt_data()
                    update_ctrl_pt_data(
                        g_ctrl_points[edited].x, g_ctrl_points[edited].y, g_ctrl_points[edited].weight)
        if event.type == pygame.MOUSEBUTTONUP:
            dragged = -1
        if event.type == pygame.MOUSEMOTION:
            if dragged != -1:
                world_mouse_pos = camera_to_world_space(event.pos)
                g_ctrl_points[edited].x = world_mouse_pos[0]
                g_ctrl_points[edited].y = world_mouse_pos[1]
                update_ctrl_pt_data(
                    g_ctrl_points[edited].x, g_ctrl_points[edited].y, g_ctrl_points[edited].weight)
            elif pygame.mouse.get_pressed()[0] and manager.get_focus_set() is None:
                translate_camera(event.rel[0], event.rel[1])

    manager.update(time_delta)

    window_surface.fill(manager.ui_theme.get_colour('dark_bg'))
    draw_grid(window_surface)
    draw_spline(window_surface, 100)
    manager.draw_ui(window_surface)

    pygame.display.update()
