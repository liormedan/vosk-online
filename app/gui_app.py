### DEBUG ### Script execution starting...
import sys
import os
# import json # Unused
import queue
import threading
# import time # Unused
print("### DEBUG ### Basic imports successful.") # DEBUG

# --- בדיקת ייבוא ספריות קריטיות ---
try:
    import sounddevice as sd
    print("### DEBUG ### sounddevice imported.") # DEBUG
    # import numpy as np # Unused in current state
    print("### DEBUG ### numpy imported.") # DEBUG
    import vosk
    print("### DEBUG ### vosk imported.") # DEBUG
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QPushButton, QLabel, QStatusBar, QComboBox,
        QProgressBar, QMessageBox, QButtonGroup, QCheckBox # Added QCheckBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject # Removed QSize, QThread
    from PyQt6.QtGui import QClipboard # Removed QPalette, QColor, QFont, QIcon
    print("### DEBUG ### PyQt6 imported successfully.") # DEBUG
except ImportError as e:
    print(f"FATAL ERROR: Could not import required library: {e}", file=sys.stderr)
    print("Please ensure PyQt6, vosk, sounddevice, and numpy are installed in your virtual environment.", file=sys.stderr)
    print("Try running: pip install PyQt6 vosk sounddevice numpy", file=sys.stderr)
    sys.exit(1)
# -----------------------------------------

# --- גיליון סגנון (ללא שינוי) ---
DARK_STYLE = """
    QWidget { background-color: #2E3440; color: #ECEFF4; font-size: 10pt; }
    QMainWindow { background-color: #2E3440; }
    QTextEdit { background-color: #3B4252; border: 1px solid #4C566A; border-radius: 4px; color: #D8DEE9; padding: 5px; }
    QPushButton { background-color: #5E81AC; color: #ECEFF4; border: none; padding: 8px 12px; border-radius: 4px; font-weight: bold; }
    QPushButton:hover { background-color: #81A1C1; }
    QPushButton:pressed { background-color: #4C566A; }
    QPushButton#sourceButton:checked { background-color: #88C0D0; color: #2E3440; font-weight: bold; border: 1px solid #ECEFF4; }
    QStatusBar { background-color: #3B4252; color: #D8DEE9; }
    QStatusBar::item { border: none; }
    QStatusBar QLabel { background-color: transparent; color: #D8DEE9; padding-left: 5px; }
    QComboBox { background-color: #4C566A; border: 1px solid #5E81AC; border-radius: 4px; padding: 5px; min-width: 6em; }
    QComboBox:hover { border: 1px solid #81A1C1; }
    QComboBox QAbstractItemView { background-color: #3B4252; border: 1px solid #4C566A; selection-background-color: #5E81AC; color: #D8DEE9; outline: 0px; }
    QLabel { color: #D8DEE9; padding-right: 5px; }
    QProgressBar { background-color: #4C566A; border: 1px solid #5E81AC; border-radius: 4px; text-align: center; color: #ECEFF4; height: 10px; }
    QProgressBar::chunk { background-color: #88C0D0; border-radius: 3px; margin: 0.5px; }
    QPushButton#fontButton, QPushButton#aboutButton { padding: 5px 8px; font-weight: normal; min-width: 30px; }
"""

