import sounddevice as sd
import numpy as np
import vosk
import json
import sys
import os
import queue # <-- ייבוא התור
import threading # <-- ייבוא תהליכונים
import time # <-- נייבא זמן להמחשה

# --- הגדרות ---
MODEL_PATH = "app/model/vosk-model-small-en-us-0.15" # <-- ודא שזה הנתיב המדויק למודל!
SAMPLERATE = 16000
CHANNELS = 1
DTYPE = 'int16'
BLOCK_SIZE = 8192 # גודל בלוק סביר להתחיל איתו בגישה זו

# --- בדיקה מקדימה של נתיב המודל ---
if not os.path.exists(MODEL_PATH):
    print(f"שגיאה: תיקיית המודל '{MODEL_PATH}' לא נמצאה.")
    print("אנא הורד מודל מאתר Vosk, חלץ אותו, ועדכן את משתנה MODEL_PATH בקוד לנתיב הנכון.")
    sys.exit(1)

# --- יצירת תור ואירוע עצירה ---
q = queue.Queue() # התור שיכיל את נתוני האודיו
stop_event = threading.Event() # אירוע שיסמן לתהליכון העיבוד מתי לעצור

# --- טעינת מודל Vosk (בלי יצירת מזהה עדיין) ---
try:
    print(f"טוען מודל Vosk מנתיב: '{os.path.abspath(MODEL_PATH)}'...")
    vosk.SetLogLevel(-1)
    model = vosk.Model(MODEL_PATH)
    print("המודל נטען בהצלחה.")
except Exception as e:
    print(f"שגיאה בטעינת המודל: {e}")
    sys.exit(1)

# --- פונקציית Callback (רק מכניסה לתור) ---
def audio_callback(indata, frames, time, status):
    """רק מכניס את נתוני האודיו לתור."""
    if status:
        print(status, file=sys.stderr)
        return
    # חשוב להשתמש ב-copy() כדי שהנתונים לא יידרסו לפני שהמעבד מספיק לקחת אותם
    q.put(indata.copy())

# --- פונקציית תהליכון העיבוד (Vosk Worker) ---
def vosk_worker():
    """רץ בתהליכון נפרד, לוקח אודיו מהתור ומעבד עם Vosk."""
    print("תהליכון Vosk מתחיל...")
    # ניצור את המזהה כאן, בתוך התהליכון שישתמש בו
    recognizer = vosk.KaldiRecognizer(model, SAMPLERATE)
    recognizer.SetWords(True) # אם נרצה גם מידע על מילים בודדות (אופציונלי)

    while not stop_event.is_set():
        try:
            # נסה לקחת פריט מהתור, המתן עד 100 מילישניות אם ריק
            data = q.get(timeout=0.1)

            if recognizer.AcceptWaveform(data.tobytes()):
                result_json = recognizer.Result()
                result_dict = json.loads(result_json)
                text = result_dict.get('text', '')
                if text:
                    print(f"\nסופי: {text} (גודל תור: {q.qsize()})") # הדפסת גודל התור להמחשה
            else:
                partial_json = recognizer.PartialResult()
                partial_dict = json.loads(partial_json)
                partial_text = partial_dict.get('partial', '')
                if partial_text:
                    print(f"\rחלקי: {partial_text} (גודל תור: {q.qsize()})   ", end='')

            q.task_done() # מסמן שהפריט טופל (חשוב אם משתמשים ב-q.join() בהמשך)

        except queue.Empty:
            # התור היה ריק, ממשיכים בלולאה (או בודקים אם צריך לעצור)
            continue
        except Exception as e:
            print(f"שגיאה בתהליכון Vosk: {e}")
            # במקרה של שגיאה חמורה, אולי נרצה לעצור את הכל
            # stop_event.set()

    # --- סיום התהליכון ---
    # קבלת תוצאה סופית אחרונה לפני שהתהליכון נסגר
    final_result_json = recognizer.FinalResult()
    final_result_dict = json.loads(final_result_json)
    final_text = final_result_dict.get('text', '')
    if final_text:
        print(f"\nסופי אחרון (Vosk Worker): {final_text}")
    print("תהליכון Vosk הסתיים.")


# --- חלק ראשי ---
if __name__ == "__main__":
    # יצירה והפעלה של תהליכון העיבוד
    worker_thread = threading.Thread(target=vosk_worker)
    worker_thread.daemon = True # מאפשר לתוכנית הראשית להיסגר גם אם התהליכון עדיין חי
    worker_thread.start()

    try:
        print(f"\nקצב דגימה: {SAMPLERATE} Hz, גודל בלוק: {BLOCK_SIZE} דגימות")
        print("מתחיל להאזין למיקרופון (לחץ Ctrl+C לעצירה)...")
        # יצירת זרם קלט (InputStream) עם ה-callback הפשוט
        with sd.InputStream(samplerate=SAMPLERATE,
                             channels=CHANNELS,
                             dtype=DTYPE,
                             blocksize=BLOCK_SIZE,
                             callback=audio_callback):
            # התוכנית הראשית ממתינה כאן עד לעצירה
            while not stop_event.is_set():
                 time.sleep(0.1) # אפשר להשאיר את התוכנית הראשית חיה כך

    except KeyboardInterrupt:
        print("\n\nCtrl+C זוהה. מבקש מתהליכון Vosk לעצור...")
        stop_event.set() # סימון לתהליכון העיבוד לעצור

    except Exception as e:
        print(f"\nאירעה שגיאה כללית: {e}")
        stop_event.set() # גם במקרה שגיאה, נבקש לעצור את התהליכון

    finally:
        # המתנה לסיום תהליכון העיבוד (עם Timeout למקרה שנתקע)
        print("ממתין לסיום תהליכון Vosk...")
        worker_thread.join(timeout=2.0) # המתן עד 2 שניות
        if worker_thread.is_alive():
            print("אזהרה: תהליכון Vosk לא הסתיים בזמן.")
        print("התוכנית הראשית מסתיימת.")
