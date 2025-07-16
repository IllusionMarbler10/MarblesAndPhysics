import pygame
import pymunk
import pymunk.pygame_util
import json # For saving and loading projects
import random
import math
import copy # For copying states in undo/redo history
import colorsys # Import colorsys for color conversions
import pygame_gui 
from pygame_gui.windows import UIMessageWindow # Import UIMessageWindow from windows
import os # For file system operations
import datetime # For logging timestamps
import traceback # For logging full tracebacks on errors

# --- Initial Constants ---
initial_WIDTH, initial_HEIGHT = 1200, 800
TOOLBAR_WIDTH = 200
TOP_BAR_HEIGHT = 50
SPACE_COLOR = (20, 20, 20, 255) # Initial background color (now with alpha)
LINE_COLOR = (255, 255, 255, 255) # Color for drawing lines (e.g., when creating shapes)
STATIC_BODY_COLOR = (100, 100, 100, 255) # Static body color (opaque by default)
SELECTED_OUTLINE_COLOR = (255, 255, 0, 255) # Color of the selected object outline
JOINT_COLOR = (0, 200, 255, 255) # Color for drawing joints (light blue)
TRAIL_COLOR = (255, 0, 0, 255) # Color for drawing trails (red)
FPS = 60

# --- PYMUNK GLOBAL / CONFIGURATION CONSTANTS ---
DEFAULT_DENSITY = 1.0
GRAVITY_MULTIPLIER = 1.0 # New: Multiplier for gravity strength

# --- Global Variables for dimensions (will be updated) ---
WIDTH, HEIGHT = initial_WIDTH, initial_HEIGHT

# --- Pygame Initialization ---
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
# Updated: Set window caption with program name and version
pygame.display.set_caption("Marbles & Physics v0.1.0 alpha")
clock = pygame.time.Clock()

icon_image = pygame.image.load('MarbPhysIcon2.png') 

pygame.display.set_icon(icon_image)

# --- Camera Variables (Globalized for clarity and to prevent SyntaxError) ---
# camera_offset stores the translation of the camera in world coordinates
camera_offset = pymunk.Vec2d(0, 0)
# camera_zoom stores the current zoom level (1.0 is no zoom)
camera_zoom = 1.0
mouse_camera_start_pos = None # Used to track mouse position when starting a pan
is_panning = False # Flag to indicate if the camera is currently being panned

# --- Simulation and Tool Control Variables (Globalized for clarity) ---
simulation_running = False # Simulation starts paused
# 'select' is now an an explicit tool for selection box. None means pan/default interaction.
active_tool = None # 'select', 'box', 'circle', 'drag', 'move', 'rotate', 'hinge', 'spring' 

# --- Variables for Interactive Object Drawing (Globalized for clarity) ---
drawing = False
start_pos = None
end_pos = None
min_dim = 10 # Minimum dimension to create objects
# Variables for transformations
initial_angle_at_click = None
initial_mouse_angle = None
initial_radius_at_click = None
initial_dims_at_click = None # For boxes

# Variables for joint creation (Globalized for clarity)
joint_anchor_body_1 = None
joint_anchor_pos_1 = None # In Pymunk coordinates
joint_message_shown = False # Flag to control joint creation messages

# --- Variables for Object Selection (Globalized for clarity) ---
selected_bodies = set() # Use a set for multiple selection
selected_constraints = set() # New: for selected joints/constraints
mouse_joint = None # For dragging objects (con la herramienta 'drag')
dragged_body = None # The body being dragged (con la herramienta 'move')
drag_box_selection = False # Indicates if a selection box is being used
drag_box_start_pos = None # Start point of the selection box (Pygame coords)

# --- Trails variables (Globalized for clarity) ---
show_trails = False
trails_data = {} # Dictionary to store trails: {body: [(x,y), (x,y), ...]}
MAX_TRAIL_LENGTH = 100 # Maximum number of points in a trail

# --- Undo/Redo History (Globalized for clarity) ---
history = []
history_index = -1
MAX_HISTORY = 50

# --- Clipboard for Copy/Paste ---
clipboard_data = None # Stores serialized data for copy/paste

# --- UI Layout Constants ---
BUTTON_HEIGHT = 40
BUTTON_SPACING = 10
BUTTON_X_MARGIN = 10 # Horizontal margin for buttons
BUTTON_Y_OFFSET_TOP_TOOLS = 20 # Offset for the first tool button from the top of the left panel
# TOOL_BUTTON_COUNT updated to reflect the removal of "Generate Trails"
TOOL_BUTTON_COUNT = 8 # Select, Drag, Move, Rotate, Box, Circle, Hinge, Spring

# Calculated height for the tool buttons block
TOOLS_BLOCK_HEIGHT = BUTTON_Y_OFFSET_TOP_TOOLS + (BUTTON_HEIGHT * TOOL_BUTTON_COUNT) + (BUTTON_SPACING * (TOOL_BUTTON_COUNT - 1)) + BUTTON_SPACING # Extra spacing at the end

# SETTINGS_BUTTON_COUNT now only for buttons NOT in the left tools panel
# No separate bottom panel with these buttons, so adjust to 0 or remove.
SETTINGS_BUTTON_COUNT = 0 
SETTINGS_BLOCK_HEIGHT = 0 # No separate bottom settings panel

# --- Collision Filtering Categories ---
# Define collision categories for objects
COLLIDABLE_CATEGORY = 0b1 # Objects in this category can collide
NON_COLLIDABLE_CATEGORY = 0b10 # Objects in this category do not collide with COLLIDABLE_CATEGORY

