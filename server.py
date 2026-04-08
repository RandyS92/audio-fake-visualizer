import os
import io
import tempfile
import subprocess
import wave
import base64
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Audio Visual Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def analyze_and_plot(filepath: str):
    temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
    os.close(temp_fd)
    
    try:
        # Decode using afconvert to standardize 44.1kHz mono
        cmd = ['afconvert', filepath, '-f', 'WAVE', '-d', 'LEI16@44100', '-c', '1', temp_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        with wave.open(temp_path, 'rb') as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            
            skip_frames = int(framerate * 15)  # skip 15s
            target_frames = min(nframes - skip_frames, int(framerate * 45)) # Analyze 45 seconds for visualization
            
            if nframes > skip_frames:
                wf.readframes(skip_frames)
            else:
                target_frames = nframes
                
            audio_data = wf.readframes(target_frames)
            
        data = np.frombuffer(audio_data, dtype=np.int16)
        
        if len(data) == 0:
            return {"status": "error", "message": "Archivo silencioso/vacío"}
            
        # Analysis math
        fft_data = np.abs(np.fft.rfft(data))
        freqs = np.fft.rfftfreq(len(data), d=1.0/framerate)
        
        max_power = np.max(fft_data)
        threshold = max_power * 0.001 
        
        significant_freqs = freqs[fft_data > threshold]
        max_freq = np.max(significant_freqs) if len(significant_freqs) > 0 else 0
        
        detected_status = "Fake" if max_freq < 18500 else "Sana"
        if max_freq < 16500:
            quality = f"Baja Calidad (~128kbps) | Corte: {int(max_freq)}Hz"
            explanation = "Este archivo corta la frecuencia alrededor de los 16kHz, lo que es característico de los archivos fuertemente comprimidos como MP3 a 128kbps o grabaciones de YouTube. Si el archivo pesa mucho o dice ser Lossless (.wav/.flac), significa que ha sido inflado desde un archivo de mala calidad."
        elif max_freq < 18500:
            quality = f"Calidad Media (~192kbps) | Corte: {int(max_freq)}Hz"
            explanation = "Este archivo recorta sus frecuencias altas de forma moderada (~18kHz). Usualmente es un MP3 a 192kbps."
        else:
            quality = f"Sana | Corte: {int(max_freq)}Hz"
            explanation = "Espectro saludable. Las frecuencias altas se mantienen sólidas demostrando un archivo puro o MP3 a 320kbps real."
            
        # Plotting Spectrogram
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.specgram(data, Fs=framerate, NFFT=2048, noverlap=1024, cmap='inferno')
        ax.set_ylim(0, 22000)
        ax.axis('off')  # No axes
        fig.tight_layout(pad=0)
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        return {
            "status": "success",
            "detected_status": detected_status,
            "quality": quality,
            "explanation": explanation,
            "max_freq": float(max_freq),
            "spectrogram": f"data:image/png;base64,{img_base64}"
        }
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/api/scan_folder")
def scan_folder(path: str):
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="La carpeta no existe")
        
    valid_extensions = ('.mp3', '.wav', '.aif', '.aiff', '.flac', '.m4a')
    files_found = []
    
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.lower().endswith(valid_extensions) and not f.startswith('.'):
                files_found.append({
                    "name": f,
                    "fullpath": os.path.join(root, f)
                })
                
    return {"files": files_found}

@app.get("/api/analyze_file")
def analyze_file(filepath: str):
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
    result = analyze_and_plot(filepath)
    return result

class MoveRequest(BaseModel):
    files: List[str]
    folder_path: str

def get_unique_filename(destination_dir, filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    while os.path.exists(os.path.join(destination_dir, new_filename)):
        new_filename = f"{name}_{counter}{ext}"
        counter += 1
    return new_filename

@app.get("/api/select_folder")
def select_folder():
    try:
        # Pide a macOS que abra la ventana selectora de carpetas nativa
        script = 'POSIX path of (choose folder with prompt "Seleccione la carpeta de música a analizar:")'
        result = subprocess.check_output(['osascript', '-e', script]).decode('utf-8').strip()
        return {"status": "success", "path": result}
    except subprocess.CalledProcessError:
        # El usuario canceló la selección de la carpeta
        return {"status": "canceled"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/move_fakes")
def move_fakes(request: MoveRequest):
    fake_folder = os.path.join(request.folder_path, "FAKE-AUDIO")
    if not os.path.exists(fake_folder):
        os.makedirs(fake_folder)
        
    moved_count = 0
    errors = []
    
    for file_path in request.files:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            safe_name = get_unique_filename(fake_folder, filename)
            dest_path = os.path.join(fake_folder, safe_name)
            try:
                shutil.move(file_path, dest_path)
                moved_count += 1
            except Exception as e:
                errors.append(f"Error moviendo {filename}: {e}")
                
    return {"moved": moved_count, "errors": errors, "fake_folder": fake_folder}