# === מחלקת Backend (AudioProcessor - ללא שינוי פונקציונלי כרגע) ===
# נשאיר אותה כאן, אבל לא נפעיל אותה מהממשק בשלב זה
class AudioProcessor(QObject):
    text_recognized = pyqtSignal(str, bool); status_update = pyqtSignal(str)
    level_update = pyqtSignal(int); error_occurred = pyqtSignal(str)
    processing_stopped = pyqtSignal()
    import numpy as np

    def __init__(self, model_path=None, samplerate=16000, channels=1, dtype='int16', blocksize=8192):
        super().__init__()
        self.model_path = model_path; self.samplerate = samplerate; self.channels = channels; self.dtype = dtype; self.blocksize = blocksize
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.stream = None; self.model = None; self.recognizer = None
        if self.model_path: self._load_model() # ניסיון טעינה אם סופק נתיב

    def _load_model(self):
        print(f"### DEBUG ### AP: Attempting to load model: {self.model_path}")
        if not self.model_path or not os.path.exists(self.model_path):
             self.error_occurred.emit(f"Model path invalid or not set: {self.model_path}"); self.model = None; return
        try:
            self.status_update.emit(f"Loading model: {os.path.basename(self.model_path)}..."); QApplication.processEvents()
            vosk.SetLogLevel(-1); self.model = vosk.Model(self.model_path)
            self.status_update.emit("Model loaded."); self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
            print("### DEBUG ### AP: Model loaded, recognizer created.")
        except Exception as e: self.error_occurred.emit(f"Error loading model: {e}"); self.model = None

    def is_model_loaded(self): return self.model is not None and self.recognizer is not None
    def is_running(self): return self.worker_thread is not None and self.worker_thread.is_alive()

    def start_processing(self, _device_index=None): # Mark unused parameter
        print(f"### DEBUG ### AP: start_processing called (LOGIC CURRENTLY DISABLED)")
        # --- מנוטרל זמנית ---
        if self.is_running(): self.status_update.emit("Already running."); return
        if not self.is_model_loaded(): self.error_occurred.emit("Vosk model not loaded."); return
        self.stop_event.clear(); self.q = queue.Queue()
        try:
            self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
            self.worker_thread = threading.Thread(target=self._vosk_worker, args=(self.recognizer,)); self.worker_thread.start()
            self.stream = sd.InputStream(samplerate=self.samplerate, channels=self.channels, dtype=self.dtype, blocksize=self.blocksize, callback=self._audio_callback)
            self.stream.start(); self.status_update.emit("Listening (Vosk)...")
        except Exception as e: self.error_occurred.emit(f"Error starting audio stream: {e}"); self.stop_processing()
        # ---------------------

    def stop_processing(self):
        print("### DEBUG ### AP: stop_processing called (LOGIC CURRENTLY DISABLED)")
        # --- מנוטרל זמנית ---
        self.status_update.emit("Stopping...")
        if self.stream:
            try: self.stream.stop(); self.stream.close()
            except Exception as e: print(f"Error stopping stream: {e}")
            self.stream = None
        if self.worker_thread and self.worker_thread.is_alive(): self.stop_event.set()
        else: self.processing_stopped.emit()
        # ---------------------
        # נשלח את האות ידנית כדי שהממשק יתעדכן
        self.processing_stopped.emit()


    def _audio_callback(self, _indata, _frames, _time, _status): pass # לא יופעל כרגע, mark unused parameters
    def _vosk_worker(self, _recognizer_instance): pass # לא יופעל כרגע, mark unused parameter

    def _audio_callback(self, indata, _frames, _time, _status):
        import numpy as np
        # Calculate audio level (RMS)
        level = np.sqrt(np.mean(indata**2)) * 100  # Scale to 0-100
        self.level_update.emit(int(level))

    def _vosk_worker(self, recognizer_instance):
        """Runs in a separate thread, takes audio from the queue and processes with Vosk."""
        print("### DEBUG ### AP: Vosk worker thread starting...")
        recognizer_instance.SetWords(True)  # Optional: Enable word-level information

        while not self.stop_event.is_set():
            try:
                data = self.q.get(timeout=0.1)
                if recognizer_instance.AcceptWaveform(data.tobytes()):
                    result_json = recognizer_instance.Result()
                    result_dict = json.loads(result_json)
                    text = result_dict.get('text', '')
                    if text:
                        print(f"### DEBUG ### AP: Final result: {text}")
                        self.text_recognized.emit(text, True)
                else:
                    partial_json = recognizer_instance.PartialResult()
                    partial_dict = json.loads(partial_json)
                    partial_text = partial_dict.get('partial', '')
                    if partial_text:
                        print(f"### DEBUG ### AP: Partial result: {partial_text}")
                        self.text_recognized.emit(partial_text, False)
                self.q.task_done()

            except queue.Empty:
                continue  # Queue was empty, continue in the loop
            except Exception as e:
                print(f"### DEBUG ### AP: Error in Vosk worker: {e}")
                self.error_occurred.emit(f"Vosk worker error: {e}")
                break

        # Final result processing before thread closes
        final_result_json = recognizer_instance.FinalResult()
        final_result_dict = json.loads(final_result_json)
        final_text = final_result_dict.get('text', '')
        if final_text:
            print(f"### DEBUG ### AP: Final result (worker closing): {final_text}")
            self.text_recognized.emit(final_text, True)
        print("### DEBUG ### AP: Vosk worker thread finished.")


