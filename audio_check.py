import os
import sys
import tempfile
import subprocess
import wave
import numpy as np
import shutil
from pathlib import Path

def analyze_audio(filepath):
    temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
    os.close(temp_fd)
    try:
        cmd = ['afconvert', filepath, '-f', 'WAVE', '-d', 'LEI16@44100', '-c', '1', temp_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        with wave.open(temp_path, 'rb') as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            
            skip_frames = int(framerate * 15)
            target_frames = min(nframes - skip_frames, int(framerate * 90))
            
            if nframes > skip_frames:
                wf.readframes(skip_frames)
            else:
                target_frames = nframes
                
            audio_data = wf.readframes(target_frames)
            
        data = np.frombuffer(audio_data, dtype=np.int16)
        
        if len(data) == 0:
            return "Silencio/Vacio"
            
        fft_data = np.abs(np.fft.rfft(data))
        freqs = np.fft.rfftfreq(len(data), d=1.0/framerate)
        
        max_power = np.max(fft_data)
        threshold = max_power * 0.001 
        
        significant_freqs = freqs[fft_data > threshold]
        if len(significant_freqs) == 0:
            return "Desconocido"
            
        max_freq = np.max(significant_freqs)
        
        if max_freq < 16500:
            return f"Baja Calidad (~128kbps) | Corte: {int(max_freq)}Hz"
        elif max_freq < 18500:
            return f"Calidad Media (~192kbps) | Corte: {int(max_freq)}Hz"
        else:
            return f"Sana | Corte: {int(max_freq)}Hz"
            
    except Exception as e:
        return f"Error: {e}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def get_unique_filename(destination_dir, filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    while os.path.exists(os.path.join(destination_dir, new_filename)):
        new_filename = f"{name}_{counter}{ext}"
        counter += 1
    return new_filename
    
def main():
    base_dir = "/Volumes/RANDY-M2B/MUSIC/2024"
    fake_folder = os.path.join(base_dir, "FAKE-AUDIO")
    
    if not os.path.exists(fake_folder):
        os.makedirs(fake_folder)
        
    log_file = os.path.join(fake_folder, "movimientos.log")
    
    # Encontrar todas las carpetas que empiezan con "Download"
    download_dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if d.lower().startswith('download') and os.path.isdir(os.path.join(base_dir, d))]
    
    if not download_dirs:
        print("No se encontraron carpetas de descargas.")
        return
        
    print(f"Carpetas a analizar: {len(download_dirs)}")
    for d in download_dirs:
        print(f" - {os.path.basename(d)}")
    print("\nIniciando analisis y moviendo fakes a FAKE-AUDIO...")
    
    valid_extensions = ('.mp3', '.wav', '.aif', '.aiff', '.flac', '.m4a')
    moved_count = 0
    total_count = 0
    
    with open(log_file, "a") as log:
        for target_dir in download_dirs:
            for root, dirs, files in os.walk(target_dir):
                for f in files:
                    if f.lower().endswith(valid_extensions) and not f.startswith('.'):
                        total_count += 1
                        fullpath = os.path.join(root, f)
                        
                        quality = analyze_audio(fullpath)
                        
                        if "Baja" in quality or "Media" in quality:
                            # Move it
                            safe_name = get_unique_filename(fake_folder, f)
                            dest_path = os.path.join(fake_folder, safe_name)
                            
                            try:
                                shutil.move(fullpath, dest_path)
                                log_entry = f"MOVIDO: {f} \n   DESDE: {fullpath}\n   HACIA: {dest_path}\n   MOTIVO: {quality}\n\n"
                                log.write(log_entry)
                                log.flush()
                                print(f"[FAKE DETECTADO] Movido: {f}")
                                moved_count += 1
                            except Exception as e:
                                print(f"Error moviendo {f}: {e}")
                                
    print("\n" + "="*60)
    print("REPORTE FINAL:")
    print(f"Total de archivos analizados: {total_count}")
    print(f"Total de archivos FAKE movidos: {moved_count}")
    print(f"Todos los fakes se encuentran en: {fake_folder}")
    print(f"Log de movimientos y ubicaciones originales: {log_file}")
    print("="*60)

if __name__ == "__main__":
    main()
