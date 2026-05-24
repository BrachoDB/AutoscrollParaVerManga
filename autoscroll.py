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
        self.resizable(False, False)

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
        self.calibrated_y = None
        self.current_face_y = None
        self.diff_y_val = 0
        self.face_detected = False
        self.camera_thread = None
        self.sensitivity = 20  # Pixeles de tolerancia
        self.action_tilt_up = "Detener"  # Qué hacer al levantar la cabeza: "Detener" o "Subir"
        self.last_frame = None

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

        # Caja de Control por Cámara (Gesto Facial)
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
                     "pip install opencv-python pillow",
                font=ctk.CTkFont(family="Inter", size=11),
                justify="left",
                text_color="#888888"
            )
            self.webcam_help.pack(anchor="w", padx=15, pady=10)

            self.install_opencv_btn = ctk.CTkButton(
                self.webcam_card,
                text="Instalar OpenCV Automáticamente",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                fg_color="#CC3333",
                hover_color="#992222",
                command=self.install_opencv_background
            )
            self.install_opencv_btn.pack(padx=15, pady=10, fill="x")
        else:
            # Control por cámara disponible
            self.webcam_switch = ctk.CTkSwitch(
                self.webcam_card,
                text="Activar Control por Gesto Facial",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                progress_color="#2ECC71",
                command=self.toggle_camera_control
            )
            self.webcam_switch.pack(anchor="w", padx=15, pady=8)

            # Frame de cámara (Video Preview y Controles)
            self.cam_controls_frame = ctk.CTkFrame(self.webcam_card, fg_color="transparent")
            self.cam_controls_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

            # Sub-frame izquierdo: Video preview
            self.video_frame = ctk.CTkFrame(self.cam_controls_frame, width=240, height=180, fg_color="#121216")
            self.video_frame.pack_propagate(False)
            self.video_frame.pack(side="left", fill="both", expand=False)

            self.video_label = ctk.CTkLabel(
                self.video_frame,
                text="CÁMARA APAGADA\n\nActiva el interruptor arriba\npara iniciar.",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#555555"
            )
            self.video_label.pack(fill="both", expand=True)

            # Sub-frame derecho: Botón calibrar, indicadores y sensibilidad
            self.cam_settings_frame = ctk.CTkFrame(self.cam_controls_frame, fg_color="transparent")
            self.cam_settings_frame.pack(side="left", fill="both", expand=True, padx=(15, 0))

            self.calibrate_btn = ctk.CTkButton(
                self.cam_settings_frame,
                text="📍 Calibrar Centro",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                fg_color="#2ECC71",
                hover_color="#27AE60",
                text_color="#000000",
                state="disabled",
                command=self.calibrate_neutral_position
            )
            self.calibrate_btn.pack(fill="x", pady=(0, 8))

            self.calib_status_label = ctk.CTkLabel(
                self.cam_settings_frame,
                text="Estado: Sin Calibrar",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#888888",
                anchor="w"
            )
            self.calib_status_label.pack(fill="x", pady=1)

            self.face_status_label = ctk.CTkLabel(
                self.cam_settings_frame,
                text="Rostro: No detectado",
                font=ctk.CTkFont(family="Inter", size=11),
                text_color="#CC3333",
                anchor="w"
            )
            self.face_status_label.pack(fill="x", pady=1)

            # Sensibilidad
            self.sens_title = ctk.CTkLabel(
                self.cam_settings_frame,
                text="Sensibilidad del gesto:",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                anchor="w"
            )
            self.sens_title.pack(fill="x", pady=(8, 0))

            self.sens_slider = ctk.CTkSlider(
                self.cam_settings_frame,
                from_=5,
                to=40,
                number_of_steps=35,
                command=self.on_sensitivity_changed
            )
            self.sens_slider.set(self.sensitivity)
            self.sens_slider.pack(fill="x", pady=(2, 8))

            # Indicador Visual de Inclinación de Cabeza
            self.tilt_indicator_title = ctk.CTkLabel(
                self.cam_settings_frame,
                text="Inclinación actual:",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                anchor="w"
            )
            self.tilt_indicator_title.pack(fill="x")

            self.tilt_progressbar = ctk.CTkProgressBar(
                self.cam_settings_frame,
                progress_color="#2ECC71",
                fg_color="#33333F",
                height=15
            )
            self.tilt_progressbar.set(0.5)  # 0.5 representa centro
            self.tilt_progressbar.pack(fill="x", pady=(2, 5))

            # Explicación breve
            self.tilt_explain_lbl = ctk.CTkLabel(
                self.cam_settings_frame,
                text="Inclina la cabeza ligeramente\nhacia abajo para bajar.",
                font=ctk.CTkFont(family="Inter", size=10, slant="italic"),
                text_color="#888888",
                justify="left",
                anchor="w"
            )
            self.tilt_explain_lbl.pack(fill="x", pady=(2, 0))

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

    def on_sensitivity_changed(self, value):
        self.sensitivity = int(value)

    def on_hotkey_changed(self, value):
        self.selected_hotkey = value
        if PYNPUT_AVAILABLE:
            self.start_keyboard_listener()

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
    # WEBCAM Y PROCESAMIENTO FACIAL
    # ----------------------------------------------------
    def toggle_camera_control(self):
        if not OPENCV_AVAILABLE:
            return

        self.camera_enabled = self.webcam_switch.get()
        
        if self.camera_enabled:
            # Iniciar hilo de cámara
            self.camera_active = True
            self.calibrate_btn.configure(state="normal")
            self.camera_thread = threading.Thread(target=self.camera_worker, daemon=True)
            self.camera_thread.start()
        else:
            # Detener cámara
            self.camera_active = False
            self.calibrate_btn.configure(state="disabled")
            self.calib_status_label.configure(text="Estado: Sin Calibrar", text_color="#888888")
            self.face_status_label.configure(text="Rostro: Desactivado", text_color="#888888")
            self.tilt_progressbar.set(0.5)
            self.calibrated_y = None
            self.current_face_y = None
            self.diff_y_val = 0
            
            # Detener scroll si estaba activo por la cámara
            if self.is_scrolling:
                self.is_scrolling = False
                self.update_status_ui()
                
            # Limpiar preview de video
            self.after(200, self.clear_video_label)

    def calibrate_neutral_position(self):
        if not self.face_detected or self.current_face_y is None:
            self.calib_status_label.configure(text="¡Rostro no detectado!", text_color="#CC3333")
            return
        
        self.calibrated_y = self.current_face_y
        self.calib_status_label.configure(
            text=f"Calibrado (Y={self.calibrated_y}px)", 
            text_color="#2ECC71"
        )

    def camera_worker(self):
        # Cargar el detector de rostros frontal de OpenCV Haar Cascades
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        except Exception as e:
            print(f"Error al cargar cascada de rostros: {e}")
            self.after(0, lambda: self.show_warning("Error al cargar detector facial."))
            return

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

        while self.camera_active:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            # Voltear la cámara para efecto espejo
            frame = cv2.flip(frame, 1)
            h_frame, w_frame, _ = frame.shape
            
            # Convertir a escala de grises para el detector de Haar
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detectar rostros
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(80, 80)
            )

            # Bandera temporal de detección
            face_detected_this_frame = len(faces) > 0

            if face_detected_this_frame:
                # Tomar el rostro más grande (más cercano)
                faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
                x, y, w, h = faces[0]
                
                # Calcular el centro del rostro (eje Y es el relevante para inclinar cabeza)
                face_center_y = y + h // 2
                self.current_face_y = face_center_y
                self.face_detected = True

                # Dibujar bounding box y punto central en el frame de video
                cv2.rectangle(frame, (x, y), (x+w, y+h), (46, 204, 113), 2)  # Verde brillante
                cv2.circle(frame, (x + w//2, face_center_y), 4, (231, 76, 60), -1)  # Punto rojo en el centro

                # Si ya calibramos, procesar la inclinación
                if self.calibrated_y is not None:
                    # En cámara, Y va de arriba a abajo.
                    # Si face_center_y aumenta, el rostro bajó (cabeza inclinada abajo).
                    # Si face_center_y disminuye, el rostro subió (cabeza levantada).
                    diff_y = face_center_y - self.calibrated_y
                    self.diff_y_val = diff_y

                    # Límite para mapeo visual (de -60px a +60px)
                    normalized_diff = max(min(diff_y, 60), -60)
                    # Convertir a escala de 0.0 a 1.0 para el ProgressBar de CustomTkinter (0.5 es centro)
                    progress_val = 0.5 + (normalized_diff / 120.0)
                    self.after(0, lambda p=progress_val: self.tilt_progressbar.set(p))

                    # Decidir acción de desplazamiento
                    if diff_y > self.sensitivity:
                        # Cabeza hacia ABAJO -> Activar autoscroll para BAJAR manga
                        if not self.is_scrolling or self.scroll_direction != "Bajar":
                            self.scroll_direction = "Bajar"
                            self.is_scrolling = True
                            self.after(0, self.update_status_ui)
                    elif diff_y < -self.sensitivity:
                        # Cabeza hacia ARRIBA -> Detener o Subir
                        if self.action_tilt_up == "Subir":
                            if not self.is_scrolling or self.scroll_direction != "Subir":
                                self.scroll_direction = "Subir"
                                self.is_scrolling = True
                                self.after(0, self.update_status_ui)
                        else:
                            if self.is_scrolling:
                                self.is_scrolling = False
                                self.after(0, self.update_status_ui)
                    else:
                        # Rango neutral -> Detener scroll
                        if self.is_scrolling:
                            self.is_scrolling = False
                            self.after(0, self.update_status_ui)
                else:
                    self.after(0, lambda: self.tilt_progressbar.set(0.5))
                
                # Actualizar estados de rostro en UI
                self.after(0, self.update_face_detected_ui, True)
            else:
                self.face_detected = False
                self.current_face_y = None
                self.after(0, self.update_face_detected_ui, False)
                
                # Por seguridad, si no hay rostro detectado, pausamos el scroll
                if self.is_scrolling:
                    self.is_scrolling = False
                    self.after(0, self.update_status_ui)

            # Redimensionar el frame para la vista previa de la UI (240x180)
            frame_resized = cv2.resize(frame, (240, 180))
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

    def update_video_preview(self, pil_image):
        if not self.camera_active:
            return
        try:
            # Convertir imagen PIL en PhotoImage de CustomTkinter/Tkinter
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(240, 180))
            self.video_label.configure(image=ctk_image, text="")
            # Guardar referencia para evitar recolección de basura
            self.last_frame = ctk_image
        except Exception as e:
            print(f"Error al renderizar frame en UI: {e}")

    def clear_video_label(self):
        self.video_label.configure(
            image=None, 
            text="CÁMARA APAGADA\n\nActiva el interruptor arriba\npara iniciar."
        )
        self.last_frame = None

    def update_face_detected_ui(self, detected):
        if detected:
            self.face_status_label.configure(text="Rostro: DETECTADO ✅", text_color="#2ECC71")
        else:
            self.face_status_label.configure(text="Rostro: No detectado ⚠️", text_color="#CC3333")

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
    # INSTALACIÓN AUTOMÁTICA DE OPENCV Y PILLOW
    # ----------------------------------------------------
    def install_opencv_background(self):
        self.install_opencv_btn.configure(text="Instalando dependencias...", state="disabled")
        threading.Thread(target=self.run_install_dependencies, daemon=True).start()

    def run_install_dependencies(self):
        import subprocess
        try:
            # Obtener el ejecutable de Python correspondiente (soporta venv)
            python_exe = sys.executable
            subprocess.check_call([python_exe, "-m", "pip", "install", "opencv-python", "pillow"])
            self.after(0, self.on_dependencies_installed_success)
        except Exception as e:
            self.after(0, lambda: self.show_warning(f"Error al instalar: {e}"))
            self.after(0, lambda: self.install_opencv_btn.configure(text="Instalar OpenCV Automáticamente", state="normal"))

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
