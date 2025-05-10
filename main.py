import tkinter as tk
from tkinter import ttk, scrolledtext, colorchooser, Menu, messagebox
import sounddevice as sd
import numpy as np
import queue
import threading
import sys 
from faster_whisper import WhisperModel
import translators as ts 

# --- New Color Palette ---
CP_MAIN_BG = "#6E4555"         # Dark Mauve (Main Background)
CP_MAIN_TEXT = "#F5E3E0"       # Lightest Pink/Off-White (Main Text)
CP_SECONDARY_TEXT = "#E8B4BC"  # Light Pink (Translation, less prominent labels)
CP_ACCENT_BG1 = "#3A3238"      # Darkest Brown/Purple (Caption Area Background)
CP_ACCENT_BG2 = "#D282A6"      # Medium Pink (Speaker Info, Progress Trough, some button accents)

# --- Constants using the new palette ---
DARK_GRAY_BG = CP_MAIN_BG
LIGHT_GRAY_TEXT = CP_MAIN_TEXT
CAPTION_AREA_BG = CP_ACCENT_BG1
CAPTION_TEXT_WHITE = CP_MAIN_TEXT 
SPEAKER_INFO_BG = CP_ACCENT_BG2
PROGRESS_BAR_TROUGH_COLOR = CP_ACCENT_BG2 
PROGRESS_BAR_FG_COLOR = CP_MAIN_TEXT # Progress bar fill
TRANSLATION_TEXT_COLOR = CP_SECONDARY_TEXT 

# Button Colors from Palette
BTN_START_BG = CP_SECONDARY_TEXT 
BTN_START_FG = CP_MAIN_BG        
BTN_STOP_BG = CP_ACCENT_BG2      
BTN_STOP_FG = CP_MAIN_TEXT       
BTN_CLEAR_BG = CP_ACCENT_BG1     
BTN_CLEAR_FG = CP_MAIN_TEXT      
SETTINGS_ICON_COLOR = CP_MAIN_TEXT
SWITCH_SPK_BTN_BG = CP_ACCENT_BG1
SWITCH_SPK_BTN_FG = CP_MAIN_TEXT


class LiveTranscriberApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Enhanced Live Captions Tool")
        self.root.configure(bg=DARK_GRAY_BG)
        self.root.minsize(800, 600)

        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.transcription_thread = None
        self.stream = None
        self.selected_device_id = None
        self.current_audio_level = 0.0 # For audio visualizer
        
        self.faster_whisper_model_size = "base" 
        
        self.speakers = {
            1: {"nickname": "Speaker 1", "color": "#FFB6C1"}, # LightPink as a default
            2: {"nickname": "Speaker 2", "color": "#ADD8E6"}  # LightBlue as a default
        }
        self.active_speaker = 1
        self.speaker_colors_vars = {1: tk.StringVar(value=self.speakers[1]["color"]),
                                    2: tk.StringVar(value=self.speakers[2]["color"])}
        self.speaker_nicknames_vars = {1: tk.StringVar(value=self.speakers[1]["nickname"]),
                                       2: tk.StringVar(value=self.speakers[2]["nickname"])}

        self.current_language_from_settings = "en" 
        self.transcription_lang_cycle = ["en", "es"] 
        self.current_lang_cycle_idx = 0 

        try:
            self.model = WhisperModel(self.faster_whisper_model_size, device="cpu", compute_type="int8")
            print(f"Successfully loaded Faster Whisper model: {self.faster_whisper_model_size}")
        except Exception as e:
            messagebox.showerror("Model Error", f"Failed to load Faster Whisper model: {e}\nPlease ensure '{self.faster_whisper_model_size}' is a valid multilingual model and dependencies (like ctranslate2, translators) are installed correctly.")
            self.root.destroy()
            return

        self.setup_styles()
        self.create_main_layout()
        self.create_settings_sidebar()
        
        self.update_device_list()
        if self.input_devices and not self.selected_device_id:
            self.selected_device_id = self.input_devices[0][0] 
            self.device_var.set(f"{self.input_devices[0][0]}: {self.input_devices[0][1]}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<space>", self.spacebar_action_event) 
        self.update_audio_visualizer() # Start the visualizer loop

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam') 

        self.style.configure("TFrame", background=DARK_GRAY_BG)
        self.style.configure("TLabel", background=DARK_GRAY_BG, foreground=LIGHT_GRAY_TEXT, font=("Arial", 10))
        
        self.style.configure("TMenubutton", background=CP_ACCENT_BG1, foreground=LIGHT_GRAY_TEXT, font=("Arial", 10), borderwidth=0, relief=tk.FLAT, arrowcolor=LIGHT_GRAY_TEXT)
        self.style.map("TMenubutton", background=[('active', CP_SECONDARY_TEXT)])
        
        self.style.configure("Horizontal.TProgressbar", troughcolor=PROGRESS_BAR_TROUGH_COLOR, background=PROGRESS_BAR_FG_COLOR, thickness=10, borderwidth=0)
        
        self.style.configure("Settings.TFrame", background=CP_ACCENT_BG2) 
        self.style.configure("Settings.TLabel", background=CP_ACCENT_BG2, foreground=LIGHT_GRAY_TEXT, font=("Arial", 10))
        self.style.configure("Settings.TButton", background=CP_ACCENT_BG1, foreground=LIGHT_GRAY_TEXT, font=("Arial", 9), relief=tk.FLAT, borderwidth=0, padding=5) 
        self.style.map("Settings.TButton", background=[('active', CP_MAIN_BG)]) 
        self.style.configure("Settings.TEntry", fieldbackground=CP_ACCENT_BG1, foreground=LIGHT_GRAY_TEXT, insertbackground=LIGHT_GRAY_TEXT, font=("Arial", 9), borderwidth=0, relief=tk.FLAT, padding=3)
        self.style.configure("Settings.TCombobox", 
                             fieldbackground=CP_ACCENT_BG1, 
                             background=CP_ACCENT_BG1, 
                             foreground=LIGHT_GRAY_TEXT, 
                             arrowcolor=LIGHT_GRAY_TEXT, 
                             selectbackground=CP_MAIN_BG, 
                             selectforeground=LIGHT_GRAY_TEXT, 
                             borderwidth=0, relief=tk.FLAT, padding=3)
        self.style.map("Settings.TCombobox",
                       fieldbackground=[('readonly', CP_ACCENT_BG1)],
                       selectbackground=[('readonly', CP_MAIN_BG)],
                       selectforeground=[('readonly', LIGHT_GRAY_TEXT)],
                       foreground=[('readonly', LIGHT_GRAY_TEXT)],
                       arrowcolor=[('readonly', LIGHT_GRAY_TEXT)])


    def create_main_layout(self):
        self.top_bar_frame = ttk.Frame(self.root, style="TFrame")
        self.top_bar_frame.pack(side=tk.TOP, fill=tk.X, pady=(10,5), padx=10)

        # Progress bar will now be an audio visualizer
        self.audio_level_bar = ttk.Progressbar(self.top_bar_frame, mode='determinate', style="Horizontal.TProgressbar", length=100)
        self.audio_level_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))
        self.audio_level_bar['value'] = 0

        self.controls_frame = ttk.Frame(self.top_bar_frame, style="TFrame")
        self.controls_frame.pack(side=tk.RIGHT)

        self.start_stop_button = tk.Button(self.controls_frame, text="▶ Start", command=self.toggle_transcription, 
                                           bg=BTN_START_BG, fg=BTN_START_FG, font=("Arial", 10, "bold"), width=8, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        self.start_stop_button.pack(side=tk.LEFT, padx=3)

        self.clear_button = tk.Button(self.controls_frame, text="Clear", command=self.clear_text_history,
                                      bg=BTN_CLEAR_BG, fg=BTN_CLEAR_FG, font=("Arial", 10, "bold"), width=6, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        self.clear_button.pack(side=tk.LEFT, padx=3)

        self.settings_button = tk.Button(self.controls_frame, text="⚙", command=self.toggle_settings_sidebar,
                                         bg=DARK_GRAY_BG, fg=SETTINGS_ICON_COLOR, font=("Arial", 14, "bold"), relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        self.settings_button.pack(side=tk.LEFT, padx=(3,0))

        self.speaker_info_frame = tk.Frame(self.root, bg=SPEAKER_INFO_BG, height=40) 
        self.speaker_info_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,5), padx=10)
        self.speaker_info_frame.pack_propagate(False) 

        self.speaker_label = tk.Label(self.speaker_info_frame, text=f"Active: {self.speakers[self.active_speaker]['nickname']}", 
                                      bg=SPEAKER_INFO_BG, fg=LIGHT_GRAY_TEXT, font=("Arial", 11))
        self.speaker_label.pack(side=tk.LEFT, padx=(10,5), pady=5)

        self.speaker_color_indicator = tk.Frame(self.speaker_info_frame, width=20, height=20, relief=tk.FLAT, borderwidth=1,
                                                bg=self.speakers[self.active_speaker]['color'])
        self.speaker_color_indicator.pack(side=tk.LEFT, padx=(0,15), pady=5)

        # This label is now part of the "Switch Spk/Lang" button text
        # self.transcription_language_label = tk.Label(...) 
        # self.transcription_language_label.pack(...)

        # "Switch Spk" button now also handles language and updates its text
        initial_btn_lang = self.transcription_lang_cycle[self.current_lang_cycle_idx].upper()
        self.switch_speaker_lang_button = tk.Button(self.speaker_info_frame, text=f"Switch ({initial_btn_lang})", command=self.spacebar_action_event,
                                               bg=SWITCH_SPK_BTN_BG, fg=SWITCH_SPK_BTN_FG, font=("Arial", 9, "bold"), relief=tk.FLAT, borderwidth=0, highlightthickness=0, width=12)
        self.switch_speaker_lang_button.pack(side=tk.RIGHT, padx=10, pady=5)


        self.caption_outer_frame = tk.Frame(self.root, bg=DARK_GRAY_BG) 
        self.caption_outer_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        
        self.caption_display_area = scrolledtext.ScrolledText(
            self.caption_outer_frame, wrap=tk.WORD, bg=CAPTION_AREA_BG, fg=CAPTION_TEXT_WHITE, 
            font=("Arial", 14), relief=tk.FLAT, borderwidth=0, insertbackground=CAPTION_TEXT_WHITE,
            padx=10, pady=10, state=tk.DISABLED 
        )
        self.caption_display_area.pack(fill=tk.BOTH, expand=True)
        
        self.caption_display_area.tag_configure("speaker1_nick", foreground=self.speakers[1]['color'], font=("Arial", 14, "bold"))
        self.caption_display_area.tag_configure("speaker2_nick", foreground=self.speakers[2]['color'], font=("Arial", 14, "bold"))
        self.caption_display_area.tag_configure("translation_style", foreground=TRANSLATION_TEXT_COLOR, font=("Arial", 11, "italic"), lmargin1=20, lmargin2=20)


    def create_settings_sidebar(self):
        self.settings_sidebar_visible = False
        self.settings_sidebar = tk.Frame(self.root, bg=CP_ACCENT_BG2, width=300, relief=tk.FLAT, borderwidth=0) 
        
        header_frame = tk.Frame(self.settings_sidebar, bg=CP_ACCENT_BG2)
        header_frame.pack(fill=tk.X, pady=(5,0))

        tk.Label(header_frame, text="Settings", font=("Arial", 16, "bold"), bg=CP_ACCENT_BG2, fg=LIGHT_GRAY_TEXT).pack(side=tk.LEFT, padx=10, pady=5)
        close_btn = tk.Button(header_frame, text="✕", command=self.toggle_settings_sidebar, bg=CP_ACCENT_BG2, fg=LIGHT_GRAY_TEXT, font=("Arial", 12, "bold"), relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        close_btn.pack(side=tk.RIGHT, padx=5)

        settings_content_canvas = tk.Canvas(self.settings_sidebar, bg=CP_ACCENT_BG2, highlightthickness=0, borderwidth=0)
        settings_content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        settings_scrollbar = ttk.Scrollbar(self.settings_sidebar, orient="vertical", command=settings_content_canvas.yview)
        settings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollable_settings_frame = ttk.Frame(settings_content_canvas, style="Settings.TFrame")
        self.scrollable_settings_frame.bind(
            "<Configure>", 
            lambda e: settings_content_canvas.configure(scrollregion=settings_content_canvas.bbox("all"))
        )
        settings_content_canvas.create_window((0, 0), window=self.scrollable_settings_frame, anchor="nw")
        settings_content_canvas.configure(yscrollcommand=settings_scrollbar.set)

        content_frame = self.scrollable_settings_frame

        ttk.Label(content_frame, text="Audio Input Device:", style="Settings.TLabel").pack(anchor=tk.W, padx=10, pady=(10,0))
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(content_frame, textvariable=self.device_var, state="readonly", width=35, font=("Arial", 9), style="Settings.TCombobox")
        self.device_dropdown.pack(pady=(0,10), padx=10, fill=tk.X)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.on_device_select)
        
        ttk.Label(content_frame, text="Default Language (Overrides Spacebar on Select):", style="Settings.TLabel").pack(anchor=tk.W, padx=10)
        self.languages_map = {"Auto-Detect": None, "English": "en", "Spanish": "es", "French": "fr", "German": "de", "Chinese": "zh", "Japanese": "ja", "Korean": "ko", "Italian": "it", "Russian": "ru", "Portuguese": "pt"}
        initial_lang_key = [k for k,v in self.languages_map.items() if v == self.current_language_from_settings]
        initial_lang_key = initial_lang_key[0] if initial_lang_key else "English" 
        self.language_var = tk.StringVar(value=initial_lang_key)
        
        lang_options = list(self.languages_map.keys())
        self.language_dropdown = ttk.OptionMenu(content_frame, self.language_var, self.language_var.get(), *lang_options, command=self.on_language_select_from_settings, style="TMenubutton")
        self.language_dropdown.config(width=33)
        self.language_dropdown.pack(pady=(0,10), padx=10, fill=tk.X)

        for i in [1, 2]: 
            ttk.Label(content_frame, text=f"Speaker {i} Nickname:", style="Settings.TLabel").pack(anchor=tk.W, padx=10, pady=(10,0))
            entry = ttk.Entry(content_frame, textvariable=self.speaker_nicknames_vars[i], width=30, style="Settings.TEntry") 
            entry.pack(pady=(0,5), padx=10, fill=tk.X)
            
            color_button_frame = ttk.Frame(content_frame, style="Settings.TFrame") 
            color_button_frame.pack(fill=tk.X, padx=10)
            
            btn = ttk.Button(color_button_frame, text=f"Speaker {i} Color", command=lambda spk=i: self.pick_speaker_color(spk), style="Settings.TButton", width=20)
            btn.pack(side=tk.LEFT, pady=(0,5), expand=True)
            
            preview = tk.Frame(color_button_frame, bg=self.speakers[i]['color'], width=25, height=25, relief=tk.FLAT, borderwidth=1) # Flat relief
            preview.pack(side=tk.LEFT, padx=5, pady=(0,5))
            if i == 1: self.s1_color_preview = preview
            else: self.s2_color_preview = preview

        ttk.Label(content_frame, text="Whisper Model Size:", style="Settings.TLabel").pack(anchor=tk.W, padx=10, pady=(10,0))
        model_sizes = ["tiny", "base", "small", "medium", "large-v2", "large-v3"] 
        self.model_size_var = tk.StringVar(value=self.faster_whisper_model_size)
        self.model_size_dropdown = ttk.OptionMenu(content_frame, self.model_size_var, self.faster_whisper_model_size, *model_sizes, command=self.on_model_size_select, style="TMenubutton")
        self.model_size_dropdown.config(width=33)
        self.model_size_dropdown.pack(pady=(0,5), padx=10, fill=tk.X)
        tk.Label(content_frame, text="(Restart required to change model)", font=("Arial", 8), bg=CP_ACCENT_BG2, fg=LIGHT_GRAY_TEXT).pack(padx=10, pady=(0,10), anchor=tk.W)

        apply_button = ttk.Button(content_frame, text="Apply Speaker Settings", command=self.apply_speaker_settings, style="Settings.TButton")
        apply_button.pack(pady=20, padx=10, fill=tk.X)

    def update_device_list(self):
        try:
            devices = sd.query_devices()
            self.input_devices = [(i, d['name']) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
            if self.input_devices:
                self.device_dropdown['values'] = [f"{i}: {name}" for i, name in self.input_devices]
                if not self.selected_device_id and self.input_devices: 
                     self.device_dropdown.current(0)
                     self.on_device_select() 
            else:
                self.device_dropdown['values'] = ["No input devices found"]
                self.device_dropdown.current(0)
                self.selected_device_id = None
        except Exception as e:
            messagebox.showerror("Audio Device Error", f"Could not query audio devices: {e}")
            self.input_devices = []
            self.selected_device_id = None
            if hasattr(self, 'device_dropdown'): 
                self.device_dropdown['values'] = ["Error loading devices"]
                self.device_dropdown.current(0)

    def on_device_select(self, event=None):
        if not self.input_devices: 
            self.selected_device_id = None
            return
        try:
            selection = self.device_var.get()
            self.selected_device_id = int(selection.split(":")[0]) 
            print(f"Selected audio input device ID: {self.selected_device_id}")
        except (ValueError, IndexError): 
            if self.input_devices: 
                self.selected_device_id = self.input_devices[0][0]
                self.device_var.set(f"{self.input_devices[0][0]}: {self.input_devices[0][1]}")
            else:
                self.selected_device_id = None
        except Exception as e: 
            print(f"Error selecting device: {e}", file=sys.stderr)
            self.selected_device_id = None

    def on_language_select_from_settings(self, selected_lang_key):
        self.current_language_from_settings = self.languages_map.get(selected_lang_key, "en") 
        print(f"Settings language selected: {self.current_language_from_settings or 'Auto-Detect'}")
        if self.current_language_from_settings == "en":
            self.current_lang_cycle_idx = self.transcription_lang_cycle.index("en")
        elif self.current_language_from_settings == "es":
            self.current_lang_cycle_idx = self.transcription_lang_cycle.index("es")
        self.update_ui_language_indicators()


    def on_model_size_select(self, selected_model_size):
        if selected_model_size != self.faster_whisper_model_size:
            if ".en" in selected_model_size and ("es" in self.transcription_lang_cycle): 
                 messagebox.showwarning("Model Incompatible", f"Model '{selected_model_size}' is English-only. For Spanish transcription or toggling, a multilingual model (e.g., 'base', 'small') is required. Please restart to apply a multilingual model if needed.")
            self.faster_whisper_model_size = selected_model_size
            messagebox.showinfo("Model Change", f"Model size set to '{selected_model_size}'.\nPlease restart the application for the change to take effect.")

    def pick_speaker_color(self, speaker_id):
        current_color = self.speakers[speaker_id]['color']
        color_code = colorchooser.askcolor(title=f"Choose color for {self.speakers[speaker_id]['nickname']}", initialcolor=current_color)
        if color_code and color_code[1]: 
            self.speaker_colors_vars[speaker_id].set(color_code[1])
            if speaker_id == 1: self.s1_color_preview.config(bg=color_code[1])
            else: self.s2_color_preview.config(bg=color_code[1])
            self.caption_display_area.tag_configure(f"speaker{speaker_id}_nick", foreground=color_code[1])

    
    def apply_speaker_settings(self):
        self.speakers[1]['nickname'] = self.speaker_nicknames_vars[1].get() or "Speaker 1" 
        self.speakers[1]['color'] = self.speaker_colors_vars[1].get()
        self.speakers[2]['nickname'] = self.speaker_nicknames_vars[2].get() or "Speaker 2" 
        self.speakers[2]['color'] = self.speaker_colors_vars[2].get()
        
        self.s1_color_preview.config(bg=self.speakers[1]['color'])
        self.s2_color_preview.config(bg=self.speakers[2]['color'])
        
        self.caption_display_area.tag_configure("speaker1_nick", foreground=self.speakers[1]['color'])
        self.caption_display_area.tag_configure("speaker2_nick", foreground=self.speakers[2]['color'])

        self.update_speaker_info_display() 
        messagebox.showinfo("Settings Applied", "Speaker nicknames and colors have been updated!")

    def toggle_settings_sidebar(self):
        if self.settings_sidebar_visible:
            self.settings_sidebar.place_forget() 
        else:
            self.settings_sidebar.place(relx=0, rely=0, relwidth=0.4, relheight=1) 
            self.settings_sidebar.tkraise() 
        self.settings_sidebar_visible = not self.settings_sidebar_visible

    def update_speaker_info_display(self):
        self.speaker_label.config(text=f"Active: {self.speakers[self.active_speaker]['nickname']}")
        self.speaker_color_indicator.config(bg=self.speakers[self.active_speaker]['color'])

    def toggle_active_speaker_only_event(self, event=None): 
        """Legacy function, spacebar_action_event is primary now for this button."""
        self.spacebar_action_event()


    def spacebar_action_event(self, event=None):
        # Toggle transcription language
        self.current_lang_cycle_idx = (self.current_lang_cycle_idx + 1) % len(self.transcription_lang_cycle)
        
        # Toggle active speaker
        self.active_speaker = 2 if self.active_speaker == 1 else 1
        
        self.update_ui_language_indicators() # Updates both speaker and language displays
        print(f"Transcription language toggled to: {self.transcription_lang_cycle[self.current_lang_cycle_idx].upper()}")
        print(f"Active speaker toggled to: {self.speakers[self.active_speaker]['nickname']}")


    def update_ui_language_indicators(self):
        # Update speaker display
        self.speaker_label.config(text=f"Active: {self.speakers[self.active_speaker]['nickname']}")
        self.speaker_color_indicator.config(bg=self.speakers[self.active_speaker]['color'])
        
        # Update language display on the "Switch (Lang)" button
        lang_code = self.transcription_lang_cycle[self.current_lang_cycle_idx]
        self.switch_speaker_lang_button.config(text=f"Switch ({lang_code.upper()})")


    def clear_text_history(self):
        self.caption_display_area.config(state=tk.NORMAL) 
        self.caption_display_area.delete(1.0, tk.END)    
        self.caption_display_area.config(state=tk.DISABLED) 
        self.audio_level_bar['value'] = 0 # Reset audio visualizer too

    def add_caption_line(self, original_text, speaker_id):
        self.caption_display_area.config(state=tk.NORMAL)
        speaker_nickname = self.speakers[speaker_id]['nickname']
        nick_tag = f"speaker{speaker_id}_nick"
        
        self.caption_display_area.insert(tk.END, speaker_nickname + ": ", (nick_tag,))
        self.caption_display_area.insert(tk.END, original_text + "\n")

        source_lang = self.transcription_lang_cycle[self.current_lang_cycle_idx]
        target_lang_idx = (self.current_lang_cycle_idx + 1) % len(self.transcription_lang_cycle)
        target_lang = self.transcription_lang_cycle[target_lang_idx]
        translated_text_display = ""
        try:
            if original_text.strip(): 
                translated_text_api = ts.translate_text(original_text, to_language=target_lang, from_language=source_lang)
                translated_text_display = f"  ↳ {target_lang.upper()}: {translated_text_api}"
            else:
                translated_text_display = "" 
        except Exception as e:
            print(f"Translation Error: {e}", file=sys.stderr)
            translated_text_display = f"  ↳ {target_lang.upper()}: [Translation not available]"
        
        if translated_text_display: 
            self.caption_display_area.insert(tk.END, translated_text_display + "\n", ("translation_style",))
        
        self.caption_display_area.see(tk.END) 
        self.caption_display_area.config(state=tk.DISABLED)

    def update_audio_visualizer(self):
        """Periodically updates the audio level bar."""
        # Scale current_audio_level (0.0 to ~50.0 or more) to 0-100 for progress bar
        # This scaling factor (2) is arbitrary and might need adjustment based on typical input levels.
        scaled_level = min(self.current_audio_level * 2, 100) 
        self.audio_level_bar['value'] = scaled_level
        self.root.after(50, self.update_audio_visualizer) # Update every 50ms


    def audio_callback(self, indata, frames, time, status):
        if status:
            print("Audio callback status:", status, file=sys.stderr) 
        self.audio_queue.put(indata.copy()) 
        # Calculate RMS for volume visualization
        volume_norm = np.linalg.norm(indata) * 10  # Multiplier to make it more visible
        self.current_audio_level = volume_norm


    def transcribe_loop_threaded(self):
        sample_rate = 16000 
        chunk_duration_s = 4 
        buffer = np.empty((0, 1), dtype=np.float32) 

        while self.is_listening:
            try:
                audio_data_chunk = self.audio_queue.get(timeout=0.1) 
                buffer = np.concatenate((buffer, audio_data_chunk), axis=0)

                if buffer.shape[0] >= sample_rate * chunk_duration_s:
                    process_chunk = buffer[:sample_rate * chunk_duration_s]
                    buffer = buffer[sample_rate * chunk_duration_s:] 
                    audio_np = process_chunk[:, 0].astype(np.float32) 
                    
                    # Audio visualizer is now updated independently by update_audio_visualizer
                    # No self.audio_level_bar.step() here.

                    transcription_language = self.transcription_lang_cycle[self.current_lang_cycle_idx]
                    effective_transcription_language = transcription_language
                    if self.current_language_from_settings is not None and \
                       self.current_language_from_settings not in self.transcription_lang_cycle:
                        effective_transcription_language = self.current_language_from_settings
                    elif self.current_language_from_settings is None: 
                         effective_transcription_language = None

                    segments, info = self.model.transcribe(audio_np, 
                                                           beam_size=5, 
                                                           language=effective_transcription_language, 
                                                           vad_filter=True, 
                                                           vad_parameters=dict(min_silence_duration_ms=500)
                                                           )
                    transcribed_text = "".join(segment.text + " " for segment in segments).strip()
                    if transcribed_text: 
                        self.root.after(0, self.add_caption_line, transcribed_text, self.active_speaker)
            except queue.Empty:
                continue 
            except Exception as e:
                error_message = f"Transcription error: {str(e)[:100]}" 
                print(error_message, file=sys.stderr)
                self.root.after(0, self.add_caption_line, f"[Error: {error_message}]", self.active_speaker)
                break 
        if self.stream and not self.stream.closed:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"Error stopping audio stream in transcription loop: {e}", file=sys.stderr)
        self.stream = None
        print("Transcription loop has ended.")
        self.root.after(0, self.update_button_state) 

    def toggle_transcription(self):
        if self.is_listening:
            self.is_listening = False 
            print("Transcription stopping requested...")
        else:
            if self.selected_device_id is None:
                self.update_device_list() 
                if not self.input_devices or self.selected_device_id is None:
                    messagebox.showerror("Audio Device Error", "No input audio device selected or available. Please check settings and ensure a microphone is connected.")
                    return

            self.is_listening = True
            display_lang = self.transcription_lang_cycle[self.current_lang_cycle_idx].upper()
            if self.current_language_from_settings is not None and \
               self.current_language_from_settings not in self.transcription_lang_cycle:
                display_lang = f"{self.current_language_from_settings.upper()} (from settings)"
            elif self.current_language_from_settings is None:
                 display_lang = "Auto-Detect (from settings)"

            print(f"Starting transcription. Device ID: {self.selected_device_id}, Effective Language: {display_lang}")
            
            try:
                while not self.audio_queue.empty(): self.audio_queue.get_nowait()

                self.stream = sd.InputStream(
                    device=self.selected_device_id, channels=1, samplerate=16000, 
                    callback=self.audio_callback, dtype='float32' 
                )
                self.stream.start()
                
                self.transcription_thread = threading.Thread(target=self.transcribe_loop_threaded, daemon=True) 
                self.transcription_thread.start()
            except Exception as e:
                messagebox.showerror("Audio Stream Error", f"Failed to start audio stream: {e}")
                self.is_listening = False 
                if self.stream: 
                    if not self.stream.closed: self.stream.close()
                self.stream = None
        self.update_button_state() 

    def update_button_state(self):
        if self.is_listening:
            self.start_stop_button.config(text="⏹ Stop", bg=BTN_STOP_BG, fg=BTN_STOP_FG)
        else:
            self.start_stop_button.config(text="▶ Start", bg=BTN_START_BG, fg=BTN_START_FG)
            # Don't reset audio_level_bar here, visualizer loop handles it or it shows last level
            # self.audio_level_bar['value'] = 0 


    def on_closing(self):
        print("Closing application...")
        self.is_listening = False 
        if self.transcription_thread and self.transcription_thread.is_alive():
            print("Waiting for transcription thread to finish...")
            self.transcription_thread.join(timeout=2.0) 
        if self.stream and not self.stream.closed:
            try:
                self.stream.stop()
                self.stream.close()
                print("Audio stream closed successfully on exit.")
            except Exception as e:
                print(f"Error closing audio stream on exit: {e}", file=sys.stderr)
        self.root.destroy() 

if __name__ == "__main__":
    main_root = tk.Tk()
    app = LiveTranscriberApp(main_root)
    main_root.mainloop()
