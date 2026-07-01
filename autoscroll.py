# ==============================================================================
# MangaScroll Pro - Manga & Webtoon Hands-Free Autoscroller
# Copyright (c) 2026 Darwin Bracho (BrachoDB). Todos los derechos reservados.
# Propiedad Intelectual de Darwin Bracho.
# ==============================================================================

import os
import sys
import time
import threading
import pyautogui

# Desactivar el failsafe de PyAutoGUI para evitar bloqueos del programa cuando el ratón toca las esquinas de la pantalla.
pyautogui.FAILSAFE = False

# Intentar importar pynput para atajos de teclado globales
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# Intentar importar OpenCV y Pillow para el control de gestos con webcam
try:
    import cv2
    from PIL import Image, ImageTk
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    # Definir stubs para evitar errores si no está instalado
    cv2 = None
    Image = None
    ImageTk = None

# Intentar importar MediaPipe para control por gestos de mano
try:
    import mediapipe as mp
    from mediapipe.tasks.python.vision.hand_landmarker import HandLandmarker, HandLandmarkerOptions
    from mediapipe.tasks.python.core.base_options import BaseOptions
    MEDIPIPE_AVAILABLE = True
except ImportError:
    MEDIPIPE_AVAILABLE = False
    mp = None
    HandLandmarker = None
    HandLandmarkerOptions = None
    BaseOptions = None

import customtkinter as ctk

# Configuración del tema visual de CustomTkinter
ctk.set_appearance_mode("dark")  # Modo Oscuro
ctk.set_default_color_theme("blue")  # Tema de color azul moderno

class MangaAutoscrollerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana principal
        self.title("MangaScroll Pro 📖 - Manos Libres")
        self.geometry("820x680")
        self.minsize(820, 680)
        self.resizable(True, True)

        # Variables de estado del autoscroll
        self.is_scrolling = False
        self.scroll_speed = 15  # Rango de 1 a 50 (se traduce en píxeles/pasos de scroll)
        self.scroll_direction = "Bajar"  # "Bajar" o "Subir"
        self.scroll_interval = 0.05  # Segundos entre cada evento de scroll
        self.scroll_amount = 10  # Cantidad de scroll por tick
        self.selected_hotkey = "F9"
        self.keyboard_listener = None
        self.scroll_thread = None
        self.scroll_thread_active = True

        # Variables de estado del control por cámara/webcam
        self.camera_enabled = False
        self.camera_active = False
        self.cap = None
        self.camera_mode = "hand"  # "hand" | "hand_gesture" | "air_mouse"
        self.camera_thread = None
        self.last_frame = None
        self.hand_detected = False
        self.hand_closed = False
        self.hand_stop_active = False
        self.gesture_sensitivity = 15
        self.pinch_detected = False
        self.prev_pinch_detected = False
        self.calibrated_hand_y = None
        self.calibrate_pending = False
        self.mouse_smooth_x = 0.5
        self.mouse_smooth_y = 0.5
        self.mouse_last_valid = None
        self._h_stable = {"hand": 0, "gesture": 0, "mouse": 0}
        self._h_prev = {"hand": False, "gesture": False, "mouse": False}
        self._gesture_auto_cal_samples = []
        self._gesture_auto_calibrated = False
        self._mouse_prev_pos = None

        # Configuración de interfaz
        self.setup_ui()

        # Iniciar listener de teclado si está disponible
        if PYNPUT_AVAILABLE:
            self.start_keyboard_listener()
        else:
            self.show_warning("Atajos globales no disponibles. Instala pynput.")

        # Iniciar el hilo del bucle de desplazamiento (autoscroll)
        self.start_scroll_thread()

        # Configurar cierre limpio
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        # Grid layout de 2 columnas y múltiples filas
        self.grid_columnconfigure(0, weight=4)  # Columna de controles principales
        self.grid_columnconfigure(1, weight=5)  # Columna de configuración y webcam
        self.grid_rowconfigure(0, weight=0)  # Título
        self.grid_rowconfigure(1, weight=1)  # Contenido

        # ----------------------------------------------------
        # HEADER (Título)
        # ----------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, height=70, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="ew")
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="MangaScroll Pro 📖", 
            font=ctk.CTkFont(family="Outfit", size=26, weight="bold")
        )
        self.title_label.pack(side="left", padx=10)

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame, 
            text="Desplazamiento manos libres para lectura de manga y webtoon", 
            font=ctk.CTkFont(family="Inter", size=13),
            text_color="#888888"
        )
        self.subtitle_label.pack(side="left", padx=(15, 0), pady=(8, 0))

        # ----------------------------------------------------
        # COLUMNA IZQUIERDA: CONTROLES PRINCIPALES
        # ----------------------------------------------------
        self.left_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.left_frame.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")

        # Tarjeta de Estado
        self.status_card = ctk.CTkFrame(self.left_frame, fg_color="#1E1E24", border_width=1, border_color="#33333F")
        self.status_card.pack(fill="x", padx=5, pady=5)

        self.status_title = ctk.CTkLabel(
            self.status_card, 
            text="ESTADO DEL SISTEMA", 
            font=ctk.CTkFont(family="Inter", size=10, weight="bold"),
            text_color="#888888"
        )
        self.status_title.pack(anchor="w", padx=15, pady=(10, 2))

        self.status_badge = ctk.CTkLabel(
            self.status_card, 
            text="DETENIDO", 
            fg_color="#CC3333",  # Rojo oscuro para detenido
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            height=40,
            corner_radius=8
        )
        self.status_badge.pack(fill="x", padx=15, pady=(5, 10))

        # Botón de Alternancia Principal (Iniciar/Detener)
        self.toggle_btn = ctk.CTkButton(
            self.left_frame,
            text="INICIAR AUTOSCROLL",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            fg_color="#1F6AA5",
            hover_color="#144A75",
            height=60,
            command=self.toggle_scrolling_manual
        )
        self.toggle_btn.pack(fill="x", padx=5, pady=10)

        # Contenedor de Ajustes de Desplazamiento
        self.scroll_settings_frame = ctk.CTkFrame(self.left_frame, fg_color="#1E1E24", border_width=1, border_color="#33333F")
        self.scroll_settings_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.settings_title = ctk.CTkLabel(
            self.scroll_settings_frame,
            text="PARÁMETROS DE DESPLAZAMIENTO",
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        )
        self.settings_title.pack(anchor="w", padx=15, pady=(12, 10))

        # Slider de Velocidad
        self.speed_label_frame = ctk.CTkFrame(self.scroll_settings_frame, fg_color="transparent")
        self.speed_label_frame.pack(fill="x", padx=15, pady=(5, 0))
        
        self.speed_label_title = ctk.CTkLabel(
            self.speed_label_frame,
            text="Velocidad de Scroll:",
            font=ctk.CTkFont(family="Inter", size=12, weight="bold")
        )
        self.speed_label_title.pack(side="left")
        
        self.speed_val_label = ctk.CTkLabel(
            self.speed_label_frame,
            text=f"{self.scroll_speed}",
            font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
            text_color="#1F6AA5"
        )
        self.speed_val_label.pack(side="right")

        self.speed_slider = ctk.CTkSlider(
            self.scroll_settings_frame,
            from_=1,
            to=50,
            number_of_steps=49,
            command=self.on_speed_changed
        )
        self.speed_slider.set(self.scroll_speed)
        self.speed_slider.pack(fill="x", padx=15, pady=(5, 10))

        # Texto explicativo de velocidad
        self.speed_help_label = ctk.CTkLabel(
            self.scroll_settings_frame,
            text="Velocidad media - Desplazamiento continuo suave",
            font=ctk.CTkFont(family="Inter", size=11, slant="italic"),
            text_color="#888888"
        )
        self.speed_help_label.pack(anchor="w", padx=15, pady=(0, 15))

        # Dirección del scroll
        self.dir_label = ctk.CTkLabel(
            self.scroll_settings_frame,
            text="Dirección de desplazamiento:",
            font=ctk.CTkFont(family="Inter", size=12, weight="bold")
        )
        self.dir_label.pack(anchor="w", padx=15, pady=(5, 2))

        self.dir_selector = ctk.CTkSegmentedButton(
            self.scroll_settings_frame,
            values=["Bajar", "Subir"],
            command=self.on_dir_changed
        )
        self.dir_selector.set(self.scroll_direction)
        self.dir_selector.pack(fill="x", padx=15, pady=(0, 15))

        # Sección Avanzada Colapsable (Ajustes de ticks)
        self.adv_btn = ctk.CTkButton(
            self.scroll_settings_frame,
            text="⚙️ Ajustes Avanzados",
            font=ctk.CTkFont(family="Inter", size=11),
            fg_color="transparent",
            text_color="#888888",
            hover_color="#2A2A35",
            height=25,
            command=self.toggle_advanced_panel
        )
        self.adv_btn.pack(padx=15, pady=5)

        self.adv_frame = ctk.CTkFrame(self.scroll_settings_frame, fg_color="#18181C")
        # No se empaqueta al inicio para estar colapsado

        self.adv_interval_label = ctk.CTkLabel(
            self.adv_frame,
            text=f"Intervalo entre ticks: {self.scroll_interval}s",
            font=ctk.CTkFont(family="Inter", size=11)
        )
        self.adv_interval_label.pack(anchor="w", padx=15, pady=(10, 0))

        self.adv_interval_slider = ctk.CTkSlider(
            self.adv_frame,
            from_=0.01,
            to=0.2,
            number_of_steps=19,
            command=self.on_interval_changed
        )
        self.adv_interval_slider.set(self.scroll_interval)
        self.adv_interval_slider.pack(fill="x", padx=15, pady=(2, 10))

        self.adv_amount_label = ctk.CTkLabel(
            self.adv_frame,
            text=f"Fuerza por tick: {self.scroll_amount} px",
            font=ctk.CTkFont(family="Inter", size=11)
        )
        self.adv_amount_label.pack(anchor="w", padx=15, pady=(5, 0))

        self.adv_amount_slider = ctk.CTkSlider(
            self.adv_frame,
            from_=2,
            to=50,
            number_of_steps=48,
            command=self.on_amount_changed
        )
        self.adv_amount_slider.set(self.scroll_amount)
        self.adv_amount_slider.pack(fill="x", padx=15, pady=(2, 10))

        # ----------------------------------------------------
        # COLUMNA DERECHA: CONFIGURACIÓN GENERAL Y WEBCAM
        # ----------------------------------------------------
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew")

        # Caja de Atajos de Teclado
        self.hotkey_card = ctk.CTkFrame(self.right_frame, fg_color="#1E1E24", border_width=1, border_color="#33333F")
        self.hotkey_card.pack(fill="x", padx=5, pady=5)

        self.hotkey_title = ctk.CTkLabel(
            self.hotkey_card,
            text="ATAJO DE TECLADO GLOBAL",
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#1F6AA5"
        )
        self.hotkey_title.pack(anchor="w", padx=15, pady=(12, 5))

        self.hotkey_desc = ctk.CTkLabel(
            self.hotkey_card,
            text="Elige la tecla para Activar/Desactivar el scroll desde tu navegador:",
            font=ctk.CTkFont(family="Inter", size=11),
            text_color="#888888"
        )
        self.hotkey_desc.pack(anchor="w", padx=15, pady=2)

        self.hotkey_selector_frame = ctk.CTkFrame(self.hotkey_card, fg_color="transparent")
        self.hotkey_selector_frame.pack(fill="x", padx=15, pady=(5, 12))

        self.hotkey_select = ctk.CTkComboBox(
            self.hotkey_selector_frame,
            values=["F9", "F8", "F10", "Scroll_Lock", "Pause", "Caps_Lock"],
            command=self.on_hotkey_changed,
            width=140
        )
        self.hotkey_select.set(self.selected_hotkey)
        self.hotkey_select.pack(side="left")

        self.hotkey_info = ctk.CTkLabel(
            self.hotkey_selector_frame,
            text="← Presiona esta tecla globalmente",
            font=ctk.CTkFont(family="Inter", size=11, slant="italic"),
            text_color="#888888"
        )
        self.hotkey_info.pack(side="left", padx=15)

        # Caja de Control por Cámara (Gestos)
        self.webcam_card = ctk.CTkFrame(self.right_frame, fg_color="#1E1E24", border_width=1, border_color="#33333F")
        self.webcam_card.pack(fill="both", expand=True, padx=5, pady=5)

        self.webcam_title = ctk.CTkLabel(
            self.webcam_card,
            text="CONTROL MANOS LIBRES POR CÁMARA (WEBCAM)",
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#2ECC71"  # Verde brillante
        )
        self.webcam_title.pack(anchor="w", padx=15, pady=(12, 5))

        if not OPENCV_AVAILABLE:
            # Mensaje si OpenCV no está disponible
            self.webcam_status_lbl = ctk.CTkLabel(
                self.webcam_card,
                text="❌ OpenCV o Pillow no detectados en el sistema.",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                text_color="#CC3333"
            )
            self.webcam_status_lbl.pack(anchor="w", padx=15, pady=5)

            self.webcam_help = ctk.CTkLabel(
                self.webcam_card,
                text="Para activar esta función, puedes instalar las dependencias necesarias\n"
                     "haciendo clic en el botón de abajo o ejecutando:\n"
                     "pip install opencv-python pillow mediapipe",
                font=ctk.CTkFont(family="Inter", size=11),
                justify="left",
                text_color="#888888"
            )
            self.webcam_help.pack(anchor="w", padx=15, pady=10)

            self.install_opencv_btn = ctk.CTkButton(
                self.webcam_card,
                text="Instalar Dependencias Automáticamente",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                fg_color="#CC3333",
                hover_color="#992222",
                command=self.install_opencv_background
            )
            self.install_opencv_btn.pack(padx=15, pady=10, fill="x")
        else:
            # Control por cámara disponible
            # Selector de modo de control
            self.mode_selector_frame = ctk.CTkFrame(self.webcam_card, fg_color="transparent")
            self.mode_selector_frame.pack(anchor="w", padx=15, pady=5)

            self.mode_label = ctk.CTkLabel(
                self.mode_selector_frame,
                text="Modo de control:",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold")
            )
            self.mode_label.pack(side="left", padx=(0, 10))

            self.mode_selector = ctk.CTkSegmentedButton(
                self.mode_selector_frame,
                values=["Mano Clásica", "Mano Gestos", "Air Mouse"],
                command=self.on_mode_changed
            )
            self.mode_selector.set("Mano Clásica")
            self.mode_selector.pack(side="left")

            # Switch principal de cámara
            self.webcam_switch = ctk.CTkSwitch(
                self.webcam_card,
                text="Activar Control por Cámara",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                progress_color="#2ECC71",
                command=self.toggle_camera_control
            )
            self.webcam_switch.pack(anchor="w", padx=15, pady=8)

            # Frame de cámara (Video Preview y Controles)
            self.cam_controls_frame = ctk.CTkFrame(self.webcam_card, fg_color="transparent")
            self.cam_controls_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

            # Sub-frame izquierdo: Video preview
            self.video_frame = ctk.CTkFrame(self.cam_controls_frame, fg_color="#121216")
            self.video_frame.pack_propagate(False)
            self.video_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

            self.video_label = ctk.CTkLabel(
                self.video_frame,
                text="CÁMARA APAGADA\n\nActiva el interruptor arriba\npara iniciar.",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#555555"
            )
            self.video_label.pack(fill="both", expand=True)

            # Sub-frame derecho: Controles según modo
            self.cam_settings_frame = ctk.CTkFrame(self.cam_controls_frame, fg_color="transparent")
            self.cam_settings_frame.pack(side="left", fill="both", expand=True, padx=(15, 0))

            # Controles para modo mano clásica (ocultos por defecto en modo gestos)
            self.hand_classic_controls_frame = ctk.CTkFrame(self.cam_settings_frame, fg_color="transparent")

            self.hand_status_badge = ctk.CTkLabel(
                self.hand_classic_controls_frame,
                text="NO DETECTADA",
                fg_color="#33333F",
                text_color="#888888",
                font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                height=40,
                corner_radius=8
            )
            self.hand_status_badge.pack(fill="x", pady=5)

            self.hand_instructions = ctk.CTkLabel(
                self.hand_classic_controls_frame,
                text="✋ 3 dedos → BAJAR lento | 4→medio | 5→rápido\n"
                     "☝️ Solo índice → SUBIR\n"
                     "✊ Puño o menos de 3 dedos → DETENER",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#AAAAAA",
                justify="left"
            )
            self.hand_instructions.pack(anchor="w", pady=10)

            # Frame para mostrar si mediapipe está disponible
            if not MEDIPIPE_AVAILABLE:
                self.mediapipe_warning = ctk.CTkLabel(
                    self.hand_classic_controls_frame,
                    text="⚠️ MediaPipe no detectado.\nInstala con: pip install mediapipe",
                    font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                    text_color="#CC3333"
                )
                self.mediapipe_warning.pack(fill="x", pady=5)

            # Controles para modo mano gestos (oculto por defecto)
            self.hand_gesture_controls_frame = ctk.CTkFrame(self.cam_settings_frame, fg_color="transparent")

            self.hg_status_badge = ctk.CTkLabel(
                self.hand_gesture_controls_frame,
                text="SIN CONTROL",
                fg_color="#33333F",
                text_color="#888888",
                font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                height=40,
                corner_radius=8
            )
            self.hg_status_badge.pack(fill="x", pady=5)

            self.hg_calibrate_btn = ctk.CTkButton(
                self.hand_gesture_controls_frame,
                text="📍 Calibrar Centro",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                fg_color="#2ECC71",
                hover_color="#27AE60",
                text_color="#000000",
                state="disabled",
                command=self.calibrate_hand_gesture
            )
            self.hg_calibrate_btn.pack(fill="x", pady=(0, 5))

            self.hg_instructions = ctk.CTkLabel(
                self.hand_gesture_controls_frame,
                text="☝️ Extiende el ÍNDICE para ACTIVAR control.\n"
                     "👆 Mano ARRIBA → Desplazar hacia ABAJO\n"
                     "👇 Mano ABAJO → Desplazar hacia ARRIBA\n"
                     "✊ Puño o quita la mano → DETENER",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#AAAAAA",
                justify="left"
            )
            self.hg_instructions.pack(anchor="w", pady=5)

            self.hg_sens_title = ctk.CTkLabel(
                self.hand_gesture_controls_frame,
                text="Sensibilidad del gesto:",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                anchor="w"
            )
            self.hg_sens_title.pack(fill="x", pady=(8, 0))

            self.hg_sens_slider = ctk.CTkSlider(
                self.hand_gesture_controls_frame,
                from_=5,
                to=40,
                number_of_steps=35,
                command=self.on_gesture_sensitivity_changed
            )
            self.hg_sens_slider.set(self.gesture_sensitivity)
            self.hg_sens_slider.pack(fill="x", pady=(2, 8))

            self.hg_pos_title = ctk.CTkLabel(
                self.hand_gesture_controls_frame,
                text="Posición de la mano:",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                anchor="w"
            )
            self.hg_pos_title.pack(fill="x")

            self.hg_pos_progressbar = ctk.CTkProgressBar(
                self.hand_gesture_controls_frame,
                progress_color="#2ECC71",
                fg_color="#33333F",
                height=15
            )
            self.hg_pos_progressbar.set(0.5)
            self.hg_pos_progressbar.pack(fill="x", pady=(2, 5))

            self.hg_pos_label = ctk.CTkLabel(
                self.hand_gesture_controls_frame,
                text="● Centro",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#888888",
                anchor="w"
            )
            self.hg_pos_label.pack(fill="x", pady=(0, 5))

            # Frame para mostrar si mediapipe está disponible en modo gestos
            if not MEDIPIPE_AVAILABLE:
                self.hg_mediapipe_warning = ctk.CTkLabel(
                    self.hand_gesture_controls_frame,
                    text="⚠️ MediaPipe no detectado.\nInstala con: pip install mediapipe",
                    font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                    text_color="#CC3333"
                )
                self.hg_mediapipe_warning.pack(fill="x", pady=5)

            # Controles para modo Air Mouse (oculto por defecto)
            self.hand_mouse_controls_frame = ctk.CTkFrame(self.cam_settings_frame, fg_color="transparent")

            self.hm_status_badge = ctk.CTkLabel(
                self.hand_mouse_controls_frame,
                text="SIN CONTROL",
                fg_color="#33333F",
                text_color="#888888",
                font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                height=40,
                corner_radius=8
            )
            self.hm_status_badge.pack(fill="x", pady=5)

            self.hm_instructions = ctk.CTkLabel(
                self.hand_mouse_controls_frame,
                text="☝️ Índice extendido → Mover cursor\n"
                     "🤏 Pinza (índice+pulgar) → CLIC\n"
                     "🖐️ Mano abierta (5 dedos) → Scroll vertical\n"
                     "✊ Puño → DETENER todo",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#AAAAAA",
                justify="left"
            )
            self.hm_instructions.pack(anchor="w", pady=10)

            self.hm_pos_label = ctk.CTkLabel(
                self.hand_mouse_controls_frame,
                text="● Esperando mano...",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#888888",
                anchor="w"
            )
            self.hm_pos_label.pack(fill="x", pady=(0, 5))

    # ----------------------------------------------------
    # EVENT HANDLING / CONTROL LOGIC
    # ----------------------------------------------------
    def toggle_advanced_panel(self):
        if self.adv_frame.winfo_manager():
            self.adv_frame.pack_forget()
            self.adv_btn.configure(text="⚙️ Ajustes Avanzados")
        else:
            self.adv_frame.pack(fill="x", padx=15, pady=5)
            self.adv_btn.configure(text="⚙️ Ocultar Ajustes")

    def on_speed_changed(self, value):
        self.scroll_speed = int(value)
        self.speed_val_label.configure(text=f"{self.scroll_speed}")
        
        # Actualizar dinámicamente la ayuda de velocidad y los parámetros avanzados
        if self.scroll_speed <= 10:
            self.speed_help_label.configure(text="Velocidad lenta - Ideal para leer detalladamente")
            self.scroll_amount = 5
            self.scroll_interval = 0.08
        elif self.scroll_speed <= 25:
            self.speed_help_label.configure(text="Velocidad media - Desplazamiento continuo suave")
            self.scroll_amount = 10
            self.scroll_interval = 0.05
        else:
            self.speed_help_label.configure(text="Velocidad rápida - Desplazamiento veloz")
            self.scroll_amount = 18
            self.scroll_interval = 0.03
            
        # Actualizar sliders avanzados para reflejar los cambios
        self.adv_amount_slider.set(self.scroll_amount)
        self.adv_amount_label.configure(text=f"Fuerza por tick: {self.scroll_amount} px")
        self.adv_interval_slider.set(self.scroll_interval)
        self.adv_interval_label.configure(text=f"Intervalo entre ticks: {self.scroll_interval:.2f}s")

    def on_interval_changed(self, value):
        self.scroll_interval = float(value)
        self.adv_interval_label.configure(text=f"Intervalo entre ticks: {self.scroll_interval:.2f}s")

    def on_amount_changed(self, value):
        self.scroll_amount = int(value)
        self.adv_amount_label.configure(text=f"Fuerza por tick: {self.scroll_amount} px")

    def on_dir_changed(self, value):
        self.scroll_direction = value

    def on_gesture_sensitivity_changed(self, value):
        self.gesture_sensitivity = int(value)

    def calibrate_hand_gesture(self):
        self.calibrated_hand_y = None
        self.calibrate_pending = True
        self.hg_calibrate_btn.configure(text="Espera...", state="disabled", fg_color="#888888")

    def _on_hand_calibration_done(self):
        msg = f"✅ Centro: {int(self.calibrated_hand_y)}px"
        self.hg_calibrate_btn.configure(text=msg, state="disabled", fg_color="#888888")

    def on_hotkey_changed(self, value):
        self.selected_hotkey = value
        if PYNPUT_AVAILABLE:
            self.start_keyboard_listener()

    def on_mode_changed(self, value):
        mode_map = {
            "Mano Clásica": "hand",
            "Mano Gestos": "hand_gesture",
            "Air Mouse": "air_mouse"
        }
        self.camera_mode = mode_map.get(value, "hand")
        self.update_mode_ui()
        
        # REINICIAR el hilo de cámara cuando cambie el modo
        if self.camera_enabled:
            self.camera_active = False
            time.sleep(0.2)
            self.camera_active = True
            self.camera_thread = threading.Thread(target=self.camera_worker, daemon=True)
            self.camera_thread.start()

    def update_mode_ui(self):
        self.hand_classic_controls_frame.pack_forget()
        self.hand_gesture_controls_frame.pack_forget()
        self.hand_mouse_controls_frame.pack_forget()
        if self.camera_mode == "hand_gesture":
            self.hand_gesture_controls_frame.pack(fill="both", expand=True)
        elif self.camera_mode == "air_mouse":
            self.hand_mouse_controls_frame.pack(fill="both", expand=True)
        else:
            self.hand_classic_controls_frame.pack(fill="both", expand=True)

    # ----------------------------------------------------
    # TECLADO / SHORTCUT GLOBAL (pynput)
    # ----------------------------------------------------
    def start_keyboard_listener(self):
        # Detener listener anterior si existe
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
            self.keyboard_listener = None

        # Convertir selección a formato de pynput
        hk = self.selected_hotkey.lower()
        
        # Mapear nombres especiales
        if hk == "caps_lock":
            hk_key = "<caps_lock>"
        elif hk == "scroll_lock":
            hk_key = "<scroll_lock>"
        elif hk == "pause":
            hk_key = "<pause>"
        else:
            hk_key = f"<{hk}>"

        try:
            # Crear e iniciar listener de atajo global
            self.keyboard_listener = keyboard.GlobalHotKeys({
                hk_key: self.toggle_scrolling_hotkey
            })
            self.keyboard_listener.start()
        except Exception as e:
            print(f"Error al iniciar listener de atajo global: {e}")

    def toggle_scrolling_manual(self):
        # Llamado desde el botón de la interfaz
        self.toggle_scrolling()

    def toggle_scrolling_hotkey(self):
        # Llamado desde el atajo global (ejecuta en hilo separado, por lo que usamos after() para actualizar UI de forma segura)
        self.after(0, self.toggle_scrolling)

    def toggle_scrolling(self):
        self.is_scrolling = not self.is_scrolling
        self.update_status_ui()

    def update_status_ui(self):
        if self.is_scrolling:
            self.status_badge.configure(
                text="AUTOSCROLL ACTIVO",
                fg_color="#2ECC71",  # Verde
                text_color="#000000"
            )
            self.toggle_btn.configure(
                text="DETENER AUTOSCROLL",
                fg_color="#CC3333",
                hover_color="#992222"
            )
        else:
            self.status_badge.configure(
                text="DETENIDO",
                fg_color="#CC3333",  # Rojo
                text_color="#FFFFFF"
            )
            self.toggle_btn.configure(
                text="INICIAR AUTOSCROLL",
                fg_color="#1F6AA5",
                hover_color="#144A75"
            )

    # ----------------------------------------------------
    # HILO DE DESPLAZAMIENTO (SCROLL WHEEL SIMULATION)
    # ----------------------------------------------------
    def start_scroll_thread(self):
        self.scroll_thread_active = True
        self.scroll_thread = threading.Thread(target=self.scroll_worker, daemon=True)
        self.scroll_thread.start()

    def scroll_worker(self):
        while self.scroll_thread_active:
            if self.is_scrolling:
                try:
                    # Determinar cantidad y signo del scroll (- para bajar, + para subir)
                    amount = -self.scroll_amount if self.scroll_direction == "Bajar" else self.scroll_amount
                    pyautogui.scroll(amount)
                except Exception as e:
                    print(f"Error al emular scroll: {e}")
                
                time.sleep(self.scroll_interval)
            else:
                time.sleep(0.1)

    # ----------------------------------------------------
    # WEBCAM Y PROCESAMIENTO DE GESTOS
    # ----------------------------------------------------
    def toggle_camera_control(self):
        if not OPENCV_AVAILABLE:
            return

        self.camera_enabled = self.webcam_switch.get()
        
        if self.camera_enabled:
            # Iniciar hilo de cámara
            self.camera_active = True
            self.hand_stop_active = False
            self.calibrated_hand_y = None
            self.calibrate_pending = False
            self.hg_calibrate_btn.configure(state="normal", text="📍 Calibrar Centro", fg_color="#2ECC71")
            self._frame_counter = 0
            self.camera_thread = threading.Thread(target=self.camera_worker, daemon=True)
            self.camera_thread.start()
        else:
            # Detener cámara
            self.camera_active = False
            self.hand_status_badge.configure(text="NO DETECTADA", fg_color="#33333F", text_color="#888888")
            self.hg_status_badge.configure(text="SIN CONTROL", fg_color="#33333F", text_color="#888888")
            self.hg_pos_progressbar.set(0.5)
            self.hg_pos_label.configure(text="● Centro")
            self.hg_calibrate_btn.configure(state="disabled", text="📍 Calibrar Centro", fg_color="#2ECC71")
            self.hm_status_badge.configure(text="SIN CONTROL", fg_color="#33333F", text_color="#888888")
            self.hm_pos_label.configure(text="● Esperando mano...")
            self.hand_detected = False
            self.hand_closed = False
            self.hand_stop_active = False
            self.calibrated_hand_y = None
            self.calibrate_pending = False
            
            # Detener scroll si estaba activo por la cámara
            if self.is_scrolling:
                self.is_scrolling = False
                self.update_status_ui()
                
            # Limpiar preview de video
            self.after(200, self.clear_video_label)

    def camera_worker(self):
        # Intentar conectar con la webcam index 0 (usando DirectShow en Windows para carga más veloz)
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            # Intentar fallback general
            self.cap = cv2.VideoCapture(0)
            
        if not self.cap.isOpened():
            self.after(0, lambda: self.show_warning("No se pudo acceder a la webcam."))
            self.after(0, self.reset_camera_switch)
            self.camera_active = False
            return

        # Configurar dimensiones bajas para optimizar CPU
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

        # Inicializar detector de manos con MediaPipe Tasks API
        hand_detector = None
        if MEDIPIPE_AVAILABLE and HandLandmarker:
            try:
                model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "hand_landmarker.task")
                if os.path.exists(model_path):
                    base_options = BaseOptions(model_asset_path=model_path)
                    options = HandLandmarkerOptions(base_options=base_options, num_hands=1)
                    hand_detector = HandLandmarker.create_from_options(options)
            except Exception as e:
                print(f"Error al inicializar HandLandmarker: {e}")
                hand_detector = None

        while self.camera_active:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)

            should_detect = (self._frame_counter % 2 == 0) if self.camera_mode != "air_mouse" else True
            if should_detect and hand_detector:
                if self.camera_mode == "hand":
                    self._process_hand_mode(frame, hand_detector)
                elif self.camera_mode == "hand_gesture":
                    self._process_hand_gesture_mode(frame, hand_detector)
                elif self.camera_mode == "air_mouse":
                    self._process_air_mouse_mode(frame, hand_detector)
            self._frame_counter += 1

            # Redimensionar el frame para la vista previa de la UI (relación 4:3)
            try:
                vf_w = self.video_frame.winfo_width()
                preview_w = max(160, min(480, vf_w)) if vf_w > 20 else 240
            except Exception:
                preview_w = 240
            preview_h = int(preview_w * 3 / 4)
            frame_resized = cv2.resize(frame, (preview_w, preview_h))
            # Convertir frame BGR (OpenCV) a RGB y luego a formato PIL
            img_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # Pasar la imagen de forma segura a la interfaz
            self.after(0, self.update_video_preview, pil_img)
            
            # Limitar a ~25 FPS para ahorrar CPU
            time.sleep(0.04)

        # Liberar la webcam al salir del bucle
        if self.cap:
            self.cap.release()
            self.cap = None

    def _process_hand_mode(self, frame, hand_detector):
        self.hand_detected = False
        self.hand_closed = False
        gesture = "none"
        hand_found = False
        extended_count = 0
        index_extended = False

        if MEDIPIPE_AVAILABLE and hand_detector:
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                result = hand_detector.detect(mp_image)

                if result.hand_landmarks:
                    hand_found = True
                    h, w, _ = frame.shape
                    hand_landmarks = result.hand_landmarks[0]
                    lmList = [[int(lm.x * w), int(lm.y * h), lm.z] for lm in hand_landmarks]

                    connections = [
                        (0, 1), (1, 2), (2, 3), (3, 4),
                        (0, 5), (5, 6), (6, 7), (7, 8),
                        (5, 9), (9, 10), (10, 11), (11, 12),
                        (9, 13), (13, 14), (14, 15), (15, 16),
                        (13, 17), (17, 18), (18, 19), (19, 20),
                        (0, 17)
                    ]
                    for start, end in connections:
                        cv2.line(frame, (lmList[start][0], lmList[start][1]),
                                 (lmList[end][0], lmList[end][1]), (46, 204, 113), 2)
                    for point in lmList:
                        cv2.circle(frame, (point[0], point[1]), 5, (46, 204, 113), -1)

                    index_extended = lmList[8][1] < lmList[6][1]
                    middle_extended = lmList[12][1] < lmList[10][1]
                    ring_extended = lmList[16][1] < lmList[14][1]
                    pinky_extended = lmList[20][1] < lmList[18][1]
                    extended_count = sum([index_extended, middle_extended, ring_extended, pinky_extended])
                    is_fist = extended_count <= 1
                    self.hand_closed = is_fist

                    if extended_count >= 3:
                        gesture = "down"
                        speed_labels = {3: "LENTO", 4: "MEDIO", 5: "RÁPIDO"}
                        label = speed_labels.get(extended_count, "BAJAR")
                        color = (46, 204, 113) if extended_count <= 4 else (0, 255, 0)
                        cv2.putText(frame, f"BAJAR {label}", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        cv2.putText(frame, f"{extended_count} dedos", (10, 55),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    elif extended_count == 1 and index_extended:
                        gesture = "up"
                        cv2.putText(frame, "SUBIR", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                        cv2.putText(frame, "1 dedo", (10, 55),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            except Exception as e:
                print(f"Error en detección de manos (clásico): {e}")

        if hand_found != self._h_prev["hand"]:
            self._h_stable["hand"] = 0
        else:
            self._h_stable["hand"] = min(self._h_stable["hand"] + 1, 5)
        self._h_prev["hand"] = hand_found

        if self._h_stable["hand"] >= 2:
            self.hand_detected = hand_found
            gesture = gesture if hand_found else "none"

        self.after(0, self.update_hand_status_ui)

        if gesture == "down":
            speed_map = {3: (8, 0.05), 4: (12, 0.035), 5: (18, 0.02)}
            amt, interval = speed_map.get(extended_count, (8, 0.05))
            self.scroll_amount = amt
            self.scroll_interval = interval
            self.scroll_direction = "Bajar"
            if not self.is_scrolling:
                self.is_scrolling = True
                self.after(0, self.update_status_ui)
        elif gesture == "up":
            self.scroll_amount = 8
            self.scroll_interval = 0.04
            self.scroll_direction = "Subir"
            if not self.is_scrolling:
                self.is_scrolling = True
                self.after(0, self.update_status_ui)
        else:
            if self.is_scrolling:
                self.is_scrolling = False
                self.after(0, self.update_status_ui)

    def _process_hand_gesture_mode(self, frame, hand_detector):
        h, w, _ = frame.shape
        control_active = False
        hand_y = None
        hand_found = False

        if MEDIPIPE_AVAILABLE and hand_detector:
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                result = hand_detector.detect(mp_image)

                if result.hand_landmarks:
                    hand_found = True
                    hand_landmarks = result.hand_landmarks[0]
                    lmList = [[int(lm.x * w), int(lm.y * h), lm.z] for lm in hand_landmarks]

                    connections = [
                        (0, 1), (1, 2), (2, 3), (3, 4),
                        (0, 5), (5, 6), (6, 7), (7, 8),
                        (5, 9), (9, 10), (10, 11), (11, 12),
                        (9, 13), (13, 14), (14, 15), (15, 16),
                        (13, 17), (17, 18), (18, 19), (19, 20),
                        (0, 17)
                    ]
                    for start, end in connections:
                        cv2.line(frame, (lmList[start][0], lmList[start][1]),
                                 (lmList[end][0], lmList[end][1]), (46, 204, 113), 2)
                    for point in lmList:
                        cv2.circle(frame, (point[0], point[1]), 5, (46, 204, 113), -1)

                    palm_indices = [5, 9, 13, 17]
                    palm_center_y = sum(lmList[i][1] for i in palm_indices) / len(palm_indices)
                    hand_y = palm_center_y

                    if not self._gesture_auto_calibrated:
                        self._gesture_auto_cal_samples.append(palm_center_y)
                        if len(self._gesture_auto_cal_samples) >= 15:
                            self.calibrated_hand_y = sum(self._gesture_auto_cal_samples) / len(self._gesture_auto_cal_samples)
                            self._gesture_auto_calibrated = True
                            self.after(0, lambda: self.hg_calibrate_btn.configure(
                                text=f"✅ Auto: {int(self.calibrated_hand_y)}px", state="disabled", fg_color="#888888"))
                    else:
                        rolling_avg = self.calibrated_hand_y * 0.95 + palm_center_y * 0.05
                        self.calibrated_hand_y = rolling_avg

                    index_extended = lmList[8][1] < lmList[6][1]
                    middle_extended = lmList[12][1] < lmList[10][1]
                    ring_extended = lmList[16][1] < lmList[14][1]
                    pinky_extended = lmList[20][1] < lmList[18][1]
                    extended_count = sum([index_extended, middle_extended, ring_extended, pinky_extended])
                    is_fist = extended_count <= 1

                    control_active = index_extended and not is_fist

                    center_line = self.calibrated_hand_y if self.calibrated_hand_y is not None else h // 2
                    cv2.line(frame, (0, int(center_line)), (w, int(center_line)), (100, 100, 100), 1)

                    if control_active:
                        if hand_y < center_line:
                            cv2.putText(frame, "▼", (w - 40, h - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (46, 204, 113), 3)
                        else:
                            cv2.putText(frame, "▲", (w - 40, h - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (46, 204, 113), 3)
            except Exception as e:
                print(f"Error en detección de gestos: {e}")

        if hand_found != self._h_prev["gesture"]:
            self._h_stable["gesture"] = 0
        else:
            self._h_stable["gesture"] = min(self._h_stable["gesture"] + 1, 5)
        self._h_prev["gesture"] = hand_found

        if self._h_stable["gesture"] >= 2:
            pass
        else:
            control_active = False if not hand_found else control_active
            hand_y = None if not hand_found else hand_y

        if not hand_found:
            control_active = False
            hand_y = None

        self.after(0, lambda: self.update_hand_gesture_status_ui(control_active, hand_y))

        if control_active and hand_y is not None:
            center_y = self.calibrated_hand_y if self.calibrated_hand_y is not None else h // 2
            diff = hand_y - center_y

            norm_diff = max(min(diff, 80), -80)
            progress_val = 0.5 + (norm_diff / 160.0)
            self.after(0, lambda p=progress_val: self.hg_pos_progressbar.set(p))

            abs_diff = abs(diff)
            if abs_diff > self.gesture_sensitivity:
                normalized = min((abs_diff - self.gesture_sensitivity) / 60.0, 1.0)
                speed_factor = normalized * normalized * 2.5 + 0.3
                self.scroll_amount = int(6 + speed_factor * 14)
                self.scroll_interval = max(0.02, 0.10 - speed_factor * 0.024)

                pps = self.scroll_amount / self.scroll_interval

                if hand_y < center_y - self.gesture_sensitivity:
                    self.scroll_direction = "Bajar"
                    if not self.is_scrolling:
                        self.is_scrolling = True
                        self.after(0, self.update_status_ui)
                    self.after(0, lambda p=pps: self.hg_pos_label.configure(
                        text=f"▼ {p:.0f} px/s"))
                else:
                    self.scroll_direction = "Subir"
                    if not self.is_scrolling:
                        self.is_scrolling = True
                        self.after(0, self.update_status_ui)
                    self.after(0, lambda p=pps: self.hg_pos_label.configure(
                        text=f"▲ {p:.0f} px/s"))
            else:
                if self.is_scrolling:
                    self.is_scrolling = False
                    self.after(0, self.update_status_ui)
                self.after(0, lambda: self.hg_pos_progressbar.set(0.5))
                self.after(0, lambda: self.hg_pos_label.configure(text="● Centro"))
        else:
            if self.is_scrolling:
                self.is_scrolling = False
                self.after(0, self.update_status_ui)
            self.after(0, lambda: self.hg_pos_progressbar.set(0.5))
            if hand_y is None:
                self.after(0, lambda: self.hg_pos_label.configure(text="○ Sin mano detectada"))
            else:
                self.after(0, lambda: self.hg_pos_label.configure(text="○ Gesto no válido"))

    def _process_air_mouse_mode(self, frame, hand_detector):
        h, w, _ = frame.shape
        hand_found = False
        is_pinching = False
        is_open_hand = False
        is_fist = True
        index_extended = False
        palm_center_y = None
        cur_norm = None

        if MEDIPIPE_AVAILABLE and hand_detector:
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                result = hand_detector.detect(mp_image)

                if result.hand_landmarks:
                    hand_found = True
                    hand_landmarks = result.hand_landmarks[0]
                    lmList = [[int(lm.x * w), int(lm.y * h), lm.z] for lm in hand_landmarks]

                    connections = [
                        (0, 1), (1, 2), (2, 3), (3, 4),
                        (0, 5), (5, 6), (6, 7), (7, 8),
                        (5, 9), (9, 10), (10, 11), (11, 12),
                        (9, 13), (13, 14), (14, 15), (15, 16),
                        (13, 17), (17, 18), (18, 19), (19, 20),
                        (0, 17)
                    ]
                    for start, end in connections:
                        cv2.line(frame, (lmList[start][0], lmList[start][1]),
                                 (lmList[end][0], lmList[end][1]), (46, 204, 113), 2)
                    for point in lmList:
                        cv2.circle(frame, (point[0], point[1]), 5, (46, 204, 113), -1)

                    palm_indices = [5, 9, 13, 17]
                    palm_center_y = sum(lmList[i][1] for i in palm_indices) / len(palm_indices)

                    index_extended = lmList[8][1] < lmList[6][1]
                    middle_extended = lmList[12][1] < lmList[10][1]
                    ring_extended = lmList[16][1] < lmList[14][1]
                    pinky_extended = lmList[20][1] < lmList[18][1]
                    extended_count = sum([index_extended, middle_extended, ring_extended, pinky_extended])
                    is_fist = extended_count <= 1
                    is_open_hand = extended_count >= 3

                    index_tip = lmList[8]
                    raw_x_norm = index_tip[0] / w
                    raw_y_norm = index_tip[1] / h

                    cur_norm = (raw_x_norm, raw_y_norm)

                    dx = lmList[8][0] - lmList[4][0]
                    dy = lmList[8][1] - lmList[4][1]
                    pinch_dist = (dx * dx + dy * dy) ** 0.5
                    is_pinching = pinch_dist < 25

                    cursor_display_x = int(raw_x_norm * 100)
                    cursor_display_y = int(raw_y_norm * 100)

                    if is_pinching:
                        cv2.circle(frame, (lmList[4][0], lmList[4][1]), 12, (0, 0, 255), -1)
                        cv2.circle(frame, (lmList[8][0], lmList[8][1]), 12, (0, 0, 255), -1)
                        cv2.line(frame, (lmList[4][0], lmList[4][1]),
                                 (lmList[8][0], lmList[8][1]), (0, 0, 255), 3)
                        cv2.putText(frame, "CLICK!", (lmList[8][0] + 15, lmList[8][1]),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    elif index_extended and not is_fist:
                        cv2.putText(frame, f"[{cursor_display_x}%, {cursor_display_y}%]",
                                    (lmList[8][0] + 15, lmList[8][1]),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            except Exception as e:
                print(f"Error en Air Mouse: {e}")

        if hand_found != self._h_prev["mouse"]:
            self._h_stable["mouse"] = 0
        else:
            self._h_stable["mouse"] = min(self._h_stable["mouse"] + 1, 5)
        self._h_prev["mouse"] = hand_found

        if self._h_stable["mouse"] >= 2 and index_extended and not is_fist and not is_pinching and cur_norm is not None and self._mouse_prev_pos is not None:
            dx_norm = cur_norm[0] - self._mouse_prev_pos[0]
            dy_norm = cur_norm[1] - self._mouse_prev_pos[1]

            speed = (dx_norm * dx_norm + dy_norm * dy_norm) ** 0.5
            base_gain = 600
            accel_gain = 3000
            gain = base_gain + accel_gain * speed

            try:
                screen_w, screen_h = pyautogui.size()
                move_x = int(dx_norm * gain * (screen_w / 320))
                move_y = int(dy_norm * gain * (screen_h / 240))
                if abs(move_x) > 0 or abs(move_y) > 0:
                    pyautogui.moveRel(move_x, move_y)
            except Exception:
                pass

        if cur_norm is not None:
            self._mouse_prev_pos = cur_norm

        self.pinch_detected = is_pinching
        if is_pinching and not self.prev_pinch_detected and hand_found:
            try:
                pyautogui.click()
            except Exception:
                pass
        self.prev_pinch_detected = is_pinching

        if is_open_hand and hand_found and not is_pinching:
            center_y = self.calibrated_hand_y if self.calibrated_hand_y is not None else h // 2
            diff = palm_center_y - center_y
            abs_diff = abs(diff)
            if abs_diff > self.gesture_sensitivity + 15:
                normalized = min((abs_diff - self.gesture_sensitivity - 15) / 50.0, 1.0)
                speed_factor = normalized * normalized * 2.0 + 0.3
                self.scroll_amount = int(6 + speed_factor * 12)
                self.scroll_interval = max(0.02, 0.10 - speed_factor * 0.020)
                if palm_center_y < center_y - self.gesture_sensitivity - 15:
                    self.scroll_direction = "Bajar"
                else:
                    self.scroll_direction = "Subir"
                if not self.is_scrolling:
                    self.is_scrolling = True
                    self.after(0, self.update_status_ui)
            else:
                if self.is_scrolling:
                    self.is_scrolling = False
                    self.after(0, self.update_status_ui)
        else:
            if self.is_scrolling:
                self.is_scrolling = False
                self.after(0, self.update_status_ui)

        self.after(0, self.update_hand_mouse_status_ui, hand_found, is_pinching, is_open_hand, is_fist, cur_norm, index_extended)

    def update_hand_mouse_status_ui(self, hand_found, is_pinching, is_open_hand, is_fist, cur_norm, index_extended=False):
        if not self.camera_active:
            self.hm_status_badge.configure(text="CÁMARA APAGADA", fg_color="#33333F", text_color="#888888")
            self.hm_pos_label.configure(text="● Esperando mano...")
        elif not hand_found:
            self.hm_status_badge.configure(text="MANO NO DETECTADA", fg_color="#CC3333", text_color="#FFFFFF")
            self.hm_pos_label.configure(text="● Sin mano")
        elif is_pinching:
            self.hm_status_badge.configure(text="¡CLICK!", fg_color="#FF5733", text_color="#FFFFFF")
            self.hm_pos_label.configure(text="◎ CLIC")
        elif is_fist:
            self.hm_status_badge.configure(text="PUÑO (DETENIDO)", fg_color="#CC3333", text_color="#FFFFFF")
            self.hm_pos_label.configure(text="✊ Detenido")
        elif is_open_hand:
            icon = "▼" if self.scroll_direction == "Bajar" else "▲"
            self.hm_status_badge.configure(text=f"SCROLL {icon}", fg_color="#2ECC71", text_color="#000000")
            self.hm_pos_label.configure(text=f"🖐️ Desplazando {self.scroll_direction.lower()}")
        elif cur_norm is not None and index_extended and not is_fist:
            mx = int(cur_norm[0] * 100)
            my = int(cur_norm[1] * 100)
            self.hm_status_badge.configure(text=f"🐭 ({mx}%, {my}%)", fg_color="#3498DB", text_color="#FFFFFF")
            self.hm_pos_label.configure(text=f"☝️ Moviendo cursor")
        else:
            self.hm_status_badge.configure(text="GESTO NO VÁLIDO", fg_color="#FFA500", text_color="#000000")
            self.hm_pos_label.configure(text="● Gesto no válido")

    def update_hand_gesture_status_ui(self, control_active, hand_y):
        if not self.camera_active:
            self.hg_status_badge.configure(text="CÁMARA APAGADA", fg_color="#33333F", text_color="#888888")
        elif hand_y is None:
            self.hg_status_badge.configure(text="MANO NO DETECTADA", fg_color="#CC3333", text_color="#FFFFFF")
        elif control_active:
            self.hg_status_badge.configure(text="CONTROL ACTIVO", fg_color="#2ECC71", text_color="#000000")
        else:
            self.hg_status_badge.configure(text="GESTO NO VÁLIDO", fg_color="#FFA500", text_color="#000000")

    def update_hand_status_ui(self):
        if not self.hand_detected:
            self.hand_status_badge.configure(text="NO DETECTADA", fg_color="#33333F", text_color="#888888")
        elif self.hand_closed:
            self.hand_status_badge.configure(text="PUÑO (DETENIDO)", fg_color="#CC3333", text_color="#FFFFFF")
        elif self.is_scrolling:
            dir_icon = "▼" if self.scroll_direction == "Bajar" else "▲"
            self.hand_status_badge.configure(text=f"DESPLAZANDO {dir_icon}", fg_color="#2ECC71", text_color="#000000")
        else:
            self.hand_status_badge.configure(text="MANO DETECTADA", fg_color="#FFA500", text_color="#000000")

    def update_video_preview(self, pil_image):
        if not self.camera_active:
            return
        try:
            w = pil_image.width
            h = pil_image.height
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(w, h))
            self.video_label.configure(image=ctk_image, text="")
            self.last_frame = ctk_image
        except Exception as e:
            print(f"Error al renderizar frame en UI: {e}")

    def clear_video_label(self):
        self.last_frame = None
        try:
            self.video_label.configure(
                image=None,
                text="CÁMARA APAGADA\n\nActiva el interruptor arriba\npara iniciar."
            )
        except Exception:
            pass

    def reset_camera_switch(self):
        if hasattr(self, 'webcam_switch'):
            self.webcam_switch.deselect()
            self.toggle_camera_control()

    def show_warning(self, message):
        warning_window = ctk.CTkToplevel(self)
        warning_window.title("Aviso")
        warning_window.geometry("350x150")
        warning_window.resizable(False, False)
        warning_window.attributes("-topmost", True)
        
        lbl = ctk.CTkLabel(warning_window, text=message, font=ctk.CTkFont(family="Inter", size=12), pady=20)
        lbl.pack()
        
        btn = ctk.CTkButton(warning_window, text="Entendido", command=warning_window.destroy, width=100)
        btn.pack(pady=10)

    # ----------------------------------------------------
    # INSTALACIÓN AUTOMÁTICA DE DEPENDENCIAS
    # ----------------------------------------------------
    def install_opencv_background(self):
        self.install_opencv_btn.configure(text="Instalando dependencias...", state="disabled")
        threading.Thread(target=self.run_install_dependencies, daemon=True).start()

    def run_install_dependencies(self):
        import subprocess
        try:
            python_exe = sys.executable
            subprocess.check_call([python_exe, "-m", "pip", "install", "opencv-python", "pillow", "mediapipe"])
            self.after(0, self.on_dependencies_installed_success)
        except Exception as e:
            self.after(0, lambda: self.show_warning(f"Error al instalar: {e}"))
            self.after(0, lambda: self.install_opencv_btn.configure(text="Instalar Dependencias Automáticamente", state="normal"))

    def on_dependencies_installed_success(self):
        self.show_warning("Instalación exitosa. Por favor reinicia la aplicación para activar el control por cámara.")
        self.install_opencv_btn.configure(text="Instalado. Reinicia la App", state="disabled")

    # ----------------------------------------------------
    # CIERRE DE LA APLICACIÓN
    # ----------------------------------------------------
    def on_closing(self):
        # Detener hilos y liberar recursos de manera segura antes de cerrar la ventana
        self.scroll_thread_active = False
        self.camera_active = False
        self.is_scrolling = False
        
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass

        # Esperar brevemente para que el bucle de cámara termine y libere cap
        self.after(300, self.destroy)

if __name__ == "__main__":
    app = MangaAutoscrollerApp()
    app.mainloop()