# --- Logging Setup ---
LOG_FILE_NAME = "LOGFILE.txt"
def log_message(message, level="INFO"):
    """Logs a message to the console and a file with a timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    with open(LOG_FILE_NAME, "a") as f:
        f.write(log_entry + "\n")

# --- Color Conversion Functions ---
def rgb_to_hex(rgb_tuple):
    """Converts an RGB (or RGBA) tuple to a hex string."""
    r, g, b = max(0, min(255, int(rgb_tuple[0]))), \
              max(0, min(255, int(rgb_tuple[1]))), \
              max(0, min(rgb_tuple[2], 255)) 
    return f"#{r:02X}{g:02X}{b:02X}"

def hex_to_rgb(hex_code):
    """Converts a hex string to an RGB tuple."""
    hex_code = hex_code.lstrip('#')
    if len(hex_code) != 6:
        raise ValueError("Hex code must be 6 characters (RRGGBB).")
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def hsv_to_rgb_tuple(h, s, v, a):
    """Converts HSV and Alpha values to an RGBA tuple (0-255)."""
    h = max(0, min(360, h))
    s = max(0, min(100, s))
    v = max(0, min(100, v))
    a = max(0, min(255, a))
    
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s / 100.0, v / 100.0)
    return (int(r * 255), int(g * 255), int(b * 255), int(a))

def rgb_to_hsv_tuple(rgb_tuple):
    """Converts an RGBA tuple to an HSV and Alpha tuple."""
    if len(rgb_tuple) < 4:
        rgb_tuple = rgb_tuple + (255,) # Add default alpha if missing
    r, g, b = rgb_tuple[0] / 255.0, rgb_tuple[1] / 255.0, rgb_tuple[2] / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    alpha = rgb_tuple[3]
    return (int(h * 360), int(s * 100), int(v * 100), int(alpha))


# --- GameUI Class ---
class GameUI:
    def __init__(self, resolution):
        self.WIDTH, self.HEIGHT = resolution
        self.TOOLBAR_WIDTH = 200
        self.TOP_BAR_HEIGHT = 50
        self.PROPERTIES_PANEL_WIDTH = 250 # Width of the properties panel
        
        self.manager = None 
        self.active_message_window = None

        # Callbacks are managed as direct attributes
        self.on_play_pause_pressed_callback = None
        self.on_new_scene_pressed_callback = None
        self.on_save_pressed_callback = None
        self.on_load_pressed_callback = None
        self.on_tool_selected_callback = None
        self.on_delete_callback = None
        self.on_undo_callback = None
        self.on_redo_callback = None
        self.on_generate_trails_pressed_callback = None # Kept for consistency, but button removed
        self.on_help_pressed_callback = None 
        self.on_credits_pressed_callback = None # New: Callback for credits button
        
        self.rebuild_all_ui_elements() 

    def rebuild_all_ui_elements(self):
        # Create a new UIManager instance, which implicitly cleans up everything prior
        self.manager = pygame_gui.UIManager((self.WIDTH, self.HEIGHT), 'data/themes/theme.json')
        self._create_ui_elements() 


    def _create_ui_elements(self):
        # This method ONLY creates elements; it assumes self.manager is already set.
        # This prevents duplicate element issues.

        # --- Top Panel ---
        self.top_panel = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(0, 0, self.WIDTH, self.TOP_BAR_HEIGHT),
                                                      manager=self.manager,
                                                      object_id="#top_panel")

        self.play_pause_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 5, 100, 40),
                                                              text="Resume", 
                                                              manager=self.manager,
                                                              container=self.top_panel,
                                                              object_id="#play_pause_button")

        self.new_scene_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(120, 5, 100, 40),
                                                             text="New",
                                                             manager=self.manager,
                                                             container=self.top_panel,
                                                             object_id="#new_scene_button")

        self.save_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(230, 5, 100, 40),
                                                        text="Save",
                                                        manager=self.manager,
                                                        container=self.top_panel,
                                                        object_id="#save_button")

        self.load_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(340, 5, 100, 40),
                                                        text="Load",
                                                        manager=self.manager,
                                                        container=self.top_panel,
                                                        object_id="#load_button")
        
        # Undo/Redo buttons in the top panel
        self.undo_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(450, 5, 85, BUTTON_HEIGHT), # After "Load"
            text="Undo",
            manager=self.manager,
            container=self.top_panel,
            object_id="#undo_button"
        )
        self.redo_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(450 + 85 + BUTTON_SPACING, 5, 85, BUTTON_HEIGHT), # After "Undo"
            text="Redo",
            manager=self.manager,
            container=self.top_panel,
            object_id="#redo_button"
        )

        # Help button in the top panel
        self.help_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(450 + 85 + BUTTON_SPACING + 85 + BUTTON_SPACING, 5, 85, BUTTON_HEIGHT), # After "Redo"
            text="Help",
            manager=self.manager,
            container=self.top_panel,
            object_id="#help_button"
        )

        # Credits button in the top panel
        self.credits_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(450 + 85 + BUTTON_SPACING + 85 + BUTTON_SPACING + 85 + BUTTON_SPACING, 5, 85, BUTTON_HEIGHT), # After "Help"
            text="Credits",
            manager=self.manager,
            container=self.top_panel,
            object_id="#credits_button"
        )

        # Program Name and Version Label (No longer using set_text_wrap_width or set_text_horiz_alignment)
        self.program_info_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(self.WIDTH - 250, 5, 240, BUTTON_HEIGHT), # Adjusted position for top-right
            text="Marbles & Physics v0.1.0 alpha",
            manager=self.manager,
            container=self.top_panel,
            object_id="#program_info_label"
        )


        # --- Main Left Panel (Reinitializing its content) ---
        self.main_left_panel = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(0, self.TOP_BAR_HEIGHT, self.TOOLBAR_WIDTH, self.HEIGHT - self.TOP_BAR_HEIGHT),
                                                           manager=self.manager,
                                                           object_id="#main_left_panel")

        # --- Tool Buttons directly in main_left_panel ---
        button_y_offset_current = BUTTON_Y_OFFSET_TOP_TOOLS

        self.select_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                         text="Select",
                                                         manager=self.manager,
                                                         container=self.main_left_panel,
                                                         object_id="#select_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.drag_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                         text="Drag",
                                                         manager=self.manager,
                                                         container=self.main_left_panel,
                                                         object_id="#drag_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.move_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                         text="Move",
                                                         manager=self.manager,
                                                         container=self.main_left_panel,
                                                         object_id="#move_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.rotate_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                           text="Rotate",
                                                           manager=self.manager,
                                                           container=self.main_left_panel,
                                                           object_id="#rotate_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.create_box_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                               text="Create Box",
                                                               manager=self.manager,
                                                               container=self.main_left_panel,
                                                               object_id="#create_box_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.create_circle_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                                  text="Create Circle",
                                                                  manager=self.manager,
                                                                  container=self.main_left_panel,
                                                                  object_id="#create_circle_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.hinge_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                         text="Hinge",
                                                         manager=self.manager,
                                                         container=self.main_left_panel,
                                                         object_id="#hinge_button")
        button_y_offset_current += BUTTON_HEIGHT + BUTTON_SPACING

        self.spring_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(BUTTON_X_MARGIN, button_y_offset_current, self.TOOLBAR_WIDTH - 2 * BUTTON_X_MARGIN, BUTTON_HEIGHT),
                                                           text="Spring",
                                                           manager=self.manager,
                                                           container=self.main_left_panel,
                                                           object_id="#spring_button")
        
        # --- Properties Panel (Initially hidden) ---
        self.properties_panel = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(self.WIDTH - self.PROPERTIES_PANEL_WIDTH, self.TOP_BAR_HEIGHT, self.PROPERTIES_PANEL_WIDTH, self.HEIGHT - self.TOP_BAR_HEIGHT),
            manager=self.manager,
            object_id="#properties_panel"
        )
        self.properties_panel.hide() # Start hidden

        # Properties Panel Elements - Object Properties
        panel_x_margin = 10
        panel_width_for_elements = self.PROPERTIES_PANEL_WIDTH - 2 * panel_x_margin
        current_y_offset = 10

        # Density
        self.density_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
                                    text="Density:", manager=self.manager, container=self.properties_panel)
        current_y_offset += 25
        self.density_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=DEFAULT_DENSITY, value_range=(0.1, 10.0), manager=self.manager, container=self.properties_panel,
            object_id="#density_slider"
        )
        current_y_offset += 30

        # Friction
        self.friction_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
                                    text="Friction:", manager=self.manager, container=self.properties_panel)
        current_y_offset += 25
        self.friction_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=0.5, value_range=(0.0, 1.0), manager=self.manager, container=self.properties_panel,
            object_id="#friction_slider"
        )
        current_y_offset += 30

        # Elasticity (Restitution)
        self.elasticity_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
                                    text="Restitution:", manager=self.manager, container=self.properties_panel)
        current_y_offset += 25
        self.elasticity_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=0.8, value_range=(0.0, 1.0), manager=self.manager, container=self.properties_panel,
            object_id="#elasticity_slider"
        )
        current_y_offset += 30

        # Object Color Sliders and Random Color Button
        self.object_color_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
                                    text="Object Color (RGBA):", manager=self.manager, container=self.properties_panel)
        current_y_offset += 25
        self.color_r_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=100, value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#color_r_slider"
        )
        current_y_offset += 25
        self.color_g_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=150, value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#color_g_slider"
        )
        current_y_offset += 25
        self.color_b_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=200, value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#color_b_slider"
        )
        current_y_offset += 25
        self.color_a_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, 20),
            start_value=255, value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#color_a_slider"
        )
        current_y_offset += 30
        self.random_color_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, BUTTON_HEIGHT),
            text="Random Object Color", manager=self.manager, container=self.properties_panel,
            object_id="#random_color_button"
        )
        current_y_offset += BUTTON_HEIGHT + BUTTON_SPACING

        # Static/Dynamic Toggle
        self.static_dynamic_toggle = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, BUTTON_HEIGHT),
            text="Dynamic", manager=self.manager, container=self.properties_panel,
            object_id="#static_dynamic_toggle"
        )
        current_y_offset += BUTTON_HEIGHT + BUTTON_SPACING

        # Delete Button
        self.delete_object_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset, panel_width_for_elements, BUTTON_HEIGHT),
            text="Delete Object(s)", manager=self.manager, container=self.properties_panel,
            object_id="#delete_object_button"
        )

        # Properties Panel Elements - Background/Space Properties (initially hidden)
        current_y_offset_space = 10 # Start from top of panel for space properties

        self.background_color_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
                                    text="Background Color (RGBA):", manager=self.manager, container=self.properties_panel)
        current_y_offset_space += 25
        self.background_color_r_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
            start_value=SPACE_COLOR[0], value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#background_color_r_slider"
        )
        current_y_offset_space += 25
        self.background_color_g_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
            start_value=SPACE_COLOR[1], value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#background_color_g_slider"
        )
        current_y_offset_space += 25
        self.background_color_b_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
            start_value=SPACE_COLOR[2], value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#background_color_b_slider"
        )
        current_y_offset_space += 25
        self.background_color_a_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
            start_value=SPACE_COLOR[3], value_range=(0, 255), manager=self.manager, container=self.properties_panel,
            object_id="#color_a_slider"
        )
        current_y_offset_space += 30
        self.random_background_color_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, BUTTON_HEIGHT),
            text="Random Background Color", manager=self.manager, container=self.properties_panel,
            object_id="#random_background_color_button"
        )
        current_y_offset_space += BUTTON_HEIGHT + BUTTON_SPACING

        # Gravity Slider
        self.gravity_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
                                    text="Gravity Multiplier:", manager=self.manager, container=self.properties_panel)
        current_y_offset_space += 25
        self.gravity_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x_margin, current_y_offset_space, panel_width_for_elements, 20),
            start_value=GRAVITY_MULTIPLIER, value_range=(-1.0, 1.0), manager=self.manager, container=self.properties_panel,
            object_id="#gravity_slider"
        )
        current_y_offset_space += 30

        # Group all space properties elements for easy visibility toggling
        self.space_property_elements = [
            self.background_color_label, self.background_color_r_slider, self.background_color_g_slider,
            self.background_color_b_slider, self.background_color_a_slider, self.random_background_color_button,
            self.gravity_label, self.gravity_slider
        ]

        # Group all object properties elements for easy visibility toggling
        self.object_property_elements = [
            self.density_label, self.density_slider, self.friction_label, self.friction_slider,
            self.elasticity_label, self.elasticity_slider, self.object_color_label, self.color_r_slider,
            self.color_g_slider, self.color_b_slider, self.color_a_slider, self.random_color_button,
            self.static_dynamic_toggle, self.delete_object_button
        ]

        # Hide all space properties elements initially
        for element in self.space_property_elements:
            element.hide()
        
    def process_event(self, event):
        # Dismiss message window if user interacts with it
        if event.type == pygame_gui.UI_WINDOW_CLOSE:
            if self.active_message_window and event.ui_element == self.active_message_window:
                self.active_message_window.kill()
                self.active_message_window = None
        
        # Pass event to manager
        self.manager.process_events(event) # This call updates the UI state and generates UI events

        # Handle events for properties panel elements
        if self.properties_panel.visible:
            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                # Object properties sliders
                if event.ui_element == self.density_slider:
                    apply_properties_to_selected_object('density', event.value)
                elif event.ui_element == self.friction_slider:
                    apply_properties_to_selected_object('friction', event.value)
                elif event.ui_element == self.elasticity_slider:
                    apply_properties_to_selected_object('elasticity', event.value)
                elif event.ui_element in [self.color_r_slider, self.color_g_slider, self.color_b_slider, self.color_a_slider]:
                    r = self.color_r_slider.get_current_value()
                    g = self.color_g_slider.get_current_value()
                    b = self.color_b_slider.get_current_value()
                    a = self.color_a_slider.get_current_value()
                    apply_properties_to_selected_object('color', (int(r), int(g), int(b), int(a)))
                # Background/Space properties sliders
                elif event.ui_element in [self.background_color_r_slider, self.background_color_g_slider, self.background_color_b_slider, self.background_color_a_slider]:
                    r = self.background_color_r_slider.get_current_value()
                    g = self.background_color_g_slider.get_current_value()
                    b = self.background_color_b_slider.get_current_value()
                    a = self.background_color_a_slider.get_current_value()
                    set_background_color((int(r), int(g), int(b), int(a)))
                elif event.ui_element == self.gravity_slider:
                    set_gravity_multiplier(event.value)

            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                # Object properties buttons
                if event.ui_element == self.random_color_button:
                    apply_properties_to_selected_object('random_color', True)
                elif event.ui_element == self.static_dynamic_toggle:
                    toggle_static_dynamic_for_selected()
                elif event.ui_element == self.delete_object_button:
                    self.on_delete_callback()
                # Background/Space properties buttons
                elif event.ui_element == self.random_background_color_button:
                    set_background_color("random")

        # Handle events for top panel and left panel buttons
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.play_pause_button:
                self.on_play_pause_pressed_callback()
            elif event.ui_element == self.new_scene_button:
                self.on_new_scene_pressed_callback()
            elif event.ui_element == self.save_button:
                self.on_save_pressed_callback()
            elif event.ui_element == self.load_button:
                self.on_load_pressed_callback()
            elif event.ui_element == self.select_button:
                self.on_tool_selected_callback('select')
            elif event.ui_element == self.drag_button:
                self.on_tool_selected_callback('drag')
            elif event.ui_element == self.move_button:
                self.on_tool_selected_callback('move')
            elif event.ui_element == self.rotate_button:
                self.on_tool_selected_callback('rotate')
            elif event.ui_element == self.create_box_button:
                self.on_tool_selected_callback('box')
            elif event.ui_element == self.create_circle_button:
                self.on_tool_selected_callback('circle')
            elif event.ui_element == self.hinge_button:
                self.on_tool_selected_callback('hinge')
            elif event.ui_element == self.spring_button:
                self.on_tool_selected_callback('spring')
            elif event.ui_element == self.undo_button:
                self.on_undo_callback()
            elif event.ui_element == self.redo_button:
                self.on_redo_callback()
            elif event.ui_element == self.help_button: 
                self.on_help_pressed_callback()
            elif event.ui_element == self.credits_button: # New: Credits button handler
                self.on_credits_pressed_callback()
            return True # If any button was pressed, it was consumed by UI

        return False # Event not consumed by UI (e.g., mouse motion in simulation area)

    def update(self, time_delta):
        self.manager.update(time_delta)
        # Update program info label position on window resize
        # The position is relative to its container (top_panel), so no need to adjust for WIDTH here.
        # It's already set to (self.WIDTH - 250, 5) which is relative to the top_panel's width.
        # self.program_info_label.set_relative_position(pygame.Rect(self.WIDTH - 250, 5, 240, BUTTON_HEIGHT).topleft)


    def draw(self, screen):
        self.manager.draw_ui(screen)

    def set_play_pause_text(self, text):
        self.play_pause_button.set_text(text)

    def update_undo_redo_buttons(self, history_index, history_length):
        self.undo_button.enable() if history_index > 0 else self.undo_button.disable()
        self.redo_button.enable() if history_index < history_length - 1 else self.redo_button.disable()

    def update_properties_panel(self, selected_bodies, selected_joints, default_density, mode='none'):
        # Update main left panel position (it's fixed)
        self.main_left_panel.show() 
        
        if mode == 'object' and selected_bodies:
            self.properties_panel.show()
            # Show object properties, hide space properties
            for element in self.object_property_elements:
                element.show()
            for element in self.space_property_elements:
                element.hide()

            # Calculate average/representative values for selected objects
            avg_density = sum(s.density for body in selected_bodies for s in body.shapes) / len([s for body in selected_bodies for s in body.shapes])
            avg_friction = sum(s.friction for body in selected_bodies for s in body.shapes) / len([s for body in selected_bodies for s in body.shapes])
            avg_elasticity = sum(s.elasticity for body in selected_bodies for s in body.shapes) / len([s for body in selected_bodies for s in body.shapes])
            
            # For color, take the _original_dynamic_color of the first selected body (dynamic or static)
            first_selected_body_color = (100, 150, 200, 255) # Default color
            for body in selected_bodies:
                if body.shapes:
                    first_shape = list(body.shapes)[0]
                    if hasattr(first_shape, '_original_dynamic_color'):
                        first_selected_body_color = first_shape._original_dynamic_color
                    else:
                        first_selected_body_color = first_shape.color # Fallback
                    break 

            self.density_slider.set_current_value(avg_density)
            self.friction_slider.set_current_value(avg_friction)
            self.elasticity_slider.set_current_value(avg_elasticity)
            self.color_r_slider.set_current_value(first_selected_body_color[0])
            self.color_g_slider.set_current_value(first_selected_body_color[1])
            self.color_b_slider.set_current_value(first_selected_body_color[2])
            self.color_a_slider.set_current_value(first_selected_body_color[3])

            # Update static/dynamic toggle text
            is_all_static = all(body.body_type == pymunk.Body.STATIC for body in selected_bodies)
            is_all_dynamic = all(body.body_type == pymunk.Body.DYNAMIC for body in selected_bodies)
            if is_all_static:
                self.static_dynamic_toggle.set_text("Static")
            elif is_all_dynamic:
                self.static_dynamic_toggle.set_text("Dynamic")
            else:
                self.static_dynamic_toggle.set_text("Mixed (Stat/Dyn)") # Mixed state

        elif mode == 'space':
            self.properties_panel.show()
            # Hide object properties, show space properties
            for element in self.object_property_elements:
                element.hide()
            for element in self.space_property_elements:
                element.show()
            
            # Update background color sliders
            self.background_color_r_slider.set_current_value(SPACE_COLOR[0])
            self.background_color_g_slider.set_current_value(SPACE_COLOR[1])
            self.background_color_b_slider.set_current_value(SPACE_COLOR[2])
            self.background_color_a_slider.set_current_value(SPACE_COLOR[3])
            
            # Update gravity slider
            self.gravity_slider.set_current_value(GRAVITY_MULTIPLIER)

        else: # mode == 'none' or no selection
            self.properties_panel.hide()
            # Hide all elements within the panel
            for element in self.object_property_elements:
                element.hide()
            for element in self.space_property_elements:
                element.hide()
        
    def show_message(self, title, message):
        # Close existing message window if any
        if self.active_message_window:
            self.active_message_window.kill()
            self.active_message_window = None

        self.active_message_window = UIMessageWindow(
            rect=pygame.Rect((self.WIDTH / 2) - 200, (self.HEIGHT / 2) - 75, 400, 150),
            html_message=f"<font color='#FFFFFF'>{message}</font>",
            manager=self.manager,
            window_title=title
        )

    def show_help_dialog(self):
        help_message = """
        <b>Keyboard Shortcuts:</b><br>
        Spacebar: Play/Pause Simulation<br>
        Ctrl + Z: Undo<br>
        Ctrl + Y: Redo<br>
        Ctrl + C: Copy Selected Objects<br>
        Ctrl + V: Paste Objects<br>
        Delete/Backspace: Delete Selected Objects<br>
        Mouse Wheel Up/Down: Zoom In/Out<br>
        Left Click (empty space, no tool): Pan Camera<br>
        Right Click (empty space): Show Space Properties
        """
        self.show_message("Help - Keyboard Shortcuts", help_message)

    def show_credits_dialog(self):
        credits_message = """
        <b>Marbles And Physics</b><br>
        Version 0.1.0 alpha<br>
        Author: Marcos Perez<br>
        <br>
        <font color='#FF0000'>Warning: This is an alpha state of the program so you will experience some bugs and errors.</font><br>
        <br>
        Thanks to my contributors<br>
        Who helped me to develop my program:<br>
        <br>
        IllusionMP<br>
        [and more of my contributors will be listed here]<br>
        <br>
        And all of my Alpha/Beta Testers!<br>
        <br>
        Join the Discord server: https://www.google.com<br>
        <br>
        Found a bug? Send us an issue with a screenshot and the Logfile.txt on our Github Repository!<br>
        https://www.google.com
        <br>
        """
        self.show_message("Credits", credits_message)

    # Simplified save/load methods
    def show_save_project_dialog(self):
        # Directly call perform_save_project with a fixed name
        self._perform_save_project("autosave")

    def show_load_project_dialog(self):
        # Directly call perform_load_project with a fixed name
        self._perform_load_project("autosave")

    def _perform_save_project(self, project_name):
        file_path = f"{project_name}.json" # Fixed file name

        try:
            with open(file_path, "w") as f:
                json.dump(serialize_space(), f, indent=4)
            self.show_message("Saved", f"Project '{project_name}' saved successfully.")
            log_message(f"Project '{project_name}' saved successfully.")
        except Exception as e:
            self.show_message("Error", f"Error saving project '{project_name}': {e}")
            log_message(f"Error saving project '{project_name}': {e}", level="ERROR")

    def _perform_load_project(self, project_name):
        file_path = f"{project_name}.json" # Fixed file name

        try:
            with open(file_path, "r") as f:
                loaded_state = json.load(f)
                record_history() # Record current state before loading a new one
                deserialize_space(loaded_state)
            self.show_message("Loaded", f"Project '{project_name}' loaded successfully.")
            log_message(f"Project '{project_name}' loaded successfully.")
        except FileNotFoundError:
            self.show_message("Error", f"Project file '{project_name}' not found.")
            log_message(f"Error: Project file '{project_name}' notidded not found.", level="ERROR")
        except Exception as e:
            self.show_message("Error", f"Error loading project '{project_name}': {e}")
            log_message(f"Error loading project '{project_name}': {e}", level="ERROR")


# --- Pymunk to Pygame Coordinate Conversion Functions (STANDARD) ---
# Pymunk has Y-axis up, Pygame has Y-axis down.
# The Y-axis needs to be inverted for display.
def to_pygame_coords(p):
    """
    Converts a Pymunk coordinate (Vec2d) to a Pygame tuple (x, y),
    applying camera offset and zoom.
    """
    # Ensure zoom is not zero to prevent division by zero
    if camera_zoom == 0:
        return 0, 0 # Or handle as an error/default

    # Ensure coordinates are finite numbers before casting to int
    converted_x = (p.x + camera_offset.x) * camera_zoom
    converted_y = (HEIGHT - (p.y + camera_offset.y) * camera_zoom)

    if not (math.isfinite(converted_x) and math.isfinite(converted_y)):
        return 0, 0 # Return a safe default if conversion results in NaN/Infinity

    return int(converted_x), int(converted_y)

def to_pymunk_coords(p_x, p_y):
    """
    Converts a Pygame coordinate (x, y) to a Pymunk coordinate (Vec2d),
    reversing camera offset and zoom.
    """
    # Ensure zoom is not zero to prevent division by zero
    if camera_zoom == 0:
        return pymunk.Vec2d(0, 0) # Or handle as an error/default

    return pymunk.Vec2d(p_x / camera_zoom - camera_offset.x, (HEIGHT - p_y) / camera_zoom - camera_offset.y)

# --- Pymunk Initialization ---
space = pymunk.Space()
# GRAVITY: In Pymunk, a negative Y value means "down" for falling objects.
space.gravity = (0, -981 * GRAVITY_MULTIPLIER) # Apply multiplier here

# No default ground body or shape anymore

# DrawOptions will no longer be used directly for rendering Pymunk shapes
# but is kept if needed for other future debugging features.
draw_options = pymunk.pygame_util.DrawOptions(screen)
draw_options.draw_body_bb = False
draw_options.draw_space_boundaries = False

# Global counter for unique body IDs
next_body_id_counter = 0

def get_next_body_id():
    """Returns a unique ID for a new body."""
    global next_body_id_counter
    current_id = next_body_id_counter
    next_body_id_counter += 1
    return f"body_{current_id}"

# --- Initialize the GameUI instance BEFORE any calls to record_history() or UI updates ---
game_ui = GameUI(resolution=(WIDTH, HEIGHT))

# Font for FPS counter
fps_font = pygame.font.Font(None, 24) # Default font, size 24

def record_history():
    """Saves the current simulation state to history."""
    global history, history_index

    # Remove future states if a new action is performed after an undo
    if history_index < len(history) - 1:
        history = history[:history_index + 1]

    current_state = serialize_space()
    # Use deepcopy to ensure that the saved state is completely independent
    # of the current live simulation objects.
    history.append(copy.deepcopy(current_state))
    if len(history) > MAX_HISTORY:
        history.pop(0) # Remove the oldest state
    history_index = len(history) - 1
    game_ui.update_undo_redo_buttons(history_index, len(history))
    log_message(f"State recorded to history. History size: {len(history)}")

def load_history_state(index):
    """Loads a specific state from history."""
    global simulation_running, SPACE_COLOR, selected_bodies, selected_constraints, active_tool, trails_data, camera_offset, camera_zoom, \
           drawing, start_pos, end_pos, initial_angle_at_click, initial_mouse_angle, initial_radius_at_click, initial_dims_at_click, \
           joint_anchor_body_1, joint_anchor_pos_1, mouse_joint, dragged_body, drag_box_selection, drag_box_start_pos, \
           is_panning, mouse_camera_start_pos, joint_message_shown, GRAVITY_MULTIPLIER, next_body_id_counter

    if 0 <= index < len(history):
        state = history[index]
        deserialize_space(state)
        # Ensure that background color and simulation state are also restored
        if 'background_color' in state:
            global SPACE_COLOR
            SPACE_COLOR = tuple(state['background_color'])
        if 'simulation_running' in state:
            simulation_running = state['simulation_running']
            game_ui.set_play_pause_text("Resume" if not simulation_running else "Pause")
        
        # Restore gravity multiplier and apply it
        if 'gravity_multiplier' in state:
            GRAVITY_MULTIPLIER = state['gravity_multiplier']
            space.gravity = (0, -981 * GRAVITY_MULTIPLIER)
        else:
            GRAVITY_MULTIPLIER = 1.0 # Default
            space.gravity = (0, -981 * GRAVITY_MULTIPLIER) # Apply default

        # When loading the state, the selection might be inconsistent. Deselect everything.
        selected_bodies.clear()
        selected_constraints.clear()
        active_tool = None # Reset tool to default (pan)
        clear_mouse_state() # Clear any active drag/draw state
        trails_data.clear() # Clear trails as objects will be new instances
        joint_message_shown = False # Reset joint message flag

        # Restore camera state if saved
        if 'camera_offset' in state:
            camera_offset = pymunk.Vec2d(state['camera_offset'][0], state['camera_offset'][1])
        else:
            camera_offset = pymunk.Vec2d(0,0) # Default if not saved
        if 'camera_zoom' in state:
            camera_zoom = state['camera_zoom']
        else:
            camera_zoom = 1.0 # Default if not saved

        # Restore next_body_id_counter to ensure unique IDs after loading
        if 'next_body_id_counter' in state:
            next_body_id_counter = state['next_body_id_counter']
        else:
            # If not in saved state, recalculate based on existing bodies
            max_id = -1
            for body in space.bodies:
                if hasattr(body, 'body_id') and body.body_id.startswith("body_"):
                    try:
                        num_id = int(body.body_id.split("_")[1])
                        if num_id > max_id:
                            max_id = num_id
                    except ValueError:
                        pass # Ignore non-numeric or malformed IDs
            next_body_id_counter = max_id + 1 if max_id != -1 else 0


        # Update properties panel based on current selection (which is none after load)
        game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') 
        game_ui.update_undo_redo_buttons(history_index, len(history))
        log_message(f"Loaded history state at index {index}.")

# --- Pymunk Space Serialization/Deserialization Functions ---
def serialize_space():
    """Serializes the current Pymunk space state for saving or history."""
    objects_data = []
    # Map bodies to IDs for constraint referencing
    body_to_id = {}
    
    # Assign IDs to dynamic/kinematic bodies
    for body in space.bodies:
        if body == space.static_body: # Exclude space.static_body from regular object serialization
            continue
        # Ensure body has a body_id attribute
        if not hasattr(body, 'body_id'):
            body.body_id = get_next_body_id() # Assign a new ID if missing
        body_to_id[body] = body.body_id

        body_data = {
            "body_id": body.body_id, # Save the unique ID
            "position": (body.position.x, body.position.y),
            "angle": body.angle,
            "velocity": (body.velocity.x, body.velocity.y),
            "angular_velocity": body.angular_velocity,
            "body_type": "dynamic" if body.body_type == pymunk.Body.DYNAMIC else ("static" if body.body_type == pymunk.Body.STATIC else "kinematic"), # Include kinematic
            "shapes": []
        }
        for shape in body.shapes:
            shape_data = {
                "friction": shape.friction,
                "elasticity": shape.elasticity,
                "density": shape.density,
                "color": shape.color if hasattr(shape, 'color') else (100, 150, 200, 200),
                # Serialize the original dynamic color
                "original_dynamic_color": shape._original_dynamic_color if hasattr(shape, '_original_dynamic_color') else (100, 150, 200, 200),
                "collision_category": shape.filter.categories # Save collision category
            }
            if isinstance(shape, pymunk.Circle):
                shape_data["type"] = "circle"
                shape_data["radius"] = shape.radius
            elif isinstance(shape, pymunk.Poly):
                shape_data["type"] = "box"
                # To get width/height from Poly, we need to consider its vertices in local space.
                # Assuming a rectangular shape from Poly vertices:
                verts = shape.get_vertices()
                min_x = min(v.x for v in verts)
                max_x = max(v.x for v in verts)
                min_y = min(v.y for v in verts)
                max_y = max(v.y for v in verts)
                shape_data["width"] = abs(max_x - min_x)
                shape_data["height"] = abs(max_y - min_y)
            body_data["shapes"].append(shape_data)
        objects_data.append(body_data)

    constraints_data = []
    for constraint in space.constraints:
        if isinstance(constraint, pymunk.SimpleMotor):
            continue

        body_a_id = body_to_id.get(constraint.a)
        body_b_id = body_to_id.get(constraint.b)

        # If one body is space.static_body, map it to its special ID.
        if constraint.a == space.static_body: body_a_id = "static_space_body_id"
        if constraint.b == space.static_body: body_b_id = "static_space_body_id"

        # Only serialize if both bodies involved in the constraint are recognized
        if body_a_id is None or body_b_id is None:
            continue

        if isinstance(constraint, pymunk.PinJoint):
            constraints_data.append({
                "type": "PinJoint",
                "body_a_id": body_a_id,
                "body_b_id": body_b_id,
                "anchor_a": (constraint.anchor_a.x, constraint.anchor_a.y),
                "anchor_b": (constraint.anchor_b.x, constraint.anchor_b.y),
            })
        elif isinstance(constraint, pymunk.DampedSpring):
            constraints_data.append({
                "type": "DampedSpring",
                "body_a_id": body_a_id,
                "body_b_id": body_b_id,
                "anchor_a": (constraint.anchor_a.x, constraint.anchor_a.y),
                "anchor_b": (constraint.anchor_b.x, constraint.anchor_b.y),
                "rest_length": constraint.rest_length,
                "stiffness": constraint.stiffness,
                "damping": constraint.damping
            })

    return {
        "objects": objects_data,
        "constraints": constraints_data,
        "background_color": list(SPACE_COLOR),
        "simulation_running": simulation_running,
        "show_trails": show_trails,
        "camera_offset": (camera_offset.x, camera_offset.y),
        "camera_zoom": camera_zoom,
        "gravity_multiplier": GRAVITY_MULTIPLIER, # New: Save gravity multiplier
        "next_body_id_counter": next_body_id_counter # Save the counter
    }

def deserialize_space(state_data):
    """Deserializes a Pymunk space state and loads it."""
    global selected_bodies, selected_constraints, simulation_running, SPACE_COLOR, show_trails, trails_data, camera_offset, camera_zoom, GRAVITY_MULTIPLIER, next_body_id_counter

    # Remove all existing bodies and constraints
    for body in list(space.bodies): # Iterate over a copy to avoid modification issues
        if body != space.static_body: # Crucial: Do not remove space.static_body
            space.remove(body)
            for shape in list(body.shapes):
                space.remove(shape)
    for constraint in list(space.constraints):
        space.remove(constraint)
    
    selected_bodies.clear()
    selected_constraints.clear()
    clear_mouse_state()
    trails_data.clear()

    new_bodies_list = []
    id_to_body = {}

    # The static_space_body_id is always present and doesn't need to be created.
    # It's used for mouse joints, etc.
    id_to_body["static_space_body_id"] = space.static_body 

    if 'objects' in state_data:
        for body_data in state_data['objects']:
            pos = pymunk.Vec2d(body_data["position"][0], body_data["position"][1])
            
            mass = 1
            inertia = 1 
            temp_body = pymunk.Body(mass, inertia) # Will be updated if dynamic
            temp_body.position = pos
            temp_body.angle = body_data["angle"]
            temp_body.velocity = pymunk.Vec2d(body_data["velocity"][0], body_data["velocity"][1])
            temp_body.angular_velocity = body_data["angular_velocity"]
            
            # Restore body_type
            if body_data["body_type"] == "static":
                temp_body.body_type = pymunk.Body.STATIC
                temp_body.mass = float('inf') # Static bodies have infinite mass
                temp_body.inertia = float('inf') # Static bodies have infinite inertia
            elif body_data["body_type"] == "kinematic":
                temp_body.body_type = pymunk.Body.KINEMATIC
            else: # dynamic
                temp_body.body_type = pymunk.Body.DYNAMIC

            # Restore the body_id
            temp_body.body_id = body_data.get("body_id", get_next_body_id())


            temp_shapes = [] # Store shapes temporarily to add to space together with body
            for shape_data in body_data["shapes"]:
                shape_type = shape_data["type"]
                density = shape_data.get("density", DEFAULT_DENSITY)
                color = tuple(shape_data.get("color", (100, 150, 200, 200)))
                original_dynamic_color = tuple(shape_data.get("original_dynamic_color", color)) # Retrieve original dynamic color
                collision_category = shape_data.get("collision_category", COLLIDABLE_CATEGORY) # Load collision category

                new_shape = None
                if shape_type == "circle":
                    radius = max(0.001, shape_data.get("radius", 10)) # Ensure radius is positive
                    new_shape = pymunk.Circle(temp_body, radius)
                    # Mass and inertia for dynamic bodies will be recalculated once all shapes are added to the body
                    # For a single shape body, this is effectively done here.
                    if temp_body.body_type == pymunk.Body.DYNAMIC: # Only calculate for dynamic bodies
                        temp_body.mass = max(0.001, density * math.pi * (radius ** 2))
                        temp_body.inertia = max(0.001, pymunk.moment_for_circle(temp_body.mass, 0, radius))

                elif shape_type == "box":
                    width = max(0.001, shape_data.get("width", 20)) # Ensure width is positive
                    height = max(0.001, shape_data.get("height", 20)) # Ensure height is positive
                    new_shape = pymunk.Poly.create_box(temp_body, (width, height))
                    if temp_body.body_type == pymunk.Body.DYNAMIC: # Only calculate for dynamic bodies
                        temp_body.mass = max(0.001, density * width * height)
                        temp_body.inertia = max(0.001, pymunk.moment_for_box(temp_body.mass, (width, height)))
                
                if new_shape:
                    new_shape.friction = shape_data.get("friction", 0.5)
                    new_shape.elasticity = shape_data.get("elasticity", 0.8)
                    new_shape.density = density
                    # When deserializing, apply the original_dynamic_color as the current color
                    # if the body is dynamic, otherwise apply the static color.
                    new_shape.color = original_dynamic_color if temp_body.body_type == pymunk.Body.DYNAMIC else STATIC_BODY_COLOR
                    new_shape._original_dynamic_color = original_dynamic_color # Store original dynamic color
                    new_shape.filter = pymunk.ShapeFilter(categories=collision_category) # Restore collision filter
                    temp_shapes.append(new_shape)
            
            # Add body and its shapes to the space after all shapes have been created
            if temp_shapes: # Only add body if it has shapes
                space.add(temp_body, *temp_shapes) # Add body and all its shapes
                new_bodies_list.append(temp_body)
                # Map the newly created body to its ID. This ID is an integer generated during serialization.
                id_to_body[temp_body.body_id] = temp_body # Use the actual body_id for mapping


    if 'constraints' in state_data:
        for constraint_data in state_data['constraints']:
            body_a = id_to_body.get(constraint_data["body_a_id"])
            body_b = id_to_body.get(constraint_data["body_b_id"])
            
            if body_a is not None and body_b is not None: # Ensure both bodies are found
                if constraint_data["type"] == "PinJoint":
                    anchor_a = pymunk.Vec2d(constraint_data["anchor_a"][0], constraint_data["anchor_a"][1])
                    anchor_b = pymunk.Vec2d(constraint_data["anchor_b"][0], constraint_data["anchor_b"][1])
                    pin_joint = pymunk.PinJoint(body_a, body_b, anchor_a, anchor_b)
                    space.add(pin_joint)
                    
                elif constraint_data["type"] == "DampedSpring":
                    anchor_a = pymunk.Vec2d(constraint_data["anchor_a"][0], constraint_data["anchor_a"][1])
                    anchor_b = pymunk.Vec2d(constraint_data["anchor_b"][0], constraint_data["anchor_b"][1])
                    rest_length = constraint_data["rest_length"]
                    stiffness = constraint_data["stiffness"] 
                    damping = constraint_data["damping"] 
                    spring_joint = pymunk.DampedSpring(body_a, body_b, anchor_a, anchor_b, rest_length, stiffness, damping)
                    space.add(spring_joint)

    # Restore other global states
    if 'background_color' in state_data:
        SPACE_COLOR = tuple(state_data['background_color'])
    
    if 'simulation_running' in state_data:
        simulation_running = state_data['simulation_running']
        game_ui.set_play_pause_text("Resume" if not simulation_running else "Pause")
    
    if 'show_trails' in state_data:
        show_trails = state_data['show_trails']
    
    if 'camera_offset' in state_data:
        camera_offset = pymunk.Vec2d(state_data['camera_offset'][0], state_data['camera_offset'][1])
    else:
        camera_offset = pymunk.Vec2d(0,0)
    
    if 'camera_zoom' in state_data:
        camera_zoom = state_data['camera_zoom']
    else:
        camera_zoom = 1.0
    
    # Restore gravity multiplier and apply it
    if 'gravity_multiplier' in state_data:
        GRAVITY_MULTIPLIER = state_data['gravity_multiplier']
        space.gravity = (0, -981 * GRAVITY_MULTIPLIER)
    else:
        GRAVITY_MULTIPLIER = 1.0 # Default
        space.gravity = (0, -981 * GRAVITY_MULTIPLIER) # Apply default

    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Reset panel mode

# --- Functions to create Pymunk objects ---
def create_box(space_obj, position, density, width, height, initial_dynamic=True, color=(100, 150, 200, 200)): # Default to a soft blue
    # Ensure dimensions are positive
    width = max(0.001, width)
    height = max(0.001, height)
    density = max(0.001, density) # Ensure density is positive

    # Calculate mass and inertia for the box. Mass is density * area
    mass = density * width * height
    # Pymunk moment_for_box expects width and height, not half-width/half-height
    inertia = pymunk.moment_for_box(mass, (width, height))
    
    body = pymunk.Body(mass, inertia) 
    body.position = position
    body.body_id = get_next_body_id() # Assign a unique ID to the body
    
    shape = pymunk.Poly.create_box(body, (width, height))
    shape.friction = 0.5
    shape.elasticity = 0.8
    shape.density = density # Keep density for display/re-calculation if resized
    shape.color = color 
    # Store the initial dynamic color
    shape._original_dynamic_color = color
    shape.filter = pymunk.ShapeFilter(categories=COLLIDABLE_CATEGORY) # Default to collidable
    
    if not initial_dynamic:
        body.body_type = pymunk.Body.STATIC
        shape.color = STATIC_BODY_COLOR # This line sets it to static color initially
    
    space_obj.add(body, shape)
    record_history() # Record creation to history
    log_message(f"Created box at {position} with dimensions ({width}, {height}). Body ID: {body.body_id}.")
    return body, shape

def create_circle(space_obj, position, radius, density, initial_dynamic=True, color=(100, 150, 200, 200)): # Default to a soft blue
    # Ensure radius and density are positive
    radius = max(0.001, radius)
    density = max(0.001, density) # Ensure density is positive

    # Calculate mass and inertia for the circle. Mass is density * area
    mass = density * math.pi * (radius ** 2)
    inertia = pymunk.moment_for_circle(mass, 0, radius)
    
    body = pymunk.Body(mass, inertia) 
    body.position = position
    body.body_id = get_next_body_id() # Assign a unique ID to the body
    
    shape = pymunk.Circle(body, radius) 
    shape.friction = 0.5
    shape.elasticity = 0.8
    shape.density = density # Keep density for display/re-calculation if resized
    shape.color = color 
    # Store the initial dynamic color
    shape._original_dynamic_color = color
    shape.filter = pymunk.ShapeFilter(categories=COLLIDABLE_CATEGORY) # Default to collidable

    if not initial_dynamic:
        body.body_type = pymunk.Body.STATIC
        shape.color = STATIC_BODY_COLOR 
    
    space_obj.add(body, shape)
    record_history() # Record creation to history
    log_message(f"Created circle at {position} with radius {radius}. Body ID: {body.body_id}.")
    return body, shape

# --- Function to apply property changes from the panel to selected objects (now multiple) ---
def apply_properties_to_selected_object(property_name, value):
    global selected_bodies

    if not selected_bodies:
        return

    record_history() # Record before change

    # Apply changes to all selected bodies
    for body in selected_bodies:
        # No special handling for ground_body or space.static_body anymore
        # if body == ground_body or body == space.static_body:
        #     continue

        for shape in body.shapes:
            if property_name == 'density':
                shape.density = max(0.001, value) # Ensure density is always positive
                if body.body_type == pymunk.Body.DYNAMIC: # Recalculate mass/inertia only for dynamic bodies
                    if isinstance(shape, pymunk.Circle):
                        body.mass = max(0.001, shape.density * math.pi * (shape.radius ** 2))
                        body.inertia = max(0.001, pymunk.moment_for_circle(body.mass, 0, shape.radius))
                    elif isinstance(shape, pymunk.Poly):
                        # Get actual dimensions from shape's vertices in local space
                        verts = shape.get_vertices()
                        min_x = min(v.x for v in verts)
                        max_x = max(v.x for v in verts)
                        min_y = min(v.y for v in verts)
                        max_y = max(v.y for v in verts)
                        width = abs(max_x - min_x) # Ensure width is positive
                        height = abs(max_y - min_y) # Ensure height is positive
                        body.mass = max(0.001, shape.density * width * height)
                        body.inertia = max(0.001, pymunk.moment_for_box(body.mass, (width, height)))
                log_message(f"Changed density of selected object(s) (ID: {body.body_id}) to {value}.")
            elif property_name == 'elasticity':
                shape.elasticity = value
                log_message(f"Changed elasticity of selected object(s) (ID: {body.body_id}) to {value}.")
            elif property_name == 'friction':
                shape.friction = value
                log_message(f"Changed friction of selected object(s) (ID: {body.body_id}) to {value}.")
            # Re-added color and random_color property handling
            elif property_name == 'color':
                # Almacena el nuevo color como el color dinámico deseado
                shape._original_dynamic_color = value
                # Aplica el color inmediatamente a la forma para que se vea el cambio
                # independientemente de si el cuerpo es dinámico o estático.
                shape.color = value
                log_message(f"Changed color of selected object(s) (ID: {body.body_id}) to {value}.")
            elif property_name == 'random_color':
                new_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255)
                shape.color = new_color
                shape._original_dynamic_color = new_color # Update original dynamic color
                log_message(f"Set random color for selected object(s) (ID: {body.body_id}) to {new_color}.")
    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object') # Update UI after changes

def toggle_static_dynamic_for_selected():
    global selected_bodies
    if not selected_bodies:
        return
    record_history() # Record before change

    # Determine the target state: if any selected body is dynamic, make all static. Otherwise, make all dynamic.
    target_dynamic = False
    if any(body.body_type == pymunk.Body.STATIC for body in selected_bodies):
        target_dynamic = True # If at least one is static, switch all to dynamic

    for body in selected_bodies:
        # No special handling for ground_body or space.static_body anymore
        # if body == ground_body or body == space.static_body:
        #     continue

        if target_dynamic:
            body.body_type = pymunk.Body.DYNAMIC
            # Recalculate mass and inertia based on shapes' densities
            total_mass = 0
            total_inertia = 0
            for shape in body.shapes:
                if isinstance(shape, pymunk.Circle):
                    # Ensure radius and density are positive before calculation
                    radius = max(0.001, shape.radius)
                    density = max(0.001, shape.density)
                    shape_mass = density * math.pi * (radius ** 2)
                    shape_inertia = pymunk.moment_for_circle(shape_mass, 0, radius)
                elif isinstance(shape, pymunk.Poly):
                    verts = shape.get_vertices()
                    min_x = min(v.x for v in verts)
                    max_x = max(v.x for v in verts)
                    min_y = min(v.y for v in verts)
                    max_y = max(v.y for v in verts)
                    # Ensure width and height are positive before calculation
                    width = abs(max_x - min_x)
                    height = abs(max_y - min_y)
                    density = max(0.001, shape.density) # Ensure density is positive
                    shape_mass = density * width * height
                    shape_inertia = pymunk.moment_for_box(shape_mass, (width, height))
                else: # Fallback for unknown shape types
                    shape_mass = 0
                    shape_inertia = 0

                total_mass += max(0.001, shape_mass) # Ensure individual shape mass is positive
                total_inertia += max(0.001, shape_inertia) # Ensure individual shape inertia is positive

                # Restore original dynamic color
                shape.color = shape._original_dynamic_color
            
            # Ensure final mass and inertia are positive to avoid AssertionError
            body.mass = max(0.001, total_mass) # Set a minimum mass for the body
            body.inertia = max(0.001, total_inertia) # Set a minimum inertia for the body
            log_message(f"Set selected object(s) (ID: {body.body_id}) to Dynamic.")

        else: # Make static
            body.body_type = pymunk.Body.STATIC
            body.inertia = float('inf')
            body.velocity = (0,0)
            body.angular_velocity = 0
            # Change color to static body color
            for shape in body.shapes:
                shape.color = STATIC_BODY_COLOR
            log_message(f"Set selected object(s) (ID: {body.body_id}) to Static.")
    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object') # Update UI after changes

def set_background_color(new_color):
    global SPACE_COLOR
    record_history() # Record before change
    if new_color == "random":
        SPACE_COLOR = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255)
        log_message(f"Set background color to random: {SPACE_COLOR}.")
    else:
        SPACE_COLOR = new_color
        log_message(f"Changed background color to {SPACE_COLOR}.")
    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='space') # Update UI after changes

def set_gravity_multiplier(multiplier):
    global GRAVITY_MULTIPLIER
    record_history() # Record before change
    GRAVITY_MULTIPLIER = multiplier
    space.gravity = (0, -981 * GRAVITY_MULTIPLIER)
    log_message(f"Changed gravity multiplier to {multiplier}.")
    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='space') # Update UI after changes


# --- Function to handle window resizing ---
def handle_resize_event(new_width, new_height):
    global WIDTH, HEIGHT, screen
    WIDTH, HEIGHT = new_width, new_height
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

    # Update dimensions in the GameUI instance and rebuild the entire UI
    game_ui.WIDTH = new_width
    game_ui.HEIGHT = new_height
    game_ui.rebuild_all_ui_elements()
    # Adjust properties panel position on resize
    game_ui.properties_panel.set_relative_position(pygame.Rect(WIDTH - game_ui.PROPERTIES_PANEL_WIDTH, game_ui.TOP_BAR_HEIGHT, game_ui.PROPERTIES_PANEL_WIDTH, HEIGHT - game_ui.PROPERTIES_PANEL_WIDTH).topleft)
    log_message(f"Window resized to {new_width}x{new_height}.")


# --- Function to remove a selected body or joint ---
def delete_selected_item():
    global selected_bodies, selected_constraints, mouse_joint, dragged_body, drawing, start_pos, end_pos, active_tool, trails_data
    
    record_history() # Record before deletion

    # Remove mouse_joint if active to prevent errors when its body is deleted
    if mouse_joint:
        space.remove(mouse_joint)
        mouse_joint = None
        dragged_body = None

    # Step 1: Remove all selected constraints from the space
    # Create a list copy to iterate over while modifying the original set
    for constraint in list(selected_constraints):
        if constraint in space.constraints: # Ensure it still exists in the space
            space.remove(constraint)
        selected_constraints.discard(constraint) # Remove from our selection set regardless
        log_message(f"Deleted constraint: {constraint}.")

    # Step 2: Remove all selected bodies (and their associated shapes and constraints) from the space
    # Create a list copy of selected_bodies to iterate over
    for body in list(selected_bodies):
        if body == space.static_body: # Do not delete the static space body
            continue
        
        # Remove all shapes attached to this body
        for s in list(body.shapes): # Iterate over a copy of shapes
            if s in space.shapes: # Ensure it still exists
                space.remove(s)
        
        # Remove all constraints attached to this body (some might have been removed in Step 1)
        for c in list(body.constraints): # Iterate over a copy of body's constraints
            if c in space.constraints: # Ensure it still exists
                space.remove(c)
        
        # Finally, remove the body itself
        if body in space.bodies: # Ensure body still exists in space
            space.remove(body)
        
        # Remove from our internal tracking sets
        selected_bodies.discard(body)
        if body in trails_data:
            del trails_data[body]
        log_message(f"Deleted body: {body.body_id}.")
    
    # Step 3: Clear any remaining interaction state
    drawing = False 
    start_pos = None
    end_pos = None
    active_tool = None # Return to default tool (pan)
    
    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')


# Helper function to clear mouse state
def clear_mouse_state():
    global mouse_joint, dragged_body, drawing, start_pos, end_pos, \
           initial_angle_at_click, initial_mouse_angle, initial_radius_at_click, \
           initial_dims_at_click, \
           drag_box_selection, drag_box_start_pos, \
           joint_anchor_body_1, joint_anchor_pos_1, \
           is_panning, mouse_camera_start_pos
    if mouse_joint:
        space.remove(mouse_joint)
    mouse_joint = None
    dragged_body = None
    drawing = False
    start_pos = None
    end_pos = None
    initial_angle_at_click = None
    initial_mouse_angle = None
    initial_radius_at_click = None
    initial_dims_at_click = None
    drag_box_selection = False
    drag_box_start_pos = None
    joint_anchor_body_1 = None 
    joint_anchor_pos_1 = None  
    is_panning = False
    mouse_camera_start_pos = None
    log_message("Mouse interaction state cleared.")


# --- Function to create a new simple scene ---
def create_new_simple_scene():
    global selected_bodies, selected_constraints, active_tool, simulation_running, history, history_index, SPACE_COLOR, trails_data, camera_offset, camera_zoom, GRAVITY_MULTIPLIER, next_body_id_counter

    record_history() # Record current state before clearing

    # Remove all bodies and shapes
    for body in list(space.bodies): # Iterate over a copy to avoid modification issues
        if body != space.static_body: # Do not remove pymunk static body
            space.remove(body)
            for shape in list(body.shapes): # Also remove associated shapes
                space.remove(shape)
    
    # Remove all constraints/joints
    for constraint in list(space.constraints):
        space.remove(constraint)

    # Reset state variables
    selected_bodies.clear()
    selected_constraints.clear()
    active_tool = None # Default tool is now None (pan mode)
    simulation_running = False # Ensure simulation is paused when creating a new scene
    game_ui.set_play_pause_text("Resume") # Update play/pause button text
    clear_mouse_state() # Clear any active drag/draw state
    
    SPACE_COLOR = (20, 20, 20, 255) # Reset background color
    GRAVITY_MULTIPLIER = 1.0 # Reset gravity multiplier
    space.gravity = (0, -981 * GRAVITY_MULTIPLIER) # Apply default gravity

    trails_data.clear() # Clear all trails for a new scene

    # Reset camera to default
    camera_offset = pymunk.Vec2d(0, 0)
    camera_zoom = 1.0

    # Reset history
    history = []
    history_index = -1
    next_body_id_counter = 0 # Reset the ID counter for a new scene
    record_history() # Record the initial state of the new scene
    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Update UI (now just ensures visibility of other panels)
    log_message("New scene created.")

# --- Callbacks for UI actions (registered with GameUI) ---
def on_play_pause_pressed():
    global simulation_running
    record_history() # Record state before changing pause/resume
    simulation_running = not simulation_running
    game_ui.set_play_pause_text("Resume") if not simulation_running else game_ui.set_play_pause_text("Pause")
    log_message(f"Simulation {'paused' if not simulation_running else 'resumed'}.")

def on_new_scene_pressed():
    create_new_simple_scene()
    log_message("New scene button pressed.")

def on_save_pressed():
    # Call the UI method to show the save dialog
    game_ui.show_save_project_dialog()
    log_message("Save button pressed.")

def on_load_pressed():
    # Call the UI method to show the load dialog
    game_ui.show_load_project_dialog()
    log_message("Load button pressed.")

def on_tool_selected(tool_name):
    global active_tool, selected_bodies, selected_constraints, joint_message_shown
    
    # Clear previous interaction state
    clear_mouse_state() 
    joint_message_shown = False # Reset joint message flag when tool changes

    # Set the new active tool
    active_tool = tool_name
    log_message(f"Tool selected: {tool_name}.")

    # Handle selection clearing based on the new tool
    if tool_name in ['box', 'circle', 'hinge', 'spring']:
        # For creation and joint tools, clear any existing selection
        selected_bodies.clear()
        selected_constraints.clear()
        game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')
    # For 'select', 'drag', 'move', 'rotate', we generally want to preserve selection
    # or allow adding to it. 'select' tool itself will handle its selection logic.
    # 'drag', 'move', 'rotate' operate on existing selection.
    
    # If a tool is selected, and no bodies are selected, ensure properties panel is hidden
    if not selected_bodies:
        game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')

def on_delete_selected():
    delete_selected_item() 
    log_message("Delete selected item(s) button pressed.")

def on_undo():
    global history_index
    if history_index > 0:
        history_index -= 1
        load_history_state(history_index)
        log_message("Undo action performed.")
    else:
        log_message("Undo stack is empty.", level="WARN")

def on_redo():
    global history_index
    if history_index < len(history) - 1:
        history_index += 1
        load_history_state(history_index)
        log_message("Redo action performed.")
    else:
        log_message("Redo stack is empty.", level="WARN")

def on_generate_trails_pressed():
    global show_trails, trails_data
    show_trails = not show_trails
    if not show_trails:
        trails_data.clear() # Clear trails immediately when turned off
    record_history() # Record history when toggling trails
    log_message(f"Trails display toggled {'ON' if show_trails else 'OFF'}.")

def on_help_pressed(): 
    game_ui.show_help_dialog()
    log_message("Help button pressed. Showing keyboard shortcuts.")

def on_credits_pressed(): # New: Credits button callback
    game_ui.show_credits_dialog()
    log_message("Credits button pressed. Showing credits information.")

# --- Copy/Paste Functions ---
def serialize_selected_items(bodies_to_serialize, constraints_to_serialize):
    """Serializes only the selected bodies and constraints for clipboard."""
    objects_data = []
    body_to_id = {}
    
    # First pass: Create ID mapping for selected bodies
    for body in bodies_to_serialize:
        if body == space.static_body: # Exclude space.static_body from regular object serialization
            continue
        # Ensure body has a body_id attribute
        if not hasattr(body, 'body_id'):
            body.body_id = get_next_body_id() # Assign a new ID if missing
        body_to_id[body] = body.body_id

    # Second pass: Serialize body data
    for body in bodies_to_serialize:
        if body == space.static_body: # Exclude space.static_body from regular object serialization
            continue
        
        body_data = {
            "body_id": body.body_id, # Save the unique ID
            "position": (body.position.x, body.position.y),
            "angle": body.angle,
            "velocity": (body.velocity.x, body.velocity.y),
            "angular_velocity": body.angular_velocity,
            "body_type": "dynamic" if body.body_type == pymunk.Body.DYNAMIC else ("static" if body.body_type == pymunk.Body.STATIC else "kinematic"),
            "shapes": []
        }
        for shape in body.shapes:
            shape_data = {
                "friction": shape.friction,
                "elasticity": shape.elasticity,
                "density": shape.density,
                "color": shape.color if hasattr(shape, 'color') else (100, 150, 200, 200),
                "original_dynamic_color": shape._original_dynamic_color if hasattr(shape, '_original_dynamic_color') else (100, 150, 200, 200),
                "collision_category": shape.filter.categories # Save collision category
            }
            if isinstance(shape, pymunk.Circle):
                shape_data["type"] = "circle"
                shape_data["radius"] = shape.radius
            elif isinstance(shape, pymunk.Poly):
                shape_data["type"] = "box"
                verts = shape.get_vertices()
                min_x = min(v.x for v in verts)
                max_x = max(v.x for v in verts)
                min_y = min(v.y for v in verts)
                max_y = max(v.y for v in verts)
                shape_data["width"] = abs(max_x - min_x)
                shape_data["height"] = abs(max_y - min_y)
            body_data["shapes"].append(shape_data)
        objects_data.append(body_data)

    constraints_data = []
    for constraint in constraints_to_serialize:
        # Only copy constraints where both bodies are part of the selection or are static/space.static_body
        body_a_id = body_to_id.get(constraint.a)
        body_b_id = body_to_id.get(constraint.b)

        # If one body is space.static_body, map it to its special ID.
        if constraint.a == space.static_body: body_a_id = "static_space_body_id"
        if constraint.b == space.static_body: body_b_id = "static_space_body_id"

        # Only serialize if both bodies are either in the selection OR are static/space.static_body bodies
        if body_a_id is not None and body_b_id is not None:
            if isinstance(constraint, pymunk.PinJoint):
                constraints_data.append({
                    "type": "PinJoint",
                    "body_a_id": body_a_id,
                    "body_b_id": body_b_id,
                    "anchor_a": (constraint.anchor_a.x, constraint.anchor_a.y),
                    "anchor_b": (constraint.anchor_b.x, constraint.anchor_b.y),
                })
            elif isinstance(constraint, pymunk.DampedSpring):
                constraints_data.append({
                    "type": "DampedSpring",
                    "body_a_id": body_a_id,
                    "body_b_id": body_b_id,
                    "anchor_a": (constraint.anchor_a.x, constraint.anchor_a.y),
                    "anchor_b": (constraint.anchor_b.x, constraint.anchor_b.y),
                    "rest_length": constraint.rest_length,
                    "stiffness": constraint.stiffness,
                    "damping": constraint.damping
                })
    return {"objects": objects_data, "constraints": constraints_data}


def paste_serialized_items(serialized_data, offset):
    """Pastes serialized items into the space with an offset."""
    newly_created_bodies = []
    newly_created_constraints = []
    
    # Map old IDs from serialized data to newly created bodies
    old_id_to_new_body = {}
    
    # The static_space_body_id is always present and doesn't need to be created.
    # It's used for mouse joints, etc.
    old_id_to_new_body["static_space_body_id"] = space.static_body

    # Create new bodies and shapes
    if 'objects' in serialized_data:
        for body_data in serialized_data['objects']:
            pos = pymunk.Vec2d(body_data["position"][0], body_data["position"][1]) + offset
            
            mass = 1
            inertia = 1
            new_body = pymunk.Body(mass, inertia)
            new_body.position = pos
            new_body.angle = body_data["angle"]
            new_body.velocity = pymunk.Vec2d(body_data["velocity"][0], body_data["velocity"][1])
            new_body.angular_velocity = body_data["angular_velocity"]

            if body_data["body_type"] == "static":
                new_body.body_type = pymunk.Body.STATIC
                new_body.mass = float('inf')
                new_body.inertia = float('inf')
            elif body_data["body_type"] == "kinematic":
                new_body.body_type = pymunk.Body.KINEMATIC
            else: # dynamic
                new_body.body_type = pymunk.Body.DYNAMIC

            # Assign a new unique ID to the pasted body
            new_body.body_id = get_next_body_id()
            old_id_to_new_body[body_data["body_id"]] = new_body # Map the original ID to the new body instance

            temp_shapes = []
            for shape_data in body_data["shapes"]:
                shape_type = shape_data["type"]
                density = shape_data.get("density", DEFAULT_DENSITY)
                color = tuple(shape_data.get("color", (100, 150, 200, 200)))
                original_dynamic_color = tuple(shape_data.get("original_dynamic_color", color))
                collision_category = shape_data.get("collision_category", COLLIDABLE_CATEGORY)

                new_shape = None
                if shape_type == "circle":
                    radius = max(0.001, shape_data.get("radius", 10))
                    new_shape = pymunk.Circle(new_body, radius)
                    if new_body.body_type == pymunk.Body.DYNAMIC:
                        new_body.mass = max(0.001, density * math.pi * (radius ** 2))
                        new_body.inertia = max(0.001, pymunk.moment_for_circle(new_body.mass, 0, radius))
                elif shape_type == "box":
                    width = max(0.001, shape_data.get("width", 20))
                    height = max(0.001, shape_data.get("height", 20))
                    new_shape = pymunk.Poly.create_box(new_body, (width, height))
                    if new_body.body_type == pymunk.Body.DYNAMIC:
                        new_body.mass = max(0.001, density * width * height)
                        new_body.inertia = max(0.001, pymunk.moment_for_box(new_body.mass, (width, height)))
                
                if new_shape:
                    new_shape.friction = shape_data.get("friction", 0.5)
                    new_shape.elasticity = shape_data.get("elasticity", 0.8)
                    new_shape.density = density
                    new_shape.color = color if new_body.body_type == pymunk.Body.DYNAMIC else STATIC_BODY_COLOR
                    new_shape._original_dynamic_color = original_dynamic_color
                    new_shape.filter = pymunk.ShapeFilter(categories=collision_category)
                    temp_shapes.append(new_shape)
            
            if temp_shapes:
                space.add(new_body, *temp_shapes)
                newly_created_bodies.append(new_body)
    
    # Create new constraints
    if 'constraints' in serialized_data:
        for constraint_data in serialized_data['constraints']:
            body_a = old_id_to_new_body.get(constraint_data["body_a_id"])
            body_b = old_id_to_new_body.get(constraint_data["body_b_id"])
            
            if body_a is not None and body_b is not None:
                if constraint_data["type"] == "PinJoint":
                    anchor_a = pymunk.Vec2d(constraint_data["anchor_a"][0], constraint_data["anchor_a"][1])
                    anchor_b = pymunk.Vec2d(constraint_data["anchor_b"][0], constraint_data["anchor_b"][1])
                    pin_joint = pymunk.PinJoint(body_a, body_b, anchor_a, anchor_b)
                    space.add(pin_joint)
                    newly_created_constraints.append(pin_joint)
                elif constraint_data["type"] == "DampedSpring":
                    anchor_a = pymunk.Vec2d(constraint_data["anchor_a"][0], constraint_data["anchor_a"][1])
                    anchor_b = pymunk.Vec2d(constraint_data["anchor_b"][0], constraint_data["anchor_b"][1]) 
                    rest_length = constraint_data["rest_length"]
                    stiffness = constraint_data["stiffness"] 
                    damping = constraint_data["damping"] 
                    spring_joint = pymunk.DampedSpring(body_a, body_b, anchor_a, anchor_b, rest_length, stiffness, damping)
                    space.add(spring_joint)
                    newly_created_constraints.append(spring_joint)
    
    return newly_created_bodies, newly_created_constraints


# --- Initialize history with initial state ---
game_ui = GameUI(resolution=(WIDTH, HEIGHT))

# Assign callbacks after game_ui is initialized and its elements created.
# This ensures buttons have the correct functions.
game_ui.on_play_pause_pressed_callback = on_play_pause_pressed
game_ui.on_new_scene_pressed_callback = on_new_scene_pressed
game_ui.on_save_pressed_callback = on_save_pressed
game_ui.on_load_pressed_callback = on_load_pressed
game_ui.on_tool_selected_callback = on_tool_selected
game_ui.on_delete_callback = on_delete_selected 
game_ui.on_undo_callback = on_undo
game_ui.on_redo_callback = on_redo
game_ui.on_help_pressed_callback = on_help_pressed
game_ui.on_credits_pressed_callback = on_credits_pressed # Assign credits button callback
# Assignment for on_generate_trails_pressed_callback has been removed
# game_ui.on_generate_trails_pressed_callback = on_generate_trails_pressed

# Assign the new perform save/load methods to the UI instance
game_ui._perform_save_project = game_ui._perform_save_project
game_ui._perform_load_project = game_ui._perform_load_project

record_history()
game_ui.update_undo_redo_buttons(history_index, len(history))
log_message("Program started. Initial state recorded.")


# --- Main Game Loop ---
running = True
try:
    while running:
        time_delta = clock.tick(FPS) / 1000.0

        mouse_x, mouse_y = pygame.mouse.get_pos()
        is_mouse_in_simulation_area = (mouse_x > TOOLBAR_WIDTH and mouse_y > TOP_BAR_HEIGHT and mouse_x < WIDTH - game_ui.PROPERTIES_PANEL_WIDTH)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                log_message("Program quit requested.")
            
            if event.type == pygame.VIDEORESIZE:
                handle_resize_event(event.w, event.h)
                game_ui.manager.set_window_resolution((WIDTH, HEIGHT)) 

            # Process UI events first. If UI consumed the event, skip further processing.
            if game_ui.process_event(event):
                continue

            # --- Mouse Events for Simulation Interaction (only if not handled by UI) ---
            if is_mouse_in_simulation_area: 
                if event.type == pygame.MOUSEBUTTONDOWN:
                    point_pygame = pymunk.Vec2d(mouse_x, mouse_y)
                    point_pymunk = to_pymunk_coords(point_pygame.x, point_pygame.y)
                    
                    if event.button == 1: # Left mouse button
                        hit_info = space.point_query_nearest(point_pymunk, 0, pymunk.ShapeFilter())
                        body_under_mouse = None
                        # For joint creation, allow space.static_body to be hit
                        if active_tool in ['hinge', 'spring']:
                            if hit_info:
                                body_under_mouse = hit_info.shape.body
                        else: # For other tools, exclude space.static_body from direct selection
                            if hit_info and hit_info.shape.body != space.static_body:
                                body_under_mouse = hit_info.shape.body

                        # If a creation tool is active, start drawing
                        if active_tool in ['box', 'circle']:
                            selected_bodies.clear() 
                            selected_constraints.clear()
                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Hide panel
                            drawing = True
                            start_pos = point_pygame
                            log_message(f"Started drawing with {active_tool} tool at {start_pos}.")
                        
                        # If a joint tool is active
                        elif active_tool in ['hinge', 'spring']:
                            if joint_anchor_body_1 is None: 
                                if body_under_mouse:
                                    joint_anchor_body_1 = body_under_mouse
                                    joint_anchor_pos_1 = point_pymunk 
                                    if not joint_message_shown: # Only show message once
                                        game_ui.show_message("Joint Creation", "First object selected. Click on the second to create the joint.")
                                        joint_message_shown = True
                                    selected_bodies.clear() 
                                    selected_constraints.clear()
                                    selected_bodies.add(joint_anchor_body_1)
                                    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object')
                                    log_message(f"First anchor for {active_tool} joint selected on body {body_under_mouse.body_id}.")
                                else:
                                    game_ui.show_message("Warning", "No object found for the first anchor.")
                                    clear_mouse_state() 
                                    active_tool = None 
                                    selected_bodies.clear() 
                                    selected_constraints.clear()
                                    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')
                                    log_message("Attempted joint creation without first object.", level="WARN")

                            else: # Second click for joint creation
                                body_2 = body_under_mouse
                                if body_2 and body_2 == joint_anchor_body_1: 
                                    game_ui.show_message("Warning", "Select a different object for the second anchor.")
                                    log_message("Attempted joint creation with same object for both anchors.", level="WARN")
                                elif body_2 is None: 
                                    game_ui.show_message("Warning", "A second object is needed to create the joint.")
                                    log_message("Attempted joint creation without second object.", level="WARN")
                                else:
                                    # Create the joint
                                    if active_tool == 'hinge':
                                        pin_joint = pymunk.PinJoint(joint_anchor_body_1, body_2, 
                                                                    joint_anchor_body_1.world_to_local(joint_anchor_pos_1), 
                                                                    body_2.world_to_local(point_pymunk))
                                        space.add(pin_joint)
                                        game_ui.show_message("Joint", "Hinge created.") 
                                        log_message(f"Hinge joint created between {joint_anchor_body_1.body_id} and {body_2.body_id}.")
                                        record_history()
                                        
                                    elif active_tool == 'spring':
                                        anchor1_local = joint_anchor_body_1.world_to_local(joint_anchor_pos_1)
                                        anchor2_local = body_2.world_to_local(point_pymunk)
                                        rest_length = (joint_anchor_pos_1 - point_pymunk).length 
                                        stiffness = 1000.0
                                        damping = 10.0
                                        spring_joint = pymunk.DampedSpring(joint_anchor_body_1, body_2, anchor1_local, anchor2_local, rest_length, stiffness, damping)
                                        space.add(spring_joint)
                                        game_ui.show_message("Joint", "Spring created.")
                                        log_message(f"Spring joint created between {joint_anchor_body_1.body_id} and {body_2.body_id}.")
                                        record_history()
                                        
                                    joint_anchor_body_1 = None
                                    joint_anchor_pos_1 = None
                                    clear_mouse_state()
                                    active_tool = None 
                                    selected_bodies.clear() 
                                    selected_constraints.clear()
                                    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')

                        # Selection/Drag/Move/Rotate tools (if not a creation or joint tool) or default interaction
                        else:
                            hit_body = False
                            hit_joint = False
                            
                            # If the 'select' tool is active, always go for drag box selection if no body is hit
                            if active_tool == 'select':
                                if not body_under_mouse: # If clicked on empty space (or space.static_body)
                                    if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                                        selected_bodies.clear()
                                        selected_constraints.clear()
                                    drag_box_selection = True
                                    drag_box_start_pos = point_pygame
                                    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Hide panel
                                    log_message("Started drag box selection.")
                                else: # If a body is hit with 'select' tool, handle individual selection
                                    if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                                        selected_bodies.clear()
                                        selected_constraints.clear()
                                    selected_bodies.add(body_under_mouse)
                                    hit_body = True
                                    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object')
                                    log_message(f"Selected body: {body_under_mouse.body_id}.")
                                record_history() 
                            
                            elif body_under_mouse: # A body was clicked, apply tool if any or select
                                # If no transform tool is active, or if it's 'drag' and a body was clicked,
                                # or if it's 'move'/'rotate' and a body was clicked, then handle selection.
                                if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                                    selected_bodies.clear()
                                    selected_constraints.clear()
                                
                                selected_bodies.add(body_under_mouse)
                                hit_body = True
                                selected_constraints.clear() 
                                game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object')
                                log_message(f"Selected body: {body_under_mouse.body_id}.")
                                
                                # Set up drag if 'drag' tool is active
                                if active_tool == 'drag': 
                                    dragged_body = body_under_mouse
                                    local_point = dragged_body.world_to_local(point_pymunk)
                                    mouse_joint = pymunk.PinJoint(space.static_body, dragged_body, point_pymunk, local_point)
                                    mouse_joint.collide_bodies = False 
                                    space.add(mouse_joint)
                                    log_message(f"Started dragging body: {dragged_body.body_id}.")
                                # Set up move if 'move' tool is active
                                elif active_tool == 'move':
                                    # Store initial positions and offsets for all selected bodies
                                    for body in selected_bodies:
                                        # Store original body type for dynamic bodies if simulation is running
                                        if body.body_type == pymunk.Body.DYNAMIC and simulation_running:
                                            body._original_body_type_before_move = pymunk.Body.DYNAMIC 
                                            body.body_type = pymunk.Body.KINEMATIC # Temporarily make kinematic for precise dragging
                                            body.velocity = (0,0)
                                            body.angular_velocity = 0
                                        body._initial_pos_at_click = body.position # Body's position at the start of the drag
                                        body._offset_from_click_point = point_pymunk - body.position # Offset from mouse click to body's center
                                    log_message(f"Started moving selected bodies.")
                                # Set up rotate if 'rotate' tool is active
                                elif active_tool == 'rotate':
                                    # Calculate centroid of selected bodies for rotation
                                    if selected_bodies:
                                        centroid_x = sum(b.position.x for b in selected_bodies) / len(selected_bodies)
                                        centroid_y = sum(b.position.y for b in selected_bodies) / len(selected_bodies)
                                        centroid_pymunk = pymunk.Vec2d(centroid_x, centroid_y)
                                        
                                        for body in selected_bodies:
                                            # Store original body type for dynamic bodies if simulation is running
                                            if body.body_type == pymunk.Body.DYNAMIC and simulation_running:
                                                body._original_body_type_before_rotate = pymunk.Body.DYNAMIC
                                                body.body_type = pymunk.Body.KINEMATIC
                                                body.velocity = (0,0)
                                                body.angular_velocity = 0
                                            body._initial_angle_at_click = body.angle
                                        
                                        initial_mouse_vec = point_pymunk - centroid_pymunk
                                        initial_mouse_angle = math.atan2(initial_mouse_vec.y, initial_mouse_vec.x)
                                        
                                        space._current_rotation_centroid = centroid_pymunk
                                        space._initial_mouse_angle = initial_mouse_angle
                                        log_message(f"Started rotating selected bodies around centroid {centroid_pymunk}.")
                                    else: # No bodies selected, cannot rotate
                                        active_tool = None 
                                        game_ui.show_message("Warning", "Select an object to rotate.")
                                        game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Hide panel
                                        log_message("Attempted rotate without selected objects.", level="WARN")

                            else: # No body hit, try to select a joint (constraint) or start panning
                                joint_selection_radius = 10 # Pixels
                                for constraint in space.constraints:
                                    # No longer exclude space.static_body if they are part of a constraint
                                    # if constraint.a == space.static_body or constraint.b == space.static_body:
                                    #     continue 

                                    joint_pos_world = None
                                    if isinstance(constraint, pymunk.PinJoint):
                                        # For a PinJoint, the effective joint point is usually the midpoint between anchors or one of the anchors
                                        # For selection, checking one anchor (e.g., anchor_a on body_a) is usually sufficient.
                                        joint_pos_world = constraint.a.local_to_world(constraint.anchor_a)
                                    elif isinstance(constraint, pymunk.DampedSpring):
                                        # For DampedSpring, the anchors are the attachment points
                                        joint_pos_world = constraint.a.local_to_world(constraint.anchor_a) 

                                    if joint_pos_world:
                                        joint_pos_pygame = to_pygame_coords(joint_pos_world)
                                        dist_sq = (joint_pos_pygame[0] - point_pygame.x)**2 + \
                                                  (joint_pos_pygame[1] - point_pygame.y)**2
                                        if dist_sq <= joint_selection_radius**2:
                                            selected_constraints.add(constraint)
                                            hit_joint = True
                                            selected_bodies.clear() 
                                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object') # Show object panel for joints
                                            log_message(f"Selected joint: {constraint}.")
                                            break 
                                
                                # If no body or joint was hit AND no specific tool is active, start panning
                                if not hit_body and not hit_joint and active_tool is None:
                                    clear_mouse_state() 
                                    is_panning = True
                                    mouse_camera_start_pos = point_pygame 
                                    game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Hide panel
                                    log_message("Started panning.")

                            if hit_body or hit_joint:
                                record_history() 
                                    
                    elif event.button == 3: # Right mouse button (global deselection or show space properties)
                        if is_mouse_in_simulation_area:
                            point_pymunk = to_pymunk_coords(mouse_x, mouse_y)
                            hit_info = space.point_query_nearest(point_pymunk, 0, pymunk.ShapeFilter())
                            
                            if hit_info and hit_info.shape.body != space.static_body: 
                                # Right-clicked on an object
                                selected_bodies.clear()
                                selected_constraints.clear()
                                selected_bodies.add(hit_info.shape.body)
                                game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object')
                                log_message(f"Right-clicked on object {hit_info.shape.body.body_id}. Showing object properties.")
                            else:
                                # Right-clicked on background
                                selected_bodies.clear()
                                selected_constraints.clear()
                                clear_mouse_state() # Clear any active tool state
                                active_tool = None # Reset active tool
                                game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='space')
                                log_message("Right-clicked on background. Showing space properties.")
                        else: # Right-clicked outside simulation area (e.g., on UI panel)
                            selected_bodies.clear()
                            selected_constraints.clear()
                            clear_mouse_state()
                            active_tool = None
                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')
                            log_message("Right-clicked outside simulation area. Deselected all.")


                    elif event.button == 4: # Mouse wheel up (zoom in)
                        if is_mouse_in_simulation_area:
                            old_world_pos = to_pymunk_coords(mouse_x, mouse_y)
                            camera_zoom *= 1.1 # Zoom in by 10%
                            camera_zoom = min(camera_zoom, 10.0) # Max zoom limit
                            new_world_pos = to_pymunk_coords(mouse_x, mouse_y)
                            # Adjust offset to keep the point under the mouse fixed
                            camera_offset = camera_offset + pymunk.Vec2d(old_world_pos.x - new_world_pos.x, old_world_pos.y - new_world_pos.y) 

                    elif event.button == 5: # Mouse wheel down (zoom out)
                        if is_mouse_in_simulation_area:
                            old_world_pos = to_pymunk_coords(mouse_x, mouse_y)
                            camera_zoom /= 1.1 # Zoom out by 10%
                            camera_zoom = max(camera_zoom, 0.1) # Min zoom limit
                            new_world_pos = to_pymunk_coords(mouse_x, mouse_y)
                            # Adjust offset to keep the point under the mouse fixed
                            camera_offset = camera_offset + pymunk.Vec2d(old_world_pos.x - new_world_pos.x, old_world_pos.y - new_world_pos.y) 
                        
                    
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        current_mouse_pos_pygame = pymunk.Vec2d(mouse_x, mouse_y) 
                        current_mouse_pos_pymunk = to_pymunk_coords(current_mouse_pos_pygame.x, current_mouse_pos_pygame.y)

                        if is_panning: 
                            is_panning = False
                            mouse_camera_start_pos = None
                            log_message("Stopped panning.")

                        if active_tool in ['box', 'circle'] and drawing and start_pos:
                            min_pixel_size = 5
                            distance_sq = (current_mouse_pos_pygame.x - start_pos.x)**2 + (current_mouse_pos_pygame.y - start_pos.y)**2
                            
                            newly_created_body = None

                            if distance_sq < min_pixel_size**2:
                                game_ui.show_message("Warning", "Object too small to create.")
                                log_message(f"Attempted to create {active_tool} but it was too small.", level="WARN")
                            else:
                                current_density = DEFAULT_DENSITY 
                                current_color_rgba = hsv_to_rgb_tuple(210, 50, 70, 200) 


                                start_pos_pymunk = to_pymunk_coords(start_pos.x, start_pos.y)
                                end_pos_pymunk = to_pymunk_coords(current_mouse_pos_pygame.x, current_mouse_pos_pygame.y)

                                if active_tool == 'box':
                                    box_width = abs(end_pos_pymunk.x - start_pos_pymunk.x)
                                    box_height = abs(end_pos_pymunk.y - start_pos_pymunk.y)
                                    
                                    box_center_x = (start_pos_pymunk.x + end_pos_pymunk.x) / 2
                                    box_center_y = (start_pos_pymunk.y + end_pos_pymunk.y) / 2
                                    
                                    if box_width >= min_dim and box_height >= min_dim: 
                                        newly_created_body, new_shape = create_box(space, (box_center_x, box_center_y), current_density, box_width, box_height, initial_dynamic=True, color=current_color_rgba)
                                        new_shape._original_dynamic_color = current_color_rgba 
                                    else:
                                        game_ui.show_message("Warning", "Box is too small to be created.")
                                        log_message("Box creation failed: dimensions too small.", level="WARN")

                                elif active_tool == 'circle':
                                    dx = end_pos_pymunk.x - start_pos_pymunk.x
                                    dy = end_pos_pymunk.y - start_pos_pymunk.y
                                    radius = math.sqrt(dx**2 + dy**2) * 0.5 
                                    center_x = start_pos_pymunk.x + dx / 2
                                    center_y = start_pos_pymunk.y + dy / 2
                                    
                                    if radius >= min_dim / 2: 
                                        newly_created_body, new_shape = create_circle(space, (center_x, center_y), radius, current_density, initial_dynamic=True, color=current_color_rgba)
                                        new_shape._original_dynamic_color = current_color_rgba 
                                    else:
                                        game_ui.show_message("Warning", "Circle is too small to be created.")
                                        log_message("Circle creation failed: radius too small.", level="WARN")
                            
                            # Only clear drawing state if the object was actually created or if it was too small
                            if newly_created_body or distance_sq < min_pixel_size**2:
                                drawing = False
                                start_pos = None
                                end_pos = None
                            
                            if newly_created_body:
                                selected_bodies.clear()
                                selected_bodies.add(newly_created_body)
                                selected_constraints.clear() 
                                game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object')
                            else:
                                game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none') # Hide panel if no object created
                            
                        elif drag_box_selection: 
                            drag_box_selection = False
                            drag_box_end_pos = current_mouse_pos_pygame
                            
                            rect_x = min(drag_box_start_pos.x, current_mouse_pos_pygame.x)
                            rect_y = min(drag_box_start_pos.y, current_mouse_pos_pygame.y)
                            rect_width = abs(current_mouse_pos_pygame.x - drag_box_start_pos.x)
                            rect_height = abs(current_mouse_pos_pygame.y - drag_box_start_pos.y)
                            
                            selection_rect_pygame = pygame.Rect(rect_x, rect_y, rect_width, rect_height)

                            bb_left = selection_rect_pygame.left / camera_zoom - camera_offset.x
                            bb_right = selection_rect_pygame.right / camera_zoom - camera_offset.x
                            bb_bottom = (HEIGHT - selection_rect_pygame.bottom) / camera_zoom - camera_offset.y
                            bb_top = (HEIGHT - selection_rect_pygame.top) / camera_zoom - camera_offset.y
                            
                            selection_bb_pymunk = pymunk.BB(bb_left, bb_bottom, bb_right, bb_top)

                            found_shapes = space.bb_query(selection_bb_pymunk, pymunk.ShapeFilter())
                            
                            if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                                selected_bodies.clear()
                                selected_constraints.clear() 
                            
                            for hit_shape in found_shapes:
                                if hit_shape.body != space.static_body: # Exclude space.static_body from selection
                                    selected_bodies.add(hit_shape.body)
                            
                            drag_box_start_pos = None 
                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object' if selected_bodies else 'none')
                            log_message(f"Drag box selection completed. Selected {len(selected_bodies)} bodies.")
                        
                        elif mouse_joint: 
                            space.remove(mouse_joint)
                            mouse_joint = None
                            dragged_body = None
                            record_history() 
                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object' if selected_bodies else 'none') # Update panel after drag
                            log_message("Stopped dragging object.")
                        
                        elif active_tool == 'move' and selected_bodies: 
                            for body in selected_bodies:
                                # Restore original body type if it was changed to kinematic
                                if hasattr(body, '_original_body_type_before_move') and body._original_body_type_before_move == pymunk.Body.DYNAMIC:
                                    body.body_type = pymunk.Body.DYNAMIC
                                    del body._original_body_type_before_move
                                # Clear temporary attributes
                                if hasattr(body, '_initial_pos_at_click'):
                                    del body._initial_pos_at_click
                                if hasattr(body, '_offset_from_click_point'):
                                    del body._offset_from_click_point
                            record_history() 
                            log_message("Stopped moving selected bodies.")
                        
                        elif active_tool == 'rotate' and selected_bodies: 
                            for body in selected_bodies:
                                # Restore original body type if it was changed to kinematic
                                if hasattr(body, '_original_body_type_before_rotate') and body._original_body_type_before_rotate == pymunk.Body.DYNAMIC:
                                    body.body_type = pymunk.Body.DYNAMIC
                                    del body._original_body_type_before_rotate
                                if hasattr(body, '_initial_angle_at_click'):
                                    del body._initial_angle_at_click
                            if hasattr(space, '_current_rotation_centroid'):
                                del space._current_rotation_centroid
                            if hasattr(space, '_initial_mouse_angle'):
                                del space._initial_mouse_angle
                            record_history() 
                            log_message("Stopped rotating selected bodies.")
                        
                        # If no specific tool is active and no object/selection was made, hide properties panel
                        if active_tool is None and not selected_bodies and not selected_constraints:
                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='none')
                        
                elif event.type == pygame.MOUSEMOTION:
                    current_mouse_pos_pygame = pymunk.Vec2d(mouse_x, mouse_y)
                    current_mouse_pos_pymunk = to_pymunk_coords(mouse_x, mouse_y)

                    if is_panning and mouse_camera_start_pos:
                        dx = current_mouse_pos_pygame.x - mouse_camera_start_pos.x
                        dy = current_mouse_pos_pygame.y - mouse_camera_start_pos.y
                        # Adjust camera offset based on mouse movement, scaled by zoom
                        camera_offset = camera_offset + pymunk.Vec2d(dx / camera_zoom, -dy / camera_zoom) 
                        mouse_camera_start_pos = current_mouse_pos_pygame # Update start pos for next frame


                    if drawing and (active_tool == 'box' or active_tool == 'circle'):
                        end_pos = current_mouse_pos_pygame
                    
                    elif drag_box_selection and drag_box_start_pos:
                        end_pos = current_mouse_pos_pygame
                    
                    elif mouse_joint:
                        mouse_joint.anchor_a = current_mouse_pos_pymunk
                    
                    elif active_tool == 'move' and selected_bodies:
                        for body in selected_bodies:
                            # No check for body.body_type != pymunk.Body.STATIC here, so static bodies move too
                            if hasattr(body, '_offset_from_click_point'):
                                body.position = current_mouse_pos_pymunk - body._offset_from_click_point
                    
                    elif active_tool == 'rotate' and selected_bodies and hasattr(space, '_current_rotation_centroid'):
                        centroid_pymunk = space._current_rotation_centroid
                        initial_mouse_angle = space._initial_mouse_angle

                        if initial_mouse_angle is not None:
                            current_mouse_vec = current_mouse_pos_pymunk - centroid_pymunk
                            current_mouse_angle = math.atan2(current_mouse_vec.y, current_mouse_vec.x)
                            
                            angle_change = current_mouse_angle - initial_mouse_angle
                            
                            for body in selected_bodies:
                                if hasattr(body, '_initial_angle_at_click'): # No check for body.body_type != pymunk.Body.STATIC here
                                    new_body_angle = body._initial_angle_at_click + angle_change
                                    relative_pos_to_centroid = body.position - centroid_pymunk
                                    rotated_relative_pos = relative_pos_to_centroid.rotated(angle_change)
                                    body.position = centroid_pymunk + rotated_relative_pos
                                    body.angle = new_body_angle

                    # Drawing for joint tools (visual feedback) - only if no message has been shown yet
                    if active_tool in ['hinge', 'spring'] and joint_anchor_body_1:
                        anchor_pos_pygame = to_pygame_coords(joint_anchor_pos_1)
                        current_mouse_pygame = (mouse_x, mouse_y)
                        # Only draw line if not a message is active
                        if not game_ui.active_message_window: 
                            pygame.draw.line(screen, (255, 0, 255), anchor_pos_pygame, current_mouse_pygame, int(3 * camera_zoom)) # Thickness adjusted

                elif event.type == pygame.KEYDOWN: 
                    if event.key == pygame.K_c and (event.mod & pygame.KMOD_CTRL):
                        if selected_bodies or selected_constraints:
                            clipboard_data = serialize_selected_items(selected_bodies, selected_constraints)
                            game_ui.show_message("Copy", "Selected objects copied to clipboard.")
                            log_message("Copied selected objects to clipboard.")
                        else:
                            game_ui.show_message("Copy", "No objects selected to copy.")
                            log_message("Attempted copy with no objects selected.", level="WARN")
                    elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                        if clipboard_data:
                            offset = pymunk.Vec2d(20, 20) # Small offset for pasted objects
                            new_bodies, new_constraints = paste_serialized_items(clipboard_data, offset)
                            selected_bodies.clear()
                            selected_constraints.clear()
                            for body in new_bodies:
                                selected_bodies.add(body)
                            for constraint in new_constraints:
                                selected_constraints.add(constraint)
                            record_history() # Record paste action
                            game_ui.show_message("Paste", "Objects pasted from clipboard.")
                            log_message(f"Pasted {len(new_bodies)} bodies and {len(new_constraints)} constraints from clipboard.")
                            game_ui.update_properties_panel(selected_bodies, selected_constraints, DEFAULT_DENSITY, mode='object' if selected_bodies else 'none')
                        else:
                            game_ui.show_message("Paste", "Clipboard is empty.")
                            log_message("Attempted paste with empty clipboard.", level="WARN")
                    elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                        if selected_bodies or selected_constraints: 
                            game_ui.on_delete_callback()
                            log_message("Delete key pressed.")
                        else:
                            log_message("Delete key pressed with no objects selected.", level="INFO")
                    # New: Undo/Redo/Play-Pause keyboard shortcuts
                    elif event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
                        game_ui.on_undo_callback()
                    elif event.key == pygame.K_y and (event.mod & pygame.KMOD_CTRL):
                        game_ui.on_redo_callback()
                    elif event.key == pygame.K_SPACE:
                        game_ui.on_play_pause_pressed_callback()


        # --- UI Update ---
        game_ui.update(time_delta)

        # --- Physics Update ---
        if simulation_running:
            space.step(1 / FPS) 
            # Update trails data
            if show_trails:
                for body in space.bodies:
                    if body.body_type == pymunk.Body.DYNAMIC: 
                        if body not in trails_data:
                            trails_data[body] = []
                        
                        # Ensure the trail points are stored in Pygame coordinates AFTER camera transform
                        # This prevents them from "moving" with the camera later if they were stored in Pymunk world coords
                        trails_data[body].append(to_pygame_coords(body.position))
                        
                        if len(trails_data[body]) > MAX_TRAIL_LENGTH:
                            trails_data[body].pop(0) 


        # --- Drawing ---
        screen.fill(SPACE_COLOR) 

        # Draw Pymunk shapes
        for shape in space.shapes:
            shape_color = shape.color

            if isinstance(shape, pymunk.Circle):
                center_x_pygame, center_y_pygame = to_pygame_coords(shape.body.position)
                # Adjust radius for zoom
                zoomed_radius = int(shape.radius * camera_zoom)
                pygame.draw.circle(screen, shape_color, (center_x_pygame, center_y_pygame), zoomed_radius, 0)
                pygame.draw.circle(screen, (0,0,0,255), (center_x_pygame, center_y_pygame), zoomed_radius, 1)

            elif isinstance(shape, pymunk.Poly):
                points_pygame = []
                for v in shape.get_vertices():
                    world_v = shape.body.position + v.rotated(shape.body.angle)
                    points_pygame.append(to_pygame_coords(world_v))
                pygame.draw.polygon(screen, shape_color, points_pygame, 0)
                pygame.draw.polygon(screen, (0,0,0,255), points_pygame, 1)


        # Draw yellow outline of selected objects
        for body in selected_bodies:
            for shape in body.shapes:
                if isinstance(shape, pymunk.Circle):
                    center_x_pygame, center_y_pygame = to_pygame_coords(shape.body.position)
                    zoomed_radius = int(shape.radius * camera_zoom)
                    # Adjust selected outline thickness for circles
                    pygame.draw.circle(screen, SELECTED_OUTLINE_COLOR, (center_x_pygame, center_y_pygame), int(zoomed_radius + 4 * camera_zoom), int(3 * camera_zoom))
                elif isinstance(shape, pymunk.Poly):
                    points_pygame = []
                    for v in shape.get_vertices():
                        world_v = shape.body.position + v.rotated(shape.body.angle)
                        points_pygame.append(to_pygame_coords(world_v))
                    # Adjust selected outline thickness for polygons
                    pygame.draw.polygon(screen, SELECTED_OUTLINE_COLOR, points_pygame, int(3 * camera_zoom))

        # Draw joints (constraints)
        for constraint in space.constraints:
            if isinstance(constraint, pymunk.SimpleMotor):
                continue

            if isinstance(constraint, pymunk.PinJoint):
                pivot_point_world = constraint.a.local_to_world(constraint.anchor_a)
                pivot_point_pygame = to_pygame_coords(pivot_point_world)
                pygame.draw.circle(screen, JOINT_COLOR, (int(pivot_point_pygame[0]), int(pivot_point_pygame[1])), int(5 * camera_zoom), 0) 
                pygame.draw.circle(screen, (255, 255, 255), (int(pivot_point_pygame[0]), int(pivot_point_pygame[1])), int(5 * camera_zoom), 1) 

                if constraint in selected_constraints:
                    pygame.draw.circle(screen, SELECTED_OUTLINE_COLOR, (int(pivot_point_pygame[0]), int(pivot_point_pygame[1])), int(8 * camera_zoom), int(2 * camera_zoom))
            
            elif isinstance(constraint, pymunk.DampedSpring):
                anchor_a_world = constraint.a.local_to_world(constraint.anchor_a)
                anchor_b_world = constraint.b.local_to_world(constraint.anchor_b)
                pygame.draw.line(screen, JOINT_COLOR, to_pygame_coords(anchor_a_world), to_pygame_coords(anchor_b_world), int(2 * camera_zoom))
                
                if constraint in selected_constraints:
                    pygame.draw.line(screen, SELECTED_OUTLINE_COLOR, to_pygame_coords(anchor_a_world), to_pygame_coords(anchor_b_world), int(4 * camera_zoom))
            

        # Draw creation guide lines (for 'box' or 'circle' creation)
        if drawing and start_pos and (active_tool == 'box' or active_tool == 'circle'):
            current_mouse_pos_pygame = pymunk.Vec2d(mouse_x, mouse_y)
            if active_tool == 'box':
                x = min(start_pos.x, current_mouse_pos_pygame.x)
                y = min(start_pos.y, current_mouse_pos_pygame.y)
                width_rect = abs(current_mouse_pos_pygame.x - start_pos.x)
                height_rect = abs(current_mouse_pos_pygame.y - start_pos.y) 
                # Adjust creation line thickness
                pygame.draw.rect(screen, LINE_COLOR, (x, y, width_rect, height_rect), int(3 * camera_zoom))
            elif active_tool == 'circle':
                dx = current_mouse_pos_pygame.x - start_pos.x
                dy = current_mouse_pos_pygame.y - start_pos.y
                radius = math.sqrt(dx**2 + dy**2) * 0.5 
                center_x = start_pos.x + dx / 2
                center_y = start_pos.y + dy / 2
                # Adjust creation line thickness
                pygame.draw.circle(screen, LINE_COLOR, (int(center_x), int(center_y)), int(radius), int(3 * camera_zoom))
        
        # Draw drag selection box
        if drag_box_selection and drag_box_start_pos:
            current_mouse_pos_pygame = pymunk.Vec2d(mouse_x, mouse_y)
            rect_x = min(drag_box_start_pos.x, current_mouse_pos_pygame.x)
            rect_y = min(drag_box_start_pos.y, current_mouse_pos_pygame.y)
            rect_width = abs(current_mouse_pos_pygame.x - drag_box_start_pos.x)
            rect_height = abs(current_mouse_pos_pygame.y - drag_box_start_pos.y)
            # Changed to draw only the border of the selection box
            pygame.draw.rect(screen, (0, 255, 0, 255), (rect_x, rect_y, rect_width, rect_height), int(2 * camera_zoom)) # Draw only the border with scalable thickness
    
        # Draw rotation centroid if 'rotate' tool is active and bodies are selected
        if active_tool == 'rotate' and selected_bodies and hasattr(space, '_current_rotation_centroid'):
            centroid_pygame = to_pygame_coords(space._current_rotation_centroid)
            pygame.draw.circle(screen, (255, 0, 0), (int(centroid_pygame[0]), int(centroid_pygame[1])), int(5 * camera_zoom), 0) 
            pygame.draw.line(screen, (255, 0, 0), (int(centroid_pygame[0]) - int(10 * camera_zoom), int(centroid_pygame[1])), (int(centroid_pygame[0]) + int(10 * camera_zoom), int(centroid_pygame[1])), int(3 * camera_zoom)) # Thickness adjusted
            pygame.draw.line(screen, (255, 0, 0), (int(centroid_pygame[0]), int(centroid_pygame[1]) - int(10 * camera_zoom)), (int(centroid_pygame[0]), int(centroid_pygame[1]) + int(10 * camera_zoom)), int(3 * camera_zoom)) # Thickness adjusted

        # Drawing for joint tools (visual feedback)
        if active_tool in ['hinge', 'spring'] and joint_anchor_body_1:
            anchor_pos_pygame = to_pygame_coords(joint_anchor_pos_1)
            current_mouse_pygame = (mouse_x, mouse_y)
            # Only draw line if not a message is active
            if not game_ui.active_message_window:
                pygame.draw.line(screen, (255, 0, 255), anchor_pos_pygame, current_mouse_pygame, int(3 * camera_zoom)) # Thickness adjusted

        # Draw trails
        if show_trails:
            for body, trail_points in trails_data.items():
                if len(trail_points) > 1:
                    # The points in trails_data are already in Pygame coords adjusted for camera.
                    # When drawing, just use them directly.
                    pygame.draw.lines(screen, TRAIL_COLOR, False, trail_points, int(2 * camera_zoom)) 

        # Draw FPS counter
        fps_text = fps_font.render(f"FPS: {int(clock.get_fps())}", True, (255, 255, 255)) # White color
        # Position the FPS counter in the top-left corner of the simulation area
        screen.blit(fps_text, (TOOLBAR_WIDTH + 10, TOP_BAR_HEIGHT + 10))

        game_ui.draw(screen) 

        pygame.display.flip() 

except Exception as e:
    log_message(f"An unhandled error occurred: {e}", level="CRITICAL")
    log_message(traceback.format_exc(), level="CRITICAL") # Log the full traceback
finally:
    pygame.quit() 
    log_message("Program terminated.")