# === מחלקת GUI ראשית (עם חיבורים מנוטרלים חלקית) ===
class TranscriptionApp(QMainWindow):
    DEFAULT_MIC_INDEX = 1
    SYSTEM_AUDIO_INDEX = 5 # שנה לפי הצורך

    # !!! עדכן את הנתיב למודל Vosk המקומי היחיד שלך !!!
    LOCAL_VOSK_MODEL_PATH = "model/vosk-model-small-en-us-0.15"

    def __init__(self):
        super().__init__()
        print("### DEBUG ### TranscriptionApp __init__ starting.")
        self.current_font_size = 10
        self.is_listening = False
        self.last_partial_text = ""
        self.selected_audio_device_index = self.DEFAULT_MIC_INDEX
        self.selected_stt_engine = "vosk"
        self.translate_enabled = False

        # בדיקה אם המודל קיים, רק לצורך הצגת אזהרה והשבתת כפתור
        self.local_vosk_model_exists = os.path.exists(self.LOCAL_VOSK_MODEL_PATH)
        if not self.local_vosk_model_exists:
             print(f"WARNING: Local Vosk model not found at {self.LOCAL_VOSK_MODEL_PATH}. 'Local Vosk' option will be disabled.", file=sys.stderr)

        # --- אתחול Backend (ללא טעינה מיידית) ---
        # ניצור מופע, אבל לא נקרא לטעינת מודל מכאן
        self.audio_processor = AudioProcessor(self.LOCAL_VOSK_MODEL_PATH if self.local_vosk_model_exists else None)

        print("### DEBUG ### Initializing GUI...")
        self._init_ui() # בניית הממשק
        print("### DEBUG ### Connecting signals...")
        self._connect_signals() # חיבור האותות
        print("### DEBUG ### GUI Initialized.")
        self.mic_audio_button.setChecked(True)
        self.vosk_button.setChecked(True)
        # --- הסרת טעינת מודל ברירת מחדל מוקדמת ---
        # self._update_start_button_state() # נקרא בסוף _init_ui

    def _init_ui(self):
        # ... (קוד בניית הממשק כמו בתשובה הקודמת - ללא שינוי) ...
        self.setWindowTitle("Real-time Transcription & Translation")
        self.setGeometry(200, 200, 800, 550); self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15); self.main_layout.setSpacing(10)
        self.top_config_layout = QHBoxLayout(); self.source_label = QLabel("Audio Source:")
        self.system_audio_button = QPushButton("System Audio"); self.system_audio_button.setCheckable(True); self.system_audio_button.setAutoExclusive(True); self.system_audio_button.setObjectName("sourceButton")
        self.mic_audio_button = QPushButton("Microphone"); self.mic_audio_button.setCheckable(True); self.mic_audio_button.setAutoExclusive(True); self.mic_audio_button.setObjectName("sourceButton")
        self.source_button_group = QButtonGroup(self); self.source_button_group.addButton(self.system_audio_button); self.source_button_group.addButton(self.mic_audio_button)
        self.stt_label = QLabel("STT Engine:"); self.vosk_button = QPushButton("Local Vosk"); self.vosk_button.setCheckable(True); self.vosk_button.setAutoExclusive(True); self.vosk_button.setObjectName("sourceButton")
        self.whisper_button = QPushButton("Whisper API"); self.whisper_button.setCheckable(True); self.whisper_button.setAutoExclusive(True); self.whisper_button.setObjectName("sourceButton")
        self.stt_button_group = QButtonGroup(self); self.stt_button_group.addButton(self.vosk_button); self.stt_button_group.addButton(self.whisper_button)
        if not self.local_vosk_model_exists: self.vosk_button.setEnabled(False); self.vosk_button.setToolTip("Model not found")
        self.top_config_layout.addWidget(self.source_label); self.top_config_layout.addWidget(self.system_audio_button); self.top_config_layout.addWidget(self.mic_audio_button); self.top_config_layout.addStretch(1)
        self.top_config_layout.addWidget(self.stt_label); self.top_config_layout.addWidget(self.vosk_button); self.top_config_layout.addWidget(self.whisper_button)
        self.bottom_config_layout = QHBoxLayout(); self.language_label = QLabel("Source Language:"); self.language_combo = QComboBox()
        self.available_languages = {"en-us": "English", "it": "Italian", "ar": "Arabic", "es": "Spanish","fr": "French", "de": "German", "ru": "Russian", "pt": "Portuguese","zh": "Chinese", "he": "Hebrew"}
        for lang_code, lang_name in self.available_languages.items(): self.language_combo.addItem(lang_name, userData=lang_code)
        english_index = self.language_combo.findData("en-us");
        if english_index >= 0: self.language_combo.setCurrentIndex(english_index)
        self.translate_checkbox = QCheckBox("Translate to Hebrew"); self.bottom_config_layout.addWidget(self.language_label); self.bottom_config_layout.addWidget(self.language_combo, 1); self.bottom_config_layout.addStretch(1); self.bottom_config_layout.addWidget(self.translate_checkbox)
        self.level_meter = QProgressBar(); self.level_meter.setRange(0, 100); self.level_meter.setValue(0); self.level_meter.setTextVisible(False)
        self.text_output = QTextEdit(); self.text_output.setReadOnly(True); self.text_output.setPlaceholderText("Recognized text will appear here...")
        font = self.text_output.font(); font.setPointSize(self.current_font_size); self.text_output.setFont(font)
        self.action_layout = QHBoxLayout(); self.start_stop_button = QPushButton("▶ Start Listening")
        self.decrease_font_button = QPushButton("-"); self.decrease_font_button.setObjectName("fontButton")
        self.increase_font_button = QPushButton("+"); self.increase_font_button.setObjectName("fontButton")
        self.clear_button = QPushButton("Clear Text"); self.copy_button = QPushButton("Copy Text")
        self.about_button = QPushButton("?"); self.about_button.setObjectName("aboutButton"); self.about_button.setToolTip("About this application")
        self.action_layout.addWidget(self.start_stop_button); self.action_layout.addStretch(1); self.action_layout.addWidget(QLabel("Font:"))
        self.action_layout.addWidget(self.decrease_font_button); self.action_layout.addWidget(self.increase_font_button); self.action_layout.addSpacing(20)
        self.action_layout.addWidget(self.clear_button); self.action_layout.addWidget(self.copy_button); self.action_layout.addWidget(self.about_button)
        self.main_layout.addLayout(self.top_config_layout); self.main_layout.addLayout(self.bottom_config_layout); self.main_layout.addWidget(self.level_meter); self.main_layout.addWidget(self.text_output, 1); self.main_layout.addLayout(self.action_layout)
        self.setCentralWidget(self.central_widget)
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar); self.status_label = QLabel("Ready."); self.status_bar.addWidget(self.status_label)
        self._update_start_button_state() # עדכון מצב כפתור התחלה בסוף בניית הממשק

    def _connect_signals(self):
        # --- חיבורים לפונקציות שקיימות או שנוסיף להן הגדרה ריקה ---
        self.system_audio_button.clicked.connect(lambda: self.set_audio_source(self.SYSTEM_AUDIO_INDEX, "System Audio"))
        self.mic_audio_button.clicked.connect(lambda: self.set_audio_source(self.DEFAULT_MIC_INDEX, "Microphone"))
        self.vosk_button.clicked.connect(lambda: self.set_stt_engine("vosk"))
        self.whisper_button.clicked.connect(lambda: self.set_stt_engine("whisper"))
        self.translate_checkbox.stateChanged.connect(self.set_translation_state)
        self.start_stop_button.clicked.connect(self.toggle_listening) # מחובר לגרסה המפושטת
        self.clear_button.clicked.connect(self.text_output.clear)
        self.copy_button.clicked.connect(self.copy_text_to_clipboard)
        self.increase_font_button.clicked.connect(self.increase_font_size) # צריך הגדרה
        self.decrease_font_button.clicked.connect(self.decrease_font_size) # צריך הגדרה
        self.about_button.clicked.connect(self.show_about_dialog) # צריך הגדרה
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        # --- חיבורי Backend (חלקם לא יופעלו כרגע כי ה-Backend מנוטרל) ---
        self.audio_processor.text_recognized.connect(self.handle_recognition_result)
        self.audio_processor.status_update.connect(self.update_status)
        self.audio_processor.level_update.connect(self.update_level_meter)
        self.audio_processor.error_occurred.connect(self.display_error)
        self.audio_processor.processing_stopped.connect(self.on_processing_stopped)
        print("### DEBUG ### Signals connected.")

    # --- Slots ופונקציות Helper ---

    # --- חדש: הגדרות ריקות לפונקציות החסרות ---
    def increase_font_size(self):
        print("### DEBUG ### Increase Font clicked (Not Implemented Yet)")
        # נוסיף כאן את הלוגיקה בהמשך
        self.current_font_size += 1; font = self.text_output.font(); font.setPointSize(self.current_font_size); self.text_output.setFont(font) # הוספנו את הלוגיקה בכל זאת

    def decrease_font_size(self):
        print("### DEBUG ### Decrease Font clicked (Not Implemented Yet)")
        # נוסיף כאן את הלוגיקה בהמשך
        if self.current_font_size > 7: self.current_font_size -= 1; font = self.text_output.font(); font.setPointSize(self.current_font_size); self.text_output.setFont(font) # הוספנו את הלוגיקה בכל זאת

    def show_about_dialog(self):
        print("### DEBUG ### About clicked (Not Implemented Yet)")
        # נוסיף כאן את הלוגיקה בהמשך
        QMessageBox.about(self, "About", "<b>Real-time Transcription & Translation</b><br><br>Version: 0.4 (UI Only Stage)<br>Using Vosk/Whisper(TBD), Google Translate(TBD), PyQt6, etc.") # הוספנו את הלוגיקה בכל זאת
    # ------------------------------------------

    def set_audio_source(self, device_index, source_name):
        # ... (כמו קודם) ...
        if not self.is_listening: self.selected_audio_device_index = device_index; self.update_status(f"Audio source: {source_name}"); print(f"### DEBUG ### Audio source index set to: {device_index}")
        else: self.update_status("Cannot change source while listening."); # החזרת כפתור למצב הקודם
        if self.selected_audio_device_index == self.DEFAULT_MIC_INDEX: self.mic_audio_button.setChecked(True)
        elif self.selected_audio_device_index == self.SYSTEM_AUDIO_INDEX: self.system_audio_button.setChecked(True)


    def set_stt_engine(self, engine_name):
        # ... (כמו קודם) ...
        if not self.is_listening:
            self.selected_stt_engine = engine_name; self.update_status(f"STT Engine: {engine_name.replace('_', ' ').title()}")
            print(f"### DEBUG ### STT Engine set to: {engine_name}"); self._update_start_button_state()
        else: self.update_status("Cannot change STT engine while listening."); # החזרת כפתור למצב הקודם
        if self.selected_stt_engine == "vosk": self.vosk_button.setChecked(True)
        elif self.selected_stt_engine == "whisper": self.whisper_button.setChecked(True)


    def set_translation_state(self, state):
        # ... (כמו קודם) ...
        self.translate_enabled = (state == Qt.CheckState.Checked.value); print(f"### DEBUG ### Translate enabled: {self.translate_enabled}")
        if self.translate_enabled: self.update_status("Translation to Hebrew enabled.")
        else: self.update_status("Translation disabled.")


    def on_language_changed(self):
        # ... (כמו קודם) ...
        selected_lang_name = self.language_combo.currentText(); selected_lang_code = self.language_combo.currentData()
        self.update_status(f"Source language set to: {selected_lang_name} ({selected_lang_code})"); print(f"### DEBUG ### Source language changed to: {selected_lang_code}")


    def _update_start_button_state(self):
        """בודק אם ניתן לאפשר את כפתור ההתחלה."""
        can_start = True
        # נטרל אם Vosk נבחר והמודל לא קיים
        if self.selected_stt_engine == "vosk" and not self.local_vosk_model_exists:
            can_start = False
            # עדכן סטטוס רק אם זה המצב היחיד שמונע התחלה
            if not self.is_listening: self.update_status("Cannot start: Vosk model not found.")
        # הוסף כאן בדיקות ל-Whisper API Key בעתיד
        self.start_stop_button.setEnabled(can_start)


    def toggle_listening(self):
        """מפעיל או מפסיק את ההאזנה (כרגע רק משנה UI)."""
        print("### DEBUG ### toggle_listening called.")
        if self.is_listening:
            print("### DEBUG ### Currently listening, stopping UI.")
            # --- קריאה ל-Backend מנוטרלת ---
            if self.selected_stt_engine == "vosk":
                self.audio_processor.stop_processing()
            elif self.selected_stt_engine == "whisper":
                # לוגיקה עתידית לעצירת Whisper
                self.on_processing_stopped() # הפעלה ידנית של הסלוט לעדכון UI
            # -----------------------------
            # במקום הקוד למעלה, פשוט נעדכן את הממשק
            self.is_listening = False # עדכון מיידי של המצב הפנימי
            self.on_processing_stopped() # קריאה לעדכון שאר ה-UI
            self.start_stop_button.setEnabled(True) # הפעלת הכפתור מחדש מייד
        else:
            print(f"### DEBUG ### Not listening, starting UI for engine: {self.selected_stt_engine}")
            # --- קריאה ל-Backend מנוטרלת ---
            if self.selected_stt_engine == "vosk":
                if not self.audio_processor.is_model_loaded():
                     self.display_error("Cannot start: Vosk model not loaded.")
                     return
                self.audio_processor.start_processing(self.selected_audio_device_index)
            elif self.selected_stt_engine == "whisper":
                print("### DEBUG ### Starting Whisper Processing (Not Implemented)")
                self.update_status("Whisper processing not implemented yet.")
                # לא נתחיל להאזין באמת
                return # אולי נצא מכאן כדי שהמצב לא ישתנה למאזין
            # -----------------------------

            # רק נשנה את מצב הממשק
            self.is_listening = True
            self.start_stop_button.setText("⏹ Stop Listening")
            self.update_status(f"Listening ({self.selected_stt_engine} - SIMULATED)...") # הדגשה שזה מדומה
            # נטרול פקדי הגדרה
            self.system_audio_button.setEnabled(False); self.mic_audio_button.setEnabled(False)
            self.vosk_button.setEnabled(False); self.whisper_button.setEnabled(False)
            self.language_combo.setEnabled(False); self.translate_checkbox.setEnabled(False)


    def on_processing_stopped(self):
        # ... (כמו קודם, רק עם הדפסה שונה) ...
        print("### DEBUG ### on_processing_stopped slot called (UI update).")
        self.is_listening = False; self.start_stop_button.setText("▶ Start Listening")
        self.update_status("Stopped."); self.level_meter.setValue(0)
        self.system_audio_button.setEnabled(True); self.mic_audio_button.setEnabled(True)
        # אפשר את הכפתור של Vosk רק אם המודל קיים
        self.vosk_button.setEnabled(self.local_vosk_model_exists)
        self.whisper_button.setEnabled(True)
        self.language_combo.setEnabled(True); self.translate_checkbox.setEnabled(True)
        self._update_start_button_state()


    def handle_recognition_result(self, text, is_final):
        # ... (כמו קודם, יופעל רק אם נפעיל את ה-backend) ...
        print(f"### DEBUG ### handle_recognition_result: '{text}', final: {is_final}")
        original_text = text
        translated_text = None
        if self.translate_enabled and is_final and original_text:
            print(f"### DEBUG ### Translation requested for: '{original_text}' (Not Implemented)")
        cursor = self.text_output.textCursor(); cursor.movePosition(cursor.MoveOperation.End)
        if self.last_partial_text and self.text_output.toPlainText().endswith(self.last_partial_text):
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.KeepAnchor, len(self.last_partial_text)); cursor.removeSelectedText()
        text_to_display = original_text
        if translated_text: text_to_display += f"  ->  [{translated_text}]"
        if is_final: cursor.insertText(text_to_display + "\n"); self.last_partial_text = ""
        else: cursor.insertText(original_text); self.last_partial_text = original_text
        self.text_output.ensureCursorVisible()


    def update_status(self, message): self.status_label.setText(message); self.status_label.setStyleSheet("")
    def update_level_meter(self, level): self.level_meter.setValue(level)
    def display_error(self, error_message):
        print(f"### DEBUG ### display_error slot called: '{error_message}'")
        self.status_label.setText(f"Error: {error_message}"); self.status_label.setStyleSheet("color: #BF616A;")
        print(f"Error: {error_message}", file=sys.stderr)
    def copy_text_to_clipboard(self):
        clipboard = QApplication.clipboard() # Correct indentation
        if clipboard is None:
            self.display_error("Could not access clipboard.")
            return
        clipboard.setText(self.text_output.toPlainText())
        self.update_status("Text copied.")
    def closeEvent(self, event):
        print("### DEBUG ### Close event triggered.")
        # לא צריך לעצור את ה-backend כי הוא לא רץ
        print("### DEBUG ### Accepting close event.")
        event.accept()
    def _populate_audio_devices(self): print("### DEBUG ### _populate_audio_devices (simplified)") ; pass
    def _find_lang_code_from_path(self, path): # פישוט זמני
        if path and "en-us" in os.path.basename(path): return "en-us"
        return "en-us"


