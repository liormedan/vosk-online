# Vosk Online Transcription and Translation

This project is a real-time transcription and translation application that utilizes the Vosk speech recognition toolkit and the PyQt6 framework for the graphical user interface. The application allows users to transcribe audio input from a microphone or system audio and provides options for translation.

## Project Structure

```
vosk-online
├── app
│   ├── gui_app.py        # Main application code for the transcription and translation app
│   └── __init__.py       # Initialization file for the app package
├── model
│   └── (place your Vosk model files here)  # Directory for Vosk model files
├── requirements.txt       # List of dependencies required for the project
├── .gitignore             # Files and directories to be ignored by Git
└── README.md              # Documentation for the project
```

## Requirements

To run this project, you need to install the following dependencies:

- PyQt6
- Vosk
- sounddevice

You can install the required packages using pip:

```
pip install -r requirements.txt
```

## Usage

1. Place your Vosk model files in the `model` directory.
2. Run the application by executing the `gui_app.py` file:

```
python app/gui_app.py
```

3. Select your audio source and STT engine from the GUI.
4. Click "Start Listening" to begin transcription.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.