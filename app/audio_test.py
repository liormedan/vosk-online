import sounddevice as sd
import numpy as np
import sys # כדי לבדוק שגיאות

# פרמטרים רצויים - חשוב שיתאימו למודל Vosk שנשתמש בו בהמשך
SAMPLERATE = 16000  # קצב דגימה - נפוץ למודלי Vosk
CHANNELS = 1        # ערוץ אחד (מונו)
DTYPE = 'int16'     # סוג נתונים - נפוץ למודלי Vosk
BLOCK_SIZE = 1024   # גודל חתיכת אודיו לעיבוד בכל פעם (ניתן לשנות לניסוי)

# פונקציית Callback שתופעל על כל חתיכת אודיו חדשה
def audio_callback(indata, frames, time, status):
    """זו הפונקציה שמופעלת כשמגיע אודיו חדש מהמיקרופון."""
    if status:
        # מדפיס הודעת שגיאה אם קרתה תקלה בזרם האודיו
        print(status, file=sys.stderr)
    # כאן נוסיף בהמשך את הקוד ששולח את האודיו ל-Vosk
    # כרגע רק נדפיס את צורת הנתונים שקיבלנו
    print(f"קבלתי נתוני אודיו בצורה: {indata.shape}")

# בדיקה עיקרית
if __name__ == "__main__":
    try:
        print("מתחיל להאזין למיקרופון...")
        # יצירת זרם קלט (InputStream) עם הפרמטרים ופונקציית ה-callback
        with sd.InputStream(samplerate=SAMPLERATE,
                             channels=CHANNELS,
                             dtype=DTYPE,
                             blocksize=BLOCK_SIZE,
                             callback=audio_callback):
            # נחכה כאן למשך כמה שניות כדי לראות את הפלט
            print("האזנה פעילה למשך 10 שניות...")
            print("לחץ Ctrl+C כדי לעצור מוקדם יותר.")
            sd.sleep(10 * 1000) # המתנה במילי-שניות (10 שניות)
            print("סיום האזנה.")

    except Exception as e:
        print(f"אירעה שגיאה: {e}")
    except KeyboardInterrupt:
        print("\nהמשתמש עצר את התוכנית.")