# --- חלק ראשי ---
if __name__ == "__main__":
    print("### DEBUG ### Starting main execution block.")
    # ... (בדיקת ספריות כמו קודם) ...
    try: print(f"### DEBUG ### Sounddevice version: {sd.__version__}"); print(f"### DEBUG ### Vosk available: {'vosk' in sys.modules}")
    except NameError: print("### DEBUG ### Core libraries not defined.", file=sys.stderr); sys.exit(1)

    app = QApplication(sys.argv)
    print("### DEBUG ### QApplication created.")
    try:
        app.setStyleSheet(DARK_STYLE); print("### DEBUG ### Stylesheet applied.")
        print("### DEBUG ### Creating main window...")
        main_window = TranscriptionApp() # יצירת החלון הראשי
        print("### DEBUG ### Showing main window...")
        main_window.show() # הצגת החלון
        print("### DEBUG ### Starting application event loop...")
        exit_code = app.exec() # הפעלת לולאת האירועים
        print(f"### DEBUG ### Application event loop finished with exit code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        error_msg = f"FATAL ERROR during app initialization or execution: {e}"; print(error_msg, file=sys.stderr)
        try: QMessageBox.critical(None, "Fatal Error", f"{error_msg}\n\nThe application will now close.")
        except Exception as mb_error: print(f"Could not display graphical error message: {mb_error}", file=sys.stderr)
        sys.exit(1)